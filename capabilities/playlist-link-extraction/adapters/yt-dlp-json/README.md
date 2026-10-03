# yt-dlp-json adapter

**Adapter ID:** `yt-dlp-json`

**Proof ceiling:** offline provider-payload → observation-batch transformation only.

Converts captured or synthetic yt-dlp-style playlist JSON into
`playlist-link-observation-batch/v1` for the reusable playlist-link-extraction
core. It does **not** run `yt-dlp`, open a network session, or own
normalization/deduplication.

## Invocation

```powershell
python capabilities/playlist-link-extraction/adapters/yt-dlp-json/adapt.py `
  --payload capabilities/playlist-link-extraction/adapters/yt-dlp-json/fixtures/sample-playlist.v1.json `
  --target-id target-a `
  --output-batch Outputs/playlist-link-observation-batch.json

python capabilities/playlist-link-extraction/extract_links.py `
  --batch Outputs/playlist-link-observation-batch.json `
  --output-json Outputs/playlist-link-artifact.json `
  --output-csv Outputs/playlist-link-artifact.csv
```

## Ownership

- Owns: provider payload validation, entry URL selection, ordinal assignment, adapter_data namespacing.
- Does not own: URL normalization, uniqueness, canonical artifacts, CSV projection, live extraction.

## Status

Offline fixture proof is admitted. Live `yt-dlp` execution, authenticated
extraction, browser profiles, and production use remain unproven.
