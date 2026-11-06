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

## Optional manual installation examples (never run by the launcher)

Review these commands and package descriptions before choosing to run them on your own machine. They are not part of the app or background tasks.

Windows PowerShell with WinGet, after inspecting the package sources:

    winget install --source winget --id Python.Python.3.12
    winget install --source winget --id yt-dlp.yt-dlp
    winget install --source winget --id Gyan.FFmpeg.Essentials

Linux Mint 22, whose supported Python is generally present through the distro:

    sudo apt update
    sudo apt install python3 ffmpeg pipx
    pipx ensurepath
    pipx install 'yt-dlp[default]'

Reopen the terminal after installs so PATH includes the new binaries. Confirm Python >=3.11, yt-dlp and FFmpeg individually; real YouTube support may also need a supported JS runtime and yt-dlp-ejs per the upstream yt-dlp README.

On older Linux Mint with a supported side-by-side interpreter, the bash launcher will search python3 and versioned python3.11+ binaries without replacing distro Python. Optionally choose a trusted interpreter explicitly:

    AUTOMATION_PYTHON=/path/to/python3.12 bash capabilities/media-transcript-acquisition/run-media-delivery.sh doctor

Do not run the example until that exact interpreter exists. An unsupported version is reported rather than executing with a guessed environment.
