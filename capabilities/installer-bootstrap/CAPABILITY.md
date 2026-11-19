# Installer bootstrap

**Status:** Automation incubation. Pilot: Media Delivery. Adoption and landing gates are in [release evidence](release-gates.v1.json).

## Start here

Run the existing Media Delivery launcher with `setup` to open an interactive installer. Use `setup --plan` to read the JSON plan, or `setup --apply` to explicitly install without a browser. Append `--install-dir PATH` for a disposable proof. See [Media Delivery host setup](../media-transcript-acquisition/HOST_SETUP.md).

## Interaction contract

| State | Implemented behavior |
| --- | --- |
| Review | Show the destination and the effect of each option. The Install action commits the current choices. |
| Installing | Show waiting, active, complete, skipped and failed steps in the same order as the runner. The lower rail advances on completed selected steps only. |
| Stopping | Finish the current bounded step, then stop before further work. If the final install has already completed, report completion. |
| Needs attention | Keep the failed step visible with a safe next action. Keep choices editable so the operator can retry. |
| Installed | Show the installed destination. Prove application readiness independently of package installation. |

Use one product mark, layered low-contrast scenery, per-step state and a single motion accent tied to progress. Keep foreground contrast and keyboard access. Respect reduced motion and expose an on-screen override. Each consumer supplies its own copy and choices and owns any system permissions, configuration, dependencies and post-install handoff. Any future account, background task, system-default, agreement or privileged setting needs its own explicit decision.

The supplied reference frames show 27% and 60% progress, a marker moving on a lower rail, and a checklist with completed, active and waiting rows. The text in those rows describes browser benefits. The incubation uses actual setup steps as the progress source. The full recording is required to ground screen order, first-run gates, toggle defaults, skip/back paths and the install-to-first-run transition.

## Reuse

Use semantic ID `installer-bootstrap/v1`. Pin the capability directory and import the public `Installer`, `Option`, `Step` and `SetupError` interface from `installer_bootstrap`. The adjacent HTML and JS ship with that module. A consumer provides title, description, destination, boolean options and ordered idempotent steps. Each step receives validated choices and returns a short safe detail or raises `SetupError`. Use `plan`, `apply` or `show` on the same instance. Keep platform or container lifecycle inside the consumer adapter. Shell launchers and other harnesses call the same adapter.

The interactive UI is a transient loopback server. Its launch URL is session-local. Do not include it, install paths or other private state in public receipts. The adapter is trusted local code. Browser options select declared behavior and carry no executable commands. Keep steps bounded and publish only verified output. The Media Delivery adapter stages and verifies a Python archive before atomically replacing the installed copy.

## Validation

Run `python -m unittest discover -s tests -p test_installer_bootstrap.py -v` from the repository root. This covers the isolated consumer, headless setup and browser transport. Browser interaction, reference playback, Windows desktop, and downstream adoption are distinct evidence. Automation owns the shared mechanism. The pilot owns application packaging and runtime readiness.
