# P04 — Artifact Sync Factoring — 2026-10-03

## LAUNCH ORDER

1. **Current-runtime authority/failure analysis — COMPLETE**
   - Establish the actual provider-backed artifact class and the failure mode.
   - Freeze authority, storage, privacy, conflict, and native-write semantics.
2. **Current-runtime repository contract publication — ACTIVE IN THIS SPRINT**
   - Persist the reusable `artifact-sync` boundary, v1 binding/receipt contracts, sanitized fixture, and deterministic local-agent packet.
3. **Cursor — Rust CLI implementation**
   - Consume `docs/examples/runtime-handoff.artifact-sync-rust-cli.json`.
   - Implement only the frozen contract.
4. **CI convergence**
   - Run repository + Rust validation on the exact Cursor head.
5. **Live-provider certification — WAITING**
   - Requires explicit credentials/runtime availability and remains outside the Cursor packet.

**PARALLEL EXECUTION: NOT_APPLICABLE — dependency graph width is 1.**  
Architecture and provider/storage semantics must be frozen before the implementation lane; CI depends on the implementation head; live-provider certification depends on the implementation.

## COMPACT PREFLIGHT

- Repository: `EndeavorEverlasting/Automation`
- Base branch: `main`
- Refreshed base head: `a2fdfe964aeef29de164b97e00cb7b509f0bcaed`
- Open PRs at preflight: none
- Recent center of gravity: repository-owned prompt invocation, runtime handoff/privacy boundaries, reusable seam doctrine, and the first admitted capability core.
- Existing reusable mechanism to extend: capability/adapters/contracts plus `automation-runtime-handoff-packet/v1`.
- Missing mechanism: provider-backed artifact synchronization with explicit storage/freshness/authority semantics.
- Current source evidence: the representative document was resolved through the connected provider as a **native provider document**, not a raw Word/blob file. Its raw locator is protected runtime evidence and is intentionally absent from this public plan.
- Observed harness defect: a provider-backed formatting task produced a local derivative and stopped there, despite an existing provider source. This creates source-of-truth drift and unnecessary local storage.

## RUNTIME PARTITION

| Work unit | Host | Provider route | State | Evidence / boundary |
| --- | --- | --- | --- | --- |
| Establish representative artifact class and source authority | `CURRENT_CHAT_RUNTIME` | connected workspace provider | COMPLETE | protected exact-source metadata; no raw locator tracked |
| Freeze reusable sync/storage/privacy/native-write contract | `CURRENT_CHAT_RUNTIME` | GitHub | COMPLETE when this plan commit is pushed | public sanitized contract only |
| Implement Rust CLI and synthetic adapter proof | `LOCAL_AGENT_RUNTIME` | none required | READY after architecture commit | consumes deterministic packet; no architecture judgment |
| Validate exact implementation head | `CI_OR_REMOTE_RUNNER` | GitHub Actions | WAITING | depends on Cursor head |
| Live OAuth/provider mutation certification | `LOCAL_AGENT_RUNTIME` or explicit current runtime with credentials | workspace provider | WAITING | separate authorization/proof gate |

Current-runtime work is not re-planned as Cursor work. Cursor inherits the frozen public contract.

## FACTORING LEDGER

### Harness spine

Keep:
- `planning.runtime_partition` upstream as placement authority.
- `automation-runtime-execution-handoff/v1` as the deterministic local-executor packet.
- public/private boundary rules that reject private provider IDs/URLs.

Strengthen:
- root wayfinding must identify provider-backed artifact synchronization as a reusable capability.
- local agents must receive exact storage, privacy, conflict, and authority semantics rather than infer them.

### Capability core

Create `capabilities/artifact-sync/`.

Core owns:
- semantic binding;
- authority/direction;
- freshness/conflict state machine;
- hashing/read-back verification;
- local materialization lifecycle;
- provider-neutral receipts;
- periodic polling contract.

### Provider adapter

First adapter target: workspace provider APIs.

Adapter owns:
- OAuth/token behavior;
- private locator resolution;
- exact-provider-object operations;
- change/revision translation;
- native document versus raw blob operations.

No provider identifier is committed to Automation.

### Provenance integration

Entire remains a provenance/checkpoint system around Git/agent work. It is not the sync transport and is not made responsible for provider scheduling. The safe seam is an invocation adapter that runs artifact-sync at declared checkpoints and lets Entire capture the resulting session context.

### Storage policy

Default: `ephemeral`.

A provider-backed artifact is not retained locally after successful provider write + read-back verification unless an explicit binding opts into a bounded persistent mirror.

This directly addresses limited local storage and prevents duplicate local artifacts from becoming accidental authority.

## RUST CLI SKETCH

Planned commands:

```text
artifact-sync validate-binding --binding <path>
artifact-sync status --binding <path>
artifact-sync sync --binding <path> --checkpoint before_consume
artifact-sync sync --binding <path> --checkpoint after_mutation
artifact-sync checkpoint --binding <path> --checkpoint handoff
artifact-sync periodic-poll --binding <path> --interval-seconds <n>
```

Design constraints:

- Rust stable.
- Provider-neutral core plus provider adapters.
- JSON receipts on stdout by default.
- Private locator resolution occurs at runtime; normal commands consume a semantic binding.
- No raw provider URL/ID is required in tracked config or CLI arguments.
- `ephemeral` local storage is the default.
- `fail_closed` is the only v1 conflict policy.
- provider-native docs reject raw-byte replacement.
- blocked/failed attempts remain retryable; they do not disable checkpoint or periodic synchronization.

Suggested implementation crates are an implementation detail, not contract identity. A workspace adapter can use generated Workspace API crates plus OAuth support; the contract must remain portable if those crates change.

## BINDING MANIFEST

Machine-readable authority:

- `capabilities/artifact-sync/schemas/binding.v1.json`
- sanitized fixture: `capabilities/artifact-sync/fixtures/binding.example.v1.json`

The tracked binding intentionally stores only a semantic `locator_handle`. The raw provider object locator belongs in protected runtime state.

## RECEIPT CONTRACT

Machine-readable authority:

- `capabilities/artifact-sync/schemas/receipt.v1.json`

A mutation cannot report `SYNCED` until provider write **and** read-back verification succeed. Conflict/auth/unresolved-locator failures are explicit states.

## COLLISIONS

- `.github/workflows/validate.yml` is shared and Cursor must refresh it before editing.
- `tests/test_artifact_sync_contracts.py` is reserved for this capability.
- Architecture files created by this sprint are frozen for Cursor; semantic redesign returns to a frontier/runtime judgment lane.

## PROOF GATES

Current sprint:
- public artifacts contain no raw private provider locators;
- binding fixture uses ephemeral materialization and fail-closed conflict handling;
- native document policy requires provider-native writes;
- Cursor packet validates under `automation-runtime-execution-handoff/v1`;
- repo branch/PR is created from refreshed `main`.

Cursor:
- `cargo fmt --check`;
- `cargo clippy --all-targets --all-features -- -D warnings`;
- `cargo test`;
- full Python repository tests;
- synthetic conflict/native-write/storage cleanup proof;
- exact-head CI.

Live provider:
- separate OAuth proof;
- exact identity resolution from protected state;
- provider freshness;
- one controlled pull and one controlled provider-native mutation;
- read-back verification;
- ephemeral local cleanup;
- receipt surfaced in session/provenance.

## PROOF CEILING

This P04 sprint can reach **designed + repository-persisted architecture + deterministic READY implementation packet**. It does not claim Rust implementation, live OAuth, live provider synchronization, deployment, or production verification.

## SUCCESSOR

Cursor consumes exactly:

`docs/examples/runtime-handoff.artifact-sync-rust-cli.json`

It must not reinterpret the authority model, replace ephemeral-by-default storage, permit raw tracked provider locators, change fail-closed conflict semantics, or make local-only output an accepted provider-backed mutation result.
