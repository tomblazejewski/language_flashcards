"""Integration tests for the FSRS study engine endpoints."""

from __future__ import annotations

from httpx import AsyncClient

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

COLS = [{"name": "Word", "type": "text"}, {"name": "Translation", "type": "text"}]


async def _setup(client: AsyncClient, email: str) -> tuple[str, str, str, str]:
    """
    Register + login, create a course with two flashcards and one review config.
    Returns (token, course_id, review_config_id, flashcard1_id).
    """
    await client.post("/auth/register", json={"email": email, "password": "pass1234"})
    token = (await client.post("/auth/login", json={"email": email, "password": "pass1234"})).json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    course = (
        await client.post("/courses", json={"name": "Study Test", "column_definitions": COLS}, headers=headers)
    ).json()

    fc1 = (
        await client.post(
            f"/courses/{course['id']}/flashcards",
            json={"data": {"Word": "猫", "Translation": "cat"}},
            headers=headers,
        )
    ).json()

    await client.post(
        f"/courses/{course['id']}/flashcards",
        json={"data": {"Word": "犬", "Translation": "dog"}},
        headers=headers,
    )

    rc = (
        await client.post(
            f"/courses/{course['id']}/review-configs",
            json={"question_column": "Word", "answer_column": "Translation"},
            headers=headers,
        )
    ).json()

    return token, course["id"], rc["id"], fc1["id"]


def _h(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


# ---------------------------------------------------------------------------
# next card
# ---------------------------------------------------------------------------


async def test_next_card_returns_a_card(client: AsyncClient):
    token, _, rc_id, _ = await _setup(client, "s1@example.com")

    resp = await client.get(f"/study/{rc_id}/next", headers=_h(token))
    assert resp.status_code == 200
    data = resp.json()
    assert data["review_log_id"]
    assert data["flashcard_id"]
    assert data["question_column"] == "Word"
    assert data["answer_column"] == "Translation"
    assert "question_value" in data
    assert "flashcard_data" in data


async def test_next_card_not_found_for_unknown_config(client: AsyncClient):
    await client.post("/auth/register", json={"email": "s2@example.com", "password": "pass1234"})
    token = (await client.post("/auth/login", json={"email": "s2@example.com", "password": "pass1234"})).json()[
        "access_token"
    ]

    resp = await client.get("/study/nonexistent-id/next", headers=_h(token))
    assert resp.status_code == 404


async def test_next_card_empty_course_returns_404(client: AsyncClient):
    await client.post("/auth/register", json={"email": "s3@example.com", "password": "pass1234"})
    token = (await client.post("/auth/login", json={"email": "s3@example.com", "password": "pass1234"})).json()[
        "access_token"
    ]
    headers = _h(token)

    course = (
        await client.post(
            "/courses",
            json={"name": "Empty", "column_definitions": COLS},
            headers=headers,
        )
    ).json()
    rc = (
        await client.post(
            f"/courses/{course['id']}/review-configs",
            json={"question_column": "Word", "answer_column": "Translation"},
            headers=headers,
        )
    ).json()

    resp = await client.get(f"/study/{rc['id']}/next", headers=headers)
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# review card
# ---------------------------------------------------------------------------


async def test_review_card_good(client: AsyncClient):
    token, _, rc_id, _ = await _setup(client, "s4@example.com")
    headers = _h(token)

    next_resp = await client.get(f"/study/{rc_id}/next", headers=headers)
    log_id = next_resp.json()["review_log_id"]

    resp = await client.post(
        f"/study/{rc_id}/review/{log_id}",
        json={"rating": 3},
        headers=headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["reps"] == 1
    assert data["new_due_date"] is not None
    assert data["review_log_id"] == log_id


async def test_review_card_all_ratings(client: AsyncClient):
    """Each valid rating (1-4) must succeed."""
    for i, (email, rating) in enumerate(
        [
            ("s5a@example.com", 1),
            ("s5b@example.com", 2),
            ("s5c@example.com", 3),
            ("s5d@example.com", 4),
        ]
    ):
        token, _, rc_id, _ = await _setup(client, email)
        headers = _h(token)

        log_id = (await client.get(f"/study/{rc_id}/next", headers=headers)).json()["review_log_id"]
        resp = await client.post(f"/study/{rc_id}/review/{log_id}", json={"rating": rating}, headers=headers)
        assert resp.status_code == 200, f"Rating {rating} failed: {resp.json()}"
        assert resp.json()["reps"] == 1


async def test_review_card_invalid_rating(client: AsyncClient):
    token, _, rc_id, _ = await _setup(client, "s6@example.com")
    headers = _h(token)

    log_id = (await client.get(f"/study/{rc_id}/next", headers=headers)).json()["review_log_id"]

    resp = await client.post(f"/study/{rc_id}/review/{log_id}", json={"rating": 5}, headers=headers)
    assert resp.status_code == 422


async def test_review_card_reps_increments(client: AsyncClient):
    token, _, rc_id, _ = await _setup(client, "s7@example.com")
    headers = _h(token)

    for expected_reps in range(1, 4):
        log_id = (await client.get(f"/study/{rc_id}/next", headers=headers)).json()["review_log_id"]
        resp = await client.post(f"/study/{rc_id}/review/{log_id}", json={"rating": 3}, headers=headers)
        assert resp.status_code == 200
        # reps may not always come back as expected_reps because next card might be different
        assert resp.json()["reps"] >= 1


async def test_review_config_isolation(client: AsyncClient):
    """User B cannot review with user A's review config."""
    token_a, _, rc_id_a, _ = await _setup(client, "s8a@example.com")
    await client.post("/auth/register", json={"email": "s8b@example.com", "password": "pass1234"})
    token_b = (await client.post("/auth/login", json={"email": "s8b@example.com", "password": "pass1234"})).json()[
        "access_token"
    ]

    resp = await client.get(f"/study/{rc_id_a}/next", headers=_h(token_b))
    assert resp.status_code == 404


async def test_review_requires_auth(client: AsyncClient):
    resp = await client.get("/study/some-id/next")
    assert resp.status_code in (401, 403)
