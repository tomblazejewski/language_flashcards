# Language Flashcards - Development Roadmap

This document outlines the phased implementation plan. Each phase maps to one or more PRs.
ADRs covering key architectural decisions live in [`docs/adr/`](docs/adr/).

---

## Phase 1 — Backend Foundation

**Goal:** A fully tested FastAPI backend that any HTTP client can drive.

### 1.1 — Project scaffolding
- [ ] Move `main.py` into `backend/app/` structure
- [ ] Configure `pyproject.toml` with all backend dependencies (`fastapi`, `uvicorn`, `sqlalchemy`, `alembic`, `pydantic-settings`, `python-jose`, `passlib`, `psycopg2-binary`, `py-fsrs`)
- [ ] `docker-compose.yml` for local PostgreSQL + backend
- [ ] `.env.example` documenting all required environment variables
- [ ] `Makefile` with common dev tasks (`make dev`, `make migrate`, `make test`)

### 1.2 — Database models & migrations
- [ ] SQLAlchemy async models: `User`, `Course`, `Flashcard`, `ReviewConfig`, `ReviewLog`
- [ ] Alembic migration: initial schema
- [ ] Seed script for local development data

### 1.3 — Authentication
- [ ] `POST /auth/register` — create account
- [ ] `POST /auth/login` — return access + refresh JWT tokens
- [ ] `POST /auth/refresh` — exchange refresh token for new access token
- [ ] `POST /auth/logout` — revoke refresh token
- [ ] Auth middleware / `get_current_user` dependency

### 1.4 — Course & Flashcard CRUD
- [ ] `GET/POST /courses` — list user's courses, create course (with `column_definitions`)
- [ ] `GET/PATCH/DELETE /courses/{id}` — retrieve, update, delete course
- [ ] `GET/POST /courses/{id}/flashcards` — list or create flashcards
- [ ] `GET/PATCH/DELETE /flashcards/{id}` — retrieve, update, delete flashcard
- [ ] `GET/POST /courses/{id}/review-configs` — manage which column pairs are tested

### 1.5 — FSRS Study Engine
- [ ] `GET /study/{review_config_id}/due` — return batch of due flashcards
- [ ] `POST /study/{review_config_id}/review` — submit rating (Again/Hard/Good/Easy), advance FSRS state
- [ ] `GET /study/{review_config_id}/stats` — retention stats for a review config
- [ ] FSRS service isolated in `services/fsrs_engine.py`, fully unit tested

### 1.6 — Tests & CI
- [ ] Pytest setup with async test client (`httpx`)
- [ ] Tests for all auth, CRUD, and study endpoints
- [ ] GitHub Actions workflow: lint (`ruff`), type-check (`mypy`), tests

**PR checklist for Phase 1:** All endpoints return correct status codes, all tests pass, OpenAPI docs render correctly at `/docs`.

---

## Phase 2 — Import System

**Goal:** Users can populate courses from existing data without manual card entry.

### 2.1 — CSV Import
- [ ] `POST /courses/{id}/import/csv` — upload CSV, auto-detect or manually map columns
- [ ] Preview endpoint returning first N rows before committing
- [ ] Duplicate detection (skip or overwrite mode)
- [ ] Error reporting (row-level validation failures returned in response)

### 2.2 — Anki Import (`.apkg`)
- [ ] Parse `.apkg` (it is a renamed `.zip` containing SQLite + media)
- [ ] Map Anki note types to `column_definitions`
- [ ] Import cards, handle HTML stripping and basic media references
- [ ] `POST /courses/{id}/import/anki` endpoint

**PR checklist for Phase 2:** Import endpoints tested with real sample files; error paths return structured JSON errors.

---

## Phase 3 — Flutter Web App

**Goal:** A working web app backed by the Phase 1 + 2 API.

### 3.1 — Project setup
- [ ] `flutter create frontend` inside repo root
- [ ] Dependencies: `riverpod`, `go_router`, `drift`, `dio`, `flutter_secure_storage`
- [ ] API client generated from OpenAPI spec (or hand-written service layer)
- [ ] Environment config (dev/prod API base URLs)

### 3.2 — Auth screens
- [ ] Login screen
- [ ] Register screen
- [ ] Token storage and auto-refresh logic

### 3.3 — Course screens
- [ ] Course list screen (with create-course dialog)
- [ ] Course detail screen (flashcard list, review config selector)
- [ ] Flashcard editor (add/edit card with dynamic column form)

### 3.4 — Study screen
- [ ] Card display (show question column, reveal answer column)
- [ ] Rating buttons: Again / Hard / Good / Easy
- [ ] Session summary (cards reviewed, retention estimate)
- [ ] Empty state when no cards are due

### 3.5 — Import screen
- [ ] File picker (CSV or `.apkg`)
- [ ] Column mapping UI for CSV
- [ ] Progress indicator and error display

**PR checklist for Phase 3:** App runs with `flutter run -d chrome`; all screens reachable; study loop end-to-end working.

---

## Phase 4 — Offline-First Sync

**Goal:** Users can study without an internet connection; data syncs when back online.

### 4.1 — Local Drift schema
- [ ] Mirror `Flashcard`, `ReviewConfig`, and `ReviewLog` tables in Drift
- [ ] Sync service: pull due cards from server, push pending reviews

### 4.2 — Optimistic study loop
- [ ] Study session writes to local DB immediately
- [ ] Background isolate attempts server sync; merges on conflict (last-write-wins per review)
- [ ] Visual indicator for sync status (synced / pending / offline)

### 4.3 — Course cache
- [ ] Full course + flashcard list cached locally
- [ ] Incremental update using `updated_at` cursor (server returns only changed records)

**PR checklist for Phase 4:** App fully functional with network disabled; reviews sync correctly after reconnecting.

---

## Phase 5 — Mobile Polish & Release

**Goal:** Publish to Google Play and App Store.

### 5.1 — Android
- [ ] App icon, splash screen
- [ ] Review notification (local notification when cards are due)
- [ ] Test on physical device and emulator
- [ ] Sign release build, upload to Play Console internal testing track

### 5.2 — iOS
- [ ] Provisioning profiles and signing
- [ ] Test on simulator and physical device
- [ ] TestFlight internal build

### 5.3 — Cross-platform UX polish
- [ ] Haptic feedback on card rating
- [ ] Keyboard shortcuts for web (1-4 keys for Again/Hard/Good/Easy)
- [ ] Dark mode support
- [ ] Accessibility audit (screen reader labels, contrast)

**PR checklist for Phase 5:** App installable from store listing; no crashes on review; push notification permission flow working.

---

## Dependency Graph

```
Phase 1 (Backend)
  └── Phase 2 (Import)
        └── Phase 3 (Flutter Web)
              └── Phase 4 (Sync)
                    └── Phase 5 (Mobile)
```

Each phase should be fully merged and stable before the next begins.

---

## Tech Stack Summary

| Concern | Technology |
|---|---|
| Backend language | Python 3.12 |
| Web framework | FastAPI |
| Database (prod) | PostgreSQL |
| Database (dev) | SQLite (via `aiosqlite`) |
| ORM / migrations | SQLAlchemy 2.0 async + Alembic |
| Auth | JWT (`python-jose` + `passlib`) |
| SRS algorithm | FSRS (`py-fsrs`) |
| Frontend | Flutter 3 |
| State management | Riverpod |
| Local DB (Flutter) | Drift (SQLite) |
| HTTP client (Flutter) | Dio |
| Routing (Flutter) | go_router |
| Containerisation | Docker Compose |
| Linting | Ruff (Python), `flutter analyze` |
| Type checking | Mypy (Python) |
| Testing | Pytest + httpx (Python), Flutter test |
