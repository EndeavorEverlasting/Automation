# Artifact Sync

`artifact-sync` is the reusable synchronization boundary for provider-backed artifacts that must remain fresh without turning every consumer repository or agent into a provider client.

## Activation versus mechanics

The repository-wide `artifact-continuity-preflight/v1` contract decides **when** an existing provider-backed source must be considered before local artifact creation/return. This capability owns **how** synchronization proceeds after a binding is selected.

Repeated rediscovery of cloud/source authority is therefore an activation/inheritance defect, not a reason to redesign synchronization in every repository.

## Ownership

Core owns binding validation, semantic identity, authority/direction evaluation, checkpoint synchronization, durable baseline recovery, freshness/conflict transitions, hashing/read-back verification, local materialization policy, receipts, and periodic polling contract.

Provider adapters own authentication, private locator resolution, provider revision/change-token translation, provider-native reads/writes, watch/poll behavior, and provider error translation.

Integrations own calling the stable CLI at declared artifact checkpoints, attaching evidence to provenance systems such as Entire, and consumer-specific semantic bindings.

Entire is provenance, not file transfer, scheduling, authority selection, or conflict resolution.

## Storage default

Provider-backed artifacts default to ephemeral local materialization:

1. resolve exact provider identity from protected runtime state;
2. recover the last common verified baseline;
3. check provider freshness;
4. materialize only when local bytes are needed;
5. perform the bounded operation;
6. for provider-bound mutation, write through the correct provider API;
7. read back/verify as required;
8. advance the durable baseline only after successful verification;
9. emit a receipt;
10. clean ephemeral bytes after verified success.

Persistent mirrors are explicit and storage-bounded. A provider-backed edit never silently becomes a local-only canonical file.

## Identity, local side, and baseline

Tracked bindings use semantic handles. Raw provider IDs/URLs, local private paths, credentials, and private baseline-store locations stay outside public Git.

Local or bidirectional authority requires an explicit semantic `local_side` handle. Hidden consumer-specific path knowledge is not a contract.

Every binding also carries a semantic private `baseline_state.state_handle`. Conflict detection compares current sides to that recovered common verified state.

A bidirectional sync with two pre-existing sides and no recoverable common baseline emits `BLOCKED_NO_BASELINE`.

## Native provider documents versus blob files

Blob files may use byte operations when supported. Native documents/spreadsheets/presentations require provider-native mutation APIs. Exported local files are projections, not writable canonical identity.

## Checkpoints

Required trigger vocabulary:

- `before_consume`
- `after_mutation`
- `handoff`
- `periodic`

Checkpoint synchronization is the correctness path. Periodic polling is recovery/convenience and cannot waive before-use or pre-write freshness.

## Success semantics

- Pull: may report `SYNCED` after provider freshness/read and downloaded/local content verification. No provider write is required.
- Provider-bound push/reconcile: may report `SYNCED` only after provider write and provider read-back verification.
- Durable baseline advances only after required verification.
- Blocked/failed attempts remain retryable and do not disable later checkpoints.

## CLI target

```text
artifact-sync validate-binding --binding <binding.json>
artifact-sync status           --binding <binding.json>
artifact-sync sync             --binding <binding.json> --checkpoint before_consume
artifact-sync sync             --binding <binding.json> --checkpoint after_mutation
artifact-sync checkpoint       --binding <binding.json> --checkpoint handoff
artifact-sync periodic-poll    --binding <binding.json> --interval-seconds <n>
```

Tracked invocations use semantic bindings, not raw provider URLs/IDs. JSON receipts go to stdout by default.

## Entire integration boundary

Only work that consumes or mutates the **bound artifact** is gated on its artifact-sync result. Unrelated repository changes are not blocked merely because a provider is unavailable.

A future Entire/hook adapter may invoke artifact-sync for covered work units and preserve the surrounding session/checkpoint provenance, but provider availability must never become a hidden dependency of unrelated commits.

## Future inheritance

New repository/bootstrap tooling should expose `artifact-continuity-preflight/v1` from root wayfinding or a pinned shared dependency. Existing repositories migrate by representative archetype rather than copying provider rules by hand.

## Proof ceiling

Current repository work defines activation/binding/receipt/baseline contracts and deterministic validators. Rust implementation, live OAuth/provider mutation, service installation, deployment, and production synchronization remain unproven.
