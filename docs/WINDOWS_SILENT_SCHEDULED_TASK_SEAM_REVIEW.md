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


## Addendum — due-time / multi-consumer evidence seam (2026-11-02)

- **Owner:** Automation core owns evidence classification; consumers retain
  task registration, observation collection, scheduler permissions, tick scripts,
  and any live focus/fullscreen certification.
- **Semantic input/output:** `automation.windows-silent-scheduled-task.silence-evidence/v1`
  → `automation.windows-silent-scheduled-task.silence-audit/v1`.
- **Normal consumer knowledge:** task ID/name, scheduler command, hidden bit,
  optional due-time sampling and explicit certification, plus stable CLI.
  No donor repository, internal scheduler ID, prompt registry or user-specific path.
- **Discoverability:** root README → capability CAPABILITY.md → CLI/schema/tests.
- **Portability canary:** test copies only `core/silence_audit.py` into an
  isolated folder, imports and classifies without Automation internals.
- **Negative cases:** console-subsystem launcher cannot be promoted by zero-hit
  observation; a console hit overrides prior certification; Hidden PowerShell
  remains a review item; absent fullscreen/child proof never certifies.
- **Remaining adoption:** at least one live downstream consumer must adopt the
  versioned audit interface, remove duplicate classification, and prove a live
  due-time and fullscreen focus session before broad certification claims.
- **Result:** isolated classifier portable in synthetic tests; downstream scar
  deletion and Windows runtime certification remain open.


## Addendum — SILENT_BACKGROUND child-chain and installer seam (2026-11-02)

- **Owner:** Automation defines the opt-in execution class, Python policy,
  Node child-spawn adapter, read-only reinstall preflight, and private result
  receipt schema. Consumer applications still own clocks, ticks, intentional
  user-facing UI, detailed private logs, authentication and operator decisions.
- **Minimal consumer inputs:** `job_id`, explicit argument vector, optionally
  approved console tools, and versioned registry with `SILENT_BACKGROUND`.
  Consumers do not require donor paths, upstream prompt routers or a new daemon.
- **Normal outcomes:** `DEFERRED_INTERACTION`, `SPAWNED_NOT_CERTIFIED`,
  `SUCCEEDED`, `NONZERO`, `TIMEOUT`, `LAUNCH_FAILED` plus reason codes.
- **Enforcement limits:** `CREATE_NO_WINDOW` / `windowsHide` protects direct
  console launches, not arbitrary GUI descendants. Each nested spawn must opt
  into the shared class; close the gap with live child/focus certification.
- **Isolated canary:** Python module imports when copied alone, and Node adapter
  requires only Node built-ins. Each has negative UI/installer/shell tests.
- **Consumer migration:** retain existing schedules and application receipts;
  pin a tested Automation revision, integrate its wrapper at product-owned
  child spawn sites and installer preflight, then remove replaced local forks
  only after parity and due-time observation. Track consumer adoption
  independently from this upstream implementation.
- **Proof state:** upstream portable execution surface implemented and gated in
  CI; no unattended production activation or real fullscreen game run is claimed.
