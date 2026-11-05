# Canonical next-agent handoff — repository-handoff incubation

**Owner:** `EndeavorEverlasting/Automation`, `automation-repository-handoff/v1`
**Status:** IMPLEMENTED / CI VALIDATED / DRAFT PR — not merged or production adopted
**Parent objective:** Incubate repo-owned next-agent handoffs as a reusable Automation capability, replacing assistant recommendations to download ZIPs, duplicate host files, or manually copy code when authenticated repository writes should occur.

## Verified source and integration

- **Owned branch:** `feat/repository-native-handoff-incubation-20261105`
- **Review:** [Automation PR #45](https://github.com/EndeavorEverlasting/Automation/pull/45), draft, against `main`; no merge or deploy authorized by this task.
- **Last exact-head green suite baseline:** `e2ca3fffd084d26832ae329771e1c12c3b2ce099` (this handoff file may advance branch HEAD; resolve exact current ref before execution).
- **Windows and Ubuntu acceptance:** [Actions run 42120059139](https://github.com/EndeavorEverlasting/Automation/actions/runs/42120059139), both jobs SUCCESS.
- **Automation regression suite:** [Actions run 42120059164](https://github.com/EndeavorEverlasting/Automation/actions/runs/42120059164), main validation and Windows silent-cron parser SUCCESS.
- **ParallaxPort reference only:** [ParallaxPort PR #36](https://github.com/EndeavorEverlasting/ParallaxPort/pull/36), `harness/workflows/REPOSITORY_FIRST_HANDOFF.md`, unmerged stacked security PR. Do not copy its security implementation or override its active writer.
- **Upstream semantics:** [TokenCorridor P01 PR #309](https://github.com/EndeavorEverlasting/TokenCorridor/pull/309), draft. TokenCorridor still owns P-number bodies and their invocation catalog. Automation does not update/mirror prompt sources.

## Files committed in this capability

- `handoff.py` — Python standard-library `validate`, `render`, `write`, `verify`; accepts only a trusted packet and existing checked-out repo root. Exact branch/HEAD and SHA256 preimage guard, no clone, no patch bundle, no Git add/commit/push.
- `capability.v1.json` — declared portable ownership, environments, proof states and forbidden operations.
- `schemas/handoff.v1.schema.json` — stable semantic packet.
- `fixtures/synthetic-handoff.v1.json` — synthetic fixture; never claim it is live evidence.
- `tests/test_handoff.py` — nine behavioral/adversarial tests, including two independent consumer Git repositories.
- `CAPABILITY.md` — supported invocation, usage and provider proof ceiling.
- `docs/REPOSITORY_HANDOFF_SEAM_REVIEW.md` — owner/consumer-boundary analysis and separate implementation, adversarial and consumer-proof review lenses.
- Root README/CONTRIBUTING, `tests/test_repository_handoff.py`, `.github/workflows/repository-handoff.yml` — discoverability and cross-platform regression gates.

## Distinct Trifecta review lenses

1. **Build/owner:** portable operation admitted in Automation; no consumer business rules in core. Owner decision documented.
2. **Attack/failure:** branch mismatch, stale HEAD, default branch, changed old file, unsafe path, symlink and private locator all refuse. Passing checks require nonempty evidence strings.
3. **Consumer/proof:** isolated two-repo portability canaries pass on Windows/Linux. Main Automation suite is green at the recorded code commit. These are independent review/test lenses, not fabricated external agent sessions.

## Immutable boundaries

- The handoff remains in the consumer repository's **existing, designated tracked path**. Do not hand the operator an archive, installer, duplicate checkout or local-file transfer instructions.
- The generic writer produces `WRITTEN_WORKTREE_NOT_COMMITTED`; local verify produces `LOCAL_CONTENT_MATCH_NOT_REMOTE_PROOF`. Neither status is a pushed commit, approved PR, deployed service, or live agent proof.
- Provider authentication, remote write CAS/branch lease, commit/readback, agent dispatch and merge/deployment authorization belong to a consumer/provider adapter.
- Never silently copy private provider/Drive content into Automation's public repository, or reinterpret reference examples as authority.
- Protect other contributors' work, default branch, account settings, DNS, scheduler and production runtime.

## First unproven gate and exact successor actions

1. Refresh PR #45's head, scope and current `main`; confirm no conflicting writer and exact code/test statuses after this handoff commit.
2. Review the contract for security, portability, and consumer input simplicity. Run:
   `python -m unittest discover -s capabilities/repository-handoff/tests -p 'test_*.py' -v`
   `python -m unittest discover -s tests -p 'test_repository_handoff.py' -v`
3. A future authorized **second real consumer** must name its own existing canonical handoff path, branch, exact HEAD and remote provider writing method. Implement a thin authenticated provider adapter that uses the validated packet, checks existing remote file SHA/branch lease, commits to its owned branch and independently reads back SHA/content. Do not require any operator file-copy step.
4. Only after the real consumer/adaptor proof can the capability move beyond `INCUBATING`. Do not merge PR #45, change another repo, or claim ubiquitous live activation without appropriate authority.

**Proof ceiling:** committed to the Automation feature branch; latest code baseline passed cross-platform CI and original Automation validation; no provider-backed remote write via this new capability, second real consumer adoption, merge or production activation has been proven.
