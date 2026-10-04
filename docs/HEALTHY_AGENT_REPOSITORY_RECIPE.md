# Healthy Agent-Enabled Repository Recipe

Repositories that allow local agents to mutate code need more than passing CI. A healthy repository should make the **local execution projection** observable and evidence-bounded.

This recipe is intentionally host-agnostic.

## Necessary ingredients

### 1. Canonical repository/path identity

The executor must know which checkout it is operating on and which remote identity is authoritative.

Automation owner:

- `harness/contracts/canonical-path.v1.json`
- `scripts/path_receipt.py`

Never invent a replacement clone because a path is unknown.

### 2. Repository-owned agent projections

Track the files that repository-local agents interpret at runtime:

- hooks;
- rules;
- shared agent instructions;
- skills;
- wrappers/launchers;
- pinned runtime adapters;
- repository-local agent configuration.

Do **not** silently absorb user-level configuration into repository authority.

Declare these surfaces in a `local-agent-readiness-profile/v1` profile. Treat ignored/untracked files beneath declared projections as possible runtime shadows, and reject declared projection symlinks rather than allowing repository authority to escape through external targets.

### 3. Projection freshness before host blame

Before diagnosing Cursor, OpenCode, or another host:

1. refresh the configured remote baseline;
2. prove local `HEAD` contains that baseline;
3. prove the selected agent's repository-owned projection matches the baseline.

If either fails, classify the local projection first. Do not attribute the symptom to the host. Recheck `HEAD` and projection parity before finalizing the readiness receipt so another local agent cannot change the checkout mid-assessment and inherit stale proof.

### 4. Live-host proof

Repository tests cannot prove an installed local agent loaded or obeyed the intended projection.

Each host adapter should emit a normalized:

`local-agent-runtime-observation/v1`

with only privacy-safe evidence.

The selected profile declares the runtime claims it requires.

### 5. Separate Git/write proof

Hook/runtime health does not prove Git/provider write capability.

Keep distinct:

- remote-write dry-run proof;
- actual remote mutation readback.

The generic readiness capability never performs the actual push.

### 6. Non-destructive diagnosis

Readiness tooling should never repair by default.

It must not:

- reset or clean the repository;
- stash/delete local work;
- rewrite Cursor/OpenCode configuration;
- install hooks/rules silently;
- mutate user-level agent configuration;
- create remote canary refs.

Repair remains an explicit consumer/operator lane after diagnosis.

### 7. Proof-state vocabulary

Recommended proof classes:

`REMOTE_INTEGRATED`

`REPOSITORY_CHECKOUT_CURRENT`

`AGENT_PROJECTION_MATCHES_BASELINE`

`LOCAL_AGENT_RUNTIME_VERIFIED`

`REMOTE_WRITE_VERIFIED`

`ACTUAL_PUSH_PROVEN`

Do not collapse them into “works.”

## Multi-agent rule

Profiles are per agent.

A Cursor-only projector change must not invalidate OpenCode unless the changed file belongs to a projection set OpenCode also consumes.

Shared files such as `AGENTS.md` may intentionally invalidate both.

This isolation prevents a repair for one local agent from rewriting or destabilizing another.

## Bootstrap recommendation

A repository adopting the recipe should add a tracked profile, for example:

`automation/local-agent-readiness.v1.json`

and run:

`python <Automation>/capabilities/local-agent-readiness/verify.py --repo-root . --profile automation/local-agent-readiness.v1.json --agent <agent-id> --refresh-remote`

The resulting receipt is diagnostic until the profile-required gates are all PASS.

## Relationship to hook transport

If a host has hook/event transport, use `agent-hook-runtime` to normalize and observe that transport.

Do not embed hook JSON parsing into local-agent readiness. The readiness layer consumes normalized host evidence; it does not replace the host adapter.

## Proof ceiling

This recipe defines repository health ingredients. It does not make every agent or provider universally compatible, and it does not authorize configuration repair or remote mutation.
