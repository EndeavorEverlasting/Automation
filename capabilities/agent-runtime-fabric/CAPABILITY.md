# Agent Runtime Fabric

## Purpose

`agent-runtime-fabric` is the reusable admission seam between an already-authorized work unit and the concrete runtime modality that may execute it.

It exists because a provider name is not a capability. The same provider or product may expose several materially different execution surfaces — synchronous hooks, local CLI/process execution, cloud agents, connected tools, CI jobs, or future mechanisms — with different limits, quotas, authority, and proof requirements.

The fabric therefore routes over **runtime adapters**, not over product names.

## Composition boundary

The normal call stack is:

```text
upstream planning.runtime_partition / authority decision
  -> automation-runtime-execution-handoff/v1
  -> agent-runtime-fabric admission
  -> selected provider/harness adapter
  -> native runtime execution (outside this capability)
  -> provider/live-host evidence
  -> local-agent-readiness / consumer acceptance
```

This capability does **not** become a planner, semantic broker, prompt resolver, execution authority, or native runtime.

It composes with existing Automation owners:

- `agent-hook-runtime` owns hook transport normalization and provider event-shape adapters;
- `local-agent-readiness` owns workstation/readiness proof classes;
- `runtime-execution-handoff` consumes the upstream runtime-placement decision;
- this capability owns adapter admission across declared role/capability/resource/quota constraints.

## Budget vocabulary

A single word such as "budget" is too ambiguous for a portable harness. Keep these dimensions separate:

1. **Host hard limits** — externally enforced ceilings such as a synchronous hook timeout. A 10,000 ms hook timeout is a wall-clock limit, not a token limit.
2. **Workflow execution envelope** — admitted workers, parallel workers, model tokens, wall clock, output bytes, or other task-level ceilings.
3. **Provider/economic quota** — cloud-agent launches, requests/day, tokens/day, monetary allowance, or similar provider-account limits.
4. **Machine capacity** — CPU/RAM/process/disk/I/O capacity. These affect feasibility and elapsed time but are not automatically the host's contract.
5. **Capability/authority gates** — whether a runtime can perform the operation and is allowed to do so. These are admission facts, not budgets.

Hardware, process startup, filesystem latency, imports, and contention can consume a host's wall-clock allowance. They influence whether an implementation fits the limit; they do not redefine that limit as "hardware budget."

## Adapter profile

Each adapter exposes `agent-runtime-profile/v1` through a read-only `probe()`.

A profile declares:

- stable `adapter_id` for one execution modality;
- `harness_family`;
- current `state` (`READY`, `BLOCKED`, `UNKNOWN`);
- supported capabilities;
- **admitted roles** inherited from upstream authority policy;
- numeric hard limits and safety reserve;
- provider quotas with `KNOWN`, `UNLIMITED`, or `UNKNOWN` state;
- per-dispatch quota costs;
- proof ceiling.

The fabric never infers model intelligence or grants a role. A weaker or execution-only runtime can stay in the pool and remain useful for work that requires only its admitted role. A lane requiring a judgment role will fail closed unless some probed adapter is explicitly admitted for that role by upstream policy.

## Fail-closed rules

Admission is denied when any of these is true:

- adapter state is not `READY`;
- required role is not admitted;
- a required capability is missing;
- expected use exceeds `hard_limit - reserve`;
- a required per-dispatch quota is absent, unknown, or exhausted.

The first admitted adapter in deterministic preference order is selected. If none qualify, the fabric returns a `BLOCKED` route decision with the per-adapter reasons. It does not ask the operator to rediscover why each provider failed.

## Why modality-level adapters

Do not model "Cursor", "Grok", "OpenCode", or any other product as a single boolean availability bit. A cloud-agent surface can be quota-capped while a local or connected surface remains valid. A hook interface can change while repository execution remains available through another adapter. New provider shapes should be added or changed behind adapters without rewriting consumer workflows.

## P04 / P95 origin

This capability is the reusable owner extracted from a P04 + P95 convergence pass. TokenCorridor already had execution-adapter envelopes, provider fallback, and agent tiering; Automation already owned host transport and local readiness. The missing seam was one portable admission surface that kept host limits, task envelopes, provider quotas, hardware constraints, and authority/capability facts distinct.

## Proof ceiling

The current implementation proves deterministic profile validation and synthetic admission/fallback behavior. It does **not** prove any real provider quota, current host limit, native dispatch, live hook behavior, or production resource accounting. Those require adapter-specific probes and downstream live evidence.
