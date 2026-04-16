@echo off
::
:: Reclaimerr Web Server - Windows Batch Launcher
:: ------------------------------------------------
:: Double-click this file or run it from a Command Prompt / Terminal to start
:: the Reclaimerr web server on Windows.
::
:: All configuration is read from a .env file in the repository root.
:: See scripts\start_web.ps1 for the full list of supported environment variables.
::
:: Requirements
::   - Python 3.11+  on PATH   (or install uv: https://docs.astral.sh/uv/)
::   - Node 20+      on PATH   (needed only for the first-time frontend build)
::
:: First-time setup (run once from the repo root):
::   cd frontend
::   npm install
::   npm run build
::   cd ..
::

setlocal EnableExtensions EnableDelayedExpansion

:: Determine the directory that contains this batch file, then the repo root.
set "SCRIPT_DIR=%~dp0"
:: Remove trailing backslash from SCRIPT_DIR
if "%SCRIPT_DIR:~-1%"=="\" set "SCRIPT_DIR=%SCRIPT_DIR:~0,-1%"
set "REPO_ROOT=%SCRIPT_DIR%\.."

:: Resolve PowerShell executable.
:: Prefer pwsh (PowerShell 7+) for better compatibility; fall back to the
:: Windows-built-in powershell.exe (PowerShell 5.1).
where /q pwsh 2>nul
if %ERRORLEVEL% equ 0 (
    set "PS_EXE=pwsh"
) else (
    set "PS_EXE=powershell"
)

echo [INFO] Starting Reclaimerr via %PS_EXE% ...
echo [INFO] Repo root: %REPO_ROOT%
echo.

%PS_EXE% -NoLogo -ExecutionPolicy Bypass -File "%SCRIPT_DIR%\start_web.ps1" %*

set EXIT_CODE=%ERRORLEVEL%
if %EXIT_CODE% neq 0 (
    echo.
    echo [ERROR] Reclaimerr exited with code %EXIT_CODE%.
    pause
)

endlocal
exit /b %EXIT_CODE%
