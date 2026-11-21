# Repository-owned canonical handoff — incubation

**Contract:** `automation-repository-handoff/v1`
**Owner:** Automation `capabilities/repository-handoff/`
**Status:** INCUBATING — standard-library validator, renderer, safe existing-worktree writer and local verifier. Provider commit/PR/live certification is **not** part of this capability.

## Parent purpose

Every agent sprint should leave a *single canonical successor handoff in the owning repository* rather than providing an archive for the operator to download, unzip, duplicate, or copy to a machine. Ownership remains with the consumer repository. Automation incubates the reusable format, deterministic validation, safe local authoring seam, and proof vocabulary.

The ParallaxPort P124 handoff ([PR #36](https://github.com/EndeavorEverlasting/ParallaxPort/pull/36)) is the original reference consumer, **not** a required dependency or source template. Its security- and website-specific content stays in ParallaxPort. TokenCorridor is the sole owner of P01 prompt identity and the canonical prompt body. This capability never alters a prompt registry.

## Interfaces

- `capability.v1.json` — supported environments, operation and ownership.
- `schemas/handoff.v1.schema.json` — semantic packet shape; Python validator adds path, privacy, evidence and Git checks.
- `fixtures/synthetic-handoff.v1.json` — safe, portable sample; **do not write it to a live repo unchanged**.
- `handoff.py` — `validate`, `render`, `write`, `verify`.
- `tests/test_handoff.py` — isolate/concurrency/preimage/privacy and two-consumer canaries.
- [`HANDOFF.md`](HANDOFF.md) — canonical in-repository next-agent continuation, current PR/proof ceiling and executable successor gates.

Example read-only operations:

```sh
python capabilities/repository-handoff/handoff.py validate --packet capabilities/repository-handoff/fixtures/synthetic-handoff.v1.json
python capabilities/repository-handoff/handoff.py render --packet capabilities/repository-handoff/fixtures/synthetic-handoff.v1.json
```

For an **already-authorized existing** worktree whose `git HEAD`, branch, and canonical destination exactly match a packet, a local executor may issue:

```sh
python capabilities/repository-handoff/handoff.py write --repo-root /existing/checkout --packet /trusted/packet.json
python capabilities/repository-handoff/handoff.py verify --repo-root /existing/checkout --packet /trusted/packet.json
```

An existing handoff can only be replaced with `--expected-sha256 <64-character actual old file hash>`; changed preimages, unexpected branch/head, symlinks, default branches, missing repo roots and path traversal fail closed. This writer creates or updates **one file inside the existing checkout**, never a second clone or an export. It does not `git add`, commit, push, open a PR, or deploy. The result `WRITTEN_WORKTREE_NOT_COMMITTED` is **not remote proof**. A provider-connected agent can instead render the validated Markdown and write it directly to the canonical target through authenticated provider file/commit APIs, then independently read back its remote SHA.

A consumer must configure its own `canonical_path` to an **existing authoritative handoff** or designated tracked destination. The `harness/handoffs/CURRENT.md` shown in the synthetic fixture is an example, not an instruction to create that path in every repo. Preserve the incumbent handoff and require the exact old-file digest for authorized replacement. No silent alternate files.

## Invariants

1. The source repository and its authorized branch own the handoff; Automation owns only the reusable capability.
2. A packet contains mission, scoped/forbidden writes, accomplished work, named checks with evidence, blockers, exact next action, and evidence-bounded proof ceiling.
3. No private continuity-store locators, credentials, identifiable host paths, or arbitrary HTML in tracked packets. An agent must also review content beyond the syntactic guard before publication.
4. No prompt-body mirror, magic Trifecta invocation, hidden downstream dispatcher, or third-party account modification.
5. Provider errors become a truthful `WRITE_BLOCKED` state with recovery requirements, never an operator-host file-copy fallback.
6. Remote commit, provider readback, PR, merge, deployment and live runtime are separate independent proof events.
7. An existing tracked original is protected against stale overwrite. Branch/HEAD checked before every local write; *multi-writer distributed fencing and fully atomic network-provider commits remain adapter responsibilities*.
8. Fresh-agent discovery: README/CONTRIBUTING point here; consumer README/AGENTS may point at the contract only under the consumer's own governance ownership.

## Testing and adoption

```sh
python -m unittest discover -s capabilities/repository-handoff/tests -p 'test_*.py' -v
python -m unittest discover -s tests -p 'test_repository_handoff.py' -v
```

Portability canary: two **separate synthetic Git worktrees**, different semantic repository IDs and handoff paths, without external repo topology. Rejected mutations: main/master branch, stale head, changed preimage, symlink, traversal, private locators, fabricated PASS without evidence. CI runs this alongside the repository's existing checks.

**Next provider gate:** build/readback the same content through a supported authenticated GitHub or other Git-provider adapter, preserving branch lease and existing file SHA. Certify a real second consumer before claiming universal rollout. No default-branch merge, other-repo mutation, or live account setting change is authorized by this incubation.
