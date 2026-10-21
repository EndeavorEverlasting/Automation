@echo off
REM Root wayfinding shim — canonical owner is capabilities\ghidra-bootstrap\
call "%~dp0capabilities\ghidra-bootstrap\Bootstrap-Ghidra.cmd" %*
exit /b %ERRORLEVEL%
