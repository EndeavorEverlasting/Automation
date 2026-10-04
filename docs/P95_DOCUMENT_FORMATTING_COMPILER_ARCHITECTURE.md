# P95 — Document Formatting Compiler & Provider Adapter Architecture

Status: **P95 EXECUTABLE PROTOTYPE / PROVIDER EXECUTION UNPROVEN**  
Date: 2026-10-03  
Repository: `EndeavorEverlasting/Automation`  
Program: `document-formatting`

## User outcome

A consuming repository supplies semantic document content plus a declarative design/profile contract. Automation deterministically constructs the document semantics once, then provider adapters translate the same IR without re-deciding navigation, resources, semantic roles, or proof-state rules.

Consumers do not need donor repositories, H&H paths, chat memory, or provider internals.

## Evidence floor

- Automation owns the reusable `document-formatting` capability.
- NYC H&H is the first real consumer and retains its project-specific tokens/archetypes/evidence.
- H&H PR #51 and #47 are donor evidence only.
- The donor compiler proved useful invariants: deterministic semantic compilation, compiler-owned navigation, named resource links, typed failures, component requirements, and independent content/structure/non-color/palette fingerprints.
- The donor implementation was rejected as a direct port because it imports H&H contracts and repository paths as runtime dependencies.

## Candidates compared

| Candidate | Result | Reason |
| --- | --- | --- |
| Consumer-code import/plugin compiler | REJECTED | Makes Automation depend on consumer repository topology and executable consumer code. |
| Provider adapter compiles raw semantic source | REJECTED | Each provider would duplicate navigation, resource, archetype and fingerprint decisions. |
| Declarative design spec → provider-neutral IR → adapters | **SELECTED** | One semantic owner, portable data contract, provider-specific behavior terminates at adapters, easy success/failure testing. |
| Fully generic free-form document AST | DEFERRED | More abstraction than current evidence requires; would weaken enforceable semantic roles without a proved need. |

## Domain vocabulary

- **Consumer profile** — runtime/provider/acceptance placement contract already owned by `document-formatting-consumer-profile/v1`.
- **Design spec** — declarative consumer-owned archetypes, semantic roles, palette and non-color mechanics.
- **Document source** — semantic authoring input. Navigation is not caller-authored.
- **Compiler** — validates source/spec and emits deterministic provider-neutral IR.
- **IR** — ordered semantic blocks with resolved role styling and independent fingerprints.
- **Provider adapter** — translates IR into provider-specific phased operations and negotiates required features.
- **Transport** — performs actual provider mutation/readback. Not implemented by this P95 slice.
- **Visual acceptance** — independently observed render proof. Never inferred from compilation, plan generation, or provider readback.

## Ownership and dependency direction

```text
CONSUMER
  |-- consumer profile
  |-- design spec
  |-- semantic document source
  v
AUTOMATION document-formatting core
  -> validate source + design
  -> generate navigation/resources/roles
  -> derive content/structure/non-color/palette fingerprints
  -> provider-neutral IR + compiler receipt
  v
PROVIDER ADAPTER
  -> capability negotiation
  -> provider-specific phased operation plan
  v
TRANSPORT / PROVIDER
  -> mutation
  -> readback
  v
VISUAL / OPERATOR ACCEPTANCE
```

No arrow points back into the consumer to discover core behavior.

## Success call stack

```text
CLI compile.py
  -> core.compiler.compile_document
  -> validate_design_spec
  -> validate_source
  -> compiler-owned navigation/resource construction
  -> fingerprint derivation
  -> document-formatting-ir/v1 + compiler receipt
  -> adapters/google_docs.py build_plan
  -> capability_report
  -> CONSTRUCT_AND_STYLE
  -> RESOLVE_HEADING_IDENTITIES
  -> APPLY_INTERNAL_LINKS
  -> FINAL_READBACK
  -> document-formatting-google-docs-plan/v1
```

Terminal value for this P95 slice: an executable, deterministic provider-neutral compiler seam plus a provider adapter plan that no consumer must reimplement.

## Consequential failure stacks

### Semantic rejection

```text
source
  -> validate_source
  -> raw URL / missing resource / missing section component / duplicate identity
  -> DocumentCompileError(code)
  -> CLI exit 2
```

### Provider capability rejection

```text
IR + required features
  -> google_docs.capability_report
  -> unsupported capability detected
  -> GoogleDocsAdapterError(GDA_UNSUPPORTED_FEATURE)
  -> no provider plan emitted
```

`dynamic_page_fields` intentionally takes this path today.

## Google Docs adapter model

Internal navigation cannot be treated as a one-shot precomputed mutation because heading identities are provider-owned. The prototype therefore uses:

1. `CONSTRUCT_AND_STYLE` — content/style plan under revision control.
2. `RESOLVE_HEADING_IDENTITIES` — provider readback.
3. `APPLY_INTERNAL_LINKS` — bind links against observed heading identities under revision control.
4. `FINAL_READBACK` — provider evidence boundary.

This is deeper than a direct `source -> batchUpdate` mapper because it hides volatile provider identity mechanics behind the adapter.

## Dynamic page-field boundary

Google Docs resources expose AutoText types `PAGE_NUMBER` and `PAGE_COUNT`, but the current public batchUpdate Request surface does not expose an AutoText insertion request.

Therefore:

`dynamic_page_fields = READABLE_EXISTING_NOT_CREATABLE_VIA_CURRENT_BATCHUPDATE_SURFACE`

A provider adapter must fail closed when a consumer requires creation of dynamic page fields. Static footer text is not equivalent proof.

## State model

```text
SOURCE_VALID
  -> COMPILED_PROVIDER_NEUTRAL_DOCUMENT
  -> ADAPTER_PLAN_READY
  -> PROVIDER_MUTATION_ATTEMPTED       [successor]
  -> PROVIDER_READBACK_VERIFIED        [successor]
  -> VISUAL_ACCEPTED_ON_SURFACE        [successor]
  -> CROSS_SURFACE_FIDELITY_ACCEPTED   [successor]
```

No weaker state promotes itself to a stronger one.

## Second-pass critique

Prototype evidence changed the initial design in three ways:

1. **Images became a first-class source/IR block.** The accepted evidence-packet consumer requires this; hiding images in provider code would leak archetype semantics.
2. **Internal links became explicitly multi-phase.** Provider heading identities are not safely precomputable.
3. **Palette and non-color mechanics remain separate data owners.** This preserves the existing generic-lock-before-branding contract and lets consumers change color without accidentally proving geometry stability.

## Proof ceiling

Proven by this P95 slice once CI is green:

- provider-neutral compiler interface;
- deterministic IR/receipt for identical inputs;
- typed semantic failures;
- generated navigation and named resources;
- image/table/list semantic preservation;
- independent content/structure/non-color/palette fingerprints;
- Google Docs capability negotiation;
- two-phase internal-link provider plan;
- fail-closed dynamic-page-field capability handling;
- no H&H-specific assumptions in reusable core/adapter.

Not proven:

- actual Google Docs mutation/readback;
- real heading-ID resolution;
- dynamic page-field creation;
- Word/Office generation or rendering;
- visual fidelity;
- H&H consumer adoption of this exact compiler revision;
- deployment or production use.

## Build seam ready for P07

P07 may harden the schemas and implement real Google Docs transport/readback behind the existing adapter plan without moving compiler decisions into the adapter. If a provider lacks a required feature, the adapter reports the capability gap; it does not approximate the feature silently.
