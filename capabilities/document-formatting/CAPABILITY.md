# Document Formatting

Status: **COMPILER_IR_PROTOTYPE_PROVEN_GOOGLE_DOCS_PLAN_ADAPTER_PROVEN**

`document-formatting` is the reusable owner for deterministic document-formatting orchestration across repositories and projects.

A consumer supplies its own profile: archetypes, style/token contract, provider requirements, visual-acceptance surfaces, and branding policy. Automation owns the portable lifecycle, validation rules, execution placement metadata, proof-state ordering, and provider-neutral plan receipt.

## Ownership boundary

Automation owns:

- the consumer-profile contract;
- deterministic profile validation and hashing;
- provider-neutral stage/dependency construction;
- runtime placement carried as typed execution environments;
- proof-state ordering and anti-promotion rules;
- the rule that branding cannot precede the consumer's generic/non-color lock when that policy is enabled;
- machine-readable plan receipts.

Consumers own:

- domain/project-specific visual tokens and branding;
- artifact archetypes and required sections;
- private/provider identities and credentials;
- provider-specific content and business rules;
- operator-approved exemplars and visual evidence;
- local adapters that are genuinely consumer-specific.

Provider adapters may live here when they are reusable across consumers. A consumer must not fork the reusable core merely to change its profile.

## Smallest portable operation

```text
consumer profile
  -> validate portable contract
  -> canonical profile SHA-256
  -> build provider-neutral execution/acceptance graph
  -> emit document-formatting-plan/v1
  -> consumer/provider executors perform their owned stages
  -> stronger proof states are established only by their own evidence
```

The current implementation does **not** mutate Google Docs, Word, PDFs, or any other provider. It makes the ownership and execution contract deterministic so adapters can be added without contaminating the core.

## Consumer Knowledge Test

A normal consumer needs only:

1. the `document-formatting-consumer-profile/v1` schema;
2. its own semantic contract/profile reference;
3. the providers/features it requires;
4. the visual surfaces that must be accepted;
5. its proof/branding policy.

It does **not** need to know which repository originally discovered the formatting problem, donor branch history, H&H-specific paths, or another consumer's tokens.

## Run the synthetic canary

```powershell
python capabilities/document-formatting/plan.py \
  --profile capabilities/document-formatting/fixtures/consumer-profile.synthetic.v1.json \
  --output Outputs/document-formatting-plan.json
```

## Proof ceiling

The executable core proves portable profile validation, canonical hashing, stage ordering, runtime-placement preservation, and branding/proof guards using synthetic consumers.

Provider mutation, visual fidelity, dynamic page fields, Microsoft Word/Office rendering, Google Docs readback, consumer adoption, deployment, and production use are separate proof states.


## P95 compiler and adapter prototype

The next reusable seam is now executable:

```text
semantic source + consumer design spec
  -> document-formatting compiler
  -> provider-neutral IR + fingerprints + receipt
  -> provider adapter capability negotiation
  -> provider-specific phased operation plan
  -> live transport/readback (successor build work)
```

Compile the synthetic consumer:

```powershell
python capabilities/document-formatting/compile.py \
  --source capabilities/document-formatting/fixtures/document-source.synthetic.v1.json \
  --design capabilities/document-formatting/fixtures/design-spec.synthetic.v1.json \
  --output Outputs/document-formatting-ir.json \
  --receipt Outputs/document-formatting-compiler-receipt.json
```

Build the Google Docs plan:

```powershell
python capabilities/document-formatting/adapters/google_docs.py \
  --ir Outputs/document-formatting-ir.json \
  --required-feature semantic_headings \
  --required-feature internal_navigation \
  --required-feature named_external_links \
  --required-feature inline_images \
  --required-feature revision_readback \
  --output Outputs/document-formatting-google-docs-plan.json
```

The Google Docs adapter is deliberately two-phase for internal navigation: construct/style first, read back heading identities, then bind internal links against the observed provider structure. It also fail-closes when a consumer requires an unsupported feature.

Current Google Docs API evidence exposes page-number/page-count AutoText in read resources but no batchUpdate request that creates AutoText. Therefore `dynamic_page_fields` remains a typed unsupported creation capability rather than being approximated with static text.

This P95 slice prototypes architecture. It does not claim live Google Docs mutation or visual fidelity.
