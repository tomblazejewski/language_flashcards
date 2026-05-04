"""
Integration tests for the CSV and Anki import endpoints.

Anki fixture
------------
The ``_build_apkg`` helper builds a minimal but structurally valid ``.apkg``
file entirely in memory:
  - A zip archive containing ``collection.anki21`` (a real SQLite database)
  - The SQLite DB has the two tables Anki requires: ``col`` and ``notes``
  - ``col`` holds a JSON ``models`` blob describing field names
  - ``notes`` has one row per card

We create the SQLite DB as a file-backed DB (``sqlite3.connect`` with a temp
path) rather than in-memory, because ``Connection.serialize()`` and
``Connection.deserialize()`` are only available when Python's SQLite binding
was compiled with ``SQLITE_ENABLE_DESERIALIZE`` — which is not guaranteed.
"""

from __future__ import annotations

import io
import json
import os
import sqlite3
import tempfile
import time
import zipfile

from httpx import AsyncClient

# ---------------------------------------------------------------------------
# Shared helpers (mirrors test_courses_api.py)
# ---------------------------------------------------------------------------

COLS = [{"name": "Word", "type": "text"}, {"name": "Translation", "type": "text"}]


async def _register_and_login(client: AsyncClient, email: str) -> str:
    await client.post("/auth/register", json={"email": email, "password": "password123"})
    resp = await client.post("/auth/login", json={"email": email, "password": "password123"})
    return resp.json()["access_token"]


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def _make_course(client: AsyncClient, token: str) -> dict:
    resp = await client.post(
        "/courses",
        json={"name": "Import Test Course", "column_definitions": COLS},
        headers=_auth(token),
    )
    return resp.json()


# ---------------------------------------------------------------------------
# Fixture: minimal .apkg
# ---------------------------------------------------------------------------


def _build_apkg(
    field_names: list[str],
    notes: list[list[str]],
    model_id: int = 1234567890,
) -> bytes:
    """
    Build a minimal Anki .apkg as bytes.

    Creates a zip archive containing ``collection.anki21``, a real SQLite
    database with the ``col`` and ``notes`` tables populated.
    """
    fields_json = [{"name": n, "ord": i} for i, n in enumerate(field_names)]
    model = {
        "id": model_id,
        "name": "Basic",
        "flds": fields_json,
        "tmpls": [],
        "type": 0,
        "mod": int(time.time()),
    }
    models_json = json.dumps({str(model_id): model})

    # Use a file-backed DB so we can read the raw bytes back.
    tmp_fd, tmp_path = tempfile.mkstemp(suffix=".anki2")
    os.close(tmp_fd)
    try:
        conn = sqlite3.connect(tmp_path)
        conn.execute(
            """
            CREATE TABLE col (
                id INTEGER PRIMARY KEY,
                crt INTEGER NOT NULL,
                mod INTEGER NOT NULL,
                scm INTEGER NOT NULL,
                ver INTEGER NOT NULL,
                dty INTEGER NOT NULL,
                usn INTEGER NOT NULL,
                ls  INTEGER NOT NULL,
                conf TEXT NOT NULL,
                models TEXT NOT NULL,
                decks TEXT NOT NULL,
                dconf TEXT NOT NULL,
                tags TEXT NOT NULL
            )
            """
        )
        conn.execute(
            "INSERT INTO col VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                1,
                int(time.time()),
                int(time.time()),
                int(time.time() * 1000),
                11,
                0,
                -1,
                0,
                "{}",
                models_json,
                "{}",
                "{}",
                "{}",
            ),
        )
        conn.execute(
            """
            CREATE TABLE notes (
                id   INTEGER PRIMARY KEY,
                guid TEXT NOT NULL,
                mid  INTEGER NOT NULL,
                mod  INTEGER NOT NULL,
                usn  INTEGER NOT NULL,
                tags TEXT NOT NULL,
                flds TEXT NOT NULL,
                sfld TEXT NOT NULL,
                csum INTEGER NOT NULL,
                flags INTEGER NOT NULL,
                data TEXT NOT NULL
            )
            """
        )
        for i, fields in enumerate(notes):
            flds = "\x1f".join(fields)
            conn.execute(
                "INSERT INTO notes VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                (i + 1, f"guid{i}", model_id, int(time.time()), -1, "", flds, fields[0] if fields else "", 0, 0, ""),
            )
        conn.commit()
        conn.close()

        with open(tmp_path, "rb") as fh:
            db_bytes = fh.read()
    finally:
        os.unlink(tmp_path)

    # Pack into zip
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("collection.anki21", db_bytes)
        zf.writestr("media", "{}")
    return buf.getvalue()


# ---------------------------------------------------------------------------
# CSV import tests
# ---------------------------------------------------------------------------


async def test_csv_import_basic(client: AsyncClient) -> None:
    token = await _register_and_login(client, "imp_csv1@example.com")
    course = await _make_course(client, token)

    csv_content = "Word,Translation\n猫,cat\n犬,dog\n".encode()
    resp = await client.post(
        f"/courses/{course['id']}/import/csv",
        headers=_auth(token),
        files={"file": ("cards.csv", csv_content, "text/csv")},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["imported"] == 2
    assert data["skipped"] == 0
    assert data["errors"] == []


async def test_csv_import_duplicate_skipped(client: AsyncClient) -> None:
    token = await _register_and_login(client, "imp_csv2@example.com")
    course = await _make_course(client, token)

    csv_content = b"Word,Translation\nhello,world\n"

    # First import
    resp1 = await client.post(
        f"/courses/{course['id']}/import/csv",
        headers=_auth(token),
        files={"file": ("cards.csv", csv_content, "text/csv")},
    )
    assert resp1.json()["imported"] == 1

    # Second import — same file → duplicate
    resp2 = await client.post(
        f"/courses/{course['id']}/import/csv",
        headers=_auth(token),
        files={"file": ("cards.csv", csv_content, "text/csv")},
    )
    assert resp2.status_code == 200
    data = resp2.json()
    assert data["imported"] == 0
    assert data["skipped"] == 1


async def test_csv_import_with_explicit_column_mapping(client: AsyncClient) -> None:
    token = await _register_and_login(client, "imp_csv3@example.com")
    course = await _make_course(client, token)

    # CSV has different header names
    csv_content = b"Term,Meaning\nhello,world\n"
    mapping = json.dumps(
        [
            {"csv_header": "Term", "course_column": "Word"},
            {"csv_header": "Meaning", "course_column": "Translation"},
        ]
    )
    resp = await client.post(
        f"/courses/{course['id']}/import/csv",
        headers=_auth(token),
        files={"file": ("cards.csv", csv_content, "text/csv")},
        data={"column_mapping": mapping},
    )
    assert resp.status_code == 200
    assert resp.json()["imported"] == 1


async def test_csv_import_blank_rows_reported_as_errors(client: AsyncClient) -> None:
    token = await _register_and_login(client, "imp_csv4@example.com")
    course = await _make_course(client, token)

    # One valid row, one blank
    csv_content = b"Word,Translation\nhello,world\n,\n"
    resp = await client.post(
        f"/courses/{course['id']}/import/csv",
        headers=_auth(token),
        files={"file": ("cards.csv", csv_content, "text/csv")},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["imported"] == 1
    assert len(data["errors"]) == 1
    assert data["errors"][0]["row"] == 3  # header=1, valid=2, blank=3


async def test_csv_import_requires_auth(client: AsyncClient) -> None:
    resp = await client.post(
        "/courses/some-id/import/csv",
        files={"file": ("cards.csv", b"Word\nhello\n", "text/csv")},
    )
    assert resp.status_code in (401, 403)


async def test_csv_import_wrong_course_returns_404(client: AsyncClient) -> None:
    token = await _register_and_login(client, "imp_csv5@example.com")
    resp = await client.post(
        "/courses/nonexistent-id/import/csv",
        headers=_auth(token),
        files={"file": ("cards.csv", b"Word\nhello\n", "text/csv")},
    )
    assert resp.status_code == 404


async def test_csv_import_invalid_mapping_json_returns_422(client: AsyncClient) -> None:
    token = await _register_and_login(client, "imp_csv6@example.com")
    course = await _make_course(client, token)

    resp = await client.post(
        f"/courses/{course['id']}/import/csv",
        headers=_auth(token),
        files={"file": ("cards.csv", b"Word\nhello\n", "text/csv")},
        data={"column_mapping": "not-valid-json"},
    )
    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# Anki import tests
# ---------------------------------------------------------------------------


async def test_anki_import_basic(client: AsyncClient) -> None:
    token = await _register_and_login(client, "imp_anki1@example.com")
    course = await _make_course(client, token)

    apkg = _build_apkg(
        field_names=["Word", "Translation"],
        notes=[["猫", "cat"], ["犬", "dog"]],
    )
    resp = await client.post(
        f"/courses/{course['id']}/import/anki",
        headers=_auth(token),
        files={"file": ("deck.apkg", apkg, "application/octet-stream")},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["imported"] == 2
    assert data["skipped"] == 0
    assert data["errors"] == []


async def test_anki_import_duplicate_skipped(client: AsyncClient) -> None:
    token = await _register_and_login(client, "imp_anki2@example.com")
    course = await _make_course(client, token)

    apkg = _build_apkg(field_names=["Word", "Translation"], notes=[["hello", "world"]])

    resp1 = await client.post(
        f"/courses/{course['id']}/import/anki",
        headers=_auth(token),
        files={"file": ("deck.apkg", apkg, "application/octet-stream")},
    )
    assert resp1.json()["imported"] == 1

    resp2 = await client.post(
        f"/courses/{course['id']}/import/anki",
        headers=_auth(token),
        files={"file": ("deck.apkg", apkg, "application/octet-stream")},
    )
    assert resp2.status_code == 200
    data = resp2.json()
    assert data["imported"] == 0
    assert data["skipped"] == 1


async def test_anki_import_html_stripped(client: AsyncClient) -> None:
    token = await _register_and_login(client, "imp_anki3@example.com")
    course = await _make_course(client, token)

    apkg = _build_apkg(
        field_names=["Word", "Translation"],
        notes=[["<b>猫</b>", "<i>cat</i>"]],
    )
    resp = await client.post(
        f"/courses/{course['id']}/import/anki",
        headers=_auth(token),
        files={"file": ("deck.apkg", apkg, "application/octet-stream")},
    )
    assert resp.status_code == 200
    assert resp.json()["imported"] == 1

    # Verify the stored data has no HTML
    cards_resp = await client.get(f"/courses/{course['id']}/flashcards", headers=_auth(token))
    cards = cards_resp.json()
    assert cards[0]["data"]["Word"] == "猫"
    assert cards[0]["data"]["Translation"] == "cat"


async def test_anki_import_with_field_mapping(client: AsyncClient) -> None:
    token = await _register_and_login(client, "imp_anki4@example.com")
    course = await _make_course(client, token)

    # Anki fields named differently from course columns
    apkg = _build_apkg(field_names=["Front", "Back"], notes=[["hello", "world"]])
    mapping = json.dumps(
        [
            {"anki_field": "Front", "course_column": "Word"},
            {"anki_field": "Back", "course_column": "Translation"},
        ]
    )
    resp = await client.post(
        f"/courses/{course['id']}/import/anki",
        headers=_auth(token),
        files={"file": ("deck.apkg", apkg, "application/octet-stream")},
        data={"field_mapping": mapping},
    )
    assert resp.status_code == 200
    assert resp.json()["imported"] == 1


async def test_anki_import_bad_file_returns_error_in_body(client: AsyncClient) -> None:
    token = await _register_and_login(client, "imp_anki5@example.com")
    course = await _make_course(client, token)

    resp = await client.post(
        f"/courses/{course['id']}/import/anki",
        headers=_auth(token),
        files={"file": ("deck.apkg", b"this is not a zip", "application/octet-stream")},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["imported"] == 0
    assert len(data["errors"]) >= 1
    assert "Invalid" in data["errors"][0]["message"]


async def test_anki_import_requires_auth(client: AsyncClient) -> None:
    resp = await client.post(
        "/courses/some-id/import/anki",
        files={"file": ("deck.apkg", b"data", "application/octet-stream")},
    )
    assert resp.status_code in (401, 403)


async def test_anki_import_wrong_course_returns_404(client: AsyncClient) -> None:
    token = await _register_and_login(client, "imp_anki6@example.com")
    resp = await client.post(
        "/courses/nonexistent-id/import/anki",
        headers=_auth(token),
        files={"file": ("deck.apkg", b"data", "application/octet-stream")},
    )
    assert resp.status_code == 404
