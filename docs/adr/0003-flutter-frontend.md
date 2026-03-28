# ADR-0003: Use Flutter for all frontend targets

**Date:** 2026-03-28
**Status:** Accepted

## Context

The app must target:
1. Web (initial launch)
2. Android (second)
3. iOS (third)

A single codebase is strongly preferred to avoid duplicating UI logic. The primary developer knows some JS/TS but is primarily a Python developer.

## Decision

Use **Flutter** with a single `frontend/` package for web, Android, and iOS.

## Rationale

- Single Dart codebase compiles to native Android/iOS and a JS-based web app
- Dart is easy to pick up for a Python developer (similar OOP model, strong types)
- Flutter's widget model is self-contained — no dependency on platform-specific UI components, which ensures visual consistency across targets
- Large package ecosystem (`pub.dev`): `riverpod`, `go_router`, `drift`, `dio` cover all necessary concerns
- Flutter Web has improved significantly and is suitable for a study-oriented app (no heavy animation or canvas requirements)

## Alternatives considered

| Option | Reason rejected |
|---|---|
| React Native + React Web | Requires JS/TS expertise; two somewhat different paradigms for web vs native |
| PWA only | Limited native capabilities (notifications, offline storage APIs vary) |
| Native per platform | Infeasible for a single developer |
| Kotlin Multiplatform | Immature for shared UI layer; primarily targets logic sharing |

## Consequences

- `frontend/` contains the Flutter project
- State management: **Riverpod** (compile-safe, testable, no `BuildContext` threading required)
- Routing: **go_router** (URL-based routing works correctly on web)
- Local persistence: **Drift** (type-safe SQLite wrapper, works on all Flutter targets)
- HTTP: **Dio** (interceptors for auth token injection and refresh)
- The Flutter OpenAPI client is generated from the FastAPI `/openapi.json` during the Phase 3 setup step
