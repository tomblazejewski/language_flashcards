"""Pydantic schemas for the CSV and Anki import endpoints."""

from __future__ import annotations

from pydantic import BaseModel, Field


class ImportRowError(BaseModel):
    """A validation error tied to a specific row of the import source."""

    row: int = Field(..., description="1-based row number in the source file")
    message: str


class ImportResult(BaseModel):
    """Summary returned by both import endpoints."""

    imported: int = Field(..., description="Number of flashcards successfully created")
    skipped: int = Field(..., description="Number of rows skipped due to duplicates")
    errors: list[ImportRowError] = Field(
        default_factory=list,
        description="Row-level validation errors (rows that could not be imported)",
    )


class CsvColumnMapping(BaseModel):
    """
    Maps a CSV header to a course column name.

    If not provided, CSV headers are matched to course columns by exact name.
    """

    csv_header: str
    course_column: str


class AnkiFieldMapping(BaseModel):
    """Maps an Anki field name to a course column name."""

    anki_field: str
    course_column: str
