# ADR-0007: Run SRS scheduling server-side

**Date:** 2026-03-28
**Status:** Accepted

## Context

The FSRS algorithm must compute the next review date for each flashcard after a rating is submitted. This calculation can run either on the client (Flutter) or on the server (Python).

## Decision

**FSRS scheduling runs exclusively on the server.**

The Flutter client submits a rating (`1`–`4`) and receives back the updated card state and next due date. The client does not implement or run any SRS logic.

## Rationale

- A single authoritative source of truth for scheduling prevents drift between devices (if a user studies on phone and web, there is no conflict)
- `py-fsrs` is a well-tested Python library; re-implementing FSRS in Dart introduces risk of subtle differences
- Future algorithm updates (e.g., custom FSRS parameters per user, optimised weights from review history) only need to be deployed in one place
- The client remains thin and easier to maintain

## Alternatives considered

| Option | Reason rejected |
|---|---|
| Client-side scheduling (Dart FSRS) | Two implementations to maintain; sync conflicts between devices |
| Hybrid (client schedules offline, server reconciles) | Complex conflict resolution; not needed given the offline sync strategy already queues reviews |

## Consequences

- The study API is: client fetches due cards → user rates → client POSTs rating → server returns next due date
- During offline study (Phase 4), reviews are queued locally with a timestamp. When synced, the server recomputes scheduling from the queued ratings in order
- The `ReviewLog` table is the single source of truth for all scheduling state
- A `GET /study/{review_config_id}/stats` endpoint exposes retention data computed server-side
