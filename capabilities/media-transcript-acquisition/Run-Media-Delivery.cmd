@echo off
setlocal
rem Explicitly launched by user; no install, account change, or scheduler.
where py >nul 2>nul
if errorlevel 1 goto :python_fallback
py -3 -c "import sys; sys.exit(0 if sys.version_info >= (3, 11) else 1)" >nul 2>nul
if errorlevel 1 goto :python_fallback
py -3 "%~dp0host_app.py" %*
exit /b %errorlevel%
:python_fallback
where python >nul 2>nul
if errorlevel 1 goto :missing_python
python -c "import sys; sys.exit(0 if sys.version_info >= (3, 11) else 1)" >nul 2>nul
if errorlevel 1 goto :missing_python
python "%~dp0host_app.py" %*
exit /b %errorlevel%
:missing_python
echo Python 3.11+ was not found. Read HOST_SETUP.md for manual installation.
exit /b 2
