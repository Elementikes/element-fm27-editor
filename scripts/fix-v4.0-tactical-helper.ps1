$ErrorActionPreference = 'Stop'
$SourceRoot = (Get-Location).Path
$Path = Join-Path $SourceRoot 'src/ui/club_panel.rs'
if (-not (Test-Path -LiteralPath $Path)) { throw "Source file not found: $Path" }
$text = [IO.File]::ReadAllText($Path)

if ($text.Contains('fn element_tactical_pointer_ok(')) {
    Write-Host 'v4.0 compat: tactical pointer guard already present.'
    exit 0
}

$anchor = 'fn show_tactical_understanding('
$at = $text.IndexOf($anchor)
if ($at -lt 0) { throw 'v4.0 compat: Tactical Knowledge function boundary not found' }

$helper = @'
fn element_tactical_pointer_ok(addr: Option<u64>) -> bool {
    addr.is_some_and(crate::player::is_valid_ptr)
}

'@

$text = $text.Substring(0, $at) + $helper + $text.Substring($at)
[IO.File]::WriteAllText($Path, $text, [Text.UTF8Encoding]::new($false))
Write-Host 'v4.0 compat: restored tactical pointer guard removed by Transfer Center replacement.'
