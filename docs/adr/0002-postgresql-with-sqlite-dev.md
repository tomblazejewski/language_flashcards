# ADR-0002: PostgreSQL in production, SQLite for development

**Date:** 2026-03-28
**Status:** Accepted

## Context

The app needs a relational database that can:

- Handle multiple concurrent users
- Store flexible JSON data (column definitions, flashcard data, FSRS state)
- Be easy to run locally without a heavy setup burden

## Decision

Use **PostgreSQL** in staging and production. Use **SQLite** (via `aiosqlite`) in local development and the test suite.

## Rationale

- PostgreSQL has first-class JSON/JSONB column support; JSONB is indexed and queryable — critical for `column_definitions` and `flashcard.data`
- Multi-user concurrency is a primary requirement; PostgreSQL handles this correctly under load
- SQLite for dev/test means a developer can run the backend with zero extra services (`DATABASE_URL=sqlite+aiosqlite:///./dev.db`)
- SQLAlchemy 2.0 abstracts the driver differences; the same model code runs on both

## Alternatives considered

| Option | Reason rejected |
|---|---|
| MySQL / MariaDB | Weaker JSON support historically; no compelling advantage |
| MongoDB | Would remove the relational integrity between users, courses, cards, and reviews |
| SQLite everywhere | Not suitable for production multi-user concurrent writes |

## Consequences

- `DATABASE_URL` environment variable controls the active database
- Docker Compose provides a local PostgreSQL container for integration testing
- Alembic migrations are written to be compatible with both engines where possible; any PostgreSQL-specific SQL is gated behind dialect checks
- JSONB (`postgresql.JSONB`) is used on PostgreSQL; `JSON` falls back on SQLite
