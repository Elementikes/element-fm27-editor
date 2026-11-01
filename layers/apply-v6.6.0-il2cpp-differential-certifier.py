from pathlib import Path

root = Path.cwd()

def rd(path):
    p = root / path
    if not p.exists():
        raise SystemExit(f"v6.6.0 missing {path}")
    return p.read_text(encoding="utf-8")

def wr(path, text):
    (root / path).write_text(text, encoding="utf-8")

def one(text, old, new, label):
    if old not in text:
        raise SystemExit(f"v6.6.0 marker missing: {label}")
    return text.replace(old, new, 1)

# Bridge protocol --------------------------------------------------------------
p = "src/bridge/cmd.rs"
t = rd(p)
if "pub struct TeamCohesionDeltaReport" not in t:
    marker = "/// Full staff data including name and role sub-record.\n"
    defs = '''#[derive(Clone, Debug, Default)]
pub struct TeamCohesionDeltaReport {
    pub club_addr: u64,
    pub senior_team_addr: u64,
    pub changed_bytes: usize,
    pub rows: Vec<String>,
}

'''
    t = one(t, marker, defs + marker, "delta report struct")
if "CaptureTeamCohesionBaseline" not in t:
    t = one(t, "    Ping,\n",
        "    CaptureTeamCohesionBaseline { club_addr: u64, senior_team_addr: u64 },\n"
        "    CompareTeamCohesionBaseline { club_addr: u64, senior_team_addr: u64 },\n"
        "    Ping,\n", "delta commands")
if "TeamCohesionBaselineReady" not in t:
    t = one(t, "    PingOk,\n",
        "    TeamCohesionBaselineReady { club_addr: u64, senior_team_addr: u64, bytes: usize },\n"
        "    TeamCohesionDeltaReady { club_addr: u64, report: TeamCohesionDeltaReport },\n"
        "    PingOk,\n", "delta results")
wr(p, t)

# Module registration ----------------------------------------------------------
p = "src/bridge/mod.rs"
t = rd(p)
if "mod team_cohesion_delta;" not in t:
    marker = "mod tactical_max_plan;\n"
    t = one(t, marker, marker + "mod team_cohesion_delta;\n", "delta module registration")
wr(p, t)

# Read-only differential engine ------------------------------------------------
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

pub(super) fn capture(
    fm: &FmProcess,
    club_addr: u64,
    senior_team_addr: u64,
) -> Result<TeamCohesionSnapshot, String> {
    if fm.build != GameBuild::Fm27Steam {
        return Err("Team Cohesion delta certifier is enabled only for FM27 Steam".into());
    }
    if !is_valid_ptr(club_addr) || !is_valid_ptr(senior_team_addr) {
        return Err("selected Club/SeniorTeam pointer is invalid; reload club".into());
    }
    let bytes = fm.read_bytes(senior_team_addr, REGION_SIZE)
        .map_err(|e| format!("capture SeniorTeam +0x000..+0xFFF: {e}"))?;
    if bytes.len() != REGION_SIZE {
        return Err(format!("short SeniorTeam capture: {} / {REGION_SIZE}", bytes.len()));
    }
    Ok(TeamCohesionSnapshot { club_addr, senior_team_addr, bytes })
}

fn changed_in(before: &[u8], after: &[u8], off: usize, width: usize) -> bool {
    before.get(off..off + width) != after.get(off..off + width)
}

fn u16_at(b: &[u8], off: usize) -> u16 {
    u16::from_le_bytes([b[off], b[off + 1]])
}
fn u32_at(b: &[u8], off: usize) -> u32 {
    u32::from_le_bytes([b[off], b[off + 1], b[off + 2], b[off + 3]])
}

pub(super) fn compare(
    fm: &FmProcess,
    baseline: &TeamCohesionSnapshot,
    club_addr: u64,
    senior_team_addr: u64,
) -> Result<TeamCohesionDeltaReport, String> {
    if baseline.club_addr != club_addr || baseline.senior_team_addr != senior_team_addr {
        return Err(format!(
            "baseline belongs to Club 0x{:X} / SeniorTeam 0x{:X}; current is 0x{:X} / 0x{:X}. Capture again.",
            baseline.club_addr, baseline.senior_team_addr, club_addr, senior_team_addr
        ));
    }
    let after = fm.read_bytes(senior_team_addr, REGION_SIZE)
        .map_err(|e| format!("compare SeniorTeam +0x000..+0xFFF: {e}"))?;
    if after.len() != REGION_SIZE { return Err("short SeniorTeam compare read".into()); }

    let changed_bytes = baseline.bytes.iter().zip(after.iter()).filter(|(a,b)| a != b).count();
    let mut candidates: Vec<(i64, usize, String)> = Vec::new();

    for off in (0..=REGION_SIZE - 2).step_by(2) {
        if off == KNOWN_REPUTATION_U16 || !changed_in(&baseline.bytes, &after, off, 2) { continue; }
        let a = u16_at(&baseline.bytes, off);
        let b = u16_at(&after, off);
        if a == b || a > 10_000 || b > 10_000 { continue; }
        let delta = b as i64 - a as i64;
        let mut score = delta.abs();
        if b == 10_000 { score += 50_000; }
        if b == 100 { score += 30_000; }
        if b > a { score += 5_000; }
        if a <= 100 && b <= 100 { score += 3_000; }
        candidates.push((score, off, format!(
            "Δ16 +0x{off:03X} | {a} → {b} | {delta:+} | score={score}"
        )));
    }

    for off in 0..REGION_SIZE {
        let a = baseline.bytes[off];
        let b = after[off];
        if a == b || a > 100 || b > 100 { continue; }
        let delta = b as i64 - a as i64;
        let mut score = delta.abs() * 100;
        if b == 100 { score += 25_000; }
        if b > a { score += 4_000; }
        candidates.push((score, off, format!(
            "Δ8  +0x{off:03X} | {a} → {b} | {delta:+} | score={score}"
        )));
    }

    for off in (0..=REGION_SIZE - 4).step_by(4) {
        if !changed_in(&baseline.bytes, &after, off, 4) { continue; }
        let a = u32_at(&baseline.bytes, off);
        let b = u32_at(&after, off);
        if a == b || a > 1_000_000 || b > 1_000_000 { continue; }
        let delta = b as i64 - a as i64;
        let mut score = delta.abs().min(20_000);
        if b == 10_000 { score += 40_000; }
        if b == 100 { score += 20_000; }
        candidates.push((score, off, format!(
            "Δ32 +0x{off:03X} | {a} → {b} | {delta:+} | score={score}"
        )));
    }

    candidates.sort_by(|a, b| b.0.cmp(&a.0).then_with(|| a.1.cmp(&b.1)));
    let mut rows: Vec<String> = candidates.into_iter().take(48).map(|(_,_,s)| s).collect();

    let mut i = 0usize;
    let mut raw_ranges = Vec::new();
    while i < REGION_SIZE {
        if baseline.bytes[i] == after[i] { i += 1; continue; }
        let start = i;
        while i < REGION_SIZE && baseline.bytes[i] != after[i] { i += 1; }
        let len = i - start;
        raw_ranges.push(format!("ΔRAW +0x{start:03X}..+0x{:03X} | {len} byte(s)", i - 1));
    }
    if rows.is_empty() && raw_ranges.is_empty() {
        rows.push("NO CHANGES in SeniorTeam +0x000..+0xFFF".into());
    } else {
        rows.extend(raw_ranges.into_iter().take(24));
    }

    Ok(TeamCohesionDeltaReport {
        club_addr,
        senior_team_addr,
        changed_bytes,
        rows,
    })
}
''', encoding="utf-8")

# Worker state + commands -------------------------------------------------------
p = "src/bridge/worker.rs"
t = rd(p)
if "use super::team_cohesion_delta;" not in t:
    marker = "use super::tactical_max_plan;\n"
    t = one(t, marker, marker + "use super::team_cohesion_delta;\n", "worker delta import")
if "team_cohesion_baseline" not in t:
    marker = "    let mut last_counts: Option<(usize, usize, usize)> = None;\n"
    t = one(t, marker, marker + "    let mut team_cohesion_baseline: Option<team_cohesion_delta::TeamCohesionSnapshot> = None;\n", "worker baseline state")
if "BridgeCmd::CaptureTeamCohesionBaseline" not in t:
    marker = "            BridgeCmd::Ping => {\n"
    arms = '''            BridgeCmd::CaptureTeamCohesionBaseline { club_addr, senior_team_addr } => {
                let result = match &fm {
                    Some(f) => team_cohesion_delta::capture(f, club_addr, senior_team_addr),
                    None => Err("Cannot capture Team Cohesion baseline: no process attached".to_owned()),
                };
                match result {
                    Ok(snapshot) => {
                        let bytes = snapshot.bytes.len();
                        team_cohesion_baseline = Some(snapshot);
                        let _ = tx.send(BridgeResult::TeamCohesionBaselineReady { club_addr, senior_team_addr, bytes });
                    }
                    Err(error) => { let _ = tx.send(BridgeResult::Error(format!("Team Cohesion baseline: {error}"))); }
                }
            }

            BridgeCmd::CompareTeamCohesionBaseline { club_addr, senior_team_addr } => {
                let result = match (&fm, &team_cohesion_baseline) {
                    (Some(f), Some(snapshot)) => team_cohesion_delta::compare(f, snapshot, club_addr, senior_team_addr),
                    (None, _) => Err("Cannot compare Team Cohesion: no process attached".to_owned()),
                    (_, None) => Err("No Team Cohesion baseline captured yet".to_owned()),
                };
                match result {
                    Ok(report) => { let _ = tx.send(BridgeResult::TeamCohesionDeltaReady { club_addr, report }); }
                    Err(error) => { let _ = tx.send(BridgeResult::Error(format!("Team Cohesion compare: {error}"))); }
                }
            }

'''
    t = one(t, marker, arms + marker, "worker delta command arms")
wr(p, t)

# App result/request routing ----------------------------------------------------
p = "src/app.rs"
t = rd(p)
if "BridgeResult::TeamCohesionBaselineReady" not in t:
    marker = "                BridgeResult::PingOk => {}\n"
    arms = r'''                BridgeResult::TeamCohesionBaselineReady { club_addr, senior_team_addr, bytes } => {
                    ctx.data_mut(|d| d.insert_temp(
                        egui::Id::new(("element_team_cohesion_baseline_ready", club_addr)),
                        (senior_team_addr, bytes),
                    ));
                    self.set_status(format!(
                        "Team Cohesion baseline captured • SeniorTeam 0x{senior_team_addr:X} • {bytes} bytes"
                    ));
                }
                BridgeResult::TeamCohesionDeltaReady { club_addr, report } => {
                    let changed = report.changed_bytes;
                    ctx.data_mut(|d| d.insert_temp(
                        egui::Id::new(("element_team_cohesion_delta_report", club_addr)),
                        report,
                    ));
                    self.set_status(format!("Team Cohesion differential complete • {changed} changed byte(s)"));
                }
'''
    t = one(t, marker, arms + marker, "app delta results")

if "element_capture_team_cohesion_baseline_request" not in t:
    marker = "        // Element v2.8 read-only Tactical Knowledge inspector request.\n"
    block = r'''        let cohesion_capture = ctx.data_mut(|d| {
            let id = egui::Id::new("element_capture_team_cohesion_baseline_request");
            let request = d.get_temp::<(u64, u64)>(id);
            d.remove::<(u64, u64)>(id);
            request
        });
        if let Some((club_addr, senior_team_addr)) = cohesion_capture {
            if self.conn.is_writable() {
                self.bridge.send(BridgeCmd::CaptureTeamCohesionBaseline { club_addr, senior_team_addr });
                self.set_status("Capturing Team Cohesion baseline…".into());
            }
        }

        let cohesion_compare = ctx.data_mut(|d| {
            let id = egui::Id::new("element_compare_team_cohesion_baseline_request");
            let request = d.get_temp::<(u64, u64)>(id);
            d.remove::<(u64, u64)>(id);
            request
        });
        if let Some((club_addr, senior_team_addr)) = cohesion_compare {
            if self.conn.is_writable() {
                self.bridge.send(BridgeCmd::CompareTeamCohesionBaseline { club_addr, senior_team_addr });
                self.set_status("Comparing Team Cohesion snapshot…".into());
            }
        }

'''
    t = one(t, marker, block + marker, "app delta requests")
wr(p, t)

# Tactical Knowledge UI --------------------------------------------------------
p = "src/ui/club_panel.rs"
t = rd(p)
if "IL2CPP ACTION CERTIFIER" not in t:
    anchor = '            ui.label(egui::RichText::new("Observed FM27 after MAX:").strong());\n'
    if anchor not in t:
        raise SystemExit("v6.6.0 marker missing: tactical observed anchor")
    panel = r'''            egui::Frame::group(ui.style()).show(ui, |ui| {
                ui.horizontal_wrapped(|ui| {
                    ui.label(egui::RichText::new("IL2CPP ACTION CERTIFIER").strong().color(egui::Color32::from_rgb(112, 177, 255)));
                    ui.separator();
                    ui.label(egui::RichText::new("TeamImproveTeamCohesion • native FM27 ActionID discovered").small().weak());
                });
                ui.label(egui::RichText::new("Pause FM27. Capture baseline → in FMRTE run only Improve Team Cohesion for this team → return here and Compare. Element ranks only bytes that actually changed; no cohesion write occurs.").small());
                ui.add_space(3.0);
                if let Some(team) = club.senior_team_addr {
                    ui.horizontal_wrapped(|ui| {
                        let enabled = crate::ui::navigation::editing_enabled(ui);
                        if ui.add_enabled(enabled, egui::Button::new("1 • CAPTURE COHESION BASELINE")).clicked() {
                            ui.ctx().data_mut(|d| d.insert_temp(
                                egui::Id::new("element_capture_team_cohesion_baseline_request"),
                                (club.addr, team),
                            ));
                        }
                        let baseline_ready = ui.ctx().data_mut(|d| {
                            d.get_temp::<(u64, usize)>(egui::Id::new(("element_team_cohesion_baseline_ready", club.addr)))
                        }).is_some_and(|(addr, _)| addr == team);
                        if ui.add_enabled(enabled && baseline_ready, egui::Button::new("2 • COMPARE AFTER FMRTE COHESION")).clicked() {
                            ui.ctx().data_mut(|d| d.insert_temp(
                                egui::Id::new("element_compare_team_cohesion_baseline_request"),
                                (club.addr, team),
                            ));
                        }
                        if baseline_ready {
                            ui.label(egui::RichText::new("BASELINE READY").small().strong().color(egui::Color32::from_rgb(88, 214, 141)));
                        }
                    });
                }
                if let Some(report) = ui.ctx().data_mut(|d| {
                    d.get_temp::<crate::bridge::TeamCohesionDeltaReport>(
                        egui::Id::new(("element_team_cohesion_delta_report", club.addr))
                    )
                }) {
                    ui.add_space(4.0);
                    ui.label(egui::RichText::new(format!("DELTA RESULT • {} changed byte(s)", report.changed_bytes)).strong());
                    egui::ScrollArea::vertical().max_height(220.0).show(ui, |ui| {
                        for row in report.rows.iter().take(40) {
                            ui.label(egui::RichText::new(row).monospace().size(8.0));
                        }
                    });
                }
            });
            ui.add_space(4.0);
'''
    t = t.replace(anchor, panel + anchor, 1)

t = t.replace("v6.5.0 • TACTICAL KNOWLEDGE", "v6.6.0 • IL2CPP ACTION CERTIFIER", 1)
wr(p, t)

print("Element v6.6.0 IL2CPP-assisted Team Cohesion differential certifier applied.")
