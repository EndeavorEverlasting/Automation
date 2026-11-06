# Artifact Sync

`artifact-sync` is the reusable synchronization boundary for provider-backed artifacts that must remain fresh without turning every consumer repository or agent into a provider client.

## Activation versus mechanics

The repository-wide `artifact-continuity-preflight/v1` contract decides **when** an existing provider-backed source applies and **which fidelity dimensions** the task requires. This capability owns **how** synchronization and verification proceed after a binding is selected.

Repeated rediscovery of cloud/source authority or requested representation fidelity is therefore an activation/inheritance defect, not a reason to redesign synchronization in every repository.

## Fidelity is dimensioned

Synchronization is not merely "same file identity" or "same text."

The contract distinguishes:

- `identity` — correct canonical/provider object;
- `content` — required textual/data/media content;
- `structure` — sections, hierarchy, ordering, tables, document organization;
- `presentation` — formatting, typography, spacing, color, sizing, visual layout.

Task intent selects required dimensions. A `format` task requires `presentation`. If a formatted local derivative looks correct while the authoritative provider source remains visually unchanged, the task is **not synchronized**.

## Ownership

Core owns binding validation, semantic identity, authority/direction evaluation, checkpoint synchronization, durable baseline recovery, freshness/conflict transitions, fidelity verification state, local materialization policy, receipts, and periodic polling contract.

Provider adapters own authentication, private locator resolution, provider revision/change-token translation, provider-native reads/writes, provider-side structure/style read-back, watch/poll behavior, and provider error translation.

Integrations own calling the stable CLI at declared artifact checkpoints, attaching evidence to provenance systems such as Entire, and consumer-specific semantic bindings.

Entire is provenance, not file transfer, scheduling, authority selection, conflict resolution, or visual verification.

## Storage default

Provider-backed artifacts default to ephemeral local materialization:

1. resolve exact provider identity from protected runtime state;
2. recover the last common verified baseline;
3. check provider freshness;
4. determine required fidelity dimensions from the preflight/task;
5. materialize only when local bytes are needed;
6. perform the bounded operation;
7. for provider-bound mutation, write through the correct provider API;
8. read back and verify every required fidelity dimension;
9. advance the durable baseline only after successful verification;
10. emit a receipt;
11. clean ephemeral bytes after verified success.

Persistent mirrors are explicit and storage-bounded. A provider-backed edit never silently becomes a local-only canonical file.

## Identity, local side, and baseline

Tracked bindings use semantic handles. Raw provider IDs/URLs, local private paths, credentials, and private baseline-store locations stay outside public Git.

Local or bidirectional authority requires an explicit semantic `local_side` handle. Hidden consumer-specific path knowledge is not a contract.

Every binding carries a semantic private `baseline_state.state_handle`. Conflict detection compares current sides to that recovered common verified state.

A bidirectional sync with two pre-existing sides and no recoverable common baseline emits `BLOCKED_NO_BASELINE`.

## Native provider documents versus blob files

Blob files may use byte operations when supported. Native documents/spreadsheets/presentations require provider-native mutation APIs. Exported local files are projections, not writable canonical identity.

For provider-native formatting tasks, provider-native write plus presentation verification is part of completion. A local DOCX/PDF export with the requested styling is not proof that the native provider document has that styling.

## Checkpoints

Required trigger vocabulary:

- `before_consume`
- `after_mutation`
- `handoff`
- `periodic`

Checkpoint synchronization is the correctness path. Periodic polling is recovery/convenience and cannot waive before-use, pre-write, or required-fidelity verification.

## Success semantics

- Pull: may report `SYNCED` after provider freshness/read and all required local fidelity dimensions are verified. No provider write is required.
- Provider-bound push/reconcile: may report `SYNCED` only after provider write, provider read-back, and all required fidelity dimensions are verified.
- Format: `presentation` is mandatory. Missing presentation verification makes `SYNCED` invalid.
- Durable baseline advances only after required verification.
- Blocked/failed attempts remain retryable and do not disable later checkpoints.

Deterministic receipt validation:

```text
python scripts/validate_artifact_sync_receipt.py --receipt <receipt.json>
```

The formatting-parity negative canary intentionally represents a local formatted derivative with an unchanged/unverified provider presentation and must fail validation.

## Entire integration boundary

Only work that consumes or mutates the **bound artifact** is gated on its artifact-sync result. Unrelated repository changes are not blocked merely because a provider is unavailable.

A future Entire/hook adapter may invoke artifact-sync for covered work units and preserve surrounding session/checkpoint provenance. It does not replace provider-side or rendered presentation proof.

## Future inheritance and visual proof

New repository/bootstrap tooling should expose `artifact-continuity-preflight/v1` from root wayfinding or a pinned shared dependency. Existing repositories migrate by representative archetype.

A future screenshot/render comparison capability can verify `presentation` without relying on agent visual judgment by rendering donor/reference and target artifacts through deterministic adapters and comparing the resulting evidence. That is a successor validation seam, not a substitute for the current fidelity contract.

## Proof ceiling

Current repository work defines activation/binding/receipt/baseline/fidelity contracts and deterministic validators. Rust implementation, live OAuth/provider mutation, deterministic render comparison, deployment, and production synchronization remain unproven.
