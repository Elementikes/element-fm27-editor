$ErrorActionPreference = 'Stop'
$SourceRoot = (Get-Location).Path
$Path = Join-Path $SourceRoot 'src/ui/club_panel.rs'
if (-not (Test-Path -LiteralPath $Path)) { throw "Source file not found: $Path" }
$text = [IO.File]::ReadAllText($Path)

# Normalize the historical tactical-understanding/stadium boundary when needed.
if ($text.Contains("}`r`nfn show_stadium(")) {
    $text = $text.Replace("}`r`nfn show_stadium(", "}`r`n`r`nfn show_stadium(")
} elseif ($text.Contains("}`nfn show_stadium(")) {
    $text = $text.Replace("}`nfn show_stadium(", "}`n`nfn show_stadium(")
}

# The v3.6 premium repair historically used the next `fn show_stadium(` token as
# its end marker. In the generated club panel, several other Club tab helpers
# (starting with show_squads) live between Tactical Knowledge and the real
# show_stadium function. Insert a harmless comment sentinel immediately before
# show_squads so the repair stops at the correct boundary and preserves every
# following helper.
$sentinel = '// v3.6 repair sentinel: fn show_stadium('
if (-not $text.Contains($sentinel)) {
    $needle = 'fn show_squads('
    $at = $text.IndexOf($needle)
    if ($at -lt 0) { throw 'v3.6: show_squads boundary not found for repair sentinel' }
    $text = $text.Substring(0, $at) + $sentinel + "`n" + $text.Substring($at)
}

[IO.File]::WriteAllText($Path, $text, [Text.UTF8Encoding]::new($false))
Write-Host 'v3.6 Tactical Knowledge boundary + club-function preservation sentinel prepared.'
