from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import DateTime, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import JSON

from app.db.database import Base


class ReviewConfig(Base):
    """
    Defines one study direction within a course for a specific user.

    Example: question_column="Word", answer_column="Translation"
    """

    __tablename__ = "review_configs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    course_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("courses.id", ondelete="CASCADE"), nullable=False, index=True
    )
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    question_column: Mapped[str] = mapped_column(String(255), nullable=False)
    answer_column: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    # relationships
    course: Mapped[Any] = relationship("Course", back_populates="review_configs")
    review_logs: Mapped[list[ReviewLog]] = relationship(
        "ReviewLog", back_populates="review_config", cascade="all, delete-orphan"
    )


class ReviewLog(Base):
    """Per-user SRS state for a single (flashcard, review_config) pair."""

    __tablename__ = "review_logs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    flashcard_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("flashcards.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    review_config_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("review_configs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    # FSRS card state (stability, difficulty, due, etc.)
    fsrs_state: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    due_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # 1=Again, 2=Hard, 3=Good, 4=Easy
    last_rating: Mapped[int | None] = mapped_column(Integer, nullable=True)
    reps: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=lambda: datetime.now(UTC),
        nullable=False,
    )

    # relationships
    flashcard: Mapped[Any] = relationship("Flashcard", back_populates="review_logs")
    review_config: Mapped[Any] = relationship("ReviewConfig", back_populates="review_logs")
