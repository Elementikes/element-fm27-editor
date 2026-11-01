from pathlib import Path

root = Path.cwd()

def rd(path):
    p = root / path
    if not p.exists():
        raise SystemExit(f"v6.4.3 missing {path}")
    return p.read_text(encoding="utf-8")

def wr(path, text):
    (root / path).write_text(text, encoding="utf-8")

# Extend the existing read-only tactical planner with SeniorTeam-level scalar
# candidates. FMRTE metadata exposes TeamCohesion as a separate model from
# PlayerTacticalFamiliarity/TacticFamiliarity, so this deliberately probes the
# selected SeniorTeam object rather than writing unknown bytes.
plan_path = "src/bridge/tactical_max_plan.rs"
plan = rd(plan_path)
marker = "    Ok(plan)\n}\n"
if "v6.4.3: FMRTE TeamCohesion SeniorTeam probe" not in plan:
    block = r'''    // v6.4.3: FMRTE TeamCohesion SeniorTeam probe (READ ONLY).
    // User-provided FMRTE27 metadata exposes TeamCohesion as its own model,
    // separate from PlayerTacticalFamiliarity/TacticFamiliarity. Scan only the
    // selected SeniorTeam object and surface plausible bounded scalars. No
    // candidate discovered here is ever converted into a write automatically.
    let mut tc16: Vec<(u64, u16, u64)> = Vec::new();
    for off in (0x00u64..=0x7FEu64).step_by(2) {
        if let Ok(bytes) = fm.read_bytes(senior_team_addr + off, 2) {
            if bytes.len() == 2 {
                let v = u16::from_le_bytes([bytes[0], bytes[1]]);
                if v == 0 || v > 10_000 { continue; }
                let scale_bonus = if v <= 100 { 12_000 } else if v >= 1_000 { 8_000 } else { 2_000 };
                let edge_bonus = if v == 100 || v == 10_000 { 6_000 } else { 0 };
                let score = scale_bonus + edge_bonus + (v as u64).min(10_000);
                tc16.push((off, v, score));
            }
        }
    }
    tc16.sort_by(|a, b| b.2.cmp(&a.2).then_with(|| a.0.cmp(&b.0)));
    for (off, value, score) in tc16.into_iter().take(12) {
        plan.candidate_matrix.push(format!(
            "TC16+0x{off:X} | SeniorTeam={value} | score={score} | READ ONLY"
        ));
    }

    let mut tc8: Vec<(u64, u8, u64)> = Vec::new();
    for off in 0x00u64..=0x7FFu64 {
        if let Ok(bytes) = fm.read_bytes(senior_team_addr + off, 1) {
            if bytes.len() == 1 {
                let v = bytes[0];
                if v == 0 || v > 100 { continue; }
                let score = 10_000 + (v as u64) * 100 + if v == 100 { 6_000 } else { 0 };
                tc8.push((off, v, score));
            }
        }
    }
    tc8.sort_by(|a, b| b.2.cmp(&a.2).then_with(|| a.0.cmp(&b.0)));
    for (off, value, score) in tc8.into_iter().take(8) {
        plan.candidate_matrix.push(format!(
            "TC8+0x{off:X} | SeniorTeam={value} | score={score} | READ ONLY"
        ));
    }

'''
    if marker not in plan:
        raise SystemExit("v6.4.3 planner return marker missing")
    plan = plan.replace(marker, block + marker, 1)
wr(plan_path, plan)

# Make the UI clearly distinguish player familiarity candidates from the new
# SeniorTeam TeamCohesion candidates and surface the exact FMRTE semantic hints.
club_path = "src/ui/club_panel.rs"
club = rd(club_path)
club = club.replace("v6.4.2 • FMRTE TACTICAL CHAIN", "v6.4.3 • FMRTE COHESION MAPPER", 1)
club = club.replace("FMRTE27 VERIFIED + DERIVED MODEL", "FMRTE27 TEAM COHESION MAPPER", 1)
club = club.replace("FAMILIARITY WRITE VERIFIED", "FAMILIARITY VERIFIED • COHESION READ-ONLY", 1)
club = club.replace("TACTICAL CANDIDATE MATRIX • READ ONLY", "FMRTE / FM27 MAPPING MATRIX • READ ONLY", 1)
club = club.replace(
    "Top player-level u16 candidates. Compare low/high values against FM27 Shape/Build Up witnesses; these offsets are not writable yet.",
    "P16/P8 = player context candidates. TC16/TC8 = selected SeniorTeam candidates for FMRTE TeamCohesion. All mapper rows are read-only until independently certified.",
    1,
)

# Add a compact semantic breadcrumb from the FMRTE metadata inspected offline.
anchor = '            ui.label(egui::RichText::new("Observed FM27 after MAX:").strong());\n'
if "FMRTE type hints:" not in club and anchor in club:
    semantic = '''            ui.horizontal_wrapped(|ui| {
                ui.label(egui::RichText::new("FMRTE type hints:").strong());
                ui.label("TeamCohesion • PlayerTacticalFamiliarity • TacticFamiliarity • TacticalArea • TacticalAttributes • TeamTactic/TeamTactics");
            });
            ui.add_space(3.0);
'''
    club = club.replace(anchor, semantic + anchor, 1)

club = club.replace(
    "⚡ FULL FMRTE CHAIN • COHESION LOCKED",
    "⚡ FULL FMRTE CHAIN • COHESION MAPPING",
    1,
)
club = club.replace(
    "FMRTE resource chain is MaxTacticalFamiliarity → ImproveTeamCohesion. Familiarity is verified; cohesion has no certified FM27 write mapping yet, so Element refuses a blind write.",
    "FMRTE resource chain is MaxTacticalFamiliarity → ImproveTeamCohesion. v6.4.3 now maps bounded SeniorTeam candidates read-only; write remains locked until one TeamCohesion field is independently certified.",
    1,
)
wr(club_path, club)

print("Element v6.4.3 FMRTE Team Cohesion Mapper applied.")
