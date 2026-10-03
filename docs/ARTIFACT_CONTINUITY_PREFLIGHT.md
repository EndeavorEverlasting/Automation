# Artifact Continuity Preflight

This contract prevents a recurring harness defect: a provider-backed source already exists, yet an agent creates or returns a new local artifact and only later rediscovers that the provider source should have remained authoritative.

The preflight owns **activation**. `artifact-sync` owns **synchronization mechanics** after a binding is selected.

## Run it when

- entering or creating a repository/workflow with provider-backed artifacts;
- reading, editing, formatting, exporting, or creating a document/spreadsheet/presentation/file;
- an exact provider mapping is already known;
- a local download is about to be returned for work that began from a provider-backed source;
- closeout would leave a provider mutation unsynchronized.

Machine-readable authority:

- `harness/contracts/artifact-continuity-preflight.v1.json`
- `scripts/validate_artifact_continuity_preflight.py`
- `docs/examples/artifact-continuity-preflight.example.json`

## Decision order

1. Determine whether a provider-backed canonical source is already known.
2. If known, use exact source identity; do not rediscover by title/filename.
3. If the current runtime has provider access, keep provider-side source/freshness/mutation work in that runtime.
4. Provider-backed edit/format work with write authority completes against the provider source, not a local-only derivative.
5. Local materialization is ephemeral by default. Persistent output requires explicit export/mirror intent.
6. When provider access/write is unavailable, continue locally only when safe and carry an explicit unresolved sync obligation.
7. Return the verified provider link as the primary artifact reference when available.

## Future inheritance

Do not paste this rule into every new repository. New-repository/bootstrap tooling should depend on the semantic contract/version and expose it from root wayfinding. Existing repositories migrate by representative archetype.

Repeated rediscovery of this rule is evidence of a missing activation/inheritance seam, not evidence that the principle needs to be reinvented.
