# Automation feature map

Generated from `harness/contracts/feature-ontology.v1.json`. Do not edit this projection manually.

Every tracked path has exactly one primary feature owner. This includes implementation, adapters, tests, contracts, fixtures, workflows, vendor files and documentation. No wildcard ownership or catch-all exclusions. Capability directory ownership, file roles and declared entrypoints are checked against existing repository contracts.

Validate locally: `python scripts/validate_feature_ontology.py`

When adding, deleting, renaming or moving files, update the ontology, stage the affected paths, and regenerate this map in the same change: `python scripts/validate_feature_ontology.py --render` (redirect to FEATURE_MAP.md using UTF-8). The repository test suite checks both coverage and projection parity. The local validator also rejects non-ignored, unstaged source files.

**23 features; 268 mapped paths.**

## agent-hook-runtime

Normalize native agent hook protocols, sample shapes and transport hook receipts.

Entrypoints:
- [`capabilities/agent-hook-runtime/diagnose_cursor_hook.py`](capabilities/agent-hook-runtime/diagnose_cursor_hook.py)
- [`capabilities/agent-hook-runtime/sample_shapes.py`](capabilities/agent-hook-runtime/sample_shapes.py)

- `documentation` — [`capabilities/agent-hook-runtime/CAPABILITY.md`](capabilities/agent-hook-runtime/CAPABILITY.md)
- `adapter` — [`capabilities/agent-hook-runtime/adapters/__init__.py`](capabilities/agent-hook-runtime/adapters/__init__.py)
- `adapter` — [`capabilities/agent-hook-runtime/adapters/cursor.py`](capabilities/agent-hook-runtime/adapters/cursor.py)
- `contract` — [`capabilities/agent-hook-runtime/capability.v1.json`](capabilities/agent-hook-runtime/capability.v1.json)
- `source` — [`capabilities/agent-hook-runtime/core/__init__.py`](capabilities/agent-hook-runtime/core/__init__.py)
- `source` — [`capabilities/agent-hook-runtime/core/protocol_fabric.py`](capabilities/agent-hook-runtime/core/protocol_fabric.py)
- `source` — [`capabilities/agent-hook-runtime/core/shape_sampler.py`](capabilities/agent-hook-runtime/core/shape_sampler.py)
- `source` — [`capabilities/agent-hook-runtime/core/transport.py`](capabilities/agent-hook-runtime/core/transport.py)
- `source` — [`capabilities/agent-hook-runtime/diagnose_cursor_hook.py`](capabilities/agent-hook-runtime/diagnose_cursor_hook.py)
- `fixture` — [`capabilities/agent-hook-runtime/fixtures/shape-sampling-matrix.synthetic.v1.json`](capabilities/agent-hook-runtime/fixtures/shape-sampling-matrix.synthetic.v1.json)
- `contract` — [`capabilities/agent-hook-runtime/profiles/current.v1.json`](capabilities/agent-hook-runtime/profiles/current.v1.json)
- `source` — [`capabilities/agent-hook-runtime/sample_shapes.py`](capabilities/agent-hook-runtime/sample_shapes.py)
- `contract` — [`capabilities/agent-hook-runtime/schemas/shape-sampling-receipt.v1.json`](capabilities/agent-hook-runtime/schemas/shape-sampling-receipt.v1.json)
- `contract` — [`capabilities/agent-hook-runtime/schemas/transport-receipt.v1.json`](capabilities/agent-hook-runtime/schemas/transport-receipt.v1.json)
- `documentation` — [`docs/P95_HOOK_PROTOCOL_FABRIC_ARCHITECTURE_2026-10-04.md`](docs/P95_HOOK_PROTOCOL_FABRIC_ARCHITECTURE_2026-10-04.md)
- `documentation` — [`docs/P97_HOOK_PROTOCOL_PRIOR_ART_2026-10-04.md`](docs/P97_HOOK_PROTOCOL_PRIOR_ART_2026-10-04.md)
- `documentation` — [`docs/plans/HARNESS_SHAPE_SAMPLING_CERTIFICATION_2026-10-04.md`](docs/plans/HARNESS_SHAPE_SAMPLING_CERTIFICATION_2026-10-04.md)
- `documentation` — [`docs/plans/HOOK_PROTOCOL_FABRIC_P04_P95_P97_2026-10-04.md`](docs/plans/HOOK_PROTOCOL_FABRIC_P04_P95_P97_2026-10-04.md)
- `contract` — [`docs/plans/HOOK_PROTOCOL_FABRIC_P04_P95_P97_2026-10-04.plan.json`](docs/plans/HOOK_PROTOCOL_FABRIC_P04_P95_P97_2026-10-04.plan.json)
- `test` — [`tests/test_agent_hook_protocol_fabric.py`](tests/test_agent_hook_protocol_fabric.py)
- `test` — [`tests/test_agent_hook_runtime.py`](tests/test_agent_hook_runtime.py)
- `test` — [`tests/test_agent_hook_shape_sampler.py`](tests/test_agent_hook_shape_sampler.py)

## canonical-path

Resolve canonical development and production path evidence.

Entrypoints:
- [`scripts/path_receipt.py`](scripts/path_receipt.py)

- `contract` — [`harness/contracts/canonical-path.v1.json`](harness/contracts/canonical-path.v1.json)
- `source` — [`scripts/path_receipt.py`](scripts/path_receipt.py)
- `test` — [`tests/test_path_receipt.py`](tests/test_path_receipt.py)

## document-formatting

Compile portable document design contracts and adapt them to Google Docs.

Entrypoints:
- [`capabilities/document-formatting/compile.py`](capabilities/document-formatting/compile.py)
- [`capabilities/document-formatting/plan.py`](capabilities/document-formatting/plan.py)

- `documentation` — [`capabilities/document-formatting/CAPABILITY.md`](capabilities/document-formatting/CAPABILITY.md)
- `adapter` — [`capabilities/document-formatting/adapters/__init__.py`](capabilities/document-formatting/adapters/__init__.py)
- `adapter` — [`capabilities/document-formatting/adapters/google_docs.py`](capabilities/document-formatting/adapters/google_docs.py)
- `contract` — [`capabilities/document-formatting/capability.v1.json`](capabilities/document-formatting/capability.v1.json)
- `source` — [`capabilities/document-formatting/compile.py`](capabilities/document-formatting/compile.py)
- `source` — [`capabilities/document-formatting/core/__init__.py`](capabilities/document-formatting/core/__init__.py)
- `source` — [`capabilities/document-formatting/core/compiler.py`](capabilities/document-formatting/core/compiler.py)
- `source` — [`capabilities/document-formatting/core/contract.py`](capabilities/document-formatting/core/contract.py)
- `fixture` — [`capabilities/document-formatting/fixtures/consumer-profile.synthetic.v1.json`](capabilities/document-formatting/fixtures/consumer-profile.synthetic.v1.json)
- `fixture` — [`capabilities/document-formatting/fixtures/design-spec.synthetic.v1.json`](capabilities/document-formatting/fixtures/design-spec.synthetic.v1.json)
- `fixture` — [`capabilities/document-formatting/fixtures/document-source.synthetic.v1.json`](capabilities/document-formatting/fixtures/document-source.synthetic.v1.json)
- `fixture` — [`capabilities/document-formatting/fixtures/google-docs-degradation-policy.synthetic.v1.json`](capabilities/document-formatting/fixtures/google-docs-degradation-policy.synthetic.v1.json)
- `source` — [`capabilities/document-formatting/plan.py`](capabilities/document-formatting/plan.py)
- `contract` — [`capabilities/document-formatting/schemas/compiler-receipt.v1.json`](capabilities/document-formatting/schemas/compiler-receipt.v1.json)
- `contract` — [`capabilities/document-formatting/schemas/consumer-profile.v1.json`](capabilities/document-formatting/schemas/consumer-profile.v1.json)
- `contract` — [`capabilities/document-formatting/schemas/design-spec.v1.json`](capabilities/document-formatting/schemas/design-spec.v1.json)
- `contract` — [`capabilities/document-formatting/schemas/google-docs-plan.v1.json`](capabilities/document-formatting/schemas/google-docs-plan.v1.json)
- `contract` — [`capabilities/document-formatting/schemas/ir.v1.json`](capabilities/document-formatting/schemas/ir.v1.json)
- `contract` — [`capabilities/document-formatting/schemas/plan.v1.json`](capabilities/document-formatting/schemas/plan.v1.json)
- `contract` — [`capabilities/document-formatting/schemas/source.v1.json`](capabilities/document-formatting/schemas/source.v1.json)
- `documentation` — [`docs/DOCUMENT_FORMATTING_SEAM_REVIEW.md`](docs/DOCUMENT_FORMATTING_SEAM_REVIEW.md)
- `documentation` — [`docs/P95_DOCUMENT_FORMATTING_COMPILER_ARCHITECTURE.md`](docs/P95_DOCUMENT_FORMATTING_COMPILER_ARCHITECTURE.md)
- `fixture` — [`docs/evidence/document-formatting-google-docs-autotext-probe-20261003.json`](docs/evidence/document-formatting-google-docs-autotext-probe-20261003.json)
- `test` — [`tests/test_document_formatting_capability.py`](tests/test_document_formatting_capability.py)
- `test` — [`tests/test_document_formatting_compiler_p95.py`](tests/test_document_formatting_compiler_p95.py)
- `test` — [`tests/test_document_formatting_consumer_canary.py`](tests/test_document_formatting_consumer_canary.py)

## entire-local-continuous

Admit and verify Actions-optional local continuous development.

Entrypoints:
- [`capabilities/entire-local-continuous/continuous_local.py`](capabilities/entire-local-continuous/continuous_local.py)

- `documentation` — [`capabilities/entire-local-continuous/CAPABILITY.md`](capabilities/entire-local-continuous/CAPABILITY.md)
- `contract` — [`capabilities/entire-local-continuous/capability.v1.json`](capabilities/entire-local-continuous/capability.v1.json)
- `source` — [`capabilities/entire-local-continuous/continuous_local.py`](capabilities/entire-local-continuous/continuous_local.py)
- `source` — [`capabilities/entire-local-continuous/core/__init__.py`](capabilities/entire-local-continuous/core/__init__.py)
- `source` — [`capabilities/entire-local-continuous/core/continuous_local.py`](capabilities/entire-local-continuous/core/continuous_local.py)
- `fixture` — [`capabilities/entire-local-continuous/fixtures/afk-proposal.admitted.v1.json`](capabilities/entire-local-continuous/fixtures/afk-proposal.admitted.v1.json)
- `fixture` — [`capabilities/entire-local-continuous/fixtures/afk-proposal.console-rejected.v1.json`](capabilities/entire-local-continuous/fixtures/afk-proposal.console-rejected.v1.json)
- `fixture` — [`capabilities/entire-local-continuous/fixtures/entire-status.enabled-local.v1.json`](capabilities/entire-local-continuous/fixtures/entire-status.enabled-local.v1.json)
- `fixture` — [`capabilities/entire-local-continuous/fixtures/entire-status.not-setup.v1.json`](capabilities/entire-local-continuous/fixtures/entire-status.not-setup.v1.json)
- `contract` — [`capabilities/entire-local-continuous/schemas/afk-proposal.v1.json`](capabilities/entire-local-continuous/schemas/afk-proposal.v1.json)
- `contract` — [`capabilities/entire-local-continuous/schemas/continuous-local-receipt.v1.json`](capabilities/entire-local-continuous/schemas/continuous-local-receipt.v1.json)
- `test` — [`capabilities/entire-local-continuous/tests/test_continuous_local.py`](capabilities/entire-local-continuous/tests/test_continuous_local.py)
- `documentation` — [`docs/ENTIRE_LOCAL_CONTINUOUS_SEAM_REVIEW.md`](docs/ENTIRE_LOCAL_CONTINUOUS_SEAM_REVIEW.md)
- `contract` — [`harness/contracts/entire-local-continuous.v1.json`](harness/contracts/entire-local-continuous.v1.json)

## feature-ontology

Enforce exact ownership for every tracked file and render the synchronized feature map.

Entrypoints:
- [`scripts/validate_feature_ontology.py`](scripts/validate_feature_ontology.py)

- `documentation` — [`FEATURE_MAP.md`](FEATURE_MAP.md)
- `contract` — [`harness/contracts/feature-ontology.v1.json`](harness/contracts/feature-ontology.v1.json)
- `source` — [`scripts/validate_feature_ontology.py`](scripts/validate_feature_ontology.py)
- `test` — [`tests/test_feature_ontology.py`](tests/test_feature_ontology.py)

## ghidra-bootstrap

Bootstrap and certify portable Ghidra installations.

Entrypoints:
- [`Bootstrap-Ghidra.cmd`](Bootstrap-Ghidra.cmd)
- [`capabilities/ghidra-bootstrap/Bootstrap-Ghidra.cmd`](capabilities/ghidra-bootstrap/Bootstrap-Ghidra.cmd)
- [`capabilities/ghidra-bootstrap/Prove-GhidraBootstrap.ps1`](capabilities/ghidra-bootstrap/Prove-GhidraBootstrap.ps1)

- `source` — [`Bootstrap-Ghidra.cmd`](Bootstrap-Ghidra.cmd)
- `source` — [`capabilities/ghidra-bootstrap/Bootstrap-Ghidra.cmd`](capabilities/ghidra-bootstrap/Bootstrap-Ghidra.cmd)
- `source` — [`capabilities/ghidra-bootstrap/Bootstrap-Ghidra.ps1`](capabilities/ghidra-bootstrap/Bootstrap-Ghidra.ps1)
- `documentation` — [`capabilities/ghidra-bootstrap/CAPABILITY.md`](capabilities/ghidra-bootstrap/CAPABILITY.md)
- `source` — [`capabilities/ghidra-bootstrap/Prove-GhidraBootstrap.ps1`](capabilities/ghidra-bootstrap/Prove-GhidraBootstrap.ps1)
- `contract` — [`capabilities/ghidra-bootstrap/capability.v1.json`](capabilities/ghidra-bootstrap/capability.v1.json)
- `fixture` — [`capabilities/ghidra-bootstrap/fixtures/synthetic-ghidra/ghidraRun.bat`](capabilities/ghidra-bootstrap/fixtures/synthetic-ghidra/ghidraRun.bat)
- `fixture` — [`capabilities/ghidra-bootstrap/fixtures/synthetic-ghidra/support/analyzeHeadless.bat`](capabilities/ghidra-bootstrap/fixtures/synthetic-ghidra/support/analyzeHeadless.bat)
- `fixture` — [`capabilities/ghidra-bootstrap/fixtures/synthetic-ghidra/support/launch.properties`](capabilities/ghidra-bootstrap/fixtures/synthetic-ghidra/support/launch.properties)
- `contract` — [`capabilities/ghidra-bootstrap/ghidra-bootstrap.manifest.json`](capabilities/ghidra-bootstrap/ghidra-bootstrap.manifest.json)
- `contract` — [`capabilities/ghidra-bootstrap/schemas/manifest.v1.json`](capabilities/ghidra-bootstrap/schemas/manifest.v1.json)
- `test` — [`capabilities/ghidra-bootstrap/tests/test_ghidra_bootstrap.py`](capabilities/ghidra-bootstrap/tests/test_ghidra_bootstrap.py)

## git-portability

Bundle, verify and restore Git history and repository portability.

Entrypoints:
- [`capabilities/git-portability/portable_git.py`](capabilities/git-portability/portable_git.py)

- `documentation` — [`capabilities/git-portability/CAPABILITY.md`](capabilities/git-portability/CAPABILITY.md)
- `contract` — [`capabilities/git-portability/capability.v1.json`](capabilities/git-portability/capability.v1.json)
- `source` — [`capabilities/git-portability/portable_git.py`](capabilities/git-portability/portable_git.py)
- `test` — [`tests/test_git_portability.py`](tests/test_git_portability.py)

## idea-work-continuity

Preserve durable idea-to-work ownership and continuity receipts.

Entrypoints:
- [`scripts/validate_idea_work_continuity.py`](scripts/validate_idea_work_continuity.py)

- `documentation` — [`capabilities/idea-work-continuity/CAPABILITY.md`](capabilities/idea-work-continuity/CAPABILITY.md)
- `contract` — [`capabilities/idea-work-continuity/capability.v1.json`](capabilities/idea-work-continuity/capability.v1.json)
- `fixture` — [`docs/examples/idea-work-continuity.tokencorridor-deferred.v1.json`](docs/examples/idea-work-continuity.tokencorridor-deferred.v1.json)
- `documentation` — [`docs/plans/IDEA_WORK_CONTINUITY_2026-10-03.md`](docs/plans/IDEA_WORK_CONTINUITY_2026-10-03.md)
- `contract` — [`harness/contracts/idea-work-continuity.v1.json`](harness/contracts/idea-work-continuity.v1.json)
- `source` — [`scripts/validate_idea_work_continuity.py`](scripts/validate_idea_work_continuity.py)
- `test` — [`tests/test_idea_work_continuity.py`](tests/test_idea_work_continuity.py)

## legacy-spreadsheet-day

Legacy Google Apps Script for adding a new day.

Entrypoints:
- [`Add_New_Day.gs`](Add_New_Day.gs)

- `source` — [`Add_New_Day.gs`](Add_New_Day.gs)

## local-agent-readiness

Diagnose agent checkout, projection and runtime readiness.

Entrypoints:
- [`capabilities/local-agent-readiness/core/readiness.py`](capabilities/local-agent-readiness/core/readiness.py)
- [`capabilities/local-agent-readiness/verify.py`](capabilities/local-agent-readiness/verify.py)

- `documentation` — [`capabilities/local-agent-readiness/CAPABILITY.md`](capabilities/local-agent-readiness/CAPABILITY.md)
- `contract` — [`capabilities/local-agent-readiness/capability.v1.json`](capabilities/local-agent-readiness/capability.v1.json)
- `source` — [`capabilities/local-agent-readiness/core/__init__.py`](capabilities/local-agent-readiness/core/__init__.py)
- `source` — [`capabilities/local-agent-readiness/core/readiness.py`](capabilities/local-agent-readiness/core/readiness.py)
- `fixture` — [`capabilities/local-agent-readiness/fixtures/profile.multi-agent.synthetic.v1.json`](capabilities/local-agent-readiness/fixtures/profile.multi-agent.synthetic.v1.json)
- `contract` — [`capabilities/local-agent-readiness/schemas/harness-availability.v1.json`](capabilities/local-agent-readiness/schemas/harness-availability.v1.json)
- `contract` — [`capabilities/local-agent-readiness/schemas/profile.v1.json`](capabilities/local-agent-readiness/schemas/profile.v1.json)
- `contract` — [`capabilities/local-agent-readiness/schemas/readiness-receipt.v1.json`](capabilities/local-agent-readiness/schemas/readiness-receipt.v1.json)
- `contract` — [`capabilities/local-agent-readiness/schemas/runtime-observation.v1.json`](capabilities/local-agent-readiness/schemas/runtime-observation.v1.json)
- `source` — [`capabilities/local-agent-readiness/verify.py`](capabilities/local-agent-readiness/verify.py)
- `documentation` — [`docs/HEALTHY_AGENT_REPOSITORY_RECIPE.md`](docs/HEALTHY_AGENT_REPOSITORY_RECIPE.md)
- `documentation` — [`docs/plans/LOCAL_AGENT_READINESS_EXTRACTION_2026-10-04.md`](docs/plans/LOCAL_AGENT_READINESS_EXTRACTION_2026-10-04.md)
- `documentation` — [`docs/reviews/LOCAL_AGENT_READINESS_SEAM_REVIEW_2026-10-04.md`](docs/reviews/LOCAL_AGENT_READINESS_SEAM_REVIEW_2026-10-04.md)
- `test` — [`tests/test_local_agent_readiness.py`](tests/test_local_agent_readiness.py)

## media-transcript-acquisition

Acquire, normalize, inspect and deliver media/transcript evidence locally.

Entrypoints:
- [`capabilities/media-transcript-acquisition/Run-Media-Delivery.cmd`](capabilities/media-transcript-acquisition/Run-Media-Delivery.cmd)
- [`capabilities/media-transcript-acquisition/acquire.py`](capabilities/media-transcript-acquisition/acquire.py)
- [`capabilities/media-transcript-acquisition/deliver_artifact.py`](capabilities/media-transcript-acquisition/deliver_artifact.py)
- [`capabilities/media-transcript-acquisition/host_app.py`](capabilities/media-transcript-acquisition/host_app.py)
- [`capabilities/media-transcript-acquisition/inspect_local_video.py`](capabilities/media-transcript-acquisition/inspect_local_video.py)
- [`capabilities/media-transcript-acquisition/run-media-delivery.sh`](capabilities/media-transcript-acquisition/run-media-delivery.sh)
- [`capabilities/media-transcript-acquisition/social_insights.py`](capabilities/media-transcript-acquisition/social_insights.py)

- `workflow` — [`.github/workflows/media-transcript-acquisition.yml`](.github/workflows/media-transcript-acquisition.yml)
- `documentation` — [`capabilities/media-transcript-acquisition/ARTIFACT_DELIVERY.md`](capabilities/media-transcript-acquisition/ARTIFACT_DELIVERY.md)
- `documentation` — [`capabilities/media-transcript-acquisition/CAPABILITY.md`](capabilities/media-transcript-acquisition/CAPABILITY.md)
- `documentation` — [`capabilities/media-transcript-acquisition/HOST_SETUP.md`](capabilities/media-transcript-acquisition/HOST_SETUP.md)
- `source` — [`capabilities/media-transcript-acquisition/Run-Media-Delivery.cmd`](capabilities/media-transcript-acquisition/Run-Media-Delivery.cmd)
- `documentation` — [`capabilities/media-transcript-acquisition/SOCIAL_MEDIA_INSIGHTS.md`](capabilities/media-transcript-acquisition/SOCIAL_MEDIA_INSIGHTS.md)
- `documentation` — [`capabilities/media-transcript-acquisition/VIDEO_PROCESSING.md`](capabilities/media-transcript-acquisition/VIDEO_PROCESSING.md)
- `source` — [`capabilities/media-transcript-acquisition/acquire.py`](capabilities/media-transcript-acquisition/acquire.py)
- `adapter` — [`capabilities/media-transcript-acquisition/adapters/ffmpeg_files.py`](capabilities/media-transcript-acquisition/adapters/ffmpeg_files.py)
- `adapter` — [`capabilities/media-transcript-acquisition/adapters/ollama_local.py`](capabilities/media-transcript-acquisition/adapters/ollama_local.py)
- `adapter` — [`capabilities/media-transcript-acquisition/adapters/yt_dlp_social.py`](capabilities/media-transcript-acquisition/adapters/yt_dlp_social.py)
- `source` — [`capabilities/media-transcript-acquisition/deliver_artifact.py`](capabilities/media-transcript-acquisition/deliver_artifact.py)
- `source` — [`capabilities/media-transcript-acquisition/host_app.py`](capabilities/media-transcript-acquisition/host_app.py)
- `source` — [`capabilities/media-transcript-acquisition/inspect_local_video.py`](capabilities/media-transcript-acquisition/inspect_local_video.py)
- `source` — [`capabilities/media-transcript-acquisition/run-media-delivery.sh`](capabilities/media-transcript-acquisition/run-media-delivery.sh)
- `contract` — [`capabilities/media-transcript-acquisition/schemas/media-artifact-delivery.v1.schema.json`](capabilities/media-transcript-acquisition/schemas/media-artifact-delivery.v1.schema.json)
- `contract` — [`capabilities/media-transcript-acquisition/schemas/transcript-evidence.v1.schema.json`](capabilities/media-transcript-acquisition/schemas/transcript-evidence.v1.schema.json)
- `source` — [`capabilities/media-transcript-acquisition/social_insights.py`](capabilities/media-transcript-acquisition/social_insights.py)
- `test` — [`capabilities/media-transcript-acquisition/tests/test_acquire.py`](capabilities/media-transcript-acquisition/tests/test_acquire.py)
- `test` — [`capabilities/media-transcript-acquisition/tests/test_artifact_delivery.py`](capabilities/media-transcript-acquisition/tests/test_artifact_delivery.py)
- `test` — [`capabilities/media-transcript-acquisition/tests/test_contract.py`](capabilities/media-transcript-acquisition/tests/test_contract.py)
- `test` — [`capabilities/media-transcript-acquisition/tests/test_host_app.py`](capabilities/media-transcript-acquisition/tests/test_host_app.py)
- `test` — [`capabilities/media-transcript-acquisition/tests/test_inspect_local_video.py`](capabilities/media-transcript-acquisition/tests/test_inspect_local_video.py)
- `test` — [`capabilities/media-transcript-acquisition/tests/test_social_insights.py`](capabilities/media-transcript-acquisition/tests/test_social_insights.py)
- `contract` — [`docs/handoffs/MEDIA_ARTIFACT_HOST_CERTIFICATION_2026-11-06.json`](docs/handoffs/MEDIA_ARTIFACT_HOST_CERTIFICATION_2026-11-06.json)
- `documentation` — [`docs/handoffs/MEDIA_ARTIFACT_HOST_CERTIFICATION_2026-11-06.md`](docs/handoffs/MEDIA_ARTIFACT_HOST_CERTIFICATION_2026-11-06.md)
- `documentation` — [`docs/reviews/MEDIA_HOST_CROSS_PLATFORM_P141_2026-11-06.md`](docs/reviews/MEDIA_HOST_CROSS_PLATFORM_P141_2026-11-06.md)
- `test` — [`tests/test_media_artifact_handoff.py`](tests/test_media_artifact_handoff.py)

## parallel-dispatch

Dispatch independent work and manage execution leases.

Entrypoints:
- [`capabilities/parallel-dispatch/lease_ledger.py`](capabilities/parallel-dispatch/lease_ledger.py)
- [`capabilities/parallel-dispatch/run.py`](capabilities/parallel-dispatch/run.py)

- `documentation` — [`capabilities/parallel-dispatch/CAPABILITY.md`](capabilities/parallel-dispatch/CAPABILITY.md)
- `source` — [`capabilities/parallel-dispatch/lease_ledger.py`](capabilities/parallel-dispatch/lease_ledger.py)
- `source` — [`capabilities/parallel-dispatch/run.py`](capabilities/parallel-dispatch/run.py)
- `documentation` — [`docs/PARALLEL_DISPATCH.md`](docs/PARALLEL_DISPATCH.md)
- `fixture` — [`docs/examples/parallel-dispatch.synthetic.v1.json`](docs/examples/parallel-dispatch.synthetic.v1.json)
- `test` — [`tests/test_parallel_dispatch_capability.py`](tests/test_parallel_dispatch_capability.py)
- `test` — [`tests/test_parallel_dispatch_lease_ledger.py`](tests/test_parallel_dispatch_lease_ledger.py)

## playlist-link-extraction

Normalize playlist observations and export link artifacts.

Entrypoints:
- [`capabilities/playlist-link-extraction/extract_links.py`](capabilities/playlist-link-extraction/extract_links.py)

- `documentation` — [`capabilities/playlist-link-extraction/CAPABILITY.md`](capabilities/playlist-link-extraction/CAPABILITY.md)
- `documentation` — [`capabilities/playlist-link-extraction/adapters/README.md`](capabilities/playlist-link-extraction/adapters/README.md)
- `documentation` — [`capabilities/playlist-link-extraction/adapters/yt-dlp-json/README.md`](capabilities/playlist-link-extraction/adapters/yt-dlp-json/README.md)
- `adapter` — [`capabilities/playlist-link-extraction/adapters/yt-dlp-json/adapt.py`](capabilities/playlist-link-extraction/adapters/yt-dlp-json/adapt.py)
- `adapter` — [`capabilities/playlist-link-extraction/adapters/yt-dlp-json/convert.py`](capabilities/playlist-link-extraction/adapters/yt-dlp-json/convert.py)
- `fixture` — [`capabilities/playlist-link-extraction/adapters/yt-dlp-json/fixtures/sample-playlist.v1.json`](capabilities/playlist-link-extraction/adapters/yt-dlp-json/fixtures/sample-playlist.v1.json)
- `contract` — [`capabilities/playlist-link-extraction/adapters/yt-dlp-json/schemas/provider-payload.v1.json`](capabilities/playlist-link-extraction/adapters/yt-dlp-json/schemas/provider-payload.v1.json)
- `contract` — [`capabilities/playlist-link-extraction/capability.v1.json`](capabilities/playlist-link-extraction/capability.v1.json)
- `source` — [`capabilities/playlist-link-extraction/core/__init__.py`](capabilities/playlist-link-extraction/core/__init__.py)
- `source` — [`capabilities/playlist-link-extraction/core/artifact.py`](capabilities/playlist-link-extraction/core/artifact.py)
- `source` — [`capabilities/playlist-link-extraction/core/normalize.py`](capabilities/playlist-link-extraction/core/normalize.py)
- `source` — [`capabilities/playlist-link-extraction/extract_links.py`](capabilities/playlist-link-extraction/extract_links.py)
- `fixture` — [`capabilities/playlist-link-extraction/fixtures/synthetic-observation-batch.v1.json`](capabilities/playlist-link-extraction/fixtures/synthetic-observation-batch.v1.json)
- `contract` — [`capabilities/playlist-link-extraction/schemas/artifact.v1.json`](capabilities/playlist-link-extraction/schemas/artifact.v1.json)
- `contract` — [`capabilities/playlist-link-extraction/schemas/observation-batch.v1.json`](capabilities/playlist-link-extraction/schemas/observation-batch.v1.json)
- `test` — [`tests/test_playlist_link_extraction.py`](tests/test_playlist_link_extraction.py)
- `test` — [`tests/test_playlist_yt_dlp_json_adapter.py`](tests/test_playlist_yt_dlp_json_adapter.py)

## profile-artwork

Generate, verify and roll back coordinated profile artwork.

Entrypoints:
- [`capabilities/profile-artwork/profile_artwork.py`](capabilities/profile-artwork/profile_artwork.py)

- `documentation` — [`capabilities/profile-artwork/CAPABILITY.md`](capabilities/profile-artwork/CAPABILITY.md)
- `contract` — [`capabilities/profile-artwork/capability.v1.json`](capabilities/profile-artwork/capability.v1.json)
- `source` — [`capabilities/profile-artwork/profile_artwork.py`](capabilities/profile-artwork/profile_artwork.py)
- `test` — [`capabilities/profile-artwork/tests/test_profile_artwork.py`](capabilities/profile-artwork/tests/test_profile_artwork.py)

## prompt-runtime

Consume the pinned upstream prompt invocation dependency.

Entrypoints:
- [`scripts/prompt_runtime.py`](scripts/prompt_runtime.py)

- `documentation` — [`docs/PROMPT_RUNTIME.md`](docs/PROMPT_RUNTIME.md)
- `source` — [`scripts/prompt_runtime.py`](scripts/prompt_runtime.py)
- `test` — [`tests/test_prompt_runtime.py`](tests/test_prompt_runtime.py)
- `vendor` — [`vendor/prompt-invocation-upstream/catalog.v1.json`](vendor/prompt-invocation-upstream/catalog.v1.json)
- `vendor` — [`vendor/prompt-invocation-upstream/contract.v1.json`](vendor/prompt-invocation-upstream/contract.v1.json)
- `vendor` — [`vendor/prompt-invocation-upstream/manifest.v1.json`](vendor/prompt-invocation-upstream/manifest.v1.json)
- `vendor` — [`vendor/prompt-invocation-upstream/prompt_invocation_resolver.py`](vendor/prompt-invocation-upstream/prompt_invocation_resolver.py)

## repository-governance

Define repository identity, contribution boundaries, and seam review.

- `documentation` — [`.gitignore`](.gitignore)
- `documentation` — [`AGENTS.md`](AGENTS.md)
- `documentation` — [`CONTRIBUTING.md`](CONTRIBUTING.md)
- `documentation` — [`LICENSE`](LICENSE)
- `documentation` — [`README.md`](README.md)
- `documentation` — [`docs/REPOSITORY_CHARTER.md`](docs/REPOSITORY_CHARTER.md)
- `documentation` — [`docs/SEAM_BOUNDARY_REVIEW.md`](docs/SEAM_BOUNDARY_REVIEW.md)
- `contract` — [`harness/contracts/seam-boundary-review.v1.json`](harness/contracts/seam-boundary-review.v1.json)
- `test` — [`tests/test_repository_contracts.py`](tests/test_repository_contracts.py)
- `test` — [`tests/test_seam_boundary_review.py`](tests/test_seam_boundary_review.py)

## runtime-handoff

Validate runtime execution handoff and public/private placement.

Entrypoints:
- [`scripts/validate_runtime_handoff.py`](scripts/validate_runtime_handoff.py)

- `documentation` — [`docs/PUBLIC_PRIVATE_BRIDGE.md`](docs/PUBLIC_PRIVATE_BRIDGE.md)
- `documentation` — [`docs/RUNTIME_DISTRIBUTION.md`](docs/RUNTIME_DISTRIBUTION.md)
- `fixture` — [`docs/examples/runtime-handoff.example.json`](docs/examples/runtime-handoff.example.json)
- `contract` — [`harness/contracts/runtime-execution-handoff.v1.json`](harness/contracts/runtime-execution-handoff.v1.json)
- `source` — [`scripts/validate_runtime_handoff.py`](scripts/validate_runtime_handoff.py)
- `test` — [`tests/test_runtime_handoff.py`](tests/test_runtime_handoff.py)

## slide-flow-compiler

Compile slide flows and verify Google Slides readback.

Entrypoints:
- [`capabilities/slide-flow-compiler/adapters/google-slides-readback.mjs`](capabilities/slide-flow-compiler/adapters/google-slides-readback.mjs)
- [`capabilities/slide-flow-compiler/adapters/google-slides.mjs`](capabilities/slide-flow-compiler/adapters/google-slides.mjs)
- [`capabilities/slide-flow-compiler/compile.mjs`](capabilities/slide-flow-compiler/compile.mjs)

- `workflow` — [`.github/workflows/slide-flow-compiler.yml`](.github/workflows/slide-flow-compiler.yml)
- `documentation` — [`capabilities/slide-flow-compiler/CAPABILITY.md`](capabilities/slide-flow-compiler/CAPABILITY.md)
- `adapter` — [`capabilities/slide-flow-compiler/adapters/google-slides-readback.mjs`](capabilities/slide-flow-compiler/adapters/google-slides-readback.mjs)
- `adapter` — [`capabilities/slide-flow-compiler/adapters/google-slides.mjs`](capabilities/slide-flow-compiler/adapters/google-slides.mjs)
- `source` — [`capabilities/slide-flow-compiler/compile.mjs`](capabilities/slide-flow-compiler/compile.mjs)
- `test` — [`capabilities/slide-flow-compiler/tests/test_compile.mjs`](capabilities/slide-flow-compiler/tests/test_compile.mjs)
- `test` — [`capabilities/slide-flow-compiler/tests/test_readback.mjs`](capabilities/slide-flow-compiler/tests/test_readback.mjs)

## social-publication

Compile publication intent and isolate provider-specific delivery.

Entrypoints:
- [`capabilities/social-publication/prototype.py`](capabilities/social-publication/prototype.py)

- `documentation` — [`capabilities/social-publication/CAPABILITY.md`](capabilities/social-publication/CAPABILITY.md)
- `adapter` — [`capabilities/social-publication/adapters/__init__.py`](capabilities/social-publication/adapters/__init__.py)
- `adapter` — [`capabilities/social-publication/adapters/linkedin.py`](capabilities/social-publication/adapters/linkedin.py)
- `contract` — [`capabilities/social-publication/capability.v1.json`](capabilities/social-publication/capability.v1.json)
- `source` — [`capabilities/social-publication/core/__init__.py`](capabilities/social-publication/core/__init__.py)
- `source` — [`capabilities/social-publication/core/publication.py`](capabilities/social-publication/core/publication.py)
- `fixture` — [`capabilities/social-publication/fixtures/text-intent.synthetic.v1.json`](capabilities/social-publication/fixtures/text-intent.synthetic.v1.json)
- `source` — [`capabilities/social-publication/prototype.py`](capabilities/social-publication/prototype.py)
- `contract` — [`capabilities/social-publication/schemas/publication-intent.v1.json`](capabilities/social-publication/schemas/publication-intent.v1.json)
- `contract` — [`capabilities/social-publication/schemas/publication-receipt.v1.json`](capabilities/social-publication/schemas/publication-receipt.v1.json)
- `documentation` — [`docs/P95_LINKEDIN_PUBLICATION_ARCHITECTURE.md`](docs/P95_LINKEDIN_PUBLICATION_ARCHITECTURE.md)
- `test` — [`tests/test_social_publication_p95.py`](tests/test_social_publication_p95.py)

## upstream-reference-discovery

Discover and qualify upstream references.

Entrypoints:
- [`capabilities/upstream-reference-discovery/lookup.py`](capabilities/upstream-reference-discovery/lookup.py)

- `documentation` — [`.agents/skills/upstream-intelligence/SKILL.md`](.agents/skills/upstream-intelligence/SKILL.md)
- `documentation` — [`.cursor/rules/upstream-intelligence.mdc`](.cursor/rules/upstream-intelligence.mdc)
- `workflow` — [`.github/workflows/upstream-reference-discovery.yml`](.github/workflows/upstream-reference-discovery.yml)
- `documentation` — [`capabilities/upstream-reference-discovery/CAPABILITY.md`](capabilities/upstream-reference-discovery/CAPABILITY.md)
- `contract` — [`capabilities/upstream-reference-discovery/capability.v1.json`](capabilities/upstream-reference-discovery/capability.v1.json)
- `source` — [`capabilities/upstream-reference-discovery/lookup.py`](capabilities/upstream-reference-discovery/lookup.py)
- `test` — [`capabilities/upstream-reference-discovery/tests/test_lookup.py`](capabilities/upstream-reference-discovery/tests/test_lookup.py)
- `contract` — [`harness/upstream-intelligence/consumer.v1.json`](harness/upstream-intelligence/consumer.v1.json)

## validation-infrastructure

Orchestrate repository-wide validation without becoming a runtime prerequisite.

- `workflow` — [`.github/workflows/product-authority.yml`](.github/workflows/product-authority.yml)
- `workflow` — [`.github/workflows/validate.yml`](.github/workflows/validate.yml)

## visual-state-compare

Compare visual observations and orchestrate OCR/browser capture adapters.

Entrypoints:
- [`capabilities/visual-state-compare/adapters/playwright-browser/capture.py`](capabilities/visual-state-compare/adapters/playwright-browser/capture.py)
- [`capabilities/visual-state-compare/benchmark_ocr.py`](capabilities/visual-state-compare/benchmark_ocr.py)
- [`capabilities/visual-state-compare/compare.py`](capabilities/visual-state-compare/compare.py)
- [`capabilities/visual-state-compare/upstreams.py`](capabilities/visual-state-compare/upstreams.py)
- [`capabilities/visual-state-compare/vision_cli.py`](capabilities/visual-state-compare/vision_cli.py)

- `workflow` — [`.github/workflows/visual-state-compare.yml`](.github/workflows/visual-state-compare.yml)
- `documentation` — [`capabilities/visual-state-compare/CAPABILITY.md`](capabilities/visual-state-compare/CAPABILITY.md)
- `adapter` — [`capabilities/visual-state-compare/adapters/ocr-paddle/recognize.py`](capabilities/visual-state-compare/adapters/ocr-paddle/recognize.py)
- `adapter` — [`capabilities/visual-state-compare/adapters/ocr-paddle/worker.py`](capabilities/visual-state-compare/adapters/ocr-paddle/worker.py)
- `adapter` — [`capabilities/visual-state-compare/adapters/ocr-tesseract/recognize.py`](capabilities/visual-state-compare/adapters/ocr-tesseract/recognize.py)
- `documentation` — [`capabilities/visual-state-compare/adapters/playwright-browser/README.md`](capabilities/visual-state-compare/adapters/playwright-browser/README.md)
- `adapter` — [`capabilities/visual-state-compare/adapters/playwright-browser/capture.py`](capabilities/visual-state-compare/adapters/playwright-browser/capture.py)
- `contract` — [`capabilities/visual-state-compare/adapters/playwright-browser/schemas/browser-visual-capture.v1.schema.json`](capabilities/visual-state-compare/adapters/playwright-browser/schemas/browser-visual-capture.v1.schema.json)
- `test` — [`capabilities/visual-state-compare/adapters/playwright-browser/tests/test_capture.py`](capabilities/visual-state-compare/adapters/playwright-browser/tests/test_capture.py)
- `source` — [`capabilities/visual-state-compare/benchmark_ocr.py`](capabilities/visual-state-compare/benchmark_ocr.py)
- `source` — [`capabilities/visual-state-compare/compare.py`](capabilities/visual-state-compare/compare.py)
- `source` — [`capabilities/visual-state-compare/ocr_common.py`](capabilities/visual-state-compare/ocr_common.py)
- `contract` — [`capabilities/visual-state-compare/schemas/visual-observation.v1.schema.json`](capabilities/visual-state-compare/schemas/visual-observation.v1.schema.json)
- `contract` — [`capabilities/visual-state-compare/schemas/visual-state-comparison.v1.schema.json`](capabilities/visual-state-compare/schemas/visual-state-comparison.v1.schema.json)
- `fixture` — [`capabilities/visual-state-compare/tests/fixtures/ocr/blank.png`](capabilities/visual-state-compare/tests/fixtures/ocr/blank.png)
- `fixture` — [`capabilities/visual-state-compare/tests/fixtures/ocr/dark_dialog.png`](capabilities/visual-state-compare/tests/fixtures/ocr/dark_dialog.png)
- `fixture` — [`capabilities/visual-state-compare/tests/fixtures/ocr/labels.v1.json`](capabilities/visual-state-compare/tests/fixtures/ocr/labels.v1.json)
- `fixture` — [`capabilities/visual-state-compare/tests/fixtures/ocr/plain_serial.png`](capabilities/visual-state-compare/tests/fixtures/ocr/plain_serial.png)
- `test` — [`capabilities/visual-state-compare/tests/generate_ocr_fixtures.py`](capabilities/visual-state-compare/tests/generate_ocr_fixtures.py)
- `test` — [`capabilities/visual-state-compare/tests/test_compare_cli.py`](capabilities/visual-state-compare/tests/test_compare_cli.py)
- `test` — [`capabilities/visual-state-compare/tests/test_upstreams.py`](capabilities/visual-state-compare/tests/test_upstreams.py)
- `test` — [`capabilities/visual-state-compare/tests/test_vision_ocr.py`](capabilities/visual-state-compare/tests/test_vision_ocr.py)
- `source` — [`capabilities/visual-state-compare/upstreams.py`](capabilities/visual-state-compare/upstreams.py)
- `contract` — [`capabilities/visual-state-compare/upstreams.v1.json`](capabilities/visual-state-compare/upstreams.v1.json)
- `source` — [`capabilities/visual-state-compare/vision_cli.py`](capabilities/visual-state-compare/vision_cli.py)
- `documentation` — [`docs/VISUAL_INTELLIGENCE_STACK.md`](docs/VISUAL_INTELLIGENCE_STACK.md)
- `test` — [`tests/test_visual_upstreams.py`](tests/test_visual_upstreams.py)

## windows-silent-scheduled-task

Register and verify silent Windows background scheduling.

Entrypoints:
- [`capabilities/windows-silent-scheduled-task/Register-SilentCron.ps1`](capabilities/windows-silent-scheduled-task/Register-SilentCron.ps1)
- [`capabilities/windows-silent-scheduled-task/adapters/node/silent_background.cjs`](capabilities/windows-silent-scheduled-task/adapters/node/silent_background.cjs)
- [`capabilities/windows-silent-scheduled-task/core/silent_background.py`](capabilities/windows-silent-scheduled-task/core/silent_background.py)
- [`capabilities/windows-silent-scheduled-task/silent_cron.py`](capabilities/windows-silent-scheduled-task/silent_cron.py)

- `documentation` — [`capabilities/windows-silent-scheduled-task/CAPABILITY.md`](capabilities/windows-silent-scheduled-task/CAPABILITY.md)
- `source` — [`capabilities/windows-silent-scheduled-task/Register-SilentCron.ps1`](capabilities/windows-silent-scheduled-task/Register-SilentCron.ps1)
- `adapter` — [`capabilities/windows-silent-scheduled-task/adapters/node/silent_background.cjs`](capabilities/windows-silent-scheduled-task/adapters/node/silent_background.cjs)
- `contract` — [`capabilities/windows-silent-scheduled-task/capability.v1.json`](capabilities/windows-silent-scheduled-task/capability.v1.json)
- `source` — [`capabilities/windows-silent-scheduled-task/core/__init__.py`](capabilities/windows-silent-scheduled-task/core/__init__.py)
- `source` — [`capabilities/windows-silent-scheduled-task/core/ensure.py`](capabilities/windows-silent-scheduled-task/core/ensure.py)
- `source` — [`capabilities/windows-silent-scheduled-task/core/pythonw.py`](capabilities/windows-silent-scheduled-task/core/pythonw.py)
- `source` — [`capabilities/windows-silent-scheduled-task/core/registry.py`](capabilities/windows-silent-scheduled-task/core/registry.py)
- `source` — [`capabilities/windows-silent-scheduled-task/core/schtasks_parse.py`](capabilities/windows-silent-scheduled-task/core/schtasks_parse.py)
- `source` — [`capabilities/windows-silent-scheduled-task/core/silence_audit.py`](capabilities/windows-silent-scheduled-task/core/silence_audit.py)
- `source` — [`capabilities/windows-silent-scheduled-task/core/silent_background.py`](capabilities/windows-silent-scheduled-task/core/silent_background.py)
- `source` — [`capabilities/windows-silent-scheduled-task/core/win_subprocess.py`](capabilities/windows-silent-scheduled-task/core/win_subprocess.py)
- `fixture` — [`capabilities/windows-silent-scheduled-task/fixtures/demo_tick.py`](capabilities/windows-silent-scheduled-task/fixtures/demo_tick.py)
- `fixture` — [`capabilities/windows-silent-scheduled-task/fixtures/registry.synthetic.v1.json`](capabilities/windows-silent-scheduled-task/fixtures/registry.synthetic.v1.json)
- `fixture` — [`capabilities/windows-silent-scheduled-task/fixtures/schtasks-list.console-python.fixture.txt`](capabilities/windows-silent-scheduled-task/fixtures/schtasks-list.console-python.fixture.txt)
- `fixture` — [`capabilities/windows-silent-scheduled-task/fixtures/schtasks-list.pythonw.fixture.txt`](capabilities/windows-silent-scheduled-task/fixtures/schtasks-list.pythonw.fixture.txt)
- `fixture` — [`capabilities/windows-silent-scheduled-task/fixtures/silence-evidence.synthetic.v1.json`](capabilities/windows-silent-scheduled-task/fixtures/silence-evidence.synthetic.v1.json)
- `contract` — [`capabilities/windows-silent-scheduled-task/schemas/silence-evidence.v1.json`](capabilities/windows-silent-scheduled-task/schemas/silence-evidence.v1.json)
- `contract` — [`capabilities/windows-silent-scheduled-task/schemas/silent-background-receipt.v1.json`](capabilities/windows-silent-scheduled-task/schemas/silent-background-receipt.v1.json)
- `contract` — [`capabilities/windows-silent-scheduled-task/schemas/silent-cron-registry.v1.json`](capabilities/windows-silent-scheduled-task/schemas/silent-cron-registry.v1.json)
- `source` — [`capabilities/windows-silent-scheduled-task/silent_cron.py`](capabilities/windows-silent-scheduled-task/silent_cron.py)
- `test` — [`capabilities/windows-silent-scheduled-task/tests/test_silence_audit.py`](capabilities/windows-silent-scheduled-task/tests/test_silence_audit.py)
- `test` — [`capabilities/windows-silent-scheduled-task/tests/test_silent_background.py`](capabilities/windows-silent-scheduled-task/tests/test_silent_background.py)
- `test` — [`capabilities/windows-silent-scheduled-task/tests/test_silent_background_node.cjs`](capabilities/windows-silent-scheduled-task/tests/test_silent_background_node.cjs)
- `test` — [`capabilities/windows-silent-scheduled-task/tests/test_silent_cron.py`](capabilities/windows-silent-scheduled-task/tests/test_silent_cron.py)
- `documentation` — [`docs/WINDOWS_SILENT_SCHEDULED_TASK_SEAM_REVIEW.md`](docs/WINDOWS_SILENT_SCHEDULED_TASK_SEAM_REVIEW.md)

