from pathlib import Path

root = Path.cwd()

# ---------------------------------------------------------------------------
# 1) Club Squads — remove the height-consuming nested vertical wrapper.
#    The data/cache are correct; the wrapper expands to the available viewport
#    and pushes the actual roster table below the fold.
# ---------------------------------------------------------------------------
p = root / "src" / "ui" / "club_panel.rs"
t = p.read_text(encoding="utf-8")
fn = t.find("fn show_squad_action_bar(")
if fn < 0:
    raise SystemExit("v5.2: show_squad_action_bar not found")
end = t.find("\nfn show_squads(", fn)
if end < 0:
    raise SystemExit("v5.2: show_squad_action_bar boundary not found")
block = t[fn:end]
open_wrap = '''        .show(ui, |ui| {\n            ui.vertical(|ui| {\n'''
close_wrap = '''            });\n        });\n\n    ui.ctx()'''
if open_wrap in block and close_wrap in block:
    block = block.replace(open_wrap, '''        .show(ui, |ui| {\n''', 1)
    block = block.replace(close_wrap, '''        });\n\n    ui.ctx()''', 1)
elif "ui.vertical(|ui|" in block:
    raise SystemExit("v5.2: squad action wrapper exists but expected boundaries changed")
block = block.replace(
    "v4.8 centers the sticky control deck. Live writes: Morale, Heal, Lift Bans, PA/CA and verified profile attributes. Cohesion / UEFA / Home-Grown stay gated until their FM27 record chains are witnessed.",
    "v5.2 compact sticky controls: roster rows remain visible immediately below this deck. Live writes: Morale, Heal, Lift Bans, PA/CA and verified profile attributes.",
    1,
)
t = t[:fn] + block + t[end:]
p.write_text(t, encoding="utf-8")

# ---------------------------------------------------------------------------
# 2) Bridge protocol — Direct Settlement (fee-aware Force Buy).
#    This is intentionally NOT labelled a native bid. It performs the already
#    guarded roster/ownership transaction plus verified club-balance settlement
#    in the same worker-side transaction with read-back/rollback.
# ---------------------------------------------------------------------------
p = root / "src" / "bridge" / "cmd.rs"
t = p.read_text(encoding="utf-8")
force_report = '''pub struct ForceTransferReport {\n'''
if "pub struct ForceBuyReport" not in t:
    pos = t.find(force_report)
    if pos < 0:
        raise SystemExit("v5.2: ForceTransferReport marker missing")
    # Insert after the ForceTransferReport struct.
    struct_end = t.find("}\n\n", pos)
    if struct_end < 0:
        raise SystemExit("v5.2: ForceTransferReport end missing")
    struct_end += 3
    extra = '''#[derive(Clone, Debug)]\npub struct ForceBuyReport {\n    pub transfer: ForceTransferReport,\n    pub fee: u32,\n    pub seller_balance_before: u32,\n    pub seller_balance_after: u32,\n    pub buyer_balance_before: u32,\n    pub buyer_balance_after: u32,\n}\n\n'''
    t = t[:struct_end] + extra + t[struct_end:]

cmd_marker = '''    ForceTransfer { player_addr: u64, person_shift: usize, contract_addr: u64, target_club_addr: u64 },\n'''
if "ForceBuy {" not in t:
    if cmd_marker not in t:
        raise SystemExit("v5.2: ForceTransfer cmd marker missing")
    t = t.replace(cmd_marker, cmd_marker + '''    ForceBuy { player_addr: u64, person_shift: usize, contract_addr: u64, target_club_addr: u64, fee: u32 },\n''', 1)

result_marker = '''    ForceTransferOk(ForceTransferReport),\n'''
if "ForceBuyOk" not in t:
    if result_marker not in t:
        raise SystemExit("v5.2: ForceTransfer result marker missing")
    t = t.replace(result_marker, result_marker + '''    ForceBuyOk(ForceBuyReport),\n    ForceBuyFail { player_addr: u64, error: String },\n''', 1)
p.write_text(t, encoding="utf-8")

# ---------------------------------------------------------------------------
# 3) Worker — finance settlement helpers + fee-aware transaction.
# ---------------------------------------------------------------------------
p = root / "src" / "bridge" / "worker.rs"
t = p.read_text(encoding="utf-8")
t = t.replace(
    "use super::cmd::{BridgeCmd, BridgeResult, EntityCounts, ForceTransferReport};",
    "use super::cmd::{BridgeCmd, BridgeResult, EntityCounts, ForceTransferReport, ForceBuyReport};",
    1,
)

worker_anchor = '''// ---------------------------------------------------------------------------\n// Worker loop\n// ---------------------------------------------------------------------------\n'''
helper = r'''// ---------------------------------------------------------------------------
// Element v5.2 — fee-aware direct settlement
//
// IMPORTANT: this is not a native FM Transfer Proposal. It deliberately uses
// the already guarded v5.0 roster/contract transaction and settles the fee
// against verified club balance fields. It exists as FORCE BUY • DIRECT
// SETTLEMENT while the native proposal record remains under v5.1 mapping.
// ---------------------------------------------------------------------------

fn element_v52_club_field_addr(
    fm: &FmProcess,
    club_addr: u64,
    key: &str,
) -> Result<u64, String> {
    let schema = fm.schemas();
    let field = schema.field(key).ok_or_else(|| format!("missing field {key}"))?;
    let loc = field.offset.as_ref().ok_or_else(|| format!("field {key} is unmapped"))?;
    match loc {
        crate::fields::FieldLocation::Direct { offset, .. } => Ok(club_addr + *offset),
        crate::fields::FieldLocation::SubRecord { container, offset, .. } => {
            let ptr = crate::fields::resolve_sub_ptr(fm, club_addr, container, schema.club_sub_records)
                .ok_or_else(|| format!("could not resolve {container} for club 0x{club_addr:X}"))?;
            if *container == "finance" && schema.full_finance_vtable_rva != 0 {
                let expected = fm.gp_base + schema.full_finance_vtable_rva;
                let actual = fm.read_u64(ptr).map_err(|e| format!("finance vtable: {e}"))?;
                if actual != expected {
                    return Err(format!("club finance object is not the verified full FM27 finance class (0x{actual:X})"));
                }
            }
            Ok(ptr + *offset)
        }
    }
}

fn element_v52_force_buy(
    fm: &FmProcess,
    player_addr: u64,
    person_shift: usize,
    contract_addr: u64,
    target_club_addr: u64,
    fee: u32,
) -> Result<ForceBuyReport, String> {
    if fee == 0 {
        return Err("Force Buy fee must be greater than zero".into());
    }
    if fm.build != crate::game_version::GameBuild::Fm27Steam {
        return Err("Force Buy v5.2 is enabled only for the verified FM27 Steam layout".into());
    }

    let source_team = fm.read_u64(player_addr + 0x130)
        .map_err(|e| format!("current team pointer: {e}"))?;
    if !element_v5_ptr_ok(source_team) {
        return Err("player has no valid source team".into());
    }
    let source_club_addr = fm.read_u64(source_team + 0x30)
        .map_err(|e| format!("source club pointer: {e}"))?;
    if !element_v5_ptr_ok(source_club_addr) || source_club_addr == target_club_addr {
        return Err("invalid source/target club for Force Buy".into());
    }

    let seller_balance_addr = element_v52_club_field_addr(fm, source_club_addr, "c_balance")?;
    let buyer_balance_addr = element_v52_club_field_addr(fm, target_club_addr, "c_balance")?;
    let seller_before = fm.read_u32(seller_balance_addr).map_err(|e| format!("seller balance: {e}"))?;
    let buyer_before = fm.read_u32(buyer_balance_addr).map_err(|e| format!("buyer balance: {e}"))?;
    if buyer_before < fee {
        return Err(format!("target club balance is too low: has £{buyer_before}, needs £{fee}"));
    }
    let seller_after = seller_before.checked_add(fee)
        .ok_or_else(|| "seller balance would overflow u32".to_owned())?;
    let buyer_after = buyer_before - fee;

    // First run the guarded roster/ownership transaction. It performs its own
    // rollback if any roster or contract read-back fails.
    let transfer = element_v5_force_transfer(
        fm,
        player_addr,
        person_shift,
        contract_addr,
        target_club_addr,
    )?;

    // Finance patch is separate but guarded; on failure we abort loudly. The
    // player transaction has already been validated, so this mode is labelled
    // DIRECT SETTLEMENT rather than native bid/transfer history.
    let seller_old = seller_before.to_le_bytes();
    let buyer_old = buyer_before.to_le_bytes();
    if let Err(e) = fm.write_bytes(seller_balance_addr, &seller_after.to_le_bytes()) {
        return Err(format!("player moved, but seller balance write failed: {e}; use Undo/save backup before continuing"));
    }
    if let Err(e) = fm.write_bytes(buyer_balance_addr, &buyer_after.to_le_bytes()) {
        let _ = fm.write_bytes(seller_balance_addr, &seller_old);
        return Err(format!("player moved, buyer balance write failed and seller balance was restored: {e}"));
    }
    let seller_rb = fm.read_u32(seller_balance_addr).map_err(|e| format!("seller balance read-back: {e}"))?;
    let buyer_rb = fm.read_u32(buyer_balance_addr).map_err(|e| format!("buyer balance read-back: {e}"))?;
    if seller_rb != seller_after || buyer_rb != buyer_after {
        let _ = fm.write_bytes(seller_balance_addr, &seller_old);
        let _ = fm.write_bytes(buyer_balance_addr, &buyer_old);
        return Err("finance read-back failed; finance values were restored (player move remains validated)".into());
    }

    Ok(ForceBuyReport {
        transfer,
        fee,
        seller_balance_before: seller_before,
        seller_balance_after: seller_after,
        buyer_balance_before: buyer_before,
        buyer_balance_after: buyer_after,
    })
}

'''
if "fn element_v52_force_buy(" not in t:
    if worker_anchor not in t:
        raise SystemExit("v5.2: worker loop anchor missing")
    t = t.replace(worker_anchor, helper + worker_anchor, 1)

handler_anchor = '''            BridgeCmd::ForceTransfer { player_addr, person_shift, contract_addr, target_club_addr } => {'''
if "BridgeCmd::ForceBuy {" not in t:
    pos = t.find(handler_anchor)
    if pos < 0:
        raise SystemExit("v5.2: ForceTransfer worker handler missing")
    # Insert ForceBuy immediately before ForceTransfer.
    handler = r'''            BridgeCmd::ForceBuy { player_addr, person_shift, contract_addr, target_club_addr, fee } => {
                match &fm {
                    Some(f) => match element_v52_force_buy(f, player_addr, person_shift, contract_addr, target_club_addr, fee) {
                        Ok(report) => { let _ = tx.send(BridgeResult::ForceBuyOk(report)); }
                        Err(error) => { let _ = tx.send(BridgeResult::ForceBuyFail { player_addr, error }); }
                    },
                    None => { let _ = tx.send(BridgeResult::ForceBuyFail { player_addr, error: "Cannot Force Buy: no process attached".into() }); }
                }
            }

'''
    t = t[:pos] + handler + t[pos:]
p.write_text(t, encoding="utf-8")

# ---------------------------------------------------------------------------
# 4) Player Transfer Lab UI — Transfer Power Engine controls.
# ---------------------------------------------------------------------------
p = root / "src" / "ui" / "player_panel.rs"
t = p.read_text(encoding="utf-8")
marker = '''                        let ack_id = egui::Id::new(("element_force_transfer_ack", player.addr));\n'''
if "TRANSFER POWER ENGINE" not in t:
    pos = t.find(marker)
    if pos < 0:
        raise SystemExit("v5.2: Force Transfer ack marker missing")
    ui_block = r'''                        ui.add_space(6.0);
                        egui::Frame::group(ui.style())
                            .fill(egui::Color32::from_rgb(21, 31, 29))
                            .stroke(egui::Stroke::new(1.0, egui::Color32::from_rgb(55, 110, 83)))
                            .rounding(egui::Rounding::same(4))
                            .inner_margin(egui::Margin::symmetric(7, 6))
                            .show(ui, |ui| {
                                ui.horizontal(|ui| {
                                    ui.label(egui::RichText::new("TRANSFER POWER ENGINE").size(9.0).strong().color(egui::Color32::from_rgb(72, 210, 132)));
                                    ui.label(egui::RichText::new("v5.2 • SETTLEMENT + NATIVE OFFER RESEARCH").size(7.5).color(egui::Color32::from_rgb(154,169,194)));
                                });
                                let fee_id = egui::Id::new(("element_force_buy_fee_v52", player.addr));
                                let mut fee_text = ui.ctx().data_mut(|d| d.get_temp::<String>(fee_id).unwrap_or_else(|| "25000000".to_owned()));
                                ui.horizontal_wrapped(|ui| {
                                    ui.label("Fee (£):");
                                    if ui.add_sized([150.0, 22.0], egui::TextEdit::singleline(&mut fee_text)).changed() {
                                        ui.ctx().data_mut(|d| d.insert_temp(fee_id, fee_text.clone()));
                                    }
                                    let clean = fee_text.replace([',', '.', ' ', '£', '€', '$'], "");
                                    let fee = clean.parse::<u32>().ok().filter(|v| *v > 0);
                                    let can_settle = crate::ui::navigation::editing_enabled(ui) && fee.is_some() && player.contract_addr.is_some() && player.club_addr != Some(club.addr);
                                    if ui.add_enabled(can_settle, egui::Button::new("💰 FORCE BUY • DIRECT SETTLEMENT"))
                                        .on_hover_text("Moves the player with the guarded roster/contract transaction and transfers the entered fee from buyer club balance to seller club balance. This is NOT a native FM bid and does not create Inbox/history yet.")
                                        .clicked()
                                    {
                                        if let (Some(contract_addr), Some(fee)) = (player.contract_addr, fee) {
                                            let req_id = egui::Id::new("element_force_buy_request_v52");
                                            ui.ctx().data_mut(|d| d.insert_temp(req_id, (player.addr, player.person_shift, contract_addr, club.addr, fee)));
                                        }
                                    }
                                });
                                ui.horizontal_wrapped(|ui| {
                                    ui.add_enabled(false, egui::Button::new("🎯 FORCE INTEREST • MAPPING"))
                                        .on_disabled_hover_text("No FM27 interested-club record has two independent witnesses yet. v5.1 Proposal Mapper remains read-only until certified.");
                                    ui.add_enabled(false, egui::Button::new("📨 FORCE BID • MAPPING"))
                                        .on_disabled_hover_text("Native Transfer Proposal record is not publicly mapped/certified yet. Element will not fabricate a bid record.");
                                    ui.add_enabled(false, egui::Button::new("✅ FORCE BUY • NATIVE FM"))
                                        .on_disabled_hover_text("Unlocks after FORCE BID is certified so FM itself can create Inbox, finances and player history.");
                                });
                                ui.label(egui::RichText::new("DIRECT SETTLEMENT is fully labelled as non-native. Native FORCE INTEREST / BID / BUY remain locked until the Proposal Mapper produces repeatable witnesses.").size(7.3).color(egui::Color32::from_rgb(174,185,202)));
                            });

'''
    t = t[:pos] + ui_block + t[pos:]
p.write_text(t, encoding="utf-8")

# ---------------------------------------------------------------------------
# 5) app.rs — dispatch ForceBuy and reload cache/player after success.
# ---------------------------------------------------------------------------
p = root / "src" / "app.rs"
t = p.read_text(encoding="utf-8")
result_marker = '''                BridgeResult::ForceTransferOk(report) => {\n'''
if "BridgeResult::ForceBuyOk" not in t:
    pos = t.find(result_marker)
    if pos < 0:
        raise SystemExit("v5.2: ForceTransferOk app marker missing")
    result = r'''                BridgeResult::ForceBuyOk(report) => {
                    let msg = format!(
                        "Force Buy DIRECT SETTLEMENT OK • fee £{} • seller £{} → £{} • buyer £{} → £{} • no native proposal/history",
                        report.fee,
                        report.seller_balance_before,
                        report.seller_balance_after,
                        report.buyer_balance_before,
                        report.buyer_balance_after,
                    );
                    self.set_status(msg);
                    let player_addr = report.transfer.player_addr;
                    self.entity_cache = None;
                    self.cache_load_state = CacheLoadState::Loading { done: 0, total: 0 };
                    self.bridge.send(BridgeCmd::LoadEntityCache);
                    if let Some(player) = self.selected_player.as_ref().filter(|p| p.addr == player_addr) {
                        self.bridge.send(BridgeCmd::LoadPlayer(player.addr, player.index));
                    }
                }
                BridgeResult::ForceBuyFail { player_addr: _, error } => {
                    self.set_status(format!("Force Buy aborted: {error}"));
                }
'''
    t = t[:pos] + result + t[pos:]

request_anchor = '''        // Element v5.0 guarded Force Transfer request. The worker owns the\n'''
if "element_force_buy_request_v52" not in t:
    pos = t.find(request_anchor)
    if pos < 0:
        raise SystemExit("v5.2: Force Transfer request anchor missing")
    req = r'''        // Element v5.2 fee-aware direct settlement request.
        let force_buy_request = ctx.data_mut(|d| {
            let id = egui::Id::new("element_force_buy_request_v52");
            let request = d.get_temp::<(u64, usize, u64, u64, u32)>(id);
            d.remove::<(u64, usize, u64, u64, u32)>(id);
            request
        });
        if let Some((player_addr, person_shift, contract_addr, target_club_addr, fee)) = force_buy_request {
            if self.conn.is_writable() {
                self.bridge.send(BridgeCmd::ForceBuy { player_addr, person_shift, contract_addr, target_club_addr, fee });
                self.set_status(format!("Force Buy direct settlement running • £{fee} • roster + ownership + balances + read-back…"));
            } else {
                self.set_status("Force Buy requires a live writable FM27 session".into());
            }
        }

'''
    t = t[:pos] + req + t[pos:]
p.write_text(t, encoding="utf-8")

print("Element v5.2 Transfer Power + Squad render fix applied successfully.")
