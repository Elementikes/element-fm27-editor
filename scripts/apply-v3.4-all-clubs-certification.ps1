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
    if (-not $Text.Contains($Old)) { throw "v3.4: expected text not found in $RelativePath`n--- expected ---`n$Old" }
    Write-Text $RelativePath ($Text.Replace($Old, $New))
}

# -----------------------------------------------------------------------------
# Element v3.4 — ALL CLUBS TACTICAL MAPPING CERTIFICATION
#
# v3.3 found the same descriptor family across unrelated clubs. v3.4 measures
# coverage across the complete FM club array automatically. Fast path checks the
# now-observed canonical family:
#   Senior Team +0x30 -> root, collections at root +0x18 + n*0x170
# The canonical shape is treated as a discovered hypothesis, not club-specific
# logic. Any club that does not certify on the fast path falls back to the fully
# structural v3.3 descriptor resolver. ZERO writes.
# -----------------------------------------------------------------------------

$inspector = 'src/bridge/tactical_inspector.rs'
$text = Read-Text $inspector
if (-not $text.Contains('pub(super) fn descriptor_map(')) {
    throw 'v3.4: v3.3 descriptor resolver source not found; refusing to certify an unknown layout'
}

# HashMap is used only for alternate-layout signature counts.
$text = $text.Replace('use std::collections::HashSet;', 'use std::collections::{HashMap, HashSet};')

if (-not $text.Contains('pub(super) fn certify_all_clubs(')) {
    $markers = @(
        "#[cfg(test)]`nmod element_descriptor_resolver_tests",
        "#[cfg(test)]`r`nmod element_descriptor_resolver_tests"
    )
    $at = -1
    foreach ($marker in $markers) {
        $at = $text.IndexOf($marker)
        if ($at -ge 0) { break }
    }
    if ($at -lt 0) { throw 'v3.4: v3.3 descriptor test boundary not found' }

    $certCode = @'
const ELEMENT_CERT_CANONICAL_ROOT_OFF: u64 = 0x30;
const ELEMENT_CERT_CANONICAL_BASE: usize = 0x18;
const ELEMENT_CERT_CANONICAL_STEP: usize = 0x170;
const ELEMENT_CERT_CANONICAL_ROOT_BYTES: usize = 0x800;
const ELEMENT_CERT_MAX_EXCEPTION_LINES: usize = 8;

#[derive(Clone, Copy, Debug, Default)]
struct CanonicalCertification {
    populated: usize,
    empty: usize,
    unallocated: usize,
    invalid: usize,
    semantic: usize,
}

impl CanonicalCertification {
    fn resolved(self) -> usize {
        self.populated + self.empty + self.unallocated
    }

    fn structure_complete(self) -> bool {
        self.resolved() == 6 && self.invalid == 0
    }

    fn semantic_certified(self) -> bool {
        self.structure_complete() && self.populated > 0 && self.semantic > 0
    }

    fn uninitialized(self) -> bool {
        self.structure_complete() && self.populated == 0
    }
}

#[derive(Clone, Debug, Default)]
struct AllClubCertificationStats {
    array_entries: usize,
    valid_club_ptrs: usize,
    searchable_clubs: usize,
    senior_teams: usize,
    no_senior_team: usize,
    canonical_full: usize,
    canonical_partial: usize,
    canonical_uninitialized: usize,
    canonical_weak: usize,
    fallback_certified: usize,
    no_family: usize,
    read_errors: usize,
    invalid_club_ptrs: usize,
}

fn certification_pct(num: usize, den: usize) -> usize {
    if den == 0 { 0 } else { num.saturating_mul(100) / den }
}

fn certification_club_uid(fm: &FmProcess, club_addr: u64, uid_off: Option<usize>) -> u32 {
    uid_off
        .and_then(|off| fm.read_u32(club_addr + off as u64).ok())
        .unwrap_or(0)
}

fn certification_is_searchable_club(
    fm: &FmProcess,
    club_addr: u64,
    name_off: Option<usize>,
    full_name_off: Option<usize>,
) -> bool {
    let ptr_at = |off: Option<usize>| -> u64 {
        off.and_then(|o| fm.read_u64(club_addr + o as u64).ok()).unwrap_or(0)
    };
    let short = ptr_at(name_off);
    let full = ptr_at(full_name_off);
    valid_ptr(short) || valid_ptr(full)
}

fn certify_canonical_team(
    fm: &FmProcess,
    senior_team_addr: u64,
) -> Result<Option<CanonicalCertification>, String> {
    let root_addr = fm
        .read_u64(senior_team_addr + ELEMENT_CERT_CANONICAL_ROOT_OFF)
        .map_err(|e| format!("cannot read Senior Team +0x30 root: {e}"))?;
    if !valid_ptr(root_addr) || (fm.gp_base..fm.gp_end).contains(&root_addr) {
        return Ok(None);
    }

    let root = fm
        .read_bytes(root_addr, ELEMENT_CERT_CANONICAL_ROOT_BYTES)
        .map_err(|e| format!("cannot read canonical tactical root 0x{root_addr:X}: {e}"))?;

    let mut out = CanonicalCertification::default();
    for n in 0..6usize {
        let off = ELEMENT_CERT_CANONICAL_BASE + n * ELEMENT_CERT_CANONICAL_STEP;
        let desc = raw_descriptor_at(&root, off);
        match desc.state {
            DescriptorState::Populated => {
                out.populated += 1;
                let v = structural_vector_from_desc(fm, off, desc);
                if v.semantic_ok { out.semantic += 1; }
            }
            DescriptorState::Empty => out.empty += 1,
            DescriptorState::Unallocated => out.unallocated += 1,
            DescriptorState::Invalid => out.invalid += 1,
        }
    }
    Ok(Some(out))
}

fn certify_fallback_team(
    fm: &FmProcess,
    senior_team_addr: u64,
) -> Result<Option<(String, DescriptorFamily)>, String> {
    let contexts = descriptor_contexts(fm, senior_team_addr)?;
    let Some(family) = descriptor_best_family(fm, &contexts) else {
        return Ok(None);
    };
    let resolved = family.populated + family.empty + family.unallocated;
    let certified = resolved >= 5
        && family.invalid <= 1
        && family.populated >= 2
        && family.semantic_members >= 1;
    if !certified { return Ok(None); }
    let label = contexts
        .get(family.context_index)
        .map(|c| c.label.clone())
        .unwrap_or_else(|| "unknown-context".to_owned());
    Ok(Some((label, family)))
}

pub(super) fn certify_all_clubs(
    fm: &FmProcess,
    selected_club_addr: u64,
    selected_senior_team_addr: u64,
) -> Result<TacticalInspectorReport, String> {
    let (clubs_data, _clubs_end, clubs_count) = crate::club::clubs_array(fm)?;
    let schema = fm.schemas();
    let club_sub_records = schema.club_sub_records;
    let uid_off = schema.offset_of("c_uid");
    let name_off = schema.offset_of("c_name");
    let full_name_off = schema.offset_of("c_full_name");

    let mut stats = AllClubCertificationStats {
        array_entries: clubs_count,
        ..Default::default()
    };
    let mut alternate_signatures: HashMap<String, usize> = HashMap::new();
    let mut exceptions = Vec::new();

    for index in 0..clubs_count {
        let club_addr = match fm.read_u64(clubs_data + index as u64 * 8) {
            Ok(ptr) if valid_ptr(ptr) => ptr,
            Ok(_) => {
                stats.invalid_club_ptrs += 1;
                continue;
            }
            Err(_) => {
                stats.invalid_club_ptrs += 1;
                stats.read_errors += 1;
                continue;
            }
        };
        stats.valid_club_ptrs += 1;

        // Match EntityCache semantics: nameless placeholder objects are not
        // searchable clubs and should not dilute mapping coverage.
        if !certification_is_searchable_club(fm, club_addr, name_off, full_name_off) {
            continue;
        }
        stats.searchable_clubs += 1;
        let uid = certification_club_uid(fm, club_addr, uid_off);

        let Some(senior_team_addr) = crate::fields::resolve_sub_ptr(
            fm,
            club_addr,
            "senior_team",
            club_sub_records,
        ) else {
            stats.no_senior_team += 1;
            continue;
        };
        if !valid_ptr(senior_team_addr) {
            stats.no_senior_team += 1;
            continue;
        }
        stats.senior_teams += 1;

        let canonical = match certify_canonical_team(fm, senior_team_addr) {
            Ok(v) => v,
            Err(e) => {
                stats.read_errors += 1;
                if exceptions.len() < ELEMENT_CERT_MAX_EXCEPTION_LINES {
                    exceptions.push(format!("EXCEPTION idx={index} uid={uid}: canonical read error: {e}"));
                }
                None
            }
        };

        if let Some(c) = canonical {
            if c.semantic_certified() {
                if c.populated == 6 {
                    stats.canonical_full += 1;
                } else {
                    stats.canonical_partial += 1;
                }
                continue;
            }
            if c.uninitialized() {
                stats.canonical_uninitialized += 1;
                continue;
            }
            if c.structure_complete() {
                stats.canonical_weak += 1;
            }
        }

        // Only exceptional clubs pay the cost of the full descriptor-first
        // scan. This keeps a 20k+ club certification practical while still
        // discovering alternate layouts rather than treating them as failures.
        match certify_fallback_team(fm, senior_team_addr) {
            Ok(Some((label, family))) => {
                stats.fallback_certified += 1;
                let signature = format!(
                    "{} / base=+0x{:X} / step=0x{:X}",
                    label, family.base, family.step,
                );
                *alternate_signatures.entry(signature).or_insert(0) += 1;
            }
            Ok(None) => {
                stats.no_family += 1;
                if exceptions.len() < ELEMENT_CERT_MAX_EXCEPTION_LINES {
                    exceptions.push(format!("EXCEPTION idx={index} uid={uid}: no certified descriptor family"));
                }
            }
            Err(e) => {
                stats.no_family += 1;
                stats.read_errors += 1;
                if exceptions.len() < ELEMENT_CERT_MAX_EXCEPTION_LINES {
                    exceptions.push(format!("EXCEPTION idx={index} uid={uid}: fallback read error: {e}"));
                }
            }
        }
    }

    let canonical_certified = stats.canonical_full + stats.canonical_partial;
    let semantic_certified = canonical_certified + stats.fallback_certified;
    let structural_recognized = semantic_certified + stats.canonical_uninitialized;
    let semantic_pct = certification_pct(semantic_certified, stats.senior_teams);
    let structural_pct = certification_pct(structural_recognized, stats.senior_teams);

    let mut alt: Vec<(String, usize)> = alternate_signatures.into_iter().collect();
    alt.sort_by(|a, b| b.1.cmp(&a.1).then_with(|| a.0.cmp(&b.0)));

    let mut lines = Vec::new();
    lines.push("ALL CLUBS CERTIFICATION v3.4: complete club-array scan • canonical fast path + descriptor-first fallback • ZERO WRITES".to_owned());
    lines.push(format!(
        "SCOPE: array_entries={} valid_ptrs={} searchable_clubs={} senior_team={} no_senior_team={} invalid_ptrs={}",
        stats.array_entries,
        stats.valid_club_ptrs,
        stats.searchable_clubs,
        stats.senior_teams,
        stats.no_senior_team,
        stats.invalid_club_ptrs,
    ));
    lines.push(format!(
        "CANONICAL SIGNATURE: SeniorTeam+0x30 -> root / collections base=+0x18 step=0x170 • full6={} partial={} uninitialized={} weak={}",
        stats.canonical_full,
        stats.canonical_partial,
        stats.canonical_uninitialized,
        stats.canonical_weak,
    ));
    lines.push(format!(
        "FALLBACK: alternate_certified={} no_family={} read_errors={}",
        stats.fallback_certified,
        stats.no_family,
        stats.read_errors,
    ));
    lines.push(format!(
        "COVERAGE: semantic_certified={}/{} ({}%) structural_recognized={}/{} ({}%)",
        semantic_certified,
        stats.senior_teams,
        semantic_pct,
        structural_recognized,
        stats.senior_teams,
        structural_pct,
    ));
    lines.push(format!(
        "CERTIFICATION VERDICT: {} • write path remains LOCKED",
        if semantic_pct >= 99 && stats.no_family == 0 {
            "FM27 UNIVERSAL MAPPING CANDIDATE"
        } else if semantic_pct >= 95 {
            "VERY HIGH COVERAGE — REVIEW EXCEPTIONS"
        } else if semantic_pct >= 80 {
            "HIGH COVERAGE — ALTERNATE LAYOUTS REMAIN"
        } else {
            "MORE LAYOUT WORK REQUIRED"
        }
    ));

    for (signature, count) in alt.into_iter().take(5) {
        lines.push(format!("ALTERNATE SIGNATURE x{count}: {signature}"));
    }
    lines.extend(exceptions);

    let confidence = if semantic_pct >= 99 { 5 }
        else if semantic_pct >= 95 { 4 }
        else if semantic_pct >= 80 { 3 }
        else if semantic_pct >= 50 { 2 }
        else { 1 };

    Ok(TacticalInspectorReport {
        club_addr: selected_club_addr,
        senior_team_addr: selected_senior_team_addr,
        scanned_roots: stats.searchable_clubs,
        pointer_candidates: stats.senior_teams,
        vector_candidates: semantic_certified,
        six_collection_candidates: canonical_certified,
        formation_candidates: stats.no_family,
        packed14_candidates: stats.fallback_certified,
        read_errors: stats.read_errors,
        strongest_score: confidence,
        candidate_lines: lines,
        ready_for_write: false,
    })
}

#[cfg(test)]
mod element_all_clubs_certification_tests {
    use super::{certification_pct, CanonicalCertification};

    #[test]
    fn certification_percentage_is_integer_and_safe() {
        assert_eq!(certification_pct(999, 1000), 99);
        assert_eq!(certification_pct(1, 0), 0);
    }

    #[test]
    fn canonical_partial_family_can_be_semantically_certified() {
        let c = CanonicalCertification {
            populated: 4,
            empty: 1,
            unallocated: 1,
            invalid: 0,
            semantic: 4,
        };
        assert!(c.structure_complete());
        assert!(c.semantic_certified());
        assert!(!c.uninitialized());
    }

    #[test]
    fn all_unallocated_is_recognized_but_not_semantically_certified() {
        let c = CanonicalCertification {
            populated: 0,
            empty: 0,
            unallocated: 6,
            invalid: 0,
            semantic: 0,
        };
        assert!(c.structure_complete());
        assert!(!c.semantic_certified());
        assert!(c.uninitialized());
    }
}

'@

    $text = $text.Substring(0, $at) + $certCode + $text.Substring($at)
    Write-Text $inspector $text
}

# Existing inspector protocol is enough: the selected club is only the UI/result
# routing anchor; the v3.4 implementation scans the complete club array.
Replace-Required 'src/bridge/worker.rs' '                    Some(f) => tactical_inspector::descriptor_map(f, club_addr, senior_team_addr),' '                    Some(f) => tactical_inspector::certify_all_clubs(f, club_addr, senior_team_addr),'

# UI wording and global certification summary.
Replace-Required 'src/ui/club_panel.rs' 'v3.3 • UNIVERSAL DESCRIPTOR RESOLVER' 'v3.4 • ALL CLUBS CERTIFICATION'
Replace-Required 'src/ui/club_panel.rs' 'Discovers vector descriptors structurally from Senior Team and bounded one-hop roots. EMPTY and UNALLOCATED collections are valid states; semantic values only add confidence. No club names, fixed spans, base or step. Zero writes.' 'Scans the complete FM27 club array. Uses the discovered canonical family as a fast certification path and runs the descriptor-first resolver only on exceptions. Reports real mapping coverage across all clubs. Zero writes.'
Replace-Required 'src/ui/club_panel.rs' 'Run Descriptor Resolver' 'Certify All Clubs'
Replace-Required 'src/ui/club_panel.rs' 'Read-only • descriptor-first universal discovery • zero writes' 'Read-only • complete club-array certification • zero writes'
Replace-Required 'src/ui/club_panel.rs' 'DESCRIPTOR RESOLVER • FULL 100% WRITE STILL LOCKED' 'ALL CLUBS CERTIFICATION • FULL 100% WRITE STILL LOCKED'
Replace-Required 'src/ui/club_panel.rs' 'Candidate confidence:' 'Certification confidence:'
Replace-Required 'src/ui/club_panel.rs' '"Roots scanned"' '"Clubs scanned"'
Replace-Required 'src/ui/club_panel.rs' '"Pointers"' '"Senior teams"'
Replace-Required 'src/ui/club_panel.rs' '"Vectors"' '"Certified"'
Replace-Required 'src/ui/club_panel.rs' '"Six-runs"' '"Canonical"'
Replace-Required 'src/ui/club_panel.rs' '"Packed14"' '"Fallback"'
Replace-Required 'src/ui/club_panel.rs' '"Formation +14"' '"No family"'

# Give the certification report enough vertical evidence lines for coverage,
# alternate signatures and the first few exceptions.
$text = Read-Text 'src/ui/club_panel.rs'
$text = $text.Replace('r.candidate_lines.iter().take(18)', 'r.candidate_lines.iter().take(24)')
$text = $text.Replace('r.candidate_lines.iter().take(10)', 'r.candidate_lines.iter().take(24)')
Write-Text 'src/ui/club_panel.rs' $text

# Status bar wording uses the same report fields, now repurposed as coverage.
Replace-Required 'src/app.rs' '"Tactical inspector: confidence {}/5, {} vectors, {} six-runs, {} formation candidates"' '"All-clubs tactical certification: confidence {}/5, {} certified, {} canonical, {} no-family"'
Replace-Required 'src/app.rs' '"Tactical inspector running read-only scan…"' '"All-clubs tactical certification running read-only…"'

Write-Host 'Element v3.4 all-clubs tactical certification scanner applied successfully.'
