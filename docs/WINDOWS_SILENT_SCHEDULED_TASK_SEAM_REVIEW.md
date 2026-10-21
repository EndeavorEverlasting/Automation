# Windows Silent Scheduled Task — Seam & Boundary Review

Date: 2026-10-21  
Capability: `windows-silent-scheduled-task`  
Result: **PASS AT PORTABLE CORE / LIVE APPLY OPERATOR-GATED**

## Owner

Automation owns reusable silent Windows Task Scheduler primitives:

- `pythonw.exe` resolution
- Hidden `Register-ScheduledTask` render/apply
- `schtasks` silent vs noisy classification
- `CREATE_NO_WINDOW` child-process helpers

Consumer repositories (qBit Cubit, TokenCorridor wake, future repos) own only
their job registries and product tick scripts.

## Semantic contract

- capability identity: `windows-silent-scheduled-task`
- consumer input: `automation.windows-silent-scheduled-task.registry/v1`
- normal invocation: `python capabilities/windows-silent-scheduled-task/silent_cron.py …`
- PowerShell wrapper: `Register-SilentCron.ps1`

Repository paths are distribution locators, not the semantic identity.

## Consumer Knowledge Test

A normal consumer must know only:

- its own job registry (task names, script paths, intervals);
- how to call `render` / `ensure` / `classify-fixture`;
- that live `--apply` mutates Task Scheduler on a Windows operator host;
- the proof ceiling (synthetic vs live).

A normal consumer does **not** need:

- qBit or TokenCorridor internal cron modules;
- donor PR history or migration notes;
- Automation `core/` module layout beyond the documented CLI;
- chat/model memory.

## Distribution artifact

Stable surfaces:

- `capabilities/windows-silent-scheduled-task/silent_cron.py`
- `capabilities/windows-silent-scheduled-task/Register-SilentCron.ps1`
- `capabilities/windows-silent-scheduled-task/schemas/silent-cron-registry.v1.json`
- `capabilities/windows-silent-scheduled-task/capability.v1.json`

## Isolated consumer canary

Synthetic canary (no Task Scheduler mutation):

```powershell
python capabilities/windows-silent-scheduled-task/silent_cron.py classify-fixture `
  --fixture capabilities/windows-silent-scheduled-task/fixtures/schtasks-list.pythonw.fixture.txt

python capabilities/windows-silent-scheduled-task/silent_cron.py render `
  --registry capabilities/windows-silent-scheduled-task/fixtures/registry.synthetic.v1.json `
  --job-id demo_tick `
  --repo-root capabilities/windows-silent-scheduled-task
```

Expected: `silent_pythonw=true` on the pythonw fixture; rendered PowerShell
contains `pythonw` and `-Hidden`.

## Downstream scar deletion (follow-on)

After consumers pin this capability:

1. Thin-wrap TokenCorridor / qBit installers to call Automation ensure.
2. Delete or shrink forked `win_subprocess` / silent-cron copies once the pin is
   proven.
3. Add a regression that refuses reintroduction of console `py.exe` /
   `python.exe` Task Scheduler launchers for silent jobs.

This admission does **not** claim those deletions are already complete.

## Proof ceiling

| Tier | What is proved |
| --- | --- |
| Synthetic CI | Fixture classify, registry load, render shape |
| Live operator | `--apply` + `query-task` on a Windows workstation |

CI must not claim live Task Scheduler registration.
