@echo off
setlocal EnableExtensions EnableDelayedExpansion
REM ============================================================================
REM  Bootstrap-Ghidra.cmd — deterministic, agent-free Ghidra install + "I agree"
REM  Owned by: capabilities/ghidra-bootstrap (EndeavorEverlasting/Automation)
REM
REM  Usage:
REM    Bootstrap-Ghidra.cmd
REM    Bootstrap-Ghidra.cmd -ClickAgreeUi
REM    Bootstrap-Ghidra.cmd -InstallRoot D:\tools
REM ============================================================================

set "ROOT=%~dp0"
set "ROOT=%ROOT:~0,-1%"
set "PS1=%ROOT%\Bootstrap-Ghidra.ps1"
set "MANIFEST=%ROOT%\ghidra-bootstrap.manifest.json"

if not exist "%PS1%" (
  echo [Bootstrap-Ghidra] Missing "%PS1%"
  exit /b 2
)

set "HAS_ROOT=0"
echo.%*| findstr /I /C:"-InstallRoot" >nul
if not errorlevel 1 set "HAS_ROOT=1"

set "PS=powershell.exe"
where pwsh >nul 2>&1 && set "PS=pwsh.exe"

if "%HAS_ROOT%"=="1" (
  "%PS%" -NoProfile -ExecutionPolicy Bypass -File "%PS1%" -ManifestPath "%MANIFEST%" %*
) else (
  "%PS%" -NoProfile -ExecutionPolicy Bypass -File "%PS1%" -ManifestPath "%MANIFEST%" %*
)
set "EC=!ERRORLEVEL!"
if not "!EC!"=="0" (
  echo [Bootstrap-Ghidra] FAILED exit=!EC!
  exit /b !EC!
)

set "DEFAULT_LAUNCH=%LOCALAPPDATA%\Automation\ghidra-bootstrap\tools\ghidra\ghidraRun-accepted.bat"
echo [Bootstrap-Ghidra] OK
echo [Bootstrap-Ghidra] Default install root: %%LOCALAPPDATA%%\Automation\ghidra-bootstrap\tools
echo [Bootstrap-Ghidra] Launch ^(if default root^): "%DEFAULT_LAUNCH%"
exit /b 0
