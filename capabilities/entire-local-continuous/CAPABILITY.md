# Entire-local continuous development

## Purpose

Incubate the **Actions-optional continuous local development** pattern so agents
stop inventing:

1. console-flashing Task Scheduler / cron jobs that disrupt fullscreen work;
2. AFK loops that treat GitHub Actions as required velocity;
3. Entire enablement that silently pushes session transcripts to a public origin.

This capability is the **admission and receipt** owner. It does **not** replace:

| Owner | Still owns |
| --- | --- |
| `capabilities/windows-silent-scheduled-task` | `pythonw` + Hidden registration, `SILENT_BACKGROUND`, silence evidence audit |
| `EndeavorEverlasting/github-config` `docs/entire/` | Fleet inventory, workstation adoption scripts, per-repo adoption state |
| Consumer repositories | Product tick scripts, local validators, cadence/clocks |
| TokenCorridor | Prompt Kit / routing authority |

## Why this belongs in Automation

Continuous AFK development is a **cross-repository mechanism**: Entire for
session/checkpoint continuity, silent scheduled tasks for unattended ticks,
repository-owned tests as semantic proof, and GitHub only as optional hosting /
optional independent evidence. Agents repeatedly recreate weaker copies. The
reusable admission rules belong here.

## Prior art → incubation (P97)

| Source | Mechanism extracted | Disposition |
| --- | --- | --- |
| github-config Entire adoption plan | local-only enable, `--skip-push-sessions`, workflow digest invariance, typed adoption states | **ADAPT** into offline classifier + receipt |
| PiShark Entire local proof groundwork | Actions optional / offline floor as semantic proof | **ADAPT** |
| EscapeHatch SubmissionSync | `pythonw` host + Automation `SILENT_BACKGROUND` child chain | **ADOPT** silence owner pointer |
| Automation silent scheduled task (#40/#41) | Non-bypassable registry admission, fullscreen certification ladder | **ALREADY_SOLVED_INTERNALLY** — related owner |
| GitHub Actions-centric AFK prompts | Actions as required harness | **REJECT** as sole AFK authority |

## Entrypoints

```powershell
python capabilities/entire-local-continuous/continuous_local.py classify-status `
  --status-json capabilities/entire-local-continuous/fixtures/entire-status.not-setup.v1.json `
  --entire-installed

python capabilities/entire-local-continuous/continuous_local.py check-workflows `
  --before ABSENT --after ABSENT

python capabilities/entire-local-continuous/continuous_local.py admit-afk `
  --proposal capabilities/entire-local-continuous/fixtures/afk-proposal.admitted.v1.json

python capabilities/entire-local-continuous/continuous_local.py receipt `
  --repository EndeavorEverlasting/Example `
  --status-json capabilities/entire-local-continuous/fixtures/entire-status.enabled-local.v1.json `
  --entire-installed --doctor-ok `
  --workflow-before DIGEST_A --workflow-after DIGEST_A `
  --proposal capabilities/entire-local-continuous/fixtures/afk-proposal.admitted.v1.json
```

Contract IDs:

- `automation.entire-local-continuous/v1`
- `automation.entire-local-continuous.receipt/v1`

## Agent admission rules (enforced)

Before creating or repairing a scheduled AFK job, an agent **must**:

1. Route silence through `capabilities/windows-silent-scheduled-task` (`SILENT_BACKGROUND`, `pythonw.exe`, Hidden).
2. Run `admit-afk` (or equivalent core call) and refuse on any violation.
3. Treat GitHub Actions as `OPTIONAL_UNCHANGED` / `ABSENT_OK` — never `REQUIRED`.
4. For Entire enablement: prefer
   `entire enable --local --skip-push-sessions --agent <used-agent>` and keep
   remote checkpoint push as a separate privacy gate.
5. Preserve existing consumer clocks/cadence; do not rewrite weekly/H&H schedules
   into this installer’s minute model without an explicit separate sprint.
6. Never claim `SILENT_CERTIFIED` or live fullscreen safety from admission alone.

Negative fixture `fixtures/afk-proposal.console-rejected.v1.json` encodes the
common agent failure mode (PowerShell host, Actions-required, silence bypass,
fullscreen disruption, remote push without policy).

## Live Entire enablement (operator / P08)

This capability classifies supplied status; live enable remains operator-gated:

```powershell
# Capture workflow digest before/after with the github-config helper or equivalent.
entire version
entire agent-help
entire enable --local --skip-push-sessions --agent cursor
entire configure --telemetry=false
entire status --json
entire doctor
```

Ignore `.entire/` in Git. Do not commit session metadata. Do not mutate
`.github/workflows/**` in an Entire lane.

Fleet inventory rows and multi-repo adoption scripts stay in github-config.

## Proof ceiling

| Gate | What it proves |
| --- | --- |
| Synthetic unittest | Classification, digest invariance, admit/reject, isolated canary |
| Live `entire status` / `doctor` | Local enablement health on one checkout |
| Silence preflight / due-time / fullscreen | Owned by `windows-silent-scheduled-task` |
| Hosted Actions green | Optional independent evidence only |

```powershell
python -m unittest discover -s capabilities/entire-local-continuous/tests -p 'test_*.py' -v
```

## Non-goals

- Replacing github-config fleet adoption
- Publishing checkpoints to origin for public repos
- Owning product tick business logic
- Declaring Actions obsolete when a consumer still wants optional provider evidence
