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

$V61Core = Join-Path $RepoRoot 'layers/apply-v6.1-player-data-hub-core.py'
if (-not (Test-Path -LiteralPath $V61Core)) { throw "Element v6.1 Player Data Hub core missing: $V61Core" }
python $V61Core
if ($LASTEXITCODE -ne 0) { throw 'Element v6.1 Player Data Hub core failed.' }

$V61Nav = Join-Path $RepoRoot 'layers/apply-v6.1-player-data-hub-nav.py'
if (-not (Test-Path -LiteralPath $V61Nav)) { throw "Element v6.1 Player Data Hub navigation missing: $V61Nav" }
python $V61Nav
if ($LASTEXITCODE -ne 0) { throw 'Element v6.1 Player Data Hub navigation failed.' }

$V611 = Join-Path $RepoRoot 'layers/apply-v6.1.1-offer-delta-certifier.py'
if (-not (Test-Path -LiteralPath $V611)) { throw "Element v6.1.1 offer delta certifier missing: $V611" }
python $V611
if ($LASTEXITCODE -ne 0) { throw 'Element v6.1.1 offer delta certifier failed.' }

$V62 = Join-Path $RepoRoot 'layers/apply-v6.2-semantic-lab.py'
if (-not (Test-Path -LiteralPath $V62)) { throw "Element v6.2 semantic lab missing: $V62" }
python $V62
if ($LASTEXITCODE -ne 0) { throw 'Element v6.2 semantic lab failed.' }

$V621 = Join-Path $RepoRoot 'layers/apply-v6.2.1-fmrte27-surface.py'
if (-not (Test-Path -LiteralPath $V621)) { throw "Element v6.2.1 FMRTE27 surface layer missing: $V621" }
python $V621
if ($LASTEXITCODE -ne 0) { throw 'Element v6.2.1 FMRTE27 surface layer failed.' }

$V622 = Join-Path $RepoRoot 'layers/apply-v6.2.2-club-tactical-understanding.py'
if (-not (Test-Path -LiteralPath $V622)) { throw "Element v6.2.2 club tactical understanding layer missing: $V622" }
python $V622
if ($LASTEXITCODE -ne 0) { throw 'Element v6.2.2 club tactical understanding layer failed.' }

$V623 = Join-Path $RepoRoot 'layers/apply-v6.2.3-player-full-surface.py'
if (-not (Test-Path -LiteralPath $V623)) { throw "Element v6.2.3 player full surface layer missing: $V623" }
python $V623
if ($LASTEXITCODE -ne 0) { throw 'Element v6.2.3 player full surface layer failed.' }

$V624 = Join-Path $RepoRoot 'layers/apply-v6.2.4-tactical-ui.py'
if (-not (Test-Path -LiteralPath $V624)) { throw "Element v6.2.4 tactical max workflow layer missing: $V624" }
python $V624
if ($LASTEXITCODE -ne 0) { throw 'Element v6.2.4 tactical max workflow layer failed.' }

$V625 = Join-Path $RepoRoot 'layers/apply-v6.2.5-club-tactical-certifier-ui.py'
if (-not (Test-Path -LiteralPath $V625)) { throw "Element v6.2.5 club tactical certifier UI layer missing: $V625" }
python $V625
if ($LASTEXITCODE -ne 0) { throw 'Element v6.2.5 club tactical certifier UI layer failed.' }

$V626 = Join-Path $RepoRoot 'layers/apply-v6.2.6-selected-club-tactical-max.py'
if (-not (Test-Path -LiteralPath $V626)) { throw "Element v6.2.6 selected-club tactical MAX layer missing: $V626" }
python $V626
if ($LASTEXITCODE -ne 0) { throw 'Element v6.2.6 selected-club tactical MAX layer failed.' }

$V6261 = Join-Path $RepoRoot 'layers/apply-v6.2.6.1-tactical-max-compile-hotfix.py'
if (-not (Test-Path -LiteralPath $V6261)) { throw "Element v6.2.6.1 tactical MAX compile hotfix missing: $V6261" }
python $V6261
if ($LASTEXITCODE -ne 0) { throw 'Element v6.2.6.1 tactical MAX compile hotfix failed.' }

Write-Host 'Element release stack applied through v6.2.6.1 Tactical MAX compile hotfix successfully.'
