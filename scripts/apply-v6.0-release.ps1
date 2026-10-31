$ErrorActionPreference = 'Stop'

# Apply the full proven stack through v5.2 first.
& (Join-Path $PSScriptRoot 'apply-v5.2-release.ps1')
if ($LASTEXITCODE -ne 0) { throw 'Element base stack through v5.2 failed.' }

$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$V60 = Join-Path $RepoRoot 'layers/apply-v6.0-fmrte-certification.py'
if (-not (Test-Path -LiteralPath $V60)) { throw "Element v6.0 layer missing: $V60" }
python $V60
if ($LASTEXITCODE -ne 0) { throw 'Element v6.0 FMRTE-informed certification layer failed.' }

Write-Host 'Element release stack applied through v6.0 successfully.'
