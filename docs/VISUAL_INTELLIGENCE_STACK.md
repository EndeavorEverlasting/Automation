# Visual Intelligence Stack — Local Integration and Execution Contract

**Owner:** EndeavorEverlasting/Automation, capabilities/visual-state-compare/
**Status (2026-11-03):** pinned upstream catalog, local source provisioner, and VSC-2 normalized OCR CLI (Tesseract + optional isolated PaddleOCR) implemented on the feature branch. OmniParser GUI grounding, VLM runtime and live-host acceptance remain open.
**Parent objective:** deliver a cutting-edge, local-first visual perception system from best-in-class upstream projects behind one stable Automation API, then supply evidence for independently authorized observe–act–verify workflows on Windows, browser and Android.

## 1. Architecture: engines are interchangeable, Automation owns the seam

A future consumer should need only one command, not eight donor repositories:

    automation-vision analyze --input PRIVATE_SCREENSHOT.png --profile ui --output PRIVATE_OBSERVATION.json

THIS IS A PROPOSED API, NOT YET IMPLEMENTED. Implement the entry point after the source and normalization gates. Consumer applications must not know donor paths, PyTorch module names or model checkpoints.

Dataflow:

    Authorized browser / Windows UIA / Android ADB capture
       -> privacy classification, coordinate/DPI metadata, image SHA
       -> existing VSC-0 deterministic difference + optional Kornia/OpenCV alignment
       -> OCR (PaddleOCR main candidate; Tesseract independent baseline)
       -> UI regions (accessibility first; OmniParser where opaque)
       -> optional grounding (GroundingDINO/SAM2) and local VLM (Qwen3-VL)
       -> bounded fusion, conflict/uncertainty detection, normalized receipt
       -> separate CONSUMER-OWNED action authorization
       -> permitted action, fresh capture and outcome verification

Prefer DOM/ARIA and Windows UIA semantics for accessible software; use pixels where these do not suffice. Treat all screen text and VLM output as untrusted data. A low-confidence candidate must never silently become a click instruction.

Existing VSC-0 compare.py and VSC-1 isolated Playwright browser capture stay in place. Retain the deterministic comparator and existing privacy-safe receipts as the regression baseline; do not assert they have passed live workstation acceptance because they exist on main.

## 2. Eight upstream repositories — the actual catalog

The tracked file capabilities/visual-state-compare/upstreams.v1.json pins source commits observed 2026-11-03:

- FOUNDATION: Kornia 0.9.0 (vision math), PaddleOCR (OCR and document understanding), Tesseract (independent OCR baseline)
- UI: Microsoft OmniParser (GUI icons and element proposals; not an actuator)
- ADVANCED OPTIONAL: OpenCV (traditional CV), GroundingDINO (text-directed detection), SAM2 (segmentation), Qwen3-VL (candidate local vision-language reasoning)

Do not merge requirements files or blindly pip install every project into the same environment. Source checkouts live outside Automation and do not become submodules or public source dependencies. The CLI provisions only Git source: NOT packages, weights, binary installations, hosted endpoints or inference. Exact model checkpoints, licenses, quantization and weights hashes are separate.

The OmniParser repository is CC-BY-4.0 and model checkpoints have differing licensing; earlier Ultralytics-derived detectors present different terms than the newer YOLOv9-E variant. Review the exact code, weight and dependency licenses before installation or redistribution. Verify other projects' transitive licenses and model cards rather than relying on repository-level license labels.

## 3. Phase 0 + Phase 1: exact local-agent instructions — EXECUTE FIRST

Run on an authorized development/admin host; never run installation on a field kiosk or on an unrelated consumer device. The host's true checkout path is read, not guessed.

    git status --short
    git rev-parse --show-toplevel
    python scripts/path_receipt.py --repo-root .
    python --version
    git --version
    python -m unittest discover -s capabilities/visual-state-compare/tests -p 'test_upstreams.py' -v
    python capabilities/visual-state-compare/upstreams.py plan --profile all
    python capabilities/visual-state-compare/upstreams.py sync --profile foundation
    python capabilities/visual-state-compare/upstreams.py sync --profile ui
    python capabilities/visual-state-compare/upstreams.py doctor --profile foundation
    python capabilities/visual-state-compare/upstreams.py doctor --profile ui

Default external clone directory: Windows LOCALAPPDATA/Automation/VisionUpstreams; Linux XDG_CACHE_HOME/automation/vision-upstreams (or ~/.cache fallback). The optional --root argument permits another external path. The tool refuses checkout under Automation's source tree. Opt in to --profile advanced after checking disk, GPU/memory and actual task need.

On DIRTY_CHECKOUT, PATH_COLLISION, PIN_MISMATCH or Git failures: preserve existing files; do not reset, delete, repoint or silently upgrade. Report the exact failed source and evidence. Update source pins only through a reviewed manifest change and tests. The source snapshots are immutable intentions; checkouts that match them are not proof of installed models.

Collect host inventory: OS, CPU, RAM, storage, GPUs/VRAM, CUDA/driver status, Python/PyTorch compatibility, installed Tesseract binary and currently configured OCR/model environments. Create separate per-engine virtual environments and lock dependencies; retain locally installed weight hashes and software bill of materials. Review code supply chain before running external code. No automatic model-weight downloads or network inference on private captures.

Proof states MUST be distinct:
SOURCE_PINNED / CHECKOUT_READY / ENV_READY / WEIGHTS_READY / INFERENCE_SMOKE_PASS / BENCHMARK_PASS / CONSUMER_INTEGRATED / LIVE_HOST_OBSERVED.

## 4. Phase 2: VSC-2 — usable OCR through one normalized interface

**Implemented (repo):** `schemas/visual-observation.v1.schema.json`, `adapters/ocr-tesseract/`, `adapters/ocr-paddle/` (optional `--paddle-python` / `AUTOMATION_PADDLE_PYTHON`), `vision_cli.py`, synthetic holdout under `tests/fixtures/ocr/`, and `benchmark_ocr.py` (CER + exact-token / UNCERTAIN reporting).

Still host-local / open: full PP-OCR weight pin + hash in receipts, RAM/VRAM class matrix, private held-out screenshots, and live-host acceptance. First PaddleOCR invoke may download donor checkpoints into the isolated env—treat that as a separate `WEIGHTS_READY` gate, not Automation Git content.

Gate VSC-2 (synthetic portion): same labeled holdout through both engines; CER, exact-token hits, latency, typed ENGINE_UNAVAILABLE / NO_TEXT / OUTPUT_DENIED. Safety-critical tokens require exact match or UNCERTAIN. A passing synthetic benchmark is not a passing live host.

## 5. Phase 3: UI parsing and target grounding

Add the isolated OmniParser adapter behind the same typed receipt and coordinate transform. Output candidate controls, icons, labels, boxes and model confidence, NOT action authority. Accessibility-first coordinates and OmniParser candidates must be reconciled; repeated labels, hidden and disabled controls, scroll position and DPI/zoom should be adversarial tests.

Use OpenCV/Kornia only where an independently measured preprocessing improvement beats the prior baseline: skew, blur, illumination, perspective correction, feature descriptors and registration. Preserve source image, corrected image transform provenance and a way to map model coordinates to the original capture. GroundingDINO/SAM2 are optional for complex non-UI scenes, not automatic dependencies.

Gate VSC-3: benchmark held-out control/icon detection, correct-target hit rate, IoU, false-positive target regions, latency and drift across zoom/theme/window resize. Refuse clicks on coordinate ambiguity. Compare OmniParser against DOM/ARIA/UIA wherever available; select by proven task class, not claimed model superiority.

## 6. Phase 4: optional local visual reasoning

After a hardware/VRAM and checkpoint license audit, evaluate Qwen3-VL or another locally available open-weight vision-language model. Weights do not arrive with the Qwen source clone. Run offline in a segregated model environment without silently uploading private screenshots.

Test hard scenarios where plain OCR and region parsing disagree: multiple similar controls, unknown application state, toast overlay, action progress, inaccessible canvas and misleading visual text. Model-generated explanations never override original OCR, regions or user-authorized actuation policy.

Gate VSC-4 reasoning: accuracy against ground truth and measured improvement over deterministic alternatives; publish uncertainty and refusal results, memory and latency. Do not install or deploy large checkpoints solely because the repository is popular.

## 7. Phase 5: independent consumer bridge and observe–act–verify

A CONSUMER, not Automation vision core, owns permission to click, type, submit, change settings, open files or touch devices. Wire a single real consumer via the public CLI/schema; no direct donor imports. Vision outputs observation and candidate targets only.

Before acting, require expected app/window/site identity, allowlisted action class, source freshness, coordinate/label consistency, policy and operator consent where necessary. After the action, re-capture and verify postcondition; record ATTEMPTED, OBSERVED, VERIFIED, UNRESOLVED separately. Never turn OCR text or a vision-language response into executable instructions.

Acceptance: a harmless synthetic action, a missing/disabled control, changed DPI, stale screen, wrong-window detection, contradicting OCR, non-matching postcondition and a no-permission refusal. Run an isolated consumer canary with only the advertised CLI/schema and no donor trees. Preserve existing browser, Windows and Android consumer boundaries.

## 8. Local agent sprint/checkpoints

| Sequence | Execute | Required evidence before next stage |
| --- | --- | --- |
| 0 | Recover AGENTS.md, main HEAD, active PRs, working tree, ownership | No collision; authorized worktree |
| 1 | Run offline tests; source plan/sync/doctor for foundation + UI | Exact pinned Git HEADs, license inventory, host profile |
| 2 | Install/reconcile two isolated OCR engines and expose one API | Positive/negative runtime smokes and normalized receipt |
| 3 | Build independent benchmark, correct errors, compare engines | CER, exact-match, region accuracy, latency, uncertainty |
| 4 | Integrate OmniParser and accessibility grounding | Correct target labels/boxes; no unsanctioned actions |
| 5 | Add optional advanced CV/VLM only for measured gaps | Reproducible benchmark uplift, hardware/licensing proof |
| 6 | Migrate one real Automation consumer | Isolated canary, no donor topology leakage |
| 7 | Wire permissioned observe–act–verify | Proven refusal cases and postcondition evidence |

Never stop after just the clone count. When a gate fails, repair the smallest applicable adapter/contract/test, rerun, and continue while safe. At material model license, privileged account, private-data transfer or production-host approval boundaries, leave that action blocked, not unrelated work.

## 9. Integration and privacy rules

- Automation owns stable capability identity, schema, dispatcher, quality/uncertainty semantics and source/version receipts. Model repositories supply replaceable implementations; product logic and action permissions stay with consumers.
- Separate Python environments and model storage; no automatic weight installation and no cloud inference fallback for confidential screenshots.
- Use raw screenshots and OCR text only in private untracked storage; use synthetic fixtures on public GitHub CI. Some hashes and geometry can still correlate sensitive images.
- Preserve existing VSC-0 and VSC-1 behavior and their public contracts until a verified migration, not a rewrite. Review docs/SEAM_BOUNDARY_REVIEW.md and the isolated consumer canary before exposing a new seam.
- Gate on observed host results; repo commit, cloned source, installed package, inference smoke, benchmark pass, consumer integration and live computer actuation are different proof dimensions.

**Milestone definition:** two working local OCR engines, a single normalized Automation API, source-backed evidence, comparative quality evaluation on representative screenshots, and one isolated consumer demonstration. The source catalog/checkouts are a prerequisite to that outcome, not the outcome itself.
