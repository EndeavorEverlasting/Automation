# Automation Repository Charter

## Purpose

`Automation` is a **repository-agnostic, domain-agnostic, platform-agnostic automation substrate**.

It exists to host reusable automation capabilities that can serve **any repository, project, environment, workflow, or use case** without inheriting the product identity, assumptions, data model, release lifecycle, or governance of any one consumer.

This repository is intentionally ubiquitous. A capability belongs here when its core behavior is useful beyond a single product boundary or can be made so through a clean adapter/interface seam.

## Core invariants

1. **No single consumer owns the core.**  
   No repository, product, client, organization, workflow, or domain may redefine Automation's core identity around itself.

2. **Portable core, isolated integration.**  
   General behavior lives in reusable modules. Repository-, provider-, vendor-, domain-, or environment-specific behavior must sit behind explicit adapters, integrations, configuration, or invocation layers.

3. **Configuration over contamination.**  
   Prefer parameters, manifests, schemas, profiles, and adapters over hard-coded assumptions about a particular repository, path, account, tenant, project, website, or operator environment.

4. **Machine-readable contracts first.**  
   Inputs, outputs, receipts, manifests, schemas, and error states should be deterministic and machine-readable whenever practical.

5. **Capability boundaries stay explicit.**  
   A tool may integrate with a specific service or product, but the repository must preserve the distinction between:
   - reusable automation capability;
   - provider/domain adapter;
   - consumer-specific configuration.

6. **No accidental product migration.**  
   Automation is not a dumping ground for unrelated application code. Product-specific business logic should remain with its product unless it is being deliberately extracted into a reusable automation primitive.

7. **Evidence before ownership expansion.**  
   A new capability should be generalized only as far as the implementation and tests actually support. Do not claim universal compatibility without proof.

8. **Secrets and runtime state never become source.**  
   Credentials, browser profiles, cookies, session stores, tokens, generated private data, and other runtime secrets must stay outside version control.

9. **Public repository independence.**  
   Private continuity stores may help the operator incubate or coordinate work, but a public Automation capability must be usable without private continuity access. Public Git must not expose private continuity-store locators merely for traceability.

10. **Executor determinism over model assumptions.**  
   Runtime-distributed work must be packaged with explicit scope, capabilities, evidence, mutation authority, acceptance gates, and proof ceiling. No reusable contract may assume frontier-model reasoning quality to fill missing architecture.

## Placement test

Before adding a capability, ask:

- Is the underlying operation useful across more than one repository, product, environment, or use case?
- If not today, is there a clean reusable core with consumer-specific behavior isolated behind an adapter?
- Can the capability accept explicit inputs instead of assuming one repository layout or one operator environment?
- Can outputs be consumed without knowledge of the original consumer?
- Would moving this code into one consuming product create avoidable duplication elsewhere?

If the answer is broadly yes, `Automation` is an appropriate owner.

If the implementation is inseparable from one product's business rules, UI, schema, or release lifecycle, that product should own it instead.

## Architecture expectation

Prefer this shape:

```text
consumer / repo / workflow
        |
        v
adapter or integration layer
        |
        v
reusable automation capability
        |
        v
machine-readable artifact / receipt / result
```

Provider-specific adapters may exist here when they expose a reusable capability. Their provider-specific assumptions must not leak into unrelated core modules.

## Compatibility philosophy

"Ubiquitous" is an architectural direction, not an excuse to pretend every environment is identical.

Capabilities should:
- declare supported platforms and prerequisites;
- fail clearly when required facilities are unavailable;
- preserve stable machine-readable interfaces where practical;
- isolate provider differences;
- add compatibility through adapters rather than forks.

## Repository evolution

Private incubation may precede public capability admission. Incubation is not source control and does not make an idea an admitted capability. Public admission still requires the contribution and seam-boundary gates.

This repository may grow from a small collection of utilities into a shared automation platform. Growth should preserve the invariants above.

When a tool becomes a full product with its own persistent domain model, UI, release lifecycle, and independent ownership boundary, splitting it into a dedicated repository may be appropriate. Until then, reusable automation primitives should remain here rather than being duplicated across consumers.
