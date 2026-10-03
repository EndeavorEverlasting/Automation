# Playlist Link Extraction Capability

**Capability ID:** `playlist-link-extraction`  
**State:** `BOUNDARY_DEFINED_IMPLEMENTATION_PENDING`

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

Only the **boundary** is admitted here. The earlier playlist extractor prototype has not yet been integrated into this repository under this contract, so implementation, adapter parity, runtime behavior, and production use remain unproven.
