# P04 — Hook Protocol Fabric Factoring Plan (2026-10-04)

Status: OWNER IMPLEMENTATION IN PROGRESS.

## Execution frame

- reusable owner: `EndeavorEverlasting/Automation`
- capability: `capabilities/agent-hook-runtime`
- consumer incident: `EndeavorEverlasting/TokenCorridor` Cursor continuity
- Automation floor: `main@5d0f363f1e98d0e4227b7abc7caf4162661ca1a6`
- current owner branch: `feat/p04-p95-p97-hook-protocol-fabric-20261004`
- overlapping open PR: #18 owns `agent-runtime-fabric`, shared README/AGENTS/validate workflow
- collision rule: this lane does not modify #18's owned capability or shared root/CI files

## Mission

Make hook protocol evolution a replaceable adapter/profile concern so consumers keep functioning when hosts introduce new versions, compatibility dialects, or execution surfaces.

## Factoring decision

### Automation owns

- hook transport normalization;
- versioned protocol profiles;
- privacy-safe shape fingerprints;
- host-version/shape bindings;
- config-dialect rendering;
- canonical event/decision IR;
- response encoders;
- compatibility/hybrid route selection.

### TokenCorridor owns

- P07 semantics;
- which boundaries are availability-first vs security-critical;
- workstation projection/convergence;
- live CTX/LO acceptance;
- its pinned/vendor projection of the Automation owner.

### Host adapters own

- provider-native callback/process mechanics;
- live version/surface probing;
- host-specific config locations;
- host acceptance/readback.

## Dependency graph

```text
HP-0 P97 evidence recovery
  └── HP-1 P95 protocol architecture
       ├── HP-2 protocol core + profiles + tests
       └── HP-3 shadow diagnostic integration
              └── HP-4 Automation exact-head CI/integration
                   └── HP-5 TokenCorridor consumer pin/adoption
                        └── HP-6 live Cursor canary / auto-switch admission
```

Graph width during owner mutation is effectively 1 because HP-2 and HP-3 share the same capability contract and must converge before CI. Research and docs were parallel-safe conceptually, but this runtime exposes no independent autonomous sub-agent executor; no parallel-execution claim is made.

## Lanes

| Lane | Owner | Scope | Forbidden | Gate |
| --- | --- | --- | --- | --- |
| HP-0 | Automation/P97 | Cursor/Codex/OpenCode prior art | provider speculation | sources + gap map |
| HP-1 | Automation/P95 | protocol IR, negotiation, hybridization, rollout | P07 semantics | success/failure call stacks |
| HP-2 | Automation | `agent-hook-runtime/core/**`, profiles, focused tests | TokenCorridor policy | full test discovery |
| HP-3 | Automation | diagnostic shadow negotiation | automatic production switch | existing diagnostics remain fail-open capable |
| HP-4 | Automation | PR + CI + integration readback | consumer mutation before owner floor | exact-head + main CI |
| HP-5 | TokenCorridor | pin/vendor owner + route P07 hook projector through fabric | duplicate generic owner | parity + P07 CI |
| HP-6 | TokenCorridor/local host | live version/shape binding + native/compat canaries | synthetic proof promotion | live receipt |

## Acceptance gates

Owner floor:

1. legacy/minimal Cursor payload remains routable;
2. current common-envelope Cursor payload selects the more specific profile;
3. additive future fields do not break routing;
4. a breaking semantic field change returns `UNKNOWN_SHAPE` instead of guessed policy;
5. Cursor Stop can hybridize to documented Claude-compatible response shapes;
6. Codex `UserPromptSubmit` uses its own host profile;
7. config projection can switch between Cursor-native and Claude/Codex group dialects;
8. host families cannot cross-match accidentally;
9. observations persist key/type structure but never payload values;
10. existing Automation unit/contract suite remains green.

Consumer floor:

1. TokenCorridor pins an integrated Automation owner SHA/blob;
2. P07 policy consumes canonical event/decision semantics rather than direct host JSON where practical;
3. ordinary prompt admission stays availability-safe on unknown protocol shape;
4. terminal/security-critical boundaries preserve explicit fail-closed classification;
5. live Cursor receipt binds actual `CURSOR_VERSION` + shape fingerprint to selected profile;
6. native response path and at least one documented compatibility fallback are canary-tested before automatic switching.

## Convergence rule

Do not delete TokenCorridor's current stable firewall merely because the owner fabric exists.

Adoption order:

`owner merge -> consumer vendor/pin -> shadow parity -> canary -> route activation -> old duplicate retirement`

## Proof ceiling

P04 factoring can prove ownership, dependencies, collision control, and repository acceptance. It cannot prove a specific installed host version/shape without HP-6 live evidence.
