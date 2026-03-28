"""Business logic for Course, Flashcard, and ReviewConfig CRUD."""

from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.course import Course
from app.models.flashcard import Flashcard
from app.models.review import ReviewConfig

# ---------------------------------------------------------------------------
# Course
# ---------------------------------------------------------------------------


async def create_course(
    owner_id: str,
    name: str,
    description: str | None,
    column_definitions: list[dict[str, Any]],
    db: AsyncSession,
) -> Course:
    course = Course(
        owner_id=owner_id,
        name=name,
        description=description,
        column_definitions=column_definitions,
    )
    db.add(course)
    await db.flush()
    await db.refresh(course)
    return course


async def get_courses_for_user(owner_id: str, db: AsyncSession) -> list[Course]:
    result = await db.execute(select(Course).where(Course.owner_id == owner_id).order_by(Course.created_at))
    return list(result.scalars().all())


async def get_course(course_id: str, owner_id: str, db: AsyncSession) -> Course | None:
    result = await db.execute(select(Course).where(Course.id == course_id, Course.owner_id == owner_id))
    return result.scalar_one_or_none()


async def update_course(
    course: Course,
    name: str | None,
    description: str | None,
    column_definitions: list[dict[str, Any]] | None,
    db: AsyncSession,
) -> Course:
    if name is not None:
        course.name = name
    if description is not None:
        course.description = description
    if column_definitions is not None:
        course.column_definitions = column_definitions
    await db.flush()
    await db.refresh(course)
    return course


async def delete_course(course: Course, db: AsyncSession) -> None:
    await db.delete(course)
    await db.flush()


# ---------------------------------------------------------------------------
# Flashcard
# ---------------------------------------------------------------------------


async def create_flashcard(
    course_id: str,
    data: dict[str, Any],
    db: AsyncSession,
) -> Flashcard:
    flashcard = Flashcard(course_id=course_id, data=data)
    db.add(flashcard)
    await db.flush()
    await db.refresh(flashcard)
    return flashcard


async def get_flashcards_for_course(course_id: str, db: AsyncSession) -> list[Flashcard]:
    result = await db.execute(select(Flashcard).where(Flashcard.course_id == course_id).order_by(Flashcard.created_at))
    return list(result.scalars().all())


async def get_flashcard(flashcard_id: str, course_id: str, db: AsyncSession) -> Flashcard | None:
    result = await db.execute(select(Flashcard).where(Flashcard.id == flashcard_id, Flashcard.course_id == course_id))
    return result.scalar_one_or_none()


async def update_flashcard(
    flashcard: Flashcard,
    data: dict[str, Any],
    db: AsyncSession,
) -> Flashcard:
    flashcard.data = data
    await db.flush()
    await db.refresh(flashcard)
    return flashcard


async def delete_flashcard(flashcard: Flashcard, db: AsyncSession) -> None:
    await db.delete(flashcard)
    await db.flush()


# ---------------------------------------------------------------------------
# ReviewConfig
# ---------------------------------------------------------------------------


async def create_review_config(
    course_id: str,
    user_id: str,
    question_column: str,
    answer_column: str,
    db: AsyncSession,
) -> ReviewConfig:
    # Prevent duplicate (user, course, question, answer) combos
    existing = await db.execute(
        select(ReviewConfig).where(
            ReviewConfig.course_id == course_id,
            ReviewConfig.user_id == user_id,
            ReviewConfig.question_column == question_column,
            ReviewConfig.answer_column == answer_column,
        )
    )
    if existing.scalar_one_or_none() is not None:
        raise ValueError("A review config with these columns already exists for this course.")
    config = ReviewConfig(
        course_id=course_id,
        user_id=user_id,
        question_column=question_column,
        answer_column=answer_column,
    )
    db.add(config)
    await db.flush()
    await db.refresh(config)
    return config


async def get_review_configs_for_course(course_id: str, user_id: str, db: AsyncSession) -> list[ReviewConfig]:
    result = await db.execute(
        select(ReviewConfig).where(
            ReviewConfig.course_id == course_id,
            ReviewConfig.user_id == user_id,
        )
    )
    return list(result.scalars().all())
