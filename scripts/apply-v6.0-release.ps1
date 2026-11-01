$ErrorActionPreference = 'Stop'

# Apply the full proven stack through v5.2 first.
& (Join-Path $PSScriptRoot 'apply-v5.2-release.ps1')
if ($LASTEXITCODE -ne 0) { throw 'Element base stack through v5.2 failed.' }

$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path

$layers = @(
  @('v6.0 offline foundation','apply-v6.0-offline-foundation.py'),
  @('v6.0 FMRTE-informed certification','apply-v6.0-fmrte-certification.py'),
  @('v6.1 Player Data Hub core','apply-v6.1-player-data-hub-core.py'),
  @('v6.1 Player Data Hub navigation','apply-v6.1-player-data-hub-nav.py'),
  @('v6.1.1 offer delta certifier','apply-v6.1.1-offer-delta-certifier.py'),
  @('v6.2 semantic lab','apply-v6.2-semantic-lab.py'),
  @('v6.2.1 FMRTE27 surface','apply-v6.2.1-fmrte27-surface.py'),
  @('v6.2.2 club tactical understanding','apply-v6.2.2-club-tactical-understanding.py'),
  @('v6.2.3 player full surface','apply-v6.2.3-player-full-surface.py'),
  @('v6.2.4 tactical max workflow','apply-v6.2.4-tactical-ui.py'),
  @('v6.2.5 club tactical certifier UI','apply-v6.2.5-club-tactical-certifier-ui.py'),
  @('v6.2.6 selected-club tactical MAX','apply-v6.2.6-selected-club-tactical-max.py'),
  @('v6.2.6.1 tactical MAX compile hotfix','apply-v6.2.6.1-tactical-max-compile-hotfix.py'),
  @('v6.2.6.2 tactical MAX diagnostics','apply-v6.2.6.2-tactical-max-diagnostics.py'),
  @('v6.2.7 tactical missing-fields probe','apply-v6.2.7-tactical-missing-fields-probe.py'),
  @('v6.2.8 tactical smart probe','apply-v6.2.8-tactical-smart-probe.py'),
  @('v6.2.9 match exposure / shape probe','apply-v6.2.9-match-exposure-shape-probe.py'),
  @('v6.3.0 tactical candidate matrix','apply-v6.3.0-tactical-candidate-matrix.py'),
  @('v6.4.0 FMRTE reference integration','apply-v6.4.0-fmrte-reference-integration.py'),
  @('v6.4.1 tactical FMRTE UI cleanup','apply-v6.4.1-tactical-fmrte-ui-cleanup.py'),
  @('v6.4.2 FMRTE tactical chain hardening','apply-v6.4.2-in-possession-chain-hardening.py'),
  @('v6.4.3 FMRTE team cohesion mapper','apply-v6.4.3-team-cohesion-mapper.py'),
  @('v6.5.0 functional core stabilization','apply-v6.5.0-functional-core.py'),
  @('v6.5.1 Squads render hotfix','apply-v6.5.1-squads-render-hotfix.py'),
  @('v6.6.0 IL2CPP-assisted Team Cohesion differential certifier','apply-v6.6.0-il2cpp-differential-certifier.py'),
  @('v6.6.1 IL2CPP certifier compile hotfix','apply-v6.6.1-il2cpp-certifier-compile-hotfix.py')
)

foreach ($layer in $layers) {
  $label = $layer[0]
  $path = Join-Path $RepoRoot ('layers/' + $layer[1])
  if (-not (Test-Path -LiteralPath $path)) { throw "Element $label layer missing: $path" }
  python $path
  if ($LASTEXITCODE -ne 0) { throw "Element $label layer failed." }
}

Write-Host 'Element release stack applied through v6.6.1 IL2CPP Action Certifier successfully.'
