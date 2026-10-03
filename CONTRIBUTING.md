# Contributing and Placement Policy

`Automation` is a ubiquitous automation substrate. Contributions are placed by **capability ownership**, not by whichever repository or project happened to need the code first.

## Placement decision

Before adding code, classify it:

1. **Reusable automation capability**  
   Put it under `capabilities/<capability-id>/` when it owns a stable operation, input/output contract, and reusable behavior.

2. **Provider/domain/runtime adapter for a capability**  
   Put it under that capability's adapter boundary, normally `capabilities/<capability-id>/adapters/<adapter-id>/`. Provider-specific behavior must not leak into the reusable core.

3. **Repository-wide execution/proof machinery**  
   Put it under `harness/` when it governs how Automation itself resolves authority, paths, evidence, invocation, validation, or proof.

4. **Repository maintenance/bootstrap helper**  
   Put it under `scripts/` only when it operates the repository or its harness. A reusable user-facing automation must not be hidden as an unowned root script.

5. **Configuration**  
   Put portable tracked configuration under `config/`. Secrets, personal paths, cookies, browser profiles, tokens, and private runtime state are not configuration and must remain untracked.

6. **Product-specific business logic**  
   Leave it with that product unless a clean reusable automation primitive is deliberately extracted. Do not migrate an application into Automation merely because it contains automation.

## Admission gate for a new capability

A new `capabilities/<id>/` boundary must define:

- purpose and supported use cases;
- inputs and outputs;
- reusable core ownership;
- adapter/provider ownership;
- explicit non-goals and forbidden assumptions;
- machine-readable artifact/schema authority where applicable;
- runtime/secrets boundary;
- validation/proof gate;
- canonical repository-relative path;
- production/use path and promotion boundary, or an explicit `UNDECLARED` state;
- evidence for why this is a new capability instead of an extension of an existing one.

Do not claim universal compatibility merely because the repository is ubiquitous. Compatibility is capability-specific and evidence-bounded.

## Extend versus create

Extend an existing capability when the new work preserves the same primary operation and artifact contract.

Create a new capability when the operation, lifecycle, authority, or artifact model is independently meaningful and would otherwise force unrelated behavior into an existing core.

If uncertain, prefer a small adapter or extension first. Split only when evidence shows an independent boundary.

## Cross-repository use

Consumer repositories may:

- call Automation capabilities;
- pin versions/commits/releases;
- provide consumer-specific configuration;
- implement thin adapters that are truly consumer-owned.

Consumer repositories must not fork Automation's reusable core merely to customize a path, provider, repository name, or UI. Strengthen the shared contract or add an adapter instead.

## Prompt-driven work

Prompt identities such as `P92` are resolved through the repository prompt runtime described in `docs/PROMPT_RUNTIME.md`.

When an operator invokes a prompt:

- recover the exact prompt body from repository-owned canonical sources;
- do not rely on conversational/model memory as authority;
- do not fuzzy-substitute a different P-number;
- execute the resolved workflow when invocation intent is present;
- when the operator says **invoke and implement**, carry authorized changes through reachable validation/integration gates rather than merely explaining the prompt;
- preserve source path, source blob SHA, and prompt-body SHA-256 in the invocation packet.

## Pull request proof

A contribution should distinguish:

- designed;
- implemented;
- locally validated;
- integration validated;
- merged;
- deployed;
- production verified.

Never collapse those states into one completion claim.
