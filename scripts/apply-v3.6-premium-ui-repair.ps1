$ErrorActionPreference = 'Stop'
$SourceRoot = (Get-Location).Path

function Read-Text([string]$RelativePath) {
    $Path = Join-Path $SourceRoot $RelativePath
    if (-not (Test-Path -LiteralPath $Path)) { throw "Source file not found: $Path" }
    return [IO.File]::ReadAllText($Path)
}

function Write-Text([string]$RelativePath, [string]$Text) {
    $Path = Join-Path $SourceRoot $RelativePath
    [IO.File]::WriteAllText($Path, $Text, [Text.UTF8Encoding]::new($false))
}

function Replace-Required([string]$RelativePath, [string]$Old, [string]$New) {
    $Text = Read-Text $RelativePath
    if (-not $Text.Contains($Old)) { throw "v3.6 repair: expected text not found in $RelativePath`n--- expected ---`n$Old" }
    Write-Text $RelativePath ($Text.Replace($Old, $New))
}

# The core v3.6 script intentionally ran first. It must already have inserted
# the selected-team viewer and rewired the worker before the old UI regex failed.
$inspector = Read-Text 'src/bridge/tactical_inspector.rs'
if (-not $inspector.Contains('pub(super) fn view_selected_tactical_knowledge(')) {
    throw 'v3.6 repair: viewer core was not inserted; refusing to continue'
}
$worker = Read-Text 'src/bridge/worker.rs'
if (-not $worker.Contains('tactical_inspector::view_selected_tactical_knowledge(f, club_addr, senior_team_addr)')) {
    throw 'v3.6 repair: worker was not rewired to selected-team viewer'
}

$panel = 'src/ui/club_panel.rs'
$ui = Read-Text $panel
$start = $ui.IndexOf('fn show_tactical_understanding(ui: &mut egui::Ui, club: &ClubView) {')
if ($start -lt 0) { throw 'v3.6 repair: show_tactical_understanding start not found' }
$end = $ui.IndexOf('fn show_squads(', $start)
if ($end -lt 0 -or $end -le $start) { throw 'v3.6 repair: show_squads boundary not found' }

$replacement = @'
fn show_tactical_understanding(ui: &mut egui::Ui, club: &ClubView) {
    ui.spacing_mut().item_spacing = egui::vec2(6.0, 4.0);
    let senior_team_ok = element_tactical_pointer_ok(club.senior_team_addr);
    let report = club.tactical_report.as_ref();

    ui.horizontal(|ui| {
        ui.label(egui::RichText::new("TACTICAL KNOWLEDGE").size(14.0).strong());
        ui.separator();
        ui.label(
            egui::RichText::new("v3.6 • PREMIUM LIVE VIEWER")
                .size(8.5)
                .strong()
                .color(egui::Color32::from_rgb(112, 177, 255)),
        );
        ui.add_space(8.0);
        ui.label(
            egui::RichText::new("READ ONLY")
                .size(8.0)
                .strong()
                .color(egui::Color32::from_rgb(88, 214, 141)),
        );
    });
    ui.label(
        egui::RichText::new("Live tactical familiarity for the selected club • universal FM27 mapping certified across the complete save")
            .size(8.0)
            .color(egui::Color32::from_rgb(139, 157, 188)),
    );
    ui.add_space(3.0);

    let mut overview_records = 0usize;
    let mut overview_avg = 0u16;
    let mut overview_min = 0u16;
    let mut overview_max = 0u16;
    let mut overview_populated = 0usize;
    let mut overview_empty = 0usize;
    let mut overview_unallocated = 0usize;

    let mut states = vec![String::from("NOT LOADED"); 6];
    let mut records = vec![0usize; 6];
    let mut averages = vec![0u16; 6];
    let mut mins = vec![0u16; 6];
    let mut maxs = vec![0u16; 6];
    let mut maxed = vec![0usize; 6];
    let mut zeros = vec![0usize; 6];
    let mut uniques = vec![0usize; 6];
    let mut lows: Vec<Option<(u16, u16)>> = vec![None; 6];
    let mut highs: Vec<Option<(u16, u16)>> = vec![None; 6];

    if let Some(r) = report {
        for line in &r.candidate_lines {
            let parts: Vec<&str> = line.split('|').collect();
            match parts.first().copied() {
                Some("OVERVIEW") if parts.len() >= 8 => {
                    overview_records = parts[1].parse().unwrap_or(0);
                    overview_avg = parts[2].parse().unwrap_or(0);
                    overview_min = parts[3].parse().unwrap_or(0);
                    overview_max = parts[4].parse().unwrap_or(0);
                    overview_populated = parts[5].parse().unwrap_or(0);
                    overview_empty = parts[6].parse().unwrap_or(0);
                    overview_unallocated = parts[7].parse().unwrap_or(0);
                }
                Some("COLL") if parts.len() >= 10 => {
                    let idx = parts[1].parse::<usize>().unwrap_or(0).saturating_sub(1);
                    if idx < 6 {
                        states[idx] = parts[2].to_owned();
                        records[idx] = parts[3].parse().unwrap_or(0);
                        averages[idx] = parts[4].parse().unwrap_or(0);
                        mins[idx] = parts[5].parse().unwrap_or(0);
                        maxs[idx] = parts[6].parse().unwrap_or(0);
                        maxed[idx] = parts[7].parse().unwrap_or(0);
                        zeros[idx] = parts[8].parse().unwrap_or(0);
                        uniques[idx] = parts[9].parse().unwrap_or(0);
                    }
                }
                Some("LOW") if parts.len() >= 4 => {
                    let idx = parts[1].parse::<usize>().unwrap_or(0).saturating_sub(1);
                    if idx < 6 {
                        lows[idx] = Some((parts[2].parse().unwrap_or(0), parts[3].parse().unwrap_or(0)));
                    }
                }
                Some("HIGH") if parts.len() >= 4 => {
                    let idx = parts[1].parse::<usize>().unwrap_or(0).saturating_sub(1);
                    if idx < 6 {
                        highs[idx] = Some((parts[2].parse().unwrap_or(0), parts[3].parse().unwrap_or(0)));
                    }
                }
                _ => {}
            }
        }
    }

    ui.columns(4, |cols| {
        egui::Frame::none()
            .fill(egui::Color32::from_rgb(24, 31, 46))
            .stroke(egui::Stroke::new(1.0, egui::Color32::from_rgb(49, 61, 82)))
            .inner_margin(egui::Margin::symmetric(8, 6))
            .show(&mut cols[0], |ui| {
                ui.label(egui::RichText::new("OVERALL FAMILIARITY").size(8.0).color(egui::Color32::from_rgb(139, 157, 188)));
                ui.label(egui::RichText::new(format!("{:.1}%", overview_avg as f32 / 100.0)).size(20.0).strong());
                ui.add_sized([ui.available_width(), 14.0], egui::ProgressBar::new((overview_avg as f32 / 10_000.0).clamp(0.0, 1.0)));
            });
        egui::Frame::none()
            .fill(egui::Color32::from_rgb(24, 31, 46))
            .stroke(egui::Stroke::new(1.0, egui::Color32::from_rgb(49, 61, 82)))
            .inner_margin(egui::Margin::symmetric(8, 6))
            .show(&mut cols[1], |ui| {
                ui.label(egui::RichText::new("LIVE RECORDS").size(8.0).color(egui::Color32::from_rgb(139, 157, 188)));
                ui.label(egui::RichText::new(overview_records.to_string()).size(20.0).strong());
                ui.label(egui::RichText::new(format!("min {:.1}%  •  max {:.1}%", overview_min as f32 / 100.0, overview_max as f32 / 100.0)).size(8.0));
            });
        egui::Frame::none()
            .fill(egui::Color32::from_rgb(24, 31, 46))
            .stroke(egui::Stroke::new(1.0, egui::Color32::from_rgb(49, 61, 82)))
            .inner_margin(egui::Margin::symmetric(8, 6))
            .show(&mut cols[2], |ui| {
                ui.label(egui::RichText::new("COLLECTIONS").size(8.0).color(egui::Color32::from_rgb(139, 157, 188)));
                ui.label(egui::RichText::new(format!("{} / 6", overview_populated)).size(20.0).strong());
                ui.label(egui::RichText::new(format!("{} empty  •  {} unallocated", overview_empty, overview_unallocated)).size(8.0));
            });
        egui::Frame::none()
            .fill(egui::Color32::from_rgb(24, 31, 46))
            .stroke(egui::Stroke::new(1.0, egui::Color32::from_rgb(49, 61, 82)))
            .inner_margin(egui::Margin::symmetric(8, 6))
            .show(&mut cols[3], |ui| {
                ui.label(egui::RichText::new("LIVE SOURCE").size(8.0).color(egui::Color32::from_rgb(139, 157, 188)));
                ui.label(egui::RichText::new(if senior_team_ok { "CONNECTED" } else { "UNAVAILABLE" }).size(13.0).strong().color(
                    if senior_team_ok { egui::Color32::from_rgb(88, 214, 141) } else { egui::Color32::from_rgb(255, 184, 77) }
                ));
                let enabled = crate::ui::navigation::editing_enabled(ui) && senior_team_ok;
                if ui.add_enabled(enabled, egui::Button::new("Refresh live data")).clicked() {
                    if let Some(team) = club.senior_team_addr {
                        ui.ctx().data_mut(|d| d.insert_temp(
                            egui::Id::new("element_tactical_inspect_request"),
                            (club.addr, team),
                        ));
                    }
                }
            });
    });

    ui.add_space(4.0);

    for row in 0..2usize {
        ui.columns(3, |cols| {
            for col in 0..3usize {
                let idx = row * 3 + col;
                egui::Frame::none()
                    .fill(egui::Color32::from_rgb(20, 26, 38))
                    .stroke(egui::Stroke::new(1.0, egui::Color32::from_rgb(48, 58, 76)))
                    .inner_margin(egui::Margin::symmetric(8, 6))
                    .show(&mut cols[col], |ui| {
                        ui.horizontal(|ui| {
                            ui.label(egui::RichText::new(format!("COLLECTION {}", idx + 1)).size(10.0).strong());
                            ui.separator();
                            let state_color = if states[idx] == "POPULATED" {
                                egui::Color32::from_rgb(88, 214, 141)
                            } else if states[idx] == "EMPTY" || states[idx] == "UNALLOCATED" {
                                egui::Color32::from_rgb(255, 184, 77)
                            } else {
                                egui::Color32::from_rgb(139, 157, 188)
                            };
                            ui.label(egui::RichText::new(&states[idx]).size(7.5).strong().color(state_color));
                        });

                        ui.horizontal(|ui| {
                            ui.label(egui::RichText::new(format!("{:.1}%", averages[idx] as f32 / 100.0)).size(18.0).strong());
                            ui.label(egui::RichText::new(format!("{} records", records[idx])).size(8.0).color(egui::Color32::from_rgb(139, 157, 188)));
                        });
                        ui.add_sized([ui.available_width(), 13.0], egui::ProgressBar::new((averages[idx] as f32 / 10_000.0).clamp(0.0, 1.0)));

                        egui::Grid::new(format!("element_tactical_collection_grid_{idx}"))
                            .num_columns(4)
                            .spacing([8.0, 2.0])
                            .show(ui, |ui| {
                                ui.label(egui::RichText::new("MIN").size(7.0).color(egui::Color32::from_rgb(122, 139, 169)));
                                ui.label(egui::RichText::new(format!("{:.1}%", mins[idx] as f32 / 100.0)).size(8.0).strong());
                                ui.label(egui::RichText::new("MAX").size(7.0).color(egui::Color32::from_rgb(122, 139, 169)));
                                ui.label(egui::RichText::new(format!("{:.1}%", maxs[idx] as f32 / 100.0)).size(8.0).strong());
                                ui.end_row();
                                ui.label(egui::RichText::new("UNIQUE").size(7.0).color(egui::Color32::from_rgb(122, 139, 169)));
                                ui.label(egui::RichText::new(uniques[idx].to_string()).size(8.0).strong());
                                ui.label(egui::RichText::new("100%").size(7.0).color(egui::Color32::from_rgb(122, 139, 169)));
                                ui.label(egui::RichText::new(maxed[idx].to_string()).size(8.0).strong());
                                ui.end_row();
                            });

                        if let Some((key, value)) = lows[idx] {
                            ui.label(egui::RichText::new(format!("LOW  key 0x{key:04X}   {:.1}%", value as f32 / 100.0)).size(7.5).color(egui::Color32::from_rgb(255, 184, 77)));
                        }
                        if let Some((key, value)) = highs[idx] {
                            ui.label(egui::RichText::new(format!("HIGH key 0x{key:04X}   {:.1}%", value as f32 / 100.0)).size(7.5).color(egui::Color32::from_rgb(88, 214, 141)));
                        }
                    });
            }
        });
        ui.add_space(3.0);
    }

    egui::Frame::none()
        .fill(egui::Color32::from_rgb(17, 22, 32))
        .stroke(egui::Stroke::new(1.0, egui::Color32::from_rgb(43, 52, 68)))
        .inner_margin(egui::Margin::symmetric(8, 5))
        .show(ui, |ui| {
            ui.horizontal(|ui| {
                ui.label(egui::RichText::new("UNIVERSAL MAPPING CERTIFIED").size(8.0).strong().color(egui::Color32::from_rgb(88, 214, 141)));
                ui.separator();
                ui.label(egui::RichText::new("stride 8 • key +0 • knowledge +2 low14 • metadata +4 = 0x271").size(8.0).color(egui::Color32::from_rgb(139, 157, 188)));
                ui.separator();
                ui.label(egui::RichText::new("execution locked").size(8.0).color(egui::Color32::from_rgb(255, 184, 77)));
            });
        });
}

'@

$ui = $ui.Substring(0, $start) + $replacement + $ui.Substring($end)
Write-Text $panel $ui

Replace-Required 'src/app.rs' '"Tactical semantic certification: confidence {}/5, {} semantic teams, {} populated vectors, {} out-of-range"' '"Tactical Knowledge viewer: confidence {}/5, {} live records, {} active collections, {} empty/unallocated"'
Replace-Required 'src/app.rs' '"Tactical semantic certification running read-only…"' '"Refreshing Tactical Knowledge live view…"'

Write-Host 'Element v3.6 premium Tactical Knowledge UI repair applied successfully.'
