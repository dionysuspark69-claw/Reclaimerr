@echo off
::
:: Reclaimerr - Build Windows Installer
:: -------------------------------------
:: Runs the full pipeline:
::   1. Build frontend SPA  (npm run build)
::   2. Build desktop bundle (PyInstaller)
::   3. Compile installer   (Inno Setup -> installer-output\Reclaimerr-Setup.exe)
::
:: Usage:
::   build_installer.bat              (version defaults to 0.0.0)
::   build_installer.bat 1.2.3        (embeds version in installer)
::
:: Requirements:
::   - Node 20+      on PATH
::   - Python 3.11+  on PATH  (or uv: https://docs.astral.sh/uv/)
::   - Inno Setup 6  at default install location
::

setlocal EnableExtensions EnableDelayedExpansion

set "VERSION=%~1"
if "!VERSION!"=="" set "VERSION=0.0.0"

set "SCRIPT_DIR=%~dp0"
if "%SCRIPT_DIR:~-1%"=="\" set "SCRIPT_DIR=%SCRIPT_DIR:~0,-1%"

where /q pwsh 2>nul
if %ERRORLEVEL% equ 0 (
    set "PS_EXE=pwsh"
) else (
    set "PS_EXE=powershell"
)

echo [INFO] Building Reclaimerr installer v%VERSION% ...
echo.

%PS_EXE% -NoLogo -ExecutionPolicy Bypass -File "%SCRIPT_DIR%\build_installer.ps1" -Version "%VERSION%"

set EXIT_CODE=%ERRORLEVEL%
if %EXIT_CODE% neq 0 (
    echo.
    echo [ERROR] Build failed with code %EXIT_CODE%.
    pause
)

endlocal
exit /b %EXIT_CODE%
