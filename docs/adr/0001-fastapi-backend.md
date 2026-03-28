# ADR-0001: Use FastAPI as the backend framework

**Date:** 2026-03-28
**Status:** Accepted

## Context

The backend needs to serve a REST API consumed by a Flutter client (web and mobile). Key requirements are:

- Primary developer is most comfortable with Python
- Need automatic API documentation for Flutter client development
- Async I/O for efficient handling of concurrent study sessions
- Strong Pydantic-based validation (shared models between request/response and DB layer)

## Decision

Use **FastAPI** as the Python web framework.

## Rationale

- Native async support via `asyncio` — fits well with async SQLAlchemy
- Automatic OpenAPI/Swagger docs generated from type annotations at `/docs`; the Flutter client can be developed against this without needing the server to be fully built
- Pydantic v2 integration is first-class; request validation and response serialisation are handled automatically
- Lightweight compared to Django; no unnecessary batteries for a pure API service
- Large ecosystem and active maintenance

## Alternatives considered

| Option | Reason rejected |
|---|---|
| Django REST Framework | Heavier, primarily sync, more than needed for a pure API service |
| Flask + marshmallow | No async, no built-in OpenAPI, more manual wiring |
| Litestar | Technically comparable to FastAPI but smaller community and less tooling |

## Consequences

- Server entry point is `backend/app/main.py`; run with `uvicorn`
- All request/response contracts are Pydantic `BaseModel` subclasses in `backend/app/schemas/`
- `pytest` + `httpx` (async test client) used for endpoint testing
