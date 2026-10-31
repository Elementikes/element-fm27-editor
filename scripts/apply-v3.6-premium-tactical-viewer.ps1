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
    if (-not $Text.Contains($Old)) { throw "v3.6: expected text not found in $RelativePath`n--- expected ---`n$Old" }
    Write-Text $RelativePath ($Text.Replace($Old, $New))
}

# -----------------------------------------------------------------------------
# Element v3.6 — PREMIUM TACTICAL KNOWLEDGE VIEWER
#
# Converts the research/certification workspace into a compact user-facing live
# viewer. Uses only the universally certified canonical mapping from v3.4/v3.5:
#   SeniorTeam +0x30 -> root; six collections at +0x18 + n*0x170
#   records are 8 bytes; knowledge is packed low14 at +2; metadata at +4.
# Read-only. No mutation or write payloads are produced.
# -----------------------------------------------------------------------------

$inspector = 'src/bridge/tactical_inspector.rs'
$text = Read-Text $inspector
if (-not $text.Contains('pub(super) fn certify_semantic_slots_all_clubs(')) {
    throw 'v3.6: v3.5 semantic certification source not found'
}

if (-not $text.Contains('pub(super) fn view_selected_tactical_knowledge(')) {
    $markers = @(
        "#[cfg(test)]`nmod element_final_semantic_cert_tests",
        "#[cfg(test)]`r`nmod element_final_semantic_cert_tests"
    )
    $at = -1
    foreach ($marker in $markers) {
        $at = $text.IndexOf($marker)
        if ($at -ge 0) { break }
    }
    if ($at -lt 0) { throw 'v3.6: v3.5 semantic test boundary not found' }

    $viewerCode = @'
fn tactical_viewer_pct(value: u16) -> f32 {
    (value as f32 / 100.0).clamp(0.0, 100.0)
}

pub(super) fn view_selected_tactical_knowledge(
    fm: &FmProcess,
    selected_club_addr: u64,
    selected_senior_team_addr: u64,
) -> Result<TacticalInspectorReport, String> {
    if !valid_ptr(selected_club_addr) {
        return Err(format!("invalid club pointer 0x{selected_club_addr:X}"));
    }
    if !valid_ptr(selected_senior_team_addr) {
        return Err(format!("invalid senior-team pointer 0x{selected_senior_team_addr:X}"));
    }

    let root_addr = fm
        .read_u64(selected_senior_team_addr + ELEMENT_CERT_CANONICAL_ROOT_OFF)
        .map_err(|e| format!("cannot read tactical root pointer: {e}"))?;
    if !valid_ptr(root_addr) || (fm.gp_base..fm.gp_end).contains(&root_addr) {
        return Err(format!("invalid tactical root 0x{root_addr:X}"));
    }
    let root = fm
        .read_bytes(root_addr, ELEMENT_CERT_CANONICAL_ROOT_BYTES)
        .map_err(|e| format!("cannot read tactical root: {e}"))?;

    let mut lines = Vec::new();
    let mut total_records = 0usize;
    let mut total_sum = 0u64;
    let mut overall_min = ELEMENT_SEMANTIC_CERT_MAX;
    let mut overall_max = 0u16;
    let mut populated = 0usize;
    let mut empty = 0usize;
    let mut unallocated = 0usize;
    let mut read_errors = 0usize;
    let mut snapshot_hash = ELEMENT_SEMANTIC_CERT_FNV_OFFSET;

    for collection in 0..6usize {
        let desc_off = ELEMENT_CERT_CANONICAL_BASE + collection * ELEMENT_CERT_CANONICAL_STEP;
        let desc = raw_descriptor_at(&root, desc_off);
        match desc.state {
            DescriptorState::Populated => {
                populated += 1;
                if desc.span == 0 || desc.span % ELEMENT_SEMANTIC_STRIDE != 0 {
                    read_errors += 1;
                    lines.push(format!("COLL|{}|INVALID|0|0|0|0|0|0|0|0", collection + 1));
                    continue;
                }
                let bytes = match fm.read_bytes(desc.data, desc.span) {
                    Ok(v) => v,
                    Err(_) => {
                        read_errors += 1;
                        lines.push(format!("COLL|{}|READ ERROR|0|0|0|0|0|0|0|0", collection + 1));
                        continue;
                    }
                };

                let mut hash = ELEMENT_SEMANTIC_CERT_FNV_OFFSET;
                hash = semantic_cert_hash(hash, &bytes);
                snapshot_hash = semantic_cert_hash(snapshot_hash, &[(collection + 1) as u8]);
                snapshot_hash = semantic_cert_hash(snapshot_hash, &bytes);

                let records = bytes.len() / ELEMENT_SEMANTIC_STRIDE;
                let mut sum = 0u64;
                let mut min_value = ELEMENT_SEMANTIC_CERT_MAX;
                let mut max_value = 0u16;
                let mut zero = 0usize;
                let mut maxed = 0usize;
                let mut unique = HashSet::new();
                let mut entries: Vec<(u16, u16)> = Vec::with_capacity(records);

                for record in 0..records {
                    let off = record * ELEMENT_SEMANTIC_STRIDE;
                    let Some(key) = semantic_cert_read_u16(&bytes, off) else { read_errors += 1; continue; };
                    let Some(raw2) = semantic_cert_read_u16(&bytes, off + 2) else { read_errors += 1; continue; };
                    let value = raw2 & ELEMENT_SEMANTIC_CERT_LOW14_MASK;
                    if value > ELEMENT_SEMANTIC_CERT_MAX {
                        read_errors += 1;
                        continue;
                    }
                    sum += value as u64;
                    min_value = min_value.min(value);
                    max_value = max_value.max(value);
                    if value == 0 { zero += 1; }
                    if value == ELEMENT_SEMANTIC_CERT_MAX { maxed += 1; }
                    unique.insert(value);
                    entries.push((value, key));
                }

                entries.sort_by_key(|(value, key)| (*value, *key));
                let avg = if entries.is_empty() { 0 } else { (sum / entries.len() as u64) as u16 };
                let min_value = if entries.is_empty() { 0 } else { min_value };
                let max_value = if entries.is_empty() { 0 } else { max_value };

                total_records += entries.len();
                total_sum += sum;
                if !entries.is_empty() {
                    overall_min = overall_min.min(min_value);
                    overall_max = overall_max.max(max_value);
                }

                lines.push(format!(
                    "COLL|{}|POPULATED|{}|{}|{}|{}|{}|{}|{}|{:016X}",
                    collection + 1, entries.len(), avg, min_value, max_value,
                    maxed, zero, unique.len(), hash,
                ));

                if let Some((value, key)) = entries.first().copied() {
                    lines.push(format!("LOW|{}|{}|{}|{:.1}", collection + 1, key, value, tactical_viewer_pct(value)));
                }
                if let Some((value, key)) = entries.last().copied() {
                    lines.push(format!("HIGH|{}|{}|{}|{:.1}", collection + 1, key, value, tactical_viewer_pct(value)));
                }
            }
            DescriptorState::Empty => {
                empty += 1;
                lines.push(format!("COLL|{}|EMPTY|0|0|0|0|0|0|0|0", collection + 1));
            }
            DescriptorState::Unallocated => {
                unallocated += 1;
                lines.push(format!("COLL|{}|UNALLOCATED|0|0|0|0|0|0|0|0", collection + 1));
            }
            DescriptorState::Invalid => {
                read_errors += 1;
                lines.push(format!("COLL|{}|INVALID|0|0|0|0|0|0|0|0", collection + 1));
            }
        }
    }

    if total_records == 0 {
        overall_min = 0;
    }
    let overall_avg = if total_records == 0 { 0 } else { (total_sum / total_records as u64) as u16 };
    lines.insert(0, format!(
        "OVERVIEW|{}|{}|{}|{}|{}|{}|{}|{:016X}",
        total_records, overall_avg, overall_min, overall_max,
        populated, empty, unallocated, snapshot_hash,
    ));

    Ok(TacticalInspectorReport {
        club_addr: selected_club_addr,
        senior_team_addr: selected_senior_team_addr,
        scanned_roots: 6,
        pointer_candidates: populated,
        vector_candidates: total_records,
        six_collection_candidates: 6usize.saturating_sub(read_errors.min(6)),
        formation_candidates: empty + unallocated,
        packed14_candidates: overall_avg as usize,
        read_errors,
        strongest_score: if read_errors == 0 { 5 } else { 3 },
        candidate_lines: lines,
        ready_for_write: false,
    })
}

#[cfg(test)]
mod element_premium_tactical_viewer_tests {
    use super::tactical_viewer_pct;

    #[test]
    fn viewer_converts_knowledge_to_percentage() {
        assert_eq!(tactical_viewer_pct(10_000), 100.0);
        assert_eq!(tactical_viewer_pct(2_397), 23.97);
    }
}

'@
    $text = $text.Substring(0, $at) + $viewerCode + $text.Substring($at)
    Write-Text $inspector $text
}

Replace-Required 'src/bridge/worker.rs' '                    Some(f) => tactical_inspector::certify_semantic_slots_all_clubs(f, club_addr, senior_team_addr),' '                    Some(f) => tactical_inspector::view_selected_tactical_knowledge(f, club_addr, senior_team_addr),'

$panel = 'src/ui/club_panel.rs'
$ui = Read-Text $panel

# Replace the complete Tactical Knowledge workspace with the premium viewer.
$pattern = '(?s)fn show_tactical_understanding\(ui: &mut egui::Ui, club: &ClubView\) \{.*?\n\}(?=\n\nfn )'
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

$regex = [regex]::new($pattern)
if (-not $regex.IsMatch($ui)) { throw 'v3.6: Tactical Knowledge function boundary not found' }
$ui = $regex.Replace($ui, $replacement, 1)
Write-Text $panel $ui

Replace-Required 'src/app.rs' '"Tactical semantic certification: confidence {}/5, {} semantic teams, {} populated vectors, {} out-of-range"' '"Tactical Knowledge viewer: confidence {}/5, {} live records, {} active collections, {} empty/unallocated"'
Replace-Required 'src/app.rs' '"Tactical semantic certification running read-only…"' '"Refreshing Tactical Knowledge live view…"'

Write-Host 'Element v3.6 premium Tactical Knowledge viewer applied successfully.'
