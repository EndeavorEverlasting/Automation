# Local installer recording handoff

Start here when an installer design depends on a private recording. Automation owns the analysis procedure and the component checklist. The operator or the authorized private work item supplies the source path at execution time.

## 1. Establish the source on the workstation

Use the local copy supplied by the operator first. Confirm the literal path, including spaces. If it is absent or unreadable, use the authorized provider copy on the same workstation. Never alter sharing or substitute a different video. A file size or name alone is insufficient to establish file identity.

From the Automation checkout, with the authorized path in `$video` and FFmpeg/FFprobe on PATH:

```powershell
if (-not (Test-Path -LiteralPath $video -PathType Leaf)) { throw "Local recording is unavailable." }
$evidence = Join-Path $env:LOCALAPPDATA ("Automation\InstallerReview\" + [guid]::NewGuid())
python .\capabilities\media-transcript-acquisition\inspect_local_video.py --input "$video" --out-dir "$evidence"
if ($LASTEXITCODE -ne 0) { throw "Recording inspection failed." }
```

The command records bytes, SHA-256, video dimensions and duration in `source.json` outside the checkout. Review from beginning to end using file-based evidence, including the handoff after installation. Background review may extract frames and decode audio as data. Never open the recording with a player, browser, or the Windows default app from the agent run. Leave the system mixer alone.

## 2. Build a timestamped decision map

For every consequential transition, record a timestamp range in playback time, screen, visible control or status, initial value when visible, action taken, resulting behavior, and any observed back, skip, defer or revisit path. Use `UNKNOWN` for unshown choices and effects. Distinguish display copy from a verified installer operation. Keep frames, full notes, and local paths private.

| Coverage | What to capture |
| --- | --- |
| Launch and entry | Initial surface, primary action, required prerequisites or permission prompt, and click-to-first-feedback timing. |
| Review and choices | Destination, option or toggle label, visible default, consequence, action, and any navigation or consent. |
| Work in progress | First meaningful progress, active versus complete labels, percentage or indeterminate states, motion cues, and any interruption. |
| Completion and first run | End of installation, next action, first usable screen, and any visible onboarding, defer, or settings revisit. |

Use the same inspector with a **new** private output directory and repeated `--at SECONDS` flags to retain representative frames, up to 24 per run. Sample across the recording, then use denser frame sequences around transitions. A requested seek identifies a nearby decoded frame. If file-based evidence cannot establish full coverage or exact timing, keep that gate open for an explicitly requested foreground review. Record the unresolved interval and keep the source private.

## 3. Reconcile and certify separately

1. Compare the observed map row by row with the [experience checklist](EXPERIENCE.md). Label each row matched, differs, or unknown, and record the owning implementation file and acceptance check for each material gap.
2. Publish the minimal changes to the existing installer candidate. Validate the exact candidate on the Windows desktop with a disposable install directory. Record installer publication, prerequisite readiness, and the first usable app state separately.
3. Attach a sanitized summary to the authorized private work item with the candidate SHA and the recording and Windows proof statuses. Keep the recording, frames, machine paths, and private locator out of public Git. Update the [release gates](release-gates.v1.json) only after the required proof exists.
