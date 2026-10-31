from pathlib import Path

root = Path.cwd()
p = root / "src" / "ui" / "club_panel.rs"
t = p.read_text(encoding="utf-8")

needle = '''    ui.add_space(3.0);\n\n    let mut overview_records = 0usize;\n'''
block = r'''    ui.add_space(3.0);

    // Element v6.2.5 — FMRTE semantic certification workspace, directly in
    // Club -> Tactical Knowledge. This is intentionally read-only until the
    // seven semantic axes are cross-witnessed against FM27.
    egui::Frame::none()
        .fill(egui::Color32::from_rgb(19, 25, 37))
        .stroke(egui::Stroke::new(1.0, egui::Color32::from_rgb(67, 84, 112)))
        .inner_margin(egui::Margin::symmetric(10, 8))
        .show(ui, |ui| {
            ui.horizontal_wrapped(|ui| {
                ui.label(egui::RichText::new("v6.2.5 • TACTICAL UNDERSTANDING CERTIFIER").strong().size(10.0));
                ui.separator();
                ui.label(egui::RichText::new("FMRTE27 SEMANTIC WITNESS").size(8.0).color(egui::Color32::from_rgb(112, 177, 255)));
                ui.separator();
                ui.label(egui::RichText::new("READ-ONLY UNTIL 7/7").size(8.0).strong().color(egui::Color32::from_rgb(255, 184, 77)));
            });
            ui.add_space(4.0);
            ui.horizontal_wrapped(|ui| {
                ui.label(egui::RichText::new("Squad:").strong());
                ui.label(egui::RichText::new("FIRST TEAM").strong().color(egui::Color32::from_rgb(88, 214, 141)));
                ui.separator();
                ui.label(egui::RichText::new("U19 • scope mapping pending").small().weak());
                ui.separator();
                ui.label(egui::RichText::new("B TEAM • scope mapping pending").small().weak());
            });

            ui.add_space(5.0);
            egui::Grid::new(format!("element_v625_tactical_axes_{}", club.addr))
                .num_columns(3)
                .striped(true)
                .spacing([12.0, 3.0])
                .show(ui, |ui| {
                    ui.strong("FM27 axis"); ui.strong("Target"); ui.strong("Mapping"); ui.end_row();
                    for axis in [
                        "Passing Style", "Build Up", "Chance Creation",
                        "Line of Engagement", "Pressing Intensity", "Pressing Trap", "Position/Role",
                    ] {
                        ui.label(axis);
                        ui.label("100");
                        ui.label(egui::RichText::new("WITNESS REQUIRED").small().color(egui::Color32::from_rgb(255, 184, 77)));
                        ui.end_row();
                    }
                });

            let snapshot_id = egui::Id::new(("element_v625_tactical_snapshot", club.addr));
            let compare_id = egui::Id::new(("element_v625_tactical_compare", club.addr));
            let current_lines: Vec<String> = report.map(|r| r.candidate_lines.clone()).unwrap_or_default();
            let has_snapshot = ui.ctx().data(|d| d.get_temp::<Vec<String>>(snapshot_id).is_some());

            ui.add_space(6.0);
            ui.horizontal_wrapped(|ui| {
                if ui.add_enabled(!current_lines.is_empty(), egui::Button::new("① CAPTURE CURRENT STATE")).clicked() {
                    ui.ctx().data_mut(|d| {
                        d.insert_temp(snapshot_id, current_lines.clone());
                        d.insert_temp(compare_id, Vec::<String>::new());
                    });
                }
                if ui.add_enabled(has_snapshot && !current_lines.is_empty(), egui::Button::new("② COMPARE AFTER FMRTE MAX")).clicked() {
                    let before = ui.ctx().data(|d| d.get_temp::<Vec<String>>(snapshot_id));
                    if let Some(before) = before {
                        let mut delta = Vec::new();
                        let max_len = before.len().max(current_lines.len());
                        for i in 0..max_len {
                            let a = before.get(i).map(String::as_str).unwrap_or("<missing>");
                            let b = current_lines.get(i).map(String::as_str).unwrap_or("<missing>");
                            if a != b {
                                delta.push(format!("#{i}: {a}  ->  {b}"));
                            }
                        }
                        ui.ctx().data_mut(|d| d.insert_temp(compare_id, delta));
                    }
                }
                ui.add_enabled(false, egui::Button::new("MAX CURRENT SQUAD • 100"));
                ui.add_enabled(false, egui::Button::new("MAX ALL SQUADS • 100"));
            });

            let captured = ui.ctx().data(|d| d.get_temp::<Vec<String>>(snapshot_id));
            let delta = ui.ctx().data(|d| d.get_temp::<Vec<String>>(compare_id));
            ui.horizontal_wrapped(|ui| {
                ui.label(egui::RichText::new(if captured.is_some() { "SNAPSHOT: READY" } else { "SNAPSHOT: NOT CAPTURED" }).small().strong().color(
                    if captured.is_some() { egui::Color32::from_rgb(88, 214, 141) } else { egui::Color32::from_rgb(139, 157, 188) }
                ));
                ui.separator();
                if let Some(ref rows) = delta {
                    ui.label(egui::RichText::new(format!("DELTA: {} changed report lines", rows.len())).small().strong().color(
                        if rows.is_empty() { egui::Color32::from_rgb(255, 184, 77) } else { egui::Color32::from_rgb(112, 177, 255) }
                    ));
                } else {
                    ui.label(egui::RichText::new("DELTA: waiting").small().weak());
                }
            });
            if let Some(rows) = delta {
                if !rows.is_empty() {
                    egui::CollapsingHeader::new(format!("Changed tactical records ({})", rows.len())).default_open(true).show(ui, |ui| {
                        for row in rows.iter().take(18) {
                            ui.label(egui::RichText::new(row).monospace().small());
                        }
                        if rows.len() > 18 { ui.label(egui::RichText::new(format!("… {} more", rows.len() - 18)).small().weak()); }
                    });
                }
            }
            ui.label(egui::RichText::new("TEST: Capture here → in FMRTE use Max Tactical Familiarity for Barcelona First Team → return to Element, click Refresh live data → Compare. MAX buttons unlock only after the seven semantic fields are certified and read-back safe.").small().weak());
        });

    ui.add_space(5.0);

    let mut overview_records = 0usize;
'''

if "v6.2.5 • TACTICAL UNDERSTANDING CERTIFIER" not in t:
    if needle not in t:
        raise SystemExit("v6.2.5: tactical viewer insertion marker missing")
    t = t.replace(needle, block, 1)

p.write_text(t, encoding="utf-8")
print("Element v6.2.5 club tactical certifier UI applied successfully.")
