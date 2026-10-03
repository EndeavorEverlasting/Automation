# Playlist Link Extraction Adapters

Adapters feed normalized observations into the reusable core. They do **not**
own URL identity, occurrence/uniqueness semantics, or canonical artifact shape.

## Contract

1. Emit a `playlist-link-observation-batch/v1` JSON batch.
2. Put provider-specific facts under `adapter_data`, never into core identity fields.
3. Keep cookies, tokens, browser profiles, and session stores outside source control.
4. Invoke the core through:

```powershell
python capabilities/playlist-link-extraction/extract_links.py `
  --batch <observation-batch.json> `
  --output-json <artifact.json> `
  --output-csv <projection.csv>
```

## Admitted adapters

### `yt-dlp-json` (offline)

Path: `adapters/yt-dlp-json/`

Converts captured/synthetic yt-dlp-style playlist JSON into an observation batch.
Proof ceiling: offline transformation only. Live `yt-dlp` execution,
authenticated extraction, browser profiles, and production use remain unproven.

```powershell
python capabilities/playlist-link-extraction/adapters/yt-dlp-json/adapt.py `
  --payload capabilities/playlist-link-extraction/adapters/yt-dlp-json/fixtures/sample-playlist.v1.json `
  --target-id target-a `
  --output-batch Outputs/playlist-link-observation-batch.json
```

## Status

One offline provider adapter is admitted: `yt-dlp-json`. No live network or
authenticated provider adapter is admitted yet. Synthetic core fixtures under
`fixtures/` remain available for provider-agnostic core proof.
