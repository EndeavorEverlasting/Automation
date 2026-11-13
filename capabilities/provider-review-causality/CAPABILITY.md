# Provider review causality — evidence before outcome

**Identity:** `automation.provider-review-causality/v1`.
**Canonical implementation:** `capabilities/provider-review-causality/classify.py`.
**Provider adapter:** `adapters/github_codex.py` (optional read-only GitHub CLI).
**Tests:** `tests/test_provider_review_causality.py`.
**Contract:** `contract.v1.json`.
**Maturity:** reusable source classifier, synthetic adapter proof; live provider/host certification outstanding.

## Exact user-visible correction

A hosted code reviewer can report **FAILED** because its execution was blocked by a quota. That proves neither that the source code failed review nor that it passed. Keep independent dimensions:

| Dimension | Example | Meaning |
| --- | --- | --- |
| Raw provider status | FAILED | A provider report, not a judgment of code quality |
| Execution state | NOT_COMPLETED | No completed review was established |
| Failure cause | USAGE_QUOTA | Machine-code or provider-message evidence identifies capacity |
| Review result | NOT_ASSESSED | No substantive reviewer verdict has been established |
| Reported findings | Empty or explicit inline finding IDs | Distinct factual evidence of specific comments; not necessarily verified defects |
| Candidate alignment | CURRENT vs STALE | Is this attempt for the commit being evaluated? |
| Code-defect verification | NOT_ESTABLISHED | Never inferred from provider status or review prose |

**Required wording:** “Codex could not complete this review because its usage limit was reached; no Codex code-defect conclusion was established.” If another reviewer reported real findings, report them separately with their own provider and evidence IDs. Do not infer “no defects” from an unfinished review, or “defects found” from a failed execution.

## Run against synthetic evidence (works without GitHub or an account)

From repository root on Python 3.11+:

```sh
python capabilities/provider-review-causality/classify.py --input capabilities/provider-review-causality/fixtures/codex-quota.synthetic.v1.json
python -m unittest tests.test_provider_review_causality -v
```

The CLI prints a deterministic `automation.review-causality-receipt/v1` JSON result with typed status, exact current/stale commit relation, reason evidence IDs, separately counted reported findings, and next action. No uploads, mutation, tokens, credentials or provider retries.

## Read current GitHub Codex review evidence (optional)

When `gh` is installed and already authenticated for the target repository:

```sh
python capabilities/provider-review-causality/classify.py --repo OWNER/REPOSITORY --github-pr 50
```

This read-only adapter obtains the PR head and GitHub issue/inline comments using bounded `gh api` GET operations. It accepts provider notices **only** from known Codex review bot identities and binds a usage notice to its nearby review-attempt summary on the same PR. It interprets the source bot's `codex-review-state:v1` marker for review execution status and SHA. It **does not treat** the marker's `has_any_findings: true` as proof of defects; only individually addressable inline comments are counted. Other bots' review findings are outside this Codex adapter; the provider-neutral input format can represent their separately owned attempts. If the reviewer entry is absent, old, or the source is unavailable, return an explicit failure or STALE, not “review passed” or “code defects.”

Raw provider comments stay in volatile process memory and are not echoed into the output. The classifier includes evidence IDs and a fingerprint of normalized inputs, not the bodies. The result is evidence **classification**, not merge approval, code quality certification, or a substitute for an independently verified PR diff.

## Failure and privacy rules

- A machine `usage_limit_exceeded` (or comparable quota code) is direct failure-cause evidence. A specifically recognized usage-limit statement from a provider-origin notice with an evidence ID is secondary evidence. A developer/user quote cannot assign provider cause.
- If cause is ambiguous, report `UNKNOWN`. If a review failed with no individually identified findings, report `NOT_ASSESSED` — do not infer code defects or certify no defects.
- A GitHub workflow that never allocated a runner and completed zero steps is `NOT_STARTED`, not a failed code test. An executed test that ends non-success is an execution failure requiring diagnostic evidence, not proof of a source defect.
- When `commit_sha != candidate.sha`, mark `STALE` and demand new source data. Old review evidence never certifies the new head.
- An explicit `no_findings_attested` from a completed review is `NO_FINDINGS_REPORTED`, not a blanket code-quality guarantee.
- No automatic retry, sleep, scheduler change, account upgrade, security bypass, provider write, PR merge, review approval, or forced provider access.
- Never include private employee/client/ticket artifacts or workstation paths in public fixtures.

## P141 / Sixth Gear strategic convergence

**Compared and falsified four directions:**

1. Rebuild review-completion orchestration in Automation — **REJECTED**. Existing consumer-side completion and promotion policy remains authoritative.
2. Add only a prompt reminding agents that failures may be quotas — **WEAKENED**. Does not prevent the next instance from incorrectly classifying a real failed review.
3. Build a narrowly scoped provider-causality classification primitive with synthetic and real-adapter seams — **SURVIVES, SELECTED**. Reusable across agent reviews and CI admission without taking provider authorization or consumer review policy.
4. Rework downstream domain-specific review and operations policy — **DEFERRED**. Existing consumers already separate provider capacity, review acceptance and real runtime proof. No private data should migrate.

P95 seam: raw provider event → provider-specific normalizer → immutable-candidate attempt → generic classifier → sanitized receipt → consumer policy owner. P82 hypothesis: quota notices can be identified without treating them as source findings, even when the provider summary contains a misleading `has_any_findings` flag. Falsify using the offline fixture and negative cases (user quotes, stale SHA, different reviewers, missing notices). P08 actual local GitHub CLI and cross-consumer live adoption remain **unproved** until executed; synthetic test evidence cannot claim them. P07 and P124 retain one canonical source/classifier, a thin adapter, and existing Automation CI tests without spawning another reviewer or scheduler.

## Adoption boundaries and next owner

- **Existing private review-completion owner:** retain required-vs-advisory checks, review actions and promotion authority. Ingest causality as evidence only, not as a second completion policy. Defer adoption while its exact owning PR is active; track the collision inside the private owner.
- **Game/runtime consumers:** maintainer approval and live gameplay proof remain separate dimensions.
- **Private operational consumers:** dated provider quota/fallback decisions remain in their own owner. No client artifacts or private identifiers are imported.

**Proven vs next:** repository implementation + offline regression suite are the first useful milestone. Test current GitHub readback using the direct CLI on an authorized host, then have the existing private review-completion owner consume the versioned result after its overlapping change is reconciled. No automatic downstream write, installation, deployment, or merge is claimed.
