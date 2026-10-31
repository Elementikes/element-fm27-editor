$ErrorActionPreference = 'Stop'

function Invoke-Layer([string]$Name) {
    $Path = Join-Path $PSScriptRoot $Name
    if (-not (Test-Path -LiteralPath $Path)) { throw "Element release layer missing: $Path" }
    Write-Host "==> $Name"
    & $Path
}

# v0.x shell / UI foundation
Invoke-Layer 'apply-v0.3-ui.ps1'
Invoke-Layer 'apply-v0.4-ui.ps1'
Invoke-Layer 'apply-v0.5-ui.ps1'
Invoke-Layer 'apply-v0.6-shell.ps1'
Invoke-Layer 'apply-v0.7-element-ui.ps1'
Invoke-Layer 'apply-v0.8-element-shell.ps1'
Invoke-Layer 'prepare-v0.9-main.ps1'
Invoke-Layer 'apply-v0.9-rebuild.ps1'

# v1.x editor workspaces
Invoke-Layer 'prepare-v1.5-compat.ps1'
Invoke-Layer 'apply-v1.0-ui-transfer.ps1'
Invoke-Layer 'apply-v1.6-compact-club.ps1'
Invoke-Layer 'apply-v1.7-fmrte-club-tools.ps1'
Invoke-Layer 'apply-v1.8-full-club-editor.ps1'
Invoke-Layer 'apply-v1.9-full-player-live-session.ps1'

# v2.x search, polish, power tools, tactical engine
Invoke-Layer 'apply-v2.0-global-search-compact-player.ps1'
Invoke-Layer 'prepare-v2.1-compat.ps1'
Invoke-Layer 'apply-v2.1-premium-polish.ps1'
Invoke-Layer 'apply-v2.2-zero-scroll-player.ps1'
Invoke-Layer 'apply-v2.3-player-power-tools.ps1'
Invoke-Layer 'apply-v2.4-player-presets.ps1'
Invoke-Layer 'apply-v2.5-staff-club-power-tools.ps1'
Invoke-Layer 'apply-v2.6-transfer-tactical-validation.ps1'
Invoke-Layer 'apply-v2.7-tactical-engine-core.ps1'
Invoke-Layer 'apply-v2.8-tactical-live-inspector.ps1'
Invoke-Layer 'prepare-v2.8-compat.ps1'
Invoke-Layer 'apply-v2.9-tactical-cross-validator.ps1'

# v3.x tactical certification and live club data
Invoke-Layer 'apply-v3.0-tactical-probe-lab.ps1'
Invoke-Layer 'apply-v3.1-tactical-semantic-mapper.ps1'
Invoke-Layer 'apply-v3.2-universal-tactical-resolver.ps1'
Invoke-Layer 'apply-v3.3-universal-descriptor-resolver.ps1'
Invoke-Layer 'apply-v3.4-all-clubs-certification.ps1'
Invoke-Layer 'apply-v3.5-final-semantic-certification.ps1'
Invoke-Layer 'prepare-v3.6-boundary.ps1'
try {
    Invoke-Layer 'apply-v3.6-premium-tactical-viewer.ps1'
} catch {
    if ($_.Exception.Message -notlike '*Tactical Knowledge function boundary not found*') { throw }
    Write-Host 'v3.6 core applied; legacy UI boundary failure handed to robust repair pass.'
}
Invoke-Layer 'apply-v3.6-premium-ui-repair.ps1'
Invoke-Layer 'apply-v3.7-tactical-intelligence.ps1'
Invoke-Layer 'apply-v3.8-live-club-squads.ps1'
Invoke-Layer 'apply-v3.8.1-club-gender-filter.ps1'

# v4.x transfer / contract / recruitment foundation
Invoke-Layer 'apply-v4.0-transfer-center-live.ps1'
Invoke-Layer 'fix-v4.0-tactical-helper.ps1'
Invoke-Layer 'apply-v4.1-contract-intelligence-premium.ps1'
Invoke-Layer 'apply-v4.1.1-market-quick-filters.ps1'
Invoke-Layer 'apply-v4.2a-player-intelligence.ps1'
Invoke-Layer 'apply-v4.2b-squad-bulk-actions.ps1'
Invoke-Layer 'apply-v4.2c-finance-potential.ps1'
Invoke-Layer 'apply-v4.2.1-intelligence-accuracy-hotfix.ps1'
Invoke-Layer 'apply-v4.2.2-morale-ux.ps1'

# v4.2.3 -> v4.7 generated-source release stack.
$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$FinalPatcher = Join-Path $RepoRoot 'layers/apply-v4.7-final.py'
if (-not (Test-Path -LiteralPath $FinalPatcher)) { throw "Element v4.7 patcher missing: $FinalPatcher" }
python $FinalPatcher
if ($LASTEXITCODE -ne 0) { throw 'Element v4.7 generated patch failed.' }

$CompileFix = Join-Path $RepoRoot 'layers/fix-v4.7-compile.py'
if (-not (Test-Path -LiteralPath $CompileFix)) { throw "Element v4.7 compile fix missing: $CompileFix" }
python $CompileFix
if ($LASTEXITCODE -ne 0) { throw 'Element v4.7 compile compatibility pass failed.' }

# v4.8 final-source overlay.
$V48Overlay = Join-Path $RepoRoot 'layers/apply-v4.8-overlay.py'
if (-not (Test-Path -LiteralPath $V48Overlay)) { throw "Element v4.8 overlay applicator missing: $V48Overlay" }
python $V48Overlay
if ($LASTEXITCODE -ne 0) { throw 'Element v4.8 source overlay failed.' }

$V48CompileFix = Join-Path $RepoRoot 'layers/fix-v4.8-compile.py'
if (-not (Test-Path -LiteralPath $V48CompileFix)) { throw "Element v4.8 compile fix missing: $V48CompileFix" }
python $V48CompileFix
if ($LASTEXITCODE -ne 0) { throw 'Element v4.8 compile compatibility pass failed.' }

# v4.8.1 stability: never recursively scan huge graphics packs from egui render.
$V481Stability = Join-Path $RepoRoot 'layers/fix-v4.8.1-stability.py'
if (-not (Test-Path -LiteralPath $V481Stability)) { throw "Element v4.8.1 stability hotfix missing: $V481Stability" }
python $V481Stability
if ($LASTEXITCODE -ne 0) { throw 'Element v4.8.1 stability hotfix failed.' }

# v4.9.x public-source mapping + recruitment consolidation.
$V49 = Join-Path $RepoRoot 'layers/apply-v4.9-consolidation.py'
if (-not (Test-Path -LiteralPath $V49)) { throw "Element v4.9 consolidator missing: $V49" }
python $V49
if ($LASTEXITCODE -ne 0) { throw 'Element v4.9 mapping consolidation failed.' }

# v5.0 boundary normalization + guarded live Force Transfer / Sell Assist / Squads.
$V50Prep = Join-Path $RepoRoot 'layers/prepare-v5.0-boundaries.py'
if (-not (Test-Path -LiteralPath $V50Prep)) { throw "Element v5.0 boundary prep missing: $V50Prep" }
python $V50Prep
if ($LASTEXITCODE -ne 0) { throw 'Element v5.0 boundary prep failed.' }

$V50 = Join-Path $RepoRoot 'layers/apply-v5.0-force-transfer.py'
if (-not (Test-Path -LiteralPath $V50)) { throw "Element v5.0 layer missing: $V50" }
python $V50
if ($LASTEXITCODE -ne 0) { throw 'Element v5.0 Force Transfer layer failed.' }

Write-Host 'Element CURRENT release stack applied through v5.0 successfully.'
