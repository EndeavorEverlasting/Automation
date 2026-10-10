# AUTO-PD1 — Bounded parallel dispatch

State: **PROTOTYPE — real local argv subprocess dispatch tested, provider agent capacity not certified**.

Owner: Automation. TokenCorridor owns the typed work/intake/judgment semantics. AgentSwitchboard/FirstMate own native coding-agent admission and crew lifecycle.

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

Next: FirstMate live-crew/AgentSwitchboard local adapter must consume a checked, host-attested packet with authorized worktree and provider readiness, and report real session IDs, token/cost, lease and cancel/retry state. Automation must add durable claims/heartbeats and independent outcome verification before recurring unattended 100-lane dispatch. Test exact concurrency and conflicting write resources on DTop; do not claim physical certification from hosted CI.

See `docs/PARALLEL_DISPATCH.md` for the plan and semantic boundaries.
