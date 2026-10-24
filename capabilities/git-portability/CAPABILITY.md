# Git Portability — incubation

**Contract:** `git-portability/v1`. This is an Automation-owned reusable core, **not** another TokenCorridor, Prompt Kit, GitHub, or GitLab product. It consumes an existing, authorized *local* Git clone/mirror. The source provider is only provenance; the archive is provider-agnostic.

## Supported workflow today

```text
Provider-authorized fetch / existing full local Git clone
          -> clean, non-shallow repository gate
          -> git bundle --all + refs + SHA-256 archive manifest
          -> ZIP, verified from fresh temporary Git repo
          -> optional rclone remote upload with byte-for-byte readback
          -> offline git clone --mirror, exact refs, fsck
          -> new provider's ordinary Git push / profile README configuration
```

The normal consumer only needs Git, Python 3 and the CLI (no knowledge of TokenCorridor internals, donor checkouts or registry paths). Rclone is optional and uses a credential configured **outside Git**. The CLI does not read, create or print provider tokens. A local backup is not equivalent to a replicated offsite backup until independently uploaded and read back.

## Local public-repository use

```bash
python capabilities/git-portability/portable_git.py backup \
  --repo /path/to/authorized-clean-clone --output /independent-storage/profile.zip \
  --visibility public

python capabilities/git-portability/portable_git.py verify --archive /independent-storage/profile.zip

# Optional, once rclone is configured with an authorized Google Drive remote:
python capabilities/git-portability/portable_git.py upload \
  --archive /independent-storage/profile.zip \
  --remote 'mydrive:Git Portability/profile.zip'

# GitHub login and internet NOT required:
python capabilities/git-portability/portable_git.py restore \
  --archive /independent-storage/profile.zip --destination /new/path/recovered.git

# Rehydrate editable worktree, then publish using host-specific authentication:
git clone /new/path/recovered.git /new/path/recovered-worktree
# Inspect remote refs; push to a freshly created repo with explicit operator approval.
```

The restore creates an **independent bare mirror** to retain original branch/tag/ref identities. Do not push `--mirror` into any nonempty destination without reviewing which refs would be replaced; create a new remote repository and deliberately choose the migration action. A GitHub user-profile repository is typically `username/username`; GitLab/Forgejo/Gitea have distinct discovery rules and require explicit adapter tests.

## Fail-closed conditions

- Existing destination or backup file: **blocked**; no overwrite.
- Shallow, dirty or untracked working tree: **blocked** rather than claiming completeness.
- `.gitmodules` or Git LFS pointer attributes: **blocked** because the bare Git bundle alone would omit external data.
- Private repository archive: **blocked** pending independently validated encryption/retention policy; a public automation repo must never ingest private source bytes.
- Provider account metadata, PRs/issues, discussion, settings, Releases, workflow secrets, keys and remote identity **are not backed up** by Git bundles.
- No scheduled job is created by this capability. Consumers may use the canonical `windows-silent-scheduled-task` capability after live readback/persistence tests; do not duplicate a cron scheduler here.
- Remote fetch, provider inventory and rclone authentication must be configured/authorized outside the core. A GitHub backup cron alone is insufficient after revocation: verified offline/offsite artifacts must already exist.

## Current EndeavorEverlasting recovery canary

An independently exported recovery ZIP was verified against public profile HEAD `97502422590f800cf8cb3083f64bb36f34bcec59` on 2026-10-24. Its four Git blob SHA-1 identities match the live source; its separate Git seed was cloned offline and the profile validator passed. A copy and its SHA-256 checksum were uploaded and read back by listing under the operator's private Google Drive recovery folder. This canary is a **source snapshot with a reconstructed seed**, **not** a full original-history bundle. Do not confuse it with a future `portable_git.py backup` produced against an authorized full clone.

## Ownership and future adoption

- **Automation:** core archive/verify/restore semantics, contract, local tests and thin provider adapters.
- **Prompt Kit / TokenCorridor:** unchanged authoritative prompt resolution, judgment routing, decision artifacts and convergence contracts. Integrate through pinned `prompt-invocation-upstream/v1` and `planning.runtime_partition`, never copy prompt contents or build a second registry.
- **Provider adapters:** GitHub, GitLab, Gitea/Forgejo: enumerate authorized repositories, fetch full history and auxiliary metadata, create a fresh profile repo, wire links and CI, verify rendering. Keep credentials out of outputs.
- **Drive storage:** encrypted, versioned immutable offsite objects, durable receipts, retention, and independent readback. The current rclone path is only for non-sensitive public source.
- **Secret/privacy gate:** explicit ownership and encryption approval before account-wide private-repository backups. Never replicate client/work secrets merely because a credential can access them.
- **Migration collisions:** source provider may remain live while new provider is incubating. Never overwrite a configured destination or change default branches implicitly.

## Proof and successor gate

Run `python -m unittest discover -s tests -p 'test_git_portability.py' -v`. This is synthetic local-history proof, not live Google Drive automation or successful provider migration. The next unproven gate is a *real authorized* local `git clone --mirror` of the profile repo and a provider-independent full-history bundle, then readback from an offsite storage adapter and a clean restore on a separate machine. Scale to the larger repo estate only after classification of public/private/client boundaries, storage encryption and blast radius.

Seam review: a normal consumer needs `repo`, `output`, `visibility`, and `restore destination`; it does not need an Automation checkout's internal registries or a TokenCorridor provider login. Empty test repositories act as isolated consumer canaries. There is no old portability implementation to retire.
