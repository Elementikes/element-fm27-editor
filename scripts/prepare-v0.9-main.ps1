$ErrorActionPreference = 'Stop'
$path = Join-Path (Get-Location).Path 'src/main.rs'
$text = [IO.File]::ReadAllText($path)
# Earlier Element layers already branded main.rs and v0.3 already enlarged the
# viewport to 1440x900. v0.9's deterministic transform expects the pinned
# upstream strings, so normalize those exact values immediately before v0.9.
$text = $text.Replace('Some(b) => format!("Element FM27 Editor [{b}]"),', 'Some(b) => format!("FM Editor [{b}]"),')
$text = $text.Replace('None => "Element FM27 Editor".to_string(),', 'None => "FM Editor".to_string(),')
$text = $text.Replace('        "Element FM27 Editor",', '        "FM Editor",')
$text = $text.Replace('.with_inner_size([1440.0 * f, 900.0 * f])', '.with_inner_size([1280.0 * f, 800.0 * f])')
[IO.File]::WriteAllText($path, $text, [Text.UTF8Encoding]::new($false))
Write-Host 'v0.9 main.rs compatibility normalization complete (branding + viewport).'
