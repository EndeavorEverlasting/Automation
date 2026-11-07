# Signal → Drive transfer

**Identity:** `automation.signal-drive-transfer/v1`  
**Ownership:** Automation reusable host logic for deterministic Signal selection/export → markdown package → Drive/Docs publish planning.  
**Status:** P95 program design + executable call-stack prototypes. Live Drive publish and live UIA clipboard paste remain separate proof gates.

## User outcome

Traverse an ordered set of Signal messages (commonly nine Note-to-Self selections) and land faithful text + images into Google Docs/Drive **without judgment filtering** and **without print-screen**.

## Media acquisition invariant (hard)

| Allowed | Banned |
| --- | --- |
| Signal Desktop **Save As** export files | PrintScreen / SysRq |
| UIA focus attachment → **clipboard copy** → Docs/Drive paste | Snipping Tool / DXGI / BitBlt / any screenshot capture |
| Optional pre-decrypted attachment files from a private DB adapter | Inferring images by capturing the Signal window |

Signal blocks screenshot detection; this capability treats screenshot avenues as fail-closed policy violations.

## Entrypoints

```powershell
python capabilities/signal-drive-transfer/host_transfer.py doctor

python capabilities/signal-drive-transfer/host_transfer.py admit-media `
  --source signal-save-as-export --action read-export-file

python capabilities/signal-drive-transfer/host_transfer.py discover-export `
  --export-root PATH\to\media\signal-transfer

python capabilities/signal-drive-transfer/host_transfer.py ingest-export `
  --export-root PATH\to\media\signal-transfer `
  --expected-media-groups 3

python capabilities/signal-drive-transfer/host_transfer.py plan `
  --profile capabilities/signal-drive-transfer/fixtures/transfer-profile.synthetic.v1.json `
  --selection capabilities/signal-drive-transfer/fixtures/selected-messages.synthetic.v1.json `
  --export-root PATH\to\media\signal-transfer

python capabilities/signal-drive-transfer/host_transfer.py attach-media `
  --markdown PATH\to\doc-clean.md `
  --uploads PATH\to\DRIVE-PNG-RECEIPT.json `
  --out PATH\to\doc-clean-with-drive-links.md

python capabilities/signal-drive-transfer/host_transfer.py publish `
  --profile PATH\to\profile.json `
  --selection PATH\to\selected-messages.json `
  --export-root PATH\to\media\signal-transfer `
  --transport PATH\to\private_transport.py
```

`publish` without `--transport` returns a deterministic `PLANNED_NO_TRANSPORT` receipt that still encodes the drive.file sibling fallback rule. With a private transport module exposing `transport(op, payload)`, it uploads images, rewrites markdown links, upserts the working Doc, and on `appNotAuthorizedToFile` creates a connector-writable sibling Doc as source of truth.

## Stages

1. **discover-export** — pick latest `export-YYYYMMDD-HHMMSS` (or Signal-image folder) under a root
2. **capture-selection** (optional UIA JSON) — ordered `selected-messages.json`
3. **ingest-export** — Save-As folder (flat Signal `signal-*-*.png` groups or message files)
4. **merge** — attach export media groups onto attachment-bearing selection rows by order
5. **render-markdown** — index + per-message + `doc-clean`
6. **admit-media** — fail closed on screenshot sources/actions
7. **attach-media** — rewrite attachment backticks to Drive `webViewLink` targets after upload
8. **drive-publish** — working Doc / INDEX / image uploads / reconcile-when-writable; **drive.file sibling fallback** on 403 `appNotAuthorizedToFile`
9. **clipboard path** (optional adapter) — UIA focus → clipboard image → paste/upload

SQLCipher decrypt remains an optional private adapter, not the required media path.

## Privacy

- Do not commit Signal DB keys, private message bodies, or real Drive file IDs.
- Public fixtures are synthetic only.
- Private locator mappings (original Doc id, folder id) stay outside public Git; profiles use semantic targets.

## Validation

```powershell
python -m unittest discover -s capabilities/signal-drive-transfer/tests -p 'test_*.py' -v
```

Offline PASS is not live Drive write proof and not live UIA clipboard proof.

## Non-goals

- Relevance/keyword filtering of messages
- Entire hook/upload trust mutation
- Task Scheduler mutation
- Print-screen workarounds
- Owning Moonwake/TokenCorridor as the durable landing place
