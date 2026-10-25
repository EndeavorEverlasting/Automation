# PS-0131 — Provider-neutral receipt/claim preflight (candidate)

**Owner:** Automation, existing `parallel-dispatch` capability. **State:** source-level prototype, **not production enforced**. This is not a scheduler, writer, claim allocator, provider client, or new Prompt Scratch owner.

The stable contract is `automation.trusted-execution-preflight/v1`, implemented by `receipt_gate.py::preflight`. Consumers need a packet and **three independently authenticated host adapters**: `claim_reader(resource_id, claim_token)`, `receipt_reader(receipt_ref)`, and `head_reader(resource_id)`. No consumer needs to know the internal Automation repository layout or any Prompt Scratch spreadsheet URL.

## Admission semantics

The packet has exactly: `schema`, `task_key`, `lane_id`, `actor`, `owner`, `resource_id`, `expected_head` (immutable 40-character lowercase Git SHA), `claim_token`, `receipt_ref`, and `max_age_seconds` (integer 1–3600).

The live claim adapter must return exactly `task_key`, `lane_id`, `actor`, `owner`, `resource_id`, `expected_head`, `claim_token`, `state=ACTIVE`, provider-issued `issued_at_epoch`, `deadline_epoch`, and positive integer `fence`. The live receipt adapter must return exactly `receipt_ref`, `task_key`, `lane_id`, `actor`, `owner`, `resource_id`, `head`, `evidence_sha256`, `observed_at_epoch`, `state=PROVIDER_VERIFIED`, and matching `fence`. The head adapter must return the current immutable Git head for the same resource.

Both independent provider records must bind the same `task_key` as the packet; lane/resource/actor/fence/head equality alone is insufficient because an otherwise matching receipt could be replayed across task namespaces. This is a fail-closed candidate-schema tightening; adapters omitting `task_key` are rejected. No production adapter currently exists to migrate.

Preflight rejects: missing/malformed fields, Unicode invisible-only identities, mismatched actor/owner/lane/resource/claim token/fence, missing readers, provider failures, expired/future-issued claim, inverted claim window, pre-claim receipt replay, stale/future receipt, absent digest, changed head, and unverified receipt. It returns `ADAPTER_ASSERTED_PREFLIGHT_ONLY` only after a consistent triple of adapter responses. **A fabricated adapter can fabricate this result**: caller/host must establish independent provider authentication. Never convert synthetic fixtures or spreadsheet assertions into execution authority.

The claim reader MUST obtain `issued_at_epoch` from the authoritative claim producer, not reconstruct it from the receipt, current clock, or caller input. This is a fail-closed tightening of the candidate v1 claim adapter shape: adapters without issuance evidence are rejected. A receipt predating its current claim cannot be promoted merely because it is within TTL and matches the same resource/head/fence. The gate remains adapter-asserted until trusted provider provenance and executor fencing are independently established.

## In-flight claim/head consistency (PS-0131)

The preflight now snapshots and **re-reads** both the claim and repository head after retrieving the receipt. If the authoritative claim changes (including revocation, renewal, token or fence turnover), the repository head moves, or either re-read fails, admission is rejected. It also checks the wall clock again after provider reads so an initially valid lease cannot pass merely because the provider call ran past its deadline. An injected `now_epoch` is strictly a deterministic test input, not a live clock attestation.

A provider adapter must tolerate two fresh claim reads and two fresh head reads per preflight. Each read must independently contact its authority or use a provider-guaranteed linearizable snapshot; returning cached or caller-controlled dictionaries defeats this check. A mutable first response is copied before the second read.

**This is not atomic executor fencing.** A claim can still turn over immediately after the second read, and an ABA transition cannot be excluded by two observations alone. The executor must enforce the live fencing token at the actual side-effect boundary, with the provider's atomic compare-and-write or equivalent guarded operation. Never use the preflight return value as a permission to perform unfenced external writes.

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

## Transactional single-host SQLite effect canary (PS-0131)

`LeaseLedger.apply_fenced_sqlite_effect(lane_id, worker, fence, effect_id=..., payload_sha256=..., apply=...)` is a **narrow, executable side-effect boundary** for effects that are **entirely inside the ledger's own SQLite database**. It uses `BEGIN IMMEDIATE` to serialize claim validation, a trusted SQLite callback, and a persistent idempotency record in one transaction. It checks the live owner/fence/deadline before and after the callback, rejects stale claims, prevents conflicting reuse of an `effect_id` across lanes or payloads, and rolls back SQL changes if the callback raises or the lease expires before commit.

- **Caller responsibility:** `effect_id` must be a stable, producer-owned semantic idempotency key, and `payload_sha256` must identify the authorized effect payload. This module validates their shape and consistency, **not their independent authenticity**.
- **Trusted callback boundary:** `apply(connection)` must perform **only SQL on the supplied connection**. It must not call external APIs, write files, launch processes, open other connections, or commit/rollback the transaction itself. Such operations cannot be atomically rolled back by this primitive.
- **Proof ceiling:** `SQLITE_EFFECT_APPLIED` / `SQLITE_EFFECT_ALREADY_APPLIED` demonstrate **single-host, same-database transactional fencing only**. They do not prove provider-authenticated claims, cross-host exclusivity, filesystem fencing, external service compare-and-write, or agent execution. This primitive does not call or replace `receipt_gate.preflight` and must not be treated as a production executor permission.
- **Regression floor:** local concurrent replay (one SQL effect), claim expiry and turnover, duplicate-key conflict, callback rollback, and expiry-during-callback rollback are covered in `tests/test_parallel_dispatch_lease_ledger.py`. Hosted tests verify source behavior, not a physical provider's fencing.

**Ledger control-plane isolation:** While the trusted callback runs, the
SQLite authorizer rejects INSERT/UPDATE/DELETE and DROP/ALTER of the ledger's
`lanes`, `metadata`, and `fenced_effects` tables. It also rejects PRAGMA
and trigger DDL, which could otherwise bypass the intended control-plane
boundary. Ordinary application-table creation and SQL effects remain allowed.
The authorizer is cleared before the ledger writes its own receipt. These are
defenses against accidental or buggy trusted callbacks, **not** hostile-Python
sandboxing or external/cross-host fencing. Native regressions cover eleven
negative SQL cases, rollback, and a caught-denial success path.

**Transactional callback safety:** The trusted same-connection callback must not
manage transactions or attach databases. SQLite authorizer enforcement rejects
COMMIT, ROLLBACK, SAVEPOINT, ATTACH and DETACH (including implicit commits from
`executescript`) before they can escape the guarded transaction. Regressions
verify that attempted transaction escape rolls back both effect data and its
idempotency receipt, and that a caught denial leaves the transaction intact.
The callback remains trusted Python code with a privileged connection; it could
remove the authorizer deliberately. This guard does **not** sandbox hostile code,
authenticate providers, or fence external effects.

**Next:** build an independently authenticated claim/receipt/head adapter and prove a real provider's atomic compare-and-write at its own side-effect boundary, with collision and turnover-after-preflight tests. Keep this PR draft until those production gates and independent review are complete.
