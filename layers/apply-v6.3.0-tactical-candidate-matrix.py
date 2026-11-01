from pathlib import Path

root = Path.cwd()

def rd(path):
    p = root / path
    if not p.exists():
        raise SystemExit(f"v6.3.0 missing {path}")
    return p.read_text(encoding="utf-8")

def wr(path, text):
    (root / path).write_text(text, encoding="utf-8")

def one(text, old, new, label):
    if old not in text:
        raise SystemExit(f"v6.3.0 marker missing: {label}")
    return text.replace(old, new, 1)

# Carry player names through the tactical planner so candidate values can be
# shown as a human-readable witness matrix (Jesus/Rodri/Yamal etc.).
cmd_path = "src/bridge/cmd.rs"
cmd = rd(cmd_path)
cmd = cmd.replace(
    "pub scalar_candidates: Vec<String>,\n    pub edits: Vec<TacticalMaxPlannedEdit>,",
    "pub scalar_candidates: Vec<String>,\n    pub candidate_matrix: Vec<String>,\n    pub edits: Vec<TacticalMaxPlannedEdit>,",
    1,
)
cmd = cmd.replace(
    "PlanSelectedClubTacticalMax { club_addr: u64, senior_team_addr: u64, player_addrs: Vec<u64> },",
    "PlanSelectedClubTacticalMax { club_addr: u64, senior_team_addr: u64, player_refs: Vec<(u64, String)> },",
    1,
)
cmd = cmd.replace(
    "pub tactical_max_plan: Option<TacticalMaxPlan>,",
    "pub tactical_max_plan: Option<TacticalMaxPlan>,\n    pub tactical_probe_matrix: Vec<String>,",
    1,
)
wr(cmd_path, cmd)

entity_path = "src/bridge/entity_load.rs"
entity = rd(entity_path)
entity = entity.replace(
    "tactical_max_plan: None,",
    "tactical_max_plan: None,\n        tactical_probe_matrix: Vec::new(),",
    1,
)
wr(entity_path, entity)

# Planner: accept (addr,name), preserve names for the read-only witness matrix.
plan_path = "src/bridge/tactical_max_plan.rs"
plan = rd(plan_path)
plan = plan.replace(
    "player_addrs: &[u64],",
    "player_refs: &[(u64, String)],",
    1,
)
plan = plan.replace(
    "players_examined: player_addrs.len(),",
    "players_examined: player_refs.len(),",
    1,
)
plan = plan.replace(
    "let mut matched_players: Vec<u64> = Vec::new();",
    "let mut matched_players: Vec<(u64, String)> = Vec::new();",
    1,
)
plan = plan.replace(
    "for &player in player_addrs {",
    "for (player_ref, player_name) in player_refs {\n        let player = *player_ref;",
    1,
)
plan = plan.replace(
    "matched_players.push(player);",
    "matched_players.push((player, player_name.clone()));",
    1,
)
plan = plan.replace("for &player in &matched_players {", "for (player, _) in &matched_players {", 2)
plan = plan.replace("fm.read_bytes(player + off, 2)", "fm.read_bytes(*player + off, 2)")
plan = plan.replace("fm.read_bytes(player + off, 1)", "fm.read_bytes(*player + off, 1)")

# Build a compact matrix from the strongest P16 candidates. This is diagnostic
# only: no candidate offset is written by v6.3.0.
needle = '''    player_u16.sort_by(|a, b| b.5.cmp(&a.5).then_with(|| a.0.cmp(&b.0)));
    for (off, min, max, distinct, avg, score) in player_u16.into_iter().take(12) {
        plan.scalar_candidates.push(format!(
            "P16+0x{off:X}: min={min} max={max} avg={avg} distinct={distinct} score={score}"
        ));
    }
'''
replacement = '''    player_u16.sort_by(|a, b| b.5.cmp(&a.5).then_with(|| a.0.cmp(&b.0)));
    let top_p16: Vec<u64> = player_u16.iter().take(3).map(|x| x.0).collect();
    for (off, min, max, distinct, avg, score) in player_u16.iter().take(12).copied() {
        plan.scalar_candidates.push(format!(
            "P16+0x{off:X}: min={min} max={max} avg={avg} distinct={distinct} score={score}"
        ));
    }
    for off in top_p16 {
        let mut row = format!("P16+0x{off:X}");
        for (player, name) in &matched_players {
            if let Ok(bytes) = fm.read_bytes(*player + off, 2) {
                if bytes.len() == 2 {
                    let v = u16::from_le_bytes([bytes[0], bytes[1]]);
                    row.push_str(&format!(" | {name}={v}"));
                }
            }
        }
        plan.candidate_matrix.push(row);
    }
'''
plan = one(plan, needle, replacement, "P16 candidate matrix")
wr(plan_path, plan)

# Worker field rename.
worker_path = "src/bridge/worker.rs"
worker = rd(worker_path)
worker = worker.replace(
    "BridgeCmd::PlanSelectedClubTacticalMax { club_addr, senior_team_addr, player_addrs } => {",
    "BridgeCmd::PlanSelectedClubTacticalMax { club_addr, senior_team_addr, player_refs } => {",
    1,
)
worker = worker.replace(
    "tactical_max_plan::plan_first_team(f, club_addr, senior_team_addr, &player_addrs)",
    "tactical_max_plan::plan_first_team(f, club_addr, senior_team_addr, &player_refs)",
    1,
)
wr(worker_path, worker)

# App request tuple now carries names. Persist matrix on ClubView before plan is consumed.
app_path = "src/app.rs"
app = rd(app_path)
app = app.replace(
    "d.get_temp::<(u64, u64, Vec<u64>)>(id);\n            d.remove::<(u64, u64, Vec<u64>)>(id);",
    "d.get_temp::<(u64, u64, Vec<(u64, String)>)>(id);\n            d.remove::<(u64, u64, Vec<(u64, String)>)>(id);",
    1,
)
app = app.replace(
    "if let Some((club_addr, senior_team_addr, player_addrs)) = tactical_max_request {",
    "if let Some((club_addr, senior_team_addr, player_refs)) = tactical_max_request {",
    1,
)
app = app.replace(
    "club_addr, senior_team_addr, player_addrs,",
    "club_addr, senior_team_addr, player_refs,",
    1,
)
app = app.replace(
    "snapshot.tactical_max_plan = Some(plan.clone());",
    "snapshot.tactical_probe_matrix = plan.candidate_matrix.clone();\n                        snapshot.tactical_max_plan = Some(plan.clone());",
    1,
)
app = app.replace(
    "club.tactical_max_plan = Some(plan);",
    "club.tactical_probe_matrix = plan.candidate_matrix.clone();\n                        club.tactical_max_plan = Some(plan);",
    1,
)
wr(app_path, app)

# Club UI: send names and show persistent candidate matrix.
club_path = "src/ui/club_panel.rs"
club = rd(club_path)
club = club.replace(
    "let club_players: Vec<u64> = navigation::entity_cache(ui)\n                    .map(|cache| cache.players.iter()\n                        .filter(|p| p.club_id == Some(club.uid))\n                        .map(|p| p.addr)\n                        .collect())",
    "let club_players: Vec<(u64, String)> = navigation::entity_cache(ui)\n                    .map(|cache| cache.players.iter()\n                        .filter(|p| p.club_id == Some(club.uid))\n                        .map(|p| (p.addr, p.name.clone()))\n                        .collect())",
    1,
)

matrix_ui = r'''
    if !club.tactical_probe_matrix.is_empty() {
        ui.add_space(6.0);
        egui::Frame::group(ui.style()).show(ui, |ui| {
            ui.strong("TACTICAL CANDIDATE MATRIX • READ ONLY");
            ui.small("Top player-level u16 candidates. Compare low/high values against FM27 Shape/Build Up witnesses; these offsets are not writable yet.");
            for row in &club.tactical_probe_matrix {
                ui.monospace(row);
            }
        });
    }

'''
anchor = "    ui.add_space(3.0);\n\n    // Element v6.2.5"
if "TACTICAL CANDIDATE MATRIX • READ ONLY" not in club:
    club = one(club, anchor, matrix_ui + anchor, "candidate matrix UI")
wr(club_path, club)

print("Element v6.3.0 Tactical Candidate Matrix applied.")
