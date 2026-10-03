# Agent Hook Runtime

## Purpose

agent-hook-runtime is the reusable transport seam for agent-host hooks. It separates host transport correctness from consumer policy so malformed provider input is not misdiagnosed as a prompt-registry or P-number defect.

The core owns provider-neutral JSON-over-stdio parsing. Provider event shapes live behind adapters; the first adapter is Cursor.

## Cursor boundary

The Cursor adapter follows the documented event boundary current on 2026-10-03:

- beforeSubmitPrompt: prompt plus optional attachments; output continue plus optional user_message.
- stop: status plus loop_count; output optional followup_message.
- sessionStart: session_id, is_background_agent, optional composer_mode; output may set session-scoped env.

Conversation identity belongs to sessionStart. Consumers must not require undocumented conversation_id or generation_id fields from beforeSubmitPrompt or stop. The sessionStart diagnostic response exports AUTOMATION_CURSOR_SESSION_ID for later hooks in the same session.

## Diagnostic probe

Run capabilities/agent-hook-runtime/diagnose_cursor_hook.py as a temporary hook adapter. Set AUTOMATION_HOOK_RECEIPT_DIR to a local, untracked directory if a receipt is desired.

In failure-policy=allow mode, malformed transport is observed rather than converted into a global prompt-submission outage. In failure-policy=block mode, the provider event is denied only after transport/schema validation fails.

Receipts do not persist prompt text, attachment paths, or raw session identifiers. They store raw-byte SHA-256, byte length, detected encoding, top-level keys, schema-validation state, Cursor version when provided by the host, and a proof ceiling.

## Ownership boundary

Automation owns transport parsing, provider event-shape validation, privacy-safe receipts, and neutral diagnostic responses.

Consumers own product/repository policy, their state machines, authorization decisions, and whether a policy failure is fail-open or fail-closed.

Prompt definitions, P-number discovery, and Prompt Kit registry composition remain upstream-owned by prompt-invocation-upstream/v1. This capability must not become another prompt resolver.

## Attribution rule

Do not label a runtime failure Cursor-owned merely because Cursor displayed the error. A host-transport attribution requires a live receipt showing EMPTY_INPUT, DECODE_ERROR, INVALID_JSON, NON_OBJECT_JSON, or a valid JSON payload that violates the documented Cursor event shape before consumer policy ran.

If transport and provider schema are valid, the defect is downstream/consumer-owned unless separate evidence proves otherwise.

## Consumer migration rule

For a Cursor policy hook that needs conversation identity:

1. register sessionStart;
2. export/use its session_id through session-scoped environment state;
3. treat beforeSubmitPrompt as prompt validation only;
4. treat stop as completion/continuation only;
5. keep transport diagnostics separate from policy denial;
6. preserve a degraded/diagnostic proof state rather than pretending policy enforcement passed when transport was unavailable.

## Proof ceiling

The synthetic suite proves transport normalization, privacy behavior, Cursor schema validation, and neutral responses. It does not prove what an installed Cursor build actually writes to stdin. That requires a live receipt from the affected workstation.
