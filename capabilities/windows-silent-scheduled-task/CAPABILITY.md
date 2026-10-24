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
