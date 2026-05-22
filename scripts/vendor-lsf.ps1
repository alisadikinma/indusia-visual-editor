# scripts/vendor-lsf.ps1
#
# Mirror the upstream Label Studio Frontend (LSF) production build into
# web/public/lsf/ so the Vite dev server and the production bundle serve it
# unchanged.
#
# Idempotent — re-running with no upstream changes leaves the tree (and the
# manifest) byte-identical. SHA256 manifest is the drift detector.
#
# Excluded from the mirror:
#   - *.map (source maps — bloat the repo, useless without source tree)
#   - public/files/  (demo audio/video/photos — ~30MB upstream demo content)
#   - public/images/ (demo logos/screenshots)
#   - *.tsbuildinfo / yarn.lock / package.json (upstream build metadata)
#
# Vendoring source is documented in CLAUDE.md §10 + docs/specs/lsf-build.md.

[CmdletBinding()]
param(
    [string]$Source = "D:\Projects\label-studio\web\dist\libs\editor",
    [string]$Destination = (Join-Path (Join-Path $PSScriptRoot "..") "web\public\lsf")
)

$ErrorActionPreference = "Stop"
$Source = (Resolve-Path -LiteralPath $Source).Path
$Destination = [System.IO.Path]::GetFullPath($Destination)

if (-not (Test-Path -LiteralPath $Source)) {
    throw "LSF upstream artifact not found at $Source. Rebuild via 'MODE=standalone yarn nx run editor:build:production' in D:\Projects\label-studio\web first."
}

Write-Output "vendor-lsf: source      = $Source"
Write-Output "vendor-lsf: destination = $Destination"

if (-not (Test-Path -LiteralPath $Destination)) {
    New-Item -ItemType Directory -Path $Destination -Force | Out-Null
}

# Files/dirs we exclude.
$excludedFileExtensions = @(".map", ".tsbuildinfo")
$excludedFileNames = @("yarn.lock", "package.json", "index.html", "3rdpartylicenses.txt")
$excludedSegments = @("public\files", "public\images", "public/files", "public/images")

function Test-Excluded([string]$relativePath, [string]$extension, [string]$name) {
    if ($excludedFileExtensions -contains $extension.ToLowerInvariant()) { return $true }
    if ($excludedFileNames -contains $name) { return $true }
    foreach ($seg in $excludedSegments) {
        if ($relativePath -like "$seg*") { return $true }
    }
    return $false
}

function Get-Sha256([string]$path) {
    return (Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash.ToLowerInvariant()
}

# Walk the source tree, copy with hashes, build manifest.
$manifestFiles = [ordered]@{}
$copied = 0
$skipped = 0

Get-ChildItem -LiteralPath $Source -Recurse -File | ForEach-Object {
    $rel = $_.FullName.Substring($Source.Length).TrimStart('\','/')
    if (Test-Excluded -relativePath $rel -extension $_.Extension -name $_.Name) {
        $skipped++
        return
    }

    $destPath = Join-Path $Destination $rel
    $destDir = Split-Path $destPath -Parent
    if (-not (Test-Path -LiteralPath $destDir)) {
        New-Item -ItemType Directory -Path $destDir -Force | Out-Null
    }

    $srcHash = Get-Sha256 $_.FullName
    $needsCopy = $true
    if (Test-Path -LiteralPath $destPath) {
        $dstHash = Get-Sha256 $destPath
        if ($dstHash -eq $srcHash) { $needsCopy = $false }
    }

    if ($needsCopy) {
        Copy-Item -LiteralPath $_.FullName -Destination $destPath -Force
        $copied++
    }

    $manifestFiles[$rel.Replace('\','/')] = [ordered]@{
        sha256 = $srcHash
        size   = [int64]$_.Length
    }
}

# Prune any files in destination that no longer exist in source (or were excluded).
$keepSet = New-Object System.Collections.Generic.HashSet[string]
foreach ($k in $manifestFiles.Keys) {
    [void]$keepSet.Add((Join-Path $Destination ($k.Replace('/','\'))).ToLowerInvariant())
}

$manifestPath = Join-Path $Destination "manifest.json"
$keepSet.Add($manifestPath.ToLowerInvariant()) | Out-Null

$pruned = 0
Get-ChildItem -LiteralPath $Destination -Recurse -File | ForEach-Object {
    if (-not $keepSet.Contains($_.FullName.ToLowerInvariant())) {
        Remove-Item -LiteralPath $_.FullName -Force
        $pruned++
    }
}

# Remove empty directories left after pruning.
Get-ChildItem -LiteralPath $Destination -Recurse -Directory |
    Sort-Object { $_.FullName.Length } -Descending |
    ForEach-Object {
        if ((Get-ChildItem -LiteralPath $_.FullName -Recurse -Force | Measure-Object).Count -eq 0) {
            try { Remove-Item -LiteralPath $_.FullName -Force } catch {}
        }
    }

# Write manifest (sorted keys for deterministic diff).
$sorted = [ordered]@{}
foreach ($k in ($manifestFiles.Keys | Sort-Object)) { $sorted[$k] = $manifestFiles[$k] }
$manifest = [ordered]@{
    source = $Source.Replace('\','/')
    files  = $sorted
}
$json = $manifest | ConvertTo-Json -Depth 10
# Use UTF8 without BOM (PS 5.1 Out-File -Encoding utf8 emits BOM, which breaks
# json.load on the Python side).
[System.IO.File]::WriteAllText($manifestPath, $json, (New-Object System.Text.UTF8Encoding($false)))

Write-Output "vendor-lsf: $copied copied, $skipped excluded, $pruned pruned"
Write-Output "vendor-lsf: manifest at $manifestPath"
