# Repository-owned handoffs — seam review and P01 incubation

**Authority split:** TokenCorridor owns P01's prompt identity and its canonical body. Automation owns `automation-repository-handoff/v1`: packet validation, deterministic content, safe local authoring and receipts. Each consuming repository owns its handoff path, content, branch, commits, PR, merge and deployment decisions. No prompt mirror, no change to public/private access boundaries.

**Origin example:** [ParallaxPort PR #36](https://github.com/EndeavorEverlasting/ParallaxPort/pull/36), `harness/workflows/REPOSITORY_FIRST_HANDOFF.md`. It demonstrated a failure pattern where agent-produced ZIPs and duplicate host copies replaced actual repository writes. The stable reusable seam is not that file's path or its security instructions; it is **one authoritative, tracked, evidence-bounded successor handoff per consumer**.

## Consumer Knowledge Test

Normal consumer knows only:

1. `automation-repository-handoff/v1` packet schema and validation endpoint.
2. Its own existing repository identity, owned branch and exact Git HEAD.
3. Its own canonical handoff relative path and authorized old-file hash when replacing.
4. Work/forbidden scope, actual evidence and one next executable step.
5. Its own provider adapter for durable commit and independent remote readback.

Consumer must **not** know ParallaxPort source layout, TokenCorridor's registry, donor provenance, the name of any other operator machine, or an Automation internal module. The helper accepts a packet and explicit existing worktree; private connector credentials remain outside the public packet.

## Boundary decisions

| Question | Disposition |
| --- | --- |
| Is this just a Git backup or continuity idea? | No. `git-portability` owns history bundles; `idea-work-continuity` owns discovered work obligations. This capability owns the *structured successor handoff*, safe write, and proof ceiling |
| Is it one product's handoff template? | No. Source and security details remain in that product; isolated two-repo canary demonstrates config-only adaptation |
| Does Automation choose the writer / PR / next agent? | No. Runtime placement, lease, provider auth and agent dispatch remain upstream/adapter decisions |
| What prevents local export becoming a second authority? | A single configured destination, explicit old SHA256 preimage, exact branch/head, repository-root assertion; local receipts cannot claim remote persistence |
| Does it install on all machines automatically? | No. Incubating only; agents may invoke an already-available capability. Consumer adoption and live-host certification are separate |
| How does it fail? | `REFUSED` for unsafe input/state; `WRITE_BLOCKED` is an agent-recorded provider refusal, never an instruction to ask the operator for an archive |

## Isolated consumer canary

`python -m unittest discover -s capabilities/repository-handoff/tests -v`

The test creates two independent disposable Git repositories with distinct repository identities and canonical destination paths. It proves deterministic Markdown rendering and exact path isolation, then rejects default branch writes, stale head, preimage mismatch, symlink escape, traversal, secret-like strings and unsupported proof claims.

## Recurrence prevention and next adoption

- The new packet is versioned and format-neutral (JSON input, Markdown projection). It does **not** own P01 semantics.
- Root `README.md` and `CONTRIBUTING.md` route fresh agents here. CI runs focused tests.
- ParallaxPort's existing handoff is a real-world reference and **must not be replaced** by this generalized fixture. This incubation adds no required ParallaxPort dependency and avoids overwriting its active PR.
- Certify a provider-backed direct commit/readback on a second real consumer, then tighten adapter authority/lease semantics if needed. Cross-platform Python+Git CI is syntactic/runtime proof only, not authenticated agent fleet proof.

## Three independent review lenses (Trifecta discipline)

1. **Implementation/owner:** does the capability serve an independent cross-repo operation without copying business rules?
2. **Adversarial/negative:** can it write outside a checkout, erase an unknown handoff, claim a false status, or expose a private locator?
3. **Consumer/proof:** can two clean synthetic consumers use it without knowing upstream topology, and is remote readback explicitly separate?

These are review/test lenses. No three external agent sessions or provider dispatches are claimed without actual session receipts.
