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
# Element v2.3 PLAYER POWER TOOLS
# - FMRTE-inspired four-column player attribute matrix + fixed right utility rail.
# - +/-/20 per mapped category.
# - -1/+1/20 all mapped football attributes.
# - Local Element Best Role scoring + role-specific -1/+1/20 presets.
# All mutations emit normal FieldEdit records, so existing bridge writes, undo and
# change-history behavior remain the single write path.
# -----------------------------------------------------------------------------
$p = 'src/ui/player_panel.rs'
$pp = Join-Path $SourceRoot $p

Replace-Required $p @'
    // Element v2.0 one-page player attribute matrix. All categories remain
    // live-editable; the old second row is folded into stacked compact cards.
    ui.spacing_mut().item_spacing = egui::vec2(4.0, 2.0);
    ui.columns(6, |cols| {
        compact_player_attribute_card(schemas, &mut cols[0], "Technical", Category::Technical, &mut player.raw, addr, edits);
        cols[0].add_space(1.0);
        compact_player_attribute_card(schemas, &mut cols[0], "Set Pieces", Category::SetPieces, &mut player.raw, addr, edits);

        compact_player_attribute_card(schemas, &mut cols[1], "Mental", Category::Mental, &mut player.raw, addr, edits);
        compact_player_attribute_card(schemas, &mut cols[2], "Physical", Category::Physical, &mut player.raw, addr, edits);

        compact_player_attribute_card(schemas, &mut cols[3], "Hidden", Category::Hidden, &mut player.raw, addr, edits);
        cols[3].add_space(1.0);
        compact_player_attribute_card(schemas, &mut cols[3], "Foot Ability", Category::Footedness, &mut player.raw, addr, edits);

        compact_player_attribute_card(schemas, &mut cols[4], "Personality", Category::Personality, &mut player.raw, addr, edits);
        compact_player_attribute_card(schemas, &mut cols[5], "Goalkeeping", Category::Goalkeeping, &mut player.raw, addr, edits);
    });
'@ @'
    // Element v2.3: FMRTE-inspired attribute workspace. Four dense columns keep
    // all outfield information visible while the right rail hosts role/preset tools.
    ui.spacing_mut().item_spacing = egui::vec2(4.0, 1.0);
    ui.horizontal_top(|ui| {
        let rail_width = 222.0;
        let main_width = (ui.available_width() - rail_width - 6.0).max(620.0);

        ui.allocate_ui_with_layout(
            egui::vec2(main_width, 0.0),
            egui::Layout::top_down(egui::Align::Min),
            |ui| {
                ui.columns(4, |cols| {
                    let mode_id = egui::Id::new(("element_tech_gk", addr));
                    let mut show_gk = cols[0].data_mut(|d| d.get_temp::<bool>(mode_id).unwrap_or(false));
                    cols[0].horizontal(|ui| {
                        if ui.selectable_label(!show_gk, "Technical").clicked() { show_gk = false; }
                        if ui.selectable_label(show_gk, "Goalkeeper").clicked() { show_gk = true; }
                    });
                    cols[0].data_mut(|d| d.insert_temp(mode_id, show_gk));
                    if show_gk {
                        power_attribute_card(schemas, &mut cols[0], "Goalkeeping", Category::Goalkeeping, &mut player.raw, addr, edits);
                    } else {
                        power_attribute_card(schemas, &mut cols[0], "Technical", Category::Technical, &mut player.raw, addr, edits);
                        cols[0].add_space(1.0);
                        power_attribute_card(schemas, &mut cols[0], "Set Pieces", Category::SetPieces, &mut player.raw, addr, edits);
                    }

                    power_attribute_card(schemas, &mut cols[1], "Mental", Category::Mental, &mut player.raw, addr, edits);

                    power_attribute_card(schemas, &mut cols[2], "Physical", Category::Physical, &mut player.raw, addr, edits);
                    cols[2].add_space(1.0);
                    power_attribute_card(schemas, &mut cols[2], "Hidden", Category::Hidden, &mut player.raw, addr, edits);

                    power_attribute_card(schemas, &mut cols[3], "Personality", Category::Personality, &mut player.raw, addr, edits);
                    cols[3].add_space(1.0);
                    power_attribute_card(schemas, &mut cols[3], "Foot Ability", Category::Footedness, &mut player.raw, addr, edits);
                });
            },
        );

        ui.add_space(4.0);
        ui.allocate_ui_with_layout(
            egui::vec2(rail_width, 0.0),
            egui::Layout::top_down(egui::Align::Min),
            |ui| show_player_power_rail(schemas, ui, player, addr, edits),
        );
    });
'@

# Insert bulk-edit and role-preset helpers immediately before the v2.0 compact card helper.
$text = [IO.File]::ReadAllText($pp)
$helperAt = $text.IndexOf('fn compact_player_attribute_card(')
if ($helperAt -lt 0) { throw 'v2.3: compact player attribute helper marker not found' }
$helpers = @'
const ELEMENT_ROLE_PRESETS: &[(&str, &[&str])] = &[
    ("Goalkeeper", &["handling", "aerial_reach", "command_of_area", "communication", "kicking", "throwing", "one_on_ones", "reflexes", "rushing_out", "positioning", "decisions", "concentration", "agility"]),
    ("Central Defender", &["heading", "marking", "tackling", "positioning", "concentration", "anticipation", "bravery", "strength", "jumping_reach"]),
    ("Full Back", &["crossing", "tackling", "marking", "positioning", "work_rate", "teamwork", "stamina", "pace", "acceleration"]),
    ("Wing Back", &["crossing", "dribbling", "first_touch", "passing", "tackling", "work_rate", "stamina", "pace", "acceleration", "off_the_ball"]),
    ("Defensive Midfielder", &["tackling", "marking", "positioning", "decisions", "anticipation", "concentration", "passing", "teamwork", "work_rate", "strength"]),
    ("Midfielder", &["passing", "first_touch", "technique", "decisions", "vision", "teamwork", "work_rate", "stamina", "anticipation"]),
    ("Wide Midfielder", &["crossing", "dribbling", "passing", "work_rate", "teamwork", "stamina", "pace", "acceleration"]),
    ("Winger", &["crossing", "dribbling", "first_touch", "technique", "pace", "acceleration", "agility", "flair", "off_the_ball"]),
    ("Attacking Midfielder", &["passing", "first_touch", "technique", "dribbling", "vision", "decisions", "flair", "off_the_ball", "composure"]),
    ("Striker", &["finishing", "first_touch", "heading", "composure", "anticipation", "off_the_ball", "acceleration", "pace", "strength", "jumping_reach"]),
];

const ELEMENT_BULK_CATEGORIES: &[Category] = &[
    Category::Technical,
    Category::SetPieces,
    Category::Mental,
    Category::Physical,
    Category::Goalkeeping,
    Category::Hidden,
    Category::Footedness,
    Category::Personality,
];

fn element_attr_value(
    schemas: &'static crate::fields::VersionedSchemas,
    raw: &[u8],
    key: &str,
) -> Option<u8> {
    let field = schemas.field(key)?;
    let loc = field.offset.as_ref()?;
    if !matches!(loc.encoding(), crate::fields::Encoding::Direct | crate::fields::Encoding::Encoded) {
        return None;
    }
    let offset = loc.offset() as usize;
    let displayed = loc.decode_u8(*raw.get(offset)?);
    (displayed <= 20).then_some(displayed.max(1))
}

fn element_mutate_attr(
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

fn element_apply_category(
    schemas: &'static crate::fields::VersionedSchemas,
    category: Category,
    raw: &mut [u8],
    entity_addr: u64,
    edits: &mut Vec<FieldEdit>,
    delta: i8,
    set_to: Option<u8>,
) {
    for field in schemas.fields_for_category(Entity::Player, category) {
        if let Some(edit) = element_mutate_attr(&field, raw, entity_addr, delta, set_to) {
            edits.push(edit);
        }
    }
}

fn element_apply_keys(
    schemas: &'static crate::fields::VersionedSchemas,
    keys: &[&str],
    raw: &mut [u8],
    entity_addr: u64,
    edits: &mut Vec<FieldEdit>,
    delta: i8,
    set_to: Option<u8>,
) {
    for key in keys {
        if let Some(field) = schemas.field(key) {
            if let Some(edit) = element_mutate_attr(field, raw, entity_addr, delta, set_to) {
                edits.push(edit);
            }
        }
    }
}

fn element_best_role_index(
    schemas: &'static crate::fields::VersionedSchemas,
    raw: &[u8],
) -> usize {
    let mut best_index = 0usize;
    let mut best_score = -1.0f32;
    for (index, (_, keys)) in ELEMENT_ROLE_PRESETS.iter().enumerate() {
        let mut sum = 0u32;
        let mut count = 0u32;
        for key in *keys {
            if let Some(v) = element_attr_value(schemas, raw, key) {
                sum += v as u32;
                count += 1;
            }
        }
        if count > 0 {
            let score = sum as f32 / count as f32;
            if score > best_score {
                best_score = score;
                best_index = index;
            }
        }
    }
    best_index
}

fn power_attribute_card(
    schemas: &'static crate::fields::VersionedSchemas,
    ui: &mut egui::Ui,
    heading: &str,
    category: Category,
    raw: &mut [u8],
    addr: u64,
    edits: &mut Vec<FieldEdit>,
) {
    egui::Frame::group(ui.style())
        .fill(egui::Color32::from_rgb(25, 31, 45))
        .stroke(egui::Stroke::new(1.0, egui::Color32::from_rgb(41, 49, 66)))
        .rounding(egui::Rounding::same(3))
        .inner_margin(egui::Margin::symmetric(4, 2))
        .show(ui, |ui| {
            ui.horizontal(|ui| {
                ui.label(egui::RichText::new(heading).size(9.5).strong().color(egui::Color32::from_rgb(225, 232, 245)));
                ui.with_layout(egui::Layout::right_to_left(egui::Align::Center), |ui| {
                    let enabled = crate::ui::navigation::editing_enabled(ui);
                    if ui.add_enabled(enabled, egui::Button::new("20").min_size(egui::vec2(20.0, 15.0))).on_hover_text("Set this category to 20").clicked() {
                        element_apply_category(schemas, category, raw, addr, edits, 0, Some(20));
                    }
                    if ui.add_enabled(enabled, egui::Button::new("+").min_size(egui::vec2(18.0, 15.0))).on_hover_text("+1 to this category").clicked() {
                        element_apply_category(schemas, category, raw, addr, edits, 1, None);
                    }
                    if ui.add_enabled(enabled, egui::Button::new("−").min_size(egui::vec2(18.0, 15.0))).on_hover_text("-1 from this category").clicked() {
                        element_apply_category(schemas, category, raw, addr, edits, -1, None);
                    }
                });
            });
            ui.separator();
            field_widget::category_column(schemas, ui, "", Entity::Player, category, raw, addr, edits);
        });
}

fn show_player_power_rail(
    schemas: &'static crate::fields::VersionedSchemas,
    ui: &mut egui::Ui,
    player: &mut PlayerRecord,
    addr: u64,
    edits: &mut Vec<FieldEdit>,
) {
    let rail_card = |ui: &mut egui::Ui, title: &str, add: &mut dyn FnMut(&mut egui::Ui)| {
        egui::Frame::group(ui.style())
            .fill(egui::Color32::from_rgb(22, 28, 40))
            .stroke(egui::Stroke::new(1.0, egui::Color32::from_rgb(42, 51, 69)))
            .rounding(egui::Rounding::same(4))
            .inner_margin(egui::Margin::symmetric(6, 4))
            .show(ui, |ui| {
                ui.label(egui::RichText::new(title).size(10.0).strong().color(egui::Color32::from_rgb(225, 232, 245)));
                ui.separator();
                add(ui);
            });
    };

    let mut ability = |ui: &mut egui::Ui| {
        let ca = player.field_u8("p_ca").unwrap_or(0);
        let pa = player.field_u8("p_pa").unwrap_or(0);
        let gap = pa.saturating_sub(ca);
        ui.horizontal(|ui| {
            ui.label(egui::RichText::new("CA / PA").size(9.5));
            ui.with_layout(egui::Layout::right_to_left(egui::Align::Center), |ui| {
                ui.label(egui::RichText::new(format!("{ca} / {pa}")).strong());
            });
        });
        let progress = if pa > 0 { (ca as f32 / pa as f32).clamp(0.0, 1.0) } else { 0.0 };
        ui.add(egui::ProgressBar::new(progress).desired_width(ui.available_width()).text(format!("Development gap {gap}")));
    };
    rail_card(ui, "Ability", &mut ability);
    ui.add_space(3.0);

    let best_index = element_best_role_index(schemas, &player.raw);
    let role_id = egui::Id::new(("element_role_preset", addr));
    let mut selected = ui.data_mut(|d| d.get_temp::<usize>(role_id).unwrap_or(best_index));
    if selected >= ELEMENT_ROLE_PRESETS.len() { selected = best_index; }

    let mut roles = |ui: &mut egui::Ui| {
        ui.label(egui::RichText::new(format!("Element Best Role: {}", ELEMENT_ROLE_PRESETS[best_index].0)).size(9.0).strong().color(egui::Color32::from_rgb(104, 166, 255)));
        egui::ComboBox::from_id_salt(("element_role_combo", addr))
            .selected_text(ELEMENT_ROLE_PRESETS[selected].0)
            .width(ui.available_width())
            .show_ui(ui, |ui| {
                for (index, (name, _)) in ELEMENT_ROLE_PRESETS.iter().enumerate() {
                    ui.selectable_value(&mut selected, index, *name);
                }
            });
        ui.data_mut(|d| d.insert_temp(role_id, selected));
        let enabled = crate::ui::navigation::editing_enabled(ui);
        let keys = ELEMENT_ROLE_PRESETS[selected].1;
        ui.horizontal(|ui| {
            if ui.add_enabled(enabled, egui::Button::new("−1 Role")).clicked() {
                element_apply_keys(schemas, keys, &mut player.raw, addr, edits, -1, None);
            }
            if ui.add_enabled(enabled, egui::Button::new("+1 Role")).clicked() {
                element_apply_keys(schemas, keys, &mut player.raw, addr, edits, 1, None);
            }
        });
        if ui.add_enabled(enabled, egui::Button::new("20 Selected Role").min_size(egui::vec2(ui.available_width(), 18.0))).clicked() {
            element_apply_keys(schemas, keys, &mut player.raw, addr, edits, 0, Some(20));
        }
    };
    rail_card(ui, "Role Presets", &mut roles);
    ui.add_space(3.0);

    let mut all_attrs = |ui: &mut egui::Ui| {
        let enabled = crate::ui::navigation::editing_enabled(ui);
        ui.horizontal(|ui| {
            if ui.add_enabled(enabled, egui::Button::new("−1 ALL")).clicked() {
                for category in ELEMENT_BULK_CATEGORIES { element_apply_category(schemas, *category, &mut player.raw, addr, edits, -1, None); }
            }
            if ui.add_enabled(enabled, egui::Button::new("+1 ALL")).clicked() {
                for category in ELEMENT_BULK_CATEGORIES { element_apply_category(schemas, *category, &mut player.raw, addr, edits, 1, None); }
            }
        });
        if ui.add_enabled(enabled, egui::Button::new("20 ALL ATTRIBUTES").min_size(egui::vec2(ui.available_width(), 19.0))).on_hover_text("Literal max: sets every mapped 1-20 player attribute, including hidden/personality, to 20").clicked() {
            for category in ELEMENT_BULK_CATEGORIES { element_apply_category(schemas, *category, &mut player.raw, addr, edits, 0, Some(20)); }
        }
        ui.label(egui::RichText::new("All bulk edits use the normal live-write + Undo path.").size(8.0).color(egui::Color32::from_rgb(139, 157, 188)));
    };
    rail_card(ui, "All Attributes", &mut all_attrs);
}

'@
$text = $text.Substring(0, $helperAt) + $helpers + $text.Substring($helperAt)
[IO.File]::WriteAllText($pp, $text, [Text.UTF8Encoding]::new($false))

Write-Host 'Element v2.3 player power tools + role presets applied successfully.'
