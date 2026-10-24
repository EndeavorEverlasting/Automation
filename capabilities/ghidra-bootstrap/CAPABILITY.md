# Ghidra bootstrap

## Purpose

Deterministic, **agent-free** Windows bootstrap for NSA Ghidra:

1. Ensure a supported JDK (winget Temurin by default)
2. Download a **pinned** Ghidra release and verify SHA-256
3. Accept the first-run user agreement without a human click
4. Pin `JAVA_HOME_OVERRIDE` so LaunchSupport does not open a Java config maze
5. Emit a durable launcher and an optional headless smoke receipt

## Why this belongs in Automation

Any reverse-engineering lab, malware triage workspace, or REA/Ghidra consumer needs the same install + agreement gate. The core is repository-agnostic: install root is configuration (`-InstallRoot` or `%LOCALAPPDATA%\Automation\ghidra-bootstrap\tools`), not a product path.

## Agreement semantics (“I agree”)

Ghidra’s GUI `UserAgreementDialog` is skipped when `USER_AGREEMENT=ACCEPT` (NSA CI documentation / issue #9124). Clicking **I agree** persists that property. This capability:

- writes `%USERPROFILE%\.ghidra\<settings_dir>\preferences`
- appends `VMARGS=-DUSER_AGREEMENT=ACCEPT` to `support\launch.properties`
- ships `ghidraRun-accepted.bat` with `JAVA_TOOL_OPTIONS=-DUSER_AGREEMENT=ACCEPT`

Optional `-ClickAgreeUi` drives the real Swing button via UI Automation.

## Entrypoints

| Surface | Path |
|---------|------|
| Root wayfinding CMD | `Bootstrap-Ghidra.cmd` |
| Canonical CMD | `capabilities/ghidra-bootstrap/Bootstrap-Ghidra.cmd` |
| Implementation | `capabilities/ghidra-bootstrap/Bootstrap-Ghidra.ps1` |
| Version pin | `capabilities/ghidra-bootstrap/ghidra-bootstrap.manifest.json` |
| Synthetic proof | `capabilities/ghidra-bootstrap/Prove-GhidraBootstrap.ps1` |

```bat
Bootstrap-Ghidra.cmd
Bootstrap-Ghidra.cmd -InstallRoot D:\tools
Bootstrap-Ghidra.cmd -ClickAgreeUi
```

```powershell
pwsh -File capabilities\ghidra-bootstrap\Prove-GhidraBootstrap.ps1
```

## Non-goals

- Owning malware-lab case workflows, VirtualBox/FLARE guest bootstrap, or sample execution policy
- Installing IDA/JADX/other engines
- Claiming live GUI click proof from preference seeding alone (use `-ClickAgreeUi` for that lane)

## Proof ceiling

- Synthetic: agreement prefs + launch.properties patch on `fixtures/synthetic-ghidra` (CI-safe)
- Live: full download/verify/smoke against a real Ghidra tree on an operator workstation
