# Public Repository / Private Continuity Boundary

Automation is public. A private continuity store may help the operator plan or incubate Automation work, but the public repository must remain independently usable.

## One-way default

Private continuity may point **outward** to public Automation commits, pull requests, releases, paths, and semantic contracts.

Automation must not require or publish a backlink to the operator's private continuity store.

A normal consumer should never need private operator context to use a public Automation capability.

## Public-safe material

Tracked Git artifacts may contain:

- reusable code and public schemas;
- semantic contract identities;
- sanitized examples and synthetic fixtures;
- provider-neutral error states;
- repository-relative paths;
- public commit/PR/release provenance;
- explicit descriptions of required private runtime inputs without their values.

## Private material

Do not commit:

- private continuity-store URLs or file/folder IDs;
- personal/client records or unpublished content;
- private provider/account locators;
- credentials, tokens, cookies, authenticated browser state, or browser-profile paths;
- private operator topology;
- absolute person-specific workstation paths.

The runtime handoff validator enforces a minimum tracked-packet privacy floor.

## Sanitization path

Use this transition:

```text
private context
  -> classify the reusable behavior
  -> replace private locators with semantic inputs
  -> isolate provider/account behavior behind adapters or runtime inputs
  -> build synthetic fixtures
  -> validate the public contract
  -> commit public code/docs/tests
```

Keep the private locator-to-semantic mapping outside public Git.

## Git remains source control

Private continuity is not a second source tree.

If private notes and Git disagree about implementation facts, refresh repository/provider truth. Git owns code/history/contracts; private notes must be repaired to follow it.

## Capability incubation

Private incubation is useful before a boundary is admitted. The public repository receives the capability only after the contribution/admission gates in `CONTRIBUTING.md` are satisfied.

When an incubated capability becomes a product with its own persistent domain model, UI, release lifecycle, and independent ownership, the product should graduate to its own repository while continuing to consume stable Automation primitives.
