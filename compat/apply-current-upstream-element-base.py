from pathlib import Path

root = Path.cwd()


def read(path):
    return (root / path).read_text(encoding="utf-8")


def write(path, text):
    (root / path).write_text(text, encoding="utf-8")


# Branding / settings isolation.
p = "src/main.rs"
t = read(p)
t = t.replace('Some(b) => format!("FM Editor [{b}]"),', 'Some(b) => format!("Element FM27 Editor [{b}]"),')
t = t.replace('None => "FM Editor".to_string(),', 'None => "Element FM27 Editor".to_string(),')
t = t.replace('        "FM Editor",\n', '        "Element FM27 Editor",\n', 1)
write(p, t)

p = "src/app.rs"
t = read(p)
t = t.replace('|| "FM Editor".to_string(),', '|| "Element FM27 Editor".to_string(),')
t = t.replace('|v| format!("{} Editor", v.display_name()),', '|v| format!("Element {} Editor", v.display_name()),')
t = t.replace('"FM Editor [preview]"', '"Element FM27 Editor [preview]"')
t = t.replace('"FM Editor"', '"Element FM27 Editor"')
write(p, t)

p = "src/settings.rs"
t = read(p)
t = t.replace('%APPDATA%/fm-editor/settings.json', '%APPDATA%/element-fm27-editor/settings.json')
t = t.replace('join("fm-editor").join("settings.json")', 'join("element-fm27-editor").join("settings.json")')
write(p, t)

# Recreate the v0.2 Transfer Lab surface expected by the historical Element
# layers. Current upstream already has richer FM27 fields underneath; this is
# only a compatibility surface so later Element layers can transform it.
p = "src/ui/player_panel.rs"
t = read(p)
if "TransferLab" not in t:
    t = t.replace('    Contract,\n}', '    Contract,\n    TransferLab,\n}', 1)
    t = t.replace(
        '        ui.selectable_value(tab, PlayerTab::Contract, "Contract");\n',
        '        ui.selectable_value(tab, PlayerTab::Contract, "Contract");\n'
        '        if player.contract_raw.is_some() {\n'
        '            ui.selectable_value(tab, PlayerTab::TransferLab, "Transfer Lab");\n'
        '        }\n',
        1,
    )
    marker = '''        PlayerTab::Contract => {
            egui::ScrollArea::vertical()
                .id_salt("player_contract")
                .show(ui, |ui| {
                    show_contract(schemas, ui, player, &mut edits);
                });
        }
'''
    repl = marker + '''        PlayerTab::TransferLab => {
            egui::ScrollArea::vertical()
                .id_salt("player_transfer_lab")
                .show(ui, |ui| {
                    show_transfer_lab(schemas, ui, player, &mut edits);
                });
        }
'''
    if marker not in t:
        raise SystemExit("current-upstream adapter: contract match arm not found")
    t = t.replace(marker, repl, 1)

    insert_at = t.find("/// Squad statuses offered for editing")
    if insert_at < 0:
        raise SystemExit("current-upstream adapter: squad status marker not found")
    fn = r'''
// ---------------------------------------------------------------------------
// Transfer Lab — Element FM27 compatibility surface
// ---------------------------------------------------------------------------
fn show_transfer_lab(
    schemas: &'static crate::fields::VersionedSchemas,
    ui: &mut egui::Ui,
    player: &mut PlayerRecord,
    edits: &mut Vec<FieldEdit>,
) {
    ui.heading("Transfer Lab");
    ui.label("Safe, mapped FM27 transfer controls. Advanced operations stay locked until their linked records are verified.");
    ui.add_space(8.0);

    if let (Some(cr), Some(caddr)) = (player.contract_raw.as_mut(), player.contract_addr) {
        ui.strong("Market Status");
        if let Some(f) = schemas.field("p_list_flags") {
            let offset = f.offset.as_ref().map(|o| o.offset() as usize);
            if let Some(offset) = offset.filter(|&o| o < cr.len()) {
                let old = cr[offset];
                let mut transfer = old & 1 != 0;
                let mut loan = old & 2 != 0;
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
                        description: format!("Transfer listing flags: {old:#04x} → {new:#04x}"),
                    });
                }
            }
        }
        if let Some(f) = schemas.field("p_contract_wage") {
            edits.extend(field_widget::raw_u32_edit(ui, f, cr, caddr));
        }
        if let Some(f) = schemas.field("p_contract_expiry") {
            edits.extend(field_widget::date_edit(ui, "Contract Expiry", cr, f, caddr, 2000..=2060));
        }
    } else {
        ui.label("Contract sub-record unavailable.");
    }

    if let Some(f) = schemas.field("p_asking_price") {
        edits.extend(field_widget::optional_money_edit(ui, "Asking Price", &mut player.raw, f, player.addr));
    }

    ui.add_space(12.0);
    ui.separator();
    ui.strong("Advanced Transfer Actions");
    ui.label("These need multiple FM27 records to be updated atomically. They are intentionally disabled until the memory chains are verified on the current build.");
    ui.horizontal_wrapped(|ui| {
        ui.add_enabled(false, egui::Button::new("Attract Clubs"));
        ui.add_enabled(false, egui::Button::new("Create Future Transfer"));
        ui.add_enabled(false, egui::Button::new("Move Player Now"));
    });
}

'''
    t = t[:insert_at] + fn + t[insert_at:]
write(p, t)

roadmap = root / "ELEMENT_ROADMAP.md"
if not roadmap.exists():
    roadmap.write_text("# Element FM27 Editor roadmap\n\nCurrent-upstream compatibility probe.\n", encoding="utf-8")

print("Element current-upstream base compatibility adapter applied.")
