@echo off
setlocal EnableExtensions DisableDelayedExpansion
cd /d "%~dp0ReSkate Studio"
if not exist "ReSkate Studio.exe" (
    echo ReSkate Studio executable missing in this Forge folder.
    pause
    exit /b 1
)
start "ReSkate Studio" "ReSkate Studio.exe"
