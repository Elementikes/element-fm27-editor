$ErrorActionPreference = 'Stop'
$SourceRoot = (Get-Location).Path
$Path = Join-Path $SourceRoot 'src/ui/club_panel.rs'
if (-not (Test-Path -LiteralPath $Path)) { throw "Source file not found: $Path" }
$text = [IO.File]::ReadAllText($Path)

$oldBadge = 'egui::RichText::new("v4.1 • PREMIUM READ-SIDE")'
if ($text.Contains($oldBadge)) {
    $text = $text.Replace($oldBadge, 'egui::RichText::new("v4.1.1 • PREMIUM READ-SIDE")')
}

$anchor = @'
                ui.ctx().data_mut(|d| d.insert_temp(mode_id, mode));

                ui.separator();
                ui.label(egui::RichText::new("SORT").size(7.5).strong().color(egui::Color32::from_rgb(139, 157, 188)));
'@

$replacement = @'
                ui.ctx().data_mut(|d| d.insert_temp(mode_id, mode));

                // v4.1.1: restore the fast market filters that were visible in
                // v4.0. The contract-horizon dropdown stays, but Transfer / Loan
                // listing status should never be hidden behind a menu.
                ui.separator();
                ui.label(
                    egui::RichText::new("MARKET")
                        .size(7.5)
                        .strong()
                        .color(egui::Color32::from_rgb(139, 157, 188)),
                );
                ui.selectable_value(&mut mode, 1, "TRANSFER LISTED");
                ui.selectable_value(&mut mode, 2, "LOAN LISTED");
                ui.selectable_value(&mut mode, 3, "ANY LISTED");
                ui.ctx().data_mut(|d| d.insert_temp(mode_id, mode));

                ui.separator();
                ui.label(egui::RichText::new("SORT").size(7.5).strong().color(egui::Color32::from_rgb(139, 157, 188)));
'@

if (-not $text.Contains($anchor)) {
    throw 'v4.1.1: premium filter-row boundary not found'
}
$text = $text.Replace($anchor, $replacement)

[IO.File]::WriteAllText($Path, $text, [Text.UTF8Encoding]::new($false))
Write-Host 'Element v4.1.1 market quick filters restored successfully.'
