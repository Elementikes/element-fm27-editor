from pathlib import Path

root = Path.cwd()


def rd(path):
    p = root / path
    if not p.exists():
        raise SystemExit(f"v7.1 missing {path}")
    return p.read_text(encoding="utf-8")


def wr(path, text):
    (root / path).write_text(text, encoding="utf-8")


def one(text, old, new, label):
    if old not in text:
        raise SystemExit(f"v7.1 marker missing: {label}")
    return text.replace(old, new, 1)


# -----------------------------------------------------------------------------
# Bridge protocol
# -----------------------------------------------------------------------------
p = "src/bridge/cmd.rs"
t = rd(p)
if "pub struct SquadPowerPlan" not in t:
    marker = "#[derive(Clone, Debug, Default)]\npub struct TeamCohesionDeltaReport"
    idx = t.find(marker)
    if idx < 0:
        raise SystemExit("v7.1 marker missing: cohesion report struct")
    defs = '''#[derive(Clone, Debug)]
pub struct SquadPowerPlannedEdit {
    pub addr: u64,
    pub old_raw: Vec<u8>,
    pub new_raw: Vec<u8>,
    pub description: String,
}

#[derive(Clone, Debug, Default)]
pub struct SquadPowerPlan {
    pub club_addr: u64,
    pub players_examined: usize,
    pub players_matched: usize,
    pub morale_edits: usize,
    pub injuries_healed: usize,
    pub bans_lifted: usize,
    pub edits: Vec<SquadPowerPlannedEdit>,
}

'''
    t = t[:idx] + defs + t[idx:]
if "PlanClubSquadPower" not in t:
    t = one(
        t,
        "    PlanSelectedClubTacticalMax { club_addr: u64, senior_team_addr: u64, player_addrs: Vec<u64> },\n",
        "    PlanSelectedClubTacticalMax { club_addr: u64, senior_team_addr: u64, player_addrs: Vec<u64> },\n"
        "    PlanClubSquadPower { club_addr: u64, club_uid: u32, players: Vec<(u64, usize)>, max_morale: bool, heal_injuries: bool, lift_bans: bool },\n",
        "squad power command",
    )
if "SquadPowerPlanReady" not in t:
    t = one(
        t,
        "    TacticalMaxPlanReady { club_addr: u64, plan: TacticalMaxPlan },\n",
        "    TacticalMaxPlanReady { club_addr: u64, plan: TacticalMaxPlan },\n"
        "    SquadPowerPlanReady { club_addr: u64, plan: SquadPowerPlan },\n",
        "squad power result",
    )
wr(p, t)

p = "src/bridge/mod.rs"
t = rd(p)
if "mod squad_power_tools;" not in t:
    t = one(t, "mod team_cohesion_delta;\n", "mod team_cohesion_delta;\nmod squad_power_tools;\n", "squad module")
if "SquadPowerPlan" not in t:
    t = one(
        t,
        "    TacticalMaxPlan, TacticalMaxPlannedEdit, TeamCohesionDeltaReport,\n",
        "    TacticalMaxPlan, TacticalMaxPlannedEdit, TeamCohesionDeltaReport,\n"
        "    SquadPowerPlan, SquadPowerPlannedEdit,\n",
        "squad re-export",
    )
wr(p, t)

# -----------------------------------------------------------------------------
# Read-only planner: all mutations still flow through acknowledged Change History
# -----------------------------------------------------------------------------
(root / "src/bridge/squad_power_tools.rs").write_text(r'''use std::collections::HashSet;

use crate::fields::FieldLocation;
use crate::game_version::GameBuild;
use crate::player::{self, ListState};
use crate::process::FmProcess;

use super::cmd::{SquadPowerPlan, SquadPowerPlannedEdit};

fn push_edit(
    plan: &mut SquadPowerPlan,
    seen: &mut HashSet<(u64, usize)>,
    addr: u64,
    old_raw: Vec<u8>,
    new_raw: Vec<u8>,
    description: String,
) -> Result<(), String> {
    if old_raw.is_empty() || old_raw.len() != new_raw.len() {
        return Err(format!("invalid planned edit at 0x{addr:X}"));
    }
    if old_raw == new_raw {
        return Ok(());
    }
    if !seen.insert((addr, old_raw.len())) {
        return Err(format!("duplicate planned edit at 0x{addr:X}"));
    }
    plan.edits.push(SquadPowerPlannedEdit { addr, old_raw, new_raw, description });
    Ok(())
}

pub(super) fn plan(
    fm: &FmProcess,
    club_addr: u64,
    _club_uid: u32,
    players: &[(u64, usize)],
    max_morale: bool,
    heal_injuries: bool,
    lift_bans: bool,
) -> Result<SquadPowerPlan, String> {
    if fm.build != GameBuild::Fm27Steam {
        return Err("Squad Power Tools are certified only for FM27 Steam".into());
    }
    if !(max_morale || heal_injuries || lift_bans) {
        return Err("no Squad Power action selected".into());
    }

    let schemas = fm.schemas();
    let morale = schemas.field("p_morale");
    let list_layout = schemas.player_lists;
    let mut result = SquadPowerPlan {
        club_addr,
        players_examined: players.len(),
        ..Default::default()
    };
    let mut seen = HashSet::new();

    for &(addr, index) in players {
        let rec = match player::read_player_at(fm, addr, index) {
            Ok(rec) => rec,
            Err(_) => continue,
        };
        // Re-validate membership live. Cached membership is only discovery;
        // a stale transfer must never make a bulk action touch another club.
        if rec.club_addr != Some(club_addr) {
            continue;
        }
        result.players_matched += 1;

        if max_morale {
            if let Some(field) = morale {
                if let Some(FieldLocation::Direct { offset, .. }) = field.offset {
                    let off = offset as usize;
                    if let Some(&old) = rec.raw.get(off) {
                        let loc = field.offset.unwrap();
                        let displayed = loc.decode_u8(old);
                        if (1..=20).contains(&displayed) && displayed != 20 {
                            let new = loc.encode_u8(20);
                            let physical = addr + player::player_phys_offset(schemas, offset, rec.person_shift);
                            push_edit(
                                &mut result,
                                &mut seen,
                                physical,
                                vec![old],
                                vec![new],
                                format!("{} • Morale: {} → 20", rec.name.as_deref().unwrap_or("Player"), displayed),
                            )?;
                            result.morale_edits += 1;
                        }
                    }
                }
            }
        }

        if heal_injuries {
            if let (Some(today), ListState::Items(injuries)) = (rec.game_date, &rec.injuries) {
                for injury in injuries {
                    let elapsed = today.elapsed_since(injury.start);
                    if elapsed >= injury.full_days {
                        continue;
                    }
                    let old_raw = [injury.full_days.to_le_bytes(), injury.light_days.to_le_bytes()].concat();
                    let new_raw = [elapsed.to_le_bytes(), injury.light_days.min(elapsed).to_le_bytes()].concat();
                    push_edit(
                        &mut result,
                        &mut seen,
                        injury.days_addr,
                        old_raw,
                        new_raw,
                        format!("{} • Heal injury: {}", rec.name.as_deref().unwrap_or("Player"), injury.name),
                    )?;
                    result.injuries_healed += 1;
                }
            }
        }

        if lift_bans {
            if let (Some(today), Some(layout), ListState::Items(absences)) = (rec.game_date, list_layout, &rec.absences) {
                for absence in absences {
                    if absence.kind != layout.absence_ban || absence.days == u16::MAX {
                        continue;
                    }
                    let elapsed = today.elapsed_since(absence.start);
                    if elapsed >= absence.days {
                        continue;
                    }
                    push_edit(
                        &mut result,
                        &mut seen,
                        absence.days_addr,
                        absence.days.to_le_bytes().to_vec(),
                        elapsed.to_le_bytes().to_vec(),
                        format!("{} • Lift date-based ban", rec.name.as_deref().unwrap_or("Player")),
                    )?;
                    result.bans_lifted += 1;
                }
            }
        }
    }

    if result.players_matched == 0 {
        return Err("no cached player still belongs to the selected club; reload club/save".into());
    }
    Ok(result)
}
''', encoding="utf-8")

# -----------------------------------------------------------------------------
# Worker wiring
# -----------------------------------------------------------------------------
p = "src/bridge/worker.rs"
t = rd(p)
if "use super::squad_power_tools;" not in t:
    t = one(t, "use super::team_cohesion_delta;\n", "use super::team_cohesion_delta;\nuse super::squad_power_tools;\n", "worker import")
if "BridgeCmd::PlanClubSquadPower" not in t:
    marker = "            BridgeCmd::PlanSelectedClubTacticalMax { club_addr, senior_team_addr, player_addrs } => {\n"
    idx = t.find(marker)
    if idx < 0:
        raise SystemExit("v7.1 marker missing: Tactical worker arm")
    # Insert the power arm immediately before tactical arm.
    arm = '''            BridgeCmd::PlanClubSquadPower { club_addr, club_uid, players, max_morale, heal_injuries, lift_bans } => {
                let result = match &fm {
                    Some(f) => squad_power_tools::plan(f, club_addr, club_uid, &players, max_morale, heal_injuries, lift_bans),
                    None => Err("Cannot plan Squad Power Tools: no process attached".into()),
                };
                match result {
                    Ok(plan) => { let _ = tx.send(BridgeResult::SquadPowerPlanReady { club_addr, plan }); }
                    Err(error) => { let _ = tx.send(BridgeResult::Error(format!("Squad Power Tools: {error}"))); }
                }
            }

'''
    t = t[:idx] + arm + t[idx:]
wr(p, t)

# -----------------------------------------------------------------------------
# Club Power Tools tab
# -----------------------------------------------------------------------------
p = "src/ui/club_panel.rs"
t = rd(p)
if "    PowerTools,\n" not in t:
    t = one(t, "    Tactical,\n}", "    Tactical,\n    PowerTools,\n}", "PowerTools enum")
    t = one(
        t,
        '        ui.selectable_value(tab, ClubTab::Tactical, "Tactical");\n',
        '        ui.selectable_value(tab, ClubTab::Tactical, "Tactical");\n        ui.selectable_value(tab, ClubTab::PowerTools, "Power Tools");\n',
        "PowerTools tab button",
    )
    t = one(
        t,
        "        ClubTab::Tactical => show_tactical(ui, club, &mut edits, writable, entity_cache),\n",
        "        ClubTab::Tactical => show_tactical(ui, club, &mut edits, writable, entity_cache),\n"
        "        ClubTab::PowerTools => show_power_tools(ui, club, &mut edits, writable, entity_cache),\n",
        "PowerTools match arm",
    )

if "fn show_power_tools(" not in t:
    marker = "fn show_tactical(\n"
    idx = t.find(marker)
    if idx < 0:
        raise SystemExit("v7.1 marker missing: show_tactical")
    fn = r'''fn show_power_tools(
    ui: &mut egui::Ui,
    club: &mut ClubView,
    edits: &mut Vec<FieldEdit>,
    writable: bool,
    entity_cache: Option<&crate::cache::EntityCache>,
) {
    ui.horizontal_wrapped(|ui| {
        ui.heading("Squad Power Tools");
        ui.label(egui::RichText::new("ELEMENT v7.1 • VERIFIED BULK").strong().color(egui::Color32::from_rgb(116,145,255)));
    });
    ui.label(egui::RichText::new("Every action re-reads each player and verifies the live club pointer before preparing guarded writes. All writes enter Change History / Undo.").weak());
    ui.add_space(8.0);

    let players: Vec<(u64, usize)> = entity_cache
        .map(|cache| cache.players.iter()
            .filter(|p| p.club_id == Some(club.uid))
            .map(|p| (p.addr, p.index))
            .collect())
        .unwrap_or_default();
    let ready = writable && !players.is_empty();

    egui::Frame::group(ui.style()).show(ui, |ui| {
        ui.strong(format!("{} cached club player(s)", players.len()));
        ui.add_space(4.0);
        ui.horizontal_wrapped(|ui| {
            if ui.add_enabled(ready, egui::Button::new("💚 MAX MORALE • FIRST TEAM/CLUB"))
                .on_hover_text("FM27 verified morale mapping. Only players whose live club pointer still matches this club are touched.")
                .clicked()
            {
                ui.ctx().data_mut(|d| d.insert_temp(
                    egui::Id::new("element_v7_squad_power_request"),
                    (club.addr, club.uid, players.clone(), true, false, false),
                ));
            }
            if ui.add_enabled(ready, egui::Button::new("🩹 HEAL ALL INJURIES"))
                .on_hover_text("Uses the same FM27 verified Heal semantics as the individual player action, applied to every live club member.")
                .clicked()
            {
                ui.ctx().data_mut(|d| d.insert_temp(
                    egui::Id::new("element_v7_squad_power_request"),
                    (club.addr, club.uid, players.clone(), false, true, false),
                ));
            }
            if ui.add_enabled(ready, egui::Button::new("🟨 LIFT DATE-BASED BANS"))
                .on_hover_text("Only verified date-based suspensions are shortened. Holidays and unknown absence kinds are untouched.")
                .clicked()
            {
                ui.ctx().data_mut(|d| d.insert_temp(
                    egui::Id::new("element_v7_squad_power_request"),
                    (club.addr, club.uid, players.clone(), false, false, true),
                ));
            }
        });
        ui.add_space(6.0);
        if ui.add_enabled(ready, egui::Button::new("⚡ RESTORE SQUAD • ALL VERIFIED"))
            .on_hover_text("Combines Max Morale + Heal Injuries + Lift date-based bans in one guarded plan. Tactical familiarity remains a separate Tactical action.")
            .clicked()
        {
            ui.ctx().data_mut(|d| d.insert_temp(
                egui::Id::new("element_v7_squad_power_request"),
                (club.addr, club.uid, players.clone(), true, true, true),
            ));
        }
    });

    let plan_id = egui::Id::new(("element_v7_squad_power_plan", club.addr));
    if let Some(plan) = ui.ctx().data_mut(|d| {
        let p=d.get_temp::<crate::bridge::SquadPowerPlan>(plan_id);
        d.remove::<crate::bridge::SquadPowerPlan>(plan_id); p
    }) {
        ui.add_space(8.0);
        ui.colored_label(egui::Color32::from_rgb(88,214,141), format!(
            "Prepared {} guarded edit(s) • {} live members • morale {} • injuries {} • bans {}",
            plan.edits.len(), plan.players_matched, plan.morale_edits, plan.injuries_healed, plan.bans_lifted));
        for e in plan.edits {
            edits.push(FieldEdit {
                addr:e.addr,
                old_raw:e.old_raw,
                new_raw:e.new_raw,
                description:e.description,
                presentation: None,
            });
        }
    }

    ui.add_space(12.0);
    ui.separator();
    ui.strong("Intentionally locked until independently mapped");
    ui.horizontal_wrapped(|ui| {
        ui.add_enabled(false, egui::Button::new("Resolve Concerns"))
            .on_disabled_hover_text("FM27 ActionID is known, but the player/team target record and undo semantics are not certified yet.");
        ui.add_enabled(false, egui::Button::new("Registration Anytime"))
            .on_disabled_hover_text("Native ActionID identified; target and rollback path still require certification.");
        ui.add_enabled(false, egui::Button::new("Max Condition / Sharpness"))
            .on_disabled_hover_text("Condition/sharpness fields are not verified on FM27 current upstream.");
    });
}

'''
    t = t[:idx] + fn + t[idx:]
wr(p, t)

# -----------------------------------------------------------------------------
# App result + request dispatch
# -----------------------------------------------------------------------------
p = "src/app.rs"
t = rd(p)
if "BridgeResult::SquadPowerPlanReady" not in t:
    t = one(
        t,
        "                BridgeResult::TacticalMaxPlanReady { club_addr, plan } => {\n",
        '''                BridgeResult::SquadPowerPlanReady { club_addr, plan } => {
                    let edits=plan.edits.len(); let players=plan.players_matched;
                    let morale=plan.morale_edits; let injuries=plan.injuries_healed; let bans=plan.bans_lifted;
                    ctx.data_mut(|d| d.insert_temp(egui::Id::new(("element_v7_squad_power_plan",club_addr)),plan));
                    self.set_status(format!("Squad Power plan • {players} live players • {edits} edits • morale {morale} • injuries {injuries} • bans {bans}"));
                }
                BridgeResult::TacticalMaxPlanReady { club_addr, plan } => {
''',
        "SquadPower result arm",
    )
if "element_v7_squad_power_request" not in t:
    marker = "        if let Some((club_addr,senior_team_addr,player_addrs)) = ctx.data_mut(|d| {\n"
    idx = t.find(marker)
    if idx < 0:
        raise SystemExit("v7.1 marker missing: tactical request dispatch")
    block = r'''        if let Some((club_addr,club_uid,players,max_morale,heal_injuries,lift_bans)) = ctx.data_mut(|d| {
            let id=egui::Id::new("element_v7_squad_power_request");
            let v=d.get_temp::<(u64,u32,Vec<(u64,usize)>,bool,bool,bool)>(id);
            d.remove::<(u64,u32,Vec<(u64,usize)>,bool,bool,bool)>(id); v
        }) {
            if self.conn.is_writable() {
                self.bridge.send(BridgeCmd::PlanClubSquadPower{club_addr,club_uid,players,max_morale,heal_injuries,lift_bans});
            }
        }
'''
    t = t[:idx] + block + t[idx:]
wr(p, t)

print("Element v7.1 verified Squad Power Tools applied.")
