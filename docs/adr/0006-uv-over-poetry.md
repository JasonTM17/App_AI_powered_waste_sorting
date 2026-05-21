# 6. uv over Poetry for dependency management

Date: 2026-05-21

## Status

Accepted

## Context

We need a reproducible Python dep manager and venv tool. Choices: pip+venv, Poetry, Hatch, PDM, uv (astral.sh).

## Decision

Use uv (`python -m uv` invocation since binary not on PATH on this box). Lockfile committed.

## Consequences

**Positive:** ~10× faster install vs Poetry. Auto-fetches managed CPython if local version is unsupported (avoided system-Python-3.14 incompatibility for ultralytics). Single binary tool.
**Negative:** Newer ecosystem (active 2024–2026), some plugins still missing. Some teams unfamiliar.
**Neutral:** PEP 621 `pyproject.toml` keeps us portable — switching to Poetry/Hatch later requires only re-running their lock command.

## Alternatives considered

- Poetry — rejected for slower resolver and weaker Python-version management.
- pip-tools — rejected for no built-in venv/python management.

## References

- https://docs.astral.sh/uv/
