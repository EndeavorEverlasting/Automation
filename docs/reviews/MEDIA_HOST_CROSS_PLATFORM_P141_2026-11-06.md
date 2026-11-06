# P141 — Cross-platform host access strategic decision

Date: 2026-11-06. Repository: EndeavorEverlasting/Automation. Decision scope: make the existing authorized URL-to-local-file media capability usable by an ordinary Windows or Linux Mint user.

## Current evidence floor

- The merged automation.media-artifact-delivery/v1 engine already supports video/audio/hybrid, bounded yt-dlp capture, local artifacts, and SHA-256 receipts.
- The preexisting user workflow required invoking a Python source file with multiple flags, externally provisioning tools, and independently discovering receipt integrity commands.
- The single canonical owner is capabilities/media-transcript-acquisition; its social_insights.py and acquire.py are separate analysis/evidence contracts.
- Existing Windows silent Task Scheduler and local agent runtime governance own unattended execution. No new scheduler or cross-repo control plane should be created.
- This repository is public. Private source video, transcript, cookies, provider credentials and user-specific host paths must never be committed.

## Competing theses with falsifiers

| Thesis | Evidence and leverage | Alternative explanation / falsifier | Disposition |
| --- | --- | --- | --- |
| One cross-platform user shell + doctor + verifier | Current user explicitly wants Windows and Linux Mint use; existing delivery entrypoint is agent/CLI-oriented | If normal users can already launch and verify without new glue, UI is redundant | SURVIVES |
| Build bespoke provider-specific Instagram/YouTube extractors | More provider customization could increase coverage | yt-dlp owns transport and provider changes; duplication adds drift, credentials and larger attack surface | WEAKENED |
| Install a new background service or scheduler | Regular scraping could automate repeated capture | Existing Automation silent-scheduler contract already owns scheduled execution; user did not authorize live tasks | REJECTED |
| Expand ASR, video understanding and local-model deployment | Additional downstream value may follow capture | The request is to deliver host artifacts and the social-insights owner already exists | DEFERRED |
| Deliver a full desktop GUI or Electron product immediately | Could reduce command-line friction | More release, installer, UX and desktop-safety surface than the first usable slice; no measured baseline | DEFERRED |

## Selected thesis / decision

Use the existing Python acquisition owner as one shared engine; add only a portable terminal application with machine-readable read-only doctor and SHA-256 receipt verifier, plus thin Windows CMD and Linux Mint bash entrypoints. This is an additive consumer seam, not a new product authority.

Confidence: HIGH for reducing the command-discovery gap; MEDIUM for real host user success until Windows/Mint tool availability, desktop interaction and live media are observed.

## P82 experiment admission

- Hypothesis: a normal host consumer can check required tools, select a source and mode, obtain a local output, and reverify its hash with one platform-specific launcher and zero implementation-module knowledge.
- Baseline: direct deliver_artifact.py invocation requires explicit private destination and manual external tool readiness/integrity steps.
- Prototype boundary: host_app.py, two thin launchers, user guide, stable delivery contract reuse. No GUI, browser, scheduler, account access or new scraping backend.
- Measurement: Python 3.11/3.12 tests on Windows/Ubuntu, all-mode receipt verification, corrupted/blocked/path-traversal cases, native launcher smoke, positive/negative READY packet validation.
- Decision rule: PROMOTE if all cross-platform CI gates pass and shared API remains unchanged; WEAKEN if Windows/Linux flags or filesystem behavior fail; REJECT if portable solution requires credentials/remote service/new scheduler; INCONCLUSIVE if CI passes but real Mint and Windows hosts remain untested.
- P08 outcome ceiling: remote CI is a runtime for simulated tests, not interactive Windows/Linux Mint desktop or actual provider media.

## P07 executed bounded implementation scope

Owned: capabilities/media-transcript-acquisition/ and this strategy record; existing canonical handoff packet and its human-readable runbook; scoped media workflow test matrix; root wayfinding links. Forbidden: unrelated repos, upstream prompt registry, private media, live host accounts, Task Scheduler/cron, unrelated PR owners.

## Portable seam / isolated consumer

Normal consumer knows the repo checkout, platform launcher, URL, mode and output folder. Doctor and verify are stable CLI subcommands. The acquisition/receipt engine is imported by the host app; consumer scripts do not import provider internals. Synthetic subprocess and direct CLI verifier canaries prove the surface with no external provider. Real codecs and platform usability require separate local certification.

## Handoff and honest proof states

Canonical runtime packet: docs/handoffs/MEDIA_ARTIFACT_HOST_CERTIFICATION_2026-11-06.json. Human instructions: docs/handoffs/MEDIA_ARTIFACT_HOST_CERTIFICATION_2026-11-06.md. Windows and Linux Mint are separate certification dimensions. An Ubuntu CI pass cannot certify Mint desktop behavior, and a Windows GitHub runner cannot certify a particular local Windows 11 installation. P04 records both as pending until live observed.

## External reference mechanism

yt-dlp official release/installation documentation: https://github.com/yt-dlp/yt-dlp/wiki/Installation ; Python 3.11+ / ffmpeg / JavaScript runtime guidance: https://github.com/yt-dlp/yt-dlp/blob/master/README.md . Reuse documented external dependencies; do not vendor external binaries or silently update host tools.
