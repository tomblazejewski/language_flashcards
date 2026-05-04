# Domain Docs

This is a **single-context** repo.

## Layout

- `CONTEXT.md` — domain glossary at the repo root (create lazily when first term is resolved)
- `docs/adr/` — architectural decision records at the repo root

## Consumer rules

- Always read `CONTEXT.md` before naming things, writing tests, or proposing interfaces. Use its vocabulary exactly.
- Always read relevant ADRs in `docs/adr/` before proposing architectural changes. Don't re-litigate closed decisions.
- If `CONTEXT.md` does not exist yet, create it when the first domain term is resolved during a session.
- New ADRs go in `docs/adr/` with the next sequential number (currently at `0009`).
