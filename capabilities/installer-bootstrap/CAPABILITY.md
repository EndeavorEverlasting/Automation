# Installer bootstrap

**Status:** Automation incubation. Pilot: Media Delivery. Adoption and landing gates are in [release evidence](release-gates.v1.json).

## Start here

Run the existing Media Delivery launcher with `setup` to open an interactive installer. Use `setup --plan` to read the JSON plan, or `setup --apply` to explicitly install without a browser. Append `--install-dir PATH` for a disposable proof. See [Media Delivery host setup](../media-transcript-acquisition/HOST_SETUP.md).

## Interaction contract

Use the [component and evidence checklist](EXPERIENCE.md) for setup, progress, recovery, and first-run work. For an operator-supplied recording, use the [local video handoff](REFERENCE_VIDEO.md).

## Reuse

Use semantic ID `installer-bootstrap/v1`. Pin the capability directory and import the public types from `installer_bootstrap`. The adjacent HTML and JS ship with that module. A consumer provides title, description, destination, boolean `Option` values, and ordered idempotent `Step` objects to `Installer`. Each step receives validated choices and returns a short safe detail, returns `StepWarning` for a completed step with follow-up, or raises `SetupError` to stop setup. Optionally name a readiness check by step ID. The JSON `readiness` record reports `pending`, `verified`, `needs_attention`, or `not_checked`. A declared `CompletionAction` is display text available after successful install. Use `plan`, `apply` or `show` on the same instance. Keep platform or container lifecycle inside the consumer adapter. Shell launchers and other harnesses call the same adapter.

The interactive UI is a transient loopback server. Its launch URL is session-local. Do not include it, install paths or other private state in public receipts. The adapter is trusted local code. Browser options select declared behavior and carry no executable commands. Keep steps bounded and publish only verified output. The Media Delivery adapter stages and verifies a Python archive before atomically replacing the installed copy.

## Validation

Run `python -m unittest discover -s tests -p test_installer_bootstrap.py -v` from the repository root. This covers the isolated consumer, headless setup and browser transport. Browser interaction, reference playback, Windows desktop, and downstream adoption are distinct evidence. Automation owns the shared mechanism. The pilot owns application packaging and runtime readiness.
