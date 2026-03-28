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


async def _get_or_create_review_log(
    flashcard_id: str,
    review_config_id: str,
    user_id: str,
    db: AsyncSession,
) -> ReviewLog:
    result = await db.execute(
        select(ReviewLog).where(
            ReviewLog.flashcard_id == flashcard_id,
            ReviewLog.review_config_id == review_config_id,
            ReviewLog.user_id == user_id,
        )
    )
    log = result.scalar_one_or_none()
    if log is None:
        card = FsrsCard()
        log = ReviewLog(
            flashcard_id=flashcard_id,
            review_config_id=review_config_id,
            user_id=user_id,
            fsrs_state=card.to_dict(),
            due_date=card.due,
            reps=0,
        )
        db.add(log)
        await db.flush()
        await db.refresh(log)
    return log


async def get_next_card(
    review_config: ReviewConfig,
    user_id: str,
    db: AsyncSession,
) -> tuple[ReviewLog, Flashcard] | None:
    """
    Return the (ReviewLog, Flashcard) pair for the card most overdue (or next
    due) for this user/config.  Initialises ReviewLog rows for any flashcards
    that have never been seen.
    """
    # Load all flashcards in the course
    fc_result = await db.execute(select(Flashcard).where(Flashcard.course_id == review_config.course_id))
    flashcards = fc_result.scalars().all()
    if not flashcards:
        return None

    # Ensure every flashcard has a ReviewLog row
    for fc in flashcards:
        await _get_or_create_review_log(fc.id, review_config.id, user_id, db)

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
    logs = logs_result.scalars().all()

    # Prefer overdue cards; fall back to the soonest upcoming
    overdue = [log for log in logs if log.due_date is None or _ensure_utc(log.due_date) <= now]
    candidates = overdue if overdue else list(logs)
    if not candidates:
        return None

    best_log = candidates[0]

    # Fetch the associated flashcard
    fc_result2 = await db.execute(select(Flashcard).where(Flashcard.id == best_log.flashcard_id))
    flashcard = fc_result2.scalar_one_or_none()
    if flashcard is None:
        return None

    return best_log, flashcard


def _ensure_utc(dt: datetime) -> datetime:
    """Attach UTC timezone if the datetime is naive (SQLite quirk)."""
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


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
