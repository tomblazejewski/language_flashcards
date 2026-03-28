# ADR-0004: Use FSRS as the spaced-repetition algorithm

**Date:** 2026-03-28
**Status:** Accepted

## Context

The app schedules flashcard reviews to maximise long-term retention with the minimum number of review sessions. An SRS (Spaced Repetition System) algorithm is required. Several options exist with different complexity and effectiveness trade-offs.

## Decision

Use **FSRS** (Free Spaced Repetition Scheduler) via the `py-fsrs` Python library.

## Rationale

- FSRS is based on modern memory research (DSR model); it is empirically more efficient than SM-2 — users reach the same retention with fewer reviews
- It is the default algorithm in Anki since version 23.10, meaning users migrating from Anki will be familiar with the rating scale (Again / Hard / Good / Easy)
- `py-fsrs` is a well-maintained, pure-Python implementation with no native dependencies
- The algorithm state per card fits in a small JSON blob (`stability`, `difficulty`, `elapsed_days`, `scheduled_days`, `reps`, `lapses`, `state`, `last_review`), suitable for the `ReviewLog.fsrs_state` JSON column
- FSRS supports four-button rating (1–4) out of the box

## Alternatives considered

| Option | Reason rejected |
|---|---|
| SM-2 | Older algorithm; less optimal interval scheduling; still widely understood but FSRS is strictly better |
| Leitner boxes | Very simple but poor retention efficiency; interval control is coarse |
| Custom algorithm | Unnecessary complexity; FSRS already solves the problem well |

## Consequences

- `py-fsrs` added as a backend dependency
- `services/fsrs_engine.py` wraps the library and exposes `schedule(card, rating) -> (updated_card, next_due)` and `get_due_cards(user_id, review_config_id, limit)` functions
- FSRS state is stored per `(user, flashcard, review_config)` tuple in `ReviewLog.fsrs_state`
- Rating labels exposed to the Flutter client: `1=Again`, `2=Hard`, `3=Good`, `4=Easy`
