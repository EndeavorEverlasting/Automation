# P97 — Hook Protocol Prior Art and Volatility Map (2026-10-04)

Status: EVIDENCE RECOVERED; feeds P95 architecture and P04 factoring.

## Question

What is the durable abstraction if agent-hook systems can change shape across products, versions, execution surfaces, and compatibility layers?

## Finding

The durable unit is **not a product hook schema**.

It is a versioned protocol profile over independent dimensions:

```text
host family
+ host/application version evidence
+ execution surface
+ transport
+ config dialect
+ host event name
+ input shape
+ canonical semantic event
+ response dialect
+ compatibility declarations
+ live acceptance state
```

A product can legitimately occupy several points in that space simultaneously.

## Cursor evidence

Current Cursor documentation establishes all of the following:

1. Native command hooks communicate JSON over stdio.
2. Project/user/team/enterprise hook sources can coexist.
3. Desktop, cloud agents, self-hosted machines, and app-lifecycle hooks do not expose identical hook availability.
4. `beforeSubmitPrompt` is the native prompt-admission event and returns `continue`.
5. `stop` can emit `followup_message`.
6. Current common hook input includes fields such as `hook_event_name`, `cursor_version`, and `workspace_roots`, with conversation/generation/model metadata for applicable events.
7. Cursor publishes explicit third-party compatibility:
   - Claude `UserPromptSubmit` -> Cursor `beforeSubmitPrompt`
   - Claude `Stop` -> Cursor `stop`
   - native and Claude-compatible Stop response shapes are accepted.
8. Cursor exposes `CURSOR_VERSION` to hook processes.
9. Cursor config currently declares schema `version: 1`, which is a config schema version, not enough by itself to identify every event/input/output shape.

Sources:
- https://prod.cursor.com/docs/hooks
- https://prod.cursor.com/docs/reference/third-party-hooks

### Important correction to the old Automation snapshot

The earlier Automation Cursor adapter documentation said `conversation_id` / `generation_id` were undocumented for prompt/stop events. Current Cursor documentation now includes these fields in the common input envelope for applicable hooks.

That does not mean the old implementation was irrational; it proves the point of this sprint: **documentation and wire shape evolve.** Consumer policy must not freeze one documentation snapshot into its core semantics.

## Codex evidence

Current Codex/ChatGPT hook documentation exposes lifecycle hooks including:

- `UserPromptSubmit`
- `PreToolUse`
- `PermissionRequest`
- `PostToolUse`
- `SessionStart`
- `Stop`

For `UserPromptSubmit`, Codex documents:

- a `prompt` field;
- Codex-specific `turn_id`;
- common output fields such as `continue`;
- a block shape using `decision: "block"` + `reason`;
- hook-specific additional context.

OpenAI plugin packaging also supports hook bundles and explicitly carries Claude compatibility environment aliases.

Sources:
- https://learn.chatgpt.com/docs/hooks
- https://developers.openai.com/plugins/build/plugins

## OpenCode evidence

OpenCode V2 exposes hook registration as an in-process plugin/callback API rather than requiring JSON-stdio command hooks for the session surfaces.

Its documentation also labels WebSocket hook surfaces experimental and warns that names/shapes can change.

Source:
- https://opencode.ai/v2/docs/build/plugins

This proves that `transport=json_stdio` itself must be an adapter dimension, not a universal assumption.

## P97 conclusions

### Rejected abstraction: one adapter per product

```text
CursorAdapter
ClaudeAdapter
CodexAdapter
OpenCodeAdapter
```

is insufficient if each class still hard-codes one shape. It merely moves brittleness into four files.

### Selected abstraction: profile registry + canonical IR

```text
host/native payload
   -> transport adapter
   -> profile negotiation / version+shape evidence
   -> canonical event IR
   -> consumer policy
   -> canonical decision IR
   -> negotiated response encoder
   -> host
```

### Version semantics

Track two versions separately:

1. **shape_version** — the schema/protocol profile version owned by Automation.
2. **host_version** — observed application/runtime version reported by the host.

A binding between them is evidence produced by an observation/canary. Do not invent release ranges from documentation dates.

### Unknown-update semantics

A surprise host update must not automatically become a global outage.

- additive fields: tolerate and fingerprint;
- known semantic subset still present: select the compatible lower/minimal profile;
- required semantic field removed/renamed/type-changed: `UNKNOWN_SHAPE`;
- unknown shape: consumer decides fail-open vs fail-closed from boundary classification;
- never infer a sensitive field mapping from payload values.

### Hybridization semantics

Hybridization is decode -> canonical IR -> encode, not schema union.

Example already supported by the ecosystem:

```text
Cursor current Stop input
  -> cursor-native decoder
  -> canonical FOLLOW_UP
  -> Claude flat Stop encoder
  -> Cursor compatibility layer
```

This is valid because Cursor explicitly documents the response compatibility.

## Proof ceiling

Public documentation proves supported/documented protocol surfaces, not what one installed workstation currently emits or accepts. Those bindings require live receipts/canaries.
