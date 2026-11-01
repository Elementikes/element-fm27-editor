from pathlib import Path

root = Path.cwd()


def rd(path):
    p = root / path
    if not p.exists():
        raise SystemExit(f"v7.0 missing {path}")
    return p.read_text(encoding="utf-8")


def wr(path, text):
    (root / path).write_text(text, encoding="utf-8")


def one(text, old, new, label):
    if old not in text:
        raise SystemExit(f"v7.0 marker missing: {label}")
    return text.replace(old, new, 1)


# -----------------------------------------------------------------------------
# Element identity + theme on current upstream
# -----------------------------------------------------------------------------
p = "src/main.rs"
t = rd(p)
t = t.replace('Some(b) => format!("FM Editor [{b}]"),', 'Some(b) => format!("Element FM27 Editor [{b}]"),')
t = t.replace('None => "FM Editor".to_string(),', 'None => "Element FM27 Editor".to_string(),')
t = t.replace('        "FM Editor",\n', '        "Element FM27 Editor",\n', 1)
wr(p, t)

p = "src/app.rs"
t = rd(p)
t = t.replace('|| "FM Editor".to_string(),', '|| "Element FM27 Editor".to_string(),')
t = t.replace('|v| format!("{} Editor", v.display_name()),', '|v| format!("Element {} Editor", v.display_name()),')
# Keep tests coherent with branding.
t = t.replace('"FM Editor [preview]"', '"Element FM27 Editor [preview]"')
t = t.replace('"FM Editor"', '"Element FM27 Editor"')
wr(p, t)

p = "src/settings.rs"
t = rd(p)
t = t.replace('%APPDATA%/fm-editor/settings.json', '%APPDATA%/element-fm27-editor/settings.json')
t = t.replace('join("fm-editor").join("settings.json")', 'join("element-fm27-editor").join("settings.json")')
if 'fn element_visuals()' not in t:
    t = t.replace('            Theme::Dark     => egui::Visuals::dark(),', '            Theme::Dark     => element_visuals(),', 1)
    marker = '/// Navy/steel-blue dark theme.\nfn dark_blue_visuals() -> egui::Visuals {'
    if marker in t:
        theme = '''fn element_visuals() -> egui::Visuals {
    let mut v = egui::Visuals::dark();
    v.window_fill = egui::Color32::from_rgb(13, 16, 23);
    v.panel_fill = egui::Color32::from_rgb(17, 21, 30);
    v.faint_bg_color = egui::Color32::from_rgb(25, 30, 43);
    v.extreme_bg_color = egui::Color32::from_rgb(8, 10, 15);
    v.hyperlink_color = egui::Color32::from_rgb(116, 145, 255);
    v.selection.bg_fill = egui::Color32::from_rgb(75, 96, 210);
    v.widgets.inactive.bg_fill = egui::Color32::from_rgb(28, 34, 47);
    v.widgets.hovered.bg_fill = egui::Color32::from_rgb(40, 49, 68);
    v.widgets.active.bg_fill = egui::Color32::from_rgb(52, 65, 96);
    v
}

'''
        t = t.replace(marker, theme + marker, 1)
wr(p, t)


# -----------------------------------------------------------------------------
# Bridge protocol: Tactical MAX + Team Cohesion differential
# -----------------------------------------------------------------------------
p = "src/bridge/cmd.rs"
t = rd(p)
if "pub struct TacticalMaxPlannedEdit" not in t:
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

#[derive(Clone, Debug, Default)]
pub struct TeamCohesionDeltaReport {
    pub club_addr: u64,
    pub senior_team_addr: u64,
    pub changed_bytes: usize,
    pub rows: Vec<String>,
}

'''
    t = one(t, marker, defs + marker, "bridge view structs")
if "PlanSelectedClubTacticalMax" not in t:
    t = one(t, "    Ping,\n",
        "    PlanSelectedClubTacticalMax { club_addr: u64, senior_team_addr: u64, player_addrs: Vec<u64> },\n"
        "    CaptureTeamCohesionBaseline { club_addr: u64, senior_team_addr: u64 },\n"
        "    CompareTeamCohesionBaseline { club_addr: u64, senior_team_addr: u64 },\n"
        "    Ping,\n", "bridge commands")
if "TacticalMaxPlanReady" not in t:
    marker = "    /// Current date for this attachment, refreshed by status polls and reloads.\n"
    results = '''    TacticalMaxPlanReady { club_addr: u64, plan: TacticalMaxPlan },
    TeamCohesionBaselineReady { club_addr: u64, senior_team_addr: u64, bytes: usize },
    TeamCohesionDeltaReady { club_addr: u64, report: TeamCohesionDeltaReport },
'''
    t = one(t, marker, results + marker, "bridge results")
wr(p, t)

p = "src/bridge/mod.rs"
t = rd(p)
if "mod tactical_max_plan;" not in t:
    t = one(t, "mod worker;\n", "mod worker;\nmod tactical_max_plan;\nmod team_cohesion_delta;\n", "bridge modules")
if "TacticalMaxPlan" not in t:
    t = t.replace(
        "    BridgeCmd, BridgeResult, ClubView, EntityCounts, ProcessBridge, StaffView,\n",
        "    BridgeCmd, BridgeResult, ClubView, EntityCounts, ProcessBridge, StaffView,\n"
        "    TacticalMaxPlan, TacticalMaxPlannedEdit, TeamCohesionDeltaReport,\n",
        1,
    )
wr(p, t)

# Tactical planner: verified FM27 Steam mapping from Element v6.
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
        return Err("selected Club/SeniorTeam pointer is invalid; reload club".into());
    }
    let mut plan = TacticalMaxPlan { club_addr, senior_team_addr, players_examined: player_addrs.len(), ..Default::default() };
    let mut seen = HashSet::new();
    for &player in player_addrs {
        if !is_valid_ptr(player) { continue; }
        let team = u64_at(fm, player + PLAYER_TEAM_PTR)?;
        if team != senior_team_addr { continue; }
        plan.players_matched += 1;
        let block = u64_at(fm, player + PLAYER_TACTICAL_PTR)?;
        if !is_valid_ptr(block) { return Err(format!("First Team player 0x{player:X} has no valid tactical block")); }
        for category in 0..CATEGORIES {
            let (data, count) = vec_info(fm, block + category as u64 * CATEGORY_STRIDE, 4, 4096)?;
            for i in 0..count {
                let addr = data + i as u64 * 4;
                let old = fm.read_bytes(addr, 4)?;
                let raw = u32::from_le_bytes(old.as_slice().try_into().unwrap());
                let maxed = (raw & !KNOWLEDGE_MASK) | MAX_KNOWLEDGE;
                plan.instruction_entries += 1;
                if raw == maxed { plan.already_maxed += 1; }
                else { add_edit(&mut plan, &mut seen, addr, old, maxed.to_le_bytes().to_vec(), format!("Tactical familiarity group {} → 100%", category + 1))?; }
            }
        }
        let (data, count) = vec_info(fm, block + FORMATION_VECTOR, FORMATION_ROW, 1024)?;
        for i in 0..count {
            let addr = data + i as u64 * FORMATION_ROW as u64 + FORMATION_VALUE;
            let old = fm.read_bytes(addr, 2)?;
            let raw = u16::from_le_bytes(old.as_slice().try_into().unwrap());
            plan.formation_rows += 1;
            if raw == MAX_KNOWLEDGE as u16 { plan.already_maxed += 1; }
            else { add_edit(&mut plan, &mut seen, addr, old, (MAX_KNOWLEDGE as u16).to_le_bytes().to_vec(), "Tactical formation/role familiarity → 100%".into())?; }
        }
        let dirty_addr = block + DIRTY_FLAG;
        let dirty = fm.read_bytes(dirty_addr, 1)?;
        if dirty[0] != 1 { add_edit(&mut plan, &mut seen, dirty_addr, dirty, vec![1], "Tactical familiarity refresh marker".into())?; }
    }
    if plan.players_matched == 0 { return Err("no cached player currently belongs to this SeniorTeam; reload save/club".into()); }
    Ok(plan)
}
''', encoding="utf-8")

(root / "src/bridge/team_cohesion_delta.rs").write_text(r'''use crate::game_version::GameBuild;
use crate::player::is_valid_ptr;
use crate::process::FmProcess;
use super::cmd::TeamCohesionDeltaReport;

const REGION_SIZE: usize = 0x1000;
const KNOWN_REPUTATION_U16: usize = 0xA8;

#[derive(Clone, Debug)]
pub(super) struct TeamCohesionSnapshot {
    pub club_addr: u64,
    pub senior_team_addr: u64,
    pub bytes: Vec<u8>,
}

pub(super) fn capture(fm: &FmProcess, club_addr: u64, senior_team_addr: u64) -> Result<TeamCohesionSnapshot, String> {
    if fm.build != GameBuild::Fm27Steam { return Err("Team Cohesion certifier is enabled only for FM27 Steam".into()); }
    if !is_valid_ptr(club_addr) || !is_valid_ptr(senior_team_addr) { return Err("invalid Club/SeniorTeam pointer".into()); }
    let bytes = fm.read_bytes(senior_team_addr, REGION_SIZE)?;
    if bytes.len() != REGION_SIZE { return Err("short SeniorTeam capture".into()); }
    Ok(TeamCohesionSnapshot { club_addr, senior_team_addr, bytes })
}

fn u16_at(b: &[u8], off: usize) -> u16 { u16::from_le_bytes([b[off], b[off+1]]) }
fn u32_at(b: &[u8], off: usize) -> u32 { u32::from_le_bytes([b[off],b[off+1],b[off+2],b[off+3]]) }

pub(super) fn compare(fm: &FmProcess, baseline: &TeamCohesionSnapshot, club_addr: u64, senior_team_addr: u64) -> Result<TeamCohesionDeltaReport, String> {
    if baseline.club_addr != club_addr || baseline.senior_team_addr != senior_team_addr { return Err("baseline belongs to a different club/team; capture again".into()); }
    let after = fm.read_bytes(senior_team_addr, REGION_SIZE)?;
    if after.len() != REGION_SIZE { return Err("short SeniorTeam compare read".into()); }
    let changed_bytes = baseline.bytes.iter().zip(after.iter()).filter(|(a,b)| a != b).count();
    let mut candidates: Vec<(i64, usize, String)> = Vec::new();
    for off in (0..=REGION_SIZE-2).step_by(2) {
        if off == KNOWN_REPUTATION_U16 || baseline.bytes[off..off+2] == after[off..off+2] { continue; }
        let a=u16_at(&baseline.bytes,off); let b=u16_at(&after,off);
        if a>10_000 || b>10_000 || a==b { continue; }
        let delta=b as i64-a as i64; let mut score=delta.abs();
        if b==10_000 {score+=50_000;} if b==100 {score+=30_000;} if b>a {score+=5_000;}
        candidates.push((score,off,format!("Δ16 +0x{off:03X} | {a} → {b} | {delta:+} | score={score}")));
    }
    for off in 0..REGION_SIZE {
        let a=baseline.bytes[off]; let b=after[off]; if a==b || a>100 || b>100 {continue;}
        let delta=b as i64-a as i64; let mut score=delta.abs()*100; if b==100 {score+=25_000;} if b>a {score+=4_000;}
        candidates.push((score,off,format!("Δ8  +0x{off:03X} | {a} → {b} | {delta:+} | score={score}")));
    }
    for off in (0..=REGION_SIZE-4).step_by(4) {
        if baseline.bytes[off..off+4] == after[off..off+4] {continue;}
        let a=u32_at(&baseline.bytes,off); let b=u32_at(&after,off); if a==b || a>1_000_000 || b>1_000_000 {continue;}
        let delta=b as i64-a as i64; let mut score=delta.abs().min(20_000); if b==10_000 {score+=40_000;} if b==100 {score+=20_000;}
        candidates.push((score,off,format!("Δ32 +0x{off:03X} | {a} → {b} | {delta:+} | score={score}")));
    }
    candidates.sort_by(|a,b| b.0.cmp(&a.0).then_with(||a.1.cmp(&b.1)));
    let mut rows:Vec<String>=candidates.into_iter().take(48).map(|x|x.2).collect();
    let mut i=0usize;
    while i<REGION_SIZE {
        if baseline.bytes[i]==after[i] {i+=1; continue;}
        let start=i; while i<REGION_SIZE && baseline.bytes[i]!=after[i] {i+=1;}
        rows.push(format!("ΔRAW +0x{start:03X}..+0x{:03X} | {} byte(s)",i-1,i-start));
    }
    if rows.is_empty(){rows.push("NO CHANGES in SeniorTeam +0x000..+0xFFF".into());}
    Ok(TeamCohesionDeltaReport{club_addr,senior_team_addr,changed_bytes,rows})
}
''', encoding="utf-8")

# -----------------------------------------------------------------------------
# Worker wiring
# -----------------------------------------------------------------------------
p = "src/bridge/worker.rs"
t = rd(p)
if "use super::tactical_max_plan;" not in t:
    t = one(t, "use super::entity_load;\n", "use super::entity_load;\nuse super::tactical_max_plan;\nuse super::team_cohesion_delta;\n", "worker imports")
if "team_cohesion_baseline" not in t:
    marker = "    let mut last_counts: Option<(usize, usize, usize)> = None;\n"
    t = one(t, marker, marker + "    let mut team_cohesion_baseline: Option<team_cohesion_delta::TeamCohesionSnapshot> = None;\n", "worker state")
if "BridgeCmd::PlanSelectedClubTacticalMax" not in t:
    marker = "            BridgeCmd::Ping => {\n"
    arms = '''            BridgeCmd::PlanSelectedClubTacticalMax { club_addr, senior_team_addr, player_addrs } => {
                let result = match &fm {
                    Some(f) => tactical_max_plan::plan_first_team(f, club_addr, senior_team_addr, &player_addrs),
                    None => Err("Cannot plan Tactical MAX: no process attached".into()),
                };
                match result {
                    Ok(plan) => { let _ = tx.send(BridgeResult::TacticalMaxPlanReady { club_addr, plan }); }
                    Err(error) => { let _ = tx.send(BridgeResult::Error(format!("Tactical MAX: {error}"))); }
                }
            }
            BridgeCmd::CaptureTeamCohesionBaseline { club_addr, senior_team_addr } => {
                let result = match &fm { Some(f) => team_cohesion_delta::capture(f, club_addr, senior_team_addr), None => Err("no process attached".into()) };
                match result {
                    Ok(snapshot) => { let bytes=snapshot.bytes.len(); team_cohesion_baseline=Some(snapshot); let _=tx.send(BridgeResult::TeamCohesionBaselineReady{club_addr,senior_team_addr,bytes}); }
                    Err(error) => { let _=tx.send(BridgeResult::Error(format!("Team Cohesion baseline: {error}"))); }
                }
            }
            BridgeCmd::CompareTeamCohesionBaseline { club_addr, senior_team_addr } => {
                let result = match (&fm,&team_cohesion_baseline) {
                    (Some(f),Some(s)) => team_cohesion_delta::compare(f,s,club_addr,senior_team_addr),
                    (None,_) => Err("no process attached".into()),
                    (_,None) => Err("no Team Cohesion baseline captured".into()),
                };
                match result {
                    Ok(report) => { let _=tx.send(BridgeResult::TeamCohesionDeltaReady{club_addr,report}); }
                    Err(error) => { let _=tx.send(BridgeResult::Error(format!("Team Cohesion compare: {error}"))); }
                }
            }

'''
    t = one(t, marker, arms + marker, "worker command arms")
wr(p, t)

# -----------------------------------------------------------------------------
# Club Tactical tab
# -----------------------------------------------------------------------------
p = "src/ui/club_panel.rs"
t = rd(p)
if "    Tactical,\n" not in t:
    t = one(t, "    ContractPolicy,\n}", "    ContractPolicy,\n    Tactical,\n}", "club tab enum")
    t = one(t,
        '        ui.selectable_value(tab, ClubTab::Stadium, "Stadium (read-only)");\n',
        '        ui.selectable_value(tab, ClubTab::Stadium, "Stadium (read-only)");\n        ui.selectable_value(tab, ClubTab::Tactical, "Tactical");\n',
        "club tactical tab button")
    # Add entity cache to show() for selected-club player membership.
    t = one(t,
        "    writable: bool,\n) -> (Vec<FieldEdit>, Option<crate::ui::club_policy::Action>) {",
        "    writable: bool,\n    entity_cache: Option<&crate::cache::EntityCache>,\n) -> (Vec<FieldEdit>, Option<crate::ui::club_policy::Action>) {",
        "club show cache arg")
    t = one(t,
        "        ClubTab::Stadium => show_stadium(schemas, ui, club),\n",
        "        ClubTab::Stadium => show_stadium(schemas, ui, club),\n        ClubTab::Tactical => show_tactical(ui, club, &mut edits, writable, entity_cache),\n",
        "club tactical match arm")

    marker = "fn show_overview(\n"
    tactical_fn = r'''fn show_tactical(
    ui: &mut egui::Ui,
    club: &mut ClubView,
    edits: &mut Vec<FieldEdit>,
    writable: bool,
    entity_cache: Option<&crate::cache::EntityCache>,
) {
    ui.horizontal_wrapped(|ui| {
        ui.heading("Tactical Knowledge");
        ui.label(egui::RichText::new("ELEMENT v7 • FM27 NATIVE-MAPPED").strong().color(egui::Color32::from_rgb(116,145,255)));
    });
    ui.label(egui::RichText::new("Verified First Team tactical familiarity writer + IL2CPP-assisted Team Cohesion certifier. Blind cohesion writes remain blocked.").weak());
    ui.add_space(8.0);

    egui::Frame::group(ui.style()).show(ui, |ui| {
        ui.strong("FM27 native semantics discovered from IL2CPP metadata");
        ui.label("TeamMaximiseTacticalUnderstanding • ActionID 0x55543568");
        ui.label("TeamImproveTeamCohesion • ActionID 0x66335264");
    });
    ui.add_space(8.0);

    let player_addrs: Vec<u64> = entity_cache
        .map(|cache| cache.players.iter().filter(|p| p.club_id == Some(club.uid)).map(|p| p.addr).collect())
        .unwrap_or_default();
    let team = club.senior_team_addr;
    let can_plan = writable && team.is_some() && !player_addrs.is_empty();
    if ui.add_enabled(can_plan, egui::Button::new("⚡ MAX TACTICAL FAMILIARITY • FIRST TEAM"))
        .on_hover_text("Uses the verified FM27 per-player tactical block. Every candidate is checked against this club's live SeniorTeam pointer and enters the normal guarded Change History / Undo pipeline.")
        .clicked()
    {
        ui.ctx().data_mut(|d| d.insert_temp(
            egui::Id::new("element_v7_plan_tactical_max_request"),
            (club.addr, team.unwrap(), player_addrs.clone()),
        ));
    }

    let plan_id = egui::Id::new(("element_v7_tactical_max_plan", club.addr));
    if let Some(plan) = ui.ctx().data_mut(|d| {
        let p=d.get_temp::<crate::bridge::TacticalMaxPlan>(plan_id);
        d.remove::<crate::bridge::TacticalMaxPlan>(plan_id); p
    }) {
        ui.colored_label(egui::Color32::from_rgb(88,214,141), format!(
            "Prepared {} guarded edits for {} First Team players ({} instruction entries, {} formation/role rows).",
            plan.edits.len(), plan.players_matched, plan.instruction_entries, plan.formation_rows));
        for e in plan.edits {
            edits.push(FieldEdit { addr:e.addr, old_raw:e.old_raw, new_raw:e.new_raw, description:e.description });
        }
    }

    ui.add_space(12.0);
    ui.separator();
    ui.strong("Team Cohesion • differential certifier");
    ui.label("Capture → run only Improve Team Cohesion in FMRTE → Compare. Reputation +0xA8 is excluded from candidate ranking.");
    if let Some(team) = team {
        ui.horizontal_wrapped(|ui| {
            if ui.add_enabled(writable, egui::Button::new("1 • CAPTURE BASELINE")).clicked() {
                ui.ctx().data_mut(|d| d.insert_temp(egui::Id::new("element_v7_capture_cohesion_request"),(club.addr,team)));
            }
            if ui.add_enabled(writable, egui::Button::new("2 • COMPARE AFTER FMRTE")).clicked() {
                ui.ctx().data_mut(|d| d.insert_temp(egui::Id::new("element_v7_compare_cohesion_request"),(club.addr,team)));
            }
        });
    }
    if let Some((team_addr,bytes)) = ui.ctx().data(|d| d.get_temp::<(u64,usize)>(egui::Id::new(("element_v7_cohesion_baseline_ready",club.addr)))) {
        ui.label(format!("Baseline ready • SeniorTeam 0x{team_addr:X} • {bytes} bytes"));
    }
    if let Some(report) = ui.ctx().data(|d| d.get_temp::<crate::bridge::TeamCohesionDeltaReport>(egui::Id::new(("element_v7_cohesion_report",club.addr)))) {
        ui.colored_label(egui::Color32::from_rgb(255,193,92), format!("{} byte(s) changed", report.changed_bytes));
        egui::ScrollArea::vertical().max_height(280.0).show(ui,|ui|{
            for row in &report.rows { ui.monospace(row); }
        });
    }
}

'''
    t = one(t, marker, tactical_fn + marker, "club tactical function")
wr(p, t)

# -----------------------------------------------------------------------------
# App routing: current upstream Change History remains source of truth.
# -----------------------------------------------------------------------------
p = "src/app.rs"
t = rd(p)
# process_results needs context to publish planner/certifier results.
if "fn process_results(&mut self, ctx: &egui::Context)" not in t:
    t = one(t, "    fn process_results(&mut self) {", "    fn process_results(&mut self, ctx: &egui::Context) {", "process_results signature")
    t = one(t, "        self.process_results();", "        self.process_results(ctx);", "process_results call")
if "BridgeResult::TacticalMaxPlanReady" not in t:
    marker = "                BridgeResult::PingOk(game_date) => self.game_date = game_date,\n"
    arms = r'''                BridgeResult::TacticalMaxPlanReady { club_addr, plan } => {
                    let count=plan.edits.len(); let matched=plan.players_matched;
                    ctx.data_mut(|d| d.insert_temp(egui::Id::new(("element_v7_tactical_max_plan",club_addr)),plan));
                    self.set_status(format!("Tactical MAX prepared • {matched} First Team players • {count} guarded edits"));
                }
                BridgeResult::TeamCohesionBaselineReady { club_addr, senior_team_addr, bytes } => {
                    ctx.data_mut(|d| d.insert_temp(egui::Id::new(("element_v7_cohesion_baseline_ready",club_addr)),(senior_team_addr,bytes)));
                    self.set_status(format!("Team Cohesion baseline captured • {bytes} bytes"));
                }
                BridgeResult::TeamCohesionDeltaReady { club_addr, report } => {
                    let changed=report.changed_bytes;
                    ctx.data_mut(|d| d.insert_temp(egui::Id::new(("element_v7_cohesion_report",club_addr)),report));
                    self.set_status(format!("Team Cohesion differential complete • {changed} changed byte(s)"));
                }
'''
    t = one(t, marker, arms + marker, "app result arms")
# Supply entity cache to Club panel.
old = '''                                    let (e,action) = club_panel::show(schemas,ui,c,&mut self.club_tab,&mut self.policy_ui,
                                        self.attached_build.is_some_and(|b|b.version()==crate::game_version::GameVersion::Fm27),
                                        self.conn.is_writable() && !self.change_history.is_pending() && edits.is_empty());'''
new = '''                                    let (e,action) = club_panel::show(schemas,ui,c,&mut self.club_tab,&mut self.policy_ui,
                                        self.attached_build.is_some_and(|b|b.version()==crate::game_version::GameVersion::Fm27),
                                        self.conn.is_writable() && !self.change_history.is_pending() && edits.is_empty(),
                                        cache_arc.as_deref());'''
if old not in t:
    raise SystemExit("v7.0 marker missing: club_panel app call")
t = t.replace(old,new,1)
# Consume UI requests in post-UI action processing.
if "element_v7_plan_tactical_max_request" not in t:
    marker = "        // A write becomes undoable only after the worker confirms success.\n"
    block = r'''        if let Some((club_addr,senior_team_addr,player_addrs)) = ctx.data_mut(|d| {
            let id=egui::Id::new("element_v7_plan_tactical_max_request"); let v=d.get_temp::<(u64,u64,Vec<u64>)>(id); d.remove::<(u64,u64,Vec<u64>)>(id); v
        }) {
            if self.conn.is_writable() { self.bridge.send(BridgeCmd::PlanSelectedClubTacticalMax{club_addr,senior_team_addr,player_addrs}); }
        }
        if let Some((club_addr,senior_team_addr)) = ctx.data_mut(|d| {
            let id=egui::Id::new("element_v7_capture_cohesion_request"); let v=d.get_temp::<(u64,u64)>(id); d.remove::<(u64,u64)>(id); v
        }) {
            if self.conn.is_writable() { self.bridge.send(BridgeCmd::CaptureTeamCohesionBaseline{club_addr,senior_team_addr}); }
        }
        if let Some((club_addr,senior_team_addr)) = ctx.data_mut(|d| {
            let id=egui::Id::new("element_v7_compare_cohesion_request"); let v=d.get_temp::<(u64,u64)>(id); d.remove::<(u64,u64)>(id); v
        }) {
            if self.conn.is_writable() { self.bridge.send(BridgeCmd::CompareTeamCohesionBaseline{club_addr,senior_team_addr}); }
        }

'''
    t = one(t, marker, block + marker, "post UI requests")
wr(p, t)

print("Element v7.0 Full Core patch applied on current upstream.")
