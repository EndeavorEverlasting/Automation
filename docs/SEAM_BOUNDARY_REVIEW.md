# Seam & Boundary Review Checklist

This is the reusable architecture doctrine extracted from Prompt Scratch **PS-0050 through PS-0056**.

The core rule is simple:

> **Correct ownership is necessary, but not sufficient. A healthy seam lets a normal consumer use the capability without learning upstream implementation topology.**

Use this review whenever a change creates or modifies a shared interface, repository dependency, adapter, provider bridge, package boundary, scheduler boundary, data authority, generated artifact, CLI surface, or other cross-system seam.

The machine-readable authority for this checklist is:

`harness/contracts/seam-boundary-review.v1.json`

## Fast review

1. **Find the true owner.** Which component owns behavior, authority, lifecycle, and canonical truth?
2. **Run the Consumer Knowledge Test.** What must a normal consumer know?
3. **Classify every required fact.** Is it domain input, stable contract identity, or leaked implementation detail?
4. **Separate semantic identity from location.** Repo names, paths, provider URLs, and deployment locations are locators/provenance, not semantic API identity.
5. **Check discoverability.** Can a fresh engineer/agent find the owner, contract, normal invocation, and proof ceiling from the repo root?
6. **Look for workaround multiplication.** Repeated downstream discovery/routing/mirroring is evidence of upstream pressure.
7. **Require one normal machine-readable surface.** Consumers should not compose the upstream system themselves.
8. **Preserve provenance without leaking topology.** Receipts/manifests may name source/version facts without making internal composition part of the consumer API.
9. **Run an Isolated Consumer Canary.** Use only the advertised dependency/interface in an otherwise empty consumer context.
10. **Delete the scar.** Once the seam is repaired, remove the compensating downstream implementation and add a regression against its return.

## Consumer Knowledge Test

Ask:

> **What does a normal downstream consumer need to know to use this capability successfully?**

Healthy knowledge usually includes:

- domain-level input;
- stable contract/protocol identity and version;
- supported invocation;
- documented output/result schema;
- explicit failure states;
- optional provenance/version receipt.

Suspicious knowledge includes:

- upstream directory or registry layout;
- internal modules/classes;
- donor repository locations;
- migration history;
- provider-specific authentication quirks;
- database table names that are not part of the public contract;
- scheduler object IDs or implementation-only task topology;
- authority-selection rules;
- generated-source composition;
- model/chat memory.

If the normal consumer needs those details, investigate the boundary before adding another adapter.

## Concrete anti-patterns

### 1. Upstream by ownership, internal by interface

**Smell:** The correct owner exists, but consumers must understand its internals.

**Example:** A canonical prompt resolver exists upstream, yet consumers must read registry files and product-boundary manifests themselves.

**Repair:** Publish one stable consumer-facing contract/artifact; keep composition and authority routing upstream.

### 2. Donor checkout dependency

**Smell:** A consumer needs a second repository checkout simply to finish a normal lookup.

**Example:** Resolving a retained item requires the consumer to locate a donor repository.

**Repair:** Upstream distributes the retained result and provenance through the stable interface while leaving definition authority with the donor owner.

### 3. Path-shaped API

**Smell:** A repository slug, filesystem path, provider URL, or deployment location becomes the dependency identity.

**Example:** Consumers bind to `repo-x/internal/registry/foo.json` rather than `capability-contract/v1`.

**Repair:** Give the seam a semantic identity/version; treat location as configuration or provenance.

### 4. Adapter multiplication

**Smell:** Multiple consumers independently implement the same discovery, normalization, fallback, or authority-selection logic.

**Example:** Every repository creates its own provider client plus mirror logic.

**Repair:** Count repetition as upstream-contract evidence. Move shared behavior to the owner; leave thin consumer adapters.

### 5. Invisible contract

**Smell:** The right seam exists, but fresh consumers cannot find it reliably.

**Example:** The canonical resolver is buried in an internal scripts directory and root governance never points to it.

**Repair:** Root wayfinding must expose owner, contract, normal invocation, and proof ceiling.

### 6. Cache becomes authority

**Smell:** A cache, mirror, vendored dependency, or generated artifact quietly becomes editable canonical truth.

**Example:** A downstream registry snapshot is edited locally and later treated as authoritative.

**Repair:** Mark derived artifacts as pinned/generated, preserve source provenance, and route mutations to the canonical owner.

### 7. Interface-only repair

**Smell:** A clean new upstream interface lands, but old downstream workarounds remain.

**Example:** A stable catalog is added while custom registry traversal and fallback code remains active in the consumer.

**Repair:** Migrate a real consumer, delete the obsolete implementation, and add regression tests preventing reintroduction.

### 8. False portability

**Smell:** The owner repository calls a boundary reusable, but every test runs with the full owner source tree present.

**Example:** Consumer tests import owner internals and never prove the advertised artifact is sufficient.

**Repair:** Use an isolated consumer with only the published interface/artifact.

### 9. Provider detail leakage

**Smell:** Every consumer must understand transport/auth/provider-specific failure behavior.

**Example:** Each repo independently handles the same provider token-scope fallback.

**Repair:** Terminate provider behavior at the adapter/upstream owner and expose stable failure states.

### 10. Ownership label as proof

**Smell:** Architecture review stops after saying “repository X owns this.”

**Example:** No one checks consumer knowledge, discoverability, duplicate workarounds, or isolated portability.

**Repair:** Run the entire checklist. Ownership is one gate, not the conclusion.

## Cross-domain anti-pattern examples

The doctrine is intentionally broader than repositories or prompt systems.

| Domain | Leaky seam | Healthy repair |
| --- | --- | --- |
| Scheduler | Every consumer must know provider task IDs, storage internals, and retry-object layout. | Expose a stable job/trigger contract and keep provider task topology behind the scheduler owner. |
| Data layer | Consumers query raw owner tables and encode migration-era column names. | Publish a stable dataset/query contract or view; keep storage schema and migrations behind the data owner. |
| Package/library | Consumers import private modules because the public entry point omits required behavior. | Promote the missing capability to a supported public interface and block private-module imports in consumers. |
| Generated artifacts | Consumers edit generated files because canonical source/generator ownership is unclear. | Make source, generator, output, provenance, and refresh command explicit; consumers depend on the generated contract, not generator internals. |
| Provider bridge | Each repo implements the same auth fallback, pagination, rate-limit, and error translation. | Terminate provider behavior in one adapter and expose stable provider-neutral results/failures. |
| Repository convergence | Consumers hard-code the old repository name/path as the API identity. | Bind to a semantic contract/version and resolve the current repository/path as a locator. |
| CLI/tooling | Users must memorize command ordering and hidden environment setup to reach a reusable operation. | Publish one stable executable entry point with explicit inputs, failure states, and receipts. |
| Agent harness | Fresh agents reconstruct ownership from search/history because no root pointer identifies the canonical seam. | Put canonical owner, invocation, contract, and proof ceiling in root wayfinding and test discoverability. |

## Holistic repair sequence

When a seam fails:

1. establish the true owner;
2. define the normal consumer's minimal inputs/outputs;
3. move topology, authority selection, routing, and provider internals behind the owner;
4. publish one stable machine-readable interface/distribution artifact;
5. preserve source/version provenance without making topology part of the API;
6. migrate one real representative consumer;
7. run isolated-consumer normal and edge-case canaries;
8. delete compensating downstream machinery;
9. add regressions preventing obsolete paths from returning;
10. roll the proven pattern outward.

The important step is **#8**. A repair that leaves the old workaround alive creates two paths and invites future agents to resurrect the wrong one.

## Isolated Consumer Canary

A boundary is not proven reusable until a consumer can succeed with **only the advertised interface/artifact**.

The canary should remove or withhold:

- upstream source tree;
- donor checkout;
- internal registries;
- migration history;
- privileged model/chat memory;
- implementation-only configuration.

Then prove at least:

- one representative normal case;
- one meaningful edge/retained case;
- expected failure behavior;
- provenance/version visibility;
- absence of forbidden upstream-internal knowledge in consumer code.

## Review output

Record:

```text
Owner:
Semantic contract:
Normal consumer input:
Normal consumer output:
Consumer knowledge required:
Leaked implementation details:
Discoverability path:
Repeated downstream workarounds:
Distribution/interface artifact:
Isolated consumer canary:
Obsolete workaround removal:
Result:
Proof ceiling:
```

Valid result states are defined in the machine-readable contract. Do not convert an unresolved owner, missing consumer contract, or unproven portability claim into PASS.
