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

# v0.6 is deliberately a visible structural pass: make the player page look like
# an editor workspace immediately, without touching proven memory-write code.
$p = 'src/ui/player_panel.rs'

Replace-Required $p @'
    crate::ui::entity_header::show(
        ui,
        player.name.as_deref().unwrap_or("Unknown"),
        "Player",
        player
            .field_u32("p_uid")
            .map(|v| v.to_string())
            .unwrap_or_else(|| "Unknown".into()),
        crate::ui::entity_header::age(schemas, &player.raw, "p_dob"),
        player.club_name.as_deref(),
        player.club_addr,
        player.nationality.as_deref(),
    );
'@ @'
    // Element 2.0 player hero: a full-width editor header rather than the upstream debug card.
    egui::Frame::none()
        .fill(egui::Color32::from_rgb(38, 91, 205))
        .inner_margin(egui::Margin::symmetric(18, 14))
        .show(ui, |ui| {
            ui.horizontal(|ui| {
                ui.vertical(|ui| {
                    ui.label(egui::RichText::new("PLAYER").small().strong().color(egui::Color32::from_rgb(205, 220, 255)));
                    ui.label(egui::RichText::new(player.name.as_deref().unwrap_or("Unknown")).size(25.0).strong().color(egui::Color32::WHITE));
                    ui.horizontal(|ui| {
                        ui.label(egui::RichText::new(player.club_name.as_deref().unwrap_or("Free Agent")).strong().color(egui::Color32::WHITE));
                        if let Some(nation) = player.nationality.as_deref() {
                            ui.label(egui::RichText::new(format!(" • {nation}")).color(egui::Color32::from_rgb(220, 230, 255)));
                        }
                    });
                });
                ui.with_layout(egui::Layout::right_to_left(egui::Align::Center), |ui| {
                    if let Some(pa) = player.field_u8("p_pa") {
                        ui.label(egui::RichText::new(format!("PA  {pa}")).size(18.0).strong().color(egui::Color32::WHITE));
                    }
                    if let Some(ca) = player.field_u8("p_ca") {
                        ui.label(egui::RichText::new(format!("CA  {ca}")).size(18.0).strong().color(egui::Color32::WHITE));
                    }
                    if let Some(price) = player.field_u32("p_asking_price") {
                        ui.label(egui::RichText::new(format!("ASK  {price}")).strong().color(egui::Color32::WHITE));
                    }
                });
            });
        });
    ui.add_space(6.0);
'@

# Turn the overview into dense framed attribute cards. This replaces the visual
# separators with a clear dashboard grid while preserving category_column writes.
Replace-Required $p @'
    ui.separator();

    for groups in [
'@ @'
    ui.add_space(10.0);
    ui.label(egui::RichText::new("PLAYER ATTRIBUTES").size(14.0).strong().color(egui::Color32::from_rgb(116, 145, 255)));
    ui.add_space(6.0);

    for groups in [
'@

Replace-Required $p @'
        crate::ui::entity_header::columns(ui, |index, col| {
            let (heading, category) = groups[index];
            field_widget::category_column(
                schemas,
                col,
                heading,
                Entity::Player,
                category,
                &mut player.raw,
                addr,
                edits,
            );
        });
'@ @'
        crate::ui::entity_header::columns(ui, |index, col| {
            let (heading, category) = groups[index];
            egui::Frame::group(col.style())
                .fill(egui::Color32::from_rgb(18, 23, 33))
                .inner_margin(egui::Margin::symmetric(10, 9))
                .show(col, |col| {
                    col.label(egui::RichText::new(heading).size(14.0).strong().color(egui::Color32::from_rgb(235, 239, 248)));
                    col.separator();
                    field_widget::category_column(
                        schemas,
                        col,
                        "",
                        Entity::Player,
                        category,
                        &mut player.raw,
                        addr,
                        edits,
                    );
                });
        });
'@

# Add an unmistakable quick-action rail to the player information page.
Replace-Required $p @'
    ui.add_space(8.0);

    // Top info row: Personal | Ability | Reputation
'@ @'
    ui.add_space(8.0);
    egui::Frame::group(ui.style())
        .fill(egui::Color32::from_rgb(18, 23, 33))
        .inner_margin(egui::Margin::symmetric(12, 9))
        .show(ui, |ui| {
            ui.horizontal_wrapped(|ui| {
                ui.label(egui::RichText::new("QUICK ACTIONS").strong().color(egui::Color32::from_rgb(116, 145, 255)));
                ui.add_enabled(false, egui::Button::new("Heal"));
                ui.add_enabled(false, egui::Button::new("Max Condition"));
                ui.add_enabled(false, egui::Button::new("Max Morale"));
                ui.add_enabled(false, egui::Button::new("Remove Ban"));
                ui.add_enabled(false, egui::Button::new("Freeze"));
                ui.add_enabled(false, egui::Button::new("Move to Club"));
            });
        });
    ui.add_space(10.0);

    // Top info row: Personal | Ability | Reputation
'@

Write-Host 'Element v0.6 full-width editor shell applied successfully.'
