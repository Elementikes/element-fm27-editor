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

# -----------------------------------------------------------------------------
# Element v4.1 — CONTRACT INTELLIGENCE + PREMIUM CLEANUP
#
# Read-side only. Uses v4.0's verified contract/listing cache and turns it into
# a denser premium contract browser. No new memory offsets and no transfer
# writes are introduced here.
# -----------------------------------------------------------------------------

$clubPath = 'src/ui/club_panel.rs'
$club = Read-Text $clubPath

# Transfer Center now needs the FM schema season reference year for contract
# horizon intelligence. Do not fake an exact "months remaining" value when the
# club panel does not own the attached save's exact current date.
if ($club.Contains('ClubTab::TransferCenter => show_transfer_center(ui, club),')) {
    $club = $club.Replace(
        'ClubTab::TransferCenter => show_transfer_center(ui, club),',
        'ClubTab::TransferCenter => show_transfer_center(schemas, ui, club),'
    )
} elseif (-not $club.Contains('ClubTab::TransferCenter => show_transfer_center(schemas, ui, club),')) {
    throw 'v4.1: Transfer Center dispatch call not found'
}

$start = $club.IndexOf('fn element_transfer_listed(')
$end = $club.IndexOf('fn element_tactical_pointer_ok(', $start)
if ($start -lt 0 -or $end -lt 0) {
    throw 'v4.1: Transfer Center helper boundaries not found'
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

fn element_contract_year(date: Option<(u16, u16)>) -> Option<u16> {
    date.map(|(_, year)| year).filter(|year| *year > 1900)
}

fn element_contract_term_years(
    signed: Option<(u16, u16)>,
    expiry: Option<(u16, u16)>,
) -> Option<f32> {
    let (signed_day, signed_year) = signed?;
    let (expiry_day, expiry_year) = expiry?;
    if expiry_year < signed_year { return None; }
    let start = signed_year as f32 + ((signed_day & 0x7fff).saturating_sub(1) as f32 / 365.25);
    let end = expiry_year as f32 + ((expiry_day & 0x7fff).saturating_sub(1) as f32 / 365.25);
    let years = end - start;
    (years >= 0.0 && years < 20.0).then_some(years)
}

fn element_contract_horizon(
    expiry: Option<(u16, u16)>,
    season_year: u16,
) -> (&'static str, egui::Color32) {
    match element_contract_year(expiry) {
        None => ("NO DATE", egui::Color32::from_rgb(118, 128, 145)),
        Some(year) if year <= season_year => ("EXPIRING", egui::Color32::from_rgb(255, 118, 118)),
        Some(year) if year == season_year.saturating_add(1) => ("NEXT SEASON", egui::Color32::from_rgb(255, 184, 77)),
        Some(year) if year <= season_year.saturating_add(3) => ("MID TERM", egui::Color32::from_rgb(112, 177, 255)),
        Some(_) => ("LONG TERM", egui::Color32::from_rgb(72, 210, 132)),
    }
}

fn element_market_status(player: &crate::cache::CachedPlayer) -> (&'static str, egui::Color32) {
    match (element_transfer_listed(player), element_loan_listed(player)) {
        (true, true) => ("TRANSFER + LOAN", egui::Color32::from_rgb(255, 184, 77)),
        (true, false) => ("TRANSFER", egui::Color32::from_rgb(72, 210, 132)),
        (false, true) => ("LOAN", egui::Color32::from_rgb(121, 205, 148)),
        (false, false) => ("—", egui::Color32::from_rgb(105, 118, 140)),
    }
}

fn element_transfer_summary_card(
    ui: &mut egui::Ui,
    label: &str,
    value: usize,
    color: egui::Color32,
) {
    egui::Frame::group(ui.style())
        .fill(egui::Color32::from_rgb(22, 28, 41))
        .stroke(egui::Stroke::new(1.0, egui::Color32::from_rgb(43, 52, 70)))
        .rounding(egui::Rounding::same(4))
        .inner_margin(egui::Margin::symmetric(8, 5))
        .show(ui, |ui| {
            ui.horizontal(|ui| {
                ui.label(egui::RichText::new(value.to_string()).size(11.0).strong().color(color));
                ui.label(egui::RichText::new(label).size(7.8).strong().color(egui::Color32::from_rgb(164, 178, 201)));
            });
        });
}

fn show_transfer_center(
    schemas: &'static crate::fields::VersionedSchemas,
    ui: &mut egui::Ui,
    club: &ClubView,
) {
    ui.spacing_mut().item_spacing = egui::vec2(6.0, 4.0);
    let season_year = schemas.age_reference_year;

    ui.horizontal(|ui| {
        ui.label(
            egui::RichText::new("TRANSFER & CONTRACT INTELLIGENCE")
                .size(13.0)
                .strong()
                .color(egui::Color32::from_rgb(225, 232, 245)),
        );
        ui.separator();
        ui.label(
            egui::RichText::new("v4.1 • PREMIUM READ-SIDE")
                .size(8.0)
                .strong()
                .color(egui::Color32::from_rgb(72, 210, 132)),
        );
    });
    ui.label(
        egui::RichText::new(format!(
            "Verified listing, value, wage, signed/expiry dates and squad status. Contract horizon is season-aware against FM27 reference season {season_year}; no guessed exact months remaining."
        ))
        .size(8.3)
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
    let expiring_now = club_players
        .iter()
        .filter(|p| element_contract_year(p.contract_expiry).is_some_and(|y| y <= season_year))
        .count();
    let expiring_next = club_players
        .iter()
        .filter(|p| element_contract_year(p.contract_expiry) == Some(season_year.saturating_add(1)))
        .count();
    let long_term = club_players
        .iter()
        .filter(|p| element_contract_year(p.contract_expiry).is_some_and(|y| y >= season_year.saturating_add(4)))
        .count();

    ui.horizontal_wrapped(|ui| {
        element_transfer_summary_card(ui, "PLAYERS", club_players.len(), egui::Color32::from_rgb(112, 177, 255));
        element_transfer_summary_card(ui, "TRANSFER LISTED", transfer_count, egui::Color32::from_rgb(72, 210, 132));
        element_transfer_summary_card(ui, "LOAN LISTED", loan_count, egui::Color32::from_rgb(121, 205, 148));
        element_transfer_summary_card(ui, "EXPIRING", expiring_now, egui::Color32::from_rgb(255, 118, 118));
        element_transfer_summary_card(ui, "NEXT SEASON", expiring_next, egui::Color32::from_rgb(255, 184, 77));
        element_transfer_summary_card(ui, "LONG TERM", long_term, egui::Color32::from_rgb(189, 165, 255));
    });
    ui.add_space(5.0);

    let search_id = egui::Id::new(("element_transfer_search_v41", club.addr));
    let mode_id = egui::Id::new(("element_transfer_mode_v41", club.addr));
    let sort_id = egui::Id::new(("element_transfer_sort_v41", club.addr));
    let desc_id = egui::Id::new(("element_transfer_desc_v41", club.addr));
    let mut search = ui.ctx().data_mut(|d| d.get_temp::<String>(search_id).unwrap_or_default());
    let mut mode = ui.ctx().data_mut(|d| d.get_temp::<u8>(mode_id).unwrap_or(0));
    let mut sort = ui.ctx().data_mut(|d| d.get_temp::<u8>(sort_id).unwrap_or(1));
    let mut descending = ui.ctx().data_mut(|d| d.get_temp::<bool>(desc_id).unwrap_or(true));

    egui::Frame::group(ui.style())
        .fill(egui::Color32::from_rgb(19, 24, 35))
        .stroke(egui::Stroke::new(1.0, egui::Color32::from_rgb(42, 50, 68)))
        .rounding(egui::Rounding::same(4))
        .inner_margin(egui::Margin::symmetric(7, 5))
        .show(ui, |ui| {
            ui.horizontal_wrapped(|ui| {
                ui.label(egui::RichText::new("SEARCH").size(7.5).strong().color(egui::Color32::from_rgb(139, 157, 188)));
                let r = ui.add_sized([210.0, 22.0], egui::TextEdit::singleline(&mut search).hint_text("Player / UID…"));
                if r.changed() { ui.ctx().data_mut(|d| d.insert_temp(search_id, search.clone())); }

                ui.separator();
                egui::ComboBox::from_id_salt(("element_transfer_mode_combo_v41", club.addr))
                    .selected_text(match mode {
                        1 => "Transfer Listed",
                        2 => "Loan Listed",
                        3 => "Any Listed",
                        4 => "Expiring",
                        5 => "By Next Season",
                        6 => "Long Term",
                        _ => "All Contracts",
                    })
                    .width(145.0)
                    .show_ui(ui, |ui| {
                        ui.selectable_value(&mut mode, 0, "All Contracts");
                        ui.selectable_value(&mut mode, 1, "Transfer Listed");
                        ui.selectable_value(&mut mode, 2, "Loan Listed");
                        ui.selectable_value(&mut mode, 3, "Any Listed");
                        ui.separator();
                        ui.selectable_value(&mut mode, 4, format!("Expiring ≤ {season_year}"));
                        ui.selectable_value(&mut mode, 5, format!("Expiring ≤ {}", season_year.saturating_add(1)));
                        ui.selectable_value(&mut mode, 6, format!("Long Term ≥ {}", season_year.saturating_add(4)));
                    });
                ui.ctx().data_mut(|d| d.insert_temp(mode_id, mode));

                ui.separator();
                ui.label(egui::RichText::new("SORT").size(7.5).strong().color(egui::Color32::from_rgb(139, 157, 188)));
                egui::ComboBox::from_id_salt(("element_transfer_sort_combo_v41", club.addr))
                    .selected_text(match sort {
                        0 => "Name",
                        1 => "Transfer Value",
                        2 => "Wage",
                        3 => "Contract Expiry",
                        4 => "Contract Term",
                        _ => "Squad Status",
                    })
                    .width(125.0)
                    .show_ui(ui, |ui| {
                        ui.selectable_value(&mut sort, 0, "Name");
                        ui.selectable_value(&mut sort, 1, "Transfer Value");
                        ui.selectable_value(&mut sort, 2, "Wage");
                        ui.selectable_value(&mut sort, 3, "Contract Expiry");
                        ui.selectable_value(&mut sort, 4, "Contract Term");
                        ui.selectable_value(&mut sort, 5, "Squad Status");
                    });
                ui.checkbox(&mut descending, "Desc");
                ui.ctx().data_mut(|d| {
                    d.insert_temp(sort_id, sort);
                    d.insert_temp(desc_id, descending);
                });
            });
        });

    let query = search.trim().to_lowercase();
    let mut rows: Vec<&crate::cache::CachedPlayer> = club_players
        .into_iter()
        .filter(|p| query.is_empty() || p.name.to_lowercase().contains(&query) || p.uid.to_string() == query)
        .filter(|p| match mode {
            1 => element_transfer_listed(p),
            2 => element_loan_listed(p),
            3 => element_transfer_listed(p) || element_loan_listed(p),
            4 => element_contract_year(p.contract_expiry).is_some_and(|y| y <= season_year),
            5 => element_contract_year(p.contract_expiry).is_some_and(|y| y <= season_year.saturating_add(1)),
            6 => element_contract_year(p.contract_expiry).is_some_and(|y| y >= season_year.saturating_add(4)),
            _ => true,
        })
        .collect();

    rows.sort_by(|a, b| {
        let ord = match sort {
            0 => a.name.to_lowercase().cmp(&b.name.to_lowercase()),
            1 => a.value.cmp(&b.value),
            2 => a.wage.cmp(&b.wage),
            3 => a.contract_expiry.cmp(&b.contract_expiry),
            4 => element_contract_term_years(a.contract_signed, a.contract_expiry)
                .partial_cmp(&element_contract_term_years(b.contract_signed, b.contract_expiry))
                .unwrap_or(std::cmp::Ordering::Equal),
            _ => a.squad_status.cmp(&b.squad_status),
        };
        if descending { ord.reverse() } else { ord }
    });

    ui.add_space(4.0);
    egui::Frame::group(ui.style())
        .fill(egui::Color32::from_rgb(22, 28, 41))
        .stroke(egui::Stroke::new(1.0, egui::Color32::from_rgb(43, 52, 70)))
        .rounding(egui::Rounding::same(4))
        .inner_margin(egui::Margin::symmetric(5, 4))
        .show(ui, |ui| {
            ui.horizontal(|ui| {
                ui.label(egui::RichText::new(format!("{} RESULTS", rows.len())).size(8.0).strong().color(egui::Color32::from_rgb(112, 177, 255)));
                ui.separator();
                ui.label(egui::RichText::new(&club.full_name).size(8.5).strong());
                ui.separator();
                ui.label(egui::RichText::new("LIVE CONTRACT CACHE").size(7.5).strong().color(egui::Color32::from_rgb(72, 210, 132)));
            });
            ui.add_space(3.0);

            if rows.is_empty() {
                ui.label("No players match the current transfer / contract filter.");
                return;
            }

            let table = egui_extras::TableBuilder::new(ui)
                .striped(true)
                .resizable(true)
                .cell_layout(egui::Layout::left_to_right(egui::Align::Center))
                .column(egui_extras::Column::initial(175.0).at_least(120.0))
                .column(egui_extras::Column::initial(105.0).at_least(82.0))
                .column(egui_extras::Column::initial(78.0).at_least(65.0))
                .column(egui_extras::Column::initial(86.0).at_least(72.0))
                .column(egui_extras::Column::initial(94.0).at_least(82.0))
                .column(egui_extras::Column::initial(176.0).at_least(140.0))
                .column(egui_extras::Column::initial(68.0).at_least(58.0))
                .column(egui_extras::Column::initial(118.0).at_least(95.0))
                .column(egui_extras::Column::initial(66.0).at_least(58.0));

            table
                .header(22.0, |mut header| {
                    for title in ["Player", "Market", "Value", "Wage", "Signed", "Expiry / Horizon", "Term", "Squad Status", "CA / PA"] {
                        header.col(|ui| {
                            ui.label(egui::RichText::new(title).size(7.8).strong().color(egui::Color32::from_rgb(170, 185, 210)));
                        });
                    }
                })
                .body(|body| {
                    body.rows(23.0, rows.len(), |mut row| {
                        let player = rows[row.index()];
                        row.col(|ui| { navigation::player_link(ui, player); });
                        row.col(|ui| {
                            let (label, color) = element_market_status(player);
                            ui.label(egui::RichText::new(label).size(7.5).strong().color(color));
                        });
                        row.col(|ui| {
                            ui.label(player.value.map(element_format_money).unwrap_or_else(|| "—".into()));
                        });
                        row.col(|ui| {
                            ui.label(player.wage.map(element_format_weekly_wage).unwrap_or_else(|| "—".into()));
                        });
                        row.col(|ui| {
                            ui.label(element_format_contract_date(player.contract_signed));
                        });
                        row.col(|ui| {
                            let (horizon, color) = element_contract_horizon(player.contract_expiry, season_year);
                            ui.horizontal(|ui| {
                                ui.label(element_format_contract_date(player.contract_expiry));
                                ui.label(egui::RichText::new(horizon).size(7.0).strong().color(color));
                            });
                        });
                        row.col(|ui| {
                            let term = element_contract_term_years(player.contract_signed, player.contract_expiry)
                                .map(|years| format!("{years:.1}y"))
                                .unwrap_or_else(|| "—".into());
                            ui.label(term).on_hover_text("Contract duration derived from verified signed and expiry dates.");
                        });
                        row.col(|ui| {
                            let text = player.squad_status
                                .and_then(element_squad_status_name)
                                .unwrap_or("—");
                            ui.label(text);
                        });
                        row.col(|ui| {
                            ui.label(egui::RichText::new(format!("{} / {}", player.ca, player.pa)).strong());
                        });
                    });
                });
        });

    ui.add_space(5.0);
    ui.horizontal_wrapped(|ui| {
        ui.add_enabled(false, egui::Button::new("ASKING PRICE • UNVERIFIED"))
            .on_disabled_hover_text("The known candidate asking-price field still returns -1 on witnessed listed players; Element will not present it as live until independently validated.");
        ui.add_enabled(false, egui::Button::new("TRANSFER PROPOSALS • GATED"))
            .on_disabled_hover_text("Proposal vector / fee / add-on structures are not yet certified.");
        ui.add_enabled(false, egui::Button::new("FORCE TRANSFER • LOCKED"))
            .on_disabled_hover_text("Requires destination team membership, source removal, contract ownership, registration and read-back validation as one safe write chain.");
        ui.separator();
        ui.label(egui::RichText::new("READ-SIDE SAFE • ZERO NEW WRITES").size(7.5).strong().color(egui::Color32::from_rgb(72, 210, 132)));
    });
}

'@

$club = $club.Substring(0, $start) + $newTransfer + $club.Substring($end)
Write-Text $clubPath $club
Write-Host 'Element v4.1 Contract Intelligence + premium Transfer Center cleanup applied successfully.'
