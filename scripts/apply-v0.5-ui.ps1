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

$p = 'src/ui/player_panel.rs'

# Replace the flat horizontal player tabs with a stronger editor-style navigation strip.
Replace-Required $p @'
    // Sub-tab bar
    ui.horizontal(|ui| {
        ui.selectable_value(tab, PlayerTab::Overview, "Overview");
        ui.selectable_value(tab, PlayerTab::PositionsTraits, "Positions & Traits");
        if player.contract_raw.is_some() {
            ui.selectable_value(tab, PlayerTab::Contract, "Contract");
            ui.selectable_value(tab, PlayerTab::TransferLab, "Transfer Lab");
        }
    });
    ui.separator();
'@ @'
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

# Make the overview feel like an editor dashboard rather than a debug form.
Replace-Required $p '    // Top info row: Personal | Ability | Reputation' @'
    ui.horizontal(|ui| {
        ui.heading(egui::RichText::new("Player Information").size(22.0).strong());
        if let (Some(ca), Some(pa)) = (player.field_u8("p_ca"), player.field_u8("p_pa")) {
            ui.separator();
            ui.label(egui::RichText::new(format!("CA {ca} / PA {pa}")).strong().color(egui::Color32::from_rgb(116, 145, 255)));
        }
    });
    ui.add_space(8.0);

    // Top info row: Personal | Ability | Reputation
'@

# Rebrand the transfer page as the direct Move-to-Club workspace and expose a target-club
# search field now. The actual force write remains guarded until linked membership records
# are mapped; this prevents a one-pointer partial transfer from corrupting the save.
Replace-Required $p '        ui.heading(egui::RichText::new("Transfer Lab").size(24.0).strong());' '        ui.heading(egui::RichText::new("Move to Club").size(24.0).strong());'
Replace-Required $p '    ui.label(egui::RichText::new("Live market and contract controls for the selected player.").weak());' @'
    ui.label(egui::RichText::new("Transfer workspace for the selected player. Market and contract writes are live; club movement is protected until the complete FM27 chain is validated.").weak());
'@

Replace-Required $p '            ui.label(egui::RichText::new("ADVANCED TRANSFER ACTIONS").size(15.0).strong());' '            ui.label(egui::RichText::new("MOVE PLAYER").size(15.0).strong());'
Replace-Required $p @'
            ui.label(egui::RichText::new("Force Transfer requires the destination team, contract and squad-membership chains to be validated together. It will unlock only when a partial write cannot be performed.").weak());
            ui.add_space(8.0);
            ui.horizontal_wrapped(|ui| {
                ui.add_enabled(false, egui::Button::new("Attract Clubs"));
                ui.add_enabled(false, egui::Button::new("Future Transfer"));
                ui.add_enabled(false, egui::Button::new("Force Transfer (mapping in progress)"));
            });
'@ @'
            ui.label(egui::RichText::new("Choose the destination club here. v0.5 deliberately blocks the final write until team + contract + squad membership can be committed together.").weak());
            ui.add_space(8.0);
            let target_id = egui::Id::new(("element_target_club", player.addr));
            let mut target = ui.data_mut(|d| d.get_temp::<String>(target_id).unwrap_or_default());
            ui.horizontal(|ui| {
                ui.label("Target club");
                let response = ui.add_sized([300.0, 28.0], egui::TextEdit::singleline(&mut target).hint_text("Search club name..."));
                if response.changed() { ui.data_mut(|d| d.insert_temp(target_id, target.clone())); }
            });
            ui.add_space(8.0);
            ui.horizontal_wrapped(|ui| {
                ui.add_enabled(false, egui::Button::new("Force Transfer — Experimental"));
                ui.add_enabled(false, egui::Button::new("Future Transfer"));
                ui.add_enabled(false, egui::Button::new("Attract Clubs"));
            });
            ui.label(egui::RichText::new("LOCKED: full FM27 membership chain not verified yet — no partial pointer writes allowed.").small().color(egui::Color32::from_rgb(255, 152, 0)));
'@

Write-Host 'Element v0.5 editor-style player UI applied successfully.'
