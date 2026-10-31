$ErrorActionPreference = 'Stop'
$SourceRoot = (Get-Location).Path
$path = Join-Path $SourceRoot 'src/app.rs'
if (-not (Test-Path -LiteralPath $path)) { throw "Source file not found: $path" }

$text = [IO.File]::ReadAllText($path)

# v1.9 expanded the contextual player navigation and changed the exact nav-helper
# formatting that the v2.1 cosmetic pass originally expected. Normalize only the
# helper signature; no navigation behaviour or memory logic is changed here.
$pattern = 'ui\.add_sized\(\[ui\.available_width\(\),\s*[0-9.]+\],\s*egui::Button::new\(egui::RichText::new\(label\)\.size\([0-9.]+\)'
$replacement = 'ui.add_sized([ui.available_width(), 25.0], egui::Button::new(egui::RichText::new(label).size(11.0)'

if (-not [regex]::IsMatch($text, $pattern)) {
    throw 'v2.1 compatibility: contextual navigation helper signature not found'
}

$text = [regex]::Replace($text, $pattern, $replacement)
[IO.File]::WriteAllText($path, $text, [Text.UTF8Encoding]::new($false))
Write-Host 'v2.1 compatibility: normalized contextual navigation helper for premium polish.'
