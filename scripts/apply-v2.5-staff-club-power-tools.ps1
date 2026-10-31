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

# -----------------------------------------------------------------------------
# Element v2.5 STAFF + CLUB POWER TOOLS
# Uses only fields already present in the active FM27 schema and emits ordinary
# FieldEdit records so existing live-write, Undo and Change History remain the
# single mutation path.
# -----------------------------------------------------------------------------

# ============================= STAFF ==========================================
$s = 'src/ui/staff_panel.rs'
$sp = Join-Path $SourceRoot $s
$staffText = [IO.File]::ReadAllText($sp)

$staffInsert = $staffText.IndexOf('fn show_overview(')
if ($staffInsert -lt 0) { throw 'v2.5: staff show_overview insertion boundary not found' }

$staffHelpers = @'
const ELEMENT_STAFF_BULK_CATEGORIES: &[Category] = &[
    Category::Coaching,
    Category::Mental,
    Category::Knowledge,
    Category::Medical,
    Category::Personality,
];

fn element_staff_mutate_field(
    field: &crate::fields::Field,
    raw: &mut [u8],
    entity_addr: u64,
    delta: i8,
    set_to: Option<u8>,
) -> Option<FieldEdit> {
    let loc = field.offset.as_ref()?;
    if !matches!(loc.encoding(), crate::fields::Encoding::Direct | crate::fields::Encoding::Encoded) {
        return None;
    }
    let offset = loc.offset() as usize;
    let old_raw = *raw.get(offset)?;
    let old_displayed = loc.decode_u8(old_raw);
    if old_displayed > 20 { return None; }
    let base = old_displayed.max(1) as i16;
    let new_displayed = set_to
        .map(|v| v.clamp(1, 20))
        .unwrap_or_else(|| (base + delta as i16).clamp(1, 20) as u8);
    if new_displayed == old_displayed { return None; }
    let new_raw = loc.encode_u8(new_displayed);
    raw[offset] = new_raw;
    Some(FieldEdit {
        addr: entity_addr + offset as u64,
        old_raw: vec![old_raw],
        new_raw: vec![new_raw],
        description: format!("{}: {} → {}", field.label, old_displayed, new_displayed),
    })
}

fn element_staff_apply_category(
    schemas: &'static crate::fields::VersionedSchemas,
    category: Category,
    staff: &mut StaffView,
    edits: &mut Vec<FieldEdit>,
    delta: i8,
    set_to: Option<u8>,
) {
    for field in schemas.fields_for_category(Entity::Staff, category) {
        if let Some(edit) = element_staff_mutate_field(
            &field,
            &mut staff.record.raw,
            staff.record.addr,
            delta,
            set_to,
        ) {
            edits.push(edit);
        }
    }
}

fn element_staff_apply_keys(
    schemas: &'static crate::fields::VersionedSchemas,
    keys: &[&str],
    staff: &mut StaffView,
    edits: &mut Vec<FieldEdit>,
    set_to: u8,
) {
    for key in keys {
        if let Some(field) = schemas.field(key) {
            if let Some(edit) = element_staff_mutate_field(
                field,
                &mut staff.record.raw,
                staff.record.addr,
                0,
                Some(set_to),
            ) {
                edits.push(edit);
            }
        }
    }
}

fn element_staff_set_u16(
    schemas: &'static crate::fields::VersionedSchemas,
    key: &str,
    staff: &mut StaffView,
    edits: &mut Vec<FieldEdit>,
    value: u16,
) {
    let Some(field) = schemas.field(key) else { return; };
    let Some(loc) = field.offset.as_ref() else { return; };
    if !matches!(loc.encoding(), crate::fields::Encoding::Raw | crate::fields::Encoding::RawCapped(_)) {
        return;
    }
    let offset = loc.offset() as usize;
    if offset + 2 > staff.record.raw.len() { return; }
    let old_bytes: [u8; 2] = staff.record.raw[offset..offset + 2].try_into().unwrap();
    let old = u16::from_le_bytes(old_bytes);
    if old == value { return; }
    let new_bytes = value.to_le_bytes();
    staff.record.raw[offset..offset + 2].copy_from_slice(&new_bytes);
    edits.push(FieldEdit {
        addr: staff.record.addr + offset as u64,
        old_raw: old_bytes.to_vec(),
        new_raw: new_bytes.to_vec(),
        description: format!("{}: {} → {}", field.label, old, value),
    });
}

fn show_staff_power_tools(
    schemas: &'static crate::fields::VersionedSchemas,
    ui: &mut egui::Ui,
    staff: &mut StaffView,
    edits: &mut Vec<FieldEdit>,
) {
    egui::Frame::group(ui.style())
        .fill(egui::Color32::from_rgb(20, 26, 38))
        .stroke(egui::Stroke::new(1.0, egui::Color32::from_rgb(43, 52, 70)))
        .rounding(egui::Rounding::same(4))
        .inner_margin(egui::Margin::symmetric(6, 4))
        .show(ui, |ui| {
            ui.horizontal(|ui| {
                ui.label(egui::RichText::new("STAFF POWER TOOLS").size(9.0).strong().color(egui::Color32::from_rgb(112, 177, 255)));
                ui.separator();
                ui.label(egui::RichText::new("LIVE • UNDO SAFE").size(8.0).color(egui::Color32::from_rgb(72, 210, 132)));
            });
            let enabled = crate::ui::navigation::editing_enabled(ui);
            ui.horizontal_wrapped(|ui| {
                if ui.add_enabled(enabled, egui::Button::new("−1 Core")).clicked() {
                    for c in ELEMENT_STAFF_BULK_CATEGORIES { element_staff_apply_category(schemas, *c, staff, edits, -1, None); }
                }
                if ui.add_enabled(enabled, egui::Button::new("+1 Core")).clicked() {
                    for c in ELEMENT_STAFF_BULK_CATEGORIES { element_staff_apply_category(schemas, *c, staff, edits, 1, None); }
                }
                if ui.add_enabled(enabled, egui::Button::new("20 Core")).clicked() {
                    for c in ELEMENT_STAFF_BULK_CATEGORIES { element_staff_apply_category(schemas, *c, staff, edits, 0, Some(20)); }
                }
                ui.separator();
                if ui.add_enabled(enabled, egui::Button::new("Elite Manager")).clicked() {
                    element_staff_apply_keys(schemas, &["s_tactical", "s_technical", "s_attacking", "s_defending", "s_possession", "s_motivating", "s_people_mgmt", "s_tactical_knowl", "s_determination", "s_judge_ability", "s_judge_potential"], staff, edits, 20);
                }
                if ui.add_enabled(enabled, egui::Button::new("Elite Coach")).clicked() {
                    element_staff_apply_category(schemas, Category::Coaching, staff, edits, 0, Some(20));
                    element_staff_apply_keys(schemas, &["s_motivating", "s_people_mgmt", "s_determination"], staff, edits, 20);
                }
                if ui.add_enabled(enabled, egui::Button::new("Elite Scout")).clicked() {
                    element_staff_apply_keys(schemas, &["s_judge_ability", "s_judge_potential", "s_judge_staff", "s_data_analysis", "s_adaptability", "s_determination"], staff, edits, 20);
                }
                if ui.add_enabled(enabled, egui::Button::new("Elite Physio")).clicked() {
                    element_staff_apply_keys(schemas, &["s_physiotherapy", "s_sports_science", "s_determination", "s_motivating"], staff, edits, 20);
                }
                if ui.add_enabled(enabled, egui::Button::new("Elite DoF")).clicked() {
                    element_staff_apply_keys(schemas, &["s_negotiating", "s_judge_ability", "s_judge_potential", "s_business", "s_buying_players", "s_people_mgmt", "s_determination"], staff, edits, 20);
                }
                if ui.add_enabled(enabled, egui::Button::new("Perfect Staff")).clicked() {
                    for c in ELEMENT_STAFF_BULK_CATEGORIES { element_staff_apply_category(schemas, *c, staff, edits, 0, Some(20)); }
                    element_staff_apply_keys(schemas, &["s_controversy", "s_dirtiness"], staff, edits, 1);
                }
                ui.separator();
                if ui.add_enabled(enabled, egui::Button::new("CA 200")).clicked() { element_staff_set_u16(schemas, "s_ca", staff, edits, 200); }
                if ui.add_enabled(enabled, egui::Button::new("PA 200")).clicked() { element_staff_set_u16(schemas, "s_pa", staff, edits, 200); }
            });
        });
}

'@
$staffText = $staffText.Substring(0, $staffInsert) + $staffHelpers + $staffText.Substring($staffInsert)
[IO.File]::WriteAllText($sp, $staffText, [Text.UTF8Encoding]::new($false))

Replace-Required $s @'
    header(schemas, ui, staff, "Staff");

    let has_contract = staff.contract_raw.is_some();
'@ @'
    header(schemas, ui, staff, "Staff");
    show_staff_power_tools(schemas, ui, staff, &mut edits);
    ui.add_space(3.0);

    let has_contract = staff.contract_raw.is_some();
'@

Replace-Required $s @'
    header(schemas, ui, staff, "Human Manager");
    ui.separator();

    egui::ScrollArea::vertical().show(ui, |ui| {
'@ @'
    header(schemas, ui, staff, "Human Manager");
    ui.separator();

    egui::ScrollArea::vertical().show(ui, |ui| {
        show_staff_power_tools(schemas, ui, staff, &mut edits);
        ui.add_space(3.0);
'@

# ============================== CLUB ==========================================
$c = 'src/ui/club_panel.rs'
$cp = Join-Path $SourceRoot $c
$clubText = [IO.File]::ReadAllText($cp)
$clubInsert = $clubText.IndexOf('fn show_overview(')
if ($clubInsert -lt 0) { throw 'v2.5: club show_overview insertion boundary not found' }

$clubHelpers = @'
fn element_club_set_u8(
    schemas: &'static crate::fields::VersionedSchemas,
    club: &mut ClubView,
    edits: &mut Vec<FieldEdit>,
    key: &str,
    value: u8,
) {
    let Some((container, offset)) = sub_location(schemas, key) else { return; };
    let Some((buf, base)) = club.sub_record_mut(container) else { return; };
    let Some(old) = buf.get(offset).copied() else { return; };
    if old == value { return; }
    buf[offset] = value;
    let label = schemas.field(key).map(|f| f.label).unwrap_or(key);
    edits.push(FieldEdit {
        addr: base + offset as u64,
        old_raw: vec![old],
        new_raw: vec![value],
        description: format!("{}: {} → {}", label, old, value),
    });
}

fn element_club_set_u16(
    schemas: &'static crate::fields::VersionedSchemas,
    club: &mut ClubView,
    edits: &mut Vec<FieldEdit>,
    key: &str,
    value: u16,
) {
    let Some((container, offset)) = sub_location(schemas, key) else { return; };
    let Some((buf, base)) = club.sub_record_mut(container) else { return; };
    if offset + 2 > buf.len() { return; }
    let old_bytes: [u8; 2] = buf[offset..offset + 2].try_into().unwrap();
    let old = u16::from_le_bytes(old_bytes);
    if old == value { return; }
    let new_bytes = value.to_le_bytes();
    buf[offset..offset + 2].copy_from_slice(&new_bytes);
    let label = schemas.field(key).map(|f| f.label).unwrap_or(key);
    edits.push(FieldEdit {
        addr: base + offset as u64,
        old_raw: old_bytes.to_vec(),
        new_raw: new_bytes.to_vec(),
        description: format!("{}: {} → {}", label, old, value),
    });
}

fn element_club_set_u32(
    schemas: &'static crate::fields::VersionedSchemas,
    club: &mut ClubView,
    edits: &mut Vec<FieldEdit>,
    key: &str,
    value: u32,
) {
    let Some((container, offset)) = sub_location(schemas, key) else { return; };
    let Some((buf, base)) = club.sub_record_mut(container) else { return; };
    if offset + 4 > buf.len() { return; }
    let old_bytes: [u8; 4] = buf[offset..offset + 4].try_into().unwrap();
    let old = u32::from_le_bytes(old_bytes);
    if old == value { return; }
    let new_bytes = value.to_le_bytes();
    buf[offset..offset + 4].copy_from_slice(&new_bytes);
    let label = schemas.field(key).map(|f| f.label).unwrap_or(key);
    edits.push(FieldEdit {
        addr: base + offset as u64,
        old_raw: old_bytes.to_vec(),
        new_raw: new_bytes.to_vec(),
        description: format!("{}: {} → {}", label, old, value),
    });
}

fn element_club_max_facilities(
    schemas: &'static crate::fields::VersionedSchemas,
    club: &mut ClubView,
    edits: &mut Vec<FieldEdit>,
) {
    for key in ["c_training", "c_youth_fac", "c_youth_coach", "c_youth_coach_fin", "c_youth_recruit", "c_youth_recruit_fin", "c_corporate"] {
        element_club_set_u8(schemas, club, edits, key, 20);
    }
}

fn element_club_balanced_fans(
    schemas: &'static crate::fields::VersionedSchemas,
    club: &mut ClubView,
    edits: &mut Vec<FieldEdit>,
) {
    for (key, value) in [
        ("c_sup_hardcore", 15u8),
        ("c_sup_core", 30u8),
        ("c_sup_family", 20u8),
        ("c_sup_fair_weather", 15u8),
        ("c_sup_casual", 10u8),
        ("c_sup_other", 10u8),
    ] {
        element_club_set_u8(schemas, club, edits, key, value);
    }
}

fn element_club_max_supporters(
    schemas: &'static crate::fields::VersionedSchemas,
    club: &mut ClubView,
    edits: &mut Vec<FieldEdit>,
) {
    for key in ["c_sup_loyalty", "c_sup_passion", "c_sup_patience", "c_sup_affluence", "c_sup_temperament", "c_sup_expectations"] {
        element_club_set_u8(schemas, club, edits, key, 20);
    }
}

fn element_club_rich(
    schemas: &'static crate::fields::VersionedSchemas,
    club: &mut ClubView,
    edits: &mut Vec<FieldEdit>,
) {
    element_club_set_u32(schemas, club, edits, "c_balance", 2_000_000_000);
    element_club_set_u32(schemas, club, edits, "c_transfer_budget", 1_000_000_000);
    element_club_set_u32(schemas, club, edits, "c_wage_budget", 20_000_000);
}

fn show_club_power_tools(
    schemas: &'static crate::fields::VersionedSchemas,
    ui: &mut egui::Ui,
    club: &mut ClubView,
    edits: &mut Vec<FieldEdit>,
) {
    egui::Frame::group(ui.style())
        .fill(egui::Color32::from_rgb(20, 26, 38))
        .stroke(egui::Stroke::new(1.0, egui::Color32::from_rgb(43, 52, 70)))
        .rounding(egui::Rounding::same(4))
        .inner_margin(egui::Margin::symmetric(6, 3))
        .show(ui, |ui| {
            ui.horizontal_wrapped(|ui| {
                ui.label(egui::RichText::new("CLUB POWER TOOLS").size(9.0).strong().color(egui::Color32::from_rgb(112, 177, 255)));
                ui.separator();
                let enabled = navigation::editing_enabled(ui);
                if ui.add_enabled(enabled, egui::Button::new("Max Facilities")).clicked() {
                    element_club_max_facilities(schemas, club, edits);
                }
                if ui.add_enabled(enabled, egui::Button::new("Rep 10000")).clicked() {
                    element_club_set_u16(schemas, club, edits, "c_reputation", 10_000);
                }
                if ui.add_enabled(enabled, egui::Button::new("Rich Club")).on_hover_text("Balance £2B • Transfer £1B • Wage budget £20M/w").clicked() {
                    element_club_rich(schemas, club, edits);
                }
                if ui.add_enabled(enabled, egui::Button::new("Balanced Fanbase")).on_hover_text("Sets supporter profile percentages to a 100% balanced distribution").clicked() {
                    element_club_balanced_fans(schemas, club, edits);
                }
                if ui.add_enabled(enabled, egui::Button::new("Max Supporters")).on_hover_text("Literal max: supporter attributes to 20").clicked() {
                    element_club_max_supporters(schemas, club, edits);
                }
                if ui.add_enabled(enabled, egui::Button::new("ALL-IN-ONE CLUB")).clicked() {
                    element_club_max_facilities(schemas, club, edits);
                    element_club_set_u16(schemas, club, edits, "c_reputation", 10_000);
                    element_club_rich(schemas, club, edits);
                    element_club_balanced_fans(schemas, club, edits);
                    element_club_max_supporters(schemas, club, edits);
                }
            });
        });
}

'@
$clubText = $clubText.Substring(0, $clubInsert) + $clubHelpers + $clubText.Substring($clubInsert)
[IO.File]::WriteAllText($cp, $clubText, [Text.UTF8Encoding]::new($false))

Replace-Required $c @'
    // Club navigation is rendered in the contextual application rail (Element v1.6).
'@ @'
    // Club navigation is rendered in the contextual application rail (Element v1.6).
    show_club_power_tools(schemas, ui, club, &mut edits);
    ui.add_space(3.0);
'@

Write-Host 'Element v2.5 staff + club power tools applied successfully.'
