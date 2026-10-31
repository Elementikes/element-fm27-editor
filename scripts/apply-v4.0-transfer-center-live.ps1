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
function Replace-Required([string]$Text, [string]$Old, [string]$New, [string]$Label) {
    if (-not $Text.Contains($Old)) { throw "v4.0: expected source fragment not found: $Label" }
    return $Text.Replace($Old, $New)
}

# -----------------------------------------------------------------------------
# Element v4.0 — LIVE TRANSFER & CONTRACT CENTER
#
# Read-side only. Uses independently validated FM27 fields:
#   - p_list_flags contract+0x57 (bit0 transfer, bit1 loan)
#   - p_contract_wage contract+0x20
#   - p_contract_signed contract+0x44
#   - p_contract_expiry contract+0x48
#   - p_squad_status contract+0x54
#   - p_value player+0x234 (verified transfer value)
#
# Asking price (+0x238) is deliberately NOT surfaced as live: upstream live
# witness testing still reads -1 for a transfer-listed player. Transfer
# proposals and Force Transfer remain gated until their complete structures /
# write chains are independently certified.
# -----------------------------------------------------------------------------

# ======================== CACHE TRANSFER SUMMARY ===============================
$cachePath = 'src/cache.rs'
$cache = Read-Text $cachePath
$cache = Replace-Required $cache @'
    pub morale: Option<u8>,
'@ @'
    pub morale: Option<u8>,
    /// Verified FM27 listing flags: bit 0 transfer-listed, bit 1 loan-listed.
    pub list_flags: Option<u8>,
    /// Verified FM27 contract signed date: (raw day-of-year word, year).
    pub contract_signed: Option<(u16, u16)>,
    /// Verified FM27 contract expiry date: (raw day-of-year word, year).
    pub contract_expiry: Option<(u16, u16)>,
'@ 'CachedPlayer transfer summary fields'
Write-Text $cachePath $cache

$bulkPath = 'src/bridge/bulk_load.rs'
$bulk = Read-Text $bulkPath
$bulk = Replace-Required $bulk @'
            wage: None, squad_status: None, morale: None,
'@ @'
            wage: None, squad_status: None, morale: None,
            list_flags: None, contract_signed: None, contract_expiry: None,
'@ 'CachedPlayer transfer summary initializer'

$valueAnchor = @'
            // v3.8.2: contract summary for the roster table. The contract
'@
$valueRead = @'
            // v4.0: verified direct transfer value. Keep the existing `value`
            // cache field useful for Transfer Center and future list columns.
            if let Some(offset) = schemas.offset_of("p_value") {
                if let Some(bytes) = player.raw.get(offset..offset + 4) {
                    let value = u32::from_le_bytes(bytes.try_into().unwrap()) as u64;
                    player.value = (value > 0).then_some(value);
                }
            }

            // v3.8.2: contract summary for the roster table. The contract
'@
$bulk = Replace-Required $bulk $valueAnchor $valueRead 'verified transfer value cache'

$contractAnchor = @'
                if let Some(offset) = schemas.offset_of("p_squad_status") {
                    player.squad_status = fm.read_u8(contract_addr + offset as u64).ok();
                }
'@
$contractRead = @'
                if let Some(offset) = schemas.offset_of("p_squad_status") {
                    player.squad_status = fm.read_u8(contract_addr + offset as u64).ok();
                }

                // v4.0 listing flags are live-validated: bit 0 = transfer
                // listed, bit 1 = loan listed. Preserve FM's other flag bits.
                if let Some(offset) = schemas.offset_of("p_list_flags") {
                    player.list_flags = fm.read_u8(contract_addr + offset as u64).ok();
                }

                let read_contract_date = |key: &str| -> Option<(u16, u16)> {
                    let offset = schemas.offset_of(key)?;
                    let raw = fm.read_bytes(contract_addr + offset as u64, 4).ok()?;
                    let day = u16::from_le_bytes(raw.get(0..2)?.try_into().ok()?);
                    let year = u16::from_le_bytes(raw.get(2..4)?.try_into().ok()?);
                    let doy = day & 0x7fff;
                    (year > 1900 && (1..=366).contains(&doy)).then_some((day, year))
                };
                player.contract_signed = read_contract_date("p_contract_signed");
                player.contract_expiry = read_contract_date("p_contract_expiry");
'@
$bulk = Replace-Required $bulk $contractAnchor $contractRead 'listing flags and contract dates'
Write-Text $bulkPath $bulk

# ======================== PREMIUM TRANSFER CENTER ==============================
$clubPath = 'src/ui/club_panel.rs'
$club = Read-Text $clubPath
$transferStart = $club.IndexOf('fn show_transfer_center(')
$transferEnd = $club.IndexOf('fn show_tactical_understanding(', $transferStart)
if ($transferStart -lt 0 -or $transferEnd -lt 0) {
    throw 'v4.0: transfer-center function boundaries not found'
}

$newTransfer = @'
fn element_transfer_listed(player: &crate::cache::CachedPlayer) -> bool {
    player.list_flags.is_some_and(|flags| flags & 0x01 != 0)
}

fn element_loan_listed(player: &crate::cache::CachedPlayer) -> bool {
    player.list_flags.is_some_and(|flags| flags & 0x02 != 0)
}

fn element_format_money(value: u64) -> String {
    if value >= 1_000_000_000 {
        format!("£{:.2}B", value as f64 / 1_000_000_000.0)
    } else if value >= 1_000_000 {
        format!("£{:.1}M", value as f64 / 1_000_000.0)
    } else if value >= 1_000 {
        format!("£{:.0}K", value as f64 / 1_000.0)
    } else {
        format!("£{value}")
    }
}

fn element_format_contract_date(date: Option<(u16, u16)>) -> String {
    let Some((raw_day, year)) = date else { return "—".to_owned(); };
    let mut day = raw_day & 0x7fff;
    if day == 0 || day > 366 || year <= 1900 { return "—".to_owned(); }

    let leap = year % 4 == 0 && (year % 100 != 0 || year % 400 == 0);
    let month_days = [31u16, if leap { 29 } else { 28 }, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31];
    let month_names = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
    for (idx, days) in month_days.iter().enumerate() {
        if day <= *days {
            return format!("{:02} {} {}", day, month_names[idx], year);
        }
        day -= *days;
    }
    format!("Day {} / {}", raw_day & 0x7fff, year)
}

fn element_listing_badge(ui: &mut egui::Ui, listed: bool, yes: &str) {
    if listed {
        ui.label(
            egui::RichText::new(yes)
                .size(8.0)
                .strong()
                .color(egui::Color32::from_rgb(72, 210, 132)),
        );
    } else {
        ui.label(egui::RichText::new("—").color(egui::Color32::from_rgb(105, 118, 140)));
    }
}

fn show_transfer_center(ui: &mut egui::Ui, club: &ClubView) {
    ui.spacing_mut().item_spacing = egui::vec2(6.0, 4.0);

    ui.horizontal(|ui| {
        ui.label(
            egui::RichText::new("LIVE TRANSFER & CONTRACT CENTER")
                .size(13.0)
                .strong()
                .color(egui::Color32::from_rgb(225, 232, 245)),
        );
        ui.separator();
        ui.label(
            egui::RichText::new("v4.0 • CONTRACTS LIVE")
                .size(8.0)
                .strong()
                .color(egui::Color32::from_rgb(72, 210, 132)),
        );
    });
    ui.label(
        egui::RichText::new("Verified FM27 listing flags, transfer value, wage and contract dates. Click any player to open the Player Editor.")
            .size(8.5)
            .color(egui::Color32::from_rgb(154, 169, 194)),
    );
    ui.add_space(5.0);

    let Some(cache) = navigation::entity_cache(ui) else {
        locked_notice(ui, "Entity cache is unavailable. Reload the save while FM27 is connected.");
        return;
    };

    let club_players: Vec<&crate::cache::CachedPlayer> = cache
        .players
        .iter()
        .filter(|p| p.club_id == Some(club.uid))
        .collect();
    let transfer_count = club_players.iter().filter(|p| element_transfer_listed(p)).count();
    let loan_count = club_players.iter().filter(|p| element_loan_listed(p)).count();
    let contract_count = club_players.iter().filter(|p| p.contract_expiry.is_some()).count();

    ui.horizontal_wrapped(|ui| {
        for (label, value, color) in [
            ("PLAYERS", club_players.len(), egui::Color32::from_rgb(112, 177, 255)),
            ("TRANSFER LISTED", transfer_count, egui::Color32::from_rgb(72, 210, 132)),
            ("LOAN LISTED", loan_count, egui::Color32::from_rgb(121, 205, 148)),
            ("CONTRACTS", contract_count, egui::Color32::from_rgb(189, 165, 255)),
        ] {
            egui::Frame::group(ui.style())
                .fill(egui::Color32::from_rgb(22, 28, 41))
                .stroke(egui::Stroke::new(1.0, egui::Color32::from_rgb(43, 52, 70)))
                .rounding(egui::Rounding::same(4))
                .inner_margin(egui::Margin::symmetric(7, 4))
                .show(ui, |ui| {
                    ui.label(egui::RichText::new(format!("{label}  {value}")).size(8.0).strong().color(color));
                });
        }
    });
    ui.add_space(5.0);

    let search_id = egui::Id::new(("element_transfer_search", club.addr));
    let mode_id = egui::Id::new(("element_transfer_mode", club.addr));
    let sort_id = egui::Id::new(("element_transfer_sort", club.addr));
    let desc_id = egui::Id::new(("element_transfer_desc", club.addr));
    let mut search = ui.ctx().data_mut(|d| d.get_temp::<String>(search_id).unwrap_or_default());
    let mut mode = ui.ctx().data_mut(|d| d.get_temp::<u8>(mode_id).unwrap_or(0));
    let mut sort = ui.ctx().data_mut(|d| d.get_temp::<u8>(sort_id).unwrap_or(1));
    let mut descending = ui.ctx().data_mut(|d| d.get_temp::<bool>(desc_id).unwrap_or(true));

    ui.horizontal_wrapped(|ui| {
        ui.label(egui::RichText::new("FILTER").size(8.0).strong().color(egui::Color32::from_rgb(139, 157, 188)));
        let r = ui.add_sized([220.0, 22.0], egui::TextEdit::singleline(&mut search).hint_text("Search contracts…"));
        if r.changed() { ui.ctx().data_mut(|d| d.insert_temp(search_id, search.clone())); }
        ui.separator();
        ui.selectable_value(&mut mode, 0, "ALL");
        ui.selectable_value(&mut mode, 1, "TRANSFER LISTED");
        ui.selectable_value(&mut mode, 2, "LOAN LISTED");
        ui.selectable_value(&mut mode, 3, "ANY LISTED");
        ui.ctx().data_mut(|d| d.insert_temp(mode_id, mode));
    });

    ui.horizontal_wrapped(|ui| {
        ui.label(egui::RichText::new("SORT").size(8.0).strong().color(egui::Color32::from_rgb(139, 157, 188)));
        egui::ComboBox::from_id_salt(("element_transfer_sort_combo", club.addr))
            .selected_text(match sort { 0 => "Name", 1 => "Transfer Value", 2 => "Wage", 3 => "Contract Expiry", _ => "Squad Status" })
            .show_ui(ui, |ui| {
                ui.selectable_value(&mut sort, 0, "Name");
                ui.selectable_value(&mut sort, 1, "Transfer Value");
                ui.selectable_value(&mut sort, 2, "Wage");
                ui.selectable_value(&mut sort, 3, "Contract Expiry");
                ui.selectable_value(&mut sort, 4, "Squad Status");
            });
        ui.checkbox(&mut descending, "Descending");
        ui.ctx().data_mut(|d| { d.insert_temp(sort_id, sort); d.insert_temp(desc_id, descending); });
        ui.separator();
        ui.add_enabled(false, egui::Button::new("FORCE TRANSFER • LOCKED"))
            .on_disabled_hover_text("Force Transfer stays locked until the complete destination-team / registration / contract write chain is independently validated.");
    });

    let query = search.trim().to_lowercase();
    let mut rows: Vec<&crate::cache::CachedPlayer> = club_players
        .into_iter()
        .filter(|p| query.is_empty() || p.name.to_lowercase().contains(&query) || p.uid.to_string() == query)
        .filter(|p| match mode {
            1 => element_transfer_listed(p),
            2 => element_loan_listed(p),
            3 => element_transfer_listed(p) || element_loan_listed(p),
            _ => true,
        })
        .collect();

    rows.sort_by(|a, b| {
        let ord = match sort {
            0 => a.name.to_lowercase().cmp(&b.name.to_lowercase()),
            1 => a.value.cmp(&b.value),
            2 => a.wage.cmp(&b.wage),
            3 => a.contract_expiry.cmp(&b.contract_expiry),
            _ => a.squad_status.cmp(&b.squad_status),
        };
        if descending { ord.reverse() } else { ord }
    });

    ui.add_space(4.0);
    egui::Frame::group(ui.style())
        .fill(egui::Color32::from_rgb(22, 28, 41))
        .stroke(egui::Stroke::new(1.0, egui::Color32::from_rgb(43, 52, 70)))
        .rounding(egui::Rounding::same(4))
        .inner_margin(egui::Margin::symmetric(7, 5))
        .show(ui, |ui| {
            ui.horizontal(|ui| {
                ui.label(egui::RichText::new(format!("{} CONTRACT ROWS", rows.len())).size(8.5).strong().color(egui::Color32::from_rgb(112, 177, 255)));
                ui.separator();
                ui.label(egui::RichText::new(&club.full_name).size(9.0).strong());
                ui.separator();
                ui.label(egui::RichText::new("LIVE READ-SIDE").size(7.5).strong().color(egui::Color32::from_rgb(72, 210, 132)));
            });
            ui.add_space(3.0);

            if rows.is_empty() {
                ui.label("No players match the current Transfer Center filter.");
            } else {
                egui::ScrollArea::horizontal().show(ui, |ui| {
                    egui::Grid::new(("element_transfer_contract_grid", club.addr))
                        .num_columns(9)
                        .striped(true)
                        .spacing([16.0, 4.0])
                        .show(ui, |ui| {
                            for h in ["Player", "Transfer", "Loan", "Value", "Asking Price", "Wage", "Expires", "Squad Status", "CA / PA"] {
                                ui.label(egui::RichText::new(h).size(8.0).strong().color(egui::Color32::from_rgb(170, 185, 210)));
                            }
                            ui.end_row();

                            for player in rows {
                                navigation::player_link(ui, player);
                                element_listing_badge(ui, element_transfer_listed(player), "LISTED");
                                element_listing_badge(ui, element_loan_listed(player), "LISTED");
                                match player.value {
                                    Some(value) => { ui.label(egui::RichText::new(element_format_money(value)).strong()); }
                                    None => { ui.label("—"); }
                                }
                                ui.label(egui::RichText::new("—").color(egui::Color32::from_rgb(110, 122, 143)))
                                    .on_hover_text("Asking Price remains unverified on FM27: +0x238 still reads -1 on a known transfer-listed witness. Element will not present it as live data yet.");
                                match player.wage {
                                    Some(wage) => { ui.label(element_format_weekly_wage(wage)); }
                                    None => { ui.label("—"); }
                                }
                                ui.label(element_format_contract_date(player.contract_expiry));
                                match player.squad_status {
                                    Some(code) if code != 0 => {
                                        ui.label(element_squad_status_name(code).unwrap_or("Unknown"))
                                            .on_hover_text(format!("Verified contract squad-status code: {code}"));
                                    }
                                    _ => { ui.label("—"); }
                                }
                                ui.label(format!("{} / {}", player.ca, player.pa));
                                ui.end_row();
                            }
                        });
                });
            }
        });

    ui.add_space(6.0);
    ui.columns(2, |cols| {
        egui::Frame::group(cols[0].style())
            .fill(egui::Color32::from_rgb(26, 32, 48))
            .stroke(egui::Stroke::new(1.0, egui::Color32::from_rgb(43, 52, 70)))
            .rounding(egui::Rounding::same(4))
            .inner_margin(egui::Margin::symmetric(8, 6))
            .show(&mut cols[0], |ui| {
                ui.label(egui::RichText::new("CONTRACT INTELLIGENCE").size(8.0).strong().color(egui::Color32::from_rgb(139, 157, 188)));
                ui.label("Wage • signed date • expiry • squad status • transfer value are backed by certified FM27 fields.");
                ui.label(egui::RichText::new("Asking Price: GATED").size(8.0).strong().color(egui::Color32::from_rgb(216, 181, 99)));
            });

        egui::Frame::group(cols[1].style())
            .fill(egui::Color32::from_rgb(26, 32, 48))
            .stroke(egui::Stroke::new(1.0, egui::Color32::from_rgb(43, 52, 70)))
            .rounding(egui::Rounding::same(4))
            .inner_margin(egui::Margin::symmetric(8, 6))
            .show(&mut cols[1], |ui| {
                ui.label(egui::RichText::new("TRANSFER PROPOSALS").size(8.0).strong().color(egui::Color32::from_rgb(139, 157, 188)));
                ui.label("Proposal / bid collection is not yet certified in FM27 memory.");
                ui.label(egui::RichText::new("READ-SIDE SAFE • FORCE TRANSFER LOCKED").size(8.0).strong().color(egui::Color32::from_rgb(72, 210, 132)));
            });
    });
}

'@
$club = $club.Substring(0, $transferStart) + $newTransfer + $club.Substring($transferEnd)
Write-Text $clubPath $club

Write-Host 'Element v4.0 LIVE TRANSFER & CONTRACT CENTER applied successfully.'
