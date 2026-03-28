"""Course, Flashcard, and ReviewConfig API routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db.database import get_db
from app.models.course import Course
from app.models.flashcard import Flashcard
from app.models.review import ReviewConfig
from app.models.user import User
from app.schemas.course import (
    CourseCreate,
    CourseResponse,
    CourseUpdate,
    FlashcardCreate,
    FlashcardResponse,
    FlashcardUpdate,
    ReviewConfigCreate,
    ReviewConfigResponse,
)
from app.services.course import (
    create_course,
    create_flashcard,
    create_review_config,
    delete_course,
    delete_flashcard,
    get_course,
    get_courses_for_user,
    get_flashcard,
    get_flashcards_for_course,
    get_review_configs_for_course,
    update_course,
    update_flashcard,
)

router = APIRouter(prefix="/courses", tags=["courses"])


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _require_course(course_id: str, current_user: User, db: AsyncSession) -> Course:
    course = await get_course(course_id, current_user.id, db)
    if course is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Course not found.")
    return course


async def _require_flashcard(flashcard_id: str, course_id: str, db: AsyncSession) -> Flashcard:
    flashcard = await get_flashcard(flashcard_id, course_id, db)
    if flashcard is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Flashcard not found.")
    return flashcard


# ---------------------------------------------------------------------------
# Courses
# ---------------------------------------------------------------------------


@router.get("", response_model=list[CourseResponse])
async def list_courses(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[Course]:
    return await get_courses_for_user(current_user.id, db)


@router.post("", response_model=CourseResponse, status_code=status.HTTP_201_CREATED)
async def create_course_endpoint(
    body: CourseCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Course:
    return await create_course(
        owner_id=current_user.id,
        name=body.name,
        description=body.description,
        column_definitions=[col.model_dump() for col in body.column_definitions],
        db=db,
    )


@router.get("/{course_id}", response_model=CourseResponse)
async def get_course_endpoint(
    course_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Course:
    return await _require_course(course_id, current_user, db)


@router.patch("/{course_id}", response_model=CourseResponse)
async def update_course_endpoint(
    course_id: str,
    body: CourseUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Course:
    course = await _require_course(course_id, current_user, db)
    col_defs = [col.model_dump() for col in body.column_definitions] if body.column_definitions is not None else None
    return await update_course(
        course=course,
        name=body.name,
        description=body.description,
        column_definitions=col_defs,
        db=db,
    )


@router.delete("/{course_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_course_endpoint(
    course_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    course = await _require_course(course_id, current_user, db)
    await delete_course(course, db)


# ---------------------------------------------------------------------------
# Flashcards
# ---------------------------------------------------------------------------


@router.get("/{course_id}/flashcards", response_model=list[FlashcardResponse])
async def list_flashcards(
    course_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[Flashcard]:
    await _require_course(course_id, current_user, db)
    return await get_flashcards_for_course(course_id, db)


@router.post(
    "/{course_id}/flashcards",
    response_model=FlashcardResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_flashcard_endpoint(
    course_id: str,
    body: FlashcardCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Flashcard:
    await _require_course(course_id, current_user, db)
    return await create_flashcard(course_id=course_id, data=body.data, db=db)


@router.get("/{course_id}/flashcards/{flashcard_id}", response_model=FlashcardResponse)
async def get_flashcard_endpoint(
    course_id: str,
    flashcard_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Flashcard:
    await _require_course(course_id, current_user, db)
    return await _require_flashcard(flashcard_id, course_id, db)


@router.patch("/{course_id}/flashcards/{flashcard_id}", response_model=FlashcardResponse)
async def update_flashcard_endpoint(
    course_id: str,
    flashcard_id: str,
    body: FlashcardUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Flashcard:
    await _require_course(course_id, current_user, db)
    flashcard = await _require_flashcard(flashcard_id, course_id, db)
    return await update_flashcard(flashcard=flashcard, data=body.data, db=db)


@router.delete("/{course_id}/flashcards/{flashcard_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_flashcard_endpoint(
    course_id: str,
    flashcard_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    await _require_course(course_id, current_user, db)
    flashcard = await _require_flashcard(flashcard_id, course_id, db)
    await delete_flashcard(flashcard, db)


# ---------------------------------------------------------------------------
# ReviewConfigs
# ---------------------------------------------------------------------------


@router.get("/{course_id}/review-configs", response_model=list[ReviewConfigResponse])
async def list_review_configs(
    course_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[ReviewConfig]:
    await _require_course(course_id, current_user, db)
    return await get_review_configs_for_course(course_id, current_user.id, db)


@router.post(
    "/{course_id}/review-configs",
    response_model=ReviewConfigResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_review_config_endpoint(
    course_id: str,
    body: ReviewConfigCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ReviewConfig:
    await _require_course(course_id, current_user, db)
    try:
        return await create_review_config(
            course_id=course_id,
            user_id=current_user.id,
            question_column=body.question_column,
            answer_column=body.answer_column,
            db=db,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
