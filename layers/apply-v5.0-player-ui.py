from pathlib import Path

path = Path.cwd() / "src" / "ui" / "player_panel.rs"
text = path.read_text(encoding="utf-8")

fn_marker = "fn show_transfer_lab("
fn_pos = text.find(fn_marker)
if fn_pos < 0:
    raise SystemExit("v5 player UI: show_transfer_lab not found")

helper = r'''fn element_v5_listing_now(
    schemas: &'static crate::fields::VersionedSchemas,
    player: &mut PlayerRecord,
    edits: &mut Vec<FieldEdit>,
) -> bool {
    let (Some(raw), Some(base), Some(today)) = (player.contract_raw.as_mut(), player.contract_addr, player.game_date) else { return false; };
    let Some(date_off) = schemas.offset_of("p_list_date") else { return false; };
    let Some(flags_off) = schemas.offset_of("p_list_flags") else { return false; };
    let Some(code_off) = schemas.offset_of("p_list_code") else { return false; };
    if date_off + 4 > raw.len() || flags_off >= raw.len() || code_off >= raw.len() { return false; }
    let start = date_off;
    let end = code_off + 1;
    if end > raw.len() || flags_off < start || flags_off >= end { return false; }
    let old = raw[start..end].to_vec();
    let mut new = old.clone();
    new[0..4].copy_from_slice(&today.raw.to_le_bytes());
    new[flags_off - start] = raw[flags_off] | 1;
    new[code_off - start] = 5;
    if new == old { return true; }
    raw[start..end].copy_from_slice(&new);
    edits.push(FieldEdit {
        addr: base + start as u64,
        old_raw: old,
        new_raw: new,
        description: "Sell Assist — transfer list now".into(),
    });
    true
}

fn element_v5_offer_magnet(
    schemas: &'static crate::fields::VersionedSchemas,
    player: &mut PlayerRecord,
    edits: &mut Vec<FieldEdit>,
    percent: u32,
) {
    let _ = element_v5_listing_now(schemas, player, edits);
    let Some(off) = schemas.offset_of("p_value") else { return; };
    let Some(bytes) = player.raw.get(off..off + 4) else { return; };
    let old = u32::from_le_bytes(bytes.try_into().unwrap());
    if old == 0 || old == u32::MAX { return; }
    let new = ((u64::from(old) * u64::from(percent)) / 100).clamp(1, u64::from(u32::MAX)) as u32;
    if new == old { return; }
    player.raw[off..off + 4].copy_from_slice(&new.to_le_bytes());
    edits.push(FieldEdit {
        addr: player.addr + off as u64,
        old_raw: old.to_le_bytes().to_vec(),
        new_raw: new.to_le_bytes().to_vec(),
        description: format!("Offer Magnet — transfer value {old} → {new} ({percent}%)"),
    });
}

'''
if "fn element_v5_listing_now(" not in text:
    text = text[:fn_pos] + helper + text[fn_pos:]
    fn_pos += len(helper)

# Scope edits to the Transfer Lab function only.
end_marker = "\n/// Squad statuses"
fn_end = text.find(end_marker, fn_pos)
if fn_end < 0:
    fn_end = text.find("\nfn ", fn_pos + len(fn_marker))
if fn_end < 0:
    raise SystemExit("v5 player UI: end of show_transfer_lab not found")
block = text[fn_pos:fn_end]

old_intro = "Transfer/loan listing, listing metadata, value, asking price and mapped contract fields are live. Force/Future Transfer stays locked until all linked membership records are verified."
new_intro = "v5.0: verified market writes + guarded roster/ownership transaction. Offer Magnet uses listing/value writes to stimulate FM's AI market; it never fabricates an unmapped proposal record."
block = block.replace(old_intro, new_intro, 1)

if "SELL / OFFER MAGNET" not in block:
    insert_at = block.find("    ui.add_space(3.0);")
    if insert_at < 0:
        raise SystemExit("v5 player UI: Transfer Lab intro spacing marker missing")
    insert_at = block.find("\n", insert_at) + 1
    sell = r'''
    egui::Frame::group(ui.style())
        .fill(egui::Color32::from_rgb(23, 34, 35))
        .stroke(egui::Stroke::new(1.0, egui::Color32::from_rgb(48, 88, 72)))
        .rounding(egui::Rounding::same(4))
        .inner_margin(egui::Margin::symmetric(7, 5))
        .show(ui, |ui| {
            ui.horizontal(|ui| {
                ui.label(egui::RichText::new("SELL / OFFER MAGNET").size(9.0).strong().color(egui::Color32::from_rgb(72, 210, 132)));
                ui.label(egui::RichText::new("AI MARKET TRIGGER • VERIFIED WRITES").size(7.5).color(egui::Color32::from_rgb(139, 157, 188)));
            });
            ui.horizontal_wrapped(|ui| {
                let enabled = crate::ui::navigation::editing_enabled(ui) && player.contract_raw.is_some() && player.game_date.is_some();
                if ui.add_enabled(enabled, egui::Button::new("LIST NOW")).on_hover_text("Transfer-list with today's live FM date and verified listing code 5.").clicked() {
                    let _ = element_v5_listing_now(schemas, player, edits);
                }
                if ui.add_enabled(enabled, egui::Button::new("OFFER MAGNET • 75%")).on_hover_text("List now + set verified transfer value to 75%. FM AI still decides whether to bid.").clicked() {
                    element_v5_offer_magnet(schemas, player, edits, 75);
                }
                if ui.add_enabled(enabled, egui::Button::new("OFFER MAGNET • 50%")).on_hover_text("Aggressive sale: list now + 50% transfer value.").clicked() {
                    element_v5_offer_magnet(schemas, player, edits, 50);
                }
                if ui.add_enabled(enabled, egui::Button::new("FIRE SALE • 25%")).on_hover_text("Extreme sale trigger: list now + 25% transfer value. Undo can restore the value later.").clicked() {
                    element_v5_offer_magnet(schemas, player, edits, 25);
                }
            });
            ui.label(egui::RichText::new("Incoming proposal vectors are not publicly mapped for FM27. Continue the game after applying a preset; Element does not synthesize fake bids.").size(7.5).color(egui::Color32::from_rgb(180, 190, 205)));
        });
    ui.add_space(5.0);
'''
    block = block[:insert_at] + sell + block[insert_at:]

# Replace only the actual disabled safety-gate button; surrounding target-club
# rendering may change without breaking this patch.
needle = 'ui.add_enabled(false,egui::Button::new("FORCE TRANSFER • SAFETY GATE 2/5")'
button_pos = block.find(needle)
if button_pos < 0 and "FORCE TRANSFER TO SELECTED CLUB" not in block:
    raise SystemExit("v5 player UI: Force Transfer safety-gate button not found")
if button_pos >= 0:
    line_start = block.rfind("\n", 0, button_pos) + 1
    semi = block.find(";", button_pos)
    if semi < 0:
        raise SystemExit("v5 player UI: Force Transfer gate line terminator missing")
    replacement = r'''                        let ack_id = egui::Id::new(("element_force_transfer_ack", player.addr));
                        let mut ack = ui.data_mut(|d| d.get_temp::<bool>(ack_id).unwrap_or(false));
                        ui.checkbox(&mut ack, "I understand: experimental live transfer; make a save backup first");
                        ui.data_mut(|d| d.insert_temp(ack_id, ack));
                        let can_force = crate::ui::navigation::editing_enabled(ui)
                            && ack
                            && player.contract_addr.is_some()
                            && player.club_addr != Some(club.addr);
                        if ui.add_enabled(can_force, egui::Button::new("⚡ FORCE TRANSFER TO SELECTED CLUB").min_size(egui::vec2(ui.available_width(), 28.0)))
                            .on_hover_text("FM27 Steam only. Removes the exact source roster entry, appends it to the target senior roster, updates player team + contract employer + transfer date, then validates every link. Failed validation triggers rollback.")
                            .clicked()
                        {
                            if let Some(contract_addr) = player.contract_addr {
                                let req_id = egui::Id::new("element_force_transfer_request_v5");
                                ui.ctx().data_mut(|d| d.insert_temp(req_id, (player.addr, player.person_shift, contract_addr, club.addr)));
                            }
                        }'''
    block = block[:line_start] + replacement + block[semi + 1:]

block = block.replace(
    "Force Transfer Lab is now interactive and target-aware. Execution unlocks only when source removal + destination membership + ownership + registration + read-back are all FM27-certified.",
    "v5.0 Force Transfer is a guarded FM27 Steam transaction. Competition-specific registration is not directly rewritten; FM may recalculate eligibility after Continue/reload.",
    1,
)

text = text[:fn_pos] + block + text[fn_end:]
path.write_text(text, encoding="utf-8")
print("Element v5.0 Player Transfer UI applied with marker-based patching.")
