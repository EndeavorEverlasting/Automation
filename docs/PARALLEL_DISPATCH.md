# Parallel dispatch — portable execution seam

Issue: [AUTO-PD1 #14](https://github.com/EndeavorEverlasting/Automation/issues/14).

## Intake hierarchy

`TokenCorridor Work Graph / P04 runtime partition` → `Automation parallel-dispatch admission/receipt` → `AgentSwitchboard/FirstMate real agent runtime` → `independent tests / merge authority`.

This capability implements only a **local argv process executor** to unblock real bounded fan-out measurement. It does not replace FirstMate, AgentSwitchboard, or a cross-host scheduler.

## Dispatch target

- **100 scoped work items in queue** is a data/intake objective. These must be recovered from actual issues, PRs and accepted plans; synthetic benchmarks do not become backlog.
- **100 claimed/running workers** requires 100 real worker/session admissions with host/provider/quota/lease evidence; currently NOT PROVEN.
- The current prototype measures *100 actual subprocess launches* with a cap of eight real overlapping processes on a synthetic fixture. This is evidence of local concurrency mechanics only.
- The reproducible baseline is one task at a time. The synthetic compare run verifies `observed_peak_overlapping_processes > 1` and never above the cap; collisions enforce serialization.

## Manifest

A JSON object with exact `schema`, `max_concurrent` and `lanes`. Each lane has:

```json
{"id":"readme-check","argv":["python","-c","print('ready')"],"depends_on":[],"exclusive_resources":["repo-a-readme"],"timeout_seconds":30}
```

No shell strings, no arbitrary environment injections, and no implicit execution. Commands and their resources MUST be bound by an already-authorized host. A process that exits 0 is not proof of a meaningful LLM result.

## Required integration before production 100-lane crew

1. Host-attested execution packet; source/ref and frozen scope integrity; operator-approved spend limit.
2. Readiness/rate/quota probes and cost per execution class; bounded backpressure.
3. Durable atomic claims, leases, heartbeats, crash recovery and cancellation across hosts.
4. FirstMate/AgentSwitchboard native agent session spawn and unique worktree ownership.
5. Independent proof/readback, retries with budgets, duplicate prevention and convergence.
6. Physical workstation and cloud validation, not just CI; stop when contention, rate limits or errors worsen.

In existing repo ownership: TokenCorridor issue #142 covers the P04 dispatcher consumer; AgentSwitchboard/FirstMate provide native crew execution, and Automation #14 provides reusable queue/dispatcher mechanics. Do not merge an alternate scheduler into TokenCorridor or GNHF.
