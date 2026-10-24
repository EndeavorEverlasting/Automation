# PS-0131 — Provider-neutral receipt/claim preflight (candidate)

**Owner:** Automation, existing `parallel-dispatch` capability. **State:** source-level prototype, **not production enforced**. This is not a scheduler, writer, claim allocator, provider client, or new Prompt Scratch owner.

The stable contract is `automation.trusted-execution-preflight/v1`, implemented by `receipt_gate.py::preflight`. Consumers need a packet and **three independently authenticated host adapters**: `claim_reader(resource_id, claim_token)`, `receipt_reader(receipt_ref)`, and `head_reader(resource_id)`. No consumer needs to know the internal Automation repository layout or any Prompt Scratch spreadsheet URL.

## Admission semantics

The packet has exactly: `schema`, `task_key`, `lane_id`, `actor`, `owner`, `resource_id`, `expected_head` (immutable 40-character lowercase Git SHA), `claim_token`, `receipt_ref`, and `max_age_seconds` (integer 1–3600).

The live claim adapter must return exactly `lane_id`, `actor`, `owner`, `resource_id`, `expected_head`, `claim_token`, `state=ACTIVE`, provider-issued `issued_at_epoch`, `deadline_epoch`, and positive integer `fence`. The live receipt adapter must return exactly `receipt_ref`, `lane_id`, `actor`, `owner`, `resource_id`, `head`, `evidence_sha256`, `observed_at_epoch`, `state=PROVIDER_VERIFIED`, and matching `fence`. The head adapter must return the current immutable Git head for the same resource.

Preflight rejects: missing/malformed fields, Unicode invisible-only identities, mismatched actor/owner/lane/resource/claim token/fence, missing readers, provider failures, expired/future-issued claim, inverted claim window, pre-claim receipt replay, stale/future receipt, absent digest, changed head, and unverified receipt. It returns `ADAPTER_ASSERTED_PREFLIGHT_ONLY` only after a consistent triple of adapter responses. **A fabricated adapter can fabricate this result**: caller/host must establish independent provider authentication. Never convert synthetic fixtures or spreadsheet assertions into execution authority.

The claim reader MUST obtain `issued_at_epoch` from the authoritative claim producer, not reconstruct it from the receipt, current clock, or caller input. This is a fail-closed tightening of the candidate v1 claim adapter shape: adapters without issuance evidence are rejected. A receipt predating its current claim cannot be promoted merely because it is within TTL and matches the same resource/head/fence. The gate remains adapter-asserted until trusted provider provenance and executor fencing are independently established.

## Explicit boundaries

- This preflight **does not allocate or atomically renew a claim**. The existing `lease_ledger.py` owns local SQLite lease transitions; a real host/provider adapter must bind a current claim to its own durable state.
- This preflight **does not enforce fencing of external writes**. Every mutating executor must check a live claim/fence again at the side-effect boundary, enforce idempotency, and reject stale work. An expired lease does not terminate an external process.
- This preflight **does not verify post-execution changes**. Repository/provider readback, exact revision, independent acceptance and proof ceiling remain downstream.
- It does not authenticate a Python callback merely because the callback returned `PROVIDER_VERIFIED`. Production requires an independently trusted adapter, not a spreadsheet or caller-controlled dictionary.
- It does not start agents, mutate user Priority, write Prompt Usage, alter Scheduled Tasks, or make decisions for TokenCorridor.

## Reproducible validation

```bash
python -m unittest discover -s tests -p 'test_parallel_dispatch_receipt_gate.py' -v
python -m unittest discover -s tests -p 'test_parallel_dispatch_native_manifest_contract.py' -v
python -m unittest discover -s tests -p 'test_parallel_dispatch_lease_ledger.py' -v
```

The native manifest parity test enforces `run.py::ID` and `receipt_gate.py::_NATIVE_RESOURCE_ID` equality. The synthetic tests prove deterministic rejection only, not provider authentication. A normal consumer needs only the published semantic packet and three adapters; the capability must pass an isolated import/consumer canary before reusable integration is claimed.

**Next integration gate:** trusted provider-backed adapter + real executor-side fence + independently read-back receipt; then exact-head CI, collision test, and authorized merge. Do not promote this prototype into production simply because tests are green.
