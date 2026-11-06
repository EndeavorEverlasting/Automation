# P04 canonical handoff — Media Delivery on Windows and Linux Mint

**Parent objective:** make an authorized, local-first social media downloader usable on both Windows and Linux Mint. The media output contract is automation.media-artifact-delivery/v1 and the host experience is automation.media-host/v1.

**Machine-readable execution packet:** MEDIA_ARTIFACT_HOST_CERTIFICATION_2026-11-06.json (READY for local agents). **User installation and launch instructions:** ../../capabilities/media-transcript-acquisition/HOST_SETUP.md.

## Current proven floor and separated proof

- Prior delivery engine merged as Automation PR #47, commit 362563cd6fe9a1a316e14d58f258057e67eb0764; video/audio/hybrid local receipt and SHA-256 validation were tested with synthetic media.
- This follow-up includes shared host_app.py, Windows CMD and Linux Mint bash wrappers, doctor/verify subcommands and OS CI; refresh main and check the current follow-up PR merge status before making any claim.
- CI on a hosted Windows runner and Ubuntu runner is distinct from a real Windows 11 installation or Linux Mint desktop. Neither CI nor a successful local tool diagnosis proves real source access/media playback or fullscreen/no-popup safety.
- No user-specific checkout path, account or source URL is assumed. First resolve actual host and repo revision; avoid building a second checkout blindly. Public tracked evidence must be sanitized.

## Lane WIN-HOST — Windows 10/11 agent or user

1. Confirm local checkout is clean and at the integrated revision. Check Python version (at least 3.11), yt-dlp and FFmpeg versions; do not auto-install or change live settings.
2. From the repository root, run the following commands in PowerShell:

    .\capabilities\media-transcript-acquisition\Run-Media-Delivery.cmd doctor
    .\capabilities\media-transcript-acquisition\Run-Media-Delivery.cmd

3. Run an operator-authorized public YouTube item and an authorized accessible Instagram item, using video, audio and hybrid where the source supports it; no cookie/login/paywall bypass.
4. Capture into a private user-selected output directory outside Git; run the same CMD launcher with verify --receipt followed by the new media folder's receipt.json path.
5. Read/inspect actual video, audio, duration/codec and SHA-256, and capture redacted command status. Observe whether a foreground terminal appears only because the user intentionally launched it. Do not call this SILENT_BACKGROUND certification.
6. Test a blocked/invalid source and confirm no promoted media folder, a typed failure, and no credential/provider error in the public record.

## Lane MINT-HOST — actual Linux Mint agent or user

1. Record distro name/version via /etc/os-release, actual interpreter python3 --version, yt-dlp and FFmpeg versions. Do not change the system Python or install dependencies unprompted.
2. From the repository root run:

    bash capabilities/media-transcript-acquisition/run-media-delivery.sh doctor
    bash capabilities/media-transcript-acquisition/run-media-delivery.sh

3. Repeat one authorized accessible YouTube and Instagram item in each feasible mode. Test both interactive and scripted capture commands and follow output into the local user's Downloads/Automation-Media directory.
4. Run the bash launcher verify --receipt for each success. Confirm bytes/hash, codec/audio/video playback, output ownership/permissions and absence of unexpected process, cron or desktop behavior.
5. Test invalid URL, missing external tool and blocked source. Record typed failure, no unwanted staging output, no bypass. Mint host certification is separate from Ubuntu CI.

## Lane P82/CI — repo-level repeatability

Run media tests on current code:

    python -m unittest discover -s capabilities/media-transcript-acquisition/tests -p 'test_*.py' -v
    python scripts/validate_runtime_handoff.py --packet docs/handoffs/MEDIA_ARTIFACT_HOST_CERTIFICATION_2026-11-06.json --require-ready

GitHub media CI must pass Python 3.11 and 3.12 on Windows and Ubuntu. Root validation and governance checks must pass before merge. If a test or host behavior fails, repair only the proven defect in a bounded branch and rerun affected checks. Do not conceal the first failure.

## P04 factoring / collision boundaries

| Lane | Owner/runtime | Output | Closure criterion |
| --- | --- | --- | --- |
| REPO | GitHub feature branch + CI | Source, tests, docs, merge receipt | All scoped CI pass, exact head merged, main file readback |
| WIN-HOST | Windows local agent/operator | Private local files and redacted diagnostic | Windows doctor + real capture + hash + playback + foreground safety observed |
| MINT-HOST | Linux Mint local agent/operator | Private local files and redacted diagnostic | Mint doctor + real capture + hash + playback + desktop behavior observed |
| JOIN | canonical issue + P04 packet | Status by OS with IDs and proof ceiling | Parent complete only after BOTH host lanes observed or explicitly dispositioned |

Do not collide with Automation PR #45's separate handoff-framework work. Do not create competing media downloaders, alter unrelated project contracts, or cross the corporate/ChatGPT boundary. The UI is deliberately interactive and not registered for unattended use.

## Redacted certification evidence, separately per OS

Record: OS version, Python/yt-dlp/FFmpeg versions, commit ID, launcher used, one-way source digest or public non-sensitive source class, mode, observed file format/duration, receipt hash parity, blocked status if any, output location category (not an actual private path), popup/foreground observation and date. Preserve raw media and full URLs locally.

Report CHANGED | PROVED | NEXT for Windows and Linux Mint separately. Never promote fixture tests or CI to live provider certification. If an upstream tool is inaccessible, keep that OS status BLOCKED and give the actual local prerequisite.

## Security invariants

User must own or be authorized to download the chosen media. No cookies, browser profiles, private-account access, bypasses, headless authentication, provider token transport, cloud uploads, hidden schedules, startup services, cron, Task Scheduler registration or private media committed to Git. No user/account/provider change is authorized by this handoff alone.
