@echo off
chcp 65001 >nul
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0run_codex_spot_discovery.ps1" %*
exit /b %ERRORLEVEL%
