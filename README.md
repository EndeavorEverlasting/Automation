# Automation

**Ubiquitous automation primitives for any repository, project, environment, workflow, or use case.**

This repository is intentionally **repository-agnostic, domain-agnostic, and platform-agnostic**. It owns reusable automation capabilities, not the product identity of any one consumer.

## Ownership rule

A capability belongs here when its core behavior can be reused across different repositories, products, environments, or use cases.

Consumer-specific behavior must be isolated behind adapters, integrations, configuration, profiles, or invocation layers. Shared core logic must not silently inherit one consumer's paths, schemas, credentials, naming, business rules, or release lifecycle.

```text
consumer / repository / workflow
            |
            v
    adapter / integration
            |
            v
 reusable automation core
            |
            v
machine-readable artifact / receipt
```

## Prompt invocation without model memory

Repository-capable agents do not need conversational memory to know what `P92` or another registered prompt means.

```powershell
python scripts/prompt_runtime.py --text "invoke & implement P92"
```

Automation delegates prompt identity, intent semantics, authority routing, and prompt bytes to the pinned `prompt-invocation-upstream/v1` dependency. It does not reproduce Prompt Kit registry logic. See [docs/PROMPT_RUNTIME.md](docs/PROMPT_RUNTIME.md).

## Runtime distribution without executor judgment

Automation consumes an upstream `planning.runtime_partition` placement decision through an execution-facing validation contract. It does not become a competing planner or broker.

A READY handoff must be explicit enough for ordinary executors such as Cursor, OpenCode, connected-provider runtimes, or CI without relying on model memory or frontier-model judgment.

- [docs/RUNTIME_DISTRIBUTION.md](docs/RUNTIME_DISTRIBUTION.md)
- [harness/contracts/runtime-execution-handoff.v1.json](harness/contracts/runtime-execution-handoff.v1.json)
- [docs/PUBLIC_PRIVATE_BRIDGE.md](docs/PUBLIC_PRIVATE_BRIDGE.md)
- `python scripts/validate_runtime_handoff.py --packet <packet.json> --require-ready`

Tracked public handoffs fail closed on private continuity-store links, person-specific workstation paths, and secret-bearing fields. Private operator continuity may point to this public repository, but this repository must remain usable without private continuity access.

## Repository charter

The canonical ownership and placement contracts are:

- [docs/REPOSITORY_CHARTER.md](docs/REPOSITORY_CHARTER.md)
- [docs/SEAM_BOUNDARY_REVIEW.md](docs/SEAM_BOUNDARY_REVIEW.md) for reusable seam/consumer-boundary review
- [harness/contracts/seam-boundary-review.v1.json](harness/contracts/seam-boundary-review.v1.json) for the machine-readable review contract
- [CONTRIBUTING.md](CONTRIBUTING.md)
- [AGENTS.md](AGENTS.md) for repository-capable agents
- [harness/contracts/canonical-path.v1.json](harness/contracts/canonical-path.v1.json) for P92 path ownership
- `python scripts/path_receipt.py --repo-root .` for the current PATH INPUT / execution-context receipt

The short version:

- reusable automation belongs here;
- product-specific business logic stays with its product;
- provider- and repo-specific seams stay isolated;
- configuration beats hard-coded assumptions;
- machine-readable contracts are preferred;
- secrets and runtime state never belong in source control;
- "ubiquitous" is a direction backed by validation, not an unsupported compatibility claim.

## Capabilities

Admitted capabilities:

- [`playlist-link-extraction`](capabilities/playlist-link-extraction/CAPABILITY.md) — status `CORE_IMPLEMENTED_ADAPTERS_PENDING`
- [`agent-hook-runtime`](capabilities/agent-hook-runtime/CAPABILITY.md) — status `CORE_IMPLEMENTED_CURSOR_ADAPTER_DIAGNOSTIC_ONLY`; separates JSON-stdio host transport/schema proof from consumer policy and emits privacy-safe runtime receipts.
- [`social-publication`](capabilities/social-publication/CAPABILITY.md) — status `PROGRAM_DESIGN_PROTOTYPE_PROVEN`; approval-bound, provider-neutral text publication with a LinkedIn adapter prototype. Live OAuth/network publication remains unproven.
- [`document-formatting`](capabilities/document-formatting/CAPABILITY.md) — status `COMPILER_IR_PROTOTYPE_PROVEN_GOOGLE_DOCS_PLAN_ADAPTER_PROVEN`; reusable consumer profiles plus deterministic semantic compilation to provider-neutral IR and a fail-closed Google Docs adapter plan.

Document-formatting portable plan:

```powershell
python capabilities/document-formatting/plan.py \
  --profile capabilities/document-formatting/fixtures/consumer-profile.synthetic.v1.json \
  --output Outputs/document-formatting-plan.json
```

Consumers keep their own tokens, archetypes, exemplars, branding, and private provider identities; Automation owns the reusable orchestration contract.

Social-publication prototype:

```powershell
python capabilities/social-publication/prototype.py \
  --intent capabilities/social-publication/fixtures/text-intent.synthetic.v1.json \
  --mode success
```

See [P95 LinkedIn publication architecture](docs/P95_LINKEDIN_PUBLICATION_ARCHITECTURE.md) for the proved call stacks and live-launch boundary.

Reusable playlist core entrypoint:

```powershell
python capabilities/playlist-link-extraction/extract_links.py `
  --batch capabilities/playlist-link-extraction/fixtures/synthetic-observation-batch.v1.json `
  --output-json Outputs/playlist-link-artifact.json `
  --output-csv Outputs/playlist-link-artifact.csv
```

Adapters emit `playlist-link-observation-batch/v1`; the core owns normalization, ordered occurrences, unique-link aggregation, canonical JSON, and CSV projection.

Offline adapter surface:

```powershell
python capabilities/playlist-link-extraction/adapters/yt-dlp-json/adapt.py `
  --payload capabilities/playlist-link-extraction/adapters/yt-dlp-json/fixtures/sample-playlist.v1.json `
  --target-id target-a `
  --output-batch Outputs/playlist-link-observation-batch.json
```

Live provider execution remains unproven; status stays `CORE_IMPLEMENTED_ADAPTERS_PENDING`.


### Artifact continuity before synchronization

Before artifact-producing work decides to create a local file, use the repository-wide [artifact continuity preflight](docs/ARTIFACT_CONTINUITY_PREFLIGHT.md) and its [machine-readable contract](harness/contracts/artifact-continuity-preflight.v1.json).

`artifact-continuity-preflight/v1` is the activation/inheritance layer: it makes existing provider source authority, current-runtime provider work, local derivative role, provider-link delivery, and unresolved sync obligations explicit. `artifact-sync` remains the mechanics layer.

### Artifact synchronization

- [`artifact-sync`](capabilities/artifact-sync/CAPABILITY.md) — status `CONTRACT_DEFINED_RUST_IMPLEMENTATION_PENDING`

Provider-backed artifact edits must not silently stop at local-only derivatives. The admitted v1 contract uses semantic bindings, exact provider identity resolved only from protected runtime state, ephemeral-by-default local materialization, fail-closed conflicts, provider-native mutation for native workspace documents, and read-back verification before a mutation can report `SYNCED`.

See:
- [binding contract](capabilities/artifact-sync/schemas/binding.v1.json)
- [receipt contract](capabilities/artifact-sync/schemas/receipt.v1.json)
- [P04 factoring plan](docs/plans/P04_ARTIFACT_SYNC_FACTORING_2026-10-03.md)
- [READY Cursor handoff](docs/examples/runtime-handoff.artifact-sync-rust-cli.json)

## Existing experiments

This repository began as a small automation sandbox. Early experiments may predate the current charter. New work should follow the charter rather than treating historical layout as the architectural model.
