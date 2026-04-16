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

if (-not $nodeCmd) {
    Write-Host "[INFO] Node.js not found — attempting automatic install..." -ForegroundColor Yellow

    # Try winget first (available on Windows 10 1709+ / Windows 11)
    $winget = Get-Command winget -ErrorAction SilentlyContinue
    if ($winget) {
        Write-Host "[INFO] Installing Node.js LTS via winget..."
        winget install OpenJS.NodeJS.LTS --silent --accept-package-agreements --accept-source-agreements
        # Refresh PATH from registry so node is visible immediately
        $env:PATH = [System.Environment]::GetEnvironmentVariable("PATH","Machine") + ";" +
                    [System.Environment]::GetEnvironmentVariable("PATH","User")
    } else {
        # Fallback: download the MSI for the latest Node LTS directly
        Write-Host "[INFO] winget not available — downloading Node.js LTS MSI..."
        try {
            $index   = Invoke-RestMethod "https://nodejs.org/dist/index.json"
            $lts     = $index | Where-Object { $_.lts -ne $false } | Select-Object -First 1
            $ver     = $lts.version          # e.g. "v22.13.1"
            $msiUrl  = "https://nodejs.org/dist/$ver/node-$ver-x64.msi"
            $msiPath = "$env:TEMP\node-lts-installer.msi"
            Write-Host "[INFO] Downloading $msiUrl ..."
            Invoke-WebRequest -Uri $msiUrl -OutFile $msiPath -UseBasicParsing
            Write-Host "[INFO] Running installer (this may take a minute)..."
            Start-Process msiexec.exe -ArgumentList "/i `"$msiPath`" /quiet /norestart ADDLOCAL=ALL" -Wait
            Remove-Item $msiPath -Force -ErrorAction SilentlyContinue
            $env:PATH = [System.Environment]::GetEnvironmentVariable("PATH","Machine") + ";" +
                        [System.Environment]::GetEnvironmentVariable("PATH","User")
        } catch {
            Die "Automatic Node.js install failed: $_`nInstall Node 20+ manually from https://nodejs.org/ then re-run."
        }
    }

    $nodeCmd = Get-Command node -ErrorAction SilentlyContinue
    if (-not $nodeCmd) {
        Die "Node.js was installed but 'node' is still not on PATH.`nOpen a new terminal and re-run this script."
    }
    Write-Host "[INFO] Node.js $(node --version) ready." -ForegroundColor Green
}

if ($nodeCmd) {
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
