# P95 — LinkedIn Publication Program Design

## User outcome

The terminal user value is **a specific, operator-approved text post appearing on the authenticated member's LinkedIn profile with a provider publication identifier captured as evidence**.

Opening LinkedIn, previewing text, or constructing an HTTP request is not terminal success.

## Constraints and invariants

- Automation owns reusable publication mechanics, not private career strategy or unpublished Drive topology.
- The first implementation path is text-only.
- No content is published unless approval is bound to the exact publishable-content hash.
- A changed post invalidates earlier approval.
- OAuth secrets and access tokens are runtime-only.
- Public Git contains synthetic fixtures only.
- Provider identity and API behavior terminate at the LinkedIn adapter.
- Provider-neutral core code must not know Person URNs, LinkedIn endpoints, or LinkedIn headers.
- P95 may prove thin call stacks, but it may not claim live publication without live OAuth/network proof.

## Design alternatives

### A. LinkedIn-only publication capability

Fastest initial implementation, but it couples the reusable core to Person URNs, LinkedIn headers, and LinkedIn lifecycle semantics. It would make later provider support a refactor of the owner rather than an adapter addition.

**Disposition: rejected.**

### B. Browser/UI automation

Could imitate manual posting without API setup, but it introduces fragile selectors, browser profile/session custody, UI drift, and secret-bearing runtime state before those costs are justified.

LinkedIn exposes a supported member-publishing API, so browser automation is not the smallest stable primary seam.

**Disposition: rejected as primary path.**

### C. Provider-neutral publication core + LinkedIn adapter

The core owns intent validation, content identity, approval binding, state, and receipts. LinkedIn owns author identity, API request shape, OAuth injection, and provider errors.

This design is only slightly larger than a LinkedIn-only script while preserving Automation's repository charter and enabling future provider adapters without changing the core lifecycle.

**Disposition: selected.**

## Domain vocabulary

**PublicationIntent** — exact publishable content plus provider and visibility.

**ContentIdentity** — canonical SHA-256 over publishable semantics, excluding request bookkeeping and secrets.

**PublicationApproval** — operator authorization bound to one ContentIdentity.

**PublicationPreview** — non-mutating representation of the current intent and its ContentIdentity.

**ProviderRequest** — adapter-owned network request shape with runtime secret requirements declared but secret values excluded.

**PublicationReceipt** — provider-neutral evidence of blocked, failed, or published state.

**ProviderPostId** — provider-returned identifier proving creation when available.

## State model

```text
DRAFT
  -> PREVIEW_READY
  -> APPROVED(content_sha256)
  -> PROVIDER_REQUEST_READY
  -> PUBLISHED

PREVIEW_READY
  -> BLOCKED_APPROVAL_REQUIRED

APPROVED(old_hash) + changed content
  -> BLOCKED_STALE_APPROVAL

PROVIDER_REQUEST_READY
  -> PROVIDER_REQUEST_BUILD_FAILED (NOT_EMITTED)
  -> PROVIDER_TRANSPORT_FAILED (UNKNOWN)
  -> PROVIDER_RESPONSE_INCOMPLETE (EMITTED)
  -> PROVIDER_AUTHORIZATION_FAILED (EMITTED)
  -> PROVIDER_REJECTED (EMITTED)
```

The state owner is the publication core. Provider adapters translate provider responses into the core's terminal states.

## Module map

### `core/publication.py`

Owns:

- intent validation;
- publishable projection;
- content hash;
- approval verification;
- provider-neutral result classification;
- receipt construction.

Does not own:

- OAuth;
- LinkedIn identity;
- HTTP client details;
- content generation;
- scheduling.

### `adapters/linkedin.py`

Owns:

- Person URN validation;
- LinkedIn `/rest/posts` endpoint;
- `Linkedin-Version`;
- `X-Restli-Protocol-Version`;
- text-post request translation;
- successor OAuth/token injection and provider error mapping.

### successor transport

Not implemented broadly in P95.

The build sprint may add an HTTP transport with access-token injection at send time. No token may enter a tracked artifact or persisted receipt.

## Success call stack

```text
operator-approved post text
  -> PublicationIntent
  -> core.validate_intent
  -> core.content_sha256
  -> core.prepare_preview
  -> operator approval of exact SHA-256
  -> core.execute_approved_publication
  -> linkedin.build_text_post_request
  -> runtime HTTP transport injects OAuth token
  -> POST /rest/posts
  -> HTTP 201 + x-restli-id
  -> core PublicationReceipt(state=PUBLISHED)
  -> terminal value: post exists + provider post ID captured
```

The P95 prototype traverses this stack with a fake transport so the approval and adapter seams are executable without claiming live network proof.

## Failure call stack — stale approval

```text
preview hash H1
  -> operator approval H1
  -> content changes to H2
  -> core.execute_approved_publication
  -> compare H1 != H2
  -> BLOCKED_STALE_APPROVAL
  -> provider request is not emitted
```

This is the critical safety failure path.

## Failure call stack — provider authorization

```text
approved H
  -> LinkedIn provider request
  -> runtime transport
  -> HTTP 401/403
  -> adapter/core translation
  -> PROVIDER_AUTHORIZATION_FAILED
  -> no success receipt
```

## Current LinkedIn platform facts

As verified against current Microsoft Learn / LinkedIn documentation during this P95 sprint:

- Share on LinkedIn grants `w_member_social` through the LinkedIn Developer Portal.
- `w_member_social` permits posting on behalf of an authenticated member.
- member posting uses member authorization / OAuth.
- the current Posts API endpoint is `POST https://api.linkedin.com/rest/posts`.
- Posts API requests require `Linkedin-Version: YYYYMM` and `X-Restli-Protocol-Version: 2.0.0`.
- a member post author is a Person URN `urn:li:person:{id}`.
- successful creation returns HTTP 201 and the created post ID in `x-restli-id`.
- restricted `r_member_social` is not required for the publication-only path.

Official references:

- https://learn.microsoft.com/en-us/linkedin/shared/authentication/getting-access
- https://learn.microsoft.com/en-us/linkedin/shared/authentication/authentication
- https://learn.microsoft.com/en-us/linkedin/marketing/community-management/shares/posts-api
- https://learn.microsoft.com/en-us/linkedin/marketing/community-management/shares/post-api-schema

## Launch path

### Phase 1 — P95 design/prototype

Prove approval, request construction, success classification, and consequential failure stacks using synthetic fixtures.

### Phase 2 — bounded build

Implement only the missing live seams:

- OAuth/member authorization bootstrap;
- authenticated-member Person URN resolution;
- HTTP transport with runtime-only token injection;
- privacy-safe runtime configuration;
- controlled live text-post command;
- publication receipt persistence.

Do not add scheduling, analytics, media, content generation, or browser automation.

### Phase 3 — first controlled post

Input the already-approved operator post at runtime, preview it, bind approval to the exact hash, and execute one live LinkedIn text post.

The post itself is the first live provider proof.

## Second-pass critique

**Leak found:** approval could have been modeled as a boolean. That would allow content to change after approval. Repaired by binding approval to ContentIdentity.

**Leak found:** OAuth could have been passed through the provider request artifact. Repaired by making the request artifact declare a runtime-secret requirement while token injection remains transport-only.

**Scope pressure found:** scheduling and content generation are adjacent but not required for the first post. They remain out of scope.

**Proof gap found:** HTTP 201 alone is not enough terminal evidence. The core now requires a non-empty provider post ID before emitting PUBLISHED; 201 without that identifier becomes PROVIDER_RESPONSE_INCOMPLETE.

**Approval-surface gap found:** the JSON schema forbids undeclared fields, but the first runtime validator did not. Unexpected top-level or content fields are now rejected so no publishable behavior can bypass the approved content projection.

**Transport-state gap found:** a transport exception cannot prove whether the remote service received the request. The first boolean emission field could not represent that uncertainty. It is replaced by `provider_request_state = NOT_EMITTED | EMITTED | UNKNOWN`; request-build failures are NOT_EMITTED and transport exceptions are UNKNOWN.

**Receipt-boundary gap found:** a permissive receipt schema could validate secret-bearing extra fields. The receipt schema is now closed, and `PUBLISHED` additionally requires a non-empty provider post ID and `EMITTED` request state.

**Provider mismatch gap found:** adapter request-build errors now become provider-neutral `PROVIDER_REQUEST_BUILD_FAILED` receipts instead of uncaught exceptions.

**Schema/runtime mismatch found:** v1 schema strings now reject whitespace-only request IDs, provider names, and text exactly as runtime validation does.

**Provider coupling check:** core tests can run without LinkedIn imports or LinkedIn identity. Provider topology terminates at the adapter.

## Exact implementation seam

Route broad implementation to P07 with this fixed seam:

```text
social-publication core (preserve)
    |
    +-- LinkedIn adapter request builder (preserve)
            |
            +-- ADD OAuth/member identity runtime
            +-- ADD HTTP transport/token injection
            +-- ADD controlled live publish launcher
            +-- ADD provider/live receipts
```

The first live gate is **operator-authorized LinkedIn OAuth**, followed by one controlled text publication.

## Proof ceiling

Repository design + executable synthetic success/failure call-stack proof only.

Unproven:

- real LinkedIn app configuration;
- `w_member_social` grant for the operator;
- real Person URN;
- live access token;
- live HTTP request;
- actual published post;
- production launcher/deployment.
