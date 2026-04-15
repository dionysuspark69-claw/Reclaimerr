<#
.SYNOPSIS
    Start the Reclaimerr web server on Windows.

.DESCRIPTION
    Sets up the environment and launches the Reclaimerr FastAPI backend,
    which also serves the built frontend SPA when FRONTEND_DIST is set.

    Prerequisites
    -------------
    - Python 3.11+ on PATH  (or use 'uv' for dependency management)
    - Node 20+ on PATH      (needed only if you want to build the frontend)
    - Run once before starting: cd frontend && npm install && npm run build

    Environment variables (optional — all have defaults; set them in .env)
    -----------------------------------------------------------------------
    DATA_DIR        Application data directory (database, logs, avatars).
                    Default: .\data  (relative to repo root)
    API_HOST        Bind address.  Default: 0.0.0.0
    API_PORT        Port number.   Default: 8000
    CORS_ORIGINS    Comma-separated allowed origins.
                    Default: *  — INSECURE, change this for production!
                    Example: http://localhost:8000,https://reclaimerr.example.com
    LOG_LEVEL       DEBUG | INFO | WARNING | ERROR.  Default: INFO
    TMDB_API_KEY    TMDB read-access token (required for metadata enrichment).

    Parameters
    ----------
    -DataDir    Override DATA_DIR for this run only.
    -Host       Override API_HOST for this run only.
    -Port       Override API_PORT for this run only.
    -LogLevel   Override LOG_LEVEL for this run only.

.EXAMPLE
    # Basic start (reads settings from .env or uses defaults)
    .\scripts\start_web.ps1

.EXAMPLE
    # Custom port and data directory
    .\scripts\start_web.ps1 -Port 9000 -DataDir C:\reclaimerr\data
#>

[CmdletBinding()]
param(
    [string] $DataDir  = "",
    [string] $Host     = "",
    [int]    $Port     = 0,
    [string] $LogLevel = ""
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

# ---------------------------------------------------------------------------
# Resolve the repo root (parent directory of this script)
# ---------------------------------------------------------------------------
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$RepoRoot  = Split-Path -Parent $ScriptDir
Push-Location $RepoRoot

# ---------------------------------------------------------------------------
# Load .env file (if present) so users can configure via a single file.
# Lines starting with # are comments; KEY=VALUE pairs set env vars.
# ---------------------------------------------------------------------------
$EnvFile = Join-Path $RepoRoot ".env"
if (Test-Path $EnvFile) {
    Get-Content $EnvFile | ForEach-Object {
        $line = $_.Trim()
        if ($line -and -not $line.StartsWith("#") -and $line -match "^([^=]+)=(.*)$") {
            $key   = $Matches[1].Trim()
            $value = $Matches[2].Trim().Trim('"').Trim("'")
            if (-not [System.Environment]::GetEnvironmentVariable($key)) {
                [System.Environment]::SetEnvironmentVariable($key, $value, "Process")
            }
        }
    }
    Write-Host "[INFO] Loaded settings from: $EnvFile"
}

# ---------------------------------------------------------------------------
# Apply parameter overrides (command-line wins over .env / environment)
# ---------------------------------------------------------------------------
if ($DataDir)    { $env:DATA_DIR  = $DataDir }
if ($Host)       { $env:API_HOST  = $Host }
if ($Port -gt 0) { $env:API_PORT  = $Port.ToString() }
if ($LogLevel)   { $env:LOG_LEVEL = $LogLevel }

# ---------------------------------------------------------------------------
# Set FRONTEND_DIST to the built SPA if the dist folder exists
# ---------------------------------------------------------------------------
if (-not $env:FRONTEND_DIST) {
    $FrontendDist = Join-Path $RepoRoot "frontend\dist"
    if (Test-Path $FrontendDist) {
        $env:FRONTEND_DIST = $FrontendDist
        Write-Host "[INFO] Serving frontend SPA from: $FrontendDist"
    } else {
        Write-Warning ("frontend\dist not found. " +
            "Run 'cd frontend && npm install && npm run build' to build the SPA. " +
            "The API will still start, but the web UI will not be served.")
    }
}

# ---------------------------------------------------------------------------
# Security reminder about CORS
# ---------------------------------------------------------------------------
$corsOrigins = $env:CORS_ORIGINS
if (-not $corsOrigins -or $corsOrigins -eq "*") {
    Write-Warning ("CORS_ORIGINS is not set or is '*' (allow all origins). " +
        "Set CORS_ORIGINS in your .env file to restrict access in production. " +
        "Example: CORS_ORIGINS=http://localhost:8000")
}

# ---------------------------------------------------------------------------
# Print startup summary
# ---------------------------------------------------------------------------
Write-Host ""
Write-Host "============================================================"
Write-Host "  Reclaimerr - Web Server"
Write-Host "============================================================"
Write-Host "  Repo root  : $RepoRoot"
Write-Host "  DATA_DIR   : $($env:DATA_DIR  ?? '.\data (default)')"
Write-Host "  API_HOST   : $($env:API_HOST  ?? '0.0.0.0 (default)')"
Write-Host "  API_PORT   : $($env:API_PORT  ?? '8000 (default)')"
Write-Host "  LOG_LEVEL  : $($env:LOG_LEVEL ?? 'INFO (default)')"
Write-Host "============================================================"
Write-Host ""

# ---------------------------------------------------------------------------
# Resolve host / port for the granian command line
# ---------------------------------------------------------------------------
$bindHost = if ($env:API_HOST) { $env:API_HOST } else { "0.0.0.0" }
$bindPort = if ($env:API_PORT) { $env:API_PORT } else { "8000" }

# ---------------------------------------------------------------------------
# Launch with 'uv run' (preferred) or fall back to granian / uvicorn directly
# ---------------------------------------------------------------------------
$uvCmd = Get-Command uv -ErrorAction SilentlyContinue

if ($uvCmd) {
    Write-Host "[INFO] Launching with: uv run granian"
    uv run granian --interface asgi --host $bindHost --port $bindPort backend.api.main:app
} else {
    # Try granian first (production server used by Docker), then uvicorn (dev)
    $granianCmd  = Get-Command granian  -ErrorAction SilentlyContinue
    $uvicornCmd  = Get-Command uvicorn  -ErrorAction SilentlyContinue

    if ($granianCmd) {
        Write-Host "[INFO] Launching with: granian"
        granian --interface asgi --host $bindHost --port $bindPort backend.api.main:app
    } elseif ($uvicornCmd) {
        Write-Host "[INFO] Launching with: uvicorn (development mode)"
        uvicorn backend.api.main:app --host $bindHost --port $bindPort
    } else {
        # Last resort: python -m uvicorn
        $pyCmd = if (Get-Command py -ErrorAction SilentlyContinue) { "py" } else { "python" }
        Write-Host "[INFO] Launching with: $pyCmd -m uvicorn (development mode)"
        & $pyCmd -m uvicorn backend.api.main:app --host $bindHost --port $bindPort
    }
}
