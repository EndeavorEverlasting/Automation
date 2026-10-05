# Harness Shape Sampling + Certification Plan (2026-10-04)

Status: OWNER IMPLEMENTATION COMPLETE, MERGE PENDING.

## Execution frame

- reusable owner: `EndeavorEverlasting/Automation`
- capability: `capabilities/agent-hook-runtime` (primary), `capabilities/local-agent-readiness` (secondary)
- consumer incident: `EndeavorEverlasting/TokenCorridor` Cursor continuity
- Automation floor: `main@9157215fc6b976ae1fa2f25d8498652ea5eaa478`
- current owner branch: `feat/harness-shape-sampler-certification-20261004`
- worktree: `C:\Users\pa_rperez26\AppData\Local\Temp\opencode\automation-hss-20261004`
- overlapping open PRs: #18 owns `capabilities/agent-runtime-fabric/**`, shared `README.md`, `.github/workflows/validate.yml`; #20 owns `docs/*.md` and `docs/plans/HOOK_PROTOCOL_FABRIC_P04_P95_P97_2026-10-04.*`
- collision rule: this lane touches none of the above. The sampler does not require a new CI job or a `py_compile` entry; it is exercised through unittest discovery.

## Mission

Give the owner a deterministic, privacy-safe way to **sample** hook shapes against the versioned profile registry and **certify** a host-shape binding, so that:

- lifecycle eligibility is derived, never asserted;
- a `PROSPECTIVE` profile can never be reported as auto-switch eligible;
- an `ACTIVE` regression degrades explicitly instead of silently falling through to a candidate;
- a happy-path sweep cannot be reported as success;
- stale bindings cannot authorize current auto-switching;
- a receipt never carries prompt text, session ids, workspace paths or payload values.

## Why now

TokenCorridor's Cursor workstation-readiness lane is blocked behind a consumer-side acceptance that needs an owner-side proof of shape lifecycle safety. This lane produces that proof in Automation so Cursor work in TokenCorridor (HP-6) has a stable dependency to pin later. HP-6 itself is explicitly out of scope here.

## Shape model

Dimensions are orthogonal. Routing eligibility is derived by `max_routing_eligibility()` from the other four plus `compatibility_admitted`.

```text
catalog_state:   LEGACY | ACTIVE | PROSPECTIVE
validation_state: UNTESTED | PASS | FAIL | BLOCKED
proof_class:     DOCUMENTED | SYNTHETIC | SHADOW_OBSERVED | LIVE_CANARY
routing_elig:    OBSERVE_ONLY | CANARY_ELIGIBLE | AUTO_SWITCH_ELIGIBLE | RETIRED
rollout_stage:   DISCOVERED -> PROFILED -> SYNTHETIC_PROVEN
                 -> SHADOW_OBSERVED -> CANARY_ACCEPTED -> AUTO_SWITCH_ELIGIBLE
```

## Enforced invariants

- `PROSPECTIVE + PASS` stays `PROSPECTIVE`, ceiling `CANARY_ELIGIBLE`.
- `PROSPECTIVE + FAIL` retained with `retained_negative_evidence: true`, `OBSERVE_ONLY`.
- `ACTIVE + FAIL` -> `UNKNOWN_SHAPE` / `ACTIVE_SHAPE_REGRESSION`, `degraded: true`, no silent prospective fallback; observed candidate IDs still reported.
- `LEGACY + PASS` only via an explicitly `compatibility_admitted` record.
- `proof_class=DOCUMENTED` can never yield `validation_state=PASS`.
- `SYNTHETIC` proof can never yield `AUTO_SWITCH_ELIGIBLE`.
- Host-family mismatch is never a candidate.

## Deliverables

| artifact | role |
| --- | --- |
| `capabilities/agent-hook-runtime/core/protocol_fabric.py` | lifecycle vocabulary, validation, derived eligibility, lifecycle-aware negotiation |
| `capabilities/agent-hook-runtime/core/shape_sampler.py` | matrix loader, case evaluators, binding certification, deterministic receipt |
| `capabilities/agent-hook-runtime/sample_shapes.py` | CLI entrypoint, exit 0 iff receipt `PASS` |
| `capabilities/agent-hook-runtime/fixtures/shape-sampling-matrix.synthetic.v1.json` | 30 cases + 4 binding certifications, 16 positive / 18 negative |
| `capabilities/agent-hook-runtime/schemas/shape-sampling-receipt.v1.json` | receipt contract, asserted structurally (no third-party validator) |
| `capabilities/agent-hook-runtime/profiles/current.v1.json` | `lifecycle_model` + 3 new profiles (prospective pass, prospective rejected, legacy) |
| `capabilities/local-agent-readiness/core/readiness.py` | independent per-harness availability classifier |
| `capabilities/local-agent-readiness/schemas/harness-availability.v1.json` | availability contract |
| `tests/test_agent_hook_shape_sampler.py` | 19 sampler/receipt/registration tests |
| `tests/test_agent_hook_protocol_fabric.py` | 28 tests (14 existing + 14 lifecycle/negotiation) |
| `tests/test_local_agent_readiness.py` | availability class (12) + symlink fixture fix |

## Privacy contract

Receipts retain `shape_sha256`, `field_count`, `field_types`, `content_persisted: false`, profile ids and state only. Prompt text, session/conversation ids, workspace paths, attachments and payload values are never written; the test suite asserts this by scanning the serialized receipt for the fixture payload values.

## Proof ceiling

This lane proves deterministic, synthetic, privacy-safe sampling and lifecycle derivation. It does not advance any profile's `rollout_stage` or `proof_class`, and it does not certify that any installed host accepted a response. Only live canary evidence can do that.

## Validation performed

1. `python -m unittest tests.test_agent_hook_shape_sampler` -> 19/19
2. `python -m unittest tests.test_agent_hook_protocol_fabric` -> 28/28
3. `python -m unittest tests.test_local_agent_readiness.HarnessAvailabilityTests` -> 12/12
4. `python -m unittest discover -s tests` -> full suite
5. `python -m py_compile` on every touched module
6. `git diff --check` / `git diff --cached --check`
7. `python capabilities/agent-hook-runtime/sample_shapes.py --output <path>` -> `PASS`, `SENSITIVE`

## Boundaries

- TokenCorridor is untouched. HP-6 is not executed.
- PR #18 and PR #20 files are untouched.
- Cursor remains an installed runtime under test, not an implementation agent.
- OpenCode remains the current execution harness; Automation remains the reusable owner.
