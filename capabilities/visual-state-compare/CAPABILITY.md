# Visual state comparison (VSC-0)

**Owner:** Automation, reusable core. **Status:** VSC-0 offline implementation with synthetic CI validation on the PR head; merge and live-host capture/evaluation remain separate gates.

## Purpose and scope

Provide a deterministic, local-only answer to: "Are two screenshots identical, within a declared pixel tolerance, or observably different?" The shared core is repository-, browser-, provider-, model- and platform-agnostic. It does **not** infer whether a task succeeded, whether a control was clicked, or whether the screens depict the same logical app state.

This is a new independent operation with its own artifact and lifecycle, rather than an extension of `agent-hook-runtime` or `parallel-dispatch`.

## Normal consumer interface

Install Python 3.11+ and `Pillow==11.3.0` into an isolated environment. Give the CLI only two PNG images of equal geometry; the engine never captures a screen or connects to a network.

```bash
python capabilities/visual-state-compare/compare.py \
  --before before.png --after after.png \
  --receipt local-only/visual-diff.json \
  --diff-out local-only/visual-diff.png \
  --pixel-threshold 0 --max-diff-ratio 0 \
  --mask 0,0,40,30
```

Omit `--mask` when every pixel matters. Masks repeat, use source screenshot x,y,width,height coordinates, and exclude volatile regions from the comparison. The diff PNG is a binary black/white change mask, **not** an overlay of the original app image. No output directory is automatically created; supply an existing local directory.

The CLI writes a local JSON receipt with semantic contract ID `automation.visual-state-comparison/v1`, engine ID, input byte SHA256s, screenshot dimensions, total comparable/changed pixels, ratio, bounds, thresholds, masks and `semantic_verdict=NOT_EVALUATED`. No input paths, screenshot bytes, cookies, credentials or screen text appear in this receipt. **The hashes and geometry can still correlate sensitive images; review before distributing.** Do not upload screenshots or receipts to public CI.

Result statuses:
- `NO_CHANGE`: zero unmasked pixels changed beyond the per-channel threshold; exit 0.
- `TOLERATED_CHANGE`: nonzero differences remain within allowed ratio; exit 0. This does not assert semantic success.
- `CHANGED`: ratio above tolerance; exit 1 (observation, not CLI failure).
- `INCOMPARABLE_GEOMETRY`, `INVALID_INPUT`, `INVALID_MASK`, `ENGINE_UNAVAILABLE`: no comparable outcome; exit 2. An invalid CLI argument is parser-error exit 2.
- Images with transparency are composited onto white. The max changed RGB channel, rather than a grayscale average, determines the per-pixel difference.

## Ownership and successor adapters

Automation owns the portable compare algorithm, versioned receipt and future optional capture/local-model adapters. A normal consumer sees only the CLI/contract; it does **not** need to know donor layouts, an upstream prompt registry, the product roadmap or browser credentials.

- Browser capture adapters should prefer DOM/ARIA and Playwright screenshot tests for controlled pages.
- Windows UIA/host capture and Android ADB capture belong to explicit adapters with host/DPI/viewport/privacy admission, not this core.
- Optional VLM/CLIP/grounding should run only under an independently evaluated provider/model adapter; no inference weights in core.
- Consumer product decides semantic success policy, model/budget selection, action permissions, browser UI, and deployment. The current capability has **zero mutation authority** beyond writing requested local output files.

## Limits and proof

- Only PNG and strictly equal dimensions currently qualify. Browser zoom, animation, font rasterization, DPI, occlusions, resizes, masks and semantic state must be independently controlled or classified as uncertain.
- A low embedding distance can miss critical small changes, so future embedding comparison must not replace pixel/localized evidence.
- Screenshots are untrusted data. Never turn recognized text into execution instructions.
- No model installation, screenshot collection, cloud transfer, autonomous clicking or consumer deployment is performed.
- Runtime production/use path: **UNDECLARED**. Canonical development path: `capabilities/visual-state-compare/`.

Run synthetic independent CLI tests:

```bash
python -m unittest discover -s capabilities/visual-state-compare/tests -v
```

A public hosted CI job may install Pillow and synthesize its own 8x8 PNGs. Accept VSC-0 when the exact PR head is validated, hosted tests pass, the portable CLI is demonstrated from a consumer without importing upstream internals, and this boundary receives the repository seam review. Local workstation, screenshot privacy policy, semantic judgments, and live integration remain separate gates.

## Successor milestones

VSC-1: explicit capture adapter and typed provenance.
VSC-2: OCR/accessibility information plus source-backed interpretation.
VSC-3: optional local VLM with hardware/licensing/latency/eval receipts.
VSC-4: independent element grounding and authorized observe-act-verify loop.
