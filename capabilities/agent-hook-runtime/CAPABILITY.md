# Agent Hook Runtime

## Purpose

`agent-hook-runtime` is the reusable boundary between **host hook protocols** and **consumer policy**.

It no longer treats a product name such as Cursor as one immutable hook schema. A host may expose multiple configuration dialects, event names, input envelopes, response formats, execution modes, and compatibility layers at the same time. Those shapes can also change independently across application versions.

The capability therefore separates:

1. transport (`json_stdio`, callback/plugin APIs, future transports);
2. configuration shape;
3. host event name;
4. canonical event semantics;
5. input wire shape;
6. response wire shape;
7. host/application version evidence;
8. consumer policy.

The canonical policy layer must not need to know whether a prompt-arrival event was called `beforeSubmitPrompt`, `UserPromptSubmit`, or something introduced later.

## Versioned protocol fabric

Portable owner:

- `core/protocol_fabric.py`
- `profiles/current.v1.json`

A protocol profile has its own stable `shape_version` and may accumulate **evidence-backed host-version bindings**. Host version is a useful routing hint, but it is not trusted as the only source of truth: a host can ship a schema change before this repository learns its release mapping.

Every live/synthetic event can therefore produce a privacy-safe structural fingerprint:

- sorted top-level key/type pairs;
- SHA-256 of that structural signature;
- host family;
- host event;
- host version when observed;
- no prompt text, attachment paths, IDs, or other payload values.

Negotiation scores only tracked profiles for the named host family. A more specific matching shape wins. Additive unknown fields are tolerated. Missing or type-changed required semantic fields produce `UNKNOWN_SHAPE` rather than guessed behavior.

## Canonical IR and hybridization

Hybridization is **not schema union**.

The safe call stack is:

```text
host payload
  -> admitted decoder/profile
  -> canonical event (prompt.submit / session.stop / ...)
  -> consumer policy
  -> canonical decision (ALLOW / BLOCK / FOLLOW_UP / CONTEXT)
  -> admitted response encoder
  -> host response
```

A decoder from one host shape may pair with a different response format **only when the selected profile explicitly declares that response shape compatible**.

This matters today. Cursor documents native hook responses and explicit Claude Code compatibility, including alternative Stop/SubagentStop response formats. The fabric can therefore keep a native Cursor decoder while falling back from `cursor.native.stop.v1` to an admitted Claude-compatible stop encoder if live evidence shows the native response path regressed.

The fabric never hybridizes across unrelated host families merely because two JSON objects look similar.

## Configuration dialects

The same canonical event bindings can currently render to:

- `cursor-native-config-v1`
- `claude-codex-group-config-v1`

This lets a consumer choose the configuration dialect independently from the canonical policy. Cursor's documented third-party hook compatibility means a Cursor deployment can legitimately consume a Claude-style configuration projection while still running Cursor.

Additional harnesses such as OpenCode use materially different plugin/callback APIs and should receive their own adapter/profile rather than being forced through JSON-stdio assumptions.

## Cursor boundary

Cursor is represented by multiple tracked profiles rather than one frozen adapter contract:

- `cursor-native-minimal-v1` preserves the smaller historical/event-specific shapes;
- `cursor-native-common-envelope-v2` represents the current documented common envelope plus event-specific fields;
- the current Cursor profile explicitly admits documented Claude-compatible stop response shapes.

The existing `adapters/cursor.py` remains a tolerant compatibility validator for the diagnostic entrypoint. It intentionally accepts unknown fields so additive host updates do not become outages. The protocol fabric runs in shadow in `diagnose_cursor_hook.py` and records the negotiated profile in privacy-safe receipts.

Current Cursor documentation now describes common fields such as `conversation_id`, `generation_id`, `hook_event_name`, `cursor_version`, and `workspace_roots` in addition to event-specific fields. Historical versions and execution surfaces have not always exposed the same envelope, which is exactly why consumer policy must not directly bind to one snapshot.

## Diagnostic probe

Run:

`capabilities/agent-hook-runtime/diagnose_cursor_hook.py`

Set `AUTOMATION_HOOK_RECEIPT_DIR` to a local, untracked directory when a durable receipt is useful.

The probe now records three independent layers:

1. byte transport parse;
2. compatibility event validation;
3. versioned protocol-shape negotiation.

In `failure-policy=allow` mode, malformed or unknown transport is observed rather than turned into a global availability outage. In `failure-policy=block` mode, the consumer deliberately chooses a stricter security boundary.

Receipt persistence itself remains observational and must never become a hook availability dependency.

## Unknown-shape rule

An unknown shape is evidence, not permission to invent a schema.

The protocol fabric returns `UNKNOWN_SHAPE` and `DEFER_TO_CONSUMER`.

A consumer may:

- fail open for observational, convenience, or availability-sensitive hooks;
- fail closed for explicitly security-critical permission boundaries;
- run one or more candidate decoders in shadow;
- persist a privacy-safe shape observation;
- admit a new profile only after tests/canary/live acceptance.

This prevents a surprise host update from globally bricking ordinary use while preserving fail-closed behavior where the consumer has explicitly classified the boundary as security-critical.

## Ownership boundary

Automation owns:

- transport parsing;
- protocol profiles and structural fingerprints;
- host-version/shape binding records;
- event-name and configuration-dialect mapping;
- response encoding;
- compatibility/hybrid route negotiation;
- privacy-safe receipts.

Consumers own:

- business/repository policy;
- authorization;
- whether an unknown/failing boundary is security-critical;
- live acceptance thresholds;
- rollout from shadow -> canary -> automatic switching.

Prompt definitions, P-number discovery, and Prompt Kit registry composition remain upstream-owned. This capability must not become another prompt resolver.

## Rollout discipline

Protocol changes advance through:

`DISCOVERED -> PROFILED -> SYNTHETIC_PROVEN -> SHADOW_OBSERVED -> CANARY_ACCEPTED -> AUTO_SWITCH_ELIGIBLE`

A documentation scrape or unit test can create a profile but cannot certify a real installed host. Auto-switch is permitted only when the consumer's live canary/acceptance contract has admitted that profile or response fallback.

## Proof ceiling

The current implementation proves deterministic profile validation, structural fingerprinting, version-hint routing, native/compat response selection, config projection, and synthetic hybridization. Cursor diagnostics now shadow-negotiate live shapes.

It does **not** prove that any installed Cursor, Codex, Claude Code, OpenCode, or future host accepted a selected response. That requires host-specific live observation/canary evidence.
