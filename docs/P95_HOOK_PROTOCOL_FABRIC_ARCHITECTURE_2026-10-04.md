# P95 — Hook Protocol Fabric Architecture (2026-10-04)

Status: **ARCHITECTURE + PROTOCOL FABRIC INTEGRATED; LIVE HOST CANARY PENDING.**

## Problem

A hook system that can globally block ordinary work when a host changes schema is not a usable control plane.

The reliability target is not "parse the current Cursor JSON." It is:

> preserve consumer policy across host products, versions, execution surfaces, and compatibility dialects while making unknown host changes observable and recoverable rather than catastrophic.

## Design principle: policy survives protocol churn

Consumer logic operates only on canonical events and canonical decisions.

Canonical event examples:

- `session.start`
- `prompt.submit`
- `tool.pre`
- `tool.post`
- `compact.pre`
- `session.stop`

Canonical decision examples:

- `ALLOW`
- `BLOCK`
- `FOLLOW_UP`
- `CONTEXT`

Provider-specific event names, field names, response JSON, config nesting, and lifecycle quirks stay below that seam.

## Architecture

```text
                    ┌───────────────────────────────┐
                    │ protocol profile registry     │
                    │ shape_version + evidence      │
                    └──────────────┬────────────────┘
                                   │
host event bytes/callback          ▼
  -> transport adapter
  -> privacy-safe shape observation
  -> profile negotiator
       ├─ exact/specific shape
       ├─ compatible minimal shape
       ├─ version-hinted shape
       └─ UNKNOWN_SHAPE
  -> canonical event IR
  -> consumer policy
  -> canonical decision IR
  -> response-shape negotiator
       ├─ native encoder
       ├─ admitted compatibility encoder
       └─ NO_RESPONSE_SHAPE
  -> host response
  -> live acceptance / health evidence
```

## Why shape version and host version are separate

Application version is useful evidence but not a schema contract unless the provider says it is.

A host can:

- backport a hook change;
- gate a feature;
- expose different shapes on desktop/cloud/CLI;
- introduce compatibility layers;
- update documentation before/after a client rollout.

So the fabric records:

- `shape_version`: Automation-owned protocol revision;
- `host_version`: observed host version;
- `shape_sha256`: structural fingerprint;
- `profile_id`: selected profile.

That becomes an evidence-backed version/shape binding.

## Negotiation strategy

### 1. Narrow by host family

No accidental cross-host inference.

### 2. Match canonical event to admitted host event names

Event aliases are profile data, not consumer policy.

### 3. Validate required semantic fields

A candidate with missing/type-changed required fields is not admitted.

### 4. Prefer the most specific successful profile

This allows both:

- a broad/minimal compatibility profile;
- a newer richer profile.

If a new host version adds fields, the rich profile wins when its required envelope is present. If the richer envelope disappears but the semantic minimum remains, the minimal profile keeps the system functional.

### 5. Use host version as evidence, not sole authority

Exact observed version bindings increase confidence. Unbound versions do not automatically reject a shape whose structure is valid.

## Unknown shape behavior

The protocol fabric never decides business policy for unknown shapes.

It emits:

`UNKNOWN_SHAPE + DEFER_TO_CONSUMER`

The consumer classifies the boundary:

| Boundary | Default |
| --- | --- |
| observability/telemetry | fail open + capture shape |
| convenience/context injection | fail open + capture shape |
| availability-sensitive prompt admission | fail open unless explicit security requirement |
| destructive permission gate | fail closed |
| secrets/data-exfiltration gate | fail closed |

This avoids the previous failure class where a hook runtime defect becomes a total application outage.

## Hybridization

Hybridization is allowed only through canonical IR and explicit compatibility declarations.

Never merge two JSON schemas and hope.

```text
decoder profile A
  -> canonical event
  -> policy
  -> canonical decision
  -> encoder shape B
```

Requirements:

1. A and B belong to the same selected host profile or an explicitly admitted compatibility set.
2. Both map the same canonical event semantics.
3. The response encoder has a tracked proof level.
4. Live host acceptance remains separate.

Current proof target: Cursor Stop.

Cursor documents all three response styles:

- Cursor native `followup_message`;
- Claude flat `decision:block + reason`;
- Claude nested `hookSpecificOutput`.

The fabric keeps native first and exposes the compatible shapes as deterministic fallbacks. A caller can provide failed response-shape evidence and receive the next admitted route without changing consumer policy.

## Configuration switching

The same canonical bindings can render to different config dialects:

```text
canonical prompt.submit
  -> Cursor native:
       hooks.beforeSubmitPrompt[].command

canonical prompt.submit
  -> Claude/Codex group:
       hooks.UserPromptSubmit[].hooks[].command
```

Config shape, event input shape, and response shape are independent dimensions.

This is important because Cursor can load third-party hook definitions. A Cursor runtime may therefore use a Claude-style config projection while still negotiating Cursor event/response semantics.

## Surprise update handling

The system uses a compatibility ladder:

1. exact known profile + accepted response;
2. richer/minimal sibling profile for same host/event;
3. compatibility response encoder explicitly supported by host;
4. shadow-only unknown-shape observation;
5. consumer-defined degraded behavior;
6. profile admission after evidence/canary.

No step asks consumer policy to know provider JSON.

## Rollout state machine

```text
DISCOVERED
  -> PROFILED
  -> SYNTHETIC_PROVEN
  -> SHADOW_OBSERVED
  -> CANARY_ACCEPTED
  -> AUTO_SWITCH_ELIGIBLE
```

Automatic routing to a newly profiled shape should require at least `CANARY_ACCEPTED` for the target consumer. A profile may exist in the registry at a lower proof state without being production-selected.

## Health ledger (consumer integration contract)

The owner fabric accepts failed response-shape IDs as routing evidence. Consumers should persist host-local health evidence such as:

```json
{
  "host_family": "cursor",
  "host_version": "...",
  "shape_sha256": "...",
  "response_shapes": {
    "cursor.native.stop.v1": "FAIL",
    "claude.flat.stop.v1": "PASS"
  }
}
```

That ledger must be local/private unless sanitized; it may contain workstation-specific evidence.

The protocol owner does not need to know why a native response failed. It only needs the typed failure to select the next admitted fallback.

## Success call stack

```text
Cursor emits current common-envelope stop event
  -> common-envelope profile wins
  -> policy returns FOLLOW_UP
  -> cursor.native.stop.v1 healthy
  -> {"followup_message": "..."}
  -> live canary PASS
```

## Hybrid success call stack

```text
same input
  -> common-envelope profile wins
  -> policy returns FOLLOW_UP
  -> health ledger says cursor.native.stop.v1 FAIL
  -> select claude.flat.stop.v1
  -> {"decision":"block","reason":"..."}
  -> Cursor documented compatibility layer consumes it
  -> live canary determines PASS/FAIL
```

## Failure call stack

```text
Cursor update renames/removes the semantic prompt field
  -> no profile satisfies required prompt.submit fields
  -> UNKNOWN_SHAPE
  -> prompt-admission consumer configured availability-first
  -> allow ordinary prompt + persist privacy-safe fingerprint
  -> no global outage
  -> new profile admitted only after evidence
```

A destructive permission hook could make the opposite consumer choice and block.

## Current implementation

- `capabilities/agent-hook-runtime/core/protocol_fabric.py`
- `capabilities/agent-hook-runtime/profiles/current.v1.json`
- `tests/test_agent_hook_protocol_fabric.py`
- Cursor diagnostic probe now performs shadow negotiation.

## Proof ceiling

The implementation can prove deterministic negotiation and encoding. It cannot prove a host accepted a response shape without a live host canary.

## Integration closeout

The architecture is no longer design-only: Automation PR #19 integrated the owner at `9157215fc6b976ae1fa2f25d8498652ea5eaa478`, and TokenCorridor PR #118 integrated the pinned consumer at `6c9e92062b77b2068d1e7e903937f716995dc871`. Both repositories' required post-merge validation passed. The remaining proof ceiling is live-host behavior, not repository implementation.
