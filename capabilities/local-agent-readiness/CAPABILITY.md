# Local Agent Readiness

## Purpose

`local-agent-readiness` prevents a repository from promoting remote/CI health into local-agent health.

It answers one reusable question:

> Is this local agent executing the intended repository-owned projection for a sufficiently current checkout, and which independent proof class is still missing before the repository may trust that agent for work?

The originating incident involved Cursor, but the core is host-neutral. Cursor, OpenCode, Codex, Claude, custom CLIs, and future local agents are represented by tracked profiles and live-observation adapters rather than hard-coded branches in the core.

## Defect class

A repository may be correct remotely while a workstation still executes stale or divergent local projection surfaces:

- project hooks;
- project rules;
- agent instructions;
- skills;
- launchers/wrappers;
- vendored runtime adapters;
- generated or pinned manifests;
- other tracked files interpreted by a local agent.

That mismatch can make a host appear broken even though the repository already contains the repair.

## Core gates

The core exposes five independent gates:

1. `REPOSITORY_CHECKOUT_CURRENT`
   - remote baseline truth was refreshed in this run;
   - refreshed baseline commit is contained by local `HEAD`.

2. `AGENT_PROJECTION_MATCHES_BASELINE`
   - the selected agent's tracked projection sets match refreshed baseline;
   - committed divergence, staged/unstaged changes, missing tracked files, ordinary or ignored untracked shadow files, and symlinks under declared projection paths are all visible;

3. `LOCAL_AGENT_RUNTIME_VERIFIED`
   - a normalized live-host observation exists for the selected agent;
   - the observation is tied to the current agent profile digest;
   - required runtime claims are PASS;
   - the observation floor is an ancestor of current `HEAD`;
   - no selected projection surface was touched by committed history after that observation, even if later reverted to identical bytes;
   - the verifier rechecks local `HEAD` and projection parity before emitting its final receipt, so concurrent local changes invalidate readiness.

4. `REMOTE_WRITE_VERIFIED`
   - optional `git push --dry-run` proves a reachable/authenticated update path;
   - it does not create or update a remote ref.

5. `ACTUAL_PUSH_PROVEN`
   - read-only `git ls-remote` proves an explicitly supplied remote branch points at the expected local commit;
   - the capability never performs the real push itself.

A profile chooses which gates are required for a particular agent role. A read-only local analyzer does not need to pretend it has push authority; an implementation agent may require all five.

## Projection integrity

Projection parity is deliberately stricter than a normal Git endpoint diff:

- ordinary and ignored untracked files beneath declared projection paths are runtime shadows and fail parity;
- symlinks within declared projection surfaces fail parity rather than being followed outside repository authority;
- a live observation is invalidated by any later commit touching its selected projection paths, even if a subsequent commit restores identical bytes;
- final readiness rechecks both `HEAD` and projection parity so concurrent local agents cannot inherit proof gathered for an earlier checkout state.

## Non-destructive boundary

This capability does **not**:

- reset, checkout, rebase, merge, stash, clean, or delete local work;
- install, rewrite, enable, disable, or normalize Cursor/OpenCode/other agent configuration;
- scan user-home agent configuration unless a consumer explicitly models a tracked repository surface;
- perform an actual push;
- create readiness canary refs;
- claim host health from repository CI alone.

The only optional Git metadata mutation is an explicit remote fetch. The optional write probe uses `git push --dry-run`.

## Profiles

A consumer supplies `local-agent-readiness-profile/v1`.

Profiles define:

- remote + baseline branch;
- optional normalized remote identity;
- reusable projection sets;
- agents and the projection sets they consume;
- required readiness gates;
- required live-runtime claims;
- dry-run canary namespace.

Projection paths are repository-relative tracked files/directories. Declared projection symlinks are rejected rather than followed because their effective bytes may live outside repository authority. Ignored local files under a declared projection are still treated as runtime shadows. User-level configuration is intentionally outside scope unless a repository explicitly chooses to model it.

Shared surfaces such as `AGENTS.md` may belong to multiple agents. Agent-specific surfaces remain isolated. A Cursor-only projector change therefore must not invalidate an OpenCode profile unless both profiles declare that surface.

## Live observation

Host-specific integrations normalize their evidence into `local-agent-runtime-observation/v1`.

The core does not decide how a host proves a claim. It verifies that:

- the observation says `LIVE_HOST_OBSERVATION`;
- the declared agent matches;
- the profile digest matches;
- all profile-required claims are PASS;
- raw private content was not persisted;
- the projection did not change after the observation floor.

This keeps host quirks in adapters and prevents one agent's lifecycle from contaminating another.

## Healthy repository recipe

See `docs/HEALTHY_AGENT_REPOSITORY_RECIPE.md`.

The readiness capability is one ingredient, alongside canonical-path evidence, deterministic repository checks, hook/transport normalization where applicable, and explicit proof ceilings.

## Validation / proof ceiling

The isolated-consumer tests create a temporary repository with separate Cursor-like and OpenCode-like projections and prove:

- stale checkout detection;
- agent-specific isolation;
- shared-surface invalidation;
- live-observation binding;
- dry-run remote-write separation;
- actual-push readback separation.

Synthetic tests prove classifier behavior only. A consumer must still execute live host observations and remote readback on its actual workstation to claim readiness.
