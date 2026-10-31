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
    if (-not $Text.Contains($Old)) { throw "v2.9: expected text not found in $RelativePath`n--- expected ---`n$Old" }
    Write-Text $RelativePath ($Text.Replace($Old, $New))
}

# -----------------------------------------------------------------------------
# Element v2.9 — TACTICAL KNOWLEDGE CROSS VALIDATOR
#
# Still strictly read-only. This pass ranks the structural candidates discovered
# by v2.8, prioritises six adjacent vector runs and formation/role rows, emits
# address-independent signatures, and dumps bounded samples for each vector.
# It does NOT enable any FM memory write.
# -----------------------------------------------------------------------------

$inspector = 'src/bridge/tactical_inspector.rs'
$existing = Read-Text $inspector
if (-not $existing.Contains('Element v2.8 read-only Tactical Knowledge live inspector')) {
    throw 'v2.9: v2.8 tactical inspector source not found; refusing to replace an unknown inspector'
}

$inspectorCode = @'
//! Element v2.9 read-only Tactical Knowledge cross validator.
//!
//! It ranks v2.8 structural candidates, prioritises six-vector runs and
//! formation/role rows, produces stable path signatures, and emits bounded
//! sample dumps. It performs zero writes to the FM process.

use std::cmp::Reverse;
use std::collections::HashSet;

use crate::process::FmProcess;

use super::cmd::TacticalInspectorReport;

const TEAM_READ: usize = 0x600;
const ROOT_READ: usize = 0x200;
const MAX_ROOTS: usize = 96;
const MAX_VECTOR_SPAN: usize = 0x20_000;
const MAX_SIX_RUNS_RENDERED: usize = 2;
const MAX_FORMATION_LINES: usize = 2;
const MAX_PACKED_LINES: usize = 2;

#[derive(Clone, Copy, Debug)]
struct VectorDesc {
    data: u64,
    end: u64,
    cap: u64,
    span: usize,
}

#[derive(Clone, Debug)]
struct SixRunCandidate {
    score: u8,
    signature: String,
    location: String,
    root_addr: u64,
    spans: [usize; 6],
    lines: Vec<String>,
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

fn packed14_score(sample: &[u8]) -> Option<(usize, usize, usize)> {
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
        Some((plausible, total, positive))
    } else {
        None
    }
}

fn formation_row_score(sample: &[u8], rows: usize) -> Option<(usize, usize, usize)> {
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
        Some((plausible, rows, positive))
    } else {
        None
    }
}

fn dump_masked14(sample: &[u8], max: usize) -> String {
    let values: Vec<String> = sample
        .chunks_exact(2)
        .take(max)
        .map(|pair| {
            let raw = u16::from_le_bytes([pair[0], pair[1]]);
            format!("{}", raw & 0x3FFF)
        })
        .collect();
    format!("[{}]", values.join(","))
}

fn element_counts(span: usize) -> String {
    format!(
        "2:{} 4:{} 8:{} 16:{}",
        span / 2,
        span / 4,
        span / 8,
        span / 16
    )
}

fn stable_path(label: &str, off: usize) -> String {
    format!("{label}+0x{off:X}")
}

fn inspect_vector(
    fm: &FmProcess,
    desc: VectorDesc,
    index: usize,
) -> Result<(String, bool, bool), ()> {
    let sample_len = desc.span.min(256).max(2);
    let sample = fm.read_bytes(desc.data, sample_len).map_err(|_| ())?;
    let p14 = packed14_score(&sample);
    let form = if desc.span % 16 == 0 {
        formation_row_score(&sample, desc.span / 16)
    } else {
        None
    };
    let p14_text = p14
        .map(|(good, total, positive)| format!("p14={good}/{total} pos={positive}"))
        .unwrap_or_else(|| "p14=no".to_owned());
    let form_text = form
        .map(|(good, total, positive)| format!("f+14={good}/{total} pos={positive}"))
        .unwrap_or_else(|| "f+14=no".to_owned());
    let line = format!(
        "  V{} @0x{:X} span={}B [{}] {} {} dump14={}",
        index + 1,
        desc.data,
        desc.span,
        element_counts(desc.span),
        p14_text,
        form_text,
        dump_masked14(&sample, 8),
    );
    Ok((line, p14.is_some(), form.is_some()))
}

fn scan_blob(
    fm: &FmProcess,
    root_addr: u64,
    label: &str,
    blob: &[u8],
    report: &mut TacticalInspectorReport,
    six_runs: &mut Vec<SixRunCandidate>,
    formation_lines: &mut Vec<String>,
    packed_lines: &mut Vec<String>,
) {
    let mut seen_vectors = HashSet::new();
    let limit = blob.len().saturating_sub(24);
    let mut off = 0usize;

    while off <= limit {
        if let Some(desc) = vector_desc_at(blob, off) {
            if seen_vectors.insert((desc.data, desc.end, desc.cap)) {
                let sample_len = desc.span.min(256).max(2);
                match fm.read_bytes(desc.data, sample_len) {
                    Ok(sample) => {
                        report.vector_candidates += 1;
                        if let Some((good, total, positive)) = packed14_score(&sample) {
                            report.packed14_candidates += 1;
                            if packed_lines.len() < 24 {
                                packed_lines.push(format!(
                                    "PACKED {} @0x{:X} span={}B {good}/{total} plausible pos={positive} dump14={}",
                                    stable_path(label, off),
                                    desc.data,
                                    desc.span,
                                    dump_masked14(&sample, 8),
                                ));
                            }
                        }
                        if desc.span % 16 == 0 {
                            let rows = desc.span / 16;
                            if (1..=256).contains(&rows) {
                                if let Some((good, checked, positive)) = formation_row_score(&sample, rows) {
                                    report.formation_candidates += 1;
                                    if formation_lines.len() < 16 {
                                        formation_lines.push(format!(
                                            "FORMATION {} @0x{:X} rows={} +14={good}/{checked} pos={positive}",
                                            stable_path(label, off),
                                            desc.data,
                                            rows,
                                        ));
                                    }
                                }
                            }
                        }
                    }
                    Err(_) => report.read_errors += 1,
                }
            }
        }

        if off + 6 * 24 <= blob.len() {
            let mut descs = Vec::with_capacity(6);
            let mut valid_run = true;
            for i in 0..6 {
                let Some(desc) = vector_desc_at(blob, off + i * 24) else {
                    valid_run = false;
                    break;
                };
                descs.push(desc);
            }

            if valid_run && descs.len() == 6 {
                let mut spans = [0usize; 6];
                let mut lines = Vec::with_capacity(6);
                let mut packed_hits = 0usize;
                let mut formation_hits = 0usize;
                let mut readable = true;

                for (i, desc) in descs.iter().copied().enumerate() {
                    spans[i] = desc.span;
                    match inspect_vector(fm, desc, i) {
                        Ok((line, p14, form)) => {
                            if p14 { packed_hits += 1; }
                            if form { formation_hits += 1; }
                            lines.push(line);
                        }
                        Err(_) => {
                            readable = false;
                            report.read_errors += 1;
                            break;
                        }
                    }
                }

                if readable {
                    report.six_collection_candidates += 1;
                    let mut score = 2u8; // six descriptors + all readable
                    if packed_hits >= 1 { score += 1; }
                    if packed_hits >= 2 { score += 1; }
                    if formation_hits >= 1 { score += 1; }
                    if label == "senior_team" || label == "team+0x30" { score += 1; }
                    let signature = format!("{} spans={:?}", stable_path(label, off), spans);
                    six_runs.push(SixRunCandidate {
                        score,
                        signature: signature.clone(),
                        location: stable_path(label, off),
                        root_addr,
                        spans,
                        lines,
                    });
                }
            }
        }

        off += 8;
    }
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
    let mut six_runs = Vec::new();
    let mut formation_lines = Vec::new();
    let mut packed_lines = Vec::new();

    scan_blob(
        fm,
        senior_team_addr,
        "senior_team",
        &team_raw,
        &mut report,
        &mut six_runs,
        &mut formation_lines,
        &mut packed_lines,
    );

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
                    &format!("team+0x{root_off:X}"),
                    &blob,
                    &mut report,
                    &mut six_runs,
                    &mut formation_lines,
                    &mut packed_lines,
                );
            }
            Err(_) => report.read_errors += 1,
        }
    }

    six_runs.sort_by_key(|candidate| Reverse(candidate.score));
    formation_lines.sort();
    packed_lines.sort();

    report.candidate_lines.clear();
    if let Some(best) = six_runs.first() {
        report.candidate_lines.push(format!(
            "CROSS-VALIDATION BEST: score={}/6 signature={} root=0x{:X}",
            best.score, best.signature, best.root_addr
        ));
    } else {
        report.candidate_lines.push("CROSS-VALIDATION: no readable six-vector run found".into());
    }

    for (rank, candidate) in six_runs.iter().take(MAX_SIX_RUNS_RENDERED).enumerate() {
        report.candidate_lines.push(format!(
            "SIX-RUN #{} score={}/6 {} root=0x{:X} spans={:?}",
            rank + 1,
            candidate.score,
            candidate.location,
            candidate.root_addr,
            candidate.spans,
        ));
        for line in &candidate.lines {
            report.candidate_lines.push(line.clone());
        }
    }

    for line in formation_lines.iter().take(MAX_FORMATION_LINES) {
        report.candidate_lines.push(line.clone());
    }
    for line in packed_lines.iter().take(MAX_PACKED_LINES) {
        report.candidate_lines.push(line.clone());
    }

    let mut score = 0u8;
    if report.pointer_candidates > 0 { score += 1; }
    if report.vector_candidates > 0 { score += 1; }
    if report.packed14_candidates > 0 { score += 1; }
    if report.formation_candidates > 0 { score += 1; }
    if report.six_collection_candidates > 0 { score += 1; }
    report.strongest_score = score.min(5);

    // Critical safety gate: v2.9 is still read-only. Even a 6/6 ranked run is
    // structural evidence, not authorisation to mutate FM memory.
    report.ready_for_write = false;
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
        assert_eq!(formation_row_score(&bytes, 4), Some((4, 4, 4)));
    }

    #[test]
    fn stable_signature_has_no_heap_address() {
        assert_eq!(stable_path("team+0x30", 0x18), "team+0x30+0x18");
    }
}
'@
Write-Text $inspector $inspectorCode

# Compact UI wording + render more ranked evidence lines.
Replace-Required 'src/ui/club_panel.rs' 'v2.8 • LIVE READ-ONLY INSPECTOR' 'v2.9 • CROSS VALIDATOR'
Replace-Required 'src/ui/club_panel.rs' 'Run the inspector against the current FM27 process. It scans bounded heap roots from the validated Senior Team object and reports structural candidates; it performs zero writes.' 'Ranks six-vector runs first, emits stable path signatures and bounded per-vector dumps, then shows formation +14 and packed14 evidence. Zero writes.'
Replace-Required 'src/ui/club_panel.rs' 'Run Live Inspector' 'Run Cross Validator'
Replace-Required 'src/ui/club_panel.rs' 'for line in r.candidate_lines.iter().take(10)' 'for line in r.candidate_lines.iter().take(18)'

Write-Host 'Element v2.9 Tactical Knowledge cross validator applied successfully.'
