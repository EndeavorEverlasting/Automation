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

## Shared seam / boundary review

Changes that create or materially alter a shared interface, adapter, cross-repository dependency, scheduler boundary, provider bridge, package boundary, data authority, generated artifact, or reusable CLI surface must apply the repository seam review:

- human checklist: `docs/SEAM_BOUNDARY_REVIEW.md`
- machine-readable contract: `harness/contracts/seam-boundary-review.v1.json`

A contribution does not pass this gate merely because the correct repository owns the code. Reviewers must establish:

- the normal consumer's minimal inputs/outputs;
- which facts the consumer must know;
- whether any of those facts are leaked upstream implementation topology;
- stable semantic contract identity distinct from repo/path/provider location;
- root discoverability;
- whether repeated downstream workarounds indicate a missing upstream contract;
- isolated-consumer portability where reuse is claimed;
- removal of obsolete compensating downstream implementations after repair.

If a consumer still needs internal source layout, donor checkout paths, migration topology, authority-selection logic, or provider-specific implementation details, treat the boundary as leaky until explicitly justified.

## Admission gate for a new capability

A new `capabilities/<id>/` boundary must define:

- purpose and supported use cases;
- inputs and outputs;
- reusable core ownership;
- adapter/provider ownership;
- explicit non-goals and forbidden assumptions;
- machine-readable artifact/schema authority where applicable;
- runtime/secrets boundary;
- supported execution environments and required capabilities;
- mutation authority, evidence inputs, and freshness requirements for runtime-distributed work;
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

Prompt definitions and prompt governance are upstream dependencies, not Automation contribution surfaces.

When an operator invokes a P-number:

- call `scripts/prompt_runtime.py` with the verbatim request;
- consume the pinned `prompt-invocation-upstream/v1` packet;
- execute the resolved workflow locally when execution intent is present;
- for **invoke and implement**, carry authorized local work through reachable proof gates;
- never recreate Prompt Kit registry traversal or retained-source routing here.

If the prompt definition itself needs creation, mutation, or retirement, contribute that change to the canonical upstream prompt owner.

## Runtime-distributed contributions

Runtime placement is an upstream planning decision; Automation validates the execution-facing handoff rather than creating a second planning protocol.

Tracked handoffs must conform to:

- `harness/contracts/runtime-execution-handoff.v1.json`
- `docs/RUNTIME_DISTRIBUTION.md`
- `docs/PUBLIC_PRIVATE_BRIDGE.md`

Before local execution, validate READY packets with:

```powershell
python scripts/validate_runtime_handoff.py --packet <packet.json> --require-ready
```

A runtime handoff must carry explicit owned/forbidden scope, evidence inputs, mutation authority, acceptance gates, proof ceiling, and freshness requirements. Local executors must not be expected to reconstruct architecture from chat history.

Private operator continuity may inform a contribution, but public Git must contain only the sanitized reusable contract, synthetic fixtures, and public provenance. Do not commit private continuity-store URLs/IDs merely to preserve traceability.

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


## Provider-backed artifact changes

Reusable provider-backed file/document synchronization belongs behind the `artifact-sync` capability rather than in one consumer's ad hoc script.

For new or modified provider-backed artifact flows:

- bind by semantic identity plus a private runtime locator handle, never a tracked provider URL or raw provider file ID;
- default local materialization to ephemeral; persistent mirrors require an explicit bounded storage budget;
- do not treat local-only output as successful completion of a provider-backed mutation;
- fail closed when both sides changed since the last verified common state;
- use provider-native mutation APIs for native documents/spreadsheets/presentations and raw byte replacement only for blob files;
- require provider write plus read-back verification before reporting `SYNCED`;
- keep authentication, tokens, account context, and private locator maps outside Git;
- route semantic changes to the artifact-sync contract owner rather than asking a lower-capability executor to invent policy.


## Artifact continuity is a bootstrap/inheritance concern

Do not solve provider-backed artifact continuity by adding a fresh handwritten rule to each repository.

Repositories/workflows that may consume or produce provider-backed artifacts should consume `artifact-continuity-preflight/v1` through root wayfinding, a pinned shared dependency, or repository/bootstrap tooling.

The preflight determines known provider source, exact identity, runtime/provider ownership, local derivative role, provider-link delivery, and unresolved sync obligations. `artifact-sync` owns synchronization mechanics after the preflight selects a binding.
