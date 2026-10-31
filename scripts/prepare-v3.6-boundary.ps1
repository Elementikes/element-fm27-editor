$ErrorActionPreference = 'Stop'
$SourceRoot = (Get-Location).Path
$Path = Join-Path $SourceRoot 'src/ui/club_panel.rs'
if (-not (Test-Path -LiteralPath $Path)) { throw "Source file not found: $Path" }
$text = [IO.File]::ReadAllText($Path)

# v3.6 core uses an LF-based regex boundary. Normalize the generated Rust file
# so the premium viewer can replace exactly show_tactical_understanding() and
# stop before the shared club UI helpers inserted by v1.8.
$text = $text.Replace("`r`n", "`n")

$start = $text.IndexOf('fn show_tactical_understanding(ui: &mut egui::Ui, club: &ClubView) {')
if ($start -lt 0) { throw 'v3.6: show_tactical_understanding start not found' }
$helper = $text.IndexOf('fn locked_notice(ui: &mut egui::Ui, text: &str) {', $start)
if ($helper -lt 0) { throw 'v3.6: locked_notice boundary not found after Tactical Knowledge' }

# Ensure the core regex lookahead (?=\n\nfn ) is satisfied immediately before
# locked_notice without moving or deleting any helper/page implementation.
$prefix = $text.Substring(0, $helper).TrimEnd("`n")
$suffix = $text.Substring($helper)
$text = $prefix + "`n`n" + $suffix

# Remove any obsolete sentinel left by earlier v3.6 repair attempts.
$text = $text.Replace('// v3.6 repair sentinel: fn show_stadium(' + "`n", '')

[IO.File]::WriteAllText($Path, $text, [Text.UTF8Encoding]::new($false))
Write-Host 'v3.6 Tactical Knowledge boundary normalized safely before shared club UI helpers.'
