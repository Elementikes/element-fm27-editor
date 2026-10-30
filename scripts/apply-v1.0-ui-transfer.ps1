$ErrorActionPreference = 'Stop'
$SourceRoot = (Get-Location).Path

function Replace-Required {
    param([string]$RelativePath, [string]$Old, [string]$New)
    $Path = Join-Path $SourceRoot $RelativePath
    $text = [IO.File]::ReadAllText($Path)
    if (-not $text.Contains($Old)) { throw "Expected text not found in $RelativePath`n--- expected ---`n$Old" }
    $text = $text.Replace($Old, $New)
    [IO.File]::WriteAllText($Path, $text, [Text.UTF8Encoding]::new($false))
}

$p = 'src/ui/player_panel.rs'

# Fix the broken vertical wage presentation by replacing the v0.7 hero with a bounded,
# horizontal FMRTE-inspired profile hero. Keep Element branding and original implementation.
$text = [IO.File]::ReadAllText((Join-Path $SourceRoot $p))
$start = $text.IndexOf('    // Element UI 2.0: player hero')
$end = $text.IndexOf('    // Element profile navigation:', $start)
if ($start -lt 0 -or $end -lt 0) { throw 'Element player hero markers not found' }
$newHero = @'
    // Element v1.0 player hero: bounded horizontal layout; metric values never wrap vertically.
    let face_uid = player.field_u32("p_uid").filter(|&uid| uid > 0);
    let ca = player.field_u8("p_ca").map(|v| v.to_string()).unwrap_or_else(|| "—".into());
    let pa = player.field_u8("p_pa").map(|v| v.to_string()).unwrap_or_else(|| "—".into());
    let value = player.field_u32("p_value").map(|v| v.to_string()).unwrap_or_else(|| "—".into());
    let wage = player.contract_raw.as_ref()
        .and_then(|raw| schemas.field("p_contract_wage").and_then(|f| fields::read_u32(raw, f.offset)))
        .map(|v| format_wage(v, wage_period)).unwrap_or_else(|| "—".into());

    egui::Frame::none()
        .fill(egui::Color32::from_rgb(33, 96, 224))
        .inner_margin(egui::Margin::same(16))
        .rounding(egui::Rounding::same(5))
        .show(ui, |ui| {
            ui.set_min_height(122.0);
            ui.horizontal(|ui| {
                if let (Some(path), Some(uid)) = (face_pack_path, face_uid) {
                    let img_path = std::path::Path::new(path).join(format!("{uid}.png"));
                    let uri = format!("file:///{}", img_path.to_string_lossy().replace('\\', "/"));
                    ui.add(egui::Image::new(uri).fit_to_exact_size(egui::vec2(92.0, 92.0)));
                } else {
                    ui.allocate_ui(egui::vec2(92.0, 92.0), |ui| { ui.centered_and_justified(|ui| { ui.label("PLAYER"); }); });
                }
                ui.add_space(12.0);
                ui.vertical(|ui| {
                    ui.label(egui::RichText::new("ELEMENT PLAYER PROFILE").size(10.0).strong().color(egui::Color32::from_rgb(190, 211, 255)));
                    ui.label(egui::RichText::new(player.name.as_deref().unwrap_or("Unknown")).size(25.0).strong().color(egui::Color32::WHITE));
                    ui.horizontal(|ui| {
                        ui.label(egui::RichText::new(player.club_name.as_deref().unwrap_or("No club")).color(egui::Color32::WHITE));
                        ui.label(egui::RichText::new("•").color(egui::Color32::WHITE));
                        ui.label(egui::RichText::new(player.nationality.as_deref().unwrap_or("Unknown")).color(egui::Color32::WHITE));
                    });
                    if let Some(uid) = face_uid { ui.label(egui::RichText::new(format!("UID {uid}")).small().color(egui::Color32::from_rgb(205, 220, 255))); }
                });
                ui.with_layout(egui::Layout::right_to_left(egui::Align::Center), |ui| {
                    for (label, val) in [("WAGE", wage.as_str()), ("VALUE", value.as_str()), ("PA", pa.as_str()), ("CA", ca.as_str())] {
                        egui::Frame::none().fill(egui::Color32::from_rgb(27, 76, 176)).inner_margin(egui::Margin::symmetric(14, 10)).show(ui, |ui| {
                            ui.set_min_width(112.0);
                            ui.vertical_centered(|ui| {
                                ui.label(egui::RichText::new(label).size(9.0).color(egui::Color32::from_rgb(185, 207, 255)));
                                ui.add(egui::Label::new(egui::RichText::new(val).size(18.0).strong().color(egui::Color32::WHITE)).wrap(false));
                            });
                        });
                        ui.add_space(8.0);
                    }
                });
            });
        });
    ui.add_space(10.0);

'@
$text = $text.Substring(0,$start) + $newHero + $text.Substring($end)
[IO.File]::WriteAllText((Join-Path $SourceRoot $p), $text, [Text.UTF8Encoding]::new($false))

# Upgrade transfer wording: real club selection/readback is the next guarded stage; do not claim
# an unsafe one-pointer move is a complete transfer.
Replace-Required $p 'ui.add_enabled(false, egui::Button::new("Force Transfer — Experimental"));' 'ui.add_enabled(false, egui::Button::new("Force Transfer — validation required"));'
Replace-Required $p 'LOCKED: full FM27 membership chain not verified yet — no partial pointer writes allowed.' 'VALIDATION GATE: destination team is mapped; squad/contract membership must pass live read-back before Force Transfer unlocks.'

Write-Host 'Element v1.0 player hero + guarded transfer workspace applied.'
