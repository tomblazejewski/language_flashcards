# ADR-0008: Offline-first with optimistic local writes

**Date:** 2026-03-28
**Status:** Accepted

## Context

Users should be able to study even without an internet connection (e.g., on a plane, in areas with poor connectivity). Reviews completed offline must not be lost and must integrate correctly with the server's SRS state when connectivity is restored.

## Decision

Use an **offline-first, optimistic sync** strategy implemented in Phase 4:

1. The Flutter client uses **Drift** (SQLite) as a local mirror of due cards and a queue for pending reviews
2. When a user rates a card offline, the review is written to a local `pending_reviews` table immediately
3. A background sync service periodically (or on reconnect) POSTs pending reviews to the server in chronological order
4. The server recomputes FSRS state from the queued reviews and returns updated due dates
5. The local cache is updated with the server's response

## Rationale

- Users study anywhere without interruption
- Optimistic writes (write locally first, sync later) give immediate feedback without waiting for a network round-trip
- Sending reviews in order to the server is safe: FSRS is deterministic given the same input sequence
- Conflict resolution is simple: server is authoritative; if the same card was somehow reviewed on two devices offline, the last review wins (rare edge case)

## Alternatives considered

| Option | Reason rejected |
|---|---|
| Online-only | Unacceptable UX; studying requires internet |
| Client-side FSRS + merge | Requires Dart FSRS implementation; complex multi-device merge logic (see ADR-0007) |
| Full CRDT-based sync | Massive complexity for marginal benefit in this use case |

## Consequences

- Phase 4 adds `Drift` schema and a `SyncService` to the Flutter app
- Local Drift tables: `CachedFlashcard`, `CachedReviewConfig`, `PendingReview`
- A `sync_status` indicator in the app UI shows `synced` / `pending (N)` / `offline`
- The server `POST /study/sync` endpoint accepts a batch of `{ flashcard_id, review_config_id, rating, reviewed_at }` records and returns updated FSRS state for each
- If a sync fails partially, unsynced reviews remain in `pending_reviews` and are retried on the next sync cycle
