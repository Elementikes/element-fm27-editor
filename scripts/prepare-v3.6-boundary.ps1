$ErrorActionPreference = 'Stop'
$SourceRoot = (Get-Location).Path
$Path = Join-Path $SourceRoot 'src/ui/club_panel.rs'
if (-not (Test-Path -LiteralPath $Path)) { throw "Source file not found: $Path" }
$text = [IO.File]::ReadAllText($Path)

if ($text.Contains("}`r`n`r`nfn show_stadium(")) {
    Write-Host 'v3.6 boundary already normalized.'
    exit 0
}
if ($text.Contains("}`n`nfn show_stadium(")) {
    Write-Host 'v3.6 boundary already normalized.'
    exit 0
}

if ($text.Contains("}`r`nfn show_stadium(")) {
    $text = $text.Replace("}`r`nfn show_stadium(", "}`r`n`r`nfn show_stadium(")
} elseif ($text.Contains("}`nfn show_stadium(")) {
    $text = $text.Replace("}`nfn show_stadium(", "}`n`nfn show_stadium(")
} else {
    throw 'v3.6: show_tactical_understanding/show_stadium boundary not found'
}

[IO.File]::WriteAllText($Path, $text, [Text.UTF8Encoding]::new($false))
Write-Host 'v3.6 Tactical Knowledge function boundary normalized.'
