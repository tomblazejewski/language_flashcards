"""FSRS study engine service."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, cast

from fsrs import Card as FsrsCard
from fsrs import Rating, Scheduler
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.flashcard import Flashcard
from app.models.review import ReviewConfig, ReviewLog

_scheduler = Scheduler()

# Map API rating int → FSRS Rating enum
_RATING_MAP = {
    1: Rating.Again,
    2: Rating.Hard,
    3: Rating.Good,
    4: Rating.Easy,
}


def _fsrs_card_from_log(log: ReviewLog) -> FsrsCard:
    """Reconstruct an FSRS Card from the JSON stored in a ReviewLog."""
    if log.fsrs_state:
        return FsrsCard.from_dict(cast(Any, log.fsrs_state))
    return FsrsCard()


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)



async def _bulk_ensure_review_logs(
    course_id: str,
    review_config_id: str,
    user_id: str,
    db: AsyncSession,
) -> None:
    """
    Ensure every flashcard in *course_id* has a ReviewLog row for the given
    (review_config_id, user_id).

    Uses two queries — one to fetch flashcard IDs, one to find already-covered
    IDs — then bulk-inserts missing rows in a single flush.  O(1) round trips
    regardless of course size.
    """
    # Fetch only the IDs we need — avoid loading full Flashcard objects
    fc_id_result = await db.execute(select(Flashcard.id).where(Flashcard.course_id == course_id))
    flashcard_ids = [row[0] for row in fc_id_result.all()]
    if not flashcard_ids:
        return

    # Fetch existing log rows for this config+user in one query
    existing_result = await db.execute(
        select(ReviewLog.flashcard_id).where(
            ReviewLog.review_config_id == review_config_id,
            ReviewLog.user_id == user_id,
            ReviewLog.flashcard_id.in_(flashcard_ids),
        )
    )
    covered: set[str] = {row[0] for row in existing_result.all()}

    # Bulk-create rows for any flashcard not yet covered
    missing = [fc_id for fc_id in flashcard_ids if fc_id not in covered]
    if missing:
        new_logs = []
        for fc_id in missing:
            card = FsrsCard()
            new_logs.append(
                ReviewLog(
                    flashcard_id=fc_id,
                    review_config_id=review_config_id,
                    user_id=user_id,
                    fsrs_state=cast(Any, card.to_dict()),
                    due_date=card.due,
                    reps=0,
                )
            )
        db.add_all(new_logs)
        await db.flush()


async def get_next_card(
    review_config: ReviewConfig,
    user_id: str,
    db: AsyncSession,
) -> tuple[ReviewLog, Flashcard] | None:
    """
    Return the (ReviewLog, Flashcard) pair for the card most overdue (or next
    due) for this user/config.  Initialises ReviewLog rows for any flashcards
    that have never been seen (bulk, O(1) queries).

    Selection is done entirely in SQL:

    1. Try to find the earliest overdue-or-unseen log
       (``due_date IS NULL OR due_date <= now``).
    2. If none are due yet, return the log with the soonest upcoming due date.

    This is O(log n) in the DB index rather than O(n) in Python.
    """
    # Ensure every flashcard in the course has a ReviewLog row
    await _bulk_ensure_review_logs(review_config.course_id, review_config.id, user_id, db)

    now = _utc_now()
    base_filter = (
        ReviewLog.review_config_id == review_config.id,
        ReviewLog.user_id == user_id,
    )

    # 1. Earliest overdue (or never-seen) card
    overdue_result = await db.execute(
        select(ReviewLog)
        .where(
            *base_filter,
            (ReviewLog.due_date.is_(None)) | (ReviewLog.due_date <= now),
        )
        .order_by(ReviewLog.due_date.asc().nullsfirst())
        .limit(1)
    )
    log = overdue_result.scalar_one_or_none()

    # 2. Fallback: soonest upcoming card
    if log is None:
        upcoming_result = await db.execute(
            select(ReviewLog).where(*base_filter).order_by(ReviewLog.due_date.asc()).limit(1)
        )
        log = upcoming_result.scalar_one_or_none()

    if log is None:
        return None

    # Point-query for the flashcard (avoids joining a potentially large table)
    fc_result = await db.execute(select(Flashcard).where(Flashcard.id == log.flashcard_id))
    flashcard = fc_result.scalar_one_or_none()
    if flashcard is None:
        return None

    return log, flashcard


async def submit_review(
    log: ReviewLog,
    rating_int: int,
    db: AsyncSession,
) -> ReviewLog:
    """Apply an FSRS rating to a ReviewLog and persist the updated state."""
    card = _fsrs_card_from_log(log)
    fsrs_rating = _RATING_MAP[rating_int]

    updated_card, _ = _scheduler.review_card(card, fsrs_rating)

    log.fsrs_state = cast(Any, updated_card.to_dict())
    log.due_date = updated_card.due
    log.last_reviewed_at = _utc_now()
    log.last_rating = rating_int
    log.reps = (log.reps or 0) + 1

    await db.flush()
    await db.refresh(log)
    return log
