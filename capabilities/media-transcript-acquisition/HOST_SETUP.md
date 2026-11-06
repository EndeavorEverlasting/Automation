# Media Delivery host setup — Windows and Linux Mint

This is a user-launched terminal application for locally saving authorized accessible public media as video, MP3 audio, or both. It does not automatically install dependencies, open a browser, register a background task, or send files to the cloud.

## Prerequisites

Python 3.11+, yt-dlp, and FFmpeg must be present on the host PATH. FFmpeg is required for every capture mode, because video may require separate audio/video stream merging. Recent YouTube extraction may also depend on yt-dlp JavaScript components. Consult upstream installation documentation before changing your host.

## Windows 10/11

Open a PowerShell terminal in the Automation repository. For a read-only dependency check run:

    .\capabilities\media-transcript-acquisition\Run-Media-Delivery.cmd doctor

To start the guided application run:

    .\capabilities\media-transcript-acquisition\Run-Media-Delivery.cmd

The launcher chooses py -3, falling back to python. It never installs packages or schedules jobs. If Python or another dependency is missing, use the official install pages below, reopen your terminal, and rerun doctor.

## Linux Mint

Open a terminal in the Automation repository and run:

    bash capabilities/media-transcript-acquisition/run-media-delivery.sh doctor
    bash capabilities/media-transcript-acquisition/run-media-delivery.sh

Python 3.11+ is required. Mint 22 commonly ships Python 3.12; older versions may provide an earlier unsupported interpreter. Do not replace system Python. Use your distro's approved Python environment and verify versions with python3 --version, yt-dlp --version, and ffmpeg -version.

Linux Mint installation is operator-controlled. Use your package manager for Python, FFmpeg and pipx and follow yt-dlp's official pipx/release installation guide; no installation or shell configuration is performed by this repository.

## Capture and verify

The guided prompt requests a source URL, a mode (video, audio, hybrid), and an optional output directory. Default output is ~/Downloads/Automation-Media or the corresponding user Downloads folder on Windows. Outputs stay outside the Git repository.

For noninteractive use, both platform launchers accept the same arguments:

    Run-Media-Delivery.cmd capture --url "https://www.youtube.com/shorts/pl0EltNU5p0" --mode video
    bash run-media-delivery.sh capture --url "https://www.youtube.com/shorts/pl0EltNU5p0" --mode hybrid

Run these from the capability directory, or prefix the launcher path when called from the repository root.

To verify a successfully delivered artifact, use the corresponding launcher with 'verify --receipt PATH_TO_RECEIPT_JSON'. This checks local bytes and SHA-256, not the authenticity or usage rights of media.

Blocked downloads leave typed receipts but no promoted media folder. Provider restrictions are not bypassed; no cookies, credential transfer, interactive login or account scraping is supported. Use only sources you are authorized to download.

Windows and Linux GitHub CI do not prove real Windows 11 or Linux Mint desktop behavior or external provider reachability. A host-only certification is recorded separately in the P04 handoff.

Official sources:
- https://github.com/yt-dlp/yt-dlp/wiki/Installation
- https://github.com/yt-dlp/yt-dlp/blob/master/README.md
- https://ffmpeg.org/download.html

See ARTIFACT_DELIVERY.md for the shared delivery contract and docs/handoffs/MEDIA_ARTIFACT_HOST_CERTIFICATION_2026-11-06.json for the executable host acceptance packet.
