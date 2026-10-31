$ErrorActionPreference = 'Stop'
$SourceRoot = (Get-Location).Path

function Read-Text([string]$RelativePath) {
    $Path = Join-Path $SourceRoot $RelativePath
    if (-not (Test-Path -LiteralPath $Path)) { throw "Source file not found: $Path" }
    return [IO.File]::ReadAllText($Path)
}

function Write-Text([string]$RelativePath, [string]$Text) {
    $Path = Join-Path $SourceRoot $RelativePath
    [IO.File]::WriteAllText($Path, $Text, [Text.UTF8Encoding]::new($false))
}

function Replace-Required([string]$RelativePath, [string]$Old, [string]$New) {
    $Text = Read-Text $RelativePath
    if (-not $Text.Contains($Old)) { throw "v2.8: expected text not found in $RelativePath`n--- expected ---`n$Old" }
    Write-Text $RelativePath ($Text.Replace($Old, $New))
}

# -----------------------------------------------------------------------------
# Element v2.8 — TACTICAL KNOWLEDGE LIVE INSPECTOR
#
# Read-only runtime research pass. It scans from the already validated senior
# team object and looks for heap pointers, std::vector-like descriptors,
# six-collection runs, packed 14-bit knowledge samples and 16-byte rows whose
# u16 knowledge value is at +14. It does NOT write FM memory and it does NOT
# unlock the 100% action merely because a heuristic candidate is found.
# -----------------------------------------------------------------------------

# ========================== BRIDGE PROTOCOL ===================================
$cmd = 'src/bridge/cmd.rs'
$cmdText = Read-Text $cmd
if (-not $cmdText.Contains('pub struct TacticalInspectorReport')) {
    $entityCounts = @'
#[derive(Clone)]
pub struct EntityCounts {
    pub players: usize,
    pub staff: usize,
    pub clubs: usize,
}
'@
    $reportStruct = @'
#[derive(Clone, Debug, Default)]
pub struct TacticalInspectorReport {
    pub club_addr: u64,
    pub senior_team_addr: u64,
    pub scanned_roots: usize,
    pub pointer_candidates: usize,
    pub vector_candidates: usize,
    pub six_collection_candidates: usize,
    pub formation_candidates: usize,
    pub packed14_candidates: usize,
    pub read_errors: usize,
    pub strongest_score: u8,
    pub candidate_lines: Vec<String>,
    /// Deliberately false until an exact ownership chain + cache-refresh path
    /// is identified and independently read-back validated.
    pub ready_for_write: bool,
}

'@
    if (-not $cmdText.Contains($entityCounts)) { throw 'v2.8: EntityCounts insertion boundary not found' }
    $cmdText = $cmdText.Replace($entityCounts, $entityCounts + "`n" + $reportStruct)

    $cmdText = $cmdText.Replace(
        '    pub senior_team_addr: Option<u64>,',
        "    pub senior_team_addr: Option<u64>,`n    pub tactical_report: Option<TacticalInspectorReport>,"
    )
    $cmdText = $cmdText.Replace(
        '    LoadHumanManager,',
        "    LoadHumanManager,`n    InspectTacticalKnowledge { club_addr: u64, senior_team_addr: u64 },"
    )
    $cmdText = $cmdText.Replace(
        '    ClubLoaded(ClubView),',
        "    ClubLoaded(ClubView),`n    TacticalInspectorDone { club_addr: u64, report: TacticalInspectorReport },"
    )
    Write-Text $cmd $cmdText
}

# ========================== BRIDGE MODULE =====================================
$bridgeMod = 'src/bridge/mod.rs'
$modText = Read-Text $bridgeMod
if (-not $modText.Contains('mod tactical_inspector;')) {
    $modText = $modText.Replace("mod entity_load;`nmod worker;", "mod entity_load;`nmod tactical_inspector;`nmod worker;")
    $modText = $modText.Replace(
        '    BridgeCmd, BridgeResult, ClubView, EntityCounts, ProcessBridge, StaffView,',
        '    BridgeCmd, BridgeResult, ClubView, EntityCounts, ProcessBridge, StaffView, TacticalInspectorReport,'
    )
    Write-Text $bridgeMod $modText
}

# ========================== CLUB VIEW INIT ====================================
$entityLoad = 'src/bridge/entity_load.rs'
$elText = Read-Text $entityLoad
if (-not $elText.Contains('tactical_report: None')) {
    $elText = $elText.Replace(
        "        senior_team_raw,`n        senior_team_addr,`n        budget_raw,",
        "        senior_team_raw,`n        senior_team_addr,`n        tactical_report: None,`n        budget_raw,"
    )
    Write-Text $entityLoad $elText
}

# ========================== READ-ONLY INSPECTOR ===============================
$inspector = 'src/bridge/tactical_inspector.rs'
$inspectorCode = @'
//! Element v2.8 read-only Tactical Knowledge live inspector.
//!
//! This module performs bounded, heuristic discovery only. It never writes
//! target memory and cannot by itself unlock Tactical Knowledge mutation.

use std::collections::HashSet;

use crate::process::FmProcess;

use super::cmd::TacticalInspectorReport;

const TEAM_READ: usize = 0x600;
const ROOT_READ: usize = 0x180;
const MAX_ROOTS: usize = 96;
const MAX_VECTOR_SPAN: usize = 0x20_000;
const MAX_LINES: usize = 18;

#[derive(Clone, Copy, Debug)]
struct VectorDesc {
    data: u64,
    end: u64,
    cap: u64,
    span: usize,
}

fn valid_ptr(p: u64) -> bool {
    p > 0x10000 && p < 0x7FFF_FFFF_FFFF
}

fn qword(buf: &[u8], off: usize) -> Option<u64> {
    Some(u64::from_le_bytes(buf.get(off..off + 8)?.try_into().ok()?))
}

fn vector_desc_at(buf: &[u8], off: usize) -> Option<VectorDesc> {
    let data = qword(buf, off)?;
    let end = qword(buf, off + 8)?;
    let cap = qword(buf, off + 16)?;
    if !valid_ptr(data) || !valid_ptr(end) || !valid_ptr(cap) || end < data || cap < end {
        return None;
    }
    let span = usize::try_from(end - data).ok()?;
    let cap_span = usize::try_from(cap - data).ok()?;
    if span == 0 || span > MAX_VECTOR_SPAN || cap_span > MAX_VECTOR_SPAN * 4 {
        return None;
    }
    Some(VectorDesc { data, end, cap, span })
}

fn packed14_score(sample: &[u8]) -> Option<(usize, usize)> {
    let mut total = 0usize;
    let mut plausible = 0usize;
    let mut positive = 0usize;
    for pair in sample.chunks_exact(2).take(64) {
        total += 1;
        let raw = u16::from_le_bytes([pair[0], pair[1]]);
        let value = raw & 0x3FFF;
        if value <= 10_000 {
            plausible += 1;
            if value > 0 {
                positive += 1;
            }
        }
    }
    if total >= 4 && plausible * 100 >= total * 80 && positive >= 2 {
        Some((plausible, total))
    } else {
        None
    }
}

fn formation_row_score(sample: &[u8], rows: usize) -> Option<(usize, usize)> {
    let rows = rows.min(sample.len() / 16).min(16);
    if rows == 0 {
        return None;
    }
    let mut plausible = 0usize;
    let mut positive = 0usize;
    for row in 0..rows {
        let off = row * 16 + 14;
        let value = u16::from_le_bytes([sample[off], sample[off + 1]]);
        if value <= 10_000 {
            plausible += 1;
            if value > 0 {
                positive += 1;
            }
        }
    }
    if plausible * 2 >= rows && positive >= 1 {
        Some((plausible, rows))
    } else {
        None
    }
}

fn push_line(report: &mut TacticalInspectorReport, line: String) {
    if report.candidate_lines.len() < MAX_LINES {
        report.candidate_lines.push(line);
    }
}

fn scan_blob(
    fm: &FmProcess,
    base: u64,
    label: &str,
    blob: &[u8],
    report: &mut TacticalInspectorReport,
) {
    let mut seen_vectors = HashSet::new();
    let limit = blob.len().saturating_sub(24);
    let mut off = 0usize;
    while off <= limit {
        if let Some(desc) = vector_desc_at(blob, off) {
            if seen_vectors.insert((desc.data, desc.end, desc.cap)) {
                let sample_len = desc.span.min(256).max(2);
                if let Ok(sample) = fm.read_bytes(desc.data, sample_len) {
                    report.vector_candidates += 1;

                    if let Some((good, total)) = packed14_score(&sample) {
                        report.packed14_candidates += 1;
                        push_line(
                            report,
                            format!(
                                "{label}+0x{off:X}: packed14-like vector @0x{:X}, span {}B ({good}/{total} plausible)",
                                desc.data, desc.span
                            ),
                        );
                    }

                    if desc.span % 16 == 0 {
                        let rows = desc.span / 16;
                        if (1..=256).contains(&rows) {
                            if let Some((good, checked)) = formation_row_score(&sample, rows) {
                                report.formation_candidates += 1;
                                push_line(
                                    report,
                                    format!(
                                        "{label}+0x{off:X}: formation-row candidate @0x{:X}, {rows} rows ({good}/{checked} +14 values plausible)",
                                        desc.data
                                    ),
                                );
                            }
                        }
                    }
                } else {
                    report.read_errors += 1;
                }
            }
        }

        // A normal MSVC std::vector is 24 bytes. Six adjacent valid vector
        // descriptors is therefore a strong structural candidate for the
        // published six learned-instruction collections. This is still only
        // a candidate until ownership and key semantics are verified.
        if off + 6 * 24 <= blob.len() {
            let mut run = true;
            let mut spans = [0usize; 6];
            for i in 0..6 {
                let Some(d) = vector_desc_at(blob, off + i * 24) else {
                    run = false;
                    break;
                };
                if fm.read_bytes(d.data, d.span.min(8).max(2)).is_err() {
                    run = false;
                    break;
                }
                spans[i] = d.span;
            }
            if run {
                report.six_collection_candidates += 1;
                push_line(
                    report,
                    format!(
                        "{label}+0x{off:X}: SIX adjacent vector descriptors; spans={:?}",
                        spans
                    ),
                );
            }
        }

        off += 8;
    }

    let _ = base; // retained in the signature for future exact-chain logging.
}

pub(super) fn inspect(
    fm: &FmProcess,
    club_addr: u64,
    senior_team_addr: u64,
) -> Result<TacticalInspectorReport, String> {
    if !valid_ptr(club_addr) {
        return Err(format!("invalid club pointer 0x{club_addr:X}"));
    }
    if !valid_ptr(senior_team_addr) {
        return Err(format!("invalid senior-team pointer 0x{senior_team_addr:X}"));
    }

    let team_raw = fm
        .read_bytes(senior_team_addr, TEAM_READ)
        .or_else(|_| fm.read_bytes(senior_team_addr, TEAM_READ / 2))
        .map_err(|e| format!("cannot read senior-team object: {e}"))?;

    let mut report = TacticalInspectorReport {
        club_addr,
        senior_team_addr,
        scanned_roots: 1,
        ..Default::default()
    };

    scan_blob(fm, senior_team_addr, "senior_team", &team_raw, &mut report);

    // Collect unique heap roots referenced directly by the senior-team
    // object. Ignore module pointers (normally vtables/code) and never scan
    // more than MAX_ROOTS so this stays bounded and responsive.
    let mut seen = HashSet::new();
    let mut roots = Vec::new();
    for off in (0..team_raw.len().saturating_sub(8)).step_by(8) {
        let Some(ptr) = qword(&team_raw, off) else { continue };
        if !valid_ptr(ptr) || (fm.gp_base..fm.gp_end).contains(&ptr) || !seen.insert(ptr) {
            continue;
        }
        roots.push((off, ptr));
        if roots.len() >= MAX_ROOTS {
            break;
        }
    }
    report.pointer_candidates = roots.len();

    for (root_off, ptr) in roots {
        match fm.read_bytes(ptr, ROOT_READ) {
            Ok(blob) => {
                report.scanned_roots += 1;
                scan_blob(
                    fm,
                    ptr,
                    &format!("team+0x{root_off:X}->0x{ptr:X}"),
                    &blob,
                    &mut report,
                );
            }
            Err(_) => report.read_errors += 1,
        }
    }

    let mut score = 0u8;
    if report.pointer_candidates > 0 { score += 1; }
    if report.vector_candidates > 0 { score += 1; }
    if report.packed14_candidates > 0 { score += 1; }
    if report.formation_candidates > 0 { score += 1; }
    if report.six_collection_candidates > 0 { score += 1; }
    report.strongest_score = score.min(5);

    // Critical safety gate: heuristic discovery never authorizes writes.
    report.ready_for_write = false;
    if report.candidate_lines.is_empty() {
        report.candidate_lines.push(
            "No high-confidence tactical collection candidate found in the bounded senior-team scan.".into(),
        );
    }
    Ok(report)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn vector_descriptor_accepts_ordered_userspace_bounds() {
        let mut buf = vec![0u8; 24];
        buf[0..8].copy_from_slice(&0x100000u64.to_le_bytes());
        buf[8..16].copy_from_slice(&0x100040u64.to_le_bytes());
        buf[16..24].copy_from_slice(&0x100080u64.to_le_bytes());
        let d = vector_desc_at(&buf, 0).unwrap();
        assert_eq!(d.span, 0x40);
    }

    #[test]
    fn packed14_requires_nonzero_plausible_values() {
        let mut bytes = Vec::new();
        for v in [10_000u16, 9_000, 8_000, 7_000, 6_000, 5_000] {
            bytes.extend_from_slice(&v.to_le_bytes());
        }
        assert!(packed14_score(&bytes).is_some());
        assert!(packed14_score(&[0u8; 16]).is_none());
    }

    #[test]
    fn formation_rows_read_u16_at_plus_14() {
        let mut bytes = vec![0u8; 16 * 4];
        for row in 0..4 {
            bytes[row * 16 + 14..row * 16 + 16].copy_from_slice(&10_000u16.to_le_bytes());
        }
        assert_eq!(formation_row_score(&bytes, 4), Some((4, 4)));
    }
}
'@
Write-Text $inspector $inspectorCode

# ========================== WORKER WIRING =====================================
$worker = 'src/bridge/worker.rs'
$workerText = Read-Text $worker
if (-not $workerText.Contains('super::tactical_inspector')) {
    $workerText = $workerText.Replace('use super::entity_load;', "use super::entity_load;`nuse super::tactical_inspector;")
}
if (-not $workerText.Contains('BridgeCmd::InspectTacticalKnowledge')) {
    $needle = '            BridgeCmd::WriteBytes { id, addr, data } => {'
    $arm = @'
            BridgeCmd::InspectTacticalKnowledge { club_addr, senior_team_addr } => {
                let result = match &fm {
                    Some(f) => tactical_inspector::inspect(f, club_addr, senior_team_addr),
                    None => Err("Cannot inspect tactical knowledge: no process attached".to_owned()),
                };
                match result {
                    Ok(report) => {
                        let _ = tx.send(BridgeResult::TacticalInspectorDone { club_addr, report });
                    }
                    Err(error) => {
                        let _ = tx.send(BridgeResult::Error(format!("Tactical inspector: {error}")));
                    }
                }
            }

'@
    $at = $workerText.IndexOf($needle)
    if ($at -lt 0) { throw 'v2.8: worker WriteBytes boundary not found' }
    $workerText = $workerText.Substring(0, $at) + $arm + $workerText.Substring($at)
}
Write-Text $worker $workerText

# ========================== TACTICAL UI =======================================
$c = 'src/ui/club_panel.rs'
$clubText = Read-Text $c
$engineStart = $clubText.IndexOf('const ELEMENT_TACTICAL_MAX_KNOWLEDGE:')
$lockedStart = $clubText.IndexOf('fn locked_notice(', $engineStart)
if ($engineStart -lt 0 -or $lockedStart -lt 0) { throw 'v2.8: v2.7 tactical engine block not found' }

$newEngine = @'
const ELEMENT_TACTICAL_MAX_KNOWLEDGE: u16 = 10_000;
const ELEMENT_TACTICAL_INSTRUCTION_COLLECTIONS: usize = 6;
const ELEMENT_TACTICAL_FORMATION_VALUE_OFFSET: usize = 14;

fn element_tactical_percent(value: u16) -> f32 {
    (value.min(ELEMENT_TACTICAL_MAX_KNOWLEDGE) as f32 / ELEMENT_TACTICAL_MAX_KNOWLEDGE as f32)
        .clamp(0.0, 1.0)
}

fn element_tactical_row_value_bytes(value: u16) -> [u8; 2] {
    value.min(ELEMENT_TACTICAL_MAX_KNOWLEDGE).to_le_bytes()
}

fn element_tactical_pointer_ok(addr: Option<u64>) -> bool {
    addr.is_some_and(crate::player::is_valid_ptr)
}

fn element_tactical_status(ui: &mut egui::Ui, label: &str, ok: bool, ready: &str, blocked: &str) {
    ui.horizontal(|ui| {
        ui.add_sized([142.0, 16.0], egui::Label::new(egui::RichText::new(label).size(8.2)));
        let (text, color) = if ok {
            (ready, egui::Color32::from_rgb(72, 210, 132))
        } else {
            (blocked, egui::Color32::from_rgb(255, 184, 77))
        };
        ui.label(egui::RichText::new(text).size(8.2).strong().color(color));
    });
}

fn show_tactical_understanding(ui: &mut egui::Ui, club: &ClubView) {
    ui.spacing_mut().item_spacing = egui::vec2(6.0, 3.0);
    let club_ptr_ok = crate::player::is_valid_ptr(club.addr);
    let senior_team_ok = element_tactical_pointer_ok(club.senior_team_addr);
    let target_bytes = element_tactical_row_value_bytes(ELEMENT_TACTICAL_MAX_KNOWLEDGE);
    let report = club.tactical_report.as_ref();

    ui.horizontal(|ui| {
        ui.label(egui::RichText::new("TACTICAL KNOWLEDGE").size(13.0).strong());
        ui.separator();
        ui.label(egui::RichText::new("v2.8 • LIVE READ-ONLY INSPECTOR").size(8.0).strong().color(egui::Color32::from_rgb(112, 177, 255)));
    });
    ui.label(egui::RichText::new("Run the inspector against the current FM27 process. It scans bounded heap roots from the validated Senior Team object and reports structural candidates; it performs zero writes.").size(8.3).color(egui::Color32::from_rgb(154, 169, 194)));
    ui.add_space(4.0);

    ui.columns(3, |cols| {
        egui::Frame::group(cols[0].style())
            .fill(egui::Color32::from_rgb(25, 31, 45))
            .inner_margin(egui::Margin::symmetric(7, 5))
            .show(&mut cols[0], |ui| {
                ui.label(egui::RichText::new("KNOWN FORMAT").size(9.0).strong()); ui.separator();
                field_widget::info_label(ui, "Instruction collections", ELEMENT_TACTICAL_INSTRUCTION_COLLECTIONS);
                field_widget::info_label(ui, "Instruction knowledge", "14-bit");
                field_widget::info_label(ui, "Formation/role", format!("u16 @ +{}", ELEMENT_TACTICAL_FORMATION_VALUE_OFFSET));
                field_widget::info_label(ui, "100%", ELEMENT_TACTICAL_MAX_KNOWLEDGE);
                field_widget::info_label(ui, "100% bytes", format!("{:02X} {:02X}", target_bytes[0], target_bytes[1]));
            });

        egui::Frame::group(cols[1].style())
            .fill(egui::Color32::from_rgb(25, 31, 45))
            .inner_margin(egui::Margin::symmetric(7, 5))
            .show(&mut cols[1], |ui| {
                ui.label(egui::RichText::new("ROOT VALIDATION").size(9.0).strong()); ui.separator();
                element_tactical_status(ui, "Club object", club_ptr_ok, "AVAILABLE", "INVALID");
                element_tactical_status(ui, "Senior Team", senior_team_ok, "AVAILABLE", "UNAVAILABLE");
                element_tactical_status(ui, "Live process", crate::ui::navigation::editing_enabled(ui), "ATTACHED", "READ-ONLY");
                element_tactical_status(ui, "Write path", false, "READY", "LOCKED");
            });

        egui::Frame::group(cols[2].style())
            .fill(egui::Color32::from_rgb(25, 31, 45))
            .inner_margin(egui::Margin::symmetric(7, 5))
            .show(&mut cols[2], |ui| {
                ui.label(egui::RichText::new("LIVE INSPECTOR").size(9.0).strong()); ui.separator();
                let enabled = crate::ui::navigation::editing_enabled(ui) && senior_team_ok;
                if ui.add_enabled(enabled, egui::Button::new("Run Live Inspector")).clicked() {
                    if let Some(team) = club.senior_team_addr {
                        ui.ctx().data_mut(|d| d.insert_temp(
                            egui::Id::new("element_tactical_inspect_request"),
                            (club.addr, team),
                        ));
                    }
                }
                ui.label(egui::RichText::new("Read-only • bounded scan • no memory writes").size(8.0).color(egui::Color32::from_rgb(139, 157, 188)));
                if let Some(r) = report {
                    let color = if r.strongest_score >= 4 { egui::Color32::from_rgb(72, 210, 132) } else { egui::Color32::from_rgb(255, 184, 77) };
                    ui.label(egui::RichText::new(format!("Candidate confidence: {}/5", r.strongest_score)).size(9.0).strong().color(color));
                }
            });
    });

    ui.add_space(5.0);
    if let Some(r) = report {
        egui::Frame::group(ui.style())
            .fill(egui::Color32::from_rgb(20, 25, 36))
            .stroke(egui::Stroke::new(1.0, egui::Color32::from_rgb(53, 61, 78)))
            .inner_margin(egui::Margin::symmetric(7, 5))
            .show(ui, |ui| {
                ui.horizontal(|ui| {
                    ui.label(egui::RichText::new("INSPECTOR RESULT").size(9.0).strong());
                    ui.separator();
                    let text = if r.strongest_score >= 4 { "STRUCTURAL CANDIDATE FOUND • WRITE STILL LOCKED" } else { "MORE MAPPING EVIDENCE REQUIRED" };
                    ui.label(egui::RichText::new(text).size(8.0).strong().color(egui::Color32::from_rgb(255, 184, 77)));
                });
                egui::Grid::new("element_tactical_inspector_summary").num_columns(4).spacing([14.0, 3.0]).show(ui, |ui| {
                    ui.label("Roots scanned"); ui.label(r.scanned_roots.to_string());
                    ui.label("Pointers"); ui.label(r.pointer_candidates.to_string()); ui.end_row();
                    ui.label("Vectors"); ui.label(r.vector_candidates.to_string());
                    ui.label("Six-runs"); ui.label(r.six_collection_candidates.to_string()); ui.end_row();
                    ui.label("Packed14"); ui.label(r.packed14_candidates.to_string());
                    ui.label("Formation +14"); ui.label(r.formation_candidates.to_string()); ui.end_row();
                    ui.label("Read errors"); ui.label(r.read_errors.to_string());
                    ui.label("Write ready"); ui.label(if r.ready_for_write { "YES" } else { "NO" }); ui.end_row();
                });
                ui.separator();
                for line in r.candidate_lines.iter().take(10) {
                    ui.label(egui::RichText::new(line).size(7.8).monospace().color(egui::Color32::from_rgb(177, 195, 222)));
                }
            });
    }

    ui.add_space(5.0);
    egui::Frame::group(ui.style())
        .fill(egui::Color32::from_rgb(20, 25, 36))
        .inner_margin(egui::Margin::symmetric(7, 5))
        .show(ui, |ui| {
            ui.horizontal(|ui| {
                ui.add_enabled(false, egui::Button::new("Apply Full Tactical Knowledge (100%)"))
                    .on_disabled_hover_text("Inspector candidates are not enough. Element needs an exact ownership chain and cache-refresh record with read-back validation before writes unlock.");
                ui.label(egui::RichText::new("WRITE LOCK ACTIVE").size(8.0).strong().color(egui::Color32::from_rgb(255, 184, 77)));
            });
            ui.label(egui::RichText::new("Next gate: prove which candidate belongs to the player-training object, verify instruction keys/ownership across multiple players, identify the knowledge-cache refresh field, then enable an all-or-nothing Undo-backed batch.").size(8.0).color(egui::Color32::from_rgb(139, 157, 188)));
        });
}

#[cfg(test)]
mod element_tactical_engine_tests {
    use super::{element_tactical_percent, element_tactical_row_value_bytes, ELEMENT_TACTICAL_MAX_KNOWLEDGE};

    #[test]
    fn tactical_max_is_exactly_one_hundred_percent() {
        assert_eq!(element_tactical_percent(ELEMENT_TACTICAL_MAX_KNOWLEDGE), 1.0);
        assert_eq!(element_tactical_percent(0), 0.0);
    }

    #[test]
    fn tactical_formation_value_is_little_endian_u16() {
        assert_eq!(element_tactical_row_value_bytes(10_000), [0x10, 0x27]);
    }
}

'@
$clubText = $clubText.Substring(0, $engineStart) + $newEngine + $clubText.Substring($lockedStart)
Write-Text $c $clubText

# ========================== APP REQUEST/RESULT ================================
$a = 'src/app.rs'
$appText = Read-Text $a
if (-not $appText.Contains('BridgeResult::TacticalInspectorDone')) {
    $humanMarker = '                BridgeResult::HumanManagerLoaded(view) => {'
    $at = $appText.IndexOf($humanMarker)
    if ($at -lt 0) { throw 'v2.8: HumanManagerLoaded result boundary not found' }
    $resultArm = @'
                BridgeResult::TacticalInspectorDone { club_addr, report } => {
                    let summary = format!(
                        "Tactical inspector: confidence {}/5, {} vectors, {} six-runs, {} formation candidates",
                        report.strongest_score,
                        report.vector_candidates,
                        report.six_collection_candidates,
                        report.formation_candidates,
                    );
                    if let Some(snapshot) = self.club_snapshots.get_mut(&club_addr) {
                        snapshot.tactical_report = Some(report.clone());
                    }
                    if let Some(club) = self.selected_club.as_mut().filter(|c| c.addr == club_addr) {
                        club.tactical_report = Some(report);
                    }
                    self.set_status(summary);
                }
'@
    $appText = $appText.Substring(0, $at) + $resultArm + $appText.Substring($at)
}

$requestMarker = '        // A write becomes undoable only after the worker confirms success.'
if (-not $appText.Contains('element_tactical_inspect_request')) {
    $at = $appText.IndexOf($requestMarker)
    if ($at -lt 0) { throw 'v2.8: post-UI write boundary not found' }
    $requestBlock = @'
        // Element v2.8 read-only Tactical Knowledge inspector request.
        let tactical_request = ctx.data_mut(|d| {
            let id = egui::Id::new("element_tactical_inspect_request");
            let request = d.get_temp::<(u64, u64)>(id);
            d.remove::<(u64, u64)>(id);
            request
        });
        if let Some((club_addr, senior_team_addr)) = tactical_request {
            if self.conn.is_writable() {
                self.bridge.send(BridgeCmd::InspectTacticalKnowledge { club_addr, senior_team_addr });
                self.set_status("Tactical inspector running read-only scan…".into());
            } else {
                self.set_status("Tactical inspector requires a live FM27 attachment".into());
            }
        }

'@
    $appText = $appText.Substring(0, $at) + $requestBlock + $appText.Substring($at)
}
Write-Text $a $appText

# ========================== ROADMAP ===========================================
$roadmap = Join-Path $SourceRoot 'ELEMENT_ROADMAP.md'
if (Test-Path -LiteralPath $roadmap) {
    $text = [IO.File]::ReadAllText($roadmap)
    if (-not $text.Contains('v2.8 live tactical inspector')) {
        $text += @'

## v2.8 live tactical inspector
- Added a bounded read-only runtime scanner rooted at the validated Senior Team object.
- Reports heap pointer roots, vector-like records, six-vector collection runs, packed 14-bit samples and 16-byte formation rows with u16 knowledge at +14.
- Heuristic discoveries never unlock writes; Full Tactical Knowledge remains locked until exact player-training ownership and cache-refresh chains pass read-back validation.
'@
        [IO.File]::WriteAllText($roadmap, $text, [Text.UTF8Encoding]::new($false))
    }
}

Write-Host 'Element v2.8 Tactical Knowledge live inspector applied successfully.'
