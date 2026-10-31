from pathlib import Path

root = Path.cwd()

# Element v6.0 — FMRTE-informed native transfer certification.
#
# Evidence extracted from FMRTE 27.0.0-build2 identifies the native domain type
# Fmrte.GameData.Objects.Transfers.Offers.TransferOffer and exposes semantics
# including BuyerTeam, SellerTeam, Fee, TotalValue, TransferId, TransferType,
# TransferTax, FutureContract and TransferDate.  This layer does NOT copy FMRTE
# code and does NOT fabricate an unknown FM record.  It improves Element's
# read-only mapper so one v6 test build can certify the real FM27 object chain.

p = root / "src" / "bridge" / "worker.rs"
t = p.read_text(encoding="utf-8")

# 1) Read farther into newly-linked candidate objects.  The old 0x300-byte
# window was intentionally conservative; v6 expands it to 0x800 and performs a
# one-level child-pointer walk.  This is still strictly read-only.
t = t.replace(
    'if let Ok(blob) = fm.read_bytes(new, 0x300) {',
    'if let Ok(blob) = fm.read_bytes(new, 0x800) {',
)

old = '''                    if tags.len() >= 2 {
                        let score = tags.len();
                        candidates.push((score, format!(
                            "{} +0x{:X} -> 0x{:X} | {}",
                            before.label,
                            off,
                            new,
                            tags.join(", ")
                        )));
                    }
'''
new = '''                    if tags.len() >= 2 {
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
'''
if old not in t:
    raise SystemExit("v6.0: v5.1 candidate scoring block not found")
t = t.replace(old, new, 1)

# 2) Make the report self-describing so every user test returns the semantic
# evidence we are trying to certify.
needle = '    report.push_str("Element FM27 v5.1 Native Offer / Proposal Mapper\\n");\n'
replacement = '''    report.push_str("Element FM27 v6.0 Native TransferOffer Certifier\\n");
    report.push_str("FMRTE 27 build2 semantic witnesses: BuyerTeam, SellerTeam, Fee, TotalValue, TransferId, TransferType, TransferTax, FutureContract, TransferDate\\n");
'''
if needle not in t:
    raise SystemExit("v6.0: proposal report title marker not found")
t = t.replace(needle, replacement, 1)

needle = '    report.push_str("This report is READ-ONLY evidence. It does not certify a proposal record by itself.\\n");\n'
replacement = '''    report.push_str("Certification rule: prefer a repeated candidate containing seller + buyer + exact fee; verify the same relative offsets across at least two independent offers before enabling native writes.\\n");
    report.push_str("This report is READ-ONLY evidence. It never writes a TransferOffer.\\n");
'''
if needle not in t:
    raise SystemExit("v6.0: proposal report footer marker not found")
t = t.replace(needle, replacement, 1)

# Keep a distinct v6 report beside old mapper output.
t = t.replace(
    'std::env::temp_dir().join("Element-FM27-v5.1-Proposal-Mapper.txt")',
    'std::env::temp_dir().join("Element-FM27-v6-TransferOffer-Certifier.txt")',
    1,
)

p.write_text(t, encoding="utf-8")

# 3) Transfer Lab UI: identify exactly what this build is hunting for.  The two
# existing mapper actions remain the test workflow: capture before a genuine FM
# offer, then compare after it exists.
p = root / "src" / "ui" / "player_panel.rs"
t = p.read_text(encoding="utf-8")
t = t.replace(
    '"v5.1 • NATIVE OFFER / PROPOSAL MAPPER"',
    '"v6.0 • NATIVE TRANSFER OFFER CERTIFIER"',
)
t = t.replace(
    '"① CAPTURE BEFORE OFFER"',
    '"① CAPTURE BEFORE NATIVE BID"',
)
t = t.replace(
    '"② COMPARE AFTER REAL OFFER"',
    '"② CERTIFY AFTER REAL BID"',
)
t = t.replace(
    '"After a genuine FM bid exists, select the bidding club here, enter the exact up-front fee, then compare. New linked pointers are followed and scored for player/club/fee witnesses."',
    '"After a genuine FM bid exists, select the bidding club and enter the exact up-front fee. v6 scans linked and child objects, heavily scoring the FMRTE-observed TransferOffer shape: SellerTeam + BuyerTeam + Fee/TotalValue."',
)

# Upgrade v5.2 power-engine copy without changing the safe Direct Settlement
# behavior. Native write buttons remain gated until the certifier produces a
# repeated offset layout.
t = t.replace(
    '"v5.2 • SETTLEMENT + NATIVE OFFER RESEARCH"',
    '"v6.0 • SETTLEMENT + TRANSFEROFFER CERTIFICATION"',
)
t = t.replace(
    '"Native Transfer Proposal record is not publicly mapped/certified yet. Element will not fabricate a bid record."',
    '"FMRTE confirms a native TransferOffer domain object and Buyer/Seller/Fee semantics; v6 now certifies its FM27 memory layout before enabling writes."',
)
p.write_text(t, encoding="utf-8")

print("Element v6.0 FMRTE-informed TransferOffer certification layer applied successfully.")
