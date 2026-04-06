"""
Import logic for CSV and Anki (.apkg) files.

Both importers return an :class:`ImportResult` describing what was created,
skipped (duplicate), or rejected (validation error).

Duplicate detection
-------------------
A flashcard is considered a duplicate if a row with identical ``data`` JSON
already exists in the course.  We load all existing ``data`` values once at
the start of each import and build a set of *frozen* representations for O(1)
lookup.

Row validation
--------------
A row is rejected (added to ``errors``) when:
- It has no non-empty values after mapping.
- For CSV: the row has more or fewer fields than the header (``csv.DictReader``
  signals this by putting a ``None`` key in the row dict).

Column mapping validation
-------------------------
When an explicit ``column_mapping`` or ``field_mapping`` is supplied, every
``course_column`` value must be a known column in the course's
``column_definitions``.  Unknown columns raise ``ValueError``; the API layer
converts this to a 422 response.

Media references in Anki cards (e.g. ``[sound:foo.mp3]`` or ``<img …>``) are
stripped to plain text because we don't yet have a media-storage layer.
"""

from __future__ import annotations

import csv
import io
import json
import re
import sqlite3
import tempfile
import zipfile
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.flashcard import Flashcard
from app.schemas.imports import AnkiFieldMapping, CsvColumnMapping, ImportResult, ImportRowError

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_ANKI_MEDIA_RE = re.compile(
    r"\[sound:[^\]]+\]"  # [sound:foo.mp3]
    r"|<img\b[^>]*>"  # <img …>
    r"|<audio\b[^>]*>.*?</audio>",  # <audio …>…</audio>
    re.IGNORECASE | re.DOTALL,
)
_HTML_TAG_RE = re.compile(r"<[^>]+>")


def _strip_html(text: str) -> str:
    """Remove HTML tags and Anki media references, collapse whitespace."""
    text = _ANKI_MEDIA_RE.sub("", text)
    text = _HTML_TAG_RE.sub("", text)
    return " ".join(text.split())


def _freeze(data: dict[str, Any]) -> str:
    """Stable JSON string used for duplicate detection."""
    return json.dumps(data, sort_keys=True, ensure_ascii=False)


async def _existing_fingerprints(course_id: str, db: AsyncSession) -> set[str]:
    """Return the set of frozen data strings for all flashcards in a course."""
    result = await db.execute(select(Flashcard.data).where(Flashcard.course_id == course_id))
    return {_freeze(row) for row in result.scalars().all()}


async def _bulk_insert(
    course_id: str,
    rows: list[dict[str, Any]],
    db: AsyncSession,
) -> None:
    for data in rows:
        db.add(Flashcard(course_id=course_id, data=data))
    await db.flush()


def _validate_course_columns(mapping_values: list[str], column_names: list[str]) -> None:
    """
    Raise ``ValueError`` if any mapped course column is not in *column_names*.

    Parameters
    ----------
    mapping_values:
        The ``course_column`` values from an explicit mapping.
    column_names:
        The course's known column names (from ``column_definitions``).
    """
    known = set(column_names)
    unknown = [c for c in mapping_values if c not in known]
    if unknown:
        raise ValueError(f"Unknown course column(s) in mapping: {unknown}. Valid columns are: {column_names}")


# ---------------------------------------------------------------------------
# CSV import
# ---------------------------------------------------------------------------


async def import_csv(
    course_id: str,
    file_bytes: bytes,
    column_names: list[str],
    column_mapping: list[CsvColumnMapping] | None,
    db: AsyncSession,
) -> ImportResult:
    """
    Parse *file_bytes* as UTF-8 CSV and bulk-insert flashcards.

    Parameters
    ----------
    course_id:
        Target course.
    file_bytes:
        Raw bytes of the uploaded CSV file.
    column_names:
        The course's ``column_definitions`` names.  When *column_mapping* is
        ``None``, only CSV headers whose names exactly match a course column are
        imported.  When *column_mapping* is provided, every ``course_column``
        must be present in this list (raises ``ValueError`` otherwise).
    column_mapping:
        Optional explicit ``csv_header → course_column`` mappings.  When
        ``None``, CSV headers are matched to course columns by exact name.

    Raises
    ------
    ValueError
        If *column_mapping* references a course column that does not exist.
    """
    try:
        text = file_bytes.decode("utf-8-sig")  # handle optional BOM
    except UnicodeDecodeError:
        text = file_bytes.decode("latin-1")

    reader = csv.DictReader(io.StringIO(text))
    if reader.fieldnames is None:
        return ImportResult(imported=0, skipped=0, errors=[])

    csv_headers: list[str] = list(reader.fieldnames)

    # Build and validate mapping: csv_header → course_column
    if column_mapping:
        _validate_course_columns([m.course_column for m in column_mapping], column_names)
        header_to_col: dict[str, str] = {m.csv_header: m.course_column for m in column_mapping}
    else:
        # auto: keep only headers that exactly match a course column
        col_set = set(column_names)
        header_to_col = {h: h for h in csv_headers if h in col_set}

    existing = await _existing_fingerprints(course_id, db)
    errors: list[ImportRowError] = []
    to_insert: list[dict[str, Any]] = []
    skipped = 0

    for row_num, raw_row in enumerate(reader, start=2):  # row 1 = header
        # csv.DictReader signals a row with too many/too few fields by adding a
        # None key.  Reject these rows rather than silently dropping data.
        if None in raw_row:
            errors.append(
                ImportRowError(
                    row=row_num,
                    message="Row has a different number of fields than the header",
                )
            )
            continue

        data: dict[str, Any] = {}
        for csv_h, col in header_to_col.items():
            data[col] = raw_row.get(csv_h, "")

        # Skip entirely empty rows
        if not any(v.strip() for v in data.values() if isinstance(v, str)):
            errors.append(ImportRowError(row=row_num, message="Row is empty or all values are blank"))
            continue

        fp = _freeze(data)
        if fp in existing:
            skipped += 1
            continue

        existing.add(fp)
        to_insert.append(data)

    await _bulk_insert(course_id, to_insert, db)
    return ImportResult(imported=len(to_insert), skipped=skipped, errors=errors)


# ---------------------------------------------------------------------------
# Anki (.apkg) import
# ---------------------------------------------------------------------------

# Anki 2.1+ uses collection.anki21; older decks use collection.anki2.
_ANKI_DB_NAMES = ("collection.anki21", "collection.anki2")


def _extract_anki_db_bytes(apkg_bytes: bytes) -> bytes:
    """Return the raw SQLite database bytes from the apkg zip archive."""
    with zipfile.ZipFile(io.BytesIO(apkg_bytes)) as zf:
        names = zf.namelist()
        db_name = next((n for n in _ANKI_DB_NAMES if n in names), None)
        if db_name is None:
            raise ValueError(f"No Anki database found in archive. Files present: {names}")
        return zf.read(db_name)


def _parse_anki_notes(db_bytes: bytes) -> tuple[list[str], list[list[str]]]:
    """
    Return (field_names, rows) from an Anki SQLite database given as bytes.

    Anki stores field names in the ``col`` table (``models`` JSON) and note
    field values in the ``notes`` table (``flds`` column, separated by \\x1f).

    We return the field names of the *first* note type found, and only rows
    that match that note type.  Multi-model decks are therefore imported with
    the first model's schema; rows belonging to other models are skipped.

    Note: ``sqlite3.Connection.deserialize()`` is not available in all Python
    builds (it requires ``SQLITE_ENABLE_DESERIALIZE``).  We write the bytes to
    a named temp file via :meth:`pathlib.Path.write_bytes` (which guarantees a
    complete write) and open it with ``sqlite3.connect``.
    """
    with tempfile.NamedTemporaryFile(suffix=".anki2", delete=False) as tmp:
        tmp_path = tmp.name

    try:
        # write_bytes guarantees all bytes are written in one call, unlike
        # os.write() which can short-write on some platforms.
        Path(tmp_path).write_bytes(db_bytes)

        conn = sqlite3.connect(tmp_path)
        try:
            # --- Retrieve field names from models JSON ---
            col_row = conn.execute("SELECT models FROM col LIMIT 1").fetchone()
            if col_row is None:
                return [], []

            models: dict[str, Any] = json.loads(col_row[0])
            if not models:
                return [], []

            # Use the first model
            first_model = next(iter(models.values()))
            field_names: list[str] = [f["name"] for f in first_model.get("flds", [])]
            first_mid = str(first_model["id"])

            # --- Retrieve note rows for that model ---
            note_rows = conn.execute("SELECT flds FROM notes WHERE mid = ?", (first_mid,)).fetchall()
        finally:
            conn.close()
    finally:
        Path(tmp_path).unlink(missing_ok=True)

    rows = [row[0].split("\x1f") for row in note_rows]
    return field_names, rows


async def import_anki(
    course_id: str,
    apkg_bytes: bytes,
    column_names: list[str],
    field_mapping: list[AnkiFieldMapping] | None,
    db: AsyncSession,
) -> ImportResult:
    """
    Parse *apkg_bytes* as an Anki package and bulk-insert flashcards.

    Parameters
    ----------
    course_id:
        Target course.
    apkg_bytes:
        Raw bytes of the uploaded ``.apkg`` file.
    column_names:
        The course's ``column_definitions`` names.  When *field_mapping* is
        ``None``, only Anki fields whose names exactly match a course column are
        imported.  When *field_mapping* is provided, every ``course_column``
        must be present in this list (raises ``ValueError`` otherwise).
    field_mapping:
        Optional explicit ``anki_field → course_column`` mappings.  When
        ``None``, Anki field names are matched to course columns by exact name.

    Raises
    ------
    ValueError
        If *field_mapping* references a course column that does not exist.
    """
    try:
        db_bytes = _extract_anki_db_bytes(apkg_bytes)
    except (zipfile.BadZipFile, ValueError) as exc:
        return ImportResult(
            imported=0,
            skipped=0,
            errors=[ImportRowError(row=0, message=f"Invalid .apkg file: {exc}")],
        )

    try:
        field_names, note_rows = _parse_anki_notes(db_bytes)
    except Exception as exc:  # noqa: BLE001
        return ImportResult(
            imported=0,
            skipped=0,
            errors=[ImportRowError(row=0, message=f"Failed to parse Anki database: {exc}")],
        )

    if not field_names:
        return ImportResult(imported=0, skipped=0, errors=[])

    # Build and validate mapping: anki_field → course_column
    if field_mapping:
        _validate_course_columns([m.course_column for m in field_mapping], column_names)
        field_to_col: dict[str, str] = {m.anki_field: m.course_column for m in field_mapping}
    else:
        col_set = set(column_names)
        field_to_col = {f: f for f in field_names if f in col_set}

    existing = await _existing_fingerprints(course_id, db)
    errors: list[ImportRowError] = []
    to_insert: list[dict[str, Any]] = []
    skipped = 0

    for row_num, fields in enumerate(note_rows, start=1):
        data: dict[str, Any] = {}
        for idx, field_name in enumerate(field_names):
            if field_name in field_to_col:
                value = fields[idx] if idx < len(fields) else ""
                data[field_to_col[field_name]] = _strip_html(value)

        if not any(v.strip() for v in data.values() if isinstance(v, str)):
            errors.append(ImportRowError(row=row_num, message="Note has no non-empty mapped fields"))
            continue

        fp = _freeze(data)
        if fp in existing:
            skipped += 1
            continue

        existing.add(fp)
        to_insert.append(data)

    await _bulk_insert(course_id, to_insert, db)
    return ImportResult(imported=len(to_insert), skipped=skipped, errors=errors)
