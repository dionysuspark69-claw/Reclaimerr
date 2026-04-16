<#
.SYNOPSIS
    Build the Reclaimerr Windows installer (Reclaimerr-Setup.exe).

.DESCRIPTION
    Runs the full pipeline:
      1. Build the frontend SPA  (npm run build)
      2. Build the desktop bundle (PyInstaller via uv)
      3. Compile the Inno Setup installer (ISCC)

    Requirements
    ------------
    - Node 20+  on PATH
    - Python 3.11+ on PATH  (or uv: https://docs.astral.sh/uv/)
    - Inno Setup 6  installed at the default location

    The finished installer is written to:
      installer-output\Reclaimerr-Setup.exe

.PARAMETER Version
    Version string embedded in the installer (e.g. "1.0.0").
    Defaults to "0.0.0".

.EXAMPLE
    .\scripts\build_installer.ps1
    .\scripts\build_installer.ps1 -Version "1.2.3"
#>

[CmdletBinding()]
param(
    [string] $Version = "0.0.0"
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$RepoRoot  = Split-Path -Parent $ScriptDir
Push-Location $RepoRoot

function Step($msg) { Write-Host "`n==> $msg" -ForegroundColor Cyan }
function Die($msg)  { Write-Host "`nERROR: $msg" -ForegroundColor Red; exit 1 }

# ---------------------------------------------------------------------------
# Step 1 — Frontend
# ---------------------------------------------------------------------------
Step "Building frontend SPA"

# Find node — check PATH first, then common Windows install locations
$nodeCmd = Get-Command node -ErrorAction SilentlyContinue
if (-not $nodeCmd) {
    $candidates = @(
        "C:\Program Files\nodejs\node.exe",
        "C:\Program Files (x86)\nodejs\node.exe",
        "$env:LOCALAPPDATA\Programs\nodejs\node.exe",
        "$env:LOCALAPPDATA\nvm\current\node.exe"
    )
    foreach ($c in $candidates) {
        if (Test-Path $c) {
            $env:PATH = (Split-Path $c) + ";" + $env:PATH
            $nodeCmd = Get-Command node -ErrorAction SilentlyContinue
            break
        }
    }
}

$frontendDist = Join-Path $RepoRoot "frontend\dist"
if (-not $nodeCmd) {
    if (Test-Path $frontendDist) {
        Write-Warning "node not found — skipping frontend build (using existing frontend\dist)."
    } else {
        Die "node not found and frontend\dist does not exist.`nInstall Node 20+ from https://nodejs.org/ then re-run."
    }
} else {
    Push-Location (Join-Path $RepoRoot "frontend")
    npm install
    if ($LASTEXITCODE -ne 0) { Die "npm install failed" }
    npm run build
    if ($LASTEXITCODE -ne 0) { Die "npm run build failed" }
    Pop-Location
}

# ---------------------------------------------------------------------------
# Step 2 — PyInstaller desktop bundle
# ---------------------------------------------------------------------------
Step "Building desktop bundle (PyInstaller)"
$uvCmd = Get-Command uv -ErrorAction SilentlyContinue
if ($uvCmd) {
    uv sync --extra desktop
    if ($LASTEXITCODE -ne 0) { Die "uv sync failed" }
    uv run python scripts/build_desktop.py
    if ($LASTEXITCODE -ne 0) { Die "PyInstaller build failed" }
} else {
    $pyCmd = if (Get-Command py -ErrorAction SilentlyContinue) { "py" } else { "python" }
    & $pyCmd -m pip install pyinstaller --quiet
    & $pyCmd scripts/build_desktop.py
    if ($LASTEXITCODE -ne 0) { Die "PyInstaller build failed" }
}

# Verify the bundle exists
$bundle = Join-Path $RepoRoot "dist\reclaimerr"
if (-not (Test-Path $bundle)) { Die "Expected bundle not found at: $bundle" }

# ---------------------------------------------------------------------------
# Step 3 — Inno Setup
# ---------------------------------------------------------------------------
Step "Compiling installer (Inno Setup)"
$iscc = "C:\Program Files (x86)\Inno Setup 6\ISCC.exe"
if (-not (Test-Path $iscc)) {
    Die "Inno Setup 6 not found at '$iscc'.`nDownload from https://jrsoftware.org/isinfo.php"
}

& $iscc /DMyAppVersion="$Version" reclaimerr.iss
if ($LASTEXITCODE -ne 0) { Die "ISCC failed" }

# ---------------------------------------------------------------------------
# Done
# ---------------------------------------------------------------------------
$output = Join-Path $RepoRoot "installer-output\Reclaimerr-Setup.exe"
Write-Host ""
Write-Host "============================================================" -ForegroundColor Green
Write-Host "  Installer ready:" -ForegroundColor Green
Write-Host "  $output" -ForegroundColor Green
Write-Host "============================================================" -ForegroundColor Green
