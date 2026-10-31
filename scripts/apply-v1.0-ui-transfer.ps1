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
    // Element v1.5 premium player hero: compact FMRTE-inspired information density.
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
        egui::Frame::none().fill(egui::Color32::from_rgb(31, 42, 61)).rounding(egui::Rounding::same(5))
            .inner_margin(egui::Margin::symmetric(10, 6)).show(ui, |ui| {
                ui.set_min_width(width); ui.set_max_width(width);
                ui.horizontal(|ui| {
                    ui.label(egui::RichText::new(value).size(15.0).strong().color(egui::Color32::WHITE));
                    ui.label(egui::RichText::new(label).size(8.0).color(egui::Color32::from_rgb(139, 157, 188)));
                });
            });
    };

    egui::Frame::none().fill(egui::Color32::from_rgb(31, 78, 170)).rounding(egui::Rounding::same(4))
        .inner_margin(egui::Margin::symmetric(10, 8)).show(ui, |ui| {
        ui.horizontal(|ui| {
            egui::Frame::none().fill(egui::Color32::from_rgb(18, 24, 35)).rounding(egui::Rounding::same(4)).inner_margin(egui::Margin::same(2)).show(ui, |ui| {
                let mut rendered = false;
                if let Some(img_path) = resolved_face_file.as_ref() { if let Ok(bytes) = std::fs::read(img_path) { if let Ok(decoded) = image::load_from_memory(&bytes) {
                    let rgba = decoded.to_rgba8(); let size=[rgba.width() as usize, rgba.height() as usize];
                    let ci=egui::ColorImage::from_rgba_unmultiplied(size,rgba.as_raw());
                    let tex=ui.ctx().load_texture(format!("element_face_{}",face_uid.unwrap_or(0)),ci,egui::TextureOptions::LINEAR);
                    ui.add(egui::Image::new(&tex).fit_to_exact_size(egui::vec2(64.0,64.0))); rendered=true;
                } } }
                if !rendered { ui.allocate_ui(egui::vec2(64.0,64.0),|ui|{ui.centered_and_justified(|ui|{ui.label("NO FACE");});}); }
            });
            ui.add_space(8.0);
            ui.vertical(|ui| {
                ui.label(egui::RichText::new(player.name.as_deref().unwrap_or("Unknown")).size(22.0).strong().color(egui::Color32::WHITE));
                ui.horizontal(|ui| {
                    ui.label(egui::RichText::new(player.club_name.as_deref().unwrap_or("No club")).size(11.0).strong().color(egui::Color32::from_rgb(235,241,255)));
                    if let Some(n)=player.nationality.as_deref(){ui.label(egui::RichText::new(format!(" / {n}")).size(11.0).color(egui::Color32::from_rgb(205,219,248)));}
                });
                if let Some(uid)=face_uid { ui.label(egui::RichText::new(format!("UID {uid}")).size(8.0).color(egui::Color32::from_rgb(180,204,250))); }
            });
            ui.with_layout(egui::Layout::right_to_left(egui::Align::Center), |ui| {
                metric(ui,"WAGE",&wage,125.0); ui.add_space(5.0); metric(ui,"ASKING",&asking,128.0); ui.add_space(5.0);
                metric(ui,"REP",&rep,88.0); ui.add_space(5.0); metric(ui,"APPS",&apps,70.0); ui.add_space(5.0);
                metric(ui,"PA",&pa,62.0); ui.add_space(5.0); metric(ui,"CA",&ca,62.0);
            });
        });
    });
    ui.add_space(6.0);

'@
$text = $text.Substring(0,$start) + $newHero + $text.Substring($end)
[IO.File]::WriteAllText((Join-Path $SourceRoot $p), $text, [Text.UTF8Encoding]::new($false))

# The entity navigation now lives in the contextual left rail, so remove the duplicate horizontal tabs.
Replace-Required $p @'
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
'@ @'
    // Navigation is rendered in the contextual application rail (Element v1.5).
'@

Replace-Required $p 'ui.add_enabled(false, egui::Button::new("Force Transfer — Experimental"));' 'ui.add_enabled(false, egui::Button::new("Force Transfer — validation required"));'
Replace-Required $p 'LOCKED: full FM27 membership chain not verified yet — no partial pointer writes allowed.' 'VALIDATION GATE: destination team is mapped; squad/contract membership must pass live read-back before Force Transfer unlocks.'

# ----- Application shell v1.5: top search, no redundant blue banner, contextual player rail -----
$a = 'src/app.rs'
$ap = Join-Path $SourceRoot $a
$app = [IO.File]::ReadAllText($ap)

# Remove the redundant workspace banner to reclaim vertical space.
$bannerStart = $app.IndexOf('        // ===== Element blue workspace banner =====')
$railStart = $app.IndexOf('        // ===== Element navigation rail =====', $bannerStart)
if ($bannerStart -lt 0 -or $railStart -lt 0) { throw 'Element banner/rail markers not found in app.rs' }
$app = $app.Substring(0,$bannerStart) + $app.Substring($railStart)
[IO.File]::WriteAllText($ap, $app, [Text.UTF8Encoding]::new($false))

# Put a real, live player search in the top command bar. Typing returns to player results.
Replace-Required $a @'
                        ui.label(egui::RichText::new("LIVE MEMORY EDITOR").small().color(egui::Color32::from_rgb(138,148,168)));
'@ @'
                        ui.label(egui::RichText::new("LIVE MEMORY EDITOR").small().color(egui::Color32::from_rgb(138,148,168)));
                        ui.add_space(8.0);
                        let search = ui.add_sized([250.0, 27.0], egui::TextEdit::singleline(&mut self.player_search.query).hint_text("Search player name / UID…"));
                        if search.changed() {
                            self.active_page = Page::PlayerSearch;
                            self.active_tab = None;
                            nav_page_clicked = true;
                        }
'@

# Replace the generic navigation rail with a contextual player navigator whenever a player is open.
$app = [IO.File]::ReadAllText($ap)
$sideStart = $app.IndexOf('        // ===== Element navigation rail =====')
$sideEnd = $app.IndexOf('        // ===== Status Bar =====', $sideStart)
if ($sideStart -lt 0 -or $sideEnd -lt 0) { throw 'Element sidebar markers not found for v1.5' }
$newSidebar = @'
        // ===== Element contextual navigation rail =====
        egui::SidePanel::left("element_sidebar")
            .default_width(172.0).min_width(164.0).max_width(190.0)
            .frame(egui::Frame::none().fill(egui::Color32::from_rgb(18,22,31)).inner_margin(egui::Margin::symmetric(8,10)))
            .show(ctx, |ui| {
                let player_open = self.active_page == Page::PlayerSearch && self.selected_player.is_some() && self.active_tab.is_some();
                if player_open {
                    ui.label(egui::RichText::new("PLAYER").size(9.0).strong().color(egui::Color32::from_rgb(112,130,158)));
                    ui.add_space(5.0);
                    let nav = |ui: &mut egui::Ui, selected: bool, label: &str| -> bool {
                        ui.add_sized([ui.available_width(), 25.0], egui::Button::new(egui::RichText::new(label).size(11.0).color(if selected { egui::Color32::WHITE } else { egui::Color32::from_rgb(190,199,216) }))
                            .fill(if selected { egui::Color32::from_rgb(33,96,224) } else { egui::Color32::TRANSPARENT }).rounding(egui::Rounding::same(3))).clicked()
                    };
                    if nav(ui, self.player_tab == player_panel::PlayerTab::Overview, "▣  Information") { self.player_tab = player_panel::PlayerTab::Overview; }
                    ui.add_enabled(false, egui::Button::new("▥  Stats"));
                    ui.add_enabled(false, egui::Button::new("⇄  Comparison"));
                    if player_open && nav(ui, self.player_tab == player_panel::PlayerTab::Contract, "▤  Contract") { self.player_tab = player_panel::PlayerTab::Contract; }
                    ui.add_enabled(false, egui::Button::new("◎  Career Plans"));
                    ui.add_enabled(false, egui::Button::new("⧉  Clone Player"));
                    if nav(ui, self.player_tab == player_panel::PlayerTab::TransferLab, "→  Move to Club") { self.player_tab = player_panel::PlayerTab::TransferLab; }
                    ui.add_enabled(false, egui::Button::new("⚡  Force Transfer"));
                    ui.add_enabled(false, egui::Button::new("◷  Future Transfer"));
                    ui.add_enabled(false, egui::Button::new("✚  Injury"));
                    ui.add_enabled(false, egui::Button::new("▧  Work Permit"));
                    ui.add_enabled(false, egui::Button::new("✓  Promises"));
                    ui.add_enabled(false, egui::Button::new("⊘  Unavailability"));
                    ui.add_enabled(false, egui::Button::new("⇆  Transfer Proposals"));
                    if nav(ui, self.player_tab == player_panel::PlayerTab::PositionsTraits, "⌖  Positions & Traits") { self.player_tab = player_panel::PlayerTab::PositionsTraits; }
                    ui.add_enabled(false, egui::Button::new("★  Preferred Moves"));
                    ui.add_enabled(false, egui::Button::new("♟  Relationships"));
                    ui.add_enabled(false, egui::Button::new("A  Languages"));
                    ui.add_enabled(false, egui::Button::new("⌕  Scout Information"));
                    ui.add_space(8.0); ui.separator(); ui.add_space(6.0);
                    if ui.button("← Back to Players").clicked() { self.active_tab = None; self.active_page = Page::PlayerSearch; nav_page_clicked = true; }
                } else {
                    ui.label(egui::RichText::new("NAVIGATION").small().strong().color(egui::Color32::from_rgb(138,148,168)));
                    ui.add_space(7.0);
                    for (page, label) in [(Page::HumanManager,"Home / Manager"),(Page::PlayerSearch,"Players"),(Page::StaffSearch,"Staff"),(Page::ClubSearch,"Clubs")] {
                        let selected=self.active_page==page;
                        if ui.add_sized([ui.available_width(),31.0],egui::Button::new(label).fill(if selected{egui::Color32::from_rgb(33,96,224)}else{egui::Color32::TRANSPARENT})).clicked(){self.active_page=page;nav_page_clicked=true;}
                    }
                    ui.add_space(12.0); ui.separator(); ui.add_space(8.0);
                    ui.label(egui::RichText::new("TOOLS").small().strong().color(egui::Color32::from_rgb(138,148,168)));
                    ui.add_enabled(false,egui::Button::new("★ Favorites")); ui.add_enabled(false,egui::Button::new("≡ Shortlists"));
                    ui.add_enabled(false,egui::Button::new("⚡ Mass Edit")); ui.add_enabled(false,egui::Button::new("❄ Freezer"));
                }
                ui.with_layout(egui::Layout::bottom_up(egui::Align::LEFT), |ui| {
                    ui.checkbox(&mut self.auto_connect,"Auto-connect");
                    match self.conn { ConnState::Ready(_) => {ui.colored_label(egui::Color32::from_rgb(31,157,74),"● Connected to FM27");}, ConnState::WaitingForSave(_) => {ui.colored_label(egui::Color32::from_rgb(201,162,39),"● Waiting for save");}, ConnState::ReadOnly(_) => {ui.colored_label(egui::Color32::from_rgb(201,162,39),"● Browse only");}, ConnState::Disconnected => {ui.colored_label(egui::Color32::from_rgb(217,58,58),"● Disconnected");} }
                });
            });

'@
$app = $app.Substring(0,$sideStart) + $newSidebar + $app.Substring($sideEnd)
[IO.File]::WriteAllText($ap, $app, [Text.UTF8Encoding]::new($false))

Write-Host 'Element v1.5 premium contextual player navigation + top search applied.'
