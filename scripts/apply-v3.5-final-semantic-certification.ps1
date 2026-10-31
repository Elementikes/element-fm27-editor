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
    if (-not $Text.Contains($Old)) { throw "v3.5: expected text not found in $RelativePath`n--- expected ---`n$Old" }
    Write-Text $RelativePath ($Text.Replace($Old, $New))
}

# -----------------------------------------------------------------------------
# Element v3.5 — FINAL TACTICAL SEMANTIC CERTIFICATION
#
# v3.4 proved 100% canonical layout coverage on the current FM27 save. v3.5
# remains strictly read-only and validates the record semantics across the whole
# club array: stride=8, key candidate @+0, packed low14 knowledge candidate @+2,
# metadata candidate @+4. It reports global distributions and snapshot hashes.
# ZERO writes and no write payload generation.
# -----------------------------------------------------------------------------

$inspector = 'src/bridge/tactical_inspector.rs'
$text = Read-Text $inspector
if (-not $text.Contains('pub(super) fn certify_all_clubs(')) {
    throw 'v3.5: v3.4 all-clubs certification source not found'
}

if (-not $text.Contains('pub(super) fn certify_semantic_slots_all_clubs(')) {
    $markers = @(
        "#[cfg(test)]`nmod element_all_clubs_certification_tests",
        "#[cfg(test)]`r`nmod element_all_clubs_certification_tests"
    )
    $at = -1
    foreach ($marker in $markers) {
        $at = $text.IndexOf($marker)
        if ($at -ge 0) { break }
    }
    if ($at -lt 0) { throw 'v3.5: v3.4 certification test boundary not found' }

    $code = @'
const ELEMENT_SEMANTIC_CERT_LOW14_MASK: u16 = 0x3FFF;
const ELEMENT_SEMANTIC_CERT_MAX: u16 = 10_000;
const ELEMENT_SEMANTIC_CERT_META271: u32 = 0x0000_0271;
const ELEMENT_SEMANTIC_CERT_FNV_OFFSET: u64 = 0xcbf29ce484222325;
const ELEMENT_SEMANTIC_CERT_FNV_PRIME: u64 = 0x100000001b3;
const ELEMENT_SEMANTIC_CERT_MAX_SAMPLES: usize = 8;

#[derive(Clone, Debug, Default)]
struct SemanticCertStats {
    searchable_clubs: usize,
    senior_teams: usize,
    certified_teams: usize,
    invalid_teams: usize,
    populated_vectors: usize,
    empty_vectors: usize,
    unallocated_vectors: usize,
    invalid_vectors: usize,
    records: usize,
    low14_valid: usize,
    low14_out_of_range: usize,
    low14_zero: usize,
    low14_max: usize,
    flagged_values: usize,
    zero_keys: usize,
    metadata271: usize,
    metadata_other: usize,
    bad_stride: usize,
    read_errors: usize,
    low14_sum: u64,
}

fn semantic_cert_read_u16(buf: &[u8], off: usize) -> Option<u16> {
    let b = buf.get(off..off + 2)?;
    Some(u16::from_le_bytes([b[0], b[1]]))
}

fn semantic_cert_read_u32(buf: &[u8], off: usize) -> Option<u32> {
    let b = buf.get(off..off + 4)?;
    Some(u32::from_le_bytes([b[0], b[1], b[2], b[3]]))
}

fn semantic_cert_hash(mut hash: u64, bytes: &[u8]) -> u64 {
    for b in bytes {
        hash ^= *b as u64;
        hash = hash.wrapping_mul(ELEMENT_SEMANTIC_CERT_FNV_PRIME);
    }
    hash
}

pub(super) fn certify_semantic_slots_all_clubs(
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

    let mut stats = SemanticCertStats::default();
    let mut low14_values: HashSet<u16> = HashSet::new();
    let mut metadata_values: HashSet<u32> = HashSet::new();
    let mut snapshot_hash = ELEMENT_SEMANTIC_CERT_FNV_OFFSET;
    let mut samples = Vec::new();

    for index in 0..clubs_count {
        let club_addr = match fm.read_u64(clubs_data + index as u64 * 8) {
            Ok(ptr) if valid_ptr(ptr) => ptr,
            Ok(_) => continue,
            Err(_) => { stats.read_errors += 1; continue; }
        };
        if !certification_is_searchable_club(fm, club_addr, name_off, full_name_off) {
            continue;
        }
        stats.searchable_clubs += 1;
        let uid = certification_club_uid(fm, club_addr, uid_off);
        let Some(team) = crate::fields::resolve_sub_ptr(fm, club_addr, "senior_team", club_sub_records) else {
            continue;
        };
        if !valid_ptr(team) { continue; }
        stats.senior_teams += 1;

        let root_addr = match fm.read_u64(team + ELEMENT_CERT_CANONICAL_ROOT_OFF) {
            Ok(v) if valid_ptr(v) && !(fm.gp_base..fm.gp_end).contains(&v) => v,
            _ => { stats.invalid_teams += 1; continue; }
        };
        let root = match fm.read_bytes(root_addr, ELEMENT_CERT_CANONICAL_ROOT_BYTES) {
            Ok(v) => v,
            Err(_) => { stats.invalid_teams += 1; stats.read_errors += 1; continue; }
        };

        let before_bad = stats.bad_stride + stats.read_errors + stats.low14_out_of_range + stats.invalid_vectors;
        let mut populated_here = 0usize;
        for collection in 0..6usize {
            let desc_off = ELEMENT_CERT_CANONICAL_BASE + collection * ELEMENT_CERT_CANONICAL_STEP;
            let desc = raw_descriptor_at(&root, desc_off);
            match desc.state {
                DescriptorState::Populated => {
                    stats.populated_vectors += 1;
                    populated_here += 1;
                    if desc.span == 0 || desc.span % ELEMENT_SEMANTIC_STRIDE != 0 {
                        stats.bad_stride += 1;
                        continue;
                    }
                    let bytes = match fm.read_bytes(desc.data, desc.span) {
                        Ok(v) => v,
                        Err(_) => { stats.read_errors += 1; continue; }
                    };
                    snapshot_hash = semantic_cert_hash(snapshot_hash, &uid.to_le_bytes());
                    snapshot_hash = semantic_cert_hash(snapshot_hash, &[(collection + 1) as u8]);
                    snapshot_hash = semantic_cert_hash(snapshot_hash, &bytes);

                    let records = bytes.len() / ELEMENT_SEMANTIC_STRIDE;
                    stats.records += records;
                    for record in 0..records {
                        let off = record * ELEMENT_SEMANTIC_STRIDE;
                        let Some(key) = semantic_cert_read_u16(&bytes, off) else { stats.read_errors += 1; continue; };
                        let Some(raw2) = semantic_cert_read_u16(&bytes, off + 2) else { stats.read_errors += 1; continue; };
                        let Some(meta4) = semantic_cert_read_u32(&bytes, off + 4) else { stats.read_errors += 1; continue; };
                        let low14 = raw2 & ELEMENT_SEMANTIC_CERT_LOW14_MASK;
                        low14_values.insert(low14);
                        metadata_values.insert(meta4);
                        stats.low14_sum = stats.low14_sum.saturating_add(low14 as u64);
                        if low14 <= ELEMENT_SEMANTIC_CERT_MAX {
                            stats.low14_valid += 1;
                            if low14 == 0 { stats.low14_zero += 1; }
                            if low14 == ELEMENT_SEMANTIC_CERT_MAX { stats.low14_max += 1; }
                        } else {
                            stats.low14_out_of_range += 1;
                        }
                        if raw2 & 0xC000 != 0 { stats.flagged_values += 1; }
                        if key == 0 { stats.zero_keys += 1; }
                        if meta4 == ELEMENT_SEMANTIC_CERT_META271 {
                            stats.metadata271 += 1;
                        } else {
                            stats.metadata_other += 1;
                        }
                        if club_addr == selected_club_addr && samples.len() < ELEMENT_SEMANTIC_CERT_MAX_SAMPLES {
                            samples.push(format!(
                                "SAMPLE uid={uid} C{} R{} key=0x{key:04X} +2raw=0x{raw2:04X} low14={} +4=0x{meta4:08X}",
                                collection + 1,
                                record,
                                low14,
                            ));
                        }
                    }
                }
                DescriptorState::Empty => stats.empty_vectors += 1,
                DescriptorState::Unallocated => stats.unallocated_vectors += 1,
                DescriptorState::Invalid => stats.invalid_vectors += 1,
            }
        }
        let after_bad = stats.bad_stride + stats.read_errors + stats.low14_out_of_range + stats.invalid_vectors;
        if populated_here > 0 && after_bad == before_bad {
            stats.certified_teams += 1;
        } else {
            stats.invalid_teams += 1;
        }
    }

    let coverage = certification_pct(stats.certified_teams, stats.senior_teams);
    let metadata_total = stats.metadata271 + stats.metadata_other;
    let metadata_pct = certification_pct(stats.metadata271, metadata_total);
    let low14_pct = certification_pct(stats.low14_valid, stats.records);
    let average = if stats.records == 0 { 0 } else { stats.low14_sum / stats.records as u64 };
    let slot_separation = low14_values.len() >= 8 && low14_values.len() > metadata_values.len();
    let semantic_certified = coverage == 100
        && low14_pct == 100
        && stats.low14_out_of_range == 0
        && stats.bad_stride == 0
        && stats.invalid_vectors == 0
        && stats.read_errors == 0
        && metadata_pct >= 95
        && slot_separation;

    let mut lines = Vec::new();
    lines.push("FINAL SEMANTIC CERTIFICATION v3.5: whole-save slot validation • ZERO WRITES".to_owned());
    lines.push(format!(
        "SCOPE: searchable_clubs={} senior_teams={} certified_teams={} invalid_teams={}",
        stats.searchable_clubs, stats.senior_teams, stats.certified_teams, stats.invalid_teams,
    ));
    lines.push("FORMAT: stride=8 • key candidate @+0 • knowledge candidate @+2 low14 • metadata candidate @+4".to_owned());
    lines.push(format!(
        "VECTOR STATES: populated={} empty={} unallocated={} invalid={}",
        stats.populated_vectors, stats.empty_vectors, stats.unallocated_vectors, stats.invalid_vectors,
    ));
    lines.push(format!(
        "KNOWLEDGE +2: valid={}/{} ({}%) out_of_range={} unique={} zero={} max10000={} avg={}",
        stats.low14_valid, stats.records, low14_pct, stats.low14_out_of_range, low14_values.len(), stats.low14_zero, stats.low14_max, average,
    ));
    lines.push(format!(
        "METADATA +4: 0x271={}/{} ({}%) other={} unique={} • slot_separation={}",
        stats.metadata271, metadata_total, metadata_pct, stats.metadata_other, metadata_values.len(), slot_separation,
    ));
    lines.push(format!(
        "INVARIANTS: flagged_highbits={} zero_keys={} bad_stride={} read_errors={} snapshot_hash=0x{snapshot_hash:016X}",
        stats.flagged_values, stats.zero_keys, stats.bad_stride, stats.read_errors,
    ));
    lines.push(format!(
        "SEMANTIC COVERAGE: {}/{} teams ({}%)",
        stats.certified_teams, stats.senior_teams, coverage,
    ));
    lines.push(format!(
        "SEMANTIC VERDICT: {} • execution remains LOCKED",
        if semantic_certified {
            "CERTIFIED — +2 behaves as the portable tactical-knowledge slot and +4 as metadata"
        } else if coverage >= 99 && low14_pct == 100 {
            "NEAR-CERTIFIED — review metadata/slot-separation evidence"
        } else {
            "NOT CERTIFIED — review integrity counters"
        }
    ));
    lines.extend(samples);

    let confidence = if semantic_certified { 5 }
        else if coverage >= 99 && low14_pct == 100 { 4 }
        else if coverage >= 95 { 3 }
        else if coverage >= 80 { 2 }
        else { 1 };

    Ok(TacticalInspectorReport {
        club_addr: selected_club_addr,
        senior_team_addr: selected_senior_team_addr,
        scanned_roots: stats.searchable_clubs,
        pointer_candidates: stats.senior_teams,
        vector_candidates: stats.certified_teams,
        six_collection_candidates: stats.populated_vectors,
        formation_candidates: stats.low14_out_of_range,
        packed14_candidates: stats.metadata_other,
        read_errors: stats.read_errors + stats.bad_stride,
        strongest_score: confidence,
        candidate_lines: lines,
        ready_for_write: false,
    })
}

#[cfg(test)]
mod element_final_semantic_cert_tests {
    use super::{semantic_cert_hash, ELEMENT_SEMANTIC_CERT_FNV_OFFSET, ELEMENT_SEMANTIC_CERT_LOW14_MASK};

    #[test]
    fn low14_extracts_known_candidate_value() {
        assert_eq!(0xC95Du16 & ELEMENT_SEMANTIC_CERT_LOW14_MASK, 2397);
    }

    #[test]
    fn snapshot_hash_is_deterministic() {
        let a = semantic_cert_hash(ELEMENT_SEMANTIC_CERT_FNV_OFFSET, &[1, 2, 3, 4]);
        let b = semantic_cert_hash(ELEMENT_SEMANTIC_CERT_FNV_OFFSET, &[1, 2, 3, 4]);
        let c = semantic_cert_hash(ELEMENT_SEMANTIC_CERT_FNV_OFFSET, &[1, 2, 3, 5]);
        assert_eq!(a, b);
        assert_ne!(a, c);
    }
}

'@

    $text = $text.Substring(0, $at) + $code + $text.Substring($at)
    Write-Text $inspector $text
}

Replace-Required 'src/bridge/worker.rs' '                    Some(f) => tactical_inspector::certify_all_clubs(f, club_addr, senior_team_addr),' '                    Some(f) => tactical_inspector::certify_semantic_slots_all_clubs(f, club_addr, senior_team_addr),'

Replace-Required 'src/ui/club_panel.rs' 'v3.4 • ALL CLUBS CERTIFICATION' 'v3.5 • FINAL SEMANTIC CERTIFICATION'
Replace-Required 'src/ui/club_panel.rs' 'Scans the complete FM27 club array. Uses the discovered canonical family as a fast certification path and runs the descriptor-first resolver only on exceptions. Reports real mapping coverage across all clubs. Zero writes.' 'Validates the tactical record semantics across the complete FM27 club array: stride 8, key candidate +0, low14 knowledge candidate +2, metadata candidate +4, global distributions and snapshot hash. Zero writes.'
Replace-Required 'src/ui/club_panel.rs' 'Certify All Clubs' 'Certify Semantic Slots'
Replace-Required 'src/ui/club_panel.rs' 'Read-only • complete club-array certification • zero writes' 'Read-only • whole-save semantic slot certification • zero writes'
Replace-Required 'src/ui/club_panel.rs' 'ALL CLUBS CERTIFICATION • FULL 100% WRITE STILL LOCKED' 'FINAL SEMANTIC CERTIFICATION • EXECUTION STILL LOCKED'
Replace-Required 'src/ui/club_panel.rs' '"Certified"' '"Semantic teams"'
Replace-Required 'src/ui/club_panel.rs' '"Canonical"' '"Pop. vectors"'
Replace-Required 'src/ui/club_panel.rs' '"Fallback"' '"Meta other"'
Replace-Required 'src/ui/club_panel.rs' '"No family"' '"Out of range"'

Replace-Required 'src/app.rs' '"All-clubs tactical certification: confidence {}/5, {} certified, {} canonical, {} no-family"' '"Tactical semantic certification: confidence {}/5, {} semantic teams, {} populated vectors, {} out-of-range"'
Replace-Required 'src/app.rs' '"All-clubs tactical certification running read-only…"' '"Tactical semantic certification running read-only…"'

$ui = Read-Text 'src/ui/club_panel.rs'
$ui = $ui.Replace(
    'Next gate: prove which candidate belongs to the player-training object, verify instruction keys/ownership across multiple players, identify the knowledge-cache refresh field, then enable an all-or-nothing Undo-backed batch.',
    'Next gate after a clean v3.5 report: keep execution locked until a separately validated transactional write/read-back/rollback mechanism exists.'
)
Write-Text 'src/ui/club_panel.rs' $ui

Write-Host 'Element v3.5 final tactical semantic certification applied successfully.'