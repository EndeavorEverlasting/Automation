#Requires -Version 5.1
<#
.SYNOPSIS
  Prove agreement seeding + launch.properties patch against a synthetic Ghidra tree (CI-safe).
  Optional -LiveInstallRoot runs against a real extracted Ghidra (SkipDownload + NoSmokeTest).
#>
param(
    [string]$LiveInstallRoot = ''
)
$ErrorActionPreference = 'Stop'
$capRoot = $PSScriptRoot
$boot = Join-Path $capRoot 'Bootstrap-Ghidra.ps1'
$manifest = Get-Content (Join-Path $capRoot 'ghidra-bootstrap.manifest.json') -Raw | ConvertFrom-Json

$failures = @()
$work = Join-Path $env:TEMP ("ghidra-bootstrap-prove-" + [guid]::NewGuid().ToString('N'))
$tools = Join-Path $work 'tools'
$ghidra = Join-Path $tools 'ghidra'
New-Item -ItemType Directory -Force -Path $ghidra | Out-Null
Copy-Item -Path (Join-Path $capRoot 'fixtures\synthetic-ghidra\*') -Destination $ghidra -Recurse -Force

$cleanHome = Join-Path $work 'home'
New-Item -ItemType Directory -Force -Path $cleanHome | Out-Null
$prevProfile = $env:USERPROFILE
$env:USERPROFILE = $cleanHome
try {
    & $boot -InstallRoot $tools -SkipDownload -NoSmokeTest -SkipJdkInstall
    if ($LASTEXITCODE -ne 0) { $failures += "synthetic bootstrap exit $LASTEXITCODE" }
} finally {
    $env:USERPROFILE = $prevProfile
}

$pref = Join-Path $cleanHome ".ghidra\$($manifest.ghidra.settings_dir_name)\preferences"
if (-not (Test-Path $pref)) { $failures += "missing preferences $pref" }
elseif ((Get-Content $pref -Raw) -notmatch 'USER_AGREEMENT=ACCEPT') {
    $failures += 'preferences missing USER_AGREEMENT=ACCEPT'
}

$lp = Join-Path $ghidra 'support\launch.properties'
$lpText = Get-Content $lp -Raw
if ($lpText -notmatch '(?m)^VMARGS=-DUSER_AGREEMENT=ACCEPT\s*$') { $failures += 'launch.properties missing VMARGS' }
if ($lpText -notmatch '(?m)^JAVA_HOME_OVERRIDE=.+') { $failures += 'JAVA_HOME_OVERRIDE not set' }
if (-not (Test-Path (Join-Path $ghidra 'ghidraRun-accepted.bat'))) { $failures += 'missing ghidraRun-accepted.bat' }

if ($LiveInstallRoot) {
    & $boot -InstallRoot $LiveInstallRoot -SkipDownload -NoSmokeTest
    if ($LASTEXITCODE -ne 0) { $failures += "live bootstrap exit $LASTEXITCODE" }
}

$result = [ordered]@{
    status = $(if ($failures.Count) { 'FAIL' } else { 'PASS' })
    proof_level = $(if ($failures.Count) { 'UNPROVEN' } else { 'OBSERVED_AGREEMENT_SEEDED_SYNTHETIC' })
    work = $work
    failures = $failures
    capability = 'ghidra-bootstrap'
}
$outDir = Join-Path (Split-Path $capRoot -Parent | Split-Path -Parent) 'Outputs\ghidra-bootstrap'
New-Item -ItemType Directory -Force -Path $outDir | Out-Null
$receipt = Join-Path $outDir ("prove-" + (Get-Date).ToUniversalTime().ToString('yyyyMMddTHHmmssZ') + '.json')
($result | ConvertTo-Json -Depth 5) | Set-Content $receipt -Encoding utf8
Write-Host ($result | ConvertTo-Json -Depth 5)
Write-Host "RECEIPT=$receipt"
if ($failures.Count) { exit 1 }
exit 0
