"""Import API routes — CSV and Anki (.apkg) upload."""

from __future__ import annotations

import json

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db.database import get_db
from app.models.user import User
from app.schemas.imports import AnkiFieldMapping, CsvColumnMapping, ImportResult
from app.services.course import get_course
from app.services.imports import import_anki, import_csv

router = APIRouter(prefix="/courses", tags=["imports"])

_MAX_UPLOAD_BYTES = 50 * 1024 * 1024  # 50 MB


async def _require_course_for_import(course_id: str, current_user: User, db: AsyncSession):  # type: ignore[return]
    course = await get_course(course_id, current_user.id, db)
    if course is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Course not found.")
    return course


@router.post(
    "/{course_id}/import/csv",
    response_model=ImportResult,
    status_code=status.HTTP_200_OK,
    summary="Import flashcards from a CSV file",
    description=(
        "Upload a UTF-8 CSV file.  The first row must be a header row.  "
        "By default, column headers are matched to course column names by exact name.  "
        "Pass an optional JSON-encoded `column_mapping` array to override the mapping."
    ),
)
async def import_csv_endpoint(
    course_id: str,
    file: UploadFile = File(..., description="CSV file to import"),
    column_mapping: str | None = Form(
        None,
        description='JSON array of {"csv_header": "...", "course_column": "..."} objects',
    ),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ImportResult:
    course = await _require_course_for_import(course_id, current_user, db)

    raw = await file.read()
    if len(raw) > _MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File exceeds the {_MAX_UPLOAD_BYTES // (1024 * 1024)} MB limit.",
        )

    mapping: list[CsvColumnMapping] | None = None
    if column_mapping is not None:
        try:
            parsed = json.loads(column_mapping)
            mapping = [CsvColumnMapping(**item) for item in parsed]
        except Exception as exc:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Invalid column_mapping JSON: {exc}",
            ) from exc

    column_names: list[str] = [col["name"] for col in course.column_definitions]
    return await import_csv(
        course_id=course_id,
        file_bytes=raw,
        column_names=column_names,
        column_mapping=mapping,
        db=db,
    )


@router.post(
    "/{course_id}/import/anki",
    response_model=ImportResult,
    status_code=status.HTTP_200_OK,
    summary="Import flashcards from an Anki .apkg file",
    description=(
        "Upload an Anki `.apkg` package.  Notes from the first note type are imported.  "
        "By default, Anki field names are matched to course column names by exact name.  "
        "Pass an optional JSON-encoded `field_mapping` array to override the mapping."
    ),
)
async def import_anki_endpoint(
    course_id: str,
    file: UploadFile = File(..., description=".apkg file to import"),
    field_mapping: str | None = Form(
        None,
        description='JSON array of {"anki_field": "...", "course_column": "..."} objects',
    ),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ImportResult:
    course = await _require_course_for_import(course_id, current_user, db)

    raw = await file.read()
    if len(raw) > _MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File exceeds the {_MAX_UPLOAD_BYTES // (1024 * 1024)} MB limit.",
        )

    mapping: list[AnkiFieldMapping] | None = None
    if field_mapping is not None:
        try:
            parsed = json.loads(field_mapping)
            mapping = [AnkiFieldMapping(**item) for item in parsed]
        except Exception as exc:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Invalid field_mapping JSON: {exc}",
            ) from exc

    column_names: list[str] = [col["name"] for col in course.column_definitions]
    return await import_anki(
        course_id=course_id,
        apkg_bytes=raw,
        column_names=column_names,
        field_mapping=mapping,
        db=db,
    )
