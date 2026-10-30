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

# Replace the v0.6 hero with an Element UI 2.0 hero that includes the configured facepack image.
Replace-Required $p @'
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
'@ @'
    // Element UI 2.0 hero. Face is loaded from the user's configured facepack by player UID.
    egui::Frame::none()
        .fill(egui::Color32::from_rgb(31, 92, 214))
        .inner_margin(egui::Margin::symmetric(18, 14))
        .show(ui, |ui| {
            ui.horizontal(|ui| {
                let face_uid = player.field_u32("p_uid").filter(|&uid| uid > 0);
                if let (Some(path), Some(uid)) = (face_pack_path, face_uid) {
                    let img_path = std::path::Path::new(path).join(format!("{uid}.png"));
                    let uri = format!("file:///{}", img_path.to_string_lossy().replace('\\', "/"));
                    egui::Frame::none()
                        .fill(egui::Color32::from_rgb(17, 24, 39))
                        .inner_margin(egui::Margin::same(3))
                        .show(ui, |ui| { ui.add(egui::Image::new(uri).max_size(egui::vec2(86.0, 86.0))); });
                    ui.add_space(12.0);
                }
                ui.vertical(|ui| {
                    ui.label(egui::RichText::new("ELEMENT PLAYER PROFILE").small().strong().color(egui::Color32::from_rgb(205, 220, 255)));
                    ui.label(egui::RichText::new(player.name.as_deref().unwrap_or("Unknown")).size(27.0).strong().color(egui::Color32::WHITE));
                    ui.horizontal(|ui| {
                        ui.label(egui::RichText::new(player.club_name.as_deref().unwrap_or("Free Agent")).strong().color(egui::Color32::WHITE));
                        if let Some(nation) = player.nationality.as_deref() {
                            ui.label(egui::RichText::new(format!("  •  {nation}")).color(egui::Color32::from_rgb(220, 230, 255)));
                        }
                        if let Some(uid) = player.field_u32("p_uid") {
                            ui.label(egui::RichText::new(format!("  •  UID {uid}")).small().color(egui::Color32::from_rgb(205, 220, 255)));
                        }
                    });
                });
                ui.with_layout(egui::Layout::right_to_left(egui::Align::Center), |ui| {
                    for (label, value) in [("PA", player.field_u8("p_pa")), ("CA", player.field_u8("p_ca"))] {
                        if let Some(value) = value {
                            egui::Frame::none().fill(egui::Color32::from_rgb(24, 69, 165)).inner_margin(egui::Margin::symmetric(12, 8)).show(ui, |ui| {
                                ui.vertical_centered(|ui| {
                                    ui.label(egui::RichText::new(label).small().color(egui::Color32::from_rgb(205, 220, 255)));
                                    ui.label(egui::RichText::new(value.to_string()).size(20.0).strong().color(egui::Color32::WHITE));
                                });
                            });
                        }
                    }
                    if let Some(wage) = player.field_u32("p_contract_wage") {
                        egui::Frame::none().fill(egui::Color32::from_rgb(24, 69, 165)).inner_margin(egui::Margin::symmetric(12, 8)).show(ui, |ui| {
                            ui.vertical_centered(|ui| {
                                ui.label(egui::RichText::new("WAGE").small().color(egui::Color32::from_rgb(205, 220, 255)));
                                ui.label(egui::RichText::new(format_wage(wage, wage_period)).strong().color(egui::Color32::WHITE));
                            });
                        });
                    }
                });
            });
        });
    ui.add_space(8.0);
'@

# Avoid showing the same face twice on Information now that it lives in the hero.
Replace-Required $p @'
    // Face image — shown when a face pack path is configured and the UID is known.
    let face_uid = player.field_u32("p_uid").filter(|&uid| uid > 0);
    if let (Some(path), Some(uid)) = (face_pack_path, face_uid) {
        let img_path = std::path::Path::new(path).join(format!("{uid}.png"));
        let uri = format!("file:///{}", img_path.to_string_lossy().replace('\\', "/"));
        ui.add(egui::Image::new(uri).max_size(egui::vec2(80.0, 80.0)));
        ui.add_space(4.0);
    }

'@ ''

$c = 'src/ui/club_panel.rs'

# Give clubs a proper dashboard hero.
Replace-Required $c @'
    entity_header::show(
        ui,
        &club.full_name,
        "Club",
        club.uid,
        None,
        None,
        None,
        None,
    );
'@ @'
    egui::Frame::none()
        .fill(egui::Color32::from_rgb(31, 92, 214))
        .inner_margin(egui::Margin::symmetric(18, 14))
        .show(ui, |ui| {
            ui.horizontal(|ui| {
                ui.vertical(|ui| {
                    ui.label(egui::RichText::new("ELEMENT CLUB PROFILE").small().strong().color(egui::Color32::from_rgb(205, 220, 255)));
                    ui.label(egui::RichText::new(&club.full_name).size(26.0).strong().color(egui::Color32::WHITE));
                    ui.label(egui::RichText::new(format!("UID {}", club.uid)).color(egui::Color32::from_rgb(220, 230, 255)));
                });
            });
        });
    ui.add_space(8.0);
'@

# Add a visible team-development workspace. Actions stay guarded until FM27 team tactical
# memory fields are mapped; we do not fake them by writing unrelated staff attributes.
Replace-Required $c @'
fn show_overview(
    schemas: &'static crate::fields::VersionedSchemas,
    ui: &mut egui::Ui,
    club: &mut ClubView,
    edits: &mut Vec<FieldEdit>,
) {
    ui.strong("Identity");
'@ @'
fn show_overview(
    schemas: &'static crate::fields::VersionedSchemas,
    ui: &mut egui::Ui,
    club: &mut ClubView,
    edits: &mut Vec<FieldEdit>,
) {
    egui::Frame::group(ui.style())
        .fill(egui::Color32::from_rgb(18, 23, 33))
        .inner_margin(egui::Margin::symmetric(12, 10))
        .show(ui, |ui| {
            ui.label(egui::RichText::new("TEAM DEVELOPMENT").size(14.0).strong().color(egui::Color32::from_rgb(116, 145, 255)));
            ui.label(egui::RichText::new("Club-wide tactical tools").weak());
            ui.add_space(6.0);
            ui.horizontal_wrapped(|ui| {
                ui.add_enabled(false, egui::Button::new("Max Tactical Knowledge"));
                ui.add_enabled(false, egui::Button::new("Max Tactical Familiarity"));
                ui.add_enabled(false, egui::Button::new("Max Team Cohesion"));
                ui.add_enabled(false, egui::Button::new("Max Morale"));
            });
            ui.label(egui::RichText::new("FM27 team tactical/cohesion offsets are not mapped yet; buttons unlock only after live-memory validation.").small().color(egui::Color32::from_rgb(255, 184, 77)));
        });
    ui.add_space(10.0);
    ui.strong("Identity");
'@

Write-Host 'Element v0.7 UI 2.0 player faces + club development shell applied successfully.'
