# ADR-0009: Support CSV and Anki .apkg import

**Date:** 2026-03-28
**Status:** Accepted

## Context

Users likely have existing flashcard data in other tools (notably Anki, the dominant SRS application, or spreadsheets). Manual re-entry would be a significant barrier to adoption. Import support is required from Phase 2.

## Decision

Support two import formats:

1. **CSV** — universal spreadsheet export format
2. **Anki `.apkg`** — Anki's deck package format (renamed `.zip` containing a SQLite database and media files)

## CSV Import Details

- `POST /courses/{id}/import/csv` accepts a multipart file upload
- The server parses the CSV, auto-detects headers, and returns a preview of the first 5 rows
- The client presents a column-mapping UI (map CSV columns → course `column_definitions`)
- Supported options: skip duplicates / overwrite duplicates (matched by exact data equality)
- Row-level validation errors are returned as a structured list; valid rows are imported, invalid rows are reported

## Anki `.apkg` Import Details

- `POST /courses/{id}/import/anki` accepts a multipart `.apkg` file upload
- The server extracts the ZIP, reads `collection.anki21` (SQLite)
- Note types are inspected; the user selects which note type to import if multiple exist
- Field names from the Anki note type map to new `column_definitions` on the course
- HTML is stripped from field values (Anki stores HTML); basic `<br>` → newline conversion applied
- Media files (images, audio) are out of scope for Phase 2 (referenced as placeholder strings)

## Rationale

- CSV covers spreadsheet users and any tool that can export to CSV
- Anki `.apkg` covers the largest existing SRS user base
- Both formats are well-documented and have stable parsing libraries (`csv` stdlib, `zipfile` stdlib + `sqlite3` stdlib for `.apkg`)
- No additional native dependencies needed

## Alternatives considered

| Option | Reason rejected |
|---|---|
| CSV only | Misses Anki users who have years of study data |
| Anki only | Too narrow; CSV is the universal fallback |
| SuperMemo XML | Very small user base; can be added later if requested |

## Consequences

- `services/importer.py` contains `CsvImporter` and `AnkiImporter` classes
- Both importers return a `ImportResult(imported: int, skipped: int, errors: list[ImportError])` dataclass
- The import endpoints are gated behind authentication; users can only import into their own courses
- Media import (images, audio in `.apkg`) is deferred to a future phase; a `TODO` is left in `AnkiImporter`
