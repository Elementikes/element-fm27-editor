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

# v0.9 changes the actual application shell in app.rs rather than merely
# recolouring detail panels. The proven bridge/memory backend is untouched.
$a = 'src/app.rs'

Replace-Required $a @'
        // ===== Menu bar =====
        egui::TopBottomPanel::top("menu_bar").show(ctx, |ui| {
            egui::menu::bar(ui, |ui| {
                ui.menu_button("File", |ui| {
                    if ui.button("Load Save").clicked() {
                        reload_save_clicked = true;
                        ui.close_menu();
                    }
                    ui.separator();
                    if ui.button("Quit").clicked() {
                        ctx.send_viewport_cmd(egui::ViewportCommand::Close);
                    }
                });

                ui.menu_button("Settings", |ui| {
                    ui.menu_button("Theme", |ui| {
                        for theme in [Theme::Dark, Theme::Light, Theme::DarkBlue] {
                            if ui
                                .selectable_label(self.settings.theme == theme, theme.label())
                                .clicked()
                            {
                                self.settings.theme = theme;
                                ctx.set_visuals(theme.visuals());
                                self.settings.save();
                                ui.close_menu();
                            }
                        }
                    });
                    ui.menu_button("Scale", |ui| {
                        let mut idx = self.settings.scale.to_index() as i32;
                        let labels = ["100%", "125%", "150%"];
                        ui.label(labels[idx as usize]);
                        if ui
                            .add(egui::Slider::new(&mut idx, 0..=2).show_value(false))
                            .changed()
                        {
                            let new_scale = Scale::from_index(idx as u8);
                            self.settings.scale = new_scale;
                            let f = new_scale.zoom_factor();
                            ctx.set_zoom_factor(f);
                            self.pending_scale_resize = Some(f);
                            self.settings.save();
                        }
                    });
                    ui.menu_button("Wage Display", |ui| {
                        for period in [WagePeriod::Weekly, WagePeriod::Monthly, WagePeriod::Yearly]
                        {
                            if ui
                                .selectable_label(
                                    self.settings.wage_period == period,
                                    period.label(),
                                )
                                .clicked()
                            {
                                self.settings.wage_period = period;
                                self.settings.save();
                                ui.close_menu();
                            }
                        }
                    });
                    ui.separator();
                    let mut rts = self.settings.reload_on_tab_switch;
                    if ui.checkbox(&mut rts, "Reload on tab switch").changed() {
                        self.settings.reload_on_tab_switch = rts;
                        self.settings.save();
                    }
                    ui.menu_button("Face Pack", |ui| {
                        let current = self.settings.face_pack_path.as_deref().unwrap_or("(none)");
                        ui.label(current);
                        if ui.button("Set path\u{2026}").clicked() {
                            if let Some(path) = rfd::FileDialog::new().pick_folder() {
                                self.settings.face_pack_path =
                                    Some(path.to_string_lossy().into_owned());
                                self.settings.save();
                            }
                            ui.close_menu();
                        }
                        if self.settings.face_pack_path.is_some() && ui.button("Clear").clicked() {
                            self.settings.face_pack_path = None;
                            self.settings.save();
                            ui.close_menu();
                        }
                    });
                });
            });
        });
'@ @'
        // ===== Element command bar =====
        egui::TopBottomPanel::top("element_command_bar")
            .frame(egui::Frame::none()
                .fill(egui::Color32::from_rgb(11, 14, 20))
                .inner_margin(egui::Margin::symmetric(12, 8)))
            .show(ctx, |ui| {
                ui.horizontal(|ui| {
                    ui.label(egui::RichText::new("ELEMENT").size(20.0).strong().color(egui::Color32::from_rgb(232,236,244)));
                    ui.label(egui::RichText::new("FM27 EDITOR").size(12.0).strong().color(egui::Color32::from_rgb(33,96,224)));
                    ui.separator();
                    if ui.button("⌂ Home").clicked() { self.active_page = Page::HumanManager; nav_page_clicked = true; }
                    if ui.add_enabled(self.can_nav_back(), egui::Button::new("←")).clicked() { nav_back_clicked = true; }
                    if ui.add_enabled(self.can_nav_forward(), egui::Button::new("→")).clicked() { nav_forward_clicked = true; }
                    if ui.add_enabled(self.active_tab.is_some() || self.manager_view.is_some(), egui::Button::new("↻ Reload")).clicked() { nav_reload_clicked = true; }
                    if ui.add_enabled(self.conn.is_writable() && !self.writes.is_pending() && !self.undo_stack.is_empty(), egui::Button::new(format!("↶ Undo {}", self.undo_stack.len()))).clicked() { undo_requested = true; }
                    ui.separator();
                    if ui.selectable_label(self.active_page == Page::PlayerSearch, "Players").clicked() { self.active_page = Page::PlayerSearch; nav_page_clicked = true; }
                    if ui.selectable_label(self.active_page == Page::StaffSearch, "Staff").clicked() { self.active_page = Page::StaffSearch; nav_page_clicked = true; }
                    if ui.selectable_label(self.active_page == Page::ClubSearch, "Clubs").clicked() { self.active_page = Page::ClubSearch; nav_page_clicked = true; }
                    ui.with_layout(egui::Layout::right_to_left(egui::Align::Center), |ui| {
                        let load = egui::Button::new(egui::RichText::new("LOAD GAME").strong().color(egui::Color32::WHITE))
                            .fill(egui::Color32::from_rgb(230,0,126));
                        if ui.add(load).clicked() { attach_requested = true; }
                        ui.label(egui::RichText::new("LIVE MEMORY EDITOR").small().color(egui::Color32::from_rgb(138,148,168)));
                    });
                });
            });

        // ===== Element blue workspace banner =====
        egui::TopBottomPanel::top("element_workspace_banner")
            .frame(egui::Frame::none().fill(egui::Color32::from_rgb(33,96,224)).inner_margin(egui::Margin::symmetric(14,7)))
            .show(ctx, |ui| {
                ui.horizontal(|ui| {
                    let section = match self.active_page { Page::PlayerSearch => "PLAYERS", Page::StaffSearch => "STAFF", Page::ClubSearch => "CLUBS", Page::HumanManager => "HUMAN MANAGER" };
                    ui.label(egui::RichText::new(section).size(14.0).strong().color(egui::Color32::WHITE));
                    ui.with_layout(egui::Layout::right_to_left(egui::Align::Center), |ui| {
                        ui.label(egui::RichText::new("Element Workspace").small().color(egui::Color32::from_rgb(220,230,255)));
                    });
                });
            });
'@

# Replace the whole visible sidebar body with an editor navigation rail.
$path = Join-Path $SourceRoot $a
$text = [IO.File]::ReadAllText($path)
$start = $text.IndexOf('        // ===== Sidebar =====')
$end = $text.IndexOf('        // ===== Status Bar =====', $start)
if ($start -lt 0 -or $end -lt 0) { throw 'Could not locate sidebar block in src/app.rs' }
$newSidebar = @'
        // ===== Element navigation rail =====
        egui::SidePanel::left("element_sidebar")
            .default_width(190.0)
            .min_width(180.0)
            .frame(egui::Frame::none().fill(egui::Color32::from_rgb(20,24,33)).inner_margin(egui::Margin::symmetric(10,12)))
            .show(ctx, |ui| {
                ui.label(egui::RichText::new("NAVIGATION").small().strong().color(egui::Color32::from_rgb(138,148,168)));
                ui.add_space(8.0);
                for (page, icon, label) in [
                    (Page::HumanManager, "◆", "Home / Manager"),
                    (Page::PlayerSearch, "●", "Players"),
                    (Page::StaffSearch, "■", "Staff"),
                    (Page::ClubSearch, "▲", "Clubs"),
                ] {
                    let selected = self.active_page == page;
                    let text = egui::RichText::new(format!("{icon}   {label}")).size(13.0)
                        .color(if selected { egui::Color32::WHITE } else { egui::Color32::from_rgb(180,188,204) });
                    let button = egui::Button::new(text)
                        .fill(if selected { egui::Color32::from_rgb(33,96,224) } else { egui::Color32::TRANSPARENT })
                        .rounding(egui::Rounding::same(5));
                    if ui.add_sized([ui.available_width(), 34.0], button).clicked() {
                        self.active_page = page;
                        nav_page_clicked = true;
                    }
                }
                ui.add_space(16.0);
                ui.separator();
                ui.add_space(10.0);
                ui.label(egui::RichText::new("TOOLS").small().strong().color(egui::Color32::from_rgb(138,148,168)));
                ui.add_enabled(false, egui::Button::new("★   Favorites"));
                ui.add_enabled(false, egui::Button::new("≡   Shortlists"));
                ui.add_enabled(false, egui::Button::new("⚡   Mass Edit"));
                ui.add_enabled(false, egui::Button::new("❄   Freezer"));
                ui.add_space(16.0);
                ui.separator();
                ui.add_space(10.0);
                ui.label(egui::RichText::new("GAME STATUS").small().strong().color(egui::Color32::from_rgb(138,148,168)));
                match self.conn {
                    ConnState::Ready(_) => { ui.colored_label(egui::Color32::from_rgb(31,157,74), "● Connected to FM27"); }
                    ConnState::WaitingForSave(_) => { ui.colored_label(egui::Color32::from_rgb(201,162,39), "● Waiting for save"); }
                    ConnState::ReadOnly(_) => { ui.colored_label(egui::Color32::from_rgb(201,162,39), "● Browse only"); }
                    ConnState::Disconnected => { ui.colored_label(egui::Color32::from_rgb(217,58,58), "● Disconnected"); }
                }
                if matches!(self.conn, ConnState::Disconnected | ConnState::ReadOnly(_)) {
                    if ui.add_sized([ui.available_width(), 30.0], egui::Button::new("Load / Reconnect Game")).clicked() { attach_requested = true; }
                }
                ui.checkbox(&mut self.auto_connect, "Auto-connect");
            });

'@
$text = $text.Substring(0, $start) + $newSidebar + $text.Substring($end)
[IO.File]::WriteAllText($path, $text, [Text.UTF8Encoding]::new($false))

# Make the central workspace visually independent from upstream defaults.
Replace-Required $a @'
        egui::CentralPanel::default().show(ctx, |ui| {
'@ @'
        egui::CentralPanel::default()
            .frame(egui::Frame::none().fill(egui::Color32::from_rgb(20,24,33)).inner_margin(egui::Margin::symmetric(14,12)))
            .show(ctx, |ui| {
'@

# Main executable title/size.
Replace-Required 'src/main.rs' 'Some(b) => format!("FM Editor [{b}]"),' 'Some(b) => format!("Element FM27 Editor [{b}]"),'
Replace-Required 'src/main.rs' 'None => "FM Editor".to_string(),' 'None => "Element FM27 Editor".to_string(),'
Replace-Required 'src/main.rs' '.with_inner_size([1280.0 * f, 800.0 * f])' '.with_inner_size([1440.0 * f, 900.0 * f])'
Replace-Required 'src/main.rs' '        "FM Editor",' '        "Element FM27 Editor",'

Write-Host 'Element v0.9 REAL application-shell rebuild applied successfully.'
