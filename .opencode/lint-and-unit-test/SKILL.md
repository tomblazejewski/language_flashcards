---
name: lint-and-unit-test
description: Run ruff lint, ty type checking, pytest unit tests, and integration tests for this repo; interpret all results and surface actionable failures
compatibility: opencode
---

## What I do

Run the CI quality gates for this repo in sequence.

## When to use me

- Before committing or opening a PR
- After writing or editing production/test code
- When the user asks to "verify", "check", "run CI", "lint", "type-check", or "run tests"
- After significant (non-patch) changes, also run the integration test suite (Step 5)

## Procedure

### Step 1 — Lint

```bash
uv run ruff check
```

### Step 2 — Format

```bash
uv run ruff format
```

### Step 3 — Type check

```bash
uv run ty check
```

### Step 4 — Unit tests

```bash
uv run pytest
```

### Step 5 — Integration tests (after significant / non-patch changes)

Run this after any change larger than a single-line patch (e.g. new features, refactors, bug fixes touching multiple files):

```bash
uv run pytest tests/integration_tests
```
