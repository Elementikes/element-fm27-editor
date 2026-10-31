$ErrorActionPreference = 'Stop'
$SourceRoot = (Get-Location).Path

function Read-Text([string]$RelativePath) {
    $Path=Join-Path $SourceRoot $RelativePath
    if(-not(Test-Path -LiteralPath $Path)){throw "Source file not found: $Path"}
    [IO.File]::ReadAllText($Path)
}
function Write-Text([string]$RelativePath,[string]$Text){
    $Path=Join-Path $SourceRoot $RelativePath
    [IO.File]::WriteAllText($Path,$Text,[Text.UTF8Encoding]::new($false))
}
function Replace-Required([string]$Text,[string]$Old,[string]$New,[string]$Label){
    if(-not $Text.Contains($Old)){throw "v4.2b: expected source fragment not found: $Label"}
    $Text.Replace($Old,$New)
}

# -----------------------------------------------------------------------------
# Element v4.2b — SQUAD BULK ACTIONS
# Multi-select framework + verified direct morale write. Injury lists, bans,
# cohesion, registration and home-grown records are not bulk-cached/mapped yet,
# so those controls remain visible but locked instead of guessing writes.
# -----------------------------------------------------------------------------

$path='src/ui/club_panel.rs'
$text=Read-Text $path
$text=Replace-Required $text 'ClubTab::Squads => show_squads(schemas, ui, club),' 'ClubTab::Squads => show_squads(schemas, ui, club, &mut edits),' 'squad match call'
$text=Replace-Required $text @'
fn show_squads(
    schemas: &'static crate::fields::VersionedSchemas,
    ui: &mut egui::Ui,
    club: &ClubView,
) {
'@ @'
fn show_squads(
    schemas: &'static crate::fields::VersionedSchemas,
    ui: &mut egui::Ui,
    club: &ClubView,
    edits: &mut Vec<FieldEdit>,
) {
'@ 'show_squads signature'

# Upgrade badge/subtitle without making cosmetic wording build-critical.
$text=$text.Replace('egui::RichText::new("v3.8.3 • SQUAD HEALTH")','egui::RichText::new("v4.2 • SQUAD ACTIONS")')

# Add selection state immediately after the rows are built/sorted so SELECT ALL
# follows the currently visible/search-filtered roster.
$anchor=@'
    rows.sort_by(|a, b| {
        let ord = match sort {
            0 => a.name.to_lowercase().cmp(&b.name.to_lowercase()),
            1 => element_squad_position(schemas, a).0.cmp(element_squad_position(schemas, b).0),
            2 => element_squad_age(schemas, a).cmp(&element_squad_age(schemas, b)),
            3 => a.ca.cmp(&b.ca),
            4 => a.pa.cmp(&b.pa),
            5 => a.squad_status.cmp(&b.squad_status),
            6 => a.wage.cmp(&b.wage),
            _ => a.morale.cmp(&b.morale),
        };
        if descending { ord.reverse() } else { ord }
    });

    ui.add_space(4.0);
'@
$replacement=@'
    rows.sort_by(|a, b| {
        let ord = match sort {
            0 => a.name.to_lowercase().cmp(&b.name.to_lowercase()),
            1 => element_squad_position(schemas, a).0.cmp(element_squad_position(schemas, b).0),
            2 => element_squad_age(schemas, a).cmp(&element_squad_age(schemas, b)),
            3 => a.ca.cmp(&b.ca),
            4 => a.pa.cmp(&b.pa),
            5 => a.squad_status.cmp(&b.squad_status),
            6 => a.wage.cmp(&b.wage),
            _ => a.morale.cmp(&b.morale),
        };
        if descending { ord.reverse() } else { ord }
    });

    let selected_id = egui::Id::new(("element_squad_bulk_selected", club.addr));
    let mut selected = ui.ctx().data_mut(|d| d.get_temp::<Vec<u64>>(selected_id).unwrap_or_default());
    selected.retain(|addr| cache.players.iter().any(|p| p.addr == *addr && p.club_id == Some(club.uid)));

    egui::Frame::group(ui.style())
        .fill(egui::Color32::from_rgb(19, 24, 35))
        .stroke(egui::Stroke::new(1.0, egui::Color32::from_rgb(42, 50, 68)))
        .rounding(egui::Rounding::same(4))
        .inner_margin(egui::Margin::symmetric(7, 5))
        .show(ui, |ui| {
            ui.horizontal_wrapped(|ui| {
                ui.label(egui::RichText::new(format!("{} SELECTED", selected.len())).size(8.0).strong().color(egui::Color32::from_rgb(112,177,255)));
                if ui.small_button("SELECT VISIBLE").clicked() {
                    selected = rows.iter().map(|p| p.addr).collect();
                }
                if ui.small_button("CLEAR").clicked() { selected.clear(); }
                ui.separator();
                let writable = crate::ui::navigation::editing_enabled(ui) && !selected.is_empty();
                if ui.add_enabled(writable, egui::Button::new("MAX MORALE")).on_hover_text("Set verified FM27 morale to 20 for every selected player. Uses normal write + Undo.").clicked() {
                    if let Some(offset) = schemas.offset_of("p_morale") {
                        for player in cache.players.iter().filter(|p| selected.contains(&p.addr) && p.club_id == Some(club.uid)) {
                            let Some(old_raw) = player.raw.get(offset).copied() else { continue; };
                            if old_raw == 20 { continue; }
                            let physical = crate::player::player_phys_offset(schemas, offset as u64, player.person_shift);
                            edits.push(FieldEdit {
                                addr: player.addr + physical,
                                old_raw: vec![old_raw],
                                new_raw: vec![20],
                                description: format!("{} — Morale: {} → 20", player.name, old_raw),
                            });
                        }
                    }
                }
                ui.add_enabled(false, egui::Button::new("HEAL"))
                    .on_disabled_hover_text("Individual Heal is verified upstream, but injuries are not yet bulk-cached in Club > Squads. Element will not fabricate injury addresses.");
                ui.add_enabled(false, egui::Button::new("LIFT BANS"))
                    .on_disabled_hover_text("Absence records are not bulk-cached for squad actions yet.");
                ui.add_enabled(false, egui::Button::new("MAX COHESION"))
                    .on_disabled_hover_text("Team cohesion write location is not independently mapped yet.");
                ui.add_enabled(false, egui::Button::new("REGISTER UEFA"))
                    .on_disabled_hover_text("Continental registration vectors and competition eligibility are not mapped yet.");
                ui.add_enabled(false, egui::Button::new("HOME GROWN / TRAINED AT CLUB"))
                    .on_disabled_hover_text("Home-grown and trained-at-club records are not mapped yet; these are not safe boolean toggles.");
            });
            ui.label(egui::RichText::new("Bulk actions target exactly the checked players. SELECT VISIBLE follows the current squad search/filter. Reload Save after writes to refresh cached morale labels.").size(7.2).color(egui::Color32::from_rgb(132,146,170)));
        });
    ui.ctx().data_mut(|d| d.insert_temp(selected_id, selected.clone()));

    ui.add_space(4.0);
'@
$text=Replace-Required $text $anchor $replacement 'selection action bar insertion'

# Add checkbox column to grid.
$text=Replace-Required $text @'
                egui::Grid::new(("element_live_squad_grid", club.addr))
                    .num_columns(9)
'@ @'
                egui::Grid::new(("element_live_squad_grid", club.addr))
                    .num_columns(10)
'@ 'squad grid column count'
$text=Replace-Required $text @'
                        for h in ["Player", "Position", "Age", "CA", "PA", "Condition", "Morale", "Squad Status", "Wage"] {
                            ui.label(egui::RichText::new(h).size(8.0).strong().color(egui::Color32::from_rgb(170, 185, 210)));
                        }
'@ @'
                        for h in ["✓", "Player", "Position", "Age", "CA", "PA", "Condition", "Morale", "Squad Status", "Wage"] {
                            ui.label(egui::RichText::new(h).size(8.0).strong().color(egui::Color32::from_rgb(170, 185, 210)));
                        }
'@ 'squad grid headers'
$text=Replace-Required $text @'
                        for player in rows {
                            navigation::player_link(ui, player);
'@ @'
                        for player in rows {
                            let mut checked = selected.contains(&player.addr);
                            if ui.checkbox(&mut checked, "").changed() {
                                if checked {
                                    if !selected.contains(&player.addr) { selected.push(player.addr); }
                                } else {
                                    selected.retain(|addr| *addr != player.addr);
                                }
                                ui.ctx().data_mut(|d| d.insert_temp(selected_id, selected.clone()));
                            }
                            navigation::player_link(ui, player);
'@ 'squad row checkbox'

Write-Text $path $text
Write-Host 'Element v4.2b Squad Bulk Actions applied successfully.'
