@echo off
setlocal EnableExtensions DisableDelayedExpansion
cd /d "%~dp0"
where py >nul 2>nul
if %ERRORLEVEL% EQU 0 (
    py -3 -m reskateforge mcp
) else (
    python -m reskateforge mcp
)
exit /b %ERRORLEVEL%
