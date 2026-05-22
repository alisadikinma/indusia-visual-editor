# Tear down the dev environment. Pass `-Volumes` to also delete the Postgres
# data volume (DESTRUCTIVE — wipes the dev database).
#
# Usage:
#   ./scripts/dev-down.ps1            # stop containers, keep data
#   ./scripts/dev-down.ps1 -Volumes   # stop AND wipe postgres data

[CmdletBinding()]
param(
    [switch]$Volumes
)

$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $repoRoot

$composeArgs = @("-f", "docker-compose.dev.yml", "down")
if ($Volumes) {
    $composeArgs += "-v"
    Write-Host "==> wiping postgres volume" -ForegroundColor Yellow
}

docker compose @composeArgs
Write-Host "==> dev environment stopped" -ForegroundColor Green
