# P95 — Signal → Drive host program design

Status: **P95 EXECUTABLE PROTOTYPE / LIVE DRIVE+UIA UNPROVEN**  
Date: 2026-11-06  
Repository: `EndeavorEverlasting/Automation`  
Program: `signal-drive-transfer`  
Resolved via: Automation `scripts/prompt_runtime.py` → upstream Prompt Kit **P95** (`Program Design & Call-Stack Prototype Architect`, source blob `5926a198…`, SHA-256 `cd796bb7…`)

## User outcomes / invariants

1. Import an ordered Signal selection (nine Note-to-Self messages in the motivating run) into Docs/Drive faithfully.
2. Images must arrive by **Save-As export files** and/or **UIA → clipboard → paste/upload**.
3. **Ban** print-screen and every screenshot-capture avenue (Signal blocks them; policy fail-closed).
4. No relevance judgment. Preserve order/count/body/attachment bytes.
5. Durable host logic lands in **Automation**, not Moonwake/TokenCorridor.
6. Reconcile to an externally owned Doc only when writable; otherwise working Doc remains source of truth (`AWAITING_GRANT`).

## Evidence floor

- Sibling Signal pipeline + `HOST-LOGIC-SPEC.md` / `AUTOMATION-HANDOFF.md` in Project store.
- Landed Save-As export: `media/signal-transfer/export-20261106-182436` (20 PNGs / 4 timestamp groups: 9+4+6+1).
- Automation capability patterns: `media-transcript-acquisition` host CLI, `document-formatting` Docs adapter, fail-closed receipts.
- Moonwake Entire-host Trifecta is **method only** and is sequenced **after** this P95 completes.

## Candidates compared

| Candidate | Result | Reason |
| --- | --- | --- |
| Screenshot / PrintScreen capture host | **REJECTED** | Explicitly banned; Signal blocks; brittle and non-portable. |
| SQLCipher decrypt as sole media path | **DEFERRED optional adapter** | Proven privately, but key/DPAPI coupling; Save-As is the operator-landed durable media path. |
| MCP-only one-off scripts in Project store | **REJECTED as architecture** | Not reusable host logic for other apps. |
| Save-As export + optional UIA clipboard dual media ports → markdown package → Drive publish plan | **SELECTED** | Matches landed export, policy bans, Automation capability shape, and Docs paste goal. |

## Domain vocabulary

- **Selection** — ordered UIA export (`selected-messages.json`).
- **Export package** — Signal Save-As directory (flat `signal-*-*.png` groups or message files).
- **Media group** — one timestamp stem’s images (= one attachment-bearing message).
- **Match spec** — exact/startsWith/includes/emptyWithAttachment rules (DB path).
- **Document bundle** — index + per-message markdown + doc-clean.
- **Media policy** — admit/deny acquisition sources and actions.
- **Publish plan** — semantic working/index/per-message/image/reconcile ops.
- **Drive transport** — injected MCP/token callback; not hard-coded private IDs in core.
- **Clipboard media adapter** — UIA focus → clipboard copy → image bytes → Docs paste/upload.

## Module / ownership map

```text
host_transfer.py (CLI)
  -> core.selection / core.export_ingest / core.match
  -> core.media_policy (ban print-screen)
  -> core.document / core.accept
  -> core.transfer (receipt + publish plan)
  -> adapters.clipboard_media (optional live UIA hooks)
  -> adapters.drive (injected transport)
```

Dependency direction: CLI → core → adapters → external OS/Drive. No cycles. Private Drive IDs stay outside public Git.

## Success call stack (export-primary)

```text
OPERATOR/CLI: plan --export-dir --selection --profile
  -> validate selection
  -> ingest Save-As export (group signal-*-*.png)
  -> merge media groups onto attachment-bearing ordinals
  -> admit media policy (export/clipboard only)
  -> build document bundle
  -> evaluate acceptance (count/ordinals/attachments)
  -> emit publish plan + receipt (dry-run)
  -> optional drive transport upsert/upload/reconcile
```

Terminal user value: faithful Doc package + image upload/paste plan for all selected messages, not “opened a folder.”

## Failure call stacks prototyped

| Failure | Classification |
| --- | --- |
| `mediaSource=printscreen` / screenshot action | `MEDIA_SOURCE_BANNED` / `MEDIA_ACTION_BANNED` |
| media group count ≠ attachment-bearing selection | `EXPORT_MEDIA_ALIGN` / `EXPORT_MEDIA_GROUP_COUNT` |
| clipboard non-image payload | `CLIPBOARD_NOT_IMAGE` |
| Drive `appNotAuthorizedToFile` | `AWAITING_GRANT` → working Doc remains source of truth |

## Executable prototypes created

- `core/media_policy.py`
- `core/export_ingest.py` (flat Signal Save-As grouping + selection merge)
- `core/transfer.py` dry-run orchestration
- `adapters/clipboard_media.py` admitted clipboard seam
- `adapters/drive.py` typed publish/error classification
- `host_transfer.py` doctor/ingest-export/admit-media/plan
- unittest suite under `capabilities/signal-drive-transfer/tests/`

## Proof ceiling / next after P95

P95 proves program seams offline. It does **not** claim live Drive writes or live UIA clipboard paste.

**Next sequence (only after this P95 fixed point):** Trifecta against Automation host logic (P83 source-faithfulness → P82 measured refine → P07 bounded implementation polish/integration → P08 live proof where authorized), still forbidding print-screen and Moonwake as landing place.
