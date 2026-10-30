$ErrorActionPreference = 'Stop'
$path = Join-Path (Get-Location).Path 'src/main.rs'
$text = [IO.File]::ReadAllText($path)
# v0.2 already branded main.rs. v0.9's deterministic transform expects the upstream
# title strings, so normalize only those strings immediately before the v0.9 rebuild.
$text = $text.Replace('Some(b) => format!("Element FM27 Editor [{b}]"),', 'Some(b) => format!("FM Editor [{b}]"),')
$text = $text.Replace('None => "Element FM27 Editor".to_string(),', 'None => "FM Editor".to_string(),')
$text = $text.Replace('        "Element FM27 Editor",', '        "FM Editor",')
[IO.File]::WriteAllText($path, $text, [Text.UTF8Encoding]::new($false))
Write-Host 'v0.9 main.rs compatibility normalization complete.'
