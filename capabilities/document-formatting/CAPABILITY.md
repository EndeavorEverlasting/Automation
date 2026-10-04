# Document Formatting

Status: **CORE_IMPLEMENTED_PROVIDER_ADAPTERS_PENDING**

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
