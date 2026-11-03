# Automation

**Ubiquitous automation primitives for any repository, project, environment, workflow, or use case.**

This repository is intentionally **repository-agnostic, domain-agnostic, and platform-agnostic**. It owns reusable automation capabilities, not the product identity of any one consumer.

## Ownership rule

A capability belongs here when its core behavior can be reused across different repositories, products, environments, or use cases.

Consumer-specific behavior must be isolated behind adapters, integrations, configuration, profiles, or invocation layers. Shared core logic must not silently inherit one consumer's paths, schemas, credentials, naming, business rules, or release lifecycle.

```text
consumer / repository / workflow
            |
            v
    adapter / integration
            |
            v
 reusable automation core
            |
            v
machine-readable artifact / receipt
```

## Prompt invocation without model memory

Repository-capable agents do not need conversational memory to know what `P92` or another registered prompt means.

```powershell
python scripts/prompt_runtime.py --text "invoke & implement P92"
```

Automation delegates prompt identity, intent semantics, authority routing, and prompt bytes to the pinned `prompt-invocation-upstream/v1` dependency. It does not reproduce Prompt Kit registry logic. See [docs/PROMPT_RUNTIME.md](docs/PROMPT_RUNTIME.md).

## Runtime distribution without executor judgment

Automation consumes an upstream `planning.runtime_partition` placement decision through an execution-facing validation contract. It does not become a competing planner or broker.

A READY handoff must be explicit enough for ordinary executors such as Cursor, OpenCode, connected-provider runtimes, or CI without relying on model memory or frontier-model judgment.

- [docs/RUNTIME_DISTRIBUTION.md](docs/RUNTIME_DISTRIBUTION.md)
- [harness/contracts/runtime-execution-handoff.v1.json](harness/contracts/runtime-execution-handoff.v1.json)
- [docs/PUBLIC_PRIVATE_BRIDGE.md](docs/PUBLIC_PRIVATE_BRIDGE.md)
- `python scripts/validate_runtime_handoff.py --packet <packet.json> --require-ready`

Tracked public handoffs fail closed on private continuity-store links, person-specific workstation paths, and secret-bearing fields. Private operator continuity may point to this public repository, but this repository must remain usable without private continuity access.

## Repository charter

The canonical ownership and placement contracts are:

- [docs/REPOSITORY_CHARTER.md](docs/REPOSITORY_CHARTER.md)
- [docs/SEAM_BOUNDARY_REVIEW.md](docs/SEAM_BOUNDARY_REVIEW.md) for reusable seam/consumer-boundary review
- [harness/contracts/seam-boundary-review.v1.json](harness/contracts/seam-boundary-review.v1.json) for the machine-readable review contract
- [CONTRIBUTING.md](CONTRIBUTING.md)
- [AGENTS.md](AGENTS.md) for repository-capable agents
- [harness/contracts/canonical-path.v1.json](harness/contracts/canonical-path.v1.json) for P92 path ownership
- `python scripts/path_receipt.py --repo-root .` for the current PATH INPUT / execution-context receipt

The short version:

- reusable automation belongs here;
- product-specific business logic stays with its product;
- provider- and repo-specific seams stay isolated;
- configuration beats hard-coded assumptions;
- machine-readable contracts are preferred;
- secrets and runtime state never belong in source control;
- "ubiquitous" is a direction backed by validation, not an unsupported compatibility claim.

## Git-provider portability (incubating)

- [Git portability contract](capabilities/git-portability/CAPABILITY.md) — create/verify an offline Git-history bundle, safely restore exact refs, and optionally upload public source through a separately configured Google Drive/rclone adapter. This is **not yet an account-wide backup**, encrypted private mirror, or provider bootstrapper. Tokens/credentials never belong in this repository. TokenCorridor's prompt registry and judgment ownership remain upstream.
- Run `python -m unittest discover -s tests -p 'test_git_portability.py' -v` for synthetic recovery proof. See the capability's successor gates before deploying unattended.

## Entire-local continuous development (incubating)

- [Entire-local continuous contract](capabilities/entire-local-continuous/CAPABILITY.md) — Actions-optional AFK continuity: classify Entire status, prove `.github/workflows` invariance, and **fail-closed admit** silent cron proposals so agents cannot ship console hosts, Actions-required loops, or remote checkpoint push without policy.
- Pair with [windows-silent-scheduled-task](capabilities/windows-silent-scheduled-task/CAPABILITY.md) for `pythonw` / `SILENT_BACKGROUND`. Fleet adoption scripts stay in github-config.
- Seam review: [docs/ENTIRE_LOCAL_CONTINUOUS_SEAM_REVIEW.md](docs/ENTIRE_LOCAL_CONTINUOUS_SEAM_REVIEW.md).

```powershell
python capabilities/entire-local-continuous/continuous_local.py admit-afk `
  --proposal capabilities/entire-local-continuous/fixtures/afk-proposal.admitted.v1.json
python -m unittest discover -s capabilities/entire-local-continuous/tests -p 'test_*.py' -v
```

## Capabilities

Admitted capabilities:

- [`media-transcript-acquisition`](capabilities/media-transcript-acquisition/CAPABILITY.md) — local-first SRT/VTT evidence normalization with optional YouTube caption adapters and explicit runtime-blocked receipts; live-source proof pending.
- [`social-media-insights`](capabilities/media-transcript-acquisition/SOCIAL_MEDIA_INSIGHTS.md) — Instagram/YouTube/TikTok/etc. URL adapter, optional local media+ASR+vision, source-grounded technical insight receipts; offline tests only, no live provider certification.
- [`visual-state-compare`](capabilities/visual-state-compare/CAPABILITY.md) — **VSC-0 synthetic CI validated (PR head)**: local-only deterministic PNG comparisons with synthetic tests, receipt and no semantic/click authority.
- [`playlist-link-extraction`](capabilities/playlist-link-extraction/CAPABILITY.md) — status `CORE_IMPLEMENTED_ADAPTERS_PENDING`
- [`agent-hook-runtime`](capabilities/agent-hook-runtime/CAPABILITY.md) — status `CORE_IMPLEMENTED_CURSOR_ADAPTER_DIAGNOSTIC_ONLY`; separates JSON-stdio host transport/schema proof from consumer policy and emits privacy-safe runtime receipts.
- [`social-publication`](capabilities/social-publication/CAPABILITY.md) — status `PROGRAM_DESIGN_PROTOTYPE_PROVEN`; approval-bound, provider-neutral text publication with a LinkedIn adapter prototype. Live OAuth/network publication remains unproven.
- [`document-formatting`](capabilities/document-formatting/CAPABILITY.md) — status `COMPILER_IR_PROTOTYPE_PROVEN_GOOGLE_DOCS_PLAN_ADAPTER_PROVEN`; reusable consumer profiles plus deterministic semantic compilation to provider-neutral IR and a fail-closed Google Docs adapter plan.
- [`ghidra-bootstrap`](capabilities/ghidra-bootstrap/CAPABILITY.md) — status `CORE_IMPLEMENTED_WINDOWS_HOST`; deterministic agent-free Ghidra download/verify/install plus non-interactive `USER_AGREEMENT=ACCEPT` (same gate as GUI **I agree**).
- [`windows-silent-scheduled-task`](capabilities/windows-silent-scheduled-task/CAPABILITY.md) — status `CORE_IMPLEMENTED_WINDOWS_HOST`; reusable `pythonw.exe` + Hidden Task Scheduler registration/classification so consumer repos stop forking noisy console cron. Live `--apply` is operator-gated; synthetic fixtures prove CI.
- [`entire-local-continuous`](capabilities/entire-local-continuous/CAPABILITY.md) — status `CORE_IMPLEMENTED_OFFLINE_ADMISSION`; Entire + silence admission for Actions-optional AFK continuous development. Live Entire enable and fullscreen certification remain separate gates.

Windows silent scheduled task:

```powershell
python capabilities/windows-silent-scheduled-task/silent_cron.py resolve-pythonw
python capabilities/windows-silent-scheduled-task/silent_cron.py classify-fixture `
  --fixture capabilities/windows-silent-scheduled-task/fixtures/schtasks-list.pythonw.fixture.txt
python capabilities/windows-silent-scheduled-task/silent_cron.py render `
  --registry capabilities/windows-silent-scheduled-task/fixtures/registry.synthetic.v1.json `
  --job-id demo_tick `
  --repo-root capabilities/windows-silent-scheduled-task
```

Seam review: [docs/WINDOWS_SILENT_SCHEDULED_TASK_SEAM_REVIEW.md](docs/WINDOWS_SILENT_SCHEDULED_TASK_SEAM_REVIEW.md). Consumers keep their own tick scripts and registries; Automation owns silent launch/register/classify.

Ghidra bootstrap (Windows):

```bat
Bootstrap-Ghidra.cmd
Bootstrap-Ghidra.cmd -InstallRoot D:\tools
```

Default install root: `%LOCALAPPDATA%\Automation\ghidra-bootstrap\tools`. Synthetic agreement proof:

```powershell
pwsh -File capabilities\ghidra-bootstrap\Prove-GhidraBootstrap.ps1
```

Document-formatting portable plan:

```powershell
python capabilities/document-formatting/plan.py \
  --profile capabilities/document-formatting/fixtures/consumer-profile.synthetic.v1.json \
  --output Outputs/document-formatting-plan.json
```

Consumers keep their own tokens, archetypes, exemplars, branding, and private provider identities; Automation owns the reusable orchestration contract.

Social-publication prototype:

```powershell
python capabilities/social-publication/prototype.py \
  --intent capabilities/social-publication/fixtures/text-intent.synthetic.v1.json \
  --mode success
```

See [P95 LinkedIn publication architecture](docs/P95_LINKEDIN_PUBLICATION_ARCHITECTURE.md) for the proved call stacks and live-launch boundary.

Reusable playlist core entrypoint:

```powershell
python capabilities/playlist-link-extraction/extract_links.py `
  --batch capabilities/playlist-link-extraction/fixtures/synthetic-observation-batch.v1.json `
  --output-json Outputs/playlist-link-artifact.json `
  --output-csv Outputs/playlist-link-artifact.csv
```

Adapters emit `playlist-link-observation-batch/v1`; the core owns normalization, ordered occurrences, unique-link aggregation, canonical JSON, and CSV projection.

Offline adapter surface:

```powershell
python capabilities/playlist-link-extraction/adapters/yt-dlp-json/adapt.py `
  --payload capabilities/playlist-link-extraction/adapters/yt-dlp-json/fixtures/sample-playlist.v1.json `
  --target-id target-a `
  --output-batch Outputs/playlist-link-observation-batch.json
```

Live provider execution remains unproven; status stays `CORE_IMPLEMENTED_ADAPTERS_PENDING`.

## Existing experiments

This repository began as a small automation sandbox. Early experiments may predate the current charter. New work should follow the charter rather than treating historical layout as the architectural model.


### Portable slide-flow compiler

`capabilities/slide-flow-compiler/` turns explicit semantic workflows and style-token profiles into deterministic editable slide geometry and a **side-effect-free Google Slides request plan**. It does not connect to, overwrite or visually certify a live presentation. Start with [the capability contract](capabilities/slide-flow-compiler/CAPABILITY.md), then run `node --test capabilities/slide-flow-compiler/tests/test_compile.mjs`. Operational sources, private links and preferred-style registries stay consumer-owned.


### Cross-repository scheduled-task silence evidence

The existing [Windows silent scheduled task capability](capabilities/windows-silent-scheduled-task/CAPABILITY.md)
also provides a read-only, versioned `audit-evidence` command covering
launcher class, Hidden metadata, due-time console/focus observation,
child/fullscreen certification and separate functional result state.

```powershell
python capabilities/windows-silent-scheduled-task/silent_cron.py audit-evidence `
  --input capabilities/windows-silent-scheduled-task/fixtures/silence-evidence.synthetic.v1.json
```

Consumers provide evidence snapshots; they do **not** install an additional
cron daemon or duplicate the classification implementation. The audit does
not query or change Task Scheduler, and a reported `SILENT_CERTIFIED` state
does not authenticate the source proof receipt.


### SILENT_BACKGROUND process-chain enforcement

The same Windows scheduled-task capability now exposes opt-in Python
`core/silent_background.py` and Node
`adapters/node/silent_background.cjs` execution classes, a private
`automation.silent-background/v1` receipt contract, and a read-only
`preflight` gate for reinstall/update registries.

```powershell
python capabilities/windows-silent-scheduled-task/silent_cron.py preflight `
  --registry capabilities/windows-silent-scheduled-task/fixtures/registry.synthetic.v1.json `
  --repo-root capabilities/windows-silent-scheduled-task
```

Existing Task Scheduler triggers, AFK clocks, in-app timers and job logic are
preserved. The contract fails closed on interactive child operations; it does
not silently uninstall, disable or change tasks. Consult the
[capability guide](capabilities/windows-silent-scheduled-task/CAPABILITY.md)
before consuming it from another repository. Launcher compliance, due-time
observation, child-process proof, fullscreen focus and job success are separate.
