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

## Status

No live provider adapter is admitted in this repository yet. Synthetic fixtures
under `fixtures/` prove the core/adapter seam without authenticated runtime
dependency.
