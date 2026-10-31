from pathlib import Path

root = Path.cwd()

# Element v6.1.1 — native TransferOffer ADD/REMOVE delta certification.
# This extends the read-only mapper so an already-existing FM bid can be used:
# capture WITH the bid present, reject/withdraw that one bid in FM, then compare.
# For removals we follow the OLD pointer instead of only the NEW pointer.
# Zero-fee offers are supported without treating every zero byte as fee evidence.

p = root / "src" / "bridge" / "worker.rs"
t = p.read_text(encoding="utf-8")

# Avoid meaningless fee witnesses for free/zero-fee offers.
old_fee = '''    if expected_fee <= u32::MAX as u64 && element_v51_contains_u32(bytes, expected_fee as u32) {
        tags.push("fee_u32");
    }
    if element_v51_contains_u64(bytes, expected_fee) { tags.push("fee_u64"); }
'''
new_fee = '''    if expected_fee > 0 {
        if expected_fee <= u32::MAX as u64 && element_v51_contains_u32(bytes, expected_fee as u32) {
            tags.push("fee_u32");
        }
        if element_v51_contains_u64(bytes, expected_fee) { tags.push("fee_u64"); }
    }
'''
if old_fee not in t:
    raise SystemExit("v6.1.1: fee witness block not found")
t = t.replace(old_fee, new_fee, 1)

# Replace the v6 new-pointer-only scan with a bidirectional delta scan.
old_scan = '''            if element_v5_ptr_ok(new) {
                if let Ok(blob) = fm.read_bytes(new, 0x800) {
                    let tags = element_v51_candidate_tags(
                        &blob,
                        snap,
                        target_team,
                        target_club_addr,
                        expected_fee,
                    );
                    if tags.len() >= 2 {
                        let has_seller = tags.iter().any(|t| *t == "source_team" || *t == "source_club");
                        let has_buyer = tags.iter().any(|t| *t == "target_team" || *t == "target_club");
                        let has_fee = tags.iter().any(|t| *t == "fee_u32" || *t == "fee_u64");
                        // FMRTE 27 build2 exposes TransferOffer with BuyerTeam,
                        // SellerTeam and Fee/TotalValue semantics.  Reward the
                        // exact three-witness shape strongly when it appears.
                        let semantic_bonus = (has_seller as usize) * 2
                            + (has_buyer as usize) * 2
                            + (has_fee as usize) * 3;
                        let score = tags.len() + semantic_bonus;
                        candidates.push((score, format!(
                            "{} +0x{:X} -> 0x{:X} | {}{}",
                            before.label,
                            off,
                            new,
                            tags.join(", "),
                            if has_seller && has_buyer && has_fee { " | TRANSFER-OFFER SHAPE" } else { "" }
                        )));

                        // A club usually owns a collection/list which in turn
                        // references the actual TransferOffer.  Walk one child
                        // pointer level so the v6 test no longer depends on the
                        // offer object being linked directly from a changed slot.
                        for child_off in (0..blob.len().saturating_sub(7)).step_by(8) {
                            let child = u64::from_le_bytes(blob[child_off..child_off + 8].try_into().unwrap());
                            if !element_v5_ptr_ok(child) || child == new { continue; }
                            let Ok(child_blob) = fm.read_bytes(child, 0x500) else { continue; };
                            let child_tags = element_v51_candidate_tags(
                                &child_blob,
                                snap,
                                target_team,
                                target_club_addr,
                                expected_fee,
                            );
                            if child_tags.len() < 2 { continue; }
                            let child_seller = child_tags.iter().any(|t| *t == "source_team" || *t == "source_club");
                            let child_buyer = child_tags.iter().any(|t| *t == "target_team" || *t == "target_club");
                            let child_fee = child_tags.iter().any(|t| *t == "fee_u32" || *t == "fee_u64");
                            let child_bonus = (child_seller as usize) * 2
                                + (child_buyer as usize) * 2
                                + (child_fee as usize) * 3
                                + 1; // child-object evidence
                            candidates.push((child_tags.len() + child_bonus, format!(
                                "{} +0x{:X} -> 0x{:X} -> child +0x{:X} 0x{:X} | {}{}",
                                before.label,
                                off,
                                new,
                                child_off,
                                child,
                                child_tags.join(", "),
                                if child_seller && child_buyer && child_fee { " | TRANSFER-OFFER SHAPE" } else { "" }
                            )));
                        }
                    }
                }
            }
'''
new_scan = '''            // v6.1.1: inspect BOTH sides of the delta.
            // ADD path: follow NEW pointer. REMOVE path: follow OLD pointer.
            for (direction, ptr) in [("ADD", new), ("REMOVE", old)] {
                if !element_v5_ptr_ok(ptr) { continue; }
                if let Ok(blob) = fm.read_bytes(ptr, 0x800) {
                    let tags = element_v51_candidate_tags(
                        &blob,
                        snap,
                        target_team,
                        target_club_addr,
                        expected_fee,
                    );
                    if tags.len() >= 2 {
                        let has_seller = tags.iter().any(|t| *t == "source_team" || *t == "source_club");
                        let has_buyer = tags.iter().any(|t| *t == "target_team" || *t == "target_club");
                        let has_fee = tags.iter().any(|t| *t == "fee_u32" || *t == "fee_u64");
                        let semantic_bonus = (has_seller as usize) * 2
                            + (has_buyer as usize) * 2
                            + (has_fee as usize) * 3
                            + if direction == "REMOVE" { 1 } else { 0 };
                        let score = tags.len() + semantic_bonus;
                        let shape = has_seller && has_buyer && (has_fee || expected_fee == 0);
                        candidates.push((score, format!(
                            "[{direction}] {} +0x{:X} -> 0x{:X} | {}{}",
                            before.label,
                            off,
                            ptr,
                            tags.join(", "),
                            if shape { " | TRANSFER-OFFER SHAPE" } else { "" }
                        )));

                        for child_off in (0..blob.len().saturating_sub(7)).step_by(8) {
                            let child = u64::from_le_bytes(blob[child_off..child_off + 8].try_into().unwrap());
                            if !element_v5_ptr_ok(child) || child == ptr { continue; }
                            let Ok(child_blob) = fm.read_bytes(child, 0x500) else { continue; };
                            let child_tags = element_v51_candidate_tags(
                                &child_blob,
                                snap,
                                target_team,
                                target_club_addr,
                                expected_fee,
                            );
                            if child_tags.len() < 2 { continue; }
                            let child_seller = child_tags.iter().any(|t| *t == "source_team" || *t == "source_club");
                            let child_buyer = child_tags.iter().any(|t| *t == "target_team" || *t == "target_club");
                            let child_fee = child_tags.iter().any(|t| *t == "fee_u32" || *t == "fee_u64");
                            let child_bonus = (child_seller as usize) * 2
                                + (child_buyer as usize) * 2
                                + (child_fee as usize) * 3
                                + 1
                                + if direction == "REMOVE" { 1 } else { 0 };
                            let child_shape = child_seller && child_buyer && (child_fee || expected_fee == 0);
                            candidates.push((child_tags.len() + child_bonus, format!(
                                "[{direction}] {} +0x{:X} -> 0x{:X} -> child +0x{:X} 0x{:X} | {}{}",
                                before.label,
                                off,
                                ptr,
                                child_off,
                                child,
                                child_tags.join(", "),
                                if child_shape { " | TRANSFER-OFFER SHAPE" } else { "" }
                            )));
                        }
                    }
                }
            }
'''
if old_scan not in t:
    raise SystemExit("v6.1.1: v6 pointer scan block not found")
t = t.replace(old_scan, new_scan, 1)

# Report wording for add/remove workflow.
t = t.replace(
    'report.push_str("Element FM27 v6.0 Native TransferOffer Certifier\\n");',
    'report.push_str("Element FM27 v6.1.1 Native TransferOffer ADD/REMOVE Certifier\\n");',
    1,
)
t = t.replace(
    'report.push_str("Certification rule: prefer a repeated candidate containing seller + buyer + exact fee; verify the same relative offsets across at least two independent offers before enabling native writes.\\n");',
    'report.push_str("Certification rule: ADD follows new pointers; REMOVE follows old pointers. For zero-fee offers, require seller+buyer and repeat the same relative layout across independent offers.\\n");',
    1,
)
t = t.replace(
    'std::env::temp_dir().join("Element-FM27-v6-TransferOffer-Certifier.txt")',
    'std::env::temp_dir().join("Element-FM27-v6.1.1-TransferOffer-Delta-Certifier.txt")',
    1,
)
p.write_text(t, encoding="utf-8")

# UI: make the existing two-button workflow clear for both ADD and REMOVE deltas.
p = root / "src" / "ui" / "player_panel.rs"
t = p.read_text(encoding="utf-8")
t = t.replace('"v6.0 • NATIVE TRANSFER OFFER CERTIFIER"', '"v6.1.1 • NATIVE OFFER ADD/REMOVE CERTIFIER"')
t = t.replace('"① CAPTURE BEFORE NATIVE BID"', '"① CAPTURE CURRENT OFFER STATE"')
t = t.replace('"② CERTIFY AFTER REAL BID"', '"② CERTIFY AFTER ADD / REMOVE"')
t = t.replace(
    '"After a genuine FM bid exists, select the bidding club and enter the exact up-front fee. v6 scans linked and child objects, heavily scoring the FMRTE-observed TransferOffer shape: SellerTeam + BuyerTeam + Fee/TotalValue."',
    '"Works both ways: capture before creating a bid, OR capture while an existing bid is present and then reject/withdraw that one bid. Select the bidder and exact fee; €0/£0 offers are supported via seller+buyer witnesses."',
)
p.write_text(t, encoding="utf-8")

print("Element v6.1.1 native offer ADD/REMOVE delta certifier applied successfully.")
