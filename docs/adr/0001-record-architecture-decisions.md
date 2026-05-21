# 1. Record architecture decisions

Date: 2026-05-21

## Status

Accepted

## Context

Decisions about architecture (chosen libraries, patterns, trade-offs) get lost if only captured in commits or chat. Future contributors need to know *why* a decision was made, not just what was built.

## Decision

Use lightweight ADRs in `docs/adr/<NNNN>-<slug>.md`. Append-only — never edit Accepted ADRs; supersede instead.

## Consequences

**Positive:** Long-term context survives. PR reviews can reference an ADR. Onboarding has a paper trail.
**Negative:** Small overhead per non-trivial decision.
**Neutral:** Following Michael Nygard's lightweight format.

## Alternatives considered

- Wiki-only — easy to lose, hard to version with code.
- Code comments — too local, no history of alternatives.

## References

- Michael Nygard, "Documenting Architecture Decisions" (2011).
