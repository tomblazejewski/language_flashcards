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


def _ensure_utc(dt: datetime) -> datetime:
    """Attach UTC timezone if the datetime is naive (SQLite quirk)."""
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


async def _bulk_ensure_review_logs(
    flashcards: list[Flashcard],
    review_config_id: str,
    user_id: str,
    db: AsyncSession,
) -> None:
    """
    Ensure every flashcard in the list has a ReviewLog row for the given
    (review_config_id, user_id).  Uses a single SELECT to find existing rows,
    then bulk-inserts the missing ones in one flush — O(1) round trips.
    """
    flashcard_ids = [fc.id for fc in flashcards]

    # Fetch all existing log rows for this config+user in one query
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
    """
    # Load all flashcards in the course
    fc_result = await db.execute(select(Flashcard).where(Flashcard.course_id == review_config.course_id))
    flashcards = list(fc_result.scalars().all())
    if not flashcards:
        return None

    # Ensure every flashcard has a ReviewLog row — bulk, no N+1
    await _bulk_ensure_review_logs(flashcards, review_config.id, user_id, db)

    now = _utc_now()

    # Find the due review log with the earliest due_date
    logs_result = await db.execute(
        select(ReviewLog)
        .where(
            ReviewLog.review_config_id == review_config.id,
            ReviewLog.user_id == user_id,
        )
        .order_by(ReviewLog.due_date.asc().nullsfirst())
    )
    logs = list(logs_result.scalars().all())

    # Prefer overdue cards; fall back to the soonest upcoming
    overdue = [log for log in logs if log.due_date is None or _ensure_utc(log.due_date) <= now]
    candidates = overdue if overdue else logs
    if not candidates:
        return None

    best_log = candidates[0]

    # Fetch the associated flashcard
    fc_result2 = await db.execute(select(Flashcard).where(Flashcard.id == best_log.flashcard_id))
    flashcard = fc_result2.scalar_one_or_none()
    if flashcard is None:
        return None

    return best_log, flashcard


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
