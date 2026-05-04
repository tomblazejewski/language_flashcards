from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from app.models.flashcard import Flashcard

from sqlalchemy import DateTime, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import JSON

from app.db.database import Base


class Course(Base):
    __tablename__ = "courses"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    owner_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    # e.g. [{"name": "Word", "type": "text"}, {"name": "Translation", "type": "text"}]
    column_definitions: Mapped[list[dict[str, Any]]] = mapped_column(
        JSON, nullable=False, default=list
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=lambda: datetime.now(UTC),
        nullable=False,
    )

    # relationships
    owner: Mapped[Any] = relationship("User", back_populates="courses")
    flashcards: Mapped[list[Flashcard]] = relationship(
        "Flashcard", back_populates="course", cascade="all, delete-orphan"
    )
    review_configs: Mapped[list[Any]] = relationship(
        "ReviewConfig", back_populates="course", cascade="all, delete-orphan"
    )
