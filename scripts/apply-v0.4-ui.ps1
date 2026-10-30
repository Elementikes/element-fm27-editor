$ErrorActionPreference = 'Stop'
$SourceRoot = (Get-Location).Path

function Replace-Required {
    param([string]$RelativePath, [string]$Old, [string]$New)
    $Path = Join-Path $SourceRoot $RelativePath
    if (-not (Test-Path -LiteralPath $Path)) { throw "Source file not found: $Path" }
    $text = [IO.File]::ReadAllText($Path)
    if (-not $text.Contains($Old)) { throw "Expected text not found in $RelativePath`n--- expected ---`n$Old" }
    $text = $text.Replace($Old, $New)
    [IO.File]::WriteAllText($Path, $text, [Text.UTF8Encoding]::new($false))
}

# Modernize the Transfer Lab into a clear dashboard/card layout while preserving
# all proven v0.2 write paths. Force Transfer stays visibly experimental/locked
# until the linked FM27 membership records are mapped and validated.
$p = 'src/ui/player_panel.rs'

Replace-Required $p @'
    ui.horizontal(|ui| {
        ui.heading("Transfer Lab");
        ui.label(egui::RichText::new("ELEMENT").strong().color(egui::Color32::from_rgb(116, 145, 255)));
    });
    ui.label(egui::RichText::new("Market status, asking price and contract controls. Advanced transfer writes remain locked until FM27 linked records are verified.").weak());
    ui.add_space(8.0);
'@ @'
    ui.horizontal(|ui| {
        ui.heading(egui::RichText::new("Transfer Lab").size(24.0).strong());
        ui.label(egui::RichText::new("ELEMENT").strong().color(egui::Color32::from_rgb(116, 145, 255)));
        ui.label(egui::RichText::new("FM27 LIVE").small().color(egui::Color32::from_rgb(76, 175, 80)));
    });
    ui.label(egui::RichText::new("Live market and contract controls for the selected player.").weak());
    ui.add_space(12.0);
    egui::Frame::group(ui.style())
        .inner_margin(egui::Margin::symmetric(14, 12))
        .show(ui, |ui| {
            ui.horizontal_wrapped(|ui| {
                ui.vertical(|ui| {
                    ui.label(egui::RichText::new("CURRENT CLUB").small().strong());
                    ui.label(player.club_name.as_deref().unwrap_or("Free Agent"));
                });
                ui.separator();
                ui.vertical(|ui| {
                    ui.label(egui::RichText::new("PLAYER").small().strong());
                    ui.label(player.name.as_deref().unwrap_or("Unknown"));
                });
                ui.separator();
                ui.vertical(|ui| {
                    ui.label(egui::RichText::new("MODE").small().strong());
                    ui.colored_label(egui::Color32::from_rgb(76, 175, 80), "Live memory editing");
                });
            });
        });
    ui.add_space(12.0);
'@

Replace-Required $p '        ui.strong("Market Status");' @'
        ui.label(egui::RichText::new("MARKET & CONTRACT").size(15.0).strong());
        ui.add_space(4.0);
'@

Replace-Required $p @'
    ui.add_space(12.0);
    ui.separator();
    ui.strong("Advanced Transfer Actions");
    ui.label("These need multiple FM27 records to be updated atomically. They are intentionally disabled until the memory chains are verified on the current build.");
    ui.horizontal_wrapped(|ui| {
        ui.add_enabled(false, egui::Button::new("Attract Clubs"));
        ui.add_enabled(false, egui::Button::new("Create Future Transfer"));
        ui.add_enabled(false, egui::Button::new("Force Transfer"));
    });
'@ @'
    ui.add_space(18.0);
    egui::Frame::group(ui.style())
        .inner_margin(egui::Margin::symmetric(14, 12))
        .show(ui, |ui| {
            ui.horizontal(|ui| {
                ui.label(egui::RichText::new("ADVANCED TRANSFER ACTIONS").size(15.0).strong());
                ui.label(egui::RichText::new("EXPERIMENTAL").small().color(egui::Color32::from_rgb(255, 152, 0)));
            });
            ui.label(egui::RichText::new("Force Transfer requires the destination team, contract and squad-membership chains to be validated together. It will unlock only when a partial write cannot be performed.").weak());
            ui.add_space(8.0);
            ui.horizontal_wrapped(|ui| {
                ui.add_enabled(false, egui::Button::new("Attract Clubs"));
                ui.add_enabled(false, egui::Button::new("Future Transfer"));
                ui.add_enabled(false, egui::Button::new("Force Transfer (mapping in progress)"));
            });
        });
'@

# Make profile tabs and panels breathe more; this is intentionally global and
# leaves the memory/editor backend untouched.
$settings = 'src/settings.rs'
Replace-Required $settings '    v.widgets.inactive.bg_fill = egui::Color32::from_rgb(28, 34, 47);' @'
    v.window_stroke = egui::Stroke::new(1.0, egui::Color32::from_rgb(44, 52, 70));
    v.widgets.inactive.bg_fill = egui::Color32::from_rgb(28, 34, 47);
'@

Write-Host 'Element v0.4 UI redesign layer applied successfully.'
