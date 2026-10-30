$ErrorActionPreference = 'Stop'
$SourceRoot = (Get-Location).Path
$p = Join-Path $SourceRoot 'src/ui/player_panel.rs'
$text = [IO.File]::ReadAllText($p)

# v1.5 moved player navigation into the contextual sidebar. Older generated
# player_panel variants do not always contain the exact v1.0 tab block that
# the transform removes. Seed the canonical block only when it is absent so
# the downstream transform stays deterministic across the pinned source stack.
$marker = '    // Element profile navigation: compact, high-contrast editor tabs.'
if (-not $text.Contains($marker)) {
$canonical = @'

    // Element profile navigation: compact, high-contrast editor tabs.
    egui::Frame::none()
        .fill(egui::Color32::from_rgb(20, 25, 36))
        .inner_margin(egui::Margin::symmetric(10, 8))
        .show(ui, |ui| {
            ui.horizontal_wrapped(|ui| {
                ui.selectable_value(tab, PlayerTab::Overview, "Information");
                ui.selectable_value(tab, PlayerTab::PositionsTraits, "Positions & Traits");
                if player.contract_raw.is_some() {
                    ui.selectable_value(tab, PlayerTab::Contract, "Contract");
                    ui.selectable_value(tab, PlayerTab::TransferLab, "Move to Club");
                }
            });
        });
    ui.add_space(6.0);
'@
    $text += $canonical
    [IO.File]::WriteAllText($p, $text, [Text.UTF8Encoding]::new($false))
    Write-Host 'v1.5 compatibility: seeded canonical navigation boundary.'
} else {
    Write-Host 'v1.5 compatibility: canonical navigation boundary already present.'
}
