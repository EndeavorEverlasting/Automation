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

## Prompt invocation contract

Prompt identities are repository-owned inputs, not model-memory shortcuts.

When the operator supplies or references a P-number:

1. Read `docs/PROMPT_RUNTIME.md`.
2. Resolve the operator's **verbatim invocation text** through:
   `python scripts/prompt_runtime.py --text "<operator text>"`
3. Use the exact resolved `copy_content`, source repository/path/blob SHA, and body SHA-256 as prompt authority.
4. Never substitute remembered prompt text, a semantically similar prompt, or a fuzzy ID match.
5. `EXECUTE` means execute the resolved workflow now.
6. `EXECUTE_AND_IMPLEMENT` means execute it and carry authorized implementation through reachable validation/integration gates. Do not stop after printing, summarizing, or recommending.
7. `EXECUTE_THEN_MUTATE` executes first unless the operator explicitly ordered prompt mutation first.
8. `REFERENCE` does not authorize execution.
9. `UNRESOLVED`, `SOURCE_CONFLICT`, or `PROVIDER_LOOKUP_REQUIRED` fail closed. Recover provider/repository truth rather than guessing.
10. Resolution proves prompt identity only. Preserve separate proof states for implementation, validation, integration, deployment, and production behavior.
11. A tracked provenance snapshot may be used when canonical transport is unavailable, but it carries `canonical_latestness=UNVERIFIED`. Freshness-sensitive execution or prompt mutation requires canonical source refresh first.

The current prompt-source repository name is configuration and may change. Do not hard-code it outside `config/prompt-sources.v1.json`; honor its environment overrides.

## P92 canonical-path contract

Before emitting path-sensitive mutation commands, read `harness/contracts/canonical-path.v1.json` and run:

`python scripts/path_receipt.py --repo-root .`

Treat its machine-readable receipt as the current path/execution-context evidence.

- Do not invent a new checkout path because the current one is unknown.
- An unresolved development root is `UNKNOWN_BLOCK_NEW_CLONE`.
- Production/use paths are capability-owned; `UNKNOWN` production use blocks production mutation but not safe development work.
- Remote merge success is not local deployment proof.

Before substantial mutation, recover current repository/provider truth and preserve these invariants.
