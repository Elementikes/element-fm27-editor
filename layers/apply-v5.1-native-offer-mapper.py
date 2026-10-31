from pathlib import Path

root = Path.cwd()

# ---------------------------------------------------------------------------
# bridge/cmd.rs — proposal-probe protocol
# ---------------------------------------------------------------------------
p = root / "src" / "bridge" / "cmd.rs"
t = p.read_text(encoding="utf-8")

force_cmd = '''    ForceTransfer { player_addr: u64, person_shift: usize, contract_addr: u64, target_club_addr: u64 },\n'''
probe_cmd = '''    ProposalProbeBaseline { player_addr: u64, person_shift: usize, contract_addr: u64 },\n    ProposalProbeCompare { player_addr: u64, person_shift: usize, contract_addr: u64, target_club_addr: u64, expected_fee: u64 },\n'''
if "ProposalProbeBaseline" not in t:
    if force_cmd not in t:
        raise SystemExit("v5.1: ForceTransfer command marker not found")
    t = t.replace(force_cmd, probe_cmd + force_cmd, 1)

force_result = '''    ForceTransferOk(ForceTransferReport),\n'''
probe_result = '''    ProposalProbeReady { player_addr: u64, source_club_addr: u64, chunks: usize },\n    ProposalProbeDone { player_addr: u64, candidates: usize, report_path: String, summary: String },\n    ProposalProbeFail { player_addr: u64, error: String },\n'''
if "ProposalProbeReady" not in t:
    if force_result not in t:
        raise SystemExit("v5.1: ForceTransfer result marker not found")
    t = t.replace(force_result, probe_result + force_result, 1)

p.write_text(t, encoding="utf-8")

# ---------------------------------------------------------------------------
# bridge/worker.rs — bounded before/after mapper around verified linked records
# ---------------------------------------------------------------------------
p = root / "src" / "bridge" / "worker.rs"
t = p.read_text(encoding="utf-8")

worker_anchor = '''// ---------------------------------------------------------------------------\n// Worker loop\n// ---------------------------------------------------------------------------\n'''
helper = r'''// ---------------------------------------------------------------------------
// Element v5.1 — native transfer proposal mapper
//
// This does NOT synthesize a bid. It snapshots the already verified player /
// contract / team / club chain before a real FM offer, then compares the same
// memory afterwards. New pointer-like values are followed and scored for
// player/source/target/fee witnesses. The resulting report is evidence for a
// future native CREATE OFFER implementation.
// ---------------------------------------------------------------------------

#[derive(Clone)]
struct ElementV51ProbeChunk {
    label: String,
    addr: u64,
    bytes: Vec<u8>,
}

#[derive(Clone)]
struct ElementV51ProbeSnapshot {
    player_addr: u64,
    person_addr: u64,
    contract_addr: u64,
    source_team_addr: u64,
    source_club_addr: u64,
    chunks: Vec<ElementV51ProbeChunk>,
}

fn element_v51_capture_chunks(
    fm: &FmProcess,
    label: &str,
    base: u64,
    span: usize,
    out: &mut Vec<ElementV51ProbeChunk>,
) {
    const STEP: usize = 0x100;
    for off in (0..span).step_by(STEP) {
        let n = STEP.min(span - off);
        if let Ok(bytes) = fm.read_bytes(base + off as u64, n) {
            out.push(ElementV51ProbeChunk {
                label: format!("{label}+0x{off:X}"),
                addr: base + off as u64,
                bytes,
            });
        }
    }
}

fn element_v51_capture_baseline(
    fm: &FmProcess,
    player_addr: u64,
    person_shift: usize,
    contract_addr: u64,
) -> Result<ElementV51ProbeSnapshot, String> {
    if fm.build != crate::game_version::GameBuild::Fm27Steam {
        return Err("Proposal Mapper v5.1 is enabled only for FM27 Steam".into());
    }
    if !element_v5_ptr_ok(player_addr) || !element_v5_ptr_ok(contract_addr) {
        return Err("player/contract pointer failed plausibility checks".into());
    }
    let schemas = fm.schemas();
    let person_addr = player_addr
        .checked_add(schemas.player_person_offset as u64)
        .and_then(|v| v.checked_add(person_shift as u64))
        .ok_or_else(|| "player person pointer overflow".to_owned())?;
    let back = fm
        .read_u64(contract_addr + 0x08)
        .map_err(|e| format!("contract back-pointer: {e}"))?;
    if back != person_addr {
        return Err(format!(
            "contract ownership guard failed: expected person 0x{person_addr:X}, got 0x{back:X}"
        ));
    }
    let source_team_addr = fm
        .read_u64(player_addr + 0x130)
        .map_err(|e| format!("current team pointer: {e}"))?;
    if !element_v5_ptr_ok(source_team_addr) {
        return Err("player has no valid current team".into());
    }
    let source_club_addr = fm
        .read_u64(source_team_addr + 0x30)
        .map_err(|e| format!("source club pointer: {e}"))?;
    if !element_v5_ptr_ok(source_club_addr) {
        return Err("source team has no valid club pointer".into());
    }

    let mut chunks = Vec::new();
    // Chunked reads are deliberate: if an object ends near a page boundary,
    // one failed 0x100 page does not discard the rest of the witness set.
    element_v51_capture_chunks(fm, "player", player_addr, 0x500, &mut chunks);
    element_v51_capture_chunks(fm, "person", person_addr, 0x300, &mut chunks);
    element_v51_capture_chunks(fm, "contract", contract_addr, 0x100, &mut chunks);
    element_v51_capture_chunks(fm, "source_team", source_team_addr, 0x300, &mut chunks);
    element_v51_capture_chunks(fm, "source_club", source_club_addr, 0x1000, &mut chunks);

    if chunks.is_empty() {
        return Err("no readable proposal-probe chunks".into());
    }
    Ok(ElementV51ProbeSnapshot {
        player_addr,
        person_addr,
        contract_addr,
        source_team_addr,
        source_club_addr,
        chunks,
    })
}

fn element_v51_contains_u64(bytes: &[u8], value: u64) -> bool {
    let needle = value.to_le_bytes();
    bytes.windows(8).any(|w| w == needle)
}

fn element_v51_contains_u32(bytes: &[u8], value: u32) -> bool {
    let needle = value.to_le_bytes();
    bytes.windows(4).any(|w| w == needle)
}

fn element_v51_candidate_tags(
    bytes: &[u8],
    snap: &ElementV51ProbeSnapshot,
    target_team: u64,
    target_club: u64,
    expected_fee: u64,
) -> Vec<&'static str> {
    let mut tags = Vec::new();
    if element_v51_contains_u64(bytes, snap.player_addr) { tags.push("player"); }
    if element_v51_contains_u64(bytes, snap.person_addr) { tags.push("person"); }
    if element_v51_contains_u64(bytes, snap.contract_addr) { tags.push("contract"); }
    if element_v51_contains_u64(bytes, snap.source_team_addr) { tags.push("source_team"); }
    if element_v51_contains_u64(bytes, snap.source_club_addr) { tags.push("source_club"); }
    if element_v51_contains_u64(bytes, target_team) { tags.push("target_team"); }
    if element_v51_contains_u64(bytes, target_club) { tags.push("target_club"); }
    if expected_fee <= u32::MAX as u64 && element_v51_contains_u32(bytes, expected_fee as u32) {
        tags.push("fee_u32");
    }
    if element_v51_contains_u64(bytes, expected_fee) { tags.push("fee_u64"); }
    tags
}

fn element_v51_compare_probe(
    fm: &FmProcess,
    snap: &ElementV51ProbeSnapshot,
    player_addr: u64,
    person_shift: usize,
    contract_addr: u64,
    target_club_addr: u64,
    expected_fee: u64,
) -> Result<(usize, String, String), String> {
    if player_addr != snap.player_addr || contract_addr != snap.contract_addr {
        return Err("baseline belongs to another player/contract; capture BEFORE again".into());
    }
    let current = element_v51_capture_baseline(fm, player_addr, person_shift, contract_addr)?;
    if current.source_club_addr != snap.source_club_addr {
        return Err("player ownership changed since baseline; proposal probe aborted".into());
    }
    let target_team = element_v5_find_senior_team(fm, target_club_addr)?;
    let mut report = String::new();
    report.push_str("Element FM27 v5.1 Native Offer / Proposal Mapper\n");
    report.push_str("================================================\n");
    report.push_str(&format!("player       0x{:X}\n", snap.player_addr));
    report.push_str(&format!("person       0x{:X}\n", snap.person_addr));
    report.push_str(&format!("contract     0x{:X}\n", snap.contract_addr));
    report.push_str(&format!("source team  0x{:X}\n", snap.source_team_addr));
    report.push_str(&format!("source club  0x{:X}\n", snap.source_club_addr));
    report.push_str(&format!("target team  0x{:X}\n", target_team));
    report.push_str(&format!("target club  0x{:X}\n", target_club_addr));
    report.push_str(&format!("expected fee {}\n\n", expected_fee));

    let mut changed_slots = 0usize;
    let mut candidates: Vec<(usize, String)> = Vec::new();

    for before in &snap.chunks {
        let Some(after) = current.chunks.iter().find(|c| c.addr == before.addr) else { continue; };
        if before.bytes == after.bytes { continue; }
        report.push_str(&format!("[changed] {} @ 0x{:X}\n", before.label, before.addr));

        let common = before.bytes.len().min(after.bytes.len());
        // Pointer-sized changes are the highest-value evidence. Follow the new
        // pointer and score its first 0x300 bytes for proposal witnesses.
        for off in (0..common.saturating_sub(7)).step_by(8) {
            let old = u64::from_le_bytes(before.bytes[off..off + 8].try_into().unwrap());
            let new = u64::from_le_bytes(after.bytes[off..off + 8].try_into().unwrap());
            if old == new { continue; }
            changed_slots += 1;
            report.push_str(&format!("  +0x{off:03X} u64 0x{old:X} -> 0x{new:X}\n"));
            if element_v5_ptr_ok(new) {
                if let Ok(blob) = fm.read_bytes(new, 0x300) {
                    let tags = element_v51_candidate_tags(
                        &blob,
                        snap,
                        target_team,
                        target_club_addr,
                        expected_fee,
                    );
                    if tags.len() >= 2 {
                        let score = tags.len();
                        candidates.push((score, format!(
                            "{} +0x{:X} -> 0x{:X} | {}",
                            before.label,
                            off,
                            new,
                            tags.join(", ")
                        )));
                    }
                }
            }
        }

        // Exact 32-bit fee / direct club pointers inside the changed owner
        // objects are useful even when no new pointer was introduced.
        let tags = element_v51_candidate_tags(
            &after.bytes,
            snap,
            target_team,
            target_club_addr,
            expected_fee,
        );
        if tags.iter().any(|t| *t == "target_club" || *t == "target_team" || *t == "fee_u32" || *t == "fee_u64") {
            candidates.push((tags.len(), format!(
                "changed owner chunk {} @ 0x{:X} | {}",
                before.label,
                before.addr,
                tags.join(", ")
            )));
        }
        report.push('\n');
    }

    candidates.sort_by(|a, b| b.0.cmp(&a.0).then_with(|| a.1.cmp(&b.1)));
    candidates.dedup_by(|a, b| a.1 == b.1);
    report.push_str("\nCANDIDATES\n----------\n");
    for (rank, (score, line)) in candidates.iter().take(30).enumerate() {
        report.push_str(&format!("{:02}. score {} | {}\n", rank + 1, score, line));
    }
    if candidates.is_empty() {
        report.push_str("No linked candidate found in bounded owner-chain scan. Next step is full readable-heap scan; no writes were performed.\n");
    }

    report.push_str(&format!("\nchanged pointer slots: {changed_slots}\n"));
    report.push_str("This report is READ-ONLY evidence. It does not certify a proposal record by itself.\n");

    let path = std::env::temp_dir().join("Element-FM27-v5.1-Proposal-Mapper.txt");
    std::fs::write(&path, report.as_bytes())
        .map_err(|e| format!("could not write proposal report: {e}"))?;
    let path_string = path.display().to_string();
    let summary = if let Some((score, top)) = candidates.first() {
        format!("top candidate score {score}: {top}")
    } else {
        "no bounded candidate — report saved for full-heap follow-up".to_owned()
    };
    Ok((candidates.len(), path_string, summary))
}

'''
if "struct ElementV51ProbeSnapshot" not in t:
    if worker_anchor not in t:
        raise SystemExit("v5.1: worker loop anchor missing")
    t = t.replace(worker_anchor, helper + worker_anchor, 1)

state_anchor = '''    let mut last_counts: Option<(usize, usize, usize)> = None;\n'''
if "element_v51_probe" not in t:
    if state_anchor not in t:
        raise SystemExit("v5.1: worker state anchor missing")
    t = t.replace(state_anchor, state_anchor + "    let mut element_v51_probe: Option<ElementV51ProbeSnapshot> = None;\n", 1)

handler_anchor = '''            BridgeCmd::ForceTransfer { player_addr, person_shift, contract_addr, target_club_addr } => {'''
if "BridgeCmd::ProposalProbeBaseline" not in t:
    if handler_anchor not in t:
        raise SystemExit("v5.1: ForceTransfer worker handler marker missing")
    handlers = r'''            BridgeCmd::ProposalProbeBaseline { player_addr, person_shift, contract_addr } => {
                match &fm {
                    Some(f) => match element_v51_capture_baseline(f, player_addr, person_shift, contract_addr) {
                        Ok(snapshot) => {
                            let source_club_addr = snapshot.source_club_addr;
                            let chunks = snapshot.chunks.len();
                            element_v51_probe = Some(snapshot);
                            let _ = tx.send(BridgeResult::ProposalProbeReady { player_addr, source_club_addr, chunks });
                        }
                        Err(error) => {
                            let _ = tx.send(BridgeResult::ProposalProbeFail { player_addr, error });
                        }
                    },
                    None => {
                        let _ = tx.send(BridgeResult::ProposalProbeFail { player_addr, error: "Proposal Mapper: no process attached".into() });
                    }
                }
            }

            BridgeCmd::ProposalProbeCompare { player_addr, person_shift, contract_addr, target_club_addr, expected_fee } => {
                match (&fm, &element_v51_probe) {
                    (Some(f), Some(snapshot)) => match element_v51_compare_probe(
                        f,
                        snapshot,
                        player_addr,
                        person_shift,
                        contract_addr,
                        target_club_addr,
                        expected_fee,
                    ) {
                        Ok((candidates, report_path, summary)) => {
                            let _ = tx.send(BridgeResult::ProposalProbeDone { player_addr, candidates, report_path, summary });
                        }
                        Err(error) => {
                            let _ = tx.send(BridgeResult::ProposalProbeFail { player_addr, error });
                        }
                    },
                    (_, None) => {
                        let _ = tx.send(BridgeResult::ProposalProbeFail { player_addr, error: "Proposal Mapper has no BEFORE snapshot. Capture BEFORE first.".into() });
                    }
                    (None, _) => {
                        let _ = tx.send(BridgeResult::ProposalProbeFail { player_addr, error: "Proposal Mapper: no process attached".into() });
                    }
                }
            }

'''
    t = t.replace(handler_anchor, handlers + handler_anchor, 1)

p.write_text(t, encoding="utf-8")

# ---------------------------------------------------------------------------
# ui/player_panel.rs — native offer mapper controls + clearer Direct Move label
# ---------------------------------------------------------------------------
p = root / "src" / "ui" / "player_panel.rs"
t = p.read_text(encoding="utf-8")

# Make the v5.0 behavior unambiguous now that we have verified the limitation.
t = t.replace(
    'egui::Button::new("⚡ FORCE TRANSFER TO SELECTED CLUB")',
    'egui::Button::new("⚡ DIRECT MOVE • NO FEE / HISTORY")',
    1,
)
t = t.replace(
    '"FM27 Steam only. Removes the exact source roster entry, appends it to the target senior roster, updates player team + contract employer + transfer date, then validates every link. Failed validation triggers rollback."',
    '"Direct ownership move only. It does NOT create an FM transfer proposal, transfer fee, inbox item or player history entry. Use the v5.1 Native Offer Mapper below to map the real proposal record."',
    1,
)

mapper_marker = '''                        let ack_id = egui::Id::new(("element_force_transfer_ack", player.addr));\n'''
if "NATIVE OFFER ENGINE" not in t:
    if mapper_marker not in t:
        raise SystemExit("v5.1: Force Transfer ack marker missing in player UI")
    mapper_ui = r'''                        ui.add_space(6.0);
                        egui::Frame::group(ui.style())
                            .fill(egui::Color32::from_rgb(28, 25, 38))
                            .stroke(egui::Stroke::new(1.0, egui::Color32::from_rgb(91, 72, 145)))
                            .rounding(egui::Rounding::same(4))
                            .inner_margin(egui::Margin::symmetric(7, 6))
                            .show(ui, |ui| {
                                ui.horizontal(|ui| {
                                    ui.label(egui::RichText::new("NATIVE OFFER ENGINE").size(9.0).strong().color(egui::Color32::from_rgb(181, 150, 255)));
                                    ui.label(egui::RichText::new("v5.1 • PROPOSAL MAPPER • READ-ONLY").size(7.5).color(egui::Color32::from_rgb(154, 169, 194)));
                                });
                                ui.label(egui::RichText::new("Goal: map FM's real Transfer Proposal so a later CREATE OFFER produces money, Inbox/Transfer Centre and player history natively.").size(7.7).color(egui::Color32::from_rgb(194, 199, 212)));

                                let fee_id = egui::Id::new(("element_proposal_probe_fee_v51", player.addr));
                                let mut fee_text = ui.data_mut(|d| d.get_temp::<String>(fee_id).unwrap_or_else(|| "50000000".to_owned()));
                                ui.horizontal(|ui| {
                                    ui.label(egui::RichText::new("REAL OFFER FEE (£ raw)").size(7.8).color(egui::Color32::from_rgb(154, 169, 194)));
                                    ui.add(egui::TextEdit::singleline(&mut fee_text).desired_width(120.0).hint_text("50000000"));
                                });
                                ui.data_mut(|d| d.insert_temp(fee_id, fee_text.clone()));
                                let clean_fee = fee_text.replace([',', '.', ' ', '£', '€', '$'], "");
                                let parsed_fee = clean_fee.parse::<u64>().ok().filter(|v| *v > 0);
                                let probe_enabled = player.contract_addr.is_some();

                                ui.horizontal_wrapped(|ui| {
                                    if ui.add_enabled(probe_enabled, egui::Button::new("① CAPTURE BEFORE OFFER"))
                                        .on_hover_text("Take a read-only baseline of the verified player → contract → source team → source club chain BEFORE FM has the real bid.")
                                        .clicked()
                                    {
                                        if let Some(contract_addr) = player.contract_addr {
                                            let req_id = egui::Id::new("element_proposal_probe_before_v51");
                                            ui.ctx().data_mut(|d| d.insert_temp(req_id, (player.addr, player.person_shift, contract_addr)));
                                        }
                                    }

                                    if ui.add_enabled(probe_enabled && parsed_fee.is_some(), egui::Button::new("② COMPARE AFTER REAL OFFER"))
                                        .on_hover_text("After a genuine FM bid exists, select the bidding club here, enter the exact up-front fee, then compare. New linked pointers are followed and scored for player/club/fee witnesses.")
                                        .clicked()
                                    {
                                        if let (Some(contract_addr), Some(expected_fee)) = (player.contract_addr, parsed_fee) {
                                            let req_id = egui::Id::new("element_proposal_probe_after_v51");
                                            ui.ctx().data_mut(|d| d.insert_temp(req_id, (player.addr, player.person_shift, contract_addr, club.addr, expected_fee)));
                                        }
                                    }
                                });
                                ui.label(egui::RichText::new("Workflow: BEFORE → let FM generate one genuine bid → select that bidder + exact fee → AFTER. The mapper writes no game memory.").size(7.4).color(egui::Color32::from_rgb(164, 172, 190)));
                            });
                        ui.add_space(6.0);
'''
    t = t.replace(mapper_marker, mapper_ui + mapper_marker, 1)

p.write_text(t, encoding="utf-8")

# ---------------------------------------------------------------------------
# app.rs — dispatch UI temp requests and surface report path/status
# ---------------------------------------------------------------------------
p = root / "src" / "app.rs"
t = p.read_text(encoding="utf-8")

result_anchor = '''                BridgeResult::ForceTransferOk(report) => {'''
if "BridgeResult::ProposalProbeReady" not in t:
    if result_anchor not in t:
        raise SystemExit("v5.1: ForceTransfer result handler marker missing in app.rs")
    result_handlers = r'''                BridgeResult::ProposalProbeReady { player_addr: _, source_club_addr, chunks } => {
                    self.set_status(format!("Native Offer Mapper: BEFORE captured • source club 0x{source_club_addr:X} • {chunks} readable chunks. Now let FM generate one real bid."));
                }
                BridgeResult::ProposalProbeDone { player_addr: _, candidates, report_path, summary } => {
                    self.set_status(format!("Native Offer Mapper: {candidates} candidate(s) • {summary} • report: {report_path}"));
                }
                BridgeResult::ProposalProbeFail { player_addr: _, error } => {
                    self.set_status(format!("Native Offer Mapper: {error}"));
                }
'''
    t = t.replace(result_anchor, result_handlers + result_anchor, 1)

request_anchor = '''        // Element v5.0 guarded Force Transfer request. The worker owns the\n'''
if "element_proposal_probe_before_v51" not in t:
    if request_anchor not in t:
        raise SystemExit("v5.1: Force Transfer request marker missing in app.rs")
    request_code = r'''        // Element v5.1 Native Offer Mapper — read-only before/after witness capture.
        let proposal_probe_before = ctx.data_mut(|d| {
            let id = egui::Id::new("element_proposal_probe_before_v51");
            let request = d.get_temp::<(u64, usize, u64)>(id);
            d.remove::<(u64, usize, u64)>(id);
            request
        });
        if let Some((player_addr, person_shift, contract_addr)) = proposal_probe_before {
            if self.conn.is_writable() {
                self.bridge.send(BridgeCmd::ProposalProbeBaseline { player_addr, person_shift, contract_addr });
                self.set_status("Native Offer Mapper: capturing BEFORE snapshot…".into());
            } else {
                self.set_status("Native Offer Mapper requires a live FM27 session".into());
            }
        }

        let proposal_probe_after = ctx.data_mut(|d| {
            let id = egui::Id::new("element_proposal_probe_after_v51");
            let request = d.get_temp::<(u64, usize, u64, u64, u64)>(id);
            d.remove::<(u64, usize, u64, u64, u64)>(id);
            request
        });
        if let Some((player_addr, person_shift, contract_addr, target_club_addr, expected_fee)) = proposal_probe_after {
            if self.conn.is_writable() {
                self.bridge.send(BridgeCmd::ProposalProbeCompare {
                    player_addr,
                    person_shift,
                    contract_addr,
                    target_club_addr,
                    expected_fee,
                });
                self.set_status("Native Offer Mapper: comparing AFTER snapshot and following changed pointers…".into());
            } else {
                self.set_status("Native Offer Mapper requires a live FM27 session".into());
            }
        }

'''
    t = t.replace(request_anchor, request_code + request_anchor, 1)

p.write_text(t, encoding="utf-8")

print("Element v5.1 Native Offer / Proposal Mapper applied successfully.")
