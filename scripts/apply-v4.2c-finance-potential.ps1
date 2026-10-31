$ErrorActionPreference='Stop'
$SourceRoot=(Get-Location).Path
function Read-Text([string]$RelativePath){$p=Join-Path $SourceRoot $RelativePath;if(-not(Test-Path -LiteralPath $p)){throw "Source file not found: $p"};[IO.File]::ReadAllText($p)}
function Write-Text([string]$RelativePath,[string]$Text){$p=Join-Path $SourceRoot $RelativePath;[IO.File]::WriteAllText($p,$Text,[Text.UTF8Encoding]::new($false))}
function Replace-Required([string]$Text,[string]$Old,[string]$New,[string]$Label){if(-not $Text.Contains($Old)){throw "v4.2c: expected source fragment not found: $Label"};$Text.Replace($Old,$New)}

# -----------------------------------------------------------------------------
# Element v4.2c — EDITABLE POTENTIAL + FINANCE COMMAND CENTER
# Uses already-mapped PA and FM27 finance fields only. No new offsets.
# -----------------------------------------------------------------------------

# ======================== PLAYER POTENTIAL ====================================
$playerPath='src/ui/player_panel.rs'
$player=Read-Text $playerPath
$helperAnchor='fn show_player_power_rail('
if(-not $player.Contains($helperAnchor)){throw 'v4.2c: player power rail helper anchor missing'}
$helper=@'
fn element_set_player_pa(
    schemas: &'static crate::fields::VersionedSchemas,
    player: &mut PlayerRecord,
    addr: u64,
    edits: &mut Vec<FieldEdit>,
    target: u8,
) {
    let Some(field) = schemas.field("p_pa") else { return; };
    let Some(loc) = field.offset.as_ref() else { return; };
    if !matches!(loc.encoding(), crate::fields::Encoding::Direct | crate::fields::Encoding::Encoded) { return; }
    let offset = loc.offset() as usize;
    let Some(old_raw) = player.raw.get(offset).copied() else { return; };
    let old = loc.decode_u8(old_raw);
    let target = target.clamp(1, 200);
    if old == target { return; }
    let new_raw = loc.encode_u8(target);
    player.raw[offset] = new_raw;
    edits.push(FieldEdit {
        addr: addr + offset as u64,
        old_raw: vec![old_raw],
        new_raw: vec![new_raw],
        description: format!("Potential Ability: {old} → {target}"),
    });
}

'@
$player=$player.Replace($helperAnchor,$helper+$helperAnchor)
$player=Replace-Required $player @'
        let progress = if pa > 0 { (ca as f32 / pa as f32).clamp(0.0, 1.0) } else { 0.0 };
        ui.add(egui::ProgressBar::new(progress).desired_width(ui.available_width()).text(format!("Development gap {gap}")));
'@ @'
        let progress = if pa > 0 { (ca as f32 / pa as f32).clamp(0.0, 1.0) } else { 0.0 };
        ui.add(egui::ProgressBar::new(progress).desired_width(ui.available_width()).text(format!("Development gap {gap}")));
        let enabled = crate::ui::navigation::editing_enabled(ui);
        ui.horizontal(|ui| {
            if ui.add_enabled(enabled && pa > 1, egui::Button::new("PA −1").min_size(egui::vec2(50.0, 18.0))).clicked() {
                element_set_player_pa(schemas, player, addr, edits, pa.saturating_sub(1).max(1));
            }
            if ui.add_enabled(enabled && pa < 200, egui::Button::new("PA +1").min_size(egui::vec2(50.0, 18.0))).clicked() {
                element_set_player_pa(schemas, player, addr, edits, pa.saturating_add(1).min(200));
            }
            if ui.add_enabled(enabled && pa != 200, egui::Button::new("PA 200").min_size(egui::vec2(56.0, 18.0))).on_hover_text("Set Potential Ability to the FM maximum (200)").clicked() {
                element_set_player_pa(schemas, player, addr, edits, 200);
            }
        });
        ui.label(egui::RichText::new("PA is a verified live-edit field; changes use normal Undo.").size(7.5).color(egui::Color32::from_rgb(139,157,188)));
'@ 'ability PA quick controls'
Write-Text $playerPath $player

# ======================== CLUB FINANCE ========================================
$clubPath='src/ui/club_panel.rs'
$club=Read-Text $clubPath
$financeAnchor='fn show_finance('
if(-not $club.Contains($financeAnchor)){throw 'v4.2c: show_finance anchor missing'}
$financeHelper=@'
fn element_set_club_money(
    schemas: &'static crate::fields::VersionedSchemas,
    club: &mut ClubView,
    key: &str,
    value: u32,
    edits: &mut Vec<FieldEdit>,
) {
    let Some((container, offset)) = sub_location(schemas, key) else { return; };
    let label = schemas.field(key).map(|f| f.label).unwrap_or(key).to_string();
    let Some((buf, base)) = club.sub_record_mut(container) else { return; };
    if offset + 4 > buf.len() { return; }
    let old_bytes: [u8;4] = buf[offset..offset+4].try_into().unwrap();
    let old = u32::from_le_bytes(old_bytes);
    if old == value { return; }
    let new_bytes = value.to_le_bytes();
    buf[offset..offset+4].copy_from_slice(&new_bytes);
    edits.push(FieldEdit {
        addr: base + offset as u64,
        old_raw: old_bytes.to_vec(),
        new_raw: new_bytes.to_vec(),
        description: format!("{label}: {old} → {value}"),
    });
}

'@
$club=$club.Replace($financeAnchor,$financeHelper+$financeAnchor)
$club=Replace-Required $club @'
    ui.strong("Finance");
    // Each row edits the sub-record its schema location names (FM26 keeps the
'@ @'
    ui.horizontal(|ui| {
        ui.label(egui::RichText::new("FINANCE COMMAND CENTER").size(13.0).strong().color(egui::Color32::from_rgb(225,232,245)));
        ui.separator();
        ui.label(egui::RichText::new("v4.2 • LIVE EDIT").size(8.0).strong().color(egui::Color32::from_rgb(72,210,132)));
    });
    ui.label(egui::RichText::new("Balance, Transfer Budget and Spending Wage Budget use verified FM27 finance fields and the normal write + Undo path.").size(8.0).color(egui::Color32::from_rgb(139,157,188)));
    ui.add_space(4.0);
    egui::Frame::group(ui.style())
        .fill(egui::Color32::from_rgb(19,24,35))
        .stroke(egui::Stroke::new(1.0,egui::Color32::from_rgb(42,50,68)))
        .rounding(egui::Rounding::same(4))
        .inner_margin(egui::Margin::symmetric(7,5))
        .show(ui,|ui|{
            let enabled=crate::ui::navigation::editing_enabled(ui);
            ui.horizontal_wrapped(|ui|{
                ui.label(egui::RichText::new("QUICK FINANCE").size(8.0).strong());
                if ui.add_enabled(enabled,egui::Button::new("£1B BALANCE")).clicked(){element_set_club_money(schemas,club,"c_balance",1_000_000_000,edits);}
                if ui.add_enabled(enabled,egui::Button::new("£500M TRANSFER")).clicked(){element_set_club_money(schemas,club,"c_transfer_budget",500_000_000,edits);}
                if ui.add_enabled(enabled,egui::Button::new("£10M/W WAGE")).clicked(){element_set_club_money(schemas,club,"c_wage_budget",10_000_000,edits);}
                if ui.add_enabled(enabled,egui::Button::new("RICH CLUB")).on_hover_text("Balance £2B • Transfer Budget £1B • Spending Wage Budget £15M/w").clicked(){
                    element_set_club_money(schemas,club,"c_balance",2_000_000_000,edits);
                    element_set_club_money(schemas,club,"c_transfer_budget",1_000_000_000,edits);
                    element_set_club_money(schemas,club,"c_wage_budget",15_000_000,edits);
                }
            });
        });
    ui.add_space(5.0);
    ui.label(egui::RichText::new("LIVE EDITABLE VALUES").size(9.0).strong().color(egui::Color32::from_rgb(112,177,255)));
    // Each row edits the sub-record its schema location names (FM26 keeps the
'@ 'finance command center'

# Clarify the one budget field we deliberately cannot expose as live.
$club=$club.Replace('if !shown {`n        ui.label("Finance data not available.");`n    }','if !shown {`n        ui.label("Finance data not available.");`n    }')
Write-Text $clubPath $club
Write-Host 'Element v4.2c Editable Potential + Finance Command Center applied successfully.'
