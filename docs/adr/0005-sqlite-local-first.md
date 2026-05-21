# 5. SQLite local-first; no server in v2.0

Date: 2026-05-21

## Status

Accepted

## Context

History needs persistence. Options: server DB (Postgres), local SQLite, JSONL files.

## Decision

SQLite at `%APPDATA%/TrashSorter/history.db` via SQLAlchemy Core. Phase 2 (web) will run a separate Postgres + push events from desktop via signed webhook.

## Consequences

**Positive:** Zero infrastructure. Works offline. Single file backup. SQLAlchemy gives us schema migrations later.
**Negative:** No realtime cross-device view in v2.0.
**Neutral:** Per-device history can be merged at the web layer in phase 2.

## Alternatives considered

- Postgres in v2.0 — overkill for single-device deployment; pushes setup burden onto end user.
- JSONL only — query/aggregate cost grows linearly; CSV export is harder.

## References

- Phase 2 plan: separate spec.
