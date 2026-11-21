# File-only video processing

Video analysis, inspection, and transcription use the recording as input data. Background and hidden jobs must produce files, decoded samples, or metadata without starting a player, opening media through the OS or a browser, or sending audio to a device. A hidden window and redirected command output control presentation only. Leave the system volume, mixer, and other applications alone. Use a separate, explicitly requested foreground session for playback.

## Inspect a local recording

From an Automation checkout with Python 3.11+, FFmpeg, and FFprobe on PATH, pass an authorized MP4, MOV, or M4V and a new private output directory outside the checkout. Omit `--at` to record source metadata only. Repeat it for up to 24 frame seeks in seconds.

```text
python capabilities/media-transcript-acquisition/inspect_local_video.py --input "<local video>" --out-dir "<new private directory>" --at 0.5 --at 8.5
```

The command writes `source.json` (`automation.local-video-review/v1`) with `processing: FILES_ONLY`, the source byte count, SHA-256, duration and dimensions, and each requested frame's relative path and hash. Seeks identify nearby decoded frames. The source retains its audio and original bytes. Exit 2 means inspection failed. If a tool is missing, the source is unusable, or the tool fails, stop the inspection without falling back to playback.

The inspector uses FFprobe for metadata. Both the inspector and the social frame sampler use FFmpeg for explicit video-only image output. ASR can decode audio in memory, and [artifact delivery](ARTIFACT_DELIVERY.md) can write audio and video files when requested.

## Check a Windows workstation

Run the media regression suite with FFmpeg and FFprobe on PATH. For desktop certification, run the inspector from the local agent's normal background entry point with a disposable clip containing a verified tone. Observe the process tree and audio sessions while it runs. Verify that the expected frames and receipt exist, the input hash and audio track persist, and the job starts no player or audio output session. Record the tested commit, launcher, and observed outcome without committing the clip, frame files, or private paths.

```text
python -m unittest discover -s capabilities/media-transcript-acquisition/tests -v
```
