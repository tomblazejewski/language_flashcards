"""Study (FSRS review) API routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db.database import get_db
from app.models.review import ReviewConfig, ReviewLog
from app.models.user import User
from app.schemas.study import NextCardResponse, ReviewRequest, ReviewResponse
from app.services.study import get_next_card, submit_review

router = APIRouter(prefix="/study", tags=["study"])


async def _require_review_config(review_config_id: str, current_user: User, db: AsyncSession) -> ReviewConfig:
    result = await db.execute(
        select(ReviewConfig).where(
            ReviewConfig.id == review_config_id,
            ReviewConfig.user_id == current_user.id,
        )
    )
    config = result.scalar_one_or_none()
    if config is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Review config not found.")
    return config


async def _require_review_log(review_log_id: str, current_user: User, db: AsyncSession) -> ReviewLog:
    result = await db.execute(
        select(ReviewLog).where(
            ReviewLog.id == review_log_id,
            ReviewLog.user_id == current_user.id,
        )
    )
    log = result.scalar_one_or_none()
    if log is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Review log not found.")
    return log


@router.get("/{review_config_id}/next", response_model=NextCardResponse)
async def next_card(
    review_config_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> NextCardResponse:
    config = await _require_review_config(review_config_id, current_user, db)
    result = await get_next_card(config, current_user.id, db)
    if result is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No cards available in this course.",
        )
    log, flashcard = result
    question_value = flashcard.data.get(config.question_column)
    return NextCardResponse(
        review_log_id=log.id,
        flashcard_id=flashcard.id,
        course_id=flashcard.course_id,
        question_column=config.question_column,
        answer_column=config.answer_column,
        question_value=question_value,
        flashcard_data=flashcard.data,
        due_date=log.due_date,
        reps=log.reps,
    )


@router.post("/{review_config_id}/review/{review_log_id}", response_model=ReviewResponse)
async def review_card(
    review_config_id: str,
    review_log_id: str,
    body: ReviewRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ReviewResponse:
    # Validate the config belongs to this user
    await _require_review_config(review_config_id, current_user, db)
    log = await _require_review_log(review_log_id, current_user, db)

    updated_log = await submit_review(log=log, rating_int=body.rating, db=db)

    state_value: int = updated_log.fsrs_state.get("state", 0) if updated_log.fsrs_state else 0
    return ReviewResponse(
        review_log_id=updated_log.id,
        flashcard_id=updated_log.flashcard_id,
        new_due_date=updated_log.due_date,
        reps=updated_log.reps,
        state=state_value,
    )
