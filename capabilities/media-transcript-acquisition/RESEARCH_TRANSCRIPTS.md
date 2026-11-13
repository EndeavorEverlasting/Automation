# Local-first research transcripts

Owner: Automation / media-transcript-acquisition. Contract: automation.research-transcript/v1.

## Operator command

From Automation's repository root on Python 3.11+ install optional caption adapters as needed:

    py -3 -m pip install youtube-transcript-api 'yt-dlp[default]'
    py -3 capabilities/media-transcript-acquisition/transcribe.py --url 'https://www.youtube.com/watch?v=pl0EltNU5p0'

The sample URL is not a claim of live-provider success. One successful command writes a new private folder inside Downloads/Automation-Transcripts. The CLI returns JSON with status, receipt, and document (when acquired). Run files are unique; no successful previous file is overwritten. Outside-Git output is mandatory.

Files:
- transcript.txt: actual normalized caption/ASR cue text, stable cue IDs, timestamps.
- transcript.html: escaped, clickable links to exact source video timestamps. Open with LibreOffice Writer and save as ODT or DOCX.
- quality-review.json: review flags and honest assurance NOT_INDEPENDENTLY_VERIFIED.
- development-notes.md: empty source-citation worksheet for verified development research, never an invented AI interpretation.
- receipt.json: source, adapter attempts, exact cues, SHA-256 file hashes, proof ceiling.

Windows PowerShell launch only on success:

    $r = py -3 capabilities/media-transcript-acquisition/transcribe.py --url 'https://www.youtube.com/watch?v=pl0EltNU5p0' | ConvertFrom-Json
    if ($r.status -ne 'TRANSCRIPT_ACQUIRED') { throw "Transcript unavailable: $($r.receipt)" }
    Start-Process $r.document

## Quality and fallback

Captions are primary evidence using the already-owned acquire.py adapters. This tool does not fabricate words or summaries. It validates cue ordering, nonempty text, bounded size, timestamps, and surfaces suspicious gaps, overlaps, adjacent repeats, non-speech markers and very short transcripts. No flags means UNVERIFIED_TRANSCRIPT, not verified accuracy. Flags result in REVIEW_REQUIRED. Check code, equations, terminology, demos and speaker identities against the actual original video; this workflow cannot observe video-only content.

Opt-in local ASR uses existing faster-whisper adapter with local_files_only=True. Independently provision a model and faster-whisper; no automatic model download. FFmpeg and yt-dlp are required only if optional audio capture is requested. Example with already available local model:

    py -3 capabilities/media-transcript-acquisition/transcribe.py --url 'https://www.youtube.com/watch?v=pl0EltNU5p0' --asr-model medium --compare-asr

When captions are accessible, they remain primary; --compare-asr flags suspicious time windows where independent ASR disagrees lexically. This is not an accuracy/confidence score and neither version is automatically corrected. If no captions are accessible, --asr-model enables an opt-in local ASR fallback when audio is accessible. You can supply owned local audio with --media-file instead of remote capture. No model, captions or audio access means BLOCKED with typed failure, not a fake transcript.

Downloaded audio is bounded by --max-audio-mb (default 128) and a timeout; deleted after processing unless --retain-audio is selected. Cleanup failure is recorded. User-provided local media is never deleted.

## Cloud optional; privacy and proof

No Google account, cloud upload, premium API, cookies or credentials needed. To make a Google Doc, manually upload the generated HTML or a LibreOffice-converted DOCX to Google Drive. Automated Google Doc publication is not implemented and requires a separately authorized adapter. Keep receipts, raw media and local transcripts out of Git.

Test with:

    python -m unittest discover -s capabilities/media-transcript-acquisition/tests -p 'test_*.py' -v

Offline tests exercise export fidelity, link escaping, hashes, blocked caption sources, ASR fallback with operator-owned media, and review flags. They are not evidence of live YouTube access, ASR word error rate, desktop open behavior or the factual validity of any technical claim. Runtime certification requires an authorized host, successful provider capture, representative audio-to-text spot checking and protected regression replay.

Seam: the consumer needs URL, optional local VTT/SRT/audio file, an opt-in locally present ASR model and output folder only. Automation owns provider adapter orchestration and normalized source evidence; downstream applications can consume citation IDs and notes without learning MoonWake's prompt layout or copying this machinery.
