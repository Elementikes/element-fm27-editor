from pathlib import Path

root = Path.cwd()


def rd(path):
    p = root / path
    if not p.exists():
        raise SystemExit(f"v7.2 missing {path}")
    return p.read_text(encoding="utf-8")


def wr(path, text):
    (root / path).write_text(text, encoding="utf-8")


def one(text, old, new, label):
    if old not in text:
        raise SystemExit(f"v7.2 marker missing: {label}")
    return text.replace(old, new, 1)

p = "src/ui/player_panel.rs"
t = rd(p)

if "    PowerTools,\n" not in t:
    t = one(t, "    Contract,\n}", "    Contract,\n    PowerTools,\n}", "PlayerTab enum")
    t = one(
        t,
        '        ui.selectable_value(tab, PlayerTab::Contract, "Contract");\n',
        '        ui.selectable_value(tab, PlayerTab::Contract, "Contract");\n        ui.selectable_value(tab, PlayerTab::PowerTools, "Power Tools");\n',
        "Power Tools tab button",
    )
    contract_arm = '''        PlayerTab::Contract => {
            egui::ScrollArea::vertical()
                .id_salt("player_contract")
                .show(ui, |ui| {
                    show_contract(schemas, ui, player, &mut edits);
                });
        }
'''
    power_arm = contract_arm + '''        PlayerTab::PowerTools => {
            egui::ScrollArea::vertical()
                .id_salt("player_power_tools")
                .show(ui, |ui| {
                    show_player_power_tools(schemas, ui, player, addr, &mut edits);
                });
        }
'''
    t = one(t, contract_arm, power_arm, "Power Tools match arm")

if "fn show_player_power_tools(" not in t:
    marker = "// ---------------------------------------------------------------------------\n// Overview\n// ---------------------------------------------------------------------------\n"
    fn = r'''fn push_max_category_edits(
    schemas: &'static fields::VersionedSchemas,
    player: &mut PlayerRecord,
    addr: u64,
    category: Category,
    label: &str,
    edits: &mut Vec<FieldEdit>,
) -> usize {
    let mut changed = 0usize;
    for f in schemas.fields_for_category(Entity::Player, category) {
        let Some(loc) = f.offset else { continue; };
        let off = loc.offset() as usize;
        let Some(&old) = player.raw.get(off) else { continue; };
        let new = loc.encode_u8(20);
        if old == new { continue; }
        player.raw[off] = new;
        let physical = addr + player::player_phys_offset(schemas, loc.offset(), player.person_shift);
        edits.push(FieldEdit {
            addr: physical,
            old_raw: vec![old],
            new_raw: vec![new],
            description: format!("{} • {} → 20", label, f.label),
            presentation: None,
        });
        changed += 1;
    }
    changed
}

fn push_ca_pa_max(
    schemas: &'static fields::VersionedSchemas,
    player: &mut PlayerRecord,
    addr: u64,
    edits: &mut Vec<FieldEdit>,
) -> usize {
    let mut changed = 0usize;
    for (key, label) in [("p_ca", "Current Ability"), ("p_pa", "Potential Ability")] {
        let Some(field) = schemas.field(key) else { continue; };
        let Some(loc) = field.offset else { continue; };
        let off = loc.offset() as usize;
        if off + 2 > player.raw.len() { continue; }
        let old_raw = player.raw[off..off + 2].to_vec();
        let old = u16::from_le_bytes([old_raw[0], old_raw[1]]);
        if old == 200 { continue; }
        let new_raw = 200u16.to_le_bytes().to_vec();
        player.raw[off..off + 2].copy_from_slice(&new_raw);
        let physical = addr + player::player_phys_offset(schemas, loc.offset(), player.person_shift);
        edits.push(FieldEdit {
            addr: physical,
            old_raw,
            new_raw,
            description: format!("{}: {} → 200", label, old),
            presentation: None,
        });
        changed += 1;
    }
    changed
}

fn show_player_power_tools(
    schemas: &'static fields::VersionedSchemas,
    ui: &mut egui::Ui,
    player: &mut PlayerRecord,
    addr: u64,
    edits: &mut Vec<FieldEdit>,
) {
    ui.horizontal_wrapped(|ui| {
        ui.heading("Player Power Tools");
        ui.label(egui::RichText::new("ELEMENT v7.2 • GUARDED PRESETS").strong().color(egui::Color32::from_rgb(116,145,255)));
    });
    ui.label(egui::RichText::new("These presets only touch fields already exposed by the mapped player editor. Every byte enters the normal expected-byte Change History / Undo path.").weak());
    ui.add_space(8.0);

    let enabled = can_edit(ui);
    egui::Grid::new("element_v7_player_power_grid")
        .num_columns(2)
        .spacing([10.0, 8.0])
        .show(ui, |ui| {
            if ui.add_enabled(enabled, egui::Button::new("⚽ TECHNICAL • 20")).clicked() {
                push_max_category_edits(schemas, player, addr, Category::Technical, "Technical", edits);
                push_max_category_edits(schemas, player, addr, Category::SetPieces, "Set Pieces", edits);
            }
            if ui.add_enabled(enabled, egui::Button::new("🧠 MENTAL • 20")).clicked() {
                push_max_category_edits(schemas, player, addr, Category::Mental, "Mental", edits);
            }
            ui.end_row();

            if ui.add_enabled(enabled, egui::Button::new("💪 PHYSICAL • 20")).clicked() {
                push_max_category_edits(schemas, player, addr, Category::Physical, "Physical", edits);
            }
            if ui.add_enabled(enabled, egui::Button::new("🧤 GOALKEEPING • 20")).clicked() {
                push_max_category_edits(schemas, player, addr, Category::Goalkeeping, "Goalkeeping", edits);
            }
            ui.end_row();

            if ui.add_enabled(enabled, egui::Button::new("📍 POSITIONS • 20")).clicked() {
                push_max_category_edits(schemas, player, addr, Category::Positions, "Position familiarity", edits);
            }
            if ui.add_enabled(enabled, egui::Button::new("🦶 BOTH FEET • 20")).clicked() {
                push_max_category_edits(schemas, player, addr, Category::Footedness, "Footedness", edits);
            }
            ui.end_row();

            if ui.add_enabled(enabled, egui::Button::new("⭐ CA / PA • 200 / 200")).clicked() {
                push_ca_pa_max(schemas, player, addr, edits);
            }
            if ui.add_enabled(enabled, egui::Button::new("🔥 FULL PLAYER MAX")).clicked() {
                for (cat, label) in [
                    (Category::Technical, "Technical"),
                    (Category::SetPieces, "Set Pieces"),
                    (Category::Mental, "Mental"),
                    (Category::Physical, "Physical"),
                    (Category::Goalkeeping, "Goalkeeping"),
                    (Category::Positions, "Position familiarity"),
                    (Category::Footedness, "Footedness"),
                ] {
                    push_max_category_edits(schemas, player, addr, cat, label, edits);
                }
                push_ca_pa_max(schemas, player, addr, edits);
            }
            ui.end_row();
        });

    ui.add_space(12.0);
    ui.separator();
    ui.strong("Manual / semantic fields");
    ui.label("Personality and Hidden attributes stay individually editable in Overview. They are intentionally not included in FULL PLAYER MAX because some high values are negative or change behaviour rather than ability.");
    ui.label("Morale, Transfer Value, Asking Price, injuries/Heal, bans/Lift Ban, contract, listings and clauses remain on Overview / Contract using the current FM27 verified controls.");
}

'''
    t = one(t, marker, fn + marker, "Power Tools function")

wr(p, t)
print("Element v7.2 Player Power Tools applied.")
