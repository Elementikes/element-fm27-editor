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

# v0.8: move from a lightly themed upstream profile to a dense Element editor workspace.
# Keep all proven FieldEdit/memory write mechanics unchanged.
$p = 'src/ui/player_panel.rs'

# Make the profile navigation read like a professional editor sidebar/section rail.
Replace-Required $p @'
    ui.horizontal(|ui| {
        ui.selectable_value(tab, PlayerTab::Overview, "Information");
        ui.selectable_value(tab, PlayerTab::PositionsTraits, "Positions & Traits");
        ui.selectable_value(tab, PlayerTab::Contract, "Contract");
        ui.selectable_value(tab, PlayerTab::TransferLab, "Move to Club");
    });
    ui.separator();
'@ @'
    egui::Frame::none()
        .fill(egui::Color32::from_rgb(11, 14, 20))
        .inner_margin(egui::Margin::symmetric(10, 7))
        .show(ui, |ui| {
            ui.horizontal_wrapped(|ui| {
                ui.spacing_mut().item_spacing.x = 4.0;
                ui.selectable_value(tab, PlayerTab::Overview, "  Information  ");
                ui.selectable_value(tab, PlayerTab::PositionsTraits, "  Positions & Traits  ");
                ui.selectable_value(tab, PlayerTab::Contract, "  Contract  ");
                ui.selectable_value(tab, PlayerTab::TransferLab, "  Move to Club  ");
            });
        });
    ui.add_space(6.0);
'@

# Strengthen the information dashboard hierarchy.
Replace-Required $p @'
    ui.label(egui::RichText::new("PLAYER ATTRIBUTES").size(14.0).strong().color(egui::Color32::from_rgb(116, 145, 255)));
'@ @'
    egui::Frame::none()
        .fill(egui::Color32::from_rgb(11, 14, 20))
        .inner_margin(egui::Margin::symmetric(10, 7))
        .show(ui, |ui| {
            ui.horizontal(|ui| {
                ui.label(egui::RichText::new("PLAYER ATTRIBUTES").size(14.0).strong().color(egui::Color32::from_rgb(232, 236, 244)));
                ui.with_layout(egui::Layout::right_to_left(egui::Align::Center), |ui| {
                    ui.label(egui::RichText::new("LIVE EDIT").small().strong().color(egui::Color32::from_rgb(75, 210, 130)));
                });
            });
        });
'@

# Cards: closer spacing, subtle border and professional dark panel surface.
Replace-Required $p @'
            egui::Frame::group(col.style())
                .fill(egui::Color32::from_rgb(18, 23, 33))
                .inner_margin(egui::Margin::symmetric(10, 9))
'@ @'
            egui::Frame::group(col.style())
                .fill(egui::Color32::from_rgb(26, 32, 48))
                .stroke(egui::Stroke::new(1.0, egui::Color32::from_rgb(42, 50, 69)))
                .rounding(egui::Rounding::same(6.0))
                .inner_margin(egui::Margin::symmetric(10, 8))
'@

# Quick actions become a right-looking toolbar strip rather than debug buttons.
Replace-Required $p @'
            ui.horizontal_wrapped(|ui| {
                ui.label(egui::RichText::new("QUICK ACTIONS").strong().color(egui::Color32::from_rgb(116, 145, 255)));
'@ @'
            ui.horizontal_wrapped(|ui| {
                ui.label(egui::RichText::new("QUICK ACTIONS").strong().color(egui::Color32::from_rgb(232, 236, 244)));
                ui.separator();
'@

$c = 'src/ui/club_panel.rs'

# Club document tabs get the same dark editor strip.
Replace-Required $c @'
    ui.horizontal(|ui| {
        ui.selectable_value(tab, ClubTab::Overview, "Overview");
        ui.selectable_value(tab, ClubTab::Facilities, "Facilities");
        ui.selectable_value(tab, ClubTab::Finance, "Finance");
        ui.selectable_value(tab, ClubTab::Stadium, "Stadium (read-only)");
    });
    ui.separator();
'@ @'
    egui::Frame::none()
        .fill(egui::Color32::from_rgb(11, 14, 20))
        .inner_margin(egui::Margin::symmetric(10, 7))
        .show(ui, |ui| {
            ui.horizontal_wrapped(|ui| {
                ui.selectable_value(tab, ClubTab::Overview, "  Information  ");
                ui.selectable_value(tab, ClubTab::Facilities, "  Facilities  ");
                ui.selectable_value(tab, ClubTab::Finance, "  Finance  ");
                ui.selectable_value(tab, ClubTab::Stadium, "  Stadium  ");
            });
        });
    ui.add_space(6.0);
'@

# Team development card matches the new panel language.
Replace-Required $c @'
    egui::Frame::group(ui.style())
        .fill(egui::Color32::from_rgb(18, 23, 33))
        .inner_margin(egui::Margin::symmetric(12, 10))
'@ @'
    egui::Frame::group(ui.style())
        .fill(egui::Color32::from_rgb(26, 32, 48))
        .stroke(egui::Stroke::new(1.0, egui::Color32::from_rgb(42, 50, 69)))
        .rounding(egui::Rounding::same(6.0))
        .inner_margin(egui::Margin::symmetric(12, 10))
'@

Write-Host 'Element v0.8 dense editor shell applied successfully.'
