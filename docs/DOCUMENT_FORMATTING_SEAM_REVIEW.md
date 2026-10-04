# Document Formatting Seam & Boundary Review

Date: 2026-10-03
Capability: `document-formatting`
Result: **PASS AT PORTABLE CORE / PROVIDER ADAPTERS UNPROVEN**

## Owner

Automation is the canonical owner of reusable document-formatting orchestration because the same problem recurs across unrelated repositories and projects.

A consuming repository owns only its domain/project profile and genuinely consumer-specific integrations.

## Semantic contract

- capability identity: `document-formatting`
- consumer input: `document-formatting-consumer-profile/v1`
- plan output: `document-formatting-plan/v1`
- normal invocation: `python capabilities/document-formatting/plan.py --profile <profile.json>`

Repository paths are distribution locators, not the semantic identity.

## Consumer Knowledge Test

A normal consumer must know only:

- its own consumer/profile identity;
- its own semantic formatting-contract reference;
- its own archetypes;
- required provider features and execution environments;
- required visual-acceptance surfaces;
- proof/readback/branding policy.

A normal consumer does **not** need:

- the repository that first discovered the problem;
- H&H naming, tokens, paths, or evidence;
- Automation internal module layout beyond the documented CLI;
- donor PRs or migration history;
- provider credentials in tracked configuration;
- chat/model memory.

## Distribution artifact

The stable machine-readable surfaces are:

- `capabilities/document-formatting/schemas/consumer-profile.v1.json`
- `capabilities/document-formatting/schemas/plan.v1.json`
- `capabilities/document-formatting/plan.py`

The plan records a canonical profile SHA-256 and explicit proof ceiling.

## Isolated Consumer Canary

`tests/test_document_formatting_consumer_canary.py` creates a consumer profile in a temporary directory and invokes only the advertised CLI.

The temporary consumer does not import Automation internals or receive H&H-specific context. It proves normal CLI consumption and fail-closed branding policy behavior.

## Repeated downstream workaround evidence

NYC H&H currently carries project-local professional-document design, provider formatting, and acceptance machinery because that project repeatedly needed the behavior. That implementation is donor/consumer evidence, not proof that H&H owns the reusable capability.

The consumer migration is a separate downstream adoption change. Automation must not ingest H&H branding, private document identities, or project business rules.

## Provider boundary

The portable core currently builds and validates plans only.

Provider-specific mutation/readback belongs behind reusable adapters when admitted. Until such adapters exist:

- Google Docs mutation is unproven upstream;
- Word/Office automation is unproven upstream;
- dynamic page fields are provider-capability proof, not core proof;
- visual acceptance remains surface-specific;
- no repository/CI proof promotes itself to visual fidelity.

## Obsolete workaround removal

**PARTIAL / CONSUMER ADOPTION REQUIRED.**

The upstream owner is now explicit, but downstream duplication is not considered repaired until a representative consumer is rebound to this semantic capability and future generic work is routed upstream.

NYC H&H is the first intended real consumer. Its H&H-specific profile may remain local; reusable engine changes must route to Automation.

## Proof ceiling

This review proves the portable ownership/interface boundary and CLI canary. It does not prove provider adapters, live document mutation/readback, Microsoft Word/Office rendering, Google Docs fidelity, H&H adoption, deployment, or production use.
