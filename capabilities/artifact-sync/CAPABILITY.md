# Artifact Sync

`artifact-sync` is the reusable synchronization boundary for provider-backed artifacts that must remain fresh without turning every consumer repository or agent into a provider client.

## Why this capability exists

A provider-backed source should not silently become a pile of local derivatives merely because a local tool can generate files more easily than it can update the source provider. That behavior creates stale duplicates, consumes local storage, obscures authority, and makes downstream agents rediscover where the real file lives.

The capability therefore treats **artifact identity, authority, freshness, storage policy, conflict handling, and proof** as first-class contract fields.

## Ownership

### Core owns

- binding validation and semantic artifact identity;
- authority/direction decisions;
- checkpoint-triggered synchronization;
- freshness and conflict state transitions;
- content hashing and read-back verification;
- local materialization policy;
- provider-neutral receipts;
- periodic polling contract.

### Provider adapters own

- authentication and token lifecycle;
- resolving a semantic `locator_handle` to the exact provider object from protected runtime state;
- provider revision/change-token APIs;
- provider-native reads/writes;
- watch/poll behavior and provider error translation.

### Integrations own

- calling the stable CLI at declared checkpoints;
- attaching sync evidence to a provenance system such as Entire;
- consumer-specific semantic bindings.

Entire is **provenance**, not the file-transfer engine and not the scheduler. A checkpoint integration may invoke artifact-sync and let Entire preserve the surrounding agent/commit context, but provider transfer and conflict logic stay in this capability.

## Storage default

Provider-backed artifacts default to **ephemeral local materialization**:

1. Resolve the exact provider object through protected runtime state.
2. Check provider freshness before use.
3. Materialize only when the consumer actually needs local bytes.
4. Perform the bounded operation.
5. For provider-bound mutation, write through the correct provider API.
6. Read back and verify.
7. Emit a receipt.
8. Delete ephemeral bytes after verified success.

A persistent local mirror is opt-in and must declare a storage budget. A successful provider-backed edit must never silently stop at a local-only file just because that is easier.

## Native provider documents versus blob files

These are different mutation classes.

- **Blob files** may use byte download/update semantics when the adapter supports them.
- **Native documents/spreadsheets/presentations** must use provider-native mutation APIs. Exported local files are projections, not writable canonical identity.

The core must reject raw-byte replacement when the bound artifact kind is provider-native.

## Identity and privacy

Tracked bindings use:

```json
{
  "provider": {
    "adapter_id": "workspace-provider",
    "locator_handle": "private:example-provider-backed-document",
    "locator_resolution": "private_runtime_only"
  }
}
```

The actual provider object identifier and account context live outside public Git. Filename/title search may help discovery during an explicit intake workflow, but it never becomes the synchronization identity.

## Checkpoint model

Required trigger vocabulary:

- `before_consume`
- `after_mutation`
- `handoff`
- `periodic`

Checkpoint synchronization is the correctness path. Periodic polling is a convenience/recovery path and cannot waive freshness checks required before use or write.

## Conflict rule

V1 is deliberately conservative: **fail closed**.

If both authoritative sides changed since the last common verified receipt, emit `BLOCKED_CONFLICT`. Do not guess, merge opaque binaries, or let a lower-capability executor select a winner.

## Rust CLI contract

The planned executable is `artifact-sync`.

```text
artifact-sync validate-binding --binding <binding.json>
artifact-sync status           --binding <binding.json>
artifact-sync sync             --binding <binding.json> --checkpoint before_consume
artifact-sync sync             --binding <binding.json> --checkpoint after_mutation
artifact-sync checkpoint       --binding <binding.json> --checkpoint handoff
artifact-sync periodic-poll    --binding <binding.json> --interval-seconds <n>
```

Common requirements:

- provider locator resolution is private runtime state;
- JSON receipt goes to stdout by default;
- `--receipt <path>` is optional and should normally target ignored/private runtime storage;
- no command accepts a raw provider URL or identifier as the normal tracked invocation path;
- mutation commands perform pre-write freshness, write, and read-back verification;
- nonzero exit status distinguishes blocked/conflict/auth/validation failures from success.

V1 implementation should use Rust stable with a small provider-neutral core. The first provider adapter may use generated Workspace API Rust crates plus OAuth support, but provider crates stay behind the adapter boundary.

## Entire integration boundary

Entire associates agent sessions/checkpoints with Git work. Artifact Sync should not modify Entire's checkpoint storage format.

The initial integration is deliberately thin:

1. Agent/harness invokes `artifact-sync sync ...` at the declared artifact checkpoint.
2. The sync receipt is emitted in the session transcript and may optionally be written to ignored runtime output.
3. Code/document changes proceed only after a PASS-like sync state.
4. When the repo commit occurs, Entire preserves the surrounding session/checkpoint provenance.
5. A future hook adapter may automate invocation, but hook ordering must not make provider availability a hidden dependency of unrelated Git commits.

## Proof ceiling

The current repository state defines the v1 architecture and deterministic contracts. It does **not** yet prove the Rust executable, live OAuth, live provider mutation, periodic service installation, or production synchronization.
