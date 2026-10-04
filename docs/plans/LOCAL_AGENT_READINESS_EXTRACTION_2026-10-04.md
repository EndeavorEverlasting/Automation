# Local Agent Readiness Extraction

**Owner:** Automation  
**State:** reusable core implemented; first real-consumer migration deferred  
**Originating consumer:** TokenCorridor  
**Consumer mutation in this lane:** forbidden

## Extracted system defect

A remote repository may contain a repair while an installed local agent continues executing stale or divergent repository-owned projection surfaces.

That defect class is larger than hooks and larger than one host. It applies to any local agent that consumes tracked configuration, instructions, launchers, skills, wrappers, or adapters.

## Extraction

Automation owns:

- repository freshness classification;
- per-agent projection-set parity;
- normalized live-host observation binding;
- remote-write dry-run classification;
- actual pushed-ref readback;
- provider-neutral readiness receipt.

Consumers own:

- projection path selection;
- agent role requirements;
- production of truthful host-specific live observations;
- repair decisions after diagnosis.

## Configuration safety

The generic capability is diagnostic by default.

It does not reset, rebase, checkout, stash, clean, delete, install hooks, rewrite rules, rewrite OpenCode configuration, rewrite Cursor configuration, or perform an actual push.

A consumer may run Cursor and OpenCode side by side with separate projection sets. Shared surfaces are explicit rather than assumed.

## First-consumer adoption

TokenCorridor already has a consumer-specific workstation-readiness implementation created during the live incident response.

Do not replace it while the current local OpenCode/Cursor recovery lane is active.

Later adoption must be a bounded migration:

`consumer-specific classifier -> tracked profile + generic Automation verifier -> parity proof -> old classifier removal`

No configuration rewriting is required for that migration.

## Required next transition

After the active TokenCorridor local-agent sprint produces stable workstation evidence:

1. refresh TokenCorridor main and local-agent runtime truth;
2. declare Cursor/OpenCode projection sets in a tracked consumer profile;
3. add a thin adapter that normalizes the existing Cursor live evidence into `local-agent-runtime-observation/v1`;
4. add an OpenCode observation adapter only for claims OpenCode can actually prove;
5. run both against the generic verifier;
6. compare receipts with the existing TokenCorridor classifier;
7. remove the duplicated classifier only after parity is proven.

## Proof ceiling

This plan preserves the extraction/adoption obligation without mutating the live consumer. It does not claim the consumer migration is complete.
