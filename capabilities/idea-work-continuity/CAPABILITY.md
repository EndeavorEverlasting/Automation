# Idea Work Continuity

## Purpose

`idea-work-continuity` keeps the human idea surface and the automation/work surface synchronized without making chat, a spreadsheet, or one consumer repository a second planning authority.

The reusable operation is:

`idea / discovered contract gap -> recover existing durable owner -> create or extend remote work state -> preserve a bounded next transition`

The capability does **not** decide product architecture for a consumer. It guarantees that execution-relevant insight cannot disappear at the end of a conversation.

## Core invariant

An execution-relevant idea is not complete merely because an agent understood it.

Before terminal handoff it must resolve to exactly one durable continuity disposition:

- `MIRROR_EXISTING_PLAN`
- `APPEND_ITERATION`
- `CREATE_REMOTE_PLAN`
- `DEFERRED_ADOPTION`
- `BLOCKED_OWNER_RESOLUTION`

Non-executable material may use `NO_EXECUTION_OBLIGATION`.

A chat-only plan is never a valid durable anchor.

## Existing-plan rule

Search/recover the current canonical owner before creating anything.

If a plan already exists, do not create another plan just to preserve the latest conversation. Either:

1. bind to the existing plan;
2. add one bounded iteration when the target is safe to mutate; or
3. leave a durable deferred-adoption obligation.

This is continuity, not plan proliferation.

## Migration/convergence guard

Active migration is a first-class collision state.

If a target consumer is `MIGRATION_ACTIVE` or `CONVERGENCE_ACTIVE`, new consumer mutation requires explicit collision-clear evidence. Without that evidence, the continuity action is `DEFERRED_ADOPTION`.

That allows insight to become remote and unavoidable **without forcing an implementation lane into a moving destination**.

## Private intake boundary

A spreadsheet, note, chat, private document, or provider event may remain the raw-authority surface for the operator's wording.

Public Automation artifacts keep only:

- semantic source identity;
- stable/private-resolution-safe item handle;
- content hash when useful;
- canonical public owner/plan anchor;
- disposition;
- next transition;
- sanitized evidence;
- proof ceiling.

Do not commit private provider IDs, URLs, raw transcripts, or raw idea text merely for traceability.

## Priority boundary

Chronology can help reconstruct context. It does not grant authority to assign operator priority.

The contract supports only:

- `OPERATOR`
- `UNSPECIFIED`

If priority was not explicitly supplied, keep it unspecified.

## Consumer adoption

Consumers may pin this contract and implement thin source/provider adapters. They should not fork the continuity rules.

A consumer with an existing planning authority keeps that authority. This capability only guarantees the bridge from captured/discovered insight to that authority remains durable.

## Validation

Validate a receipt with:

`python scripts/validate_idea_work_continuity.py --receipt <receipt.json>`

The TokenCorridor example in `docs/examples/idea-work-continuity.tokencorridor-deferred.v1.json` intentionally demonstrates migration-safe deferral: the existing Prompt Scratch program plan remains canonical and no competing TokenCorridor plan is created.
