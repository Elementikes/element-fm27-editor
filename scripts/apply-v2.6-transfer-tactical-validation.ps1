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
# Element v2.6 — VERIFIED TRANSFER STATUS + TACTICAL VALIDATION
#
# Transfer side:
#   Backports FM27 Steam listing metadata verified in newer GPL upstream work:
#   contract+0x50 Listed Since, +0x57 flags, +0x58 listing code. Existing
#   asking price / transfer value / contract controls stay on the normal
#   FieldEdit -> bridge write -> Undo/History path.
#
# Tactical side:
#   The UI now documents the independently published/open-source validation
#   model for FM27 tactical knowledge (existing learned entries only; 10000
#   means 100%). We deliberately DO NOT invent the missing player-training
#   pointer chain. The write action remains locked until that chain is ported
#   and read-back validated in Element on the supported native Windows build.
# -----------------------------------------------------------------------------

# ============================ FM27 SCHEMA =====================================
$schema = 'src/fields/fm27/player.rs'
$schemaText = Read-Text $schema
if (-not $schemaText.Contains('key: "p_list_date"')) {
    $needle = '        Field { key: "p_list_flags",       label: "Listing Flags",    entity: Player, category: Contract,   offset: sub_direct("contract", 0x57)  },'
    $at = $schemaText.IndexOf($needle)
    if ($at -lt 0) { throw 'v2.6: p_list_flags schema boundary not found' }
    $lineEnd = $schemaText.IndexOf("`n", $at)
    if ($lineEnd -lt 0) { $lineEnd = $schemaText.Length - 1 }
    $insert = @'
        // FM27 verified listing metadata. Packed 1 Jan 1900 means not listed.
        Field { key: "p_list_date",        label: "Listed Since",     entity: Player, category: Contract,   offset: sub_date("contract", 0x50)    },
        // 5 = club transfer-listed on witnessed players; loan-only/unlisted = 0.
        Field { key: "p_list_code",        label: "Listing Code",     entity: Player, category: Contract,   offset: sub_direct("contract", 0x58)  },
'@
    $schemaText = $schemaText.Substring(0, $lineEnd + 1) + $insert + $schemaText.Substring($lineEnd + 1)
    Write-Text $schema $schemaText
    Write-Host 'v2.6: added verified FM27 listing date/code fields'
} else {
    Write-Host 'v2.6: listing date/code already present'
}

# ============================ PLAYER TRANSFER LAB =============================
$p = 'src/ui/player_panel.rs'
$playerText = Read-Text $p
$transferStart = $playerText.IndexOf('fn show_transfer_lab(')
$transferEnd = $playerText.IndexOf('/// Squad statuses', $transferStart)
if ($transferStart -lt 0 -or $transferEnd -lt 0) {
    throw 'v2.6: player Transfer Lab boundaries not found'
}

$newTransferLab = @'
fn show_transfer_lab(
    schemas: &'static crate::fields::VersionedSchemas,
    ui: &mut egui::Ui,
    player: &mut PlayerRecord,
    edits: &mut Vec<FieldEdit>,
) {
    ui.spacing_mut().item_spacing = egui::vec2(6.0, 3.0);

    ui.horizontal(|ui| {
        ui.label(egui::RichText::new("TRANSFER LAB").size(13.0).strong().color(egui::Color32::from_rgb(112, 177, 255)));
        ui.separator();
        ui.label(egui::RichText::new("FM27 VERIFIED MARKET STATUS").size(8.5).strong().color(egui::Color32::from_rgb(72, 210, 132)));
    });
    ui.label(egui::RichText::new("Transfer/loan listing, listing metadata, value, asking price and mapped contract fields are live. Force/Future Transfer stays locked until all linked membership records are verified.").size(8.5).color(egui::Color32::from_rgb(150, 166, 194)));
    ui.add_space(3.0);

    egui::Frame::group(ui.style())
        .fill(egui::Color32::from_rgb(23, 29, 42))
        .stroke(egui::Stroke::new(1.0, egui::Color32::from_rgb(43, 52, 70)))
        .rounding(egui::Rounding::same(4))
        .inner_margin(egui::Margin::symmetric(7, 5))
        .show(ui, |ui| {
            ui.horizontal_wrapped(|ui| {
                ui.label(egui::RichText::new("PLAYER").size(8.0).strong().color(egui::Color32::from_rgb(139, 157, 188)));
                ui.label(player.name.as_deref().unwrap_or("Unknown"));
                ui.separator();
                ui.label(egui::RichText::new("CURRENT CLUB").size(8.0).strong().color(egui::Color32::from_rgb(139, 157, 188)));
                ui.label(player.club_name.as_deref().unwrap_or("Free Agent"));
            });
        });
    ui.add_space(4.0);

    ui.columns(2, |cols| {
        egui::Frame::group(cols[0].style())
            .fill(egui::Color32::from_rgb(25, 31, 45))
            .stroke(egui::Stroke::new(1.0, egui::Color32::from_rgb(41, 49, 66)))
            .rounding(egui::Rounding::same(4))
            .inner_margin(egui::Margin::symmetric(7, 5))
            .show(&mut cols[0], |ui| {
                ui.label(egui::RichText::new("MARKET STATUS").size(9.5).strong());
                ui.separator();

                if let (Some(cr), Some(caddr)) = (player.contract_raw.as_mut(), player.contract_addr) {
                    if let Some(flags_field) = schemas.field("p_list_flags") {
                        if let Some(flags_loc) = flags_field.offset.as_ref() {
                            let offset = flags_loc.offset() as usize;
                            if offset < cr.len() {
                                let old = cr[offset];
                                let old_transfer = old & 1 != 0;
                                let old_loan = old & 2 != 0;
                                let mut transfer = old_transfer;
                                let mut loan = old_loan;
                                let enabled = crate::ui::navigation::editing_enabled(ui);
                                ui.add_enabled_ui(enabled, |ui| {
                                    ui.checkbox(&mut transfer, "Transfer Listed");
                                    ui.checkbox(&mut loan, "Loan Listed");
                                });
                                let new = (old & !0b11) | u8::from(transfer) | (u8::from(loan) << 1);
                                if enabled && new != old {
                                    cr[offset] = new;
                                    edits.push(FieldEdit {
                                        addr: caddr + offset as u64,
                                        old_raw: vec![old],
                                        new_raw: vec![new],
                                        description: format!("Listing flags: {old:#04x} → {new:#04x}"),
                                    });

                                    // Verified FM27 witness semantics: a club transfer listing uses
                                    // code 5. Loan-only and fully unlisted records use code 0.
                                    if let Some(code_field) = schemas.field("p_list_code") {
                                        if let Some(code_loc) = code_field.offset.as_ref() {
                                            let code_off = code_loc.offset() as usize;
                                            if code_off < cr.len() {
                                                let old_code = cr[code_off];
                                                let new_code = if transfer { 5u8 } else { 0u8 };
                                                if old_code != new_code {
                                                    cr[code_off] = new_code;
                                                    edits.push(FieldEdit {
                                                        addr: caddr + code_off as u64,
                                                        old_raw: vec![old_code],
                                                        new_raw: vec![new_code],
                                                        description: format!("Listing code: {old_code} → {new_code}"),
                                                    });
                                                }
                                            }
                                        }
                                    }
                                }
                            }
                        }
                    }

                    if let Some(f) = schemas.field("p_list_date") {
                        edits.extend(field_widget::date_edit(ui, "Listed Since", cr, f, caddr, 1900..=2060));
                    }
                    if let Some(f) = schemas.field("p_list_code") {
                        let code = f.offset.as_ref().and_then(|l| cr.get(l.offset() as usize)).copied();
                        if let Some(code) = code { field_widget::info_label(ui, "Listing Code", code); }
                    }

                    let enabled = crate::ui::navigation::editing_enabled(ui);
                    if ui.add_enabled(enabled, egui::Button::new("Clear Transfer + Loan Listing")).clicked() {
                        if let Some(f) = schemas.field("p_list_flags") {
                            if let Some(loc) = f.offset.as_ref() {
                                let off = loc.offset() as usize;
                                if off < cr.len() {
                                    let old = cr[off];
                                    let new = old & !0b11;
                                    if new != old {
                                        cr[off] = new;
                                        edits.push(FieldEdit { addr: caddr + off as u64, old_raw: vec![old], new_raw: vec![new], description: "Clear transfer/loan listing".into() });
                                    }
                                }
                            }
                        }
                        if let Some(f) = schemas.field("p_list_code") {
                            if let Some(loc) = f.offset.as_ref() {
                                let off = loc.offset() as usize;
                                if off < cr.len() && cr[off] != 0 {
                                    let old = cr[off]; cr[off] = 0;
                                    edits.push(FieldEdit { addr: caddr + off as u64, old_raw: vec![old], new_raw: vec![0], description: "Clear listing code".into() });
                                }
                            }
                        }
                    }
                } else {
                    ui.label("Contract sub-record unavailable.");
                }
            });

        egui::Frame::group(cols[1].style())
            .fill(egui::Color32::from_rgb(25, 31, 45))
            .stroke(egui::Stroke::new(1.0, egui::Color32::from_rgb(41, 49, 66)))
            .rounding(egui::Rounding::same(4))
            .inner_margin(egui::Margin::symmetric(7, 5))
            .show(&mut cols[1], |ui| {
                ui.label(egui::RichText::new("VALUE & CONTRACT").size(9.5).strong());
                ui.separator();
                if let Some(f) = schemas.field("p_value") {
                    edits.extend(field_widget::raw_u32_edit(ui, f, &mut player.raw, player.addr));
                }
                if let Some(f) = schemas.field("p_asking_price") {
                    edits.extend(field_widget::optional_money_edit(ui, "Asking Price", &mut player.raw, f, player.addr));
                }
                if let (Some(cr), Some(caddr)) = (player.contract_raw.as_mut(), player.contract_addr) {
                    if let Some(f) = schemas.field("p_contract_wage") {
                        edits.extend(field_widget::raw_u32_edit(ui, f, cr, caddr));
                    }
                    if let Some(f) = schemas.field("p_contract_expiry") {
                        edits.extend(field_widget::date_edit(ui, "Contract Expiry", cr, f, caddr, 2000..=2060));
                    }
                    if let Some(f) = schemas.field("p_squad_number") {
                        if let Some(loc) = f.offset.as_ref() {
                            let off = loc.offset() as usize;
                            if let Some(v) = cr.get(off).copied() {
                                field_widget::info_label(ui, "Squad Number", if v == 255 { "—".to_string() } else { v.to_string() });
                            }
                        }
                    }
                }
            });
    });

    ui.add_space(5.0);
    egui::Frame::group(ui.style())
        .fill(egui::Color32::from_rgb(20, 25, 36))
        .stroke(egui::Stroke::new(1.0, egui::Color32::from_rgb(53, 61, 78)))
        .rounding(egui::Rounding::same(4))
        .inner_margin(egui::Margin::symmetric(7, 5))
        .show(ui, |ui| {
            ui.horizontal(|ui| {
                ui.label(egui::RichText::new("ADVANCED TRANSFERS").size(9.0).strong());
                ui.label(egui::RichText::new("VALIDATION GATE").size(8.0).color(egui::Color32::from_rgb(255, 184, 77)));
            });
            let target_id = egui::Id::new(("element_target_club", player.addr));
            let mut target = ui.data_mut(|d| d.get_temp::<String>(target_id).unwrap_or_default());
            ui.horizontal(|ui| {
                ui.label("Target club");
                let response = ui.add_sized([280.0, 22.0], egui::TextEdit::singleline(&mut target).hint_text("Search club name..."));
                if response.changed() { ui.data_mut(|d| d.insert_temp(target_id, target.clone())); }
                ui.add_enabled(false, egui::Button::new("Force Transfer"));
                ui.add_enabled(false, egui::Button::new("Future Transfer"));
                ui.add_enabled(false, egui::Button::new("Attract Clubs"));
            });
            ui.label(egui::RichText::new("These operations require target-team membership + source squad + contract/registration records to be committed consistently. Element will not perform a partial pointer-only transfer.").size(8.0).color(egui::Color32::from_rgb(154, 169, 194)));
        });
}

'@

$playerText = $playerText.Substring(0, $transferStart) + $newTransferLab + $playerText.Substring($transferEnd)
Write-Text $p $playerText
Write-Host 'v2.6: rebuilt Player Transfer Lab with verified FM27 listing metadata'

# ============================ CLUB TRANSFER/TAC ===============================
$c = 'src/ui/club_panel.rs'
$clubText = Read-Text $c
$tcStart = $clubText.IndexOf('fn show_transfer_center(')
$tuStart = $clubText.IndexOf('fn show_tactical_understanding(', $tcStart)
$lockedStart = $clubText.IndexOf('fn locked_notice(', $tuStart)
if ($tcStart -lt 0 -or $tuStart -lt 0 -or $lockedStart -lt 0) {
    throw 'v2.6: club transfer/tactical function boundaries not found'
}

$newTransferCenter = @'
fn show_transfer_center(ui: &mut egui::Ui, club: &ClubView) {
    ui.spacing_mut().item_spacing = egui::vec2(6.0, 4.0);
    ui.horizontal(|ui| {
        ui.label(egui::RichText::new("TRANSFER CENTER").size(13.0).strong());
        ui.separator();
        ui.label(egui::RichText::new("VALIDATED FM27 MARKET LAYER").size(8.5).strong().color(egui::Color32::from_rgb(72, 210, 132)));
    });
    ui.label(egui::RichText::new("Element now has verified player listing metadata. The game's proposal/future-transfer collection itself is still not mapped, so we do not invent rows or editable fees here.").size(8.5).color(egui::Color32::from_rgb(154, 169, 194)));
    ui.add_space(4.0);

    egui::Frame::group(ui.style())
        .fill(egui::Color32::from_rgb(24, 30, 43))
        .stroke(egui::Stroke::new(1.0, egui::Color32::from_rgb(43, 52, 70)))
        .rounding(egui::Rounding::same(4))
        .inner_margin(egui::Margin::symmetric(7, 5))
        .show(ui, |ui| {
            ui.label(egui::RichText::new("AVAILABLE NOW").size(9.0).strong().color(egui::Color32::from_rgb(112, 177, 255)));
            ui.horizontal_wrapped(|ui| {
                for text in ["Transfer Listed", "Loan Listed", "Listed Since", "Listing Code", "Transfer Value", "Asking Price", "Wage", "Contract Expiry"] {
                    ui.label(egui::RichText::new(text).size(8.5).background_color(egui::Color32::from_rgb(31, 42, 61)).color(egui::Color32::from_rgb(224, 232, 245)));
                }
            });
            ui.label(egui::RichText::new("Open a player → Move to Club to edit these fields live with Undo/History.").size(8.0).color(egui::Color32::from_rgb(139, 157, 188)));
        });

    ui.add_space(5.0);
    egui::Frame::group(ui.style())
        .fill(egui::Color32::from_rgb(20, 25, 36))
        .stroke(egui::Stroke::new(1.0, egui::Color32::from_rgb(42, 50, 69)))
        .rounding(egui::Rounding::same(4))
        .inner_margin(egui::Margin::symmetric(6, 5))
        .show(ui, |ui| {
            egui::Grid::new("element_transfer_center_table_v26")
                .num_columns(7)
                .spacing([14.0, 4.0])
                .striped(true)
                .show(ui, |ui| {
                    for h in ["Type", "Name", "From", "To", "Fee", "Status", "Date"] {
                        ui.label(egui::RichText::new(h).strong().small());
                    }
                    ui.end_row();
                    ui.label("—");
                    ui.label("Proposal collection not mapped");
                    ui.label("—");
                    ui.label(&club.full_name);
                    ui.label("—");
                    ui.label("Read-only");
                    ui.label("—");
                    ui.end_row();
                });
        });

    ui.add_space(5.0);
    ui.label(egui::RichText::new("NEXT VALIDATION: proposal vector → source/target club ownership → fee/add-ons → future contract → registration/squad membership. Force Transfer remains locked until this full chain is proven.").size(8.0).color(egui::Color32::from_rgb(255, 184, 77)));
}

'@

$newTactical = @'
fn show_tactical_understanding(ui: &mut egui::Ui, club: &ClubView) {
    ui.spacing_mut().item_spacing = egui::vec2(6.0, 4.0);
    ui.horizontal(|ui| {
        ui.label(egui::RichText::new("TACTICAL KNOWLEDGE").size(13.0).strong());
        ui.separator();
        ui.label(egui::RichText::new("FM27 STRUCTURE SPEC VALIDATED • WRITE PATH LOCKED").size(8.0).strong().color(egui::Color32::from_rgb(255, 184, 77)));
    });
    ui.label(egui::RichText::new("Independent open-source FM27 research confirms how learned knowledge is packed. Element still needs the exact player-training ownership/pointer chain before it will write these records.").size(8.5).color(egui::Color32::from_rgb(154, 169, 194)));
    ui.add_space(4.0);

    ui.horizontal(|ui| {
        ui.selectable_label(true, format!("{} • First Team", club.short_name));
        ui.add_enabled(false, egui::Button::new("All Club Squads"));
        ui.add_enabled(false, egui::Button::new("Selected Players"));
    });
    ui.add_space(4.0);

    ui.columns(2, |cols| {
        egui::Frame::group(cols[0].style())
            .fill(egui::Color32::from_rgb(25, 31, 45))
            .stroke(egui::Stroke::new(1.0, egui::Color32::from_rgb(41, 49, 66)))
            .rounding(egui::Rounding::same(4))
            .inner_margin(egui::Margin::symmetric(7, 5))
            .show(&mut cols[0], |ui| {
                ui.label(egui::RichText::new("LEARNED INSTRUCTIONS").size(9.5).strong());
                ui.separator();
                ui.label("6 packed instruction collections");
                ui.label("Knowledge value: 14-bit");
                ui.label("100% stored value: 10,000");
                ui.label("Instruction keys must be preserved");
                ui.label("Existing entries only — never allocate fake tactics");
            });

        egui::Frame::group(cols[1].style())
            .fill(egui::Color32::from_rgb(25, 31, 45))
            .stroke(egui::Stroke::new(1.0, egui::Color32::from_rgb(41, 49, 66)))
            .rounding(egui::Rounding::same(4))
            .inner_margin(egui::Margin::symmetric(7, 5))
            .show(&mut cols[1], |ui| {
                ui.label(egui::RichText::new("FORMATION / ROLE FAMILIARITY").size(9.5).strong());
                ui.separator();
                ui.label("Existing formation/role rows only");
                ui.label("Knowledge value: 16-bit");
                ui.label("Value is stored at row offset +14");
                ui.label("100% stored value: 10,000");
                ui.label("Ownership links must remain unchanged");
            });
    });

    ui.add_space(5.0);
    egui::Frame::group(ui.style())
        .fill(egui::Color32::from_rgb(20, 25, 36))
        .stroke(egui::Stroke::new(1.0, egui::Color32::from_rgb(53, 61, 78)))
        .rounding(egui::Rounding::same(4))
        .inner_margin(egui::Margin::symmetric(7, 5))
        .show(ui, |ui| {
            ui.horizontal(|ui| {
                ui.add_enabled(false, egui::Button::new("Full Tactical Knowledge (100%)"))
                    .on_disabled_hover_text("Locked until Element ports and validates the FM27 player-training pointer chain + knowledge-cache refresh record.");
                ui.label(egui::RichText::new("NO PARTIAL / GUESSED WRITES").size(8.0).strong().color(egui::Color32::from_rgb(255, 184, 77)));
            });
            ui.label(egui::RichText::new("The final action will set every existing learned instruction and formation/role entry to 10,000, preserve keys/ownership, then mark FM's knowledge cache for refresh. Missing or stale records will reject the whole batch.").size(8.0).color(egui::Color32::from_rgb(139, 157, 188)));
        });

    ui.add_space(4.0);
    ui.label(egui::RichText::new("This is tactical knowledge/familiarity only. It will not modify Player Ability, Player Buy-In, team cohesion or the tactic itself, and it does not claim to force FM27's overall Tactical Effectiveness gauge to 100%.").size(8.0).color(egui::Color32::from_rgb(154, 169, 194)));
}

'@

$clubText = $clubText.Substring(0, $tcStart) + $newTransferCenter + $newTactical + $clubText.Substring($lockedStart)
Write-Text $c $clubText
Write-Host 'v2.6: upgraded Transfer Center and Tactical Knowledge validation workspace'

Write-Host 'Element v2.6 verified transfer metadata + tactical validation pass applied successfully.'
