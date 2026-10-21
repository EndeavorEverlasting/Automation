#Requires -Version 5.1
<#
.SYNOPSIS
  Deterministic, agent-free Ghidra bootstrap for Windows:
  JDK (optional via winget) -> download/verify/extract Ghidra -> accept user agreement
  -> pin JAVA_HOME_OVERRIDE -> write launchers -> optional smoke proof.

.DESCRIPTION
  Agreement accept uses the official automation path:
    -DUSER_AGREEMENT=ACCEPT  (and persisted preferences USER_AGREEMENT=ACCEPT)
  That is the same gate as the GUI "I agree" button (GhidraApplicationConfiguration.showUserAgreement).

  Optional -ClickAgreeUi also drives the real Swing dialog via UI Automation when a dialog is shown
  (defense in depth / literal button press). Default path does not need a GUI.

.PARAMETER InstallRoot
  Directory that will contain ghidra\ .
  Default: %LOCALAPPDATA%\Automation\ghidra-bootstrap\tools (consumer-agnostic; not a product repo path).

.PARAMETER SkipJdkInstall
  Do not winget-install JDK; fail if no suitable JDK is found.

.PARAMETER SkipDownload
  Use an existing InstallRoot\ghidra tree (still patches agreement + launch props).

.PARAMETER ClickAgreeUi
  After seeding, briefly launch GUI and attempt to click Agree / I agree if a dialog appears.

.PARAMETER SmokeTest
  Run analyzeHeadless import of a disposable fixture (default: on).
#>
[CmdletBinding()]
param(
    [string]$InstallRoot = '',
    [string]$ManifestPath = '',
    [switch]$SkipJdkInstall,
    [switch]$SkipDownload,
    [switch]$ClickAgreeUi,
    [switch]$NoSmokeTest,
    [switch]$ForceRedownload
)

$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'

function Write-Step([string]$Message) { Write-Host "[bootstrap-ghidra] $Message" }

function Get-ScriptRoot {
    if ($PSScriptRoot) { return $PSScriptRoot }
    return Split-Path -Parent $MyInvocation.MyCommand.Path
}

function Resolve-InstallRoot([string]$Requested) {
    if ($Requested) { return [IO.Path]::GetFullPath($Requested) }
    $localApp = $env:LOCALAPPDATA
    if ($localApp) {
        return [IO.Path]::GetFullPath((Join-Path $localApp 'Automation\ghidra-bootstrap\tools'))
    }
    return [IO.Path]::GetFullPath((Join-Path (Get-Location) 'tools'))
}

function Get-Manifest([string]$Path) {
    $scriptRoot = Get-ScriptRoot
    if (-not $Path) { $Path = Join-Path $scriptRoot 'ghidra-bootstrap.manifest.json' }
    if (-not (Test-Path -LiteralPath $Path)) { throw "Manifest missing: $Path" }
    return Get-Content -LiteralPath $Path -Raw -Encoding UTF8 | ConvertFrom-Json
}

function Find-JdkHome([int]$MinMajor) {
    $candidates = @()
    if ($env:JAVA_HOME) { $candidates += $env:JAVA_HOME }
    $cmd = Get-Command java -ErrorAction SilentlyContinue
    if ($cmd) { $candidates += (Split-Path (Split-Path $cmd.Source)) }
    $candidates += @(
        'C:\Program Files\Eclipse Adoptium\jdk-21*'
        'C:\Program Files\Eclipse Adoptium\jdk-25*'
        'C:\Program Files\Microsoft\jdk-21*'
        'C:\Program Files\Microsoft\jdk-25*'
        'C:\Program Files\Java\jdk-21*'
        'C:\Program Files\Java\jdk-25*'
    )
    foreach ($pattern in $candidates) {
        foreach ($item in (Get-Item $pattern -ErrorAction SilentlyContinue)) {
            $java = Join-Path $item.FullName 'bin\java.exe'
            if (-not (Test-Path $java)) { continue }
            # java -version writes to stderr; Windows PowerShell + Stop would otherwise abort
            $prevEap = $ErrorActionPreference
            $ErrorActionPreference = 'Continue'
            try {
                $verOut = (& $java -version 2>&1 | ForEach-Object { "$_" }) -join "`n"
            } finally {
                $ErrorActionPreference = $prevEap
            }
            if ($verOut -match 'version "(\d+)') {
                $major = [int]$Matches[1]
                if ($major -ge $MinMajor) { return $item.FullName }
            }
        }
    }
    return $null
}

function Ensure-Jdk {
    param($Manifest, [switch]$SkipInstall)
    $jdkHome = Find-JdkHome -MinMajor ([int]$Manifest.jdk.major)
    if ($jdkHome) {
        Write-Step "JDK found: $jdkHome"
        return $jdkHome
    }
    if ($SkipInstall) { throw "No JDK $($Manifest.jdk.major)+ found and -SkipJdkInstall set." }
    $winget = Get-Command winget -ErrorAction SilentlyContinue
    if (-not $winget) { throw 'winget not found; install Temurin JDK 21+ manually, then re-run.' }
    Write-Step "Installing $($Manifest.jdk.winget_id) via winget..."
    & winget install --id $Manifest.jdk.winget_id -e --accept-package-agreements --accept-source-agreements --disable-interactivity
    if ($LASTEXITCODE -ne 0) { throw "winget install failed with exit $LASTEXITCODE" }
    # Refresh PATH for this process
    $env:Path = [Environment]::GetEnvironmentVariable('Path', 'Machine') + ';' + [Environment]::GetEnvironmentVariable('Path', 'User')
    $jdkHome = Find-JdkHome -MinMajor ([int]$Manifest.jdk.major)
    if (-not $jdkHome) { throw 'JDK install finished but java home still not found. Open a new shell and re-run.' }
    return $jdkHome
}

function Install-GhidraTree {
    param($Manifest, [string]$ToolsDir, [switch]$Skip, [switch]$Force)
    $ghidraHome = Join-Path $ToolsDir 'ghidra'
    $marker = Join-Path $ghidraHome 'ghidraRun.bat'
    if ($Skip) {
        if (-not (Test-Path $marker)) { throw "SkipDownload set but missing $marker" }
        return $ghidraHome
    }
    New-Item -ItemType Directory -Force -Path $ToolsDir | Out-Null
    $zip = Join-Path $ToolsDir $Manifest.ghidra.zip_name
    $needDownload = $Force -or -not (Test-Path $zip)
    if ((Test-Path $zip) -and -not $Force) {
        $hash = (Get-FileHash -Algorithm SHA256 -LiteralPath $zip).Hash.ToLower()
        if ($hash -ne $Manifest.ghidra.sha256.ToLower()) {
            Write-Step 'Existing zip hash mismatch; re-downloading.'
            $needDownload = $true
        }
    }
    if ($needDownload) {
        Write-Step "Downloading $($Manifest.ghidra.url)"
        Invoke-WebRequest -Uri $Manifest.ghidra.url -OutFile $zip -UseBasicParsing
    }
    $hash = (Get-FileHash -Algorithm SHA256 -LiteralPath $zip).Hash.ToLower()
    if ($hash -ne $Manifest.ghidra.sha256.ToLower()) {
        throw "SHA256 mismatch for Ghidra zip. expected=$($Manifest.ghidra.sha256) actual=$hash"
    }
    Write-Step "SHA256 OK: $hash"
    if ((Test-Path $ghidraHome) -and $Force) {
        Remove-Item -LiteralPath $ghidraHome -Recurse -Force
    }
    if (-not (Test-Path $marker)) {
        $stage = Join-Path $ToolsDir ("_ghidra_extract_" + [guid]::NewGuid().ToString('N'))
        New-Item -ItemType Directory -Force -Path $stage | Out-Null
        try {
            Write-Step 'Extracting zip...'
            Expand-Archive -LiteralPath $zip -DestinationPath $stage -Force
            $inner = Get-ChildItem $stage -Directory | Select-Object -First 1
            if (-not $inner) { throw 'Zip contained no directory.' }
            if (Test-Path $ghidraHome) { Remove-Item -LiteralPath $ghidraHome -Recurse -Force }
            Move-Item -LiteralPath $inner.FullName -Destination $ghidraHome
        }
        finally {
            Remove-Item -LiteralPath $stage -Recurse -Force -ErrorAction SilentlyContinue
        }
    }
    if (-not (Test-Path $marker)) { throw "Extract failed; missing $marker" }
    return $ghidraHome
}

function Set-LaunchProperties {
    param([string]$GhidraHome, [string]$JavaHome)
    $props = Join-Path $GhidraHome 'support\launch.properties'
    if (-not (Test-Path $props)) { throw "Missing $props" }
    $raw = Get-Content -LiteralPath $props -Raw
    $javaEsc = $JavaHome -replace '\\', '/'
    if ($raw -match '(?m)^JAVA_HOME_OVERRIDE=.*$') {
        $raw = [regex]::Replace($raw, '(?m)^JAVA_HOME_OVERRIDE=.*$', "JAVA_HOME_OVERRIDE=$javaEsc")
    } else {
        $raw = "JAVA_HOME_OVERRIDE=$javaEsc`r`n" + $raw
    }
    if ($raw -notmatch '(?m)^VMARGS=-DUSER_AGREEMENT=ACCEPT\s*$') {
        $raw = $raw.TrimEnd() + "`r`n`r`n# malware-lab bootstrap: non-interactive user agreement (I agree)`r`nVMARGS=-DUSER_AGREEMENT=ACCEPT`r`n"
    }
    $utf8 = New-Object System.Text.UTF8Encoding $false
    [IO.File]::WriteAllText($props, $raw, $utf8)
    Write-Step "Patched launch.properties JAVA_HOME_OVERRIDE + USER_AGREEMENT"
}

function Get-GhidraSettingsDir {
    param($Manifest, [string]$UserProfile = $env:USERPROFILE)
    $name = $Manifest.ghidra.settings_dir_name
    return (Join-Path $UserProfile (Join-Path '.ghidra' $name))
}

function Accept-UserAgreement {
    param($Manifest, [string]$GhidraHome, [string]$UserProfile = $env:USERPROFILE)
    $settings = Get-GhidraSettingsDir -Manifest $Manifest -UserProfile $UserProfile
    New-Item -ItemType Directory -Force -Path $settings | Out-Null
    $prefFile = Join-Path $settings 'preferences'
    $prop = $Manifest.agreement.property
    $val = $Manifest.agreement.accepted_value
    $lines = @()
    if (Test-Path $prefFile) {
        $lines = Get-Content -LiteralPath $prefFile
        $lines = $lines | Where-Object { $_ -notmatch ("^\s*" + [regex]::Escape($prop) + '\s*=') }
    }
    $lines += "$prop=$val"
    # Quiet first-run tip noise when present in older builds
    if (-not ($lines | Where-Object { $_ -match '^\s*Show.?Tips' })) {
        $lines += 'Tips of the Day.Show Tips=false'
    }
    Set-Content -LiteralPath $prefFile -Value ($lines -join "`r`n") -Encoding ascii
    Write-Step "Wrote $prefFile ($prop=$val)"

    # Durable env snippet for shells / REA / CI
    $envSnippet = Join-Path (Split-Path $GhidraHome -Parent) 'ghidra-agreement.env.cmd'
    @"
@echo off
REM Generated by Bootstrap-Ghidra.ps1 — same effect as clicking I agree
set "JAVA_TOOL_OPTIONS=-DUSER_AGREEMENT=ACCEPT %JAVA_TOOL_OPTIONS%"
set "GHIDRA_INSTALL_DIR=$GhidraHome"
"@ | Set-Content -LiteralPath $envSnippet -Encoding ascii

    return [pscustomobject]@{
        SettingsDir = $settings
        Preferences = $prefFile
        EnvSnippet  = $envSnippet
    }
}

function Write-AcceptedLauncher {
    param([string]$GhidraHome)
    $launcher = Join-Path $GhidraHome 'ghidraRun-accepted.bat'
    @"
@echo off
REM Deterministic launch: agreement pre-accepted (NSA CI property + launch.properties VMARGS)
set "JAVA_TOOL_OPTIONS=-DUSER_AGREEMENT=ACCEPT %JAVA_TOOL_OPTIONS%"
call "%~dp0ghidraRun.bat" %*
"@ | Set-Content -LiteralPath $launcher -Encoding ascii
    Write-Step "Wrote $launcher"
    return $launcher
}

function Invoke-AgreeUiClick {
    param([string]$GhidraHome, [int]$TimeoutSec = 90)
    Write-Step 'Launching GUI to click Agree if dialog appears...'
    $env:JAVA_TOOL_OPTIONS = ($env:JAVA_TOOL_OPTIONS -replace '-DUSER_AGREEMENT=ACCEPT', '').Trim()
    # Intentionally clear property so dialog can appear for literal click proof when prefs wiped;
    # if prefs already ACCEPT, dialog will not show — that is still success.
    Add-Type -AssemblyName UIAutomationClient
    Add-Type -AssemblyName UIAutomationTypes
    $proc = Start-Process -FilePath (Join-Path $GhidraHome 'ghidraRun.bat') -WorkingDirectory $GhidraHome -PassThru
    $deadline = [datetime]::UtcNow.AddSeconds($TimeoutSec)
    $clicked = $false
    $sawFront = $false
    while ([datetime]::UtcNow -lt $deadline) {
        Start-Sleep -Milliseconds 500
        try {
            $root = [System.Windows.Automation.AutomationElement]::RootElement
            $cond = New-Object System.Windows.Automation.PropertyCondition `
                ([System.Windows.Automation.AutomationElement]::ControlTypeProperty), `
                ([System.Windows.Automation.ControlType]::Button)
            $buttons = $root.FindAll([System.Windows.Automation.TreeScope]::Descendants, $cond)
            foreach ($b in $buttons) {
                $name = $b.Current.Name
                if ($name -match '(?i)agree|accept|i agree|yes') {
                    $invoke = $b.GetCurrentPattern([System.Windows.Automation.InvokePattern]::Pattern)
                    $invoke.Invoke()
                    $clicked = $true
                    Write-Step "Clicked UI button: $name"
                    break
                }
            }
            $winCond = New-Object System.Windows.Automation.PropertyCondition `
                ([System.Windows.Automation.AutomationElement]::NameProperty), 'Ghidra'
            $win = $root.FindFirst([System.Windows.Automation.TreeScope]::Children, $winCond)
            if ($win) { $sawFront = $true }
        } catch {
            # keep polling
        }
        if ($clicked -or $sawFront) { break }
    }
    Start-Sleep -Seconds 2
    Get-CimInstance Win32_Process -Filter "Name='java.exe'" -ErrorAction SilentlyContinue |
        Where-Object { $_.CommandLine -match 'ghidra' } |
        ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }
    if (-not $proc.HasExited) { Stop-Process -Id $proc.Id -Force -ErrorAction SilentlyContinue }
    return [pscustomobject]@{ Clicked = $clicked; SawFrontEnd = $sawFront; Pid = $proc.Id }
}

function Invoke-SmokeTest {
    param([string]$GhidraHome, [string]$JavaHome, [string]$ProofDir)
    $env:JAVA_HOME = $JavaHome
    $env:JAVA_TOOL_OPTIONS = '-DUSER_AGREEMENT=ACCEPT'
    $analyze = Join-Path $GhidraHome 'support\analyzeHeadless.bat'
    $fxDir = Join-Path $ProofDir 'fixtures'
    New-Item -ItemType Directory -Force -Path $fxDir | Out-Null
    $fx = Join-Path $fxDir 'bootstrap-smoke-cmd.exe'
    Copy-Item -LiteralPath "$env:WINDIR\System32\cmd.exe" -Destination $fx -Force
    $proj = Join-Path $ProofDir 'ghidra-smoke-project'
    New-Item -ItemType Directory -Force -Path $proj | Out-Null
    $log = Join-Path $ProofDir "bootstrap-smoke-$(Get-Date -Format 'yyyyMMddTHHmmssZ').log"
    $args = "`"$proj`" smoke -import `"$fx`" -deleteProject -noanalysis"
    $p = Start-Process -FilePath $analyze -ArgumentList $args -WorkingDirectory (Split-Path $analyze) `
        -RedirectStandardOutput $log -RedirectStandardError "$log.err" -Wait -PassThru -NoNewWindow
    if ($p.ExitCode -ne 0) { throw "Smoke analyzeHeadless failed exit=$($p.ExitCode) log=$log" }
    Write-Step "Smoke PASS (analyzeHeadless exit 0) log=$log"
    return $log
}

# --- main ---
$manifest = Get-Manifest -Path $ManifestPath
$toolsDir = Resolve-InstallRoot -Requested $InstallRoot
$proofDir = Join-Path (Split-Path $toolsDir -Parent) 'proof\runtime'
if (-not (Test-Path (Split-Path $toolsDir -Parent))) {
    $proofDir = Join-Path $toolsDir '_proof'
}
New-Item -ItemType Directory -Force -Path $proofDir | Out-Null

Write-Step "InstallRoot=$toolsDir"
$javaHome = Ensure-Jdk -Manifest $manifest -SkipInstall:$SkipJdkInstall
$env:JAVA_HOME = $javaHome
$ghidraHome = Install-GhidraTree -Manifest $manifest -ToolsDir $toolsDir -Skip:$SkipDownload -Force:$ForceRedownload
Set-LaunchProperties -GhidraHome $ghidraHome -JavaHome $javaHome
$agree = Accept-UserAgreement -Manifest $manifest -GhidraHome $ghidraHome
$launcher = Write-AcceptedLauncher -GhidraHome $ghidraHome

$ui = $null
if ($ClickAgreeUi) {
    # Temporarily move ACCEPT aside so dialog can appear, then click, then restore
    $pref = $agree.Preferences
    $backup = Get-Content -LiteralPath $pref -ErrorAction SilentlyContinue
    Set-Content -LiteralPath $pref -Value (($backup | Where-Object { $_ -notmatch 'USER_AGREEMENT' }) -join "`r`n") -Encoding ascii
    try {
        $ui = Invoke-AgreeUiClick -GhidraHome $ghidraHome
    } finally {
        Accept-UserAgreement -Manifest $manifest -GhidraHome $ghidraHome | Out-Null
    }
}

$smokeLog = $null
if (-not $NoSmokeTest) {
    $smokeLog = Invoke-SmokeTest -GhidraHome $ghidraHome -JavaHome $javaHome -ProofDir $proofDir
}

$receipt = [ordered]@{
    utc = (Get-Date).ToUniversalTime().ToString('o')
    ghidra_home = $ghidraHome
    java_home = $javaHome
    preferences = $agree.Preferences
    launcher = $launcher
    agreement = 'USER_AGREEMENT=ACCEPT'
    ui = $ui
    smoke_log = $smokeLog
    proof_level = if ($smokeLog) { 'OBSERVED_BOOTSTRAP_SMOKE' } else { 'OBSERVED_BOOTSTRAP_CONFIGURED' }
}
$receiptPath = Join-Path $proofDir ("ghidra-bootstrap-" + (Get-Date).ToUniversalTime().ToString('yyyyMMddTHHmmssZ') + '.json')
($receipt | ConvertTo-Json -Depth 6) | Set-Content -LiteralPath $receiptPath -Encoding utf8
Write-Step "RECEIPT=$receiptPath"
Write-Host ($receipt | ConvertTo-Json -Depth 6)
exit 0
