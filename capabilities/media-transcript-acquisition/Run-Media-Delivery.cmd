@echo off
setlocal
rem User-launched only; no scheduler, downloads or installation without a URL.
pushd "%~dp0"
where py >nul 2>nul
if %errorlevel%==0 (
  py -3 "%~dp0host_app.py" %*
) else (
  where python >nul 2>nul
  if errorlevel 1 (
    echo Python 3.11+ was not found. Open HOST_SETUP.md for installation steps.
    popd
    exit /b 2
  )
  python "%~dp0host_app.py" %*
)
set "exit_status=%errorlevel%"
popd
exit /b %exit_status%
