# Snapshot dev state for Macbook sync.
# - Pushes any unpushed commits to origin/main
# - Dumps the dev Postgres (ive-postgres-dev) to .sync/ive-db.sql.gz
# - Copies storage/ uploads to .sync/storage.tar.gz (golden samples, BOM xlsx)
#
# Transfer .sync/ ke Macbook (AirDrop / scp / iCloud) lalu jalankan
# ./scripts/sync-from-pc.sh di Mac.
#
# Usage:
#   ./scripts/sync-to-macbook.ps1
#   ./scripts/sync-to-macbook.ps1 -SkipPush   # local-only snapshot

[CmdletBinding()]
param(
    [switch]$SkipPush,
    [switch]$SkipStorage
)

$ErrorActionPreference = "Stop"
$repoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $repoRoot

$syncDir = Join-Path $repoRoot ".sync"
New-Item -ItemType Directory -Force -Path $syncDir | Out-Null

if (-not $SkipPush) {
    Write-Host "==> git push origin main" -ForegroundColor Cyan
    git push origin main
    if ($LASTEXITCODE -ne 0) { throw "git push failed" }
}

Write-Host "==> dumping ive-postgres-dev → .sync/ive-db.dump" -ForegroundColor Cyan
$container = "ive-postgres-dev"
$running = docker ps --filter "name=$container" --format "{{.Names}}"
if (-not $running) { throw "container $container not running — start with ./scripts/dev-up.ps1" }

# pg_dump custom format: built-in compression, parallel restore-able, byte-identical
# round-trip via pg_restore. Matches infra/scripts/pg_backup.sh prod pattern.
$dumpPath = Join-Path $syncDir "ive-db.dump"
docker exec $container pg_dump -U ive -d ive `
    --format=custom --compress=9 --no-owner --no-privileges `
    --file=/tmp/ive-db.dump
if ($LASTEXITCODE -ne 0) { throw "pg_dump failed" }
docker cp "${container}:/tmp/ive-db.dump" $dumpPath
if ($LASTEXITCODE -ne 0) { throw "docker cp failed" }
docker exec $container rm -f /tmp/ive-db.dump | Out-Null

# Capture row counts from source so Mac side can verify
Write-Host "==> capturing row-count fingerprint" -ForegroundColor Cyan
$fingerprintPath = Join-Path $syncDir "row-counts.txt"
$tables = @("projects","assets","bom_items","labels","train_runs","deployments","edges","chat_sessions","organizations","users","adapt_runs","pre_labels","proposed_pipelines")
$lines = foreach ($t in $tables) {
    $count = (docker exec $container psql -U ive -d ive -tAc "SELECT COUNT(*) FROM $t" 2>$null).Trim()
    if ($LASTEXITCODE -eq 0 -and $count -match '^\d+$') {
        "$t`t$count"
    }
}
$lines | Out-File -Encoding utf8 -FilePath $fingerprintPath
Write-Host ($lines -join "`n")

$dumpSize = "{0:N1} MB" -f ((Get-Item $dumpPath).Length / 1MB)
Write-Host "==> dump size: $dumpSize" -ForegroundColor Cyan

if (-not $SkipStorage -and (Test-Path "$repoRoot\storage")) {
    Write-Host "==> archiving storage/ → .sync/storage.tar.gz" -ForegroundColor Cyan
    tar -czf "$syncDir\storage.tar.gz" -C $repoRoot storage
    if ($LASTEXITCODE -ne 0) { throw "tar failed" }
}

$gitSha = (git rev-parse HEAD).Trim()
@"
git_sha:      $gitSha
created:      $(Get-Date -Format o)
db_dump:      ive-db.dump (pg_dump --format=custom, $dumpSize)
row_counts:   row-counts.txt
storage:      $(if (Test-Path "$syncDir\storage.tar.gz") { "storage.tar.gz" } else { "(skipped)" })
"@ | Out-File -Encoding utf8 (Join-Path $syncDir "MANIFEST.txt")

Write-Host ""
Write-Host "Done. Transfer .sync/ ke Macbook:" -ForegroundColor Green
Write-Host "  - .sync/ive-db.dump"
Write-Host "  - .sync/row-counts.txt"
Write-Host "  - .sync/storage.tar.gz"
Write-Host "  - .sync/MANIFEST.txt"
Write-Host ""
Write-Host "Di Mac: clone repo + drop .sync/ di root + ./scripts/sync-from-pc.sh" -ForegroundColor Yellow
