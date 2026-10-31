$ErrorActionPreference = 'Stop'

# Apply the full proven stack through v5.1 first.
& (Join-Path $PSScriptRoot 'apply-element-current.ps1')
if ($LASTEXITCODE -ne 0) { throw 'Element base stack through v5.1 failed.' }

$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$V52 = Join-Path $RepoRoot 'layers/apply-v5.2-transfer-power.py'
if (-not (Test-Path -LiteralPath $V52)) { throw "Element v5.2 layer missing: $V52" }
python $V52
if ($LASTEXITCODE -ne 0) { throw 'Element v5.2 Transfer Power layer failed.' }

Write-Host 'Element release stack applied through v5.2 successfully.'
