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
    // Element v1.4 premium player hero: dense editor layout + direct face texture.
    let face_uid = player.field_u32("p_uid").filter(|&uid| uid > 0);
    let ca = player.field_u8("p_ca").map(|v| v.to_string()).unwrap_or_else(|| "—".into());
    let pa = player.field_u8("p_pa").map(|v| v.to_string()).unwrap_or_else(|| "—".into());
    let format_grouped_eur = |v: u32| -> String {
        if v == 0 || v == u32::MAX { return "—".into(); }
        let raw = v.to_string(); let mut grouped = String::new();
        for (i, ch) in raw.chars().enumerate() { if i > 0 && (raw.len()-i)%3 == 0 { grouped.push('.'); } grouped.push(ch); }
        format!("€{grouped}")
    };
    let format_weekly_wage = |v: u32| -> String {
        if v == 0 || v == u32::MAX { return "—".into(); }
        if v >= 1_000_000 { format!("€{:.2}M p/w", v as f64 / 1_000_000.0) }
        else if v >= 1_000 { format!("€{:.0}K p/w", v as f64 / 1_000.0) }
        else { format!("€{v} p/w") }
    };
    let asking = player.field_u32("p_asking_price").map(&format_grouped_eur).unwrap_or_else(|| "—".into());
    let wage = player.field_u32("p_contract_wage").map(&format_weekly_wage).unwrap_or_else(|| "—".into());
    let rep = player.field_u16("p_current_rep").map(|v| v.to_string()).unwrap_or_else(|| "—".into());
    let apps = player.field_u16("p_senior_apps").map(|v| v.to_string()).unwrap_or_else(|| "—".into());

    let sortitoutsi_root = std::env::var("USERPROFILE").ok().map(|home| std::path::PathBuf::from(home)
        .join("Documents").join("Sports Interactive").join("Football Manager 27").join("graphics").join("faces").join("sortitoutsi"));
    let configured_root = face_pack_path.map(std::path::PathBuf::from);
    let resolved_face_file = face_uid.and_then(|uid| {
        let mut candidates = Vec::new();
        if let Some(root) = configured_root.as_ref() {
            candidates.push(root.join(format!("face_{uid}.png"))); candidates.push(root.join(format!("{uid}.png")));
            candidates.push(root.join("faces").join(format!("face_{uid}.png"))); candidates.push(root.join("iconfaces").join(format!("iconface_{uid}.png")));
        }
        if let Some(root) = sortitoutsi_root.as_ref() {
            candidates.push(root.join("faces").join(format!("face_{uid}.png"))); candidates.push(root.join("iconfaces").join(format!("iconface_{uid}.png")));
        }
        candidates.into_iter().find(|p| p.exists())
    });

    let metric = |ui: &mut egui::Ui, label: &str, value: &str, width: f32| {
        egui::Frame::none().fill(egui::Color32::from_rgb(27, 35, 52)).rounding(egui::Rounding::same(5))
            .inner_margin(egui::Margin::symmetric(12, 8)).show(ui, |ui| {
                ui.set_min_width(width); ui.set_max_width(width);
                ui.label(egui::RichText::new(label).size(9.0).color(egui::Color32::from_rgb(132, 147, 173)));
                ui.label(egui::RichText::new(value).size(16.0).strong().color(egui::Color32::WHITE));
            });
    };

    egui::Frame::none().fill(egui::Color32::from_rgb(22, 28, 40)).stroke(egui::Stroke::new(1.0, egui::Color32::from_rgb(43, 54, 75)))
        .rounding(egui::Rounding::same(6)).inner_margin(egui::Margin::same(12)).show(ui, |ui| {
        ui.horizontal(|ui| {
            egui::Frame::none().fill(egui::Color32::from_rgb(13, 17, 25)).rounding(egui::Rounding::same(5)).inner_margin(egui::Margin::same(3)).show(ui, |ui| {
                let mut rendered = false;
                if let Some(img_path) = resolved_face_file.as_ref() { if let Ok(bytes) = std::fs::read(img_path) { if let Ok(decoded) = image::load_from_memory(&bytes) {
                    let rgba = decoded.to_rgba8(); let size=[rgba.width() as usize, rgba.height() as usize];
                    let ci=egui::ColorImage::from_rgba_unmultiplied(size,rgba.as_raw());
                    let tex=ui.ctx().load_texture(format!("element_face_{}",face_uid.unwrap_or(0)),ci,egui::TextureOptions::LINEAR);
                    ui.add(egui::Image::new(&tex).fit_to_exact_size(egui::vec2(86.0,86.0))); rendered=true;
                } } }
                if !rendered { ui.allocate_ui(egui::vec2(86.0,86.0),|ui|{ui.centered_and_justified(|ui|{ui.label("NO FACE");});}); }
            });
            ui.add_space(10.0);
            ui.vertical(|ui| {
                ui.label(egui::RichText::new("PLAYER PROFILE").size(9.0).strong().color(egui::Color32::from_rgb(71,126,240)));
                ui.label(egui::RichText::new(player.name.as_deref().unwrap_or("Unknown")).size(24.0).strong().color(egui::Color32::from_rgb(240,243,249)));
                ui.horizontal(|ui| {
                    ui.label(egui::RichText::new(player.club_name.as_deref().unwrap_or("No club")).size(12.0).strong().color(egui::Color32::from_rgb(205,214,230)));
                    if let Some(n)=player.nationality.as_deref(){ui.label(egui::RichText::new(format!("• {n}")).size(12.0).color(egui::Color32::from_rgb(151,164,185)));}
                });
                if let Some(uid)=face_uid { ui.label(egui::RichText::new(format!("UID {uid}")).size(9.0).color(egui::Color32::from_rgb(112,126,149))); }
            });
            ui.add_space(18.0);
            ui.with_layout(egui::Layout::right_to_left(egui::Align::Center), |ui| {
                metric(ui,"WAGE",&wage,132.0); ui.add_space(6.0); metric(ui,"ASKING PRICE",&asking,142.0); ui.add_space(6.0);
                metric(ui,"REPUTATION",&rep,108.0); ui.add_space(6.0); metric(ui,"APPS",&apps,76.0); ui.add_space(6.0);
                metric(ui,"PA",&pa,68.0); ui.add_space(6.0); metric(ui,"CA",&ca,68.0);
            });
        });
        ui.add_space(9.0);
        ui.horizontal_wrapped(|ui| {
            let badge = |ui: &mut egui::Ui, text: &str| { egui::Frame::none().fill(egui::Color32::from_rgb(30,39,56)).rounding(egui::Rounding::same(4)).inner_margin(egui::Margin::symmetric(9,5)).show(ui,|ui|{ui.label(egui::RichText::new(text).size(10.0).color(egui::Color32::from_rgb(190,201,219)));}); };
            badge(ui,"LIVE MEMORY"); badge(ui,"PLAYER");
            if player.contract_raw.is_some(){badge(ui,"CONTRACT ACTIVE");}
            if player.club_name.is_some(){badge(ui,"SENIOR SQUAD");}
        });
    });
    ui.add_space(8.0);

'@
$text = $text.Substring(0,$start) + $newHero + $text.Substring($end)
[IO.File]::WriteAllText((Join-Path $SourceRoot $p), $text, [Text.UTF8Encoding]::new($false))

Replace-Required $p 'ui.add_enabled(false, egui::Button::new("Force Transfer — Experimental"));' 'ui.add_enabled(false, egui::Button::new("Force Transfer — validation required"));'
Replace-Required $p 'LOCKED: full FM27 membership chain not verified yet — no partial pointer writes allowed.' 'VALIDATION GATE: destination team is mapped; squad/contract membership must pass live read-back before Force Transfer unlocks.'

Write-Host 'Element v1.4 premium dense player page applied.'
