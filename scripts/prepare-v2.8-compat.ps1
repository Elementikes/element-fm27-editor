$ErrorActionPreference = 'Stop'
$SourceRoot = (Get-Location).Path

function Read-Text([string]$RelativePath) {
    $Path = Join-Path $SourceRoot $RelativePath
    if (-not (Test-Path -LiteralPath $Path)) { throw "v2.8 compat: source file not found: $Path" }
    return [IO.File]::ReadAllText($Path)
}

function Write-Text([string]$RelativePath, [string]$Text) {
    $Path = Join-Path $SourceRoot $RelativePath
    [IO.File]::WriteAllText($Path, $Text, [Text.UTF8Encoding]::new($false))
}

# -----------------------------------------------------------------------------
# v2.8 compatibility repair
# The original v2.8 transform used LF-specific exact strings for two insertions.
# GitHub Actions generated source can contain CRLF, so normalize these boundaries
# robustly and fail fast if the expected source shape is not present.
# -----------------------------------------------------------------------------

# 1) Declare the read-only tactical inspector module and expose its report type.
$modPath = 'src/bridge/mod.rs'
$modText = Read-Text $modPath

if (-not $modText.Contains('mod tactical_inspector;')) {
    $marker = 'mod entity_load;'
    $at = $modText.IndexOf($marker)
    if ($at -lt 0) { throw 'v2.8 compat: mod entity_load marker not found' }
    $insertAt = $at + $marker.Length
    $newline = if ($modText.Contains("`r`n")) { "`r`n" } else { "`n" }
    $modText = $modText.Substring(0, $insertAt) + $newline + 'mod tactical_inspector;' + $modText.Substring($insertAt)
}

if (-not $modText.Contains('TacticalInspectorReport')) {
    $marker = 'ProcessBridge, StaffView'
    $at = $modText.IndexOf($marker)
    if ($at -lt 0) { throw 'v2.8 compat: bridge public re-export marker not found' }
    $replacement = 'ProcessBridge, StaffView, TacticalInspectorReport'
    $modText = $modText.Substring(0, $at) + $replacement + $modText.Substring($at + $marker.Length)
}

if (-not $modText.Contains('mod tactical_inspector;')) { throw 'v2.8 compat: tactical_inspector module declaration still missing' }
if (-not $modText.Contains('TacticalInspectorReport')) { throw 'v2.8 compat: TacticalInspectorReport re-export still missing' }
Write-Text $modPath $modText
Write-Host 'v2.8 compat: bridge module declaration/re-export repaired'

# 2) Initialize the new report field in the single production ClubView initializer.
$loadPath = 'src/bridge/entity_load.rs'
$loadText = Read-Text $loadPath
if (-not $loadText.Contains('tactical_report: None')) {
    $marker = '        senior_team_addr,'
    $at = $loadText.IndexOf($marker)
    if ($at -lt 0) { throw 'v2.8 compat: senior_team_addr initializer marker not found' }
    $insertAt = $at + $marker.Length
    $newline = if ($loadText.Contains("`r`n")) { "`r`n" } else { "`n" }
    $loadText = $loadText.Substring(0, $insertAt) + $newline + '        tactical_report: None,' + $loadText.Substring($insertAt)
}
if (-not $loadText.Contains('tactical_report: None')) { throw 'v2.8 compat: ClubView tactical_report initializer still missing' }
Write-Text $loadPath $loadText
Write-Host 'v2.8 compat: ClubView tactical_report initializer repaired'

Write-Host 'v2.8 compatibility repair completed.'
