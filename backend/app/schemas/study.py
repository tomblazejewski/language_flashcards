"""Pydantic schemas for the FSRS study engine."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class NextCardResponse(BaseModel):
    """The next card due for review, with the question field shown."""

    review_log_id: str
    flashcard_id: str
    course_id: str
    question_column: str
    answer_column: str
    question_value: str | None
    # Convenience: full flashcard data so the client can render any extra columns.
    flashcard_data: dict[str, object]
    due_date: datetime | None
    reps: int


class ReviewRequest(BaseModel):
    """Body for submitting a review rating."""

    # 1=Again, 2=Hard, 3=Good, 4=Easy
    rating: int = Field(..., ge=1, le=4)


class ReviewResponse(BaseModel):
    """Result after submitting a rating."""

    review_log_id: str
    flashcard_id: str
    new_due_date: datetime | None
    reps: int
    state: int  # fsrs State enum value
