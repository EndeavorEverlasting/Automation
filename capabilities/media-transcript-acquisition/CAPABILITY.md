# Media transcript acquisition — capability contract

**Identity:** `automation.media-transcript-evidence/v1`
**Ownership:** Automation reusable content evidence core; provider-specific retrieval is optional. TokenCorridor decides interpretation, source corroboration, planning, prompting and action authority.
**Status:** candidate implementation; synthetic and CI gates required. Live provider availability is NOT proven.

## Motivation
Video citations should be grounded in the actual source text, not a title, synthesized interpretation, a previous chat summary or a failed-fetch assumption. The consumer must not depend on one ChatGPT runtime, premium API, web tool, or locally installed utility. Fallbacks are *qualified options*, not universal guarantees.

## API
Run the standalone Python 3.11+ script using only the standard library for offline caption ingestion:

```shell
python capabilities/media-transcript-acquisition/acquire.py --url https://www.youtube.com/shorts/pl0EltNU5p0 --captions-file /private/transcript.vtt --strategy offline --out /private/transcript-evidence.json
```

For network acquisition, default `--strategy auto` tries optional `youtube-transcript-api` (current API `YouTubeTranscriptApi().fetch(video_id)`) followed by the existing proven `yt-dlp` subtitle command machinery. It does not install these dependencies, attach browser cookies, select proxies, defeat provider access restrictions, download video media, or silently call a paid service. Provider access can be denied or captions genuinely unavailable.

Receipt: `contract`, `status`, `source.provider` + `source.video_id` for valid sources, `method`, `attempts`, `cues[{start_ms,end_ms,text}]`, optional `input_sha256`, `proof_ceiling`.
- `TRANSCRIPT_ACQUIRED`: text was obtained (this does not prove speaker identity, factual accuracy or video frame contents); exit 0.
- `UNRESOLVED_SOURCE_ACCESS`: available adapters exhausted; do NOT infer captions don't exist; exit 2.
- `SOURCE_NOT_ATTACHED`, `INVALID_CAPTIONS`, `INVALID_SOURCE`: explicit prerequisites failed; exit 2.
- Per-adapter typed outcomes: `ADAPTER_UNAVAILABLE`, `PROVIDER_BLOCKED`, `PROVIDER_TIMEOUT`, `CAPTIONS_UNAVAILABLE`, `PROVIDER_ERROR`. The final unresolved state takes precedence unless externally certified otherwise.

Writes only the specified local JSON file; it contains transcript text and is potentially sensitive. **Never commit raw/private transcripts, receipts, cookies, sessions or local paths to public Git.** No network in CI. The core does not authorize provider access, data publication, user impersonation, audio capture, or mutation.

## Runtime independence
Observed current chat environment may expose GitHub and public search but lack YouTube multimedia reachability. A local agent with an approved network stack can run exactly the same CLI and report its typed receipt to TokenCorridor. When neither caption provider works, a human-supplied export can be normalized locally; in a later independently authorized extension, an owned local audio file could run a pinned, licensed offline ASR model.

**Unavoidable boundary:** A URL alone cannot guarantee a transcript. A private/restricted/deleted video or a source with no accessible captions/media may require user authorization or input. Do not claim that a workflow is robust when it silently fabricates text.

## P97 prior-art dispositions
- Internal playlist-link-extraction / yt-dlp-json: **ADAPT** transport/fixture/provenance discipline; transcript is separate operation and schema.
- [yt-dlp](https://github.com/yt-dlp/yt-dlp): **ADOPT** bounded subtitle options; no internal downloader rewrite.
- [youtube-transcript-api](https://github.com/jdepoix/youtube-transcript-api): **ADAPT** optional first adapter with blocked/IP-limited outcome.
- [faster-whisper](https://github.com/SYSTRAN/faster-whisper): **DEFER** local ASR benchmark and explicit model/audio permissions.
- Unverified paid scraping services, cookie injection, fabricated transcript: **REJECT**.

## P82 measured prototype
Hypothesis: the standalone CLI parses timestamped SRT/VTT from a known local fixture and routes upstream failures without needing the caller's ChatGPT toolset. Falsifier: failure to run with Python-only environment, failure to preserve caption timestamps, accidental leakage of paths/exception text, or false `CAPTIONS_UNAVAILABLE` when access was blocked.
Run `python -m unittest discover -s capabilities/media-transcript-acquisition/tests -v`. A successful synthetic test is not proof of real YouTube access.
**Current production/use path:** `UNDECLARED`. **First real-provider gate:** authorized host/source, observed successful direct caption call, provenance + version recorded, and replay test. **Next optional gate:** local audio-to-text ASR, separately measured.
