# Repository Prompt Runtime

Automation is a downstream consumer of **`prompt-invocation-upstream/v1`**.

It does not know how Prompt Kit registries are composed, where retained prompts live, or how prompt authority is migrated. Those are upstream concerns.

## Normal use

```powershell
python scripts/prompt_runtime.py --text "invoke & implement P92"
```

Automation's wrapper loads the pinned upstream resolver and catalog from:

```text
vendor/prompt-invocation-upstream/
  manifest.v1.json
  contract.v1.json
  catalog.v1.json
  prompt_invocation_resolver.py
```

The result packet comes from the upstream resolver and includes exact prompt identity, intent, prompt body, canonical source provenance, and implementation intent.

## Dependency provenance

`vendor/prompt-invocation-upstream/manifest.v1.json` records:

- upstream repository;
- exact upstream commit;
- upstream contract identity;
- source blob SHA for every vendored dependency file.

The contract, catalog, and resolver are refreshed **as one unit** from one proven upstream commit.

The current pin is a dependency version, not a claim that no newer upstream commit exists.

## Ownership boundary

Automation owns:

- invoking the pinned upstream interface;
- applying the resolved workflow to Automation's local context;
- local implementation and proof.

Automation does **not** own:

- prompt registry discovery;
- Prompt Kit product-boundary traversal;
- retained Triage routing;
- prompt creation/admission/retirement;
- canonical prompt mutation;
- a competing prompt cache format.

If a prompt itself must be changed, route that mutation to the upstream prompt owner.

## Failure semantics

Unknown/conflicting P-numbers fail closed according to the upstream resolver. Automation must not repair an upstream lookup failure by guessing from model memory.

## P92 path preflight

P92 remains a local workflow once resolved upstream. Before path-sensitive mutation run:

```powershell
python scripts/path_receipt.py --repo-root . --output Outputs/path-receipt.json
```

Remote integration, local checkout freshness, production freshness, and entrypoint proof remain separate states.
