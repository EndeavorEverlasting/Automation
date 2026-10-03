# Playlist Link Extraction Capability

**Capability ID:** `playlist-link-extraction`  
**State:** `CORE_IMPLEMENTED_ADAPTERS_PENDING`

This is the first reusable capability boundary admitted under the Automation repository charter.

## Mission

Accept one or more playlist/page targets and produce deterministic, machine-readable link and ordered-membership artifacts. The capability may support specific providers through adapters, but its reusable core must not inherit the identity of one repository, browser profile, provider, or operator machine.

## Core boundary

The reusable core owns:

- target-list normalization;
- stable target/source provenance;
- URL/link normalization and deduplication;
- ordered occurrence versus unique entity separation;
- canonical JSON output;
- CSV projections generated from canonical JSON;
- batch aggregation;
- schemas, versioning, validation, and deterministic receipts.

The core does **not** own provider navigation, login/session mechanics, DOM selectors, or provider-specific metadata formats.

## Adapter boundary

Provider/runtime adapters may own:

- YouTube-specific page or playlist behavior;
- Playwright browser navigation and persistent-profile mechanics;
- `yt-dlp` extraction;
- provider-specific selectors, throttling, authentication, and failure translation.

Adapters feed normalized observations into the core. They must not redefine the canonical artifact shape or duplicate core deduplication/occurrence semantics.

See `adapters/README.md`.

### Admitted offline adapter: `yt-dlp-json`

```powershell
python capabilities/playlist-link-extraction/adapters/yt-dlp-json/adapt.py `
  --payload capabilities/playlist-link-extraction/adapters/yt-dlp-json/fixtures/sample-playlist.v1.json `
  --target-id target-a `
  --output-batch Outputs/playlist-link-observation-batch.json
```

## Invocation

```powershell
python capabilities/playlist-link-extraction/extract_links.py `
  --batch capabilities/playlist-link-extraction/fixtures/synthetic-observation-batch.v1.json `
  --output-json Outputs/playlist-link-artifact.json `
  --output-csv Outputs/playlist-link-artifact.csv
```

Machine-readable contracts:

- `schemas/observation-batch.v1.json`
- `schemas/artifact.v1.json`
- `capability.v1.json`

## Authentication and runtime state

Cookies, tokens, browser profiles, session stores, downloaded private data, and other authenticated runtime state remain outside source control.

A persistent browser profile is a runtime input, not repository state.

## Paths

Repository-relative development owner:

```text
capabilities/playlist-link-extraction/
```

No global production/use path is declared yet. A future launcher/install surface must define its production/use path and promotion boundary before it can claim deployment under P92.

## Current proof ceiling

The reusable **core** is implemented and proven with synthetic observation fixtures:

- URL normalization and stable identity;
- ordered occurrences including repeats;
- unique-link aggregation across targets;
- canonical JSON artifact + CSV projection;
- CLI validate/build entrypoint.

The offline **`yt-dlp-json`** adapter is implemented and proven with a synthetic
yt-dlp-style playlist fixture:

- provider payload validation fails closed;
- ordered membership is preserved, including repeats;
- observation batches feed the existing core without core schema changes.

Live `yt-dlp` execution, authenticated runtime extraction, browser-backed
extraction, and production use remain unproven. Capability status remains
`CORE_IMPLEMENTED_ADAPTERS_PENDING` because live provider use is still unproven.
