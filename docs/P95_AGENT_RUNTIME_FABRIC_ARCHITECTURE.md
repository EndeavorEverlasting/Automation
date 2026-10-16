# P95 — Agent Runtime Fabric Architecture

Status: `PROGRAM_DESIGN_ROUTING_PROTOTYPE_PROVEN`

## User outcome

Keep every useful runtime modality available without letting one unavailable, expensive, weak, or evolving surface block the workflow. Given an already-authorized work unit, select a currently probed modality that satisfies role, capability, hard-limit, quota, and resource constraints, and preserve why every rejected adapter failed admission.

## Existing owners recovered first

This design composes rather than duplicates:

- Automation `agent-hook-runtime`: hook transport/schema normalization;
- Automation `local-agent-readiness`: checkout/projection/live-host/readback proof;
- Automation `runtime-execution-handoff`: validation of upstream runtime placement;
- TokenCorridor execution-adapter v2: worker/parallel/token/wall-clock envelopes;
- TokenCorridor provider fallback/router: provider/surface fallback;
- TokenCorridor agent-execution tiering: execution authority is not judgment authority.

The generic admission seam belongs in Automation because it is independent of TokenCorridor semantics and any one provider.

## Vocabulary

- **Runtime adapter:** one concrete execution modality, not a product name.
- **Host hard limit:** ceiling imposed by the host around the adapter invocation. The Cursor incident's 10,000 ms `beforeSubmitPrompt` timeout is wall-clock, not token usage.
- **Workflow execution envelope:** task ceilings such as workers, parallel workers, model tokens, wall clock, or output bytes.
- **Provider/economic quota:** launches, requests, tokens per period, or spend allowance.
- **Machine capacity:** CPU, RAM, process slots, disk, or I/O. This can consume a host's wall-clock allowance but is not the host contract itself.
- **Authority/capability gate:** whether a runtime can and may do the work. This is admission state, not a budget.

## Candidate seams

| Candidate | Disposition | Why |
| --- | --- | --- |
| Whole-provider availability bit | Rejected | A capped cloud modality would incorrectly disable valid local/hook/tool modalities of the same product. |
| Consumer-specific fallback logic | Rejected | Repeats discovery and leaks provider internals into each consumer. |
| **Modality adapter fabric** | **Selected** | Provider evolution terminates behind adapters while consumers bind to stable profile/requirement contracts. |

## Module / ownership map

```text
upstream planning + authority owner
  -> runtime-execution-handoff/v1
  -> WorkRequirement(role, capabilities, expected usage)
  -> AdapterRegistry.route
       -> adapter.probe() -> RuntimeProfile
       -> assess(profile, requirement)
       -> SELECTED adapter | BLOCKED matrix
  -> native adapter execution (outside this capability)
  -> provider/live evidence
  -> local-agent-readiness / consumer acceptance
```

Ownership:

- upstream planner/judgment owner: semantic ownership, role assignment, required capabilities, placement;
- adapter: current host/provider facts and native mechanics;
- Agent Runtime Fabric: validation and admission only;
- provider/native runtime: actual task lifecycle;
- readiness/consumer validator: independent live proof.

No layer self-promotes its own proof ceiling.

## Prototype success path — capped cloud modality

```text
work requires EXECUTION_ONLY + repo_edit
  -> preferred cloud adapter probe
  -> cloud_agent_launches = KNOWN / remaining 0
  -> QUOTA_EXHAUSTED
  -> next adapter probe
  -> local adapter satisfies role/capability/limits
  -> SELECTED(local)
```

This is the intended pattern for an expensive cloud-agent surface: cap that modality without globally removing the agent class.

## Prototype failure path — judgment boundary

```text
work requires JUDGMENT_OWNER
  -> execution-only adapter READY
  -> ROLE_NOT_ADMITTED:JUDGMENT_OWNER
  -> evaluate remaining adapters
  -> none admitted
  -> BLOCKED + evaluation matrix
```

A weaker agent stays useful for execution-only work; availability never upgrades its authority.

## Cursor host-budget path

```text
before-submit adapter
  -> host hard wall_clock_ms = 10000
  -> reserve = 1000
  -> effective admission ceiling = 9000
  -> expected hook work compared with 9000
```

Imports, subprocess startup, filesystem latency, OneDrive latency, CPU pressure, and contention consume wall-clock time. Model tokens are a different axis.

If Cursor changes its hook event shape, the change belongs in the Cursor adapter owned by `agent-hook-runtime`. If Cursor adds a new hook modality or limit, the runtime profile changes. Consumers should not need to rewrite their workflow.

## P04 convergence

Lane A: Automation owner capability, contracts, tests, docs, CI.

Lane B: after Lane A merges, TokenCorridor consumes/pins the owner contract, maps its existing execution-adapter/fallback/tiering mechanisms, proves isolated parity, then retires only the duplicated generic machinery that is safely superseded.

## Seam review

- true owner: Automation `agent-runtime-fabric`;
- semantic contracts: `agent-runtime-profile/v1`, `agent-runtime-work-requirement/v1`, `agent-runtime-route-decision/v1`;
- normal consumer knowledge: required role/capabilities/expected usage/optional preference;
- provider auth, hook schema, cloud task id, process command, and migration history stay adapter-private;
- isolated consumer canary: synthetic tests use only the public `probe()` seam; no TokenCorridor import;
- consumer cleanup is deferred until owner merge + consumer parity proof.

## Proof ceiling

Synthetic tests prove validation, reserve-aware hard limits, quota fallback, machine-capacity fallback, role gating, unknown-quota fail-closed behavior, and blocked evaluation matrices. They do not prove current Cursor limits, a named provider's cloud-agent quota, native dispatch, live-host behavior, or production resource accounting.
