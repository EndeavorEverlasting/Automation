# AGENTS.md

## Repository identity

This repository is a **ubiquitous automation substrate**.

Treat `docs/REPOSITORY_CHARTER.md` as the canonical ownership contract and `CONTRIBUTING.md` as the canonical contribution/placement policy.

### Non-negotiable execution rules

- Keep core automation repository-, domain-, platform-, and consumer-agnostic.
- Isolate repository/provider/domain-specific behavior behind adapters, integrations, profiles, manifests, or configuration.
- Do not hard-code one consuming repository's paths, schemas, naming, credentials, product assumptions, or release lifecycle into shared core logic.
- Prefer deterministic machine-readable inputs, outputs, schemas, manifests, and receipts.
- Never commit secrets, authenticated browser profiles, cookies, tokens, or private runtime state.
- Reuse existing contracts and helpers before creating competing mechanisms.
- If a proposed feature is inseparable from one product's business logic, leave it with that product instead of contaminating this repository's core.
- Do not claim universal compatibility beyond observed validation.

## Seam / boundary review contract

When work creates or changes a shared interface, cross-repository dependency, adapter, provider bridge, package boundary, scheduler boundary, data authority, generated artifact, CLI surface, or other reusable seam, read:

- `harness/contracts/seam-boundary-review.v1.json`
- `docs/SEAM_BOUNDARY_REVIEW.md`

Required review behavior:

1. Identify the true owner.
2. Run the **Consumer Knowledge Test**: list what a normal consumer must know.
3. Treat upstream topology, donor repositories, migration history, provider quirks, and authority-routing rules as suspected leakage unless the public contract explicitly requires them.
4. Separate semantic contract identity from physical repo/path/provider location.
5. Verify fresh-agent discoverability from root wayfinding.
6. Treat repeated downstream discovery/routing/mirroring as evidence of upstream contract pressure.
7. Prove portability with an **Isolated Consumer Canary** when the seam is intended to be reusable.
8. After repairing the owner, migrate a real consumer and remove obsolete compensating downstream machinery.
9. Add a regression that prevents the obsolete path from silently returning.

Correct ownership alone is not a PASS. A seam remains defective when normal consumers still need implementation knowledge.

## Prompt invocation contract

P-number semantics are an **upstream dependency**. Automation consumes `prompt-invocation-upstream/v1`; it does not own prompt discovery, registry composition, authority routing, creation, mutation, or retirement.

When the operator supplies or references a P-number:

1. Read `docs/PROMPT_RUNTIME.md`.
2. Resolve the **verbatim operator text** through:
   `python scripts/prompt_runtime.py --text "<operator text>"`
3. Treat the returned upstream packet as prompt identity/intent authority.
4. Never substitute remembered prompt text, fuzzy-match another ID, inspect Prompt Kit registry topology, or require a Triage checkout.
5. `EXECUTE` means execute the resolved workflow now.
6. `EXECUTE_AND_IMPLEMENT` means execute it and carry authorized local implementation through reachable proof gates.
7. Prompt mutation/governance belongs upstream; Automation does not invent a downstream contribution lifecycle.
8. Preserve separate proof states for resolution, execution, implementation, integration, deployment, and production behavior.

Pinned dependency manifest: `vendor/prompt-invocation-upstream/manifest.v1.json`.

## P92 canonical-path contract

Before emitting path-sensitive mutation commands, read `harness/contracts/canonical-path.v1.json` and run:

`python scripts/path_receipt.py --repo-root .`

Treat its machine-readable receipt as the current path/execution-context evidence.

- Do not invent a new checkout path because the current one is unknown.
- An unresolved development root is `UNKNOWN_BLOCK_NEW_CLONE`.
- Production/use paths are capability-owned; `UNKNOWN` production use blocks production mutation but not safe development work.
- Remote merge success is not local deployment proof.

Before substantial mutation, recover current repository/provider truth and preserve these invariants.
