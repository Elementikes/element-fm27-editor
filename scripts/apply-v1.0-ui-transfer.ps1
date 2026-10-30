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
$text = [IO.File]::ReadAllText((Join-Path $SourceRoot $p))
$start = $text.IndexOf('    // Element UI 2.0 hero.')
if ($start -lt 0) { throw 'Element player hero start marker not found' }
$tailMarker = '    ui.add_space(8.0);'
$tail = $text.IndexOf($tailMarker, $start)
if ($tail -lt 0) { throw 'Element player hero local tail not found' }
$end = $tail + $tailMarker.Length
while ($end -lt $text.Length -and ($text[$end] -eq "`r" -or $text[$end] -eq "`n")) { $end++ }
$newHero = @'
    // Element v1.3 player hero: Sortitoutsi resolver + direct PNG byte decoding.
    let face_uid = player.field_u32("p_uid").filter(|&uid| uid > 0);
    let ca = player.field_u8("p_ca").map(|v| v.to_string()).unwrap_or_else(|| "—".into());
    let pa = player.field_u8("p_pa").map(|v| v.to_string()).unwrap_or_else(|| "—".into());

    let format_grouped_eur = |v: u32| -> String {
        if v == 0 || v == u32::MAX { return "—".into(); }
        let raw = v.to_string();
        let mut grouped = String::with_capacity(raw.len() + raw.len() / 3);
        for (i, ch) in raw.chars().enumerate() {
            if i > 0 && (raw.len() - i) % 3 == 0 { grouped.push('.'); }
            grouped.push(ch);
        }
        format!("€{grouped}")
    };
    let format_weekly_wage = |v: u32| -> String {
        if v == 0 || v == u32::MAX { return "—".into(); }
        if v >= 1_000_000 {
            let millions = v as f64 / 1_000_000.0;
            if v % 1_000_000 == 0 { format!("€{millions:.0}M p/w") } else { format!("€{millions:.2}M p/w") }
        } else if v >= 1_000 {
            format!("€{:.0}K p/w", v as f64 / 1_000.0)
        } else { format!("€{v} p/w") }
    };
    let asking = player.field_u32("p_asking_price").map(&format_grouped_eur).unwrap_or_else(|| "—".into());
    let wage = player.field_u32("p_contract_wage").map(&format_weekly_wage).unwrap_or_else(|| "—".into());

    let sortitoutsi_root = std::env::var("USERPROFILE").ok().map(|home| {
        std::path::PathBuf::from(home)
            .join("Documents").join("Sports Interactive").join("Football Manager 27")
            .join("graphics").join("faces").join("sortitoutsi")
    });
    let configured_root = face_pack_path.map(std::path::PathBuf::from);
    let resolved_face_file = face_uid.and_then(|uid| {
        let mut candidates: Vec<std::path::PathBuf> = Vec::new();
        if let Some(root) = configured_root.as_ref() {
            candidates.push(root.join(format!("face_{uid}.png")));
            candidates.push(root.join(format!("{uid}.png")));
            candidates.push(root.join("faces").join(format!("face_{uid}.png")));
            candidates.push(root.join("iconfaces").join(format!("iconface_{uid}.png")));
        }
        if let Some(root) = sortitoutsi_root.as_ref() {
            candidates.push(root.join("faces").join(format!("face_{uid}.png")));
            candidates.push(root.join("iconfaces").join(format!("iconface_{uid}.png")));
        }
        candidates.into_iter().find(|p| p.exists())
    });

    egui::Frame::none()
        .fill(egui::Color32::from_rgb(33, 96, 224))
        .inner_margin(egui::Margin::same(16))
        .rounding(egui::Rounding::same(5))
        .show(ui, |ui| {
            ui.set_min_height(122.0);
            ui.horizontal(|ui| {
                let mut face_rendered = false;
                if let Some(img_path) = resolved_face_file.as_ref() {
                    if let Ok(bytes) = std::fs::read(img_path) {
                        if let Ok(decoded) = image::load_from_memory(&bytes) {
                            let rgba = decoded.to_rgba8();
                            let size = [rgba.width() as usize, rgba.height() as usize];
                            let color_image = egui::ColorImage::from_rgba_unmultiplied(size, rgba.as_raw());
                            let texture = ui.ctx().load_texture(
                                format!("element_face_{}", face_uid.unwrap_or(0)),
                                color_image,
                                egui::TextureOptions::LINEAR,
                            );
                            ui.add(egui::Image::new(&texture).fit_to_exact_size(egui::vec2(92.0, 92.0)));
                            face_rendered = true;
                        }
                    }
                }
                if !face_rendered {
                    ui.allocate_ui(egui::vec2(92.0, 92.0), |ui| {
                        ui.centered_and_justified(|ui| { ui.label("NO FACE"); });
                    });
                }
                ui.add_space(12.0);
                ui.vertical(|ui| {
                    ui.label(egui::RichText::new("ELEMENT PLAYER PROFILE").size(10.0).strong().color(egui::Color32::from_rgb(190, 211, 255)));
                    ui.label(egui::RichText::new(player.name.as_deref().unwrap_or("Unknown")).size(25.0).strong().color(egui::Color32::WHITE));
                    ui.horizontal(|ui| {
                        ui.label(egui::RichText::new(player.club_name.as_deref().unwrap_or("No club")).color(egui::Color32::WHITE));
                        if let Some(nation) = player.nationality.as_deref() { ui.label(egui::RichText::new(format!(" • {nation}")).color(egui::Color32::WHITE)); }
                    });
                    if let Some(uid) = face_uid { ui.label(egui::RichText::new(format!("UID {uid}")).small().color(egui::Color32::from_rgb(205, 220, 255))); }
                });
                ui.with_layout(egui::Layout::right_to_left(egui::Align::Center), |ui| {
                    for (label, val) in [("WAGE", wage.as_str()), ("ASKING PRICE", asking.as_str()), ("PA", pa.as_str()), ("CA", ca.as_str())] {
                        egui::Frame::none().fill(egui::Color32::from_rgb(27, 76, 176)).inner_margin(egui::Margin::symmetric(14, 10)).show(ui, |ui| {
                            ui.set_min_width(128.0);
                            ui.set_max_width(175.0);
                            ui.vertical_centered(|ui| {
                                ui.label(egui::RichText::new(label).size(9.0).color(egui::Color32::from_rgb(185, 207, 255)));
                                ui.label(egui::RichText::new(val).size(17.0).strong().color(egui::Color32::WHITE));
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

Replace-Required $p 'ui.add_enabled(false, egui::Button::new("Force Transfer — Experimental"));' 'ui.add_enabled(false, egui::Button::new("Force Transfer — validation required"));'
Replace-Required $p 'LOCKED: full FM27 membership chain not verified yet — no partial pointer writes allowed.' 'VALIDATION GATE: destination team is mapped; squad/contract membership must pass live read-back before Force Transfer unlocks.'

Write-Host 'Element v1.3 direct PNG face decoding + Sortitoutsi resolver applied.'
