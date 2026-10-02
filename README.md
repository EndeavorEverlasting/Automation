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

## Repository charter

The canonical ownership and placement contract is:

- [docs/REPOSITORY_CHARTER.md](docs/REPOSITORY_CHARTER.md)
- [AGENTS.md](AGENTS.md) for repository-capable agents

The short version:

- reusable automation belongs here;
- product-specific business logic stays with its product;
- provider- and repo-specific seams stay isolated;
- configuration beats hard-coded assumptions;
- machine-readable contracts are preferred;
- secrets and runtime state never belong in source control;
- "ubiquitous" is a direction backed by validation, not an unsupported compatibility claim.

## Existing experiments

This repository began as a small automation sandbox. Early experiments may predate the current charter. New work should follow the charter rather than treating historical layout as the architectural model.
