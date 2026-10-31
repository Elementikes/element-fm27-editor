$ErrorActionPreference = 'Stop'

# Apply the full proven stack through v5.2 first.
& (Join-Path $PSScriptRoot 'apply-v5.2-release.ps1')
if ($LASTEXITCODE -ne 0) { throw 'Element base stack through v5.2 failed.' }

$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path

$V60Offline = Join-Path $RepoRoot 'layers/apply-v6.0-offline-foundation.py'
if (-not (Test-Path -LiteralPath $V60Offline)) { throw "Element v6.0 offline foundation missing: $V60Offline" }
python $V60Offline
if ($LASTEXITCODE -ne 0) { throw 'Element v6.0 offline foundation failed.' }

$V60 = Join-Path $RepoRoot 'layers/apply-v6.0-fmrte-certification.py'
if (-not (Test-Path -LiteralPath $V60)) { throw "Element v6.0 certification layer missing: $V60" }
python $V60
if ($LASTEXITCODE -ne 0) { throw 'Element v6.0 FMRTE-informed certification layer failed.' }

$V61 = Join-Path $RepoRoot 'layers/apply-v6.1-player-data-hub.py'
if (-not (Test-Path -LiteralPath $V61)) { throw "Element v6.1 Player Data Hub layer missing: $V61" }
python $V61
if ($LASTEXITCODE -ne 0) { throw 'Element v6.1 Player Data Hub layer failed.' }

Write-Host 'Element release stack applied through v6.1 Player Data Hub successfully.'
