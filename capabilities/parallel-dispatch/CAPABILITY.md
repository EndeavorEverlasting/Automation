# AUTO-PD1 — Bounded parallel dispatch

State: **PROTOTYPE — real local argv subprocess dispatch tested, provider agent capacity not certified**.

Owner: Automation. TokenCorridor owns the typed work/intake/judgment semantics. FirstMate owns native coding-agent crew admission and lifecycle; actual deployment must verify its host/runtime contract.

The executable adapter is `run.py` (standard-library Python). It can validate a typed batch of up to 1,000 independent/dependency-linked process lanes and launch up to 100 simultaneous local processes; the **actual** tested adoption floor is a synthetic **100-lane batch at a cap of eight concurrent Python processes**. This is not 100 authenticated LLM sessions.

- `python capabilities/parallel-dispatch/run.py --manifest <manifest> --receipt <receipt>` only validates; it NEVER launches.
- `python capabilities/parallel-dispatch/run.py --manifest <manifest> --receipt <receipt> --execute` launches the exact argv fields without a shell.
- Declared `exclusive_resources` serialize conflicting work and `depends_on` produces ordered successor gates. Validation rejects cycles, unknown/duplicate IDs, malformed fields, shells and unbounded timeouts.
- Observed process start/end monotonic timestamps prove the **maximum overlapping processes**, not merely `ThreadPoolExecutor` capacity or queue length.
- Receipts omit argv, stdout, stderr, environment values, credentials and private host paths.
- Only an explicitly authorized caller should supply the manifest and `--execute`. This prototype cannot attest repo/worktree isolation, group-kill descendants, provider quota, model sessions, deployment rights or cross-host leases. A declared resource name alone cannot enforce file-system permissions.
- Do not infer that 100 *ready* tasks equal 100 *claimed*, *running*, *authenticated*, *successful* or *merged* agents. The one-run local subprocess experiment is an adapter primitive, **not** persistent fleet scheduling.

## Scale admission, not launch theater

Start at `max_concurrent=4`, measure failure rate, runtime/memory/quota and write-set collisions, then graduate to 8/16/32/64/100 only after equivalent physical-host and provider evidence. An unsafe cap is a blocker, not a target to override. A queue may hold 100 items while only the admitted capacity runs. Nothing silently escalates provider spend.

Next: A verified FirstMate live-crew adapter must consume a checked, host-attested packet with authorized worktree and provider readiness, and report real session IDs, token/cost, lease and cancel/retry state. Automation must add durable claims/heartbeats and independent outcome verification before recurring unattended 100-lane dispatch. Test exact concurrency and conflicting write resources on DTop; do not claim physical certification from hosted CI.

See `docs/PARALLEL_DISPATCH.md` for the plan and semantic boundaries.


## PS-0131 authenticated receipt/claim preflight — nonproduction candidate

The provider-neutral `receipt_gate.py` implements a fail-closed preflight requiring
a current claim, immutable repository head, and independently retrieved receipt.
Read [RECEIPT_GATE.md](RECEIPT_GATE.md) before use: the adapter's provenance must
be authenticated outside this module, and external side effects still require
executor-side fencing. Synthetic test success **does not** establish a production
writer or a trusted provider claim.

## AUTO-PD1 persistent admission slice (source candidate)

The reusable lease_ledger.py adds **single-host SQLite persistence** on top of
the existing manifest validator, without creating a second scheduler or
requiring a particular consuming repository or agent provider.

A trusted execution adapter may call:
1. LeaseLedger(private_db_path).install(manifest) to bind an immutable
   validated manifest hash and register up to 1,000 queued work items.
2. claim(opaque_worker_id) to atomically reserve a dependency-ready item
   within the concurrency cap and exclusive-resource gate.
3. heartbeat(lane_id, worker, fence) during genuine native execution.
4. report(..., evidence_sha256=..., succeeded=True) to record only an
   UNVERIFIED worker assertion.
5. verify(lane_id, independent_verifier=trusted_verifier) to admit independent
   proof before unlocking successors.

The ledger stores no argv, stdout/stderr, environment variables or raw provider
evidence. Its SQLite database MUST remain private and untracked. Fencing tokens
reject late ledger reports from expired workers; they DO NOT kill external
workers or fence external side effects. Native adapters must enforce their own
idempotency/fencing. Expiry allows two claim attempts per item by default.
Worker failures block dependents; worker success reports never unblock them.

**Strict proof ceiling:** SQLite transactions and a 100-item synthetic fixture
do NOT demonstrate real model agent sessions, provider authentication, safe
cross-host distributed leases, completed changes, actual live parallelism, or
unattended recurrent scheduling. Use one local machine/database, not network
shared filesystems. Clock skew, host disappearance and independent verifier
qualification remain integration gates. Passing an arbitrary always-true
verifier callback is NOT evidence of accepted native work.

Focused check: python -m unittest discover -s tests -p test_parallel_dispatch_lease_ledger.py
