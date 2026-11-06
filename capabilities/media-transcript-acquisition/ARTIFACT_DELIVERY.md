# Local social-media media artifact delivery

Contract: **automation.media-artifact-delivery/v1**. Owner: **capabilities/media-transcript-acquisition/**.
Purpose: user-authorized, accessible HTTPS social video URLs → private host video, MP3 audio, or both plus a SHA-256 JSON receipt.

## CLI on the host

Install Python 3.11+, current yt-dlp, and FFmpeg for all capture modes (including video stream merging). Clone does not install or start anything.

    python capabilities/media-transcript-acquisition/deliver_artifact.py --url "https://www.youtube.com/shorts/pl0EltNU5p0" --mode video --output-dir "$env:LOCALAPPDATA\Automation\MediaDelivery"
    python capabilities/media-transcript-acquisition/deliver_artifact.py --url "https://www.youtube.com/shorts/pl0EltNU5p0" --mode hybrid --output-dir "$env:LOCALAPPDATA\Automation\MediaDelivery"

Modes: video = video file, audio = MP3 via yt-dlp + FFmpeg, hybrid = one downloaded video plus FFmpeg-extracted MP3. Each successful run creates a unique private media-* folder with receipt.json and one or two role-named files. Each file has relative filename, byte count and SHA-256 in the receipt. CLI exit 0 = DELIVERED; exit 2 = BLOCKED. Blocked runs leave failed-*.receipt.json, but no promoted media folder.

## Boundary and failure behavior

- HTTPS origin validation and provider normalization reuse social_insights.normalize_source (YouTube, Instagram, TikTok, Facebook, X, Reddit, Vimeo, LinkedIn). Provider recognition is NOT live extractor certification.
- The downloader uses yt-dlp with ignore-config, no playlist, no remote components, bounded retries, socket timeout, file size cap, and no cookies/browsers/auth flows. No DRM/CAPTCHA/paywall bypass or account scraping. Only access and reuse material you are authorized to download; honor platform terms.
- Output must be outside Git. A private staging directory is promoted only after valid nonempty file and SHA-256 verification. Failed staging is deleted. External process stdout/stderr is suppressed; no secrets or provider errors are persisted.
- No shell, hidden Windows child process flags, closed stdin, no scheduler installation, no upload, no proxy, no provider token, no cross-boundary transport. Scheduled/fullscreen silence requires separate local certification.
- --max-mb default 500, allowed 1–2048; --timeout default 300 seconds, allowed 10–900. The size cap is checked after download too; an in-progress failed download can still consume temporary disk.
- All capture modes require FFmpeg for consistent video/audio merging and postprocessing. Real codecs and streams may vary and fail; no guarantee of universal access or archival quality.
- Statuses include YTDLP_UNAVAILABLE, FFMPEG_UNAVAILABLE, PROVIDER_OR_PROCESS_ERROR, PROCESS_TIMEOUT, MEDIA_NOT_PRODUCED, ARTIFACT_TOO_LARGE, EMPTY_ARTIFACT, AUDIO_EXTRACTION_FAILED, OUTPUT_INSIDE_REPOSITORY and invalid-source/limit states.

## P97 prior-art and solved-base disposition

- ADOPT: [yt-dlp](https://github.com/yt-dlp/yt-dlp) extractor plus FFmpeg postprocessing, already used by Automation's social insights and transcript adapters. No rewrite of scraping mechanics.
- ADAPT: [Instaloader](https://github.com/instaloader/instaloader/blob/master/instaloader/__main__.py) for potential Instagram profile/post/image extensions; its login and session behavior are out of this authorized public URL slice.
- DEFER: [Cobalt](https://github.com/imputnet/cobalt) as a server-based alternative; no new service, proxy, API, network deployment or license obligation is warranted for local host file delivery.
- ALREADY SOLVED INTERNALLY: source URL normalization, transcripts, social-media evidence/ASR/vision, Windows silent scheduling. PROJECT-SPECIFIC GAP addressed: user-facing selected video/audio/hybrid artifact files plus stable receipt.
- EVIDENCE GAP: actual accessible YouTube/Instagram media, provider-format coverage, real Windows host codec/silence proof.

## P141 / P08 / P82 / P07 / P04

P141 competing theses: (1) reusable host artifact output SURVIVES (direct user pull + existing analysis-only adapter); (2) building provider-specific scraping engine WEAKENED (yt-dlp already solves transport); (3) a new scheduler REJECTED (Automation already owns one); (4) expanding ML inference DEFERRED (different downstream capability). Selected thesis is the missing local artifact-delivery seam. P82 falsifier: failed normal/blocked/oversize synthetic tests or isolated consumer CLI test. P08 live provider and host observation remain unproved. P07 owns implementation/verification, P04 owns the structured handoff.

## Verification and host acceptance

    python -m unittest discover -s capabilities/media-transcript-acquisition/tests -p 'test_*.py' -v

Existing media CI executes on Python 3.11/3.12. Synthetic consumer canary invokes the advertised CLI using a fake external downloader: no network/real provider certification.

To certify locally, record interpreter, yt-dlp and FFmpeg versions; run one authorized accessible YouTube URL and Instagram Reel separately in each desired mode, check output plays, inspect codecs/durations/hashes and directory permission; record typed access denial when blocked. Compare hash against receipt and confirm child process/window behavior when unattended. Do not upload private media or receipts to public Git. Opt-in Windows Task Scheduler only after separate explicit operator approval and silent full-chain certification.

## Seam review

Owner: Automation media-transcript-acquisition. Consumer knows only URL, mode, a private output directory, installed optional binaries and the versioned receipt. It does not depend on TokenCorridor internals, private topology or provider credentials. Existing acquire.py/social_insights.py and scheduler remain canonical and unchanged. Proof ceiling: source-level implementation and offline CI only until provider/host observed.
