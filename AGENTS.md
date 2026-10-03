# AGENTS.md

## Repository identity

This repository is a **ubiquitous automation substrate**.

Treat `docs/REPOSITORY_CHARTER.md` as the canonical ownership contract and `CONTRIBUTING.md` as the canonical contribution/placement policy.

### Non-negotiable execution rules

- Keep core automation repository-, domain-, platform-, and consumer-agnostic.
- Isolate repository/provider/domain-specific behavior behind adapters, integrations, profiles, manifests, or configuration.
- Do not hard-code one consuming repository's paths, schemas, naming, credentials, product assumptions, or release lifecycle into shared core logic.
- Prefer deterministic machine-readable inputs, outputs, schemas, manifests, and receipts.
- Never commit secrets, authenticated browser profiles, cookies, tokens, or private runtime state.
- Reuse existing contracts and helpers before creating competing mechanisms.
- If a proposed feature is inseparable from one product's business logic, leave it with that product instead of contaminating this repository's core.
- Do not claim universal compatibility beyond observed validation.

## Seam / boundary review contract

When work creates or changes a shared interface, cross-repository dependency, adapter, provider bridge, package boundary, scheduler boundary, data authority, generated artifact, CLI surface, or other reusable seam, read:

- `harness/contracts/seam-boundary-review.v1.json`
- `docs/SEAM_BOUNDARY_REVIEW.md`

Required review behavior:

1. Identify the true owner.
2. Run the **Consumer Knowledge Test**: list what a normal consumer must know.
3. Treat upstream topology, donor repositories, migration history, provider quirks, and authority-routing rules as suspected leakage unless the public contract explicitly requires them.
4. Separate semantic contract identity from physical repo/path/provider location.
5. Verify fresh-agent discoverability from root wayfinding.
6. Treat repeated downstream discovery/routing/mirroring as evidence of upstream contract pressure.
7. Prove portability with an **Isolated Consumer Canary** when the seam is intended to be reusable.
8. After repairing the owner, migrate a real consumer and remove obsolete compensating downstream machinery.
9. Add a regression that prevents the obsolete path from silently returning.

Correct ownership alone is not a PASS. A seam remains defective when normal consumers still need implementation knowledge.

## Prompt invocation contract

P-number semantics are an **upstream dependency**. Automation consumes `prompt-invocation-upstream/v1`; it does not own prompt discovery, registry composition, authority routing, creation, mutation, or retirement.

When the operator supplies or references a P-number:

1. Read `docs/PROMPT_RUNTIME.md`.
2. Resolve the **verbatim operator text** through:
   `python scripts/prompt_runtime.py --text "<operator text>"`
3. Treat the returned upstream packet as prompt identity/intent authority.
4. Never substitute remembered prompt text, fuzzy-match another ID, inspect Prompt Kit registry topology, or require a Triage checkout.
5. `EXECUTE` means execute the resolved workflow now.
6. `EXECUTE_AND_IMPLEMENT` means execute it and carry authorized local implementation through reachable proof gates.
7. Prompt mutation/governance belongs upstream; Automation does not invent a downstream contribution lifecycle.
8. Preserve separate proof states for resolution, execution, implementation, integration, deployment, and production behavior.

Pinned dependency manifest: `vendor/prompt-invocation-upstream/manifest.v1.json`.

## Runtime execution handoff contract

Automation consumes `planning.runtime_partition` as a semantic upstream dependency. This repository validates execution-facing placement; it does not invent a competing planner or broker.

Before executing a runtime-distributed packet:

1. Read `harness/contracts/runtime-execution-handoff.v1.json`.
2. Read `docs/RUNTIME_DISTRIBUTION.md` and `docs/PUBLIC_PRIVATE_BRIDGE.md`.
3. Validate the packet with:
   `python scripts/validate_runtime_handoff.py --packet <packet.json> --require-ready`
4. Treat `UNKNOWN_RUNTIME` as blocked, not executable.
5. Execute only `owned_scope`; preserve `forbidden_scope`.
6. Refresh only facts named by `freshness_requirements`; do not rediscover already inherited evidence without a freshness reason.
7. Return the requested artifacts and acceptance-gate evidence without collapsing proof states.

Local executors such as Cursor/OpenCode execute exact READY packets. They do not decide canonical ownership, select a different prompt, broaden scope, or replace the runtime-placement decision.

No contract may assume a frontier model is executing it. Architecture or ownership judgment must be resolved and persisted before a packet becomes READY.

### Public/private execution boundary

- Never commit private continuity-store URLs/IDs, credentials, authenticated browser/session state, or person-specific workstation paths.
- Public tracked packets use semantic identities, repository-relative paths, sanitized evidence, and synthetic fixtures.
- A private continuity store may reference public Automation; Automation must not require a backlink to that private store.

## P92 canonical-path contract

Before emitting path-sensitive mutation commands, read `harness/contracts/canonical-path.v1.json` and run:

`python scripts/path_receipt.py --repo-root .`

Treat its machine-readable receipt as the current path/execution-context evidence.

- Do not invent a new checkout path because the current one is unknown.
- An unresolved development root is `UNKNOWN_BLOCK_NEW_CLONE`.
- Production/use paths are capability-owned; `UNKNOWN` production use blocks production mutation but not safe development work.
- Remote merge success is not local deployment proof.

Before substantial mutation, recover current repository/provider truth and preserve these invariants.


## Provider-backed artifact synchronization

When work reads or mutates a provider-backed artifact, read:

- `capabilities/artifact-sync/CAPABILITY.md`
- `capabilities/artifact-sync/schemas/binding.v1.json`
- `capabilities/artifact-sync/schemas/receipt.v1.json`

Execution invariants:

1. Tracked public configuration uses a semantic `locator_handle`; raw provider IDs, URLs, account identity, credentials, and tokens remain protected runtime state.
2. Exact provider identity is authoritative. Filename/title search is discovery only and never the synchronization identity.
3. Provider-backed artifacts default to ephemeral local materialization. Persistent mirrors require an explicit bounded storage policy.
4. A provider-backed edit may not claim completion when it only created a local derivative and failed to update/read back the authoritative provider source.
5. Native documents/spreadsheets/presentations require provider-native mutation APIs. Raw byte replacement is for blob files only.
6. V1 conflicts fail closed. A local executor must not choose a winner when both sides changed.
7. Checkpoint triggers are `before_consume`, `after_mutation`, `handoff`, and `periodic`. Periodic checks do not replace before-use or pre-write freshness.
8. Entire may preserve provenance around the operation, but artifact-sync owns transfer/conflict/storage behavior.
9. Local executors implement the frozen contract; they do not redesign authority, privacy, storage, native-write, or conflict semantics.
