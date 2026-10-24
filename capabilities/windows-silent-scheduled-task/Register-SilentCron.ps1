#Requires -Version 5.1
<#
.SYNOPSIS
  Operator wrapper: render or apply Automation silent scheduled-task registration.

.DESCRIPTION
  Incubated capability entrypoint. Consumers supply their own job registry JSON
  conforming to automation.windows-silent-scheduled-task.registry/v1.

.PARAMETER Registry
  Path to the consumer job registry JSON.

.PARAMETER JobId
  Job id inside the registry.

.PARAMETER Apply
  Actually Register-ScheduledTask. Without -Apply, only prints the rendered plan.

.PARAMETER RepoRoot
  Consumer repository root (script paths in the registry are relative to this).
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][string] $Registry,
    [Parameter(Mandatory = $true)][string] $JobId,
    [switch] $Apply,
    [string] $RepoRoot = ""
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$capRoot = $PSScriptRoot
$python = (Get-Command python -ErrorAction SilentlyContinue | Select-Object -First 1).Source
if (-not $python) { throw "python not on PATH" }

$argv = @(
    (Join-Path $capRoot "silent_cron.py"),
    "ensure",
    "--registry", (Resolve-Path -LiteralPath $Registry).Path,
    "--job-id", $JobId
)
if ($RepoRoot) {
    $argv += @("--repo-root", (Resolve-Path -LiteralPath $RepoRoot).Path)
}
if ($Apply) {
    $argv += "--apply"
}

& $python @argv
exit $LASTEXITCODE
