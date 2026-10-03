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

The first admitted capability boundary is:

- [`playlist-link-extraction`](capabilities/playlist-link-extraction/CAPABILITY.md) - boundary defined; existing prototype integration is the next transition.

## Existing experiments

This repository began as a small automation sandbox. Early experiments may predate the current charter. New work should follow the charter rather than treating historical layout as the architectural model.
