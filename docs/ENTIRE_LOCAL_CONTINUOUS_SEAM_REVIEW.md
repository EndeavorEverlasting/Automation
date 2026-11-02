# Seam review — entire-local-continuous

Contract under review: `automation.entire-local-continuous/v1`  
Checklist authority: `docs/SEAM_BOUNDARY_REVIEW.md` /
`harness/contracts/seam-boundary-review.v1.json`

## 1. True owner

Automation owns reusable **admission, classification, and receipt** for
Actions-optional continuous local development.

Non-owners preserved:

- github-config — fleet inventory + workstation enable scripts
- windows-silent-scheduled-task — silent launch/register/classify
- consumer repos — tick scripts, clocks, local validators
- TokenCorridor — prompts/routing

## 2. Consumer Knowledge Test

A normal consumer must know:

- semantic contract id `automation.entire-local-continuous/v1`
- how to pass Entire `status --json` facts (or fixtures)
- how to pass before/after workflow digests (`ABSENT` allowed)
- how to author an AFK proposal naming the silence owner and `pythonw.exe`
- that Actions is optional evidence
- proof ceiling: classification ≠ live enable ≠ fullscreen certification

A normal consumer must **not** need:

- github-config script paths to classify a status JSON
- Automation internal test layout
- donor repository checkout topology
- Entire private session transcript contents

## 3. Suspected leakage check

Fleet adoption commands are documented as operator/live references, not as
required imports. The core accepts JSON facts only.

## 4. Semantic vs physical identity

Semantic: `automation.entire-local-continuous/v1`  
Physical path: `capabilities/entire-local-continuous/` (locator only)

## 5. Discoverability

Root pointers: `AGENTS.md`, `README.md`, capability `CAPABILITY.md`.

## 6. Workaround pressure

Repeated EscapeHatch / PiShark / qbit silent-cron and Entire local-proof copies
motivated incubation. Silence already extracted; continuous-local admission is
the remaining shared gate.

## 7. Isolated consumer canary

`tests/test_continuous_local.py::test_isolated_consumer_canary` copies only
`core/continuous_local.py` into a temp directory and imports it.

## 8. Scar removal

No competing Automation continuous-local classifier existed. Consumers should
delete ad-hoc “Actions required for AFK” and console-cron snippets after
adopting this admission + silence owner, with a regression against their return.

## Result

**PASS** for offline admission incubation. Live Entire enablement and silence
due-time/fullscreen remain separate proof ceilings.
