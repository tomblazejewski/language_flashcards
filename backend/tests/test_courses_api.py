"""Integration tests for Course, Flashcard, and ReviewConfig endpoints."""

from __future__ import annotations

from httpx import AsyncClient

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _register_and_login(client: AsyncClient, email: str = "user@example.com") -> str:
    """Register a user and return a valid access token."""
    await client.post("/auth/register", json={"email": email, "password": "password123"})
    resp = await client.post("/auth/login", json={"email": email, "password": "password123"})
    return resp.json()["access_token"]


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


COLS = [{"name": "Word", "type": "text"}, {"name": "Translation", "type": "text"}]


# ---------------------------------------------------------------------------
# Course CRUD
# ---------------------------------------------------------------------------


async def test_create_course(client: AsyncClient):
    token = await _register_and_login(client, "c1@example.com")
    resp = await client.post(
        "/courses",
        json={"name": "Japanese N5", "column_definitions": COLS},
        headers=_auth(token),
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "Japanese N5"
    assert len(data["column_definitions"]) == 2
    assert data["id"]


async def test_list_courses_empty(client: AsyncClient):
    token = await _register_and_login(client, "c2@example.com")
    resp = await client.get("/courses", headers=_auth(token))
    assert resp.status_code == 200
    assert resp.json() == []


async def test_list_courses_returns_own_courses_only(client: AsyncClient):
    token_a = await _register_and_login(client, "c3a@example.com")
    token_b = await _register_and_login(client, "c3b@example.com")

    await client.post("/courses", json={"name": "Course A"}, headers=_auth(token_a))
    await client.post("/courses", json={"name": "Course B"}, headers=_auth(token_b))

    resp = await client.get("/courses", headers=_auth(token_a))
    assert resp.status_code == 200
    names = [c["name"] for c in resp.json()]
    assert "Course A" in names
    assert "Course B" not in names


async def test_get_course(client: AsyncClient):
    token = await _register_and_login(client, "c4@example.com")
    created = (await client.post("/courses", json={"name": "Spanish"}, headers=_auth(token))).json()

    resp = await client.get(f"/courses/{created['id']}", headers=_auth(token))
    assert resp.status_code == 200
    assert resp.json()["id"] == created["id"]


async def test_get_course_not_found(client: AsyncClient):
    token = await _register_and_login(client, "c5@example.com")
    resp = await client.get("/courses/nonexistent-id", headers=_auth(token))
    assert resp.status_code == 404


async def test_get_course_wrong_owner(client: AsyncClient):
    token_a = await _register_and_login(client, "c6a@example.com")
    token_b = await _register_and_login(client, "c6b@example.com")

    course = (await client.post("/courses", json={"name": "Secret"}, headers=_auth(token_a))).json()

    resp = await client.get(f"/courses/{course['id']}", headers=_auth(token_b))
    assert resp.status_code == 404


async def test_update_course(client: AsyncClient):
    token = await _register_and_login(client, "c7@example.com")
    course = (await client.post("/courses", json={"name": "Old Name"}, headers=_auth(token))).json()

    resp = await client.patch(
        f"/courses/{course['id']}",
        json={"name": "New Name"},
        headers=_auth(token),
    )
    assert resp.status_code == 200
    assert resp.json()["name"] == "New Name"


async def test_delete_course(client: AsyncClient):
    token = await _register_and_login(client, "c8@example.com")
    course = (await client.post("/courses", json={"name": "Delete Me"}, headers=_auth(token))).json()

    resp = await client.delete(f"/courses/{course['id']}", headers=_auth(token))
    assert resp.status_code == 204

    resp2 = await client.get(f"/courses/{course['id']}", headers=_auth(token))
    assert resp2.status_code == 404


async def test_create_course_requires_auth(client: AsyncClient):
    resp = await client.post("/courses", json={"name": "No Auth"})
    assert resp.status_code in (401, 403)


# ---------------------------------------------------------------------------
# Flashcard CRUD
# ---------------------------------------------------------------------------


async def _make_course(client: AsyncClient, token: str, name: str = "Test Course") -> dict:
    return (
        await client.post(
            "/courses",
            json={"name": name, "column_definitions": COLS},
            headers=_auth(token),
        )
    ).json()


async def test_create_flashcard(client: AsyncClient):
    token = await _register_and_login(client, "f1@example.com")
    course = await _make_course(client, token)

    resp = await client.post(
        f"/courses/{course['id']}/flashcards",
        json={"data": {"Word": "猫", "Translation": "cat"}},
        headers=_auth(token),
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["data"]["Word"] == "猫"
    assert data["course_id"] == course["id"]


async def test_list_flashcards(client: AsyncClient):
    token = await _register_and_login(client, "f2@example.com")
    course = await _make_course(client, token)

    for word in ["犬", "魚"]:
        await client.post(
            f"/courses/{course['id']}/flashcards",
            json={"data": {"Word": word, "Translation": "..."}},
            headers=_auth(token),
        )

    resp = await client.get(f"/courses/{course['id']}/flashcards", headers=_auth(token))
    assert resp.status_code == 200
    assert len(resp.json()) == 2


async def test_get_flashcard(client: AsyncClient):
    token = await _register_and_login(client, "f3@example.com")
    course = await _make_course(client, token)
    fc = (
        await client.post(
            f"/courses/{course['id']}/flashcards",
            json={"data": {"Word": "空", "Translation": "sky"}},
            headers=_auth(token),
        )
    ).json()

    resp = await client.get(f"/courses/{course['id']}/flashcards/{fc['id']}", headers=_auth(token))
    assert resp.status_code == 200
    assert resp.json()["id"] == fc["id"]


async def test_update_flashcard(client: AsyncClient):
    token = await _register_and_login(client, "f4@example.com")
    course = await _make_course(client, token)
    fc = (
        await client.post(
            f"/courses/{course['id']}/flashcards",
            json={"data": {"Word": "旧", "Translation": "old"}},
            headers=_auth(token),
        )
    ).json()

    resp = await client.patch(
        f"/courses/{course['id']}/flashcards/{fc['id']}",
        json={"data": {"Word": "新", "Translation": "new"}},
        headers=_auth(token),
    )
    assert resp.status_code == 200
    assert resp.json()["data"]["Word"] == "新"


async def test_delete_flashcard(client: AsyncClient):
    token = await _register_and_login(client, "f5@example.com")
    course = await _make_course(client, token)
    fc = (
        await client.post(
            f"/courses/{course['id']}/flashcards",
            json={"data": {"Word": "bye"}},
            headers=_auth(token),
        )
    ).json()

    resp = await client.delete(f"/courses/{course['id']}/flashcards/{fc['id']}", headers=_auth(token))
    assert resp.status_code == 204

    resp2 = await client.get(f"/courses/{course['id']}/flashcards/{fc['id']}", headers=_auth(token))
    assert resp2.status_code == 404


async def test_flashcard_not_accessible_for_wrong_owner(client: AsyncClient):
    token_a = await _register_and_login(client, "f6a@example.com")
    token_b = await _register_and_login(client, "f6b@example.com")
    course = await _make_course(client, token_a)
    fc = (
        await client.post(
            f"/courses/{course['id']}/flashcards",
            json={"data": {"Word": "secret"}},
            headers=_auth(token_a),
        )
    ).json()

    # token_b cannot see the course, so should get 404
    resp = await client.get(f"/courses/{course['id']}/flashcards/{fc['id']}", headers=_auth(token_b))
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# ReviewConfig
# ---------------------------------------------------------------------------


async def test_create_review_config(client: AsyncClient):
    token = await _register_and_login(client, "r1@example.com")
    course = await _make_course(client, token)

    resp = await client.post(
        f"/courses/{course['id']}/review-configs",
        json={"question_column": "Word", "answer_column": "Translation"},
        headers=_auth(token),
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["question_column"] == "Word"
    assert data["answer_column"] == "Translation"
    assert data["course_id"] == course["id"]


async def test_list_review_configs(client: AsyncClient):
    token = await _register_and_login(client, "r2@example.com")
    course = await _make_course(client, token)

    await client.post(
        f"/courses/{course['id']}/review-configs",
        json={"question_column": "Word", "answer_column": "Translation"},
        headers=_auth(token),
    )
    await client.post(
        f"/courses/{course['id']}/review-configs",
        json={"question_column": "Translation", "answer_column": "Word"},
        headers=_auth(token),
    )

    resp = await client.get(f"/courses/{course['id']}/review-configs", headers=_auth(token))
    assert resp.status_code == 200
    assert len(resp.json()) == 2


async def test_duplicate_review_config_rejected(client: AsyncClient):
    token = await _register_and_login(client, "r3@example.com")
    course = await _make_course(client, token)

    body = {"question_column": "Word", "answer_column": "Translation"}
    await client.post(f"/courses/{course['id']}/review-configs", json=body, headers=_auth(token))
    resp = await client.post(f"/courses/{course['id']}/review-configs", json=body, headers=_auth(token))
    assert resp.status_code == 409


async def test_review_configs_isolated_per_user(client: AsyncClient):
    token_a = await _register_and_login(client, "r4a@example.com")
    token_b = await _register_and_login(client, "r4b@example.com")
    course = await _make_course(client, token_a)

    await client.post(
        f"/courses/{course['id']}/review-configs",
        json={"question_column": "Word", "answer_column": "Translation"},
        headers=_auth(token_a),
    )

    # token_b cannot see token_a's course
    resp = await client.get(f"/courses/{course['id']}/review-configs", headers=_auth(token_b))
    assert resp.status_code == 404
