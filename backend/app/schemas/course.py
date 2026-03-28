"""Pydantic schemas for Course, Flashcard, and ReviewConfig."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

# ---------------------------------------------------------------------------
# Column definition (used inside Course)
# ---------------------------------------------------------------------------


class ColumnDefinition(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    type: str = Field("text", pattern=r"^(text|image|audio)$")


# ---------------------------------------------------------------------------
# Course
# ---------------------------------------------------------------------------


class CourseCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    description: str | None = None
    column_definitions: list[ColumnDefinition] = Field(default_factory=list)


class CourseUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=255)
    description: str | None = None
    column_definitions: list[ColumnDefinition] | None = None


class CourseResponse(BaseModel):
    id: str
    owner_id: str
    name: str
    description: str | None
    column_definitions: list[dict[str, Any]]
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Flashcard
# ---------------------------------------------------------------------------


class FlashcardCreate(BaseModel):
    data: dict[str, Any] = Field(default_factory=dict)


class FlashcardUpdate(BaseModel):
    data: dict[str, Any]


class FlashcardResponse(BaseModel):
    id: str
    course_id: str
    data: dict[str, Any]
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# ReviewConfig
# ---------------------------------------------------------------------------


class ReviewConfigCreate(BaseModel):
    question_column: str = Field(..., min_length=1, max_length=255)
    answer_column: str = Field(..., min_length=1, max_length=255)


class ReviewConfigResponse(BaseModel):
    id: str
    course_id: str
    user_id: str
    question_column: str
    answer_column: str
    created_at: datetime

    model_config = {"from_attributes": True}
