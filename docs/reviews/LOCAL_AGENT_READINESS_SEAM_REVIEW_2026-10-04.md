# Seam Review — Local Agent Readiness

**Date:** 2026-10-04  
**Semantic contract:** `local-agent-readiness-profile/v1` + `local-agent-readiness-receipt/v1`  
**Owner:** `EndeavorEverlasting/Automation/capabilities/local-agent-readiness`  
**Result:** PASS for reusable owner/interface admission; real-consumer adoption remains explicitly pending and no downstream implementation is declared obsolete yet.

## Owner

Automation owns the reusable classification:

`repository freshness -> selected agent projection parity -> live-host observation -> remote-write reachability -> actual-push readback`

Host-specific observation production belongs to adapters/consumers. Repository-specific projection paths belong to tracked consumer profiles.

## Normal consumer input

- repository root;
- tracked `local-agent-readiness-profile/v1`;
- agent ID;
- explicit `--refresh-remote` when freshness proof is required;
- optional normalized `local-agent-runtime-observation/v1`;
- optional dry-run write probe;
- optional explicit remote branch ref for actual-push readback.

## Normal consumer output

`local-agent-readiness-receipt/v1` with independent gate states, diagnosis, exact local/baseline SHAs, selected agent-profile digest, and proof ceiling.

## Consumer Knowledge Test

A normal consumer must know:

- its own remote and baseline branch;
- which tracked repository surfaces each local agent consumes;
- which proof gates the agent role requires;
- which live-runtime claims its host adapter can actually prove.

A normal consumer does **not** need to know:

- Automation internal module layout;
- TokenCorridor/P07 history;
- Cursor hook parser implementation;
- OpenCode implementation internals;
- a donor checkout;
- migration-era commit IDs;
- provider authentication internals;
- user-home configuration paths.

## Semantic identity

The dependency is `local-agent-readiness-profile/v1`, not a repository slug, Cursor path, TokenCorridor path, or provider endpoint.

Physical paths inside a profile are consumer-owned repository-relative domain input: they identify the consumer's own tracked projection surfaces rather than Automation internals.

## Discoverability

Root governance points at `docs/REPOSITORY_CHARTER.md`. The charter links the healthy agent-enabled repository recipe, which links the capability, contracts, invocation, and proof ceiling.

## Repeated downstream workaround evidence

The extraction was triggered by a real consumer implementing its own stale-projector/workstation-readiness classifier after a stale local agent projection reproduced a previously repaired defect.

That consumer-specific classifier is evidence of a reusable upstream operation, but it remains active until a safe consumer migration is performed.

## Distribution/interface artifact

- `capabilities/local-agent-readiness/schemas/profile.v1.json`
- `capabilities/local-agent-readiness/schemas/runtime-observation.v1.json`
- `capabilities/local-agent-readiness/schemas/readiness-receipt.v1.json`
- `capabilities/local-agent-readiness/verify.py`

Consumers do not import private core modules on the normal path.

## Provenance without topology leakage

Receipts expose exact local/baseline SHAs and the semantic agent-profile digest. They do not expose Automation's internal module composition or private host data.

## Isolated consumer canary

`tests/test_local_agent_readiness.py` creates a temporary Git consumer with:

- a shared agent contract;
- a Cursor-like repository projection;
- an OpenCode-like repository projection;
- a bare remote.

The canary proves stale baseline detection, agent-specific isolation, shared-surface invalidation, live observation binding, dry-run write separation, actual-push readback, unsafe-path rejection, and no working-tree repair mutation.

## Obsolete workaround removal

Not yet applicable to this owner-only extraction.

The first real consumer currently has active local-agent work. Replacing its classifier during that run would create the exact configuration/runtime collision this capability is designed to prevent.

The downstream implementation is therefore **not yet declared obsolete**. A later consumer-adoption lane must:

1. refresh consumer runtime truth;
2. add a tracked profile;
3. normalize existing live-host evidence;
4. prove parity with the generic capability;
5. switch the consumer entrypoint;
6. delete the duplicated classifier;
7. retain a regression that prevents a second classifier from returning.

## Proof ceiling

PASS here means the reusable owner/interface is clean and isolated-consumer portability is proven. It does not prove a real Cursor/OpenCode workstation, remote-write authority, actual push, or completed migration of the originating consumer.
