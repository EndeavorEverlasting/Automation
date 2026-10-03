# Idea → Work Continuity — Prompt Scratch / Automation / TokenCorridor

**Plan ID:** `IDEA-WORK-CONTINUITY-2026-10-03`  
**Owner of reusable mechanism:** `EndeavorEverlasting/Automation`  
**Consumer program authority:** existing consumer planning owner; for Prompt Scratch/TokenCorridor that remains `plans/active/PROMPT-SCRATCH-UBIQUITOUS-SPRINT-MAP.md`  
**State:** IMPLEMENTED CONTRACT / TOKENCORRIDOR ADOPTION DEFERRED  
**Proof ceiling:** Automation contract/validator + repository evidence only. No live private-sheet adapter or TokenCorridor consumer mutation is claimed.

## Problem

The operator's fastest idea surface is intentionally low friction. Ideas may arrive in a spreadsheet, chat, screenshot, note, or provider event before architecture, ownership, or implementation is known.

The recurring defect is not capture. It is **continuity after capture**:

- an agent understands an idea but leaves it only in chat;
- a contract gap is identified but never becomes the next bounded sprint;
- a canonical plan already exists, but a later agent creates another plan instead of an iteration;
- a target repository is mid-migration, so useful insight is either forced into the moving target or forgotten entirely;
- chronology is mistaken for operator priority;
- lower-capability local agents are asked to reconstruct judgment already made elsewhere.

## Selected architecture

Automation owns one reusable continuity primitive:

`captured/discovered insight -> recover existing owner -> durable disposition -> next transition`

It does **not** own the raw private intake, the consumer's business rules, or the consumer's canonical planning authority.

The machine contract is `harness/contracts/idea-work-continuity.v1.json`.

## Required fixed point

Before an agent terminates work on an execution-relevant idea, one of these must be remotely durable:

1. **Existing plan binding** — the idea is already represented by a canonical plan.
2. **Bounded iteration** — the existing plan receives the new iteration when mutation is safe and owned.
3. **New remote plan** — only when no canonical plan exists and ownership/collision state is sufficiently known.
4. **Deferred adoption** — the idea is preserved remotely, but the target consumer is not mutated because migration/convergence/collision state is unresolved.
5. **Owner-resolution blocker** — ownership is unresolved, so the remote continuity artifact preserves the exact next owner-resolution transition.

`CHAT_ONLY` is not a completion state.

## Prompt Scratch role

Prompt Scratch remains a human-friendly/private intake and visual projection surface. It may provide raw wording, capture provenance, operator-entered priority, and readable state.

This plan does not move raw Prompt Scratch contents into public Git and does not make Automation a second Prompt Scratch database.

A future provider adapter may emit `idea-work-continuity-receipt/v1` from private intake events. That adapter must preserve exact provider identity privately and project only sanitized continuity state publicly.

## TokenCorridor adoption

TokenCorridor already owns a canonical Prompt Scratch program plan. Creating a second plan would violate existing authority and the continuity contract.

Provider truth refreshed for this plan shows TokenCorridor still has active migration/convergence work and open convergence-era PRs. Therefore this Automation lane **does not mutate TokenCorridor**.

Current public-safe adoption receipt:

`docs/examples/idea-work-continuity.tokencorridor-deferred.v1.json`

Disposition:

`DEFERRED_ADOPTION`

When the TokenCorridor convergence owner next refreshes the destination:

1. refresh current default branch and active migration/convergence plans;
2. recover the existing Prompt Scratch canonical plan;
3. prove the adoption change is collision-clear;
4. add one bounded iteration that consumes `idea-work-continuity/v1`;
5. do not create another Prompt Scratch program plan;
6. keep the future Prompt Scratch/Idea Reservoir UI maturity-gated by the existing consumer plan.

This makes the insight remote now without adding a new migration lane now.

## Agent activation rule

Repository agents entering Automation must apply idea-work continuity when they:

- discover a reusable contract gap;
- receive an execution-relevant idea that is not yet represented remotely;
- finish a conversation that created a required successor transition;
- identify a consumer adoption that should happen later;
- encounter an existing plan whose next iteration is otherwise likely to remain chat-only.

The agent must recover existing authority first. It must not use this contract to manufacture work from every note.

## Relationship to other Automation contracts

- `prompt-invocation-upstream/v1` owns P-number identity/intent; idea-work continuity does not create prompts.
- `planning.runtime_partition` decides runtime placement upstream; idea-work continuity does not become a second planner.
- `automation-runtime-execution-handoff/v1` packages READY executor work; idea-work continuity may point to such a packet after the durable planning transition exists.
- `artifact-continuity-preflight/v1` / `artifact-sync` own provider-backed file continuity; idea-work continuity owns the work-obligation bridge, not file transfer.
- `seam-boundary-review/v1` remains required when the eventual adoption creates a reusable seam.

## Acceptance gates

- deterministic contract and validator exist;
- execution-relevant `CHAT_ONLY` receipts fail;
- existing-plan + `CREATE_REMOTE_PLAN` fails;
- migration-active + non-clear collision + direct mutation disposition fails;
- unspecified operator priority cannot carry an inferred value;
- the TokenCorridor adoption example validates as `DEFERRED_ADOPTION`;
- Automation root agent guidance points to this contract;
- repository CI passes on the exact candidate.

## Next implementation boundary

The next capability slice is a **private-source adapter**, not another planning contract:

`Prompt Scratch event/read -> sanitized continuity observation -> idea-work-continuity receipt -> existing plan/iteration/deferred-adoption mutation through the owning provider/runtime`

That slice requires explicit provider-access proof and must reuse artifact-sync for provider-backed write/readback rather than inventing another synchronization mechanism.
