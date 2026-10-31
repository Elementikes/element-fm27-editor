from pathlib import Path

root = Path.cwd()

def rd(path):
    p = root / path
    if not p.exists():
        raise SystemExit(f"v6.2.6 missing {path}")
    return p.read_text(encoding="utf-8")

def wr(path, text):
    (root / path).write_text(text, encoding="utf-8")

def one(text, old, new, label):
    if old not in text:
        raise SystemExit(f"v6.2.6 marker missing: {label}")
    return text.replace(old, new, 1)

# Bridge protocol: read-only planner. Actual mutations still go through the
# editor's existing FieldEdit -> compare-before-write -> Undo pipeline.
cmd_path = "src/bridge/cmd.rs"
cmd = rd(cmd_path)
if "pub struct TacticalMaxPlannedEdit" not in cmd:
    marker = "/// Full staff data including name and role sub-record.\n"
    defs = '''#[derive(Clone, Debug)]
pub struct TacticalMaxPlannedEdit {
    pub addr: u64,
    pub old_raw: Vec<u8>,
    pub new_raw: Vec<u8>,
    pub description: String,
}

#[derive(Clone, Debug, Default)]
pub struct TacticalMaxPlan {
    pub club_addr: u64,
    pub senior_team_addr: u64,
    pub players_examined: usize,
    pub players_matched: usize,
    pub instruction_entries: usize,
    pub formation_rows: usize,
    pub already_maxed: usize,
    pub edits: Vec<TacticalMaxPlannedEdit>,
}

'''
    cmd = one(cmd, marker, defs + marker, "planner structs")
if "PlanSelectedClubTacticalMax" not in cmd:
    cmd = one(cmd,
        "    InspectTacticalKnowledge { club_addr: u64, senior_team_addr: u64 },\n",
        "    InspectTacticalKnowledge { club_addr: u64, senior_team_addr: u64 },\n"
        "    PlanSelectedClubTacticalMax { club_addr: u64, senior_team_addr: u64, player_addrs: Vec<u64> },\n",
        "planner command")
if "TacticalMaxPlanReady" not in cmd:
    cmd = one(cmd,
        "    TacticalInspectorDone { club_addr: u64, report: TacticalInspectorReport },\n",
        "    TacticalInspectorDone { club_addr: u64, report: TacticalInspectorReport },\n"
        "    TacticalMaxPlanReady { club_addr: u64, plan: TacticalMaxPlan },\n",
        "planner result")
wr(cmd_path, cmd)

# Module registration.
mod_path = "src/bridge/mod.rs"
mod = rd(mod_path)
if "mod tactical_max_plan;" not in mod:
    mod = one(mod, "mod tactical_inspector;\n", "mod tactical_inspector;\nmod tactical_max_plan;\n", "bridge module")
wr(mod_path, mod)

# Read-only live planner.
(root / "src/bridge/tactical_max_plan.rs").write_text(r'''use std::collections::HashSet;

use crate::player::is_valid_ptr;
use crate::process::FmProcess;

use super::cmd::{TacticalMaxPlan, TacticalMaxPlannedEdit};

const PLAYER_TACTICAL_PTR: u64 = 0x100;
const PLAYER_TEAM_PTR: u64 = 0x130;
const CATEGORIES: usize = 6;
const CATEGORY_STRIDE: u64 = 0x20;
const FORMATION_VECTOR: u64 = 0xC0;
const DIRTY_FLAG: u64 = 0xDC;
const KNOWLEDGE_MASK: u32 = 0x3FFF;
const MAX_KNOWLEDGE: u32 = 10_000;
const FORMATION_ROW: usize = 16;
const FORMATION_VALUE: u64 = 14;

fn u64_at(fm: &FmProcess, addr: u64) -> Result<u64, String> {
    let b = fm.read_bytes(addr, 8)?;
    Ok(u64::from_le_bytes(b.as_slice().try_into().map_err(|_| "short pointer read")?))
}

fn vec_info(fm: &FmProcess, addr: u64, stride: usize, max: usize) -> Result<(u64, usize), String> {
    let b = fm.read_bytes(addr, 24)?;
    let data = u64::from_le_bytes(b[0..8].try_into().unwrap());
    let end = u64::from_le_bytes(b[8..16].try_into().unwrap());
    let cap = u64::from_le_bytes(b[16..24].try_into().unwrap());
    if !is_valid_ptr(data) || !is_valid_ptr(end) || !is_valid_ptr(cap) || end < data || cap < end {
        return Err(format!("invalid tactical vector @0x{addr:X}"));
    }
    let span = usize::try_from(end - data).map_err(|_| "vector span overflow")?;
    if span % stride != 0 || span / stride > max {
        return Err(format!("implausible tactical vector @0x{addr:X}"));
    }
    Ok((data, span / stride))
}

fn add_edit(plan: &mut TacticalMaxPlan, seen: &mut HashSet<u64>, addr: u64, old_raw: Vec<u8>, new_raw: Vec<u8>, description: String) -> Result<(), String> {
    if !is_valid_ptr(addr) || old_raw.len() != new_raw.len() || old_raw.is_empty() || !seen.insert(addr) {
        return Err(format!("invalid/duplicate planned tactical edit @0x{addr:X}"));
    }
    plan.edits.push(TacticalMaxPlannedEdit { addr, old_raw, new_raw, description });
    Ok(())
}

pub(super) fn plan_first_team(
    fm: &FmProcess,
    club_addr: u64,
    senior_team_addr: u64,
    player_addrs: &[u64],
) -> Result<TacticalMaxPlan, String> {
    if fm.build != crate::game_version::GameBuild::Fm27Steam {
        return Err("Tactical Knowledge MAX is certified only for FM27 Steam".into());
    }
    if !is_valid_ptr(club_addr) || !is_valid_ptr(senior_team_addr) {
        return Err("selected club/SeniorTeam pointer is invalid; reload club".into());
    }

    let mut plan = TacticalMaxPlan {
        club_addr,
        senior_team_addr,
        players_examined: player_addrs.len(),
        ..Default::default()
    };
    let mut seen = HashSet::new();

    for &player in player_addrs {
        if !is_valid_ptr(player) {
            return Err("cached player pointer is invalid; reload save".into());
        }
        let team = u64_at(fm, player + PLAYER_TEAM_PTR)?;
        if team != senior_team_addr {
            continue;
        }
        plan.players_matched += 1;
        let block = u64_at(fm, player + PLAYER_TACTICAL_PTR)?;
        if !is_valid_ptr(block) {
            return Err(format!("first-team player 0x{player:X} has no valid tactical block"));
        }

        for category in 0..CATEGORIES {
            let (data, count) = vec_info(fm, block + category as u64 * CATEGORY_STRIDE, 4, 4096)?;
            for i in 0..count {
                let addr = data + i as u64 * 4;
                let old = fm.read_bytes(addr, 4)?;
                let raw = u32::from_le_bytes(old.as_slice().try_into().unwrap());
                let maxed = (raw & !KNOWLEDGE_MASK) | MAX_KNOWLEDGE;
                plan.instruction_entries += 1;
                if raw == maxed {
                    plan.already_maxed += 1;
                } else {
                    add_edit(&mut plan, &mut seen, addr, old, maxed.to_le_bytes().to_vec(),
                        format!("Tactical Knowledge — instruction group {} → 100%", category + 1))?;
                }
            }
        }

        let (data, count) = vec_info(fm, block + FORMATION_VECTOR, FORMATION_ROW, 1024)?;
        for i in 0..count {
            let addr = data + i as u64 * FORMATION_ROW as u64 + FORMATION_VALUE;
            let old = fm.read_bytes(addr, 2)?;
            let raw = u16::from_le_bytes(old.as_slice().try_into().unwrap());
            plan.formation_rows += 1;
            if raw == MAX_KNOWLEDGE as u16 {
                plan.already_maxed += 1;
            } else {
                add_edit(&mut plan, &mut seen, addr, old, (MAX_KNOWLEDGE as u16).to_le_bytes().to_vec(),
                    "Tactical Knowledge — formation/role → 100%".into())?;
            }
        }

        let dirty_addr = block + DIRTY_FLAG;
        let dirty = fm.read_bytes(dirty_addr, 1)?;
        if dirty[0] != 1 {
            add_edit(&mut plan, &mut seen, dirty_addr, dirty, vec![1],
                "Tactical Knowledge — refresh marker".into())?;
        }
    }

    if plan.players_matched == 0 {
        return Err("no cached player currently belongs to the selected club First Team; reload club/save".into());
    }
    Ok(plan)
}
''', encoding="utf-8")

# Worker wiring.
worker_path = "src/bridge/worker.rs"
worker = rd(worker_path)
if "use super::tactical_max_plan;" not in worker:
    worker = one(worker, "use super::tactical_inspector;\n", "use super::tactical_inspector;\nuse super::tactical_max_plan;\n", "worker import")
if "BridgeCmd::PlanSelectedClubTacticalMax" not in worker:
    marker = "            BridgeCmd::InspectTacticalKnowledge { club_addr, senior_team_addr } => {\n"
    arm = '''            BridgeCmd::PlanSelectedClubTacticalMax { club_addr, senior_team_addr, player_addrs } => {
                let result = match &fm {
                    Some(f) => tactical_max_plan::plan_first_team(f, club_addr, senior_team_addr, &player_addrs),
                    None => Err("Cannot plan Tactical Knowledge MAX: no process attached".to_owned()),
                };
                match result {
                    Ok(plan) => { let _ = tx.send(BridgeResult::TacticalMaxPlanReady { club_addr, plan }); }
                    Err(error) => { let _ = tx.send(BridgeResult::Error(format!("Tactical Knowledge MAX: {error}"))); }
                }
            }

'''
    worker = one(worker, marker, arm + marker, "worker planner arm")
wr(worker_path, worker)

# Club UI: make Tactical Knowledge accept normal FieldEdits and expose the MAX.
club_path = "src/ui/club_panel.rs"
club = rd(club_path)
club = one(club,
    "ClubTab::TacticalUnderstanding => show_tactical_understanding(ui, club),",
    "ClubTab::TacticalUnderstanding => show_tactical_understanding(ui, club, &mut edits),",
    "tactical tab call")
club = one(club,
    "fn show_tactical_understanding(ui: &mut egui::Ui, club: &ClubView) {",
    "fn show_tactical_understanding(ui: &mut egui::Ui, club: &ClubView, edits: &mut Vec<FieldEdit>) {",
    "tactical function signature")

old = '''                ui.add_enabled(false, egui::Button::new("MAX CURRENT SQUAD • 100"));
                ui.add_enabled(false, egui::Button::new("MAX ALL SQUADS • 100"));
'''
new = r'''                let club_players: Vec<u64> = navigation::entity_cache(ui)
                    .map(|cache| cache.players.iter()
                        .filter(|p| p.club_id == Some(club.uid))
                        .map(|p| p.addr)
                        .collect())
                    .unwrap_or_default();
                let can_plan = crate::ui::navigation::editing_enabled(ui) && senior_team_ok && !club_players.is_empty();
                if ui.add_enabled(can_plan, egui::Button::new("⚡ MAX FIRST TEAM • 100"))
                    .on_hover_text("Only the selected club. Planner verifies each player's live team pointer equals this club's SeniorTeam before creating normal undoable edits.")
                    .clicked()
                {
                    if let Some(team) = club.senior_team_addr {
                        ui.ctx().data_mut(|d| d.insert_temp(
                            egui::Id::new("element_plan_tactical_max_request"),
                            (club.addr, team, club_players.clone()),
                        ));
                    }
                }
                ui.add_enabled(false, egui::Button::new("MAX B TEAM • 100"))
                    .on_disabled_hover_text("B-team discriminator is not certified yet.");
                ui.add_enabled(false, egui::Button::new("MAX U19 • 100"))
                    .on_disabled_hover_text("U19 discriminator is not certified yet.");
'''
club = one(club, old, new, "MAX buttons")

# Consume a prepared plan into the existing edit/Undo pipeline.
consume_marker = "    ui.add_space(3.0);\n\n    // Element v6.2.5"
consume = r'''    let plan_id = egui::Id::new(("element_tactical_max_plan", club.addr));
    if let Some(plan) = ui.ctx().data_mut(|d| {
        let p = d.get_temp::<crate::bridge::TacticalMaxPlan>(plan_id);
        d.remove::<crate::bridge::TacticalMaxPlan>(plan_id);
        p
    }) {
        for p in plan.edits {
            edits.push(FieldEdit {
                addr: p.addr,
                old_raw: p.old_raw,
                new_raw: p.new_raw,
                description: p.description,
            });
        }
    }

    ui.add_space(3.0);

    // Element v6.2.5'''
club = one(club, consume_marker, consume, "plan consumer")
club = club.replace(
    "TEST: Capture here → in FMRTE use Max Tactical Familiarity for Barcelona First Team → return to Element, click Refresh live data → Compare. MAX buttons unlock only after the seven semantic fields are certified and read-back safe.",
    "MAX FIRST TEAM uses the live per-player FM27 tactical block and the normal Element compare-before-write + Undo pipeline. It only accepts players whose live team pointer equals the selected club SeniorTeam. B Team/U19 stay locked until team-type mapping is certified.")
wr(club_path, club)

# App: request planner and publish prepared edits back to the selected club UI.
app_path = "src/app.rs"
app = rd(app_path)
if "BridgeResult::TacticalMaxPlanReady" not in app:
    marker = "                BridgeResult::TacticalInspectorDone { club_addr, report } => {\n"
    arm = r'''                BridgeResult::TacticalMaxPlanReady { club_addr, plan } => {
                    let summary = format!(
                        "Tactical MAX prepared: {} First Team players, {} edits ({} instruction entries, {} formation/role rows)",
                        plan.players_matched, plan.edits.len(), plan.instruction_entries, plan.formation_rows,
                    );
                    ctx.data_mut(|d| d.insert_temp(
                        egui::Id::new(("element_tactical_max_plan", club_addr)),
                        plan,
                    ));
                    self.set_status(summary);
                }
'''
    app = one(app, marker, arm + marker, "app plan result")
if "element_plan_tactical_max_request" not in app:
    marker = "        // Element v2.8 read-only Tactical Knowledge inspector request.\n"
    block = r'''        let tactical_max_request = ctx.data_mut(|d| {
            let id = egui::Id::new("element_plan_tactical_max_request");
            let request = d.get_temp::<(u64, u64, Vec<u64>)>(id);
            d.remove::<(u64, u64, Vec<u64>)>(id);
            request
        });
        if let Some((club_addr, senior_team_addr, player_addrs)) = tactical_max_request {
            if self.conn.is_writable() {
                self.bridge.send(BridgeCmd::PlanSelectedClubTacticalMax {
                    club_addr, senior_team_addr, player_addrs,
                });
                self.set_status("Preparing selected-club First Team Tactical Knowledge MAX…".into());
            } else {
                self.set_status("Tactical Knowledge MAX requires a live FM27 attachment".into());
            }
        }

'''
    app = one(app, marker, block + marker, "app plan request")
wr(app_path, app)

print("Element v6.2.6 selected-club Tactical Knowledge MAX planner applied.")
