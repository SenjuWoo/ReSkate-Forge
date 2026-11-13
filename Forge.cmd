@echo off
setlocal EnableExtensions DisableDelayedExpansion
cd /d "%~dp0"
if "%~1"=="" (
    call "%~dp0Forge.cmd" doctor
    echo.
    echo ReSkateForge is available. Run Forge.cmd --help for all commands.
    pause
    exit /b 0
)
where py >nul 2>nul
if %ERRORLEVEL% EQU 0 (
    py -3 -m reskateforge %*
) else (
    python -m reskateforge %*
)
exit /b %ERRORLEVEL%
