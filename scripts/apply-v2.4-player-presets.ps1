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
# Element v2.4 PLAYER PRESETS
# - Safe mapped-field presets only.
# - CA/PA power buttons use the already-proven player raw fields.
# - Automatic pre-preset snapshot + mapped-only Restore Last.
# - No unknown FM27 structures are written.
# -----------------------------------------------------------------------------
$p = 'src/ui/player_panel.rs'
$pp = Join-Path $SourceRoot $p
$text = [IO.File]::ReadAllText($pp)

$helperAt = $text.IndexOf('fn show_player_power_rail(')
if ($helperAt -lt 0) { throw 'v2.4: show_player_power_rail marker not found' }

$helpers = @'
fn element_set_raw_u16(
    schemas: &'static crate::fields::VersionedSchemas,
    key: &str,
    raw: &mut [u8],
    entity_addr: u64,
    edits: &mut Vec<FieldEdit>,
    new_value: u16,
) {
    let Some(field) = schemas.field(key) else { return; };
    let Some(loc) = field.offset.as_ref() else { return; };
    if !matches!(loc.encoding(), crate::fields::Encoding::Raw | crate::fields::Encoding::RawCapped(_)) { return; }
    let offset = loc.offset() as usize;
    if offset + 2 > raw.len() { return; }
    let old_bytes = [raw[offset], raw[offset + 1]];
    let old_value = u16::from_le_bytes(old_bytes);
    let capped = match loc.encoding() {
        crate::fields::Encoding::RawCapped(max) => new_value.min(max),
        _ => new_value,
    };
    if capped == old_value { return; }
    let new_bytes = capped.to_le_bytes();
    raw[offset..offset + 2].copy_from_slice(&new_bytes);
    edits.push(FieldEdit {
        addr: entity_addr + offset as u64,
        old_raw: old_bytes.to_vec(),
        new_raw: new_bytes.to_vec(),
        description: format!("{}: {} → {}", field.label, old_value, capped),
    });
}

fn element_read_raw_u16(
    schemas: &'static crate::fields::VersionedSchemas,
    key: &str,
    raw: &[u8],
) -> Option<u16> {
    let field = schemas.field(key)?;
    let loc = field.offset.as_ref()?;
    if !matches!(loc.encoding(), crate::fields::Encoding::Raw | crate::fields::Encoding::RawCapped(_)) { return None; }
    let offset = loc.offset() as usize;
    if offset + 2 > raw.len() { return None; }
    Some(u16::from_le_bytes([raw[offset], raw[offset + 1]]))
}

fn element_snapshot_before_preset(ui: &mut egui::Ui, addr: u64, raw: &[u8]) {
    ui.data_mut(|d| d.insert_temp(egui::Id::new(("element_preset_snapshot", addr)), raw.to_vec()));
}

fn element_restore_last_snapshot(
    schemas: &'static crate::fields::VersionedSchemas,
    snapshot: &[u8],
    raw: &mut [u8],
    entity_addr: u64,
    edits: &mut Vec<FieldEdit>,
) {
    for category in ELEMENT_BULK_CATEGORIES {
        for field in schemas.fields_for_category(Entity::Player, *category) {
            let Some(loc) = field.offset.as_ref() else { continue; };
            if !matches!(loc.encoding(), crate::fields::Encoding::Direct | crate::fields::Encoding::Encoded) { continue; }
            let off = loc.offset() as usize;
            let Some(target_raw) = snapshot.get(off).copied() else { continue; };
            let target = loc.decode_u8(target_raw);
            if target <= 20 {
                if let Some(edit) = element_mutate_attr(&field, raw, entity_addr, 0, Some(target.max(1))) {
                    edits.push(edit);
                }
            }
        }
    }
    for key in ["p_ca", "p_pa"] {
        if let Some(target) = element_read_raw_u16(schemas, key, snapshot) {
            element_set_raw_u16(schemas, key, raw, entity_addr, edits, target);
        }
    }
}

fn element_apply_perfect_player(
    schemas: &'static crate::fields::VersionedSchemas,
    raw: &mut [u8],
    addr: u64,
    edits: &mut Vec<FieldEdit>,
) {
    for category in ELEMENT_BULK_CATEGORIES {
        element_apply_category(schemas, *category, raw, addr, edits, 0, Some(20));
    }
    element_apply_keys(schemas, &["injury_proneness", "p_dirtiness", "p_controversy"], raw, addr, edits, 0, Some(1));
    element_set_raw_u16(schemas, "p_ca", raw, addr, edits, 200);
    element_set_raw_u16(schemas, "p_pa", raw, addr, edits, 200);
}

fn element_apply_wonderkid(
    schemas: &'static crate::fields::VersionedSchemas,
    raw: &mut [u8],
    addr: u64,
    edits: &mut Vec<FieldEdit>,
) {
    element_set_raw_u16(schemas, "p_pa", raw, addr, edits, 200);
    element_apply_keys(
        schemas,
        &["p_professionalism", "p_ambition", "determination", "natural_fitness", "work_rate", "consistency", "important_matches"],
        raw, addr, edits, 0, Some(20),
    );
    element_apply_keys(schemas, &["injury_proneness", "p_dirtiness", "p_controversy"], raw, addr, edits, 0, Some(1));
}

fn element_apply_named_role_20(
    schemas: &'static crate::fields::VersionedSchemas,
    role_name: &str,
    raw: &mut [u8],
    addr: u64,
    edits: &mut Vec<FieldEdit>,
) {
    if let Some((_, keys)) = ELEMENT_ROLE_PRESETS.iter().find(|(name, _)| *name == role_name) {
        element_apply_keys(schemas, keys, raw, addr, edits, 0, Some(20));
    }
}

fn element_apply_playmaker(
    schemas: &'static crate::fields::VersionedSchemas,
    raw: &mut [u8],
    addr: u64,
    edits: &mut Vec<FieldEdit>,
) {
    element_apply_keys(
        schemas,
        &["passing", "first_touch", "technique", "vision", "decisions", "composure", "flair", "anticipation", "teamwork", "off_the_ball"],
        raw, addr, edits, 0, Some(20),
    );
}

fn element_apply_mental_monster(
    schemas: &'static crate::fields::VersionedSchemas,
    raw: &mut [u8],
    addr: u64,
    edits: &mut Vec<FieldEdit>,
) {
    element_apply_category(schemas, Category::Mental, raw, addr, edits, 0, Some(20));
    element_apply_keys(
        schemas,
        &["p_adaptability", "p_ambition", "p_loyalty", "p_pressure", "p_professionalism", "p_sportsmanship", "p_temperament"],
        raw, addr, edits, 0, Some(20),
    );
    element_apply_keys(schemas, &["p_controversy"], raw, addr, edits, 0, Some(1));
}

'@

$text = $text.Substring(0, $helperAt) + $helpers + $text.Substring($helperAt)
[IO.File]::WriteAllText($pp, $text, [Text.UTF8Encoding]::new($false))

# Extend Ability card with CA/PA power buttons.
Replace-Required $p @'
        ui.add(egui::ProgressBar::new(progress).desired_width(ui.available_width()).text(format!("Development gap {gap}")));
    };
'@ @'
        ui.add(egui::ProgressBar::new(progress).desired_width(ui.available_width()).text(format!("Development gap {gap}")));
        let enabled = crate::ui::navigation::editing_enabled(ui);
        ui.horizontal(|ui| {
            if ui.add_enabled(enabled, egui::Button::new("CA 200").min_size(egui::vec2(0.0, 17.0))).clicked() {
                element_set_raw_u16(schemas, "p_ca", &mut player.raw, addr, edits, 200);
            }
            if ui.add_enabled(enabled, egui::Button::new("PA 200").min_size(egui::vec2(0.0, 17.0))).clicked() {
                element_set_raw_u16(schemas, "p_pa", &mut player.raw, addr, edits, 200);
            }
            if ui.add_enabled(enabled, egui::Button::new("CA=PA").min_size(egui::vec2(0.0, 17.0))).clicked() {
                let target = element_read_raw_u16(schemas, "p_pa", &player.raw).unwrap_or(pa as u16);
                element_set_raw_u16(schemas, "p_ca", &mut player.raw, addr, edits, target);
            }
        });
    };
'@

# Add compact FMRTE-style player preset card after All Attributes.
Replace-Required $p @'
    rail_card(ui, "All Attributes", &mut all_attrs);
}
'@ @'
    rail_card(ui, "All Attributes", &mut all_attrs);
    ui.add_space(3.0);

    let mut presets = |ui: &mut egui::Ui| {
        let enabled = crate::ui::navigation::editing_enabled(ui);
        let button = |ui: &mut egui::Ui, label: &str| {
            ui.add_enabled(enabled, egui::Button::new(egui::RichText::new(label).size(8.5)).min_size(egui::vec2(ui.available_width(), 17.0)))
        };

        if button(ui, "PERFECT PLAYER").on_hover_text("CA/PA 200; mapped positive attributes 20; Injury Proneness, Dirtiness and Controversy 1").clicked() {
            element_snapshot_before_preset(ui, addr, &player.raw);
            element_apply_perfect_player(schemas, &mut player.raw, addr, edits);
        }
        if button(ui, "Wonderkid").on_hover_text("PA 200 + elite development personality/core; age and CA are preserved").clicked() {
            element_snapshot_before_preset(ui, addr, &player.raw);
            element_apply_wonderkid(schemas, &mut player.raw, addr, edits);
        }
        ui.horizontal(|ui| {
            if ui.add_enabled(enabled, egui::Button::new(egui::RichText::new("Physical Beast").size(8.0))).clicked() {
                element_snapshot_before_preset(ui, addr, &player.raw);
                element_apply_category(schemas, Category::Physical, &mut player.raw, addr, edits, 0, Some(20));
            }
            if ui.add_enabled(enabled, egui::Button::new(egui::RichText::new("Mental Monster").size(8.0))).clicked() {
                element_snapshot_before_preset(ui, addr, &player.raw);
                element_apply_mental_monster(schemas, &mut player.raw, addr, edits);
            }
        });
        ui.horizontal(|ui| {
            if ui.add_enabled(enabled, egui::Button::new(egui::RichText::new("Playmaker").size(8.0))).clicked() {
                element_snapshot_before_preset(ui, addr, &player.raw);
                element_apply_playmaker(schemas, &mut player.raw, addr, edits);
            }
            if ui.add_enabled(enabled, egui::Button::new(egui::RichText::new("Elite ST").size(8.0))).clicked() {
                element_snapshot_before_preset(ui, addr, &player.raw);
                element_apply_named_role_20(schemas, "Striker", &mut player.raw, addr, edits);
            }
        });
        ui.horizontal(|ui| {
            if ui.add_enabled(enabled, egui::Button::new(egui::RichText::new("Elite CB").size(8.0))).clicked() {
                element_snapshot_before_preset(ui, addr, &player.raw);
                element_apply_named_role_20(schemas, "Central Defender", &mut player.raw, addr, edits);
            }
            if ui.add_enabled(enabled, egui::Button::new(egui::RichText::new("Elite GK").size(8.0))).clicked() {
                element_snapshot_before_preset(ui, addr, &player.raw);
                element_apply_named_role_20(schemas, "Goalkeeper", &mut player.raw, addr, edits);
            }
        });

        ui.separator();
        if ui.add_enabled(enabled, egui::Button::new(egui::RichText::new("Save Snapshot").size(8.5)).min_size(egui::vec2(ui.available_width(), 17.0))).clicked() {
            element_snapshot_before_preset(ui, addr, &player.raw);
        }
        let snapshot_id = egui::Id::new(("element_preset_snapshot", addr));
        let has_snapshot = ui.data_mut(|d| d.get_temp::<Vec<u8>>(snapshot_id).is_some());
        if ui.add_enabled(enabled && has_snapshot, egui::Button::new(egui::RichText::new("Restore Last").size(8.5)).min_size(egui::vec2(ui.available_width(), 17.0))).on_hover_text("Restores mapped player attributes + CA/PA from the last preset snapshot").clicked() {
            if let Some(snapshot) = ui.data_mut(|d| d.get_temp::<Vec<u8>>(snapshot_id)) {
                element_restore_last_snapshot(schemas, &snapshot, &mut player.raw, addr, edits);
            }
        }
    };
    rail_card(ui, "Player Presets", &mut presets);
}
'@

Write-Host 'Element v2.4 player presets + snapshot restore applied successfully.'
