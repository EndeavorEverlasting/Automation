# Windows silent scheduled task

## Purpose

Incubate the **silent Windows cron** pattern so consumer repositories stop
copy-pasting competing implementations:

1. Launch ticks with **`pythonw.exe`** (no console / Windows Terminal flash)
2. Register tasks with **Hidden** settings via full `Register-ScheduledTask`
3. Spawn child tools with **`CREATE_NO_WINDOW`** when the parent is pythonw
4. Classify installed tasks as silent vs noisy from `schtasks` evidence

## Why this belongs in Automation

Any workstation repo that uses Task Scheduler (qBit Cubit, TokenCorridor wake,
future consumers) needs the same silent-launch contract. Product tick *scripts*
stay in the consumer; the reusable launch/register/classify machinery belongs
here.

## Prior art → incubation

| Source | What moved here |
| --- | --- |
| qbit-config `win_subprocess.py` / `cubit_cron.resolve_pythonw` / `Register-SilentCronTasks.ps1` | Core helpers + ensure render |
| TokenCorridor `win_discreet_subprocess` / wake installer `-RepairSilent` | Same silent contract, now owned upstream |

Consumers should **thin-wrap** this capability (pin Automation, point a registry
at their scripts) instead of keeping a second full implementation forever.

## Entrypoints

| Surface | Path |
| --- | --- |
| CLI | `capabilities/windows-silent-scheduled-task/silent_cron.py` |
| PowerShell wrapper | `capabilities/windows-silent-scheduled-task/Register-SilentCron.ps1` |
| Registry schema | `capabilities/windows-silent-scheduled-task/schemas/silent-cron-registry.v1.json` |

```powershell
python capabilities/windows-silent-scheduled-task/silent_cron.py resolve-pythonw

python capabilities/windows-silent-scheduled-task/silent_cron.py classify-fixture `
  --fixture capabilities/windows-silent-scheduled-task/fixtures/schtasks-list.pythonw.fixture.txt

python capabilities/windows-silent-scheduled-task/silent_cron.py render `
  --registry capabilities/windows-silent-scheduled-task/fixtures/registry.synthetic.v1.json `
  --job-id demo_tick `
  --repo-root capabilities/windows-silent-scheduled-task

# Live mutation (operator workstation only):
python capabilities/windows-silent-scheduled-task/silent_cron.py ensure `
  --registry path\to\consumer-registry.json `
  --job-id my_job `
  --repo-root path\to\consumer\repo `
  --apply
```

## Consumer checklist (emulate, don't fork)

1. Author a registry JSON with schema `automation.windows-silent-scheduled-task.registry/v1`.
2. Point `script` at your tick entrypoint; keep product logic in your repo.
3. `render` / `ensure --apply` through this capability (or a one-line wrapper).
4. For child processes from pythonw, import/call `core.win_subprocess.run`.
5. Operator diagnosis: Task Scheduler → Actions → Program must end in `pythonw.exe`.

## Non-goals

- Owning Cubit queue or TokenCorridor Work Graph selection
- Non-Windows cron systems in this revision
- Hiding UAC / interactive installers
- Claiming CI registered a live task

## Proof ceiling

- **Synthetic (CI):** fixture classify + registry load + PowerShell render contains `pythonw` and `-Hidden`
- **Live:** operator `--apply` on Windows; verify `silent_pythonw=true` via `query-task` or Task Scheduler UI


## Multi-repository silence evidence audit (read-only)

The capability now accepts a **supplied snapshot** from any consumer, without
opening Task Scheduler or mutating tasks. Each consumer owns collection of
installed-task metadata, due-time samples, and child/focus certification;
Automation owns their stable classification and comparison.

```powershell
python capabilities/windows-silent-scheduled-task/silent_cron.py audit-evidence `
  --input capabilities/windows-silent-scheduled-task/fixtures/silence-evidence.synthetic.v1.json
```

Input schema: `schemas/silence-evidence.v1.json` with semantic ID
`automation.windows-silent-scheduled-task.silence-evidence/v1`.
Output semantic ID: `automation.windows-silent-scheduled-task.silence-audit/v1`.

The input `tasks[]` accepts independent task IDs, exact Task Scheduler
`task_to_run`, explicit `hidden`, optional `launcher_no_window`,
`last_result`, `due_time` counts (including zero-flash and foreground checks),
and a separately sourced `certification` record. It works across any number
of repositories without importing their runtime modules. Never put actual
workstation paths, private logs, or employee/client metadata into tracked
fixtures.

**Independent output dimensions:**

- `launcher_class`: PYTHONW, HIDDEN_POWERSHELL,
  DECLARED_WINDOWLESS_NODE, CONSOLE_RISK, UNKNOWN.
- `launcher_compliant`: whether the supplied launcher meets the metadata gate.
- `silence_state`: REVIEW, LAUNCHER_COMPLIANT, DUE_TIME_OBSERVED,
  FLASH_OBSERVED, or SILENT_CERTIFIED.
- `silence_review`: queue flag distinct from `silence_state`; Hidden
  PowerShell and declared Node wrappers remain review items until certified.
- `functional_state`: ZERO, NONZERO, UNKNOWN from task `last_result`.
  A nonzero tick result is not evidence of a foreground flash.
- `reason_codes` and summary counts preserve the actual gaps.

**Certification gate:** `SILENT_CERTIFIED` is emitted only when the task is
launcher-compliant, a matched due-time sample has positive sample count, zero
console hits and preserved foreground, plus a supplied explicit
`child_processes=CERTIFIED`, `focus=CERTIFIED`,
`focus_mode=fullscreen` and nonempty `proof_ref`.
The audit verifies *the shape and logical sufficiency of reported evidence*,
not the source receipt's authenticity or actual Windows behavior.
`proof_ceiling=SUPPLIED_EVIDENCE_CLASSIFICATION_NOT_LIVE_PROVIDER_VALIDATION`
is always included. A Chrome-foreground sample does not certify a fullscreen
game, and launcher Hidden alone never certifies the child-process chain.

The implementation is a dependency-light `core/silence_audit.py` module.
The isolated consumer canary copies that file alone into a temporary directory
and imports it without Automation or any donor checkout. Consumers can either
pin and call the stable CLI or copy the capability through an approved versioned
distribution; avoid independently editing shared classification rules.

Test without workstation mutation:

```powershell
python -m unittest discover -s capabilities/windows-silent-scheduled-task/tests -p 'test_*.py' -v
```

No scheduler installation, task repair, full-screen test or live provider
certification occurs as part of the audit or its synthetic tests.


## SILENT_BACKGROUND execution class — chain policy and reinstall guard

Contract: `automation.silent-background/v1` (execution) and
`automation.silent-background.receipt/v1` (private receipt schema).
This is an **extension of the same Windows silent scheduled-task capability**,
not a second cron service. The existing Task Scheduler/AFK/logon triggers,
app-owned timers, product functions, and product-specific receipt writers stay
where they are. Intentional application launches remain `INTERACTIVE`.

**Consumer usage (Python child process):**

```python
from core.silent_background import SilentBackground

policy = SilentBackground(job_id="my-product-tick")
outcome = policy.execute(["git", "status", "--porcelain"], execution_class="SILENT_BACKGROUND")
# outcome: SUCCEEDED / NONZERO / DEFERRED_INTERACTION / TIMEOUT / LAUNCH_FAILED
# private receipt: %LOCALAPPDATA%\Automation\SilentBackground\receipts\
```

On Windows the policy sets `CREATE_NO_WINDOW` and a hidden `STARTUPINFO`,
closes stdin, captures bounded result metadata rather than displaying a popup,
and rejects `shell=True`, `cmd`, GUI/browser/installer launchers, unknown
executables, and interactive PowerShell calls by default. A consumer may declare
additional **approved console tools**; that is a provenance/approval decision,
not a runtime certification. If user input, elevation, authentication or a
visual installer is necessary, retain the job and emit
`DEFERRED_INTERACTION` with a private receipt instead of prompting.

**Consumer usage (Node child process):**

```js
const { spawnBackground } = require("./silent_background.cjs");
const { status, child, receiptPath } = spawnBackground(
  "node.exe", ["worker.js"], { jobId: "my-product-tick" }
);
```

The distributable Node adapter is
`adapters/node/silent_background.cjs`; it enforces `windowsHide:true`,
`shell:false` and ignored stdio for scheduled descendants, and records a
private lifecycle receipt. It does **not** replace an app's existing
application-specific log/outbox. An explicit `INTERACTIVE` invocation
preserves inherited IO and visible application behavior.

**Installer / update hook:** Registries still use
`automation.windows-silent-scheduled-task.registry/v1`; missing
`execution_class` defaults to `SILENT_BACKGROUND` for legacy consumers,
and explicitly declaring `INTERACTIVE` is rejected by this silent
registration capability. Run a read-only gate before `ensure --apply`:

```powershell
python capabilities/windows-silent-scheduled-task/silent_cron.py preflight `
  --registry capabilities/windows-silent-scheduled-task/fixtures/registry.synthetic.v1.json `
  --repo-root capabilities/windows-silent-scheduled-task
```

`preflight` validates all job identities and ownership-relative Python scripts,
rejects duplicate Task Scheduler names, and reports the expected `pythonw`
and Hidden registration without touching the scheduler. Existing non-Python
launchers remain consumer-owned until their adapters are independently
certified; **do not replace/disable them by forcing this Python registration**.

**Proof ladder:** install preflight → launch policy receipt → due-time sample
→ explicit child-chain and fullscreen focus certification. None may be
substituted for a later stage. The shared wrapper cannot control arbitrary
grandchildren that ignore it, or GUI APIs called inside a child; adopt it
at every subprocess boundary and certify the actual observed chain.

**CI tests:**

```sh
python -m unittest discover -s capabilities/windows-silent-scheduled-task/tests -p "test_*.py" -v
node --test capabilities/windows-silent-scheduled-task/tests/test_silent_background_node.cjs
```

**Consumer adoption:** pin a specific Automation revision; copy its published
module/adapters unchanged or use a pinned integration. Wire every scheduled
child launcher and installer preflight, preserve existing clock/cadence and
receipt writers, run isolated consumer tests, then delete proven duplicates
with a regression that prevents their return. Do not install a new scheduler,
change live task configuration, or migrate to app-owned timers without an
explicitly scoped change and live follow-up validation.

### Non-bypassable registry admission (direct render and live ensure)

Both `preflight` and direct `render` / `ensure --apply` validate the **entire**
consumer registry using `core.registry.validate_registration_inputs`. An
otherwise-valid target is refused when a sibling has an unsafe or missing
script, including resolved symlink escapes. Duplicate task names and
`INTERACTIVE` entries remain rejected by the existing registry parser.
Validation completes before resolving a Windows interpreter or contacting
Task Scheduler; a single validated registry snapshot is used for the action.
A rejected registry leaves installed tasks and clocks untouched.

**Clock exception:** this CLI's installer models repeating-minute triggers.
Existing H&H weekly schedules must retain their distinct weekday/time
triggers through their owners, rather than being migrated into this installer.
They should still use the shared child-process admission and evidence audit.
Offline regression: `python -m unittest discover -s capabilities/windows-silent-scheduled-task/tests -p 'test_*.py' -v`.
No synthetic validation is a due-time/fullscreen certification.
