# Bring up the dev Postgres in the background and wait for the healthcheck
# to pass. The api + web services are NOT started by default — run them
# locally (`poetry run uvicorn ...` + `pnpm dev`) for the best DX.
#
# Pass `-Full` to also start the dockerized api + web profile.
#
# Usage:
#   ./scripts/dev-up.ps1          # postgres only
#   ./scripts/dev-up.ps1 -Full    # postgres + api + web

[CmdletBinding()]
param(
    [switch]$Full
)

# Docker writes progress to stderr by design; treat it as informational.
$ErrorActionPreference = "Continue"

$repoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $repoRoot

$composeArgs = @("-f", "docker-compose.dev.yml")
if ($Full) {
    $composeArgs += @("--profile", "full")
}
$composeArgs += @("up", "-d", "postgres")
if ($Full) {
    $composeArgs += @("api", "web")
}

Write-Host "==> docker compose $($composeArgs -join ' ')" -ForegroundColor Cyan
docker compose @composeArgs 2>&1 | ForEach-Object { Write-Host $_ }
if ($LASTEXITCODE -ne 0) {
    Write-Error "docker compose up failed with exit $LASTEXITCODE"
    exit $LASTEXITCODE
}

Write-Host "==> waiting for postgres healthcheck..." -ForegroundColor Cyan
$deadline = (Get-Date).AddSeconds(60)
while ((Get-Date) -lt $deadline) {
    $status = (docker inspect ive-postgres-dev --format '{{.State.Health.Status}}' 2>$null)
    if ($status -eq "healthy") {
        Write-Host "==> postgres healthy" -ForegroundColor Green
        exit 0
    }
    Start-Sleep -Seconds 2
}
Write-Error "postgres did not become healthy within 60s"
exit 1
