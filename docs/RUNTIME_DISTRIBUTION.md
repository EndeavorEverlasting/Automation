# Runtime Distribution & Execution Handoff

Automation consumes the semantic runtime-placement decision from `planning.runtime_partition` and turns it into an execution-facing, fail-closed packet.

This repository does **not** own the planner that decides dependency graphs or work identity, and it does not replace an execution broker. Its job at this seam is smaller and more reusable:

1. receive an already-factored work unit;
2. require explicit runtime placement and mutation authority;
3. preserve exact inherited evidence;
4. reject privacy-leaking or incomplete tracked packets;
5. make the packet deterministic enough for ordinary local/provider/CI executors.

## Execution environments

The supported classes are:

- `CURRENT_CHAT_RUNTIME`
- `CONNECTED_PROVIDER`
- `LOCAL_AGENT_RUNTIME`
- `CI_OR_REMOTE_RUNNER`
- `OPERATOR_OR_PHYSICAL_RUNTIME`
- `UNKNOWN_RUNTIME`

`UNKNOWN_RUNTIME` is not executable. It is a resolution gate.

## Placement doctrine

Runtime placement happens upstream of this validator. The important invariant is that runtime placement must remain separate from ownership.

A planner may decide that one evidence-recovery step belongs in the current connected-provider runtime while implementation belongs in a local repository runtime. That does not change which component owns the underlying behavior.

Safe dependency-ready work that the current runtime/provider can actually complete should be completed before local handoff when doing so removes ambiguity or duplicated discovery. Local-only filesystem, shell, browser, or toolchain work remains local.

## Deterministic local-agent packet

A normal local executor should receive a READY packet containing at least:

- work-unit identity and semantic owner;
- execution environment and required capabilities;
- mutation authority;
- owned and forbidden scope;
- inherited evidence and freshness requirements;
- dependencies and collision surface;
- expected artifacts and acceptance gates;
- explicit proof ceiling;
- a runtime handoff instruction.

The machine-readable authority is:

`harness/contracts/runtime-execution-handoff.v1.json`

Validate a packet with:

```powershell
python scripts/validate_runtime_handoff.py --packet <packet.json> --require-ready
```

A sanitized example lives at:

`docs/examples/runtime-handoff.example.json`

## No frontier-model assumption

A runtime packet must not depend on the executor making high-quality architectural guesses.

If ownership, prompt identity, public/private boundary, or scope requires high-level judgment, resolve and persist that judgment before the packet becomes READY.

Cursor, OpenCode, CI jobs, provider runtimes, and other executors should be able to follow the same packet contract.

## Public/private rule

Tracked public packets must not include private continuity-store URLs or IDs, credentials, authenticated browser/session state, personal paths, or private provider state.

Use semantic identities, sanitized evidence, repository-relative paths, synthetic fixtures, and public provenance instead.

See `docs/PUBLIC_PRIVATE_BRIDGE.md`.

## Proof states

Keep these states distinct:

`DESIGNED → IMPLEMENTED → LOCALLY_VALIDATED → INTEGRATION_VALIDATED → COMMITTED → PUSHED → MERGED → DEPLOYED → PRODUCTION_VERIFIED`

A later state must never be inferred merely because an earlier one succeeded.
