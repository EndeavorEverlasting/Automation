# Artifact Continuity Preflight

This contract prevents a recurring harness defect: a provider-backed source already exists, yet an agent creates or returns a new local artifact and only later rediscovers that the provider source should have remained authoritative.

The preflight owns **activation and required fidelity**. `artifact-sync` owns **synchronization mechanics and verification** after a binding is selected.

## Run it when

- entering or creating a repository/workflow with provider-backed artifacts;
- reading, editing, formatting, exporting, or creating a document/spreadsheet/presentation/file;
- an exact provider mapping is already known;
- a local download is about to be returned for work that began from a provider-backed source;
- closeout would leave a provider mutation or requested representation change unsynchronized.

Machine-readable authority:

- `harness/contracts/artifact-continuity-preflight.v1.json`
- `scripts/validate_artifact_continuity_preflight.py`
- `docs/examples/artifact-continuity-preflight.example.json`

## Decision order

1. Determine whether a provider-backed canonical source is already known.
2. If known, use exact source identity; do not rediscover by title/filename.
3. Determine the required fidelity dimensions: `identity`, `content`, `structure`, and/or `presentation`.
4. Formatting work requires `presentation`; keeping the same text/images while leaving provider styling unchanged is not success.
5. If the current runtime has provider access, keep provider-side source/freshness/mutation work in that runtime.
6. Provider-backed edit/format work with write authority completes against the provider source, not a local-only derivative.
7. Local materialization is ephemeral by default. Persistent output requires explicit export/mirror intent.
8. When provider access/write is unavailable, continue locally only when safe and carry an explicit unresolved sync obligation.
9. Return the verified provider link as the primary artifact reference when available.

## The formatting-parity regression

A formatted local DOCX and an unchanged native cloud document are **not equivalent synchronized outputs** merely because they contain the same screenshots/text and refer to the same semantic artifact.

For a format task, completion requires the authoritative target to satisfy the presentation requirement and for that presentation dimension to be verified. A local derivative can be useful evidence or an explicit export, but it cannot substitute for provider-side formatting completion.

The deterministic negative canary is:

`capabilities/artifact-sync/fixtures/receipt.formatting-local-only-invalid.v1.json`

It deliberately claims `SYNCED` while presentation is unverified and provider write/read-back did not occur. The receipt validator must reject it.

## Future inheritance

Do not paste this rule into every new repository. New-repository/bootstrap tooling should depend on the semantic contract/version and expose it from root wayfinding. Existing repositories migrate by representative archetype.

Repeated rediscovery of this rule is evidence of a missing activation/inheritance seam, not evidence that the principle needs to be reinvented.

## Future visual proof seam

Provider/API structural read-back is necessary but may not be sufficient for visual formatting work. A future deterministic render/screenshot comparison seam can supply presentation evidence by comparing a donor/reference rendering with the authoritative target rendering. That future mechanism strengthens verification; it does not redefine artifact authority.
