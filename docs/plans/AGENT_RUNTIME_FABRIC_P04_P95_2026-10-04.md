# Agent Runtime Fabric — P04 + P95 Convergence Plan

Status: OWNER LANE IMPLEMENTED; CONSUMER MIGRATION WAITS ON MERGED OWNER FLOOR

## Floors

- Automation planning floor: `main@5d0f363f1e98d0e4227b7abc7caf4162661ca1a6`
- TokenCorridor evidence floor: `main@4e1c6199b007f619fb15965e2be0171d8599cb97`

## Mission

Make runtime/harness evolution a replaceable adapter concern instead of a workflow blocker. Preserve weak/execution-only agents as useful bounded executors while keeping expensive cloud modalities quota-capped and keeping judgment authority explicit.

## P04 factoring ledger

| Lane | Owner | Mission | Dependency | Mutable scope | Forbidden scope | Proof gate |
| --- | --- | --- | --- | --- | --- | --- |
| A — portable owner | Automation | Build provider/harness-neutral profile + admission fabric | none | `capabilities/agent-runtime-fabric/**`, focused docs/tests/CI/wayfinding | prompt semantics; provider credentials; native execution; TokenCorridor policy | synthetic success + failure call stacks; repository CI |
| B — consumer convergence | TokenCorridor | Consume/pin owner contract; map existing execution adapters/fallback/tiering; retire duplicated generic behavior only after parity | Lane A merged | bounded consumer integration surfaces selected after fresh-floor collision check | rewrite P04/P95 prompts; weaken agent tiering; delete existing adapters before parity | isolated consumer parity + TokenCorridor CI + live proof where applicable |

Graph width is 2, but Lane B has an explicit owner-floor dependency for mutation. Its analysis can proceed independently; its integration cannot safely precede Lane A merge.

## Runtime placement

Current execution environment: `CURRENT_CHAT_RUNTIME` with GitHub repository connector for provider mutations. No independent sub-agent/local executor is exposed in this chat, so actual multi-lane dispatch cannot be proven here. Serial owner-first progress is allowed to avoid deadlock; `observed_parallelism=false`.

## Acceptance

Lane A closes when:

1. stable profile/requirement contracts exist;
2. host hard limits, workflow envelopes, provider quotas, machine capacity, and role/capability gates are distinct;
3. cloud-quota exhaustion can fall back to another modality;
4. execution-only profiles cannot satisfy a judgment-required lane;
5. unknown quota fails closed;
6. docs explicitly compose existing Automation owners instead of duplicating them;
7. CI passes on the PR head.

Lane B begins only after refreshed provider truth proves the Automation owner floor is merged.

## Proof ceiling

P04 factoring and P95 prototype can prove architecture, synthetic admission semantics, and repository integration. They cannot establish current live provider quotas or host limits without adapter-specific runtime observations.
