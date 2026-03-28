# ADR-0006: JWT-based authentication

**Date:** 2026-03-28
**Status:** Accepted

## Context

The app requires user authentication that works across:
- Flutter web (cookies are viable)
- Flutter mobile (no browser cookie jar; header-based auth is standard)
- Future third-party API clients

Multi-user support must be easy to add (no per-user server state).

## Decision

Use **JWT (JSON Web Tokens)** with a short-lived access token and a longer-lived refresh token.

- Access token: 15-minute expiry, sent as `Authorization: Bearer <token>` header
- Refresh token: 30-day expiry, stored in the database to allow revocation, returned in the login response body

Libraries: `python-jose[cryptography]` for JWT encoding/decoding, `passlib[bcrypt]` for password hashing.

## Rationale

- Stateless access tokens work identically on web and mobile Flutter clients
- Refresh token stored in the DB (as a hash) enables logout and revocation without server-side session state for every request
- `python-jose` and `passlib` are the standard FastAPI auth stack with extensive documentation
- No dependency on cookies means the mobile client has a simpler implementation

## Alternatives considered

| Option | Reason rejected |
|---|---|
| Session cookies | Don't work cleanly with Flutter mobile's `Dio` HTTP client |
| OAuth2 only (social login) | Adds external dependency; users need email/password login too |
| API keys only | No expiry mechanism; not suitable for user-facing login |

## Consequences

- `POST /auth/login` returns `{ access_token, refresh_token, token_type }`
- Flutter stores `access_token` in memory (Riverpod state) and `refresh_token` in `flutter_secure_storage`
- A Dio interceptor handles 401 responses by attempting a silent token refresh before retrying the original request
- `POST /auth/logout` deletes the refresh token record, invalidating that session
- Password reset flow (email-based) is out of scope for Phase 1 but the `User` model includes an `email` field for it
