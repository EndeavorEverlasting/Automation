# Artifact Continuity Inheritance Repair — 2026-10-03

## Why this exists

A recurring operator correction established that new repositories repeatedly rediscover the same artifact-delivery principle: when an exact provider-backed artifact already exists, the workflow should preserve that authority and surface the provider artifact rather than silently stopping at a new local download.

This is recurrence evidence. The defect is not merely missing synchronization code; it is missing **activation and future inheritance**.

## Factoring correction

- `artifact-continuity-preflight/v1` owns the trigger/inheritance decision.
- `artifact-sync` owns synchronization mechanics after a binding is selected.
- provider-capable current runtimes perform provider work they can actually perform;
- lower-capability local executors inherit sanitized decisions and do not rediscover authority;
- new repository/bootstrap paths reference the semantic contract instead of copying prose;
- existing repositories migrate by representative archetype.

## Review-driven repairs before Rust

The first artifact-sync contract review exposed real holes, now repaired in the architecture layer:

1. local/bidirectional authority requires an explicit semantic local-side handle;
2. every binding carries a semantic private durable baseline-state handle;
3. bidirectional sync with two existing sides and no baseline fails closed as `BLOCKED_NO_BASELINE`;
4. successful pulls do not require provider writes;
5. artifact-sync gates only work that consumes/mutates the bound artifact, not unrelated commits;
6. deterministic validators cover binding semantics and artifact-continuity preflight;
7. public locator scanning covers the tracked design/plan surfaces used by this work.

## Proof ceiling

Repository contract/validator/CI proof only. Rust implementation, live provider mutation, repository-bootstrap generator adoption, upstream Prompt Kit adoption, deployment, and production behavior remain separately proven states.
