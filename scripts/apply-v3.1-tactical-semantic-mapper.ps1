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
    if (-not $Text.Contains($Old)) { throw "v3.1: expected text not found in $RelativePath`n--- expected ---`n$Old" }
    Write-Text $RelativePath ($Text.Replace($Old, $New))
}

# -----------------------------------------------------------------------------
# Element v3.1 — TACTICAL KNOWLEDGE SEMANTIC MAPPER
#
# Read-only semantic pass over the exact v3.0 validated candidate:
#   senior_team +0x30 -> heap object +0x18 -> six adjacent vector descriptors
#   spans [16, 8, 832, 128, 248, 136]
#
# All six spans are divisible by 8, yielding 2/1/104/16/31/17 records. This pass
# evaluates u16 slots +0/+2/+4/+6 across all 8-byte records, treats +2 as the
# current knowledge hypothesis from the v3.0 probe, emits key/value/tail samples,
# key-set fingerprints and collection statistics. ZERO writes.
# -----------------------------------------------------------------------------

$inspector = 'src/bridge/tactical_inspector.rs'
$text = Read-Text $inspector
if (-not $text.Contains('pub(super) fn probe_plan(')) {
    throw 'v3.1: v3.0 probe_plan source not found; refusing to map an unknown layout'
}

if (-not $text.Contains('pub(super) fn semantic_map(')) {
    $marker = '#[cfg(test)]`nmod element_probe_plan_tests'
    $at = $text.IndexOf($marker)
    if ($at -lt 0) {
        $marker = "#[cfg(test)]`r`nmod element_probe_plan_tests"
        $at = $text.IndexOf($marker)
    }
    if ($at -lt 0) { throw 'v3.1: v3.0 test boundary not found' }

    $semanticCode = @'
const ELEMENT_SEMANTIC_STRIDE: usize = 8;
const ELEMENT_SEMANTIC_VALUE_OFFSET: usize = 2;

fn semantic_u16(bytes: &[u8], off: usize) -> Option<u16> {
    Some(u16::from_le_bytes(bytes.get(off..off + 2)?.try_into().ok()?))
}

fn semantic_u32(bytes: &[u8], off: usize) -> Option<u32> {
    Some(u32::from_le_bytes(bytes.get(off..off + 4)?.try_into().ok()?))
}

#[derive(Clone, Copy, Debug, Default)]
struct SemanticOffsetStats {
    records: usize,
    plausible: usize,
    positive: usize,
    full: usize,
    zero: usize,
    flagged: usize,
}

fn semantic_offset_stats(bytes: &[u8], offset: usize) -> SemanticOffsetStats {
    let mut stats = SemanticOffsetStats::default();
    for record in bytes.chunks_exact(ELEMENT_SEMANTIC_STRIDE) {
        let Some(raw) = semantic_u16(record, offset) else { continue };
        let value = raw & 0x3FFF;
        stats.records += 1;
        if value <= 10_000 {
            stats.plausible += 1;
            if value == 0 { stats.zero += 1; }
            if value > 0 { stats.positive += 1; }
            if value == 10_000 { stats.full += 1; }
        }
        if raw & 0xC000 != 0 { stats.flagged += 1; }
    }
    stats
}

fn semantic_score(stats: SemanticOffsetStats) -> usize {
    if stats.records == 0 { return 0; }
    stats.plausible * 1000
        + stats.positive * 20
        + stats.full * 5
        + stats.flagged
        - stats.zero.min(stats.positive) * 2
}

fn semantic_pct(num: usize, den: usize) -> usize {
    if den == 0 { 0 } else { num * 100 / den }
}

fn semantic_fnv1a(mut hash: u64, bytes: &[u8]) -> u64 {
    for byte in bytes {
        hash ^= *byte as u64;
        hash = hash.wrapping_mul(0x100000001B3);
    }
    hash
}

fn semantic_sample(bytes: &[u8], max_records: usize) -> String {
    let mut out = Vec::new();
    for (index, record) in bytes.chunks_exact(ELEMENT_SEMANTIC_STRIDE).take(max_records).enumerate() {
        let key = semantic_u16(record, 0).unwrap_or(0);
        let raw = semantic_u16(record, 2).unwrap_or(0);
        let value = raw & 0x3FFF;
        let flags = raw >> 14;
        let tail = semantic_u32(record, 4).unwrap_or(0);
        out.push(format!("r{index}:k=0x{key:04X} v={value} f={flags} tail=0x{tail:08X}"));
    }
    out.join(" | ")
}

fn semantic_unique_keys(bytes: &[u8]) -> usize {
    let mut keys = HashSet::new();
    for record in bytes.chunks_exact(ELEMENT_SEMANTIC_STRIDE) {
        if let Some(key) = semantic_u16(record, 0) {
            keys.insert(key);
        }
    }
    keys.len()
}

pub(super) fn semantic_map(
    fm: &FmProcess,
    club_addr: u64,
    senior_team_addr: u64,
) -> Result<TacticalInspectorReport, String> {
    // Keep the complete v3.0 gate/snapshot evidence and v2.9 structural evidence.
    let mut report = probe_plan(fm, club_addr, senior_team_addr)?;
    let mut semantic = Vec::new();
    semantic.push("SEMANTIC MAPPER: stride/key/value inference only • ZERO WRITES • Full 100% remains LOCKED".to_owned());

    let root_ptr_raw = fm
        .read_bytes(senior_team_addr + ELEMENT_PROBE_ROOT_PTR_OFFSET, 8)
        .map_err(|e| format!("semantic mapper cannot read senior_team+0x30 pointer: {e}"))?;
    let root_addr = qword(&root_ptr_raw, 0)
        .ok_or_else(|| "semantic mapper cannot decode senior_team+0x30 pointer".to_owned())?;
    if !valid_ptr(root_addr) {
        semantic.push(format!("SEMANTIC GATE: FAIL invalid team+0x30 root 0x{root_addr:X}"));
        prefix_probe_lines(&mut report, semantic);
        return Ok(report);
    }

    let descriptor_addr = root_addr + ELEMENT_PROBE_VECTOR_RUN_OFFSET;
    let descriptor_bytes = fm
        .read_bytes(descriptor_addr, 6 * 24)
        .map_err(|e| format!("semantic mapper cannot read six-vector descriptor table: {e}"))?;

    let mut descs = Vec::with_capacity(6);
    for i in 0..6 {
        let Some(desc) = vector_desc_at(&descriptor_bytes, i * 24) else {
            semantic.push(format!("SEMANTIC GATE: FAIL V{} descriptor invalid", i + 1));
            prefix_probe_lines(&mut report, semantic);
            return Ok(report);
        };
        descs.push(desc);
    }

    let spans = [
        descs[0].span, descs[1].span, descs[2].span,
        descs[3].span, descs[4].span, descs[5].span,
    ];
    if spans != ELEMENT_PROBE_EXPECTED_SPANS {
        semantic.push(format!("SEMANTIC GATE: FAIL spans={spans:?}; expected {:?}", ELEMENT_PROBE_EXPECTED_SPANS));
        prefix_probe_lines(&mut report, semantic);
        return Ok(report);
    }
    if spans.iter().any(|span| span % ELEMENT_SEMANTIC_STRIDE != 0) {
        semantic.push("SEMANTIC GATE: FAIL one or more collection spans are not divisible by 8".to_owned());
        prefix_probe_lines(&mut report, semantic);
        return Ok(report);
    }

    let counts = [
        spans[0] / 8, spans[1] / 8, spans[2] / 8,
        spans[3] / 8, spans[4] / 8, spans[5] / 8,
    ];
    let total_records: usize = counts.iter().sum();
    semantic.push(format!(
        "SEMANTIC GATE: PASS team+0x30+0x18 • stride=8 • records={counts:?} total={total_records}"
    ));

    let mut buffers = Vec::with_capacity(6);
    for (i, desc) in descs.iter().enumerate() {
        let bytes = fm
            .read_bytes(desc.data, desc.span)
            .map_err(|e| format!("semantic mapper cannot snapshot V{}: {e}", i + 1))?;
        buffers.push(bytes);
    }

    // Aggregate all 8-byte records to compare the four u16 slots as value candidates.
    let mut aggregate = Vec::with_capacity(total_records * ELEMENT_SEMANTIC_STRIDE);
    for bytes in &buffers { aggregate.extend_from_slice(bytes); }
    let offsets = [0usize, 2, 4, 6];
    let stats = offsets.map(|off| semantic_offset_stats(&aggregate, off));
    let scores = stats.map(semantic_score);
    let mut ranked = [(0usize, scores[0]), (2, scores[1]), (4, scores[2]), (6, scores[3])];
    ranked.sort_by_key(|item| Reverse(item.1));

    semantic.push(format!(
        "OFFSET RANK: #1=+{} score={}  #2=+{} score={}  hypothesis=+2",
        ranked[0].0, ranked[0].1, ranked[1].0, ranked[1].1,
    ));
    for (slot, off) in offsets.iter().enumerate() {
        let s = stats[slot];
        semantic.push(format!(
            "OFFSET +{off}: plausible={}/{} ({}%) positive={} zero={} full10000={} flagged={}",
            s.plausible, s.records, semantic_pct(s.plausible, s.records),
            s.positive, s.zero, s.full, s.flagged,
        ));
    }

    // Fingerprint only candidate keys (+0 u16), so repeated scans on other teams can
    // tell us whether the instruction-ID set is structurally stable independent of values.
    let mut key_fp = 0xCBF29CE484222325u64;
    let mut layout_fp = 0xCBF29CE484222325u64;
    for (i, bytes) in buffers.iter().enumerate() {
        key_fp = semantic_fnv1a(key_fp, &[(i + 1) as u8]);
        layout_fp = semantic_fnv1a(layout_fp, &(bytes.len() as u64).to_le_bytes());
        for record in bytes.chunks_exact(ELEMENT_SEMANTIC_STRIDE) {
            key_fp = semantic_fnv1a(key_fp, &record[0..2]);
        }
    }
    semantic.push(format!("FINGERPRINT: keyset=0x{key_fp:016X} layout=0x{layout_fp:016X}"));

    let mut plus2_plausible = 0usize;
    let mut plus2_positive = 0usize;
    let mut total_unique = 0usize;
    for (i, bytes) in buffers.iter().enumerate() {
        let s = semantic_offset_stats(bytes, ELEMENT_SEMANTIC_VALUE_OFFSET);
        let unique = semantic_unique_keys(bytes);
        total_unique += unique;
        plus2_plausible += s.plausible;
        plus2_positive += s.positive;
        semantic.push(format!(
            "V{}: records={} unique_keys={} +2={}/{} plausible ({}%) pos={} full={} flags={} • {}",
            i + 1,
            counts[i],
            unique,
            s.plausible,
            s.records,
            semantic_pct(s.plausible, s.records),
            s.positive,
            s.full,
            s.flagged,
            semantic_sample(bytes, 3),
        ));
    }

    let plus2_pct = semantic_pct(plus2_plausible, total_records);
    let plus2_rank = ranked.iter().position(|item| item.0 == 2).map(|i| i + 1).unwrap_or(4);
    let semantic_pass = plus2_pct >= 80 && plus2_positive >= 2 && total_unique >= 6;
    semantic.push(format!(
        "SEMANTIC VERDICT: {} • +2 rank=#{plus2_rank}/4 plausible={plus2_plausible}/{total_records} ({plus2_pct}%) positive={plus2_positive} unique_keys_sum={total_unique}",
        if semantic_pass { "STRONG CANDIDATE" } else { "MORE EVIDENCE REQUIRED" },
    ));
    semantic.push("NEXT CROSS-CHECK: run this mapper on another senior team; matching keyset/layout fingerprints with different +2 values would strongly support key@+0 / knowledge@+2".to_owned());

    prefix_probe_lines(&mut report, semantic);
    Ok(report)
}

#[cfg(test)]
mod element_semantic_mapper_tests {
    use super::{semantic_offset_stats, semantic_unique_keys, ELEMENT_SEMANTIC_STRIDE};

    #[test]
    fn semantic_stride_is_eight() {
        assert_eq!(ELEMENT_SEMANTIC_STRIDE, 8);
    }

    #[test]
    fn semantic_plus_two_reads_low14_and_preserves_flags_as_evidence() {
        let records = [
            0x10, 0x00, 0x5D, 0xC9, 1, 0, 0, 0,
            0x11, 0x00, 0x10, 0x27, 2, 0, 0, 0,
        ];
        let stats = semantic_offset_stats(&records, 2);
        assert_eq!(stats.records, 2);
        assert_eq!(stats.plausible, 2);
        assert_eq!(stats.positive, 2);
        assert_eq!(stats.full, 1);
        assert_eq!(stats.flagged, 1);
        assert_eq!(semantic_unique_keys(&records), 2);
    }
}

'@

    $text = $text.Substring(0, $at) + $semanticCode + $text.Substring($at)
    Write-Text $inspector $text
}

# Reuse the stable inspector command/result protocol, but run the semantic mapper.
Replace-Required 'src/bridge/worker.rs' '                    Some(f) => tactical_inspector::probe_plan(f, club_addr, senior_team_addr),' '                    Some(f) => tactical_inspector::semantic_map(f, club_addr, senior_team_addr),'

# UI wording and slightly larger evidence window for semantic collection summaries.
Replace-Required 'src/ui/club_panel.rs' 'v3.0 • DRY-RUN PROBE LAB' 'v3.1 • SEMANTIC TACTICAL MAPPER'
Replace-Required 'src/ui/club_panel.rs' 'Validates the exact Barcelona candidate, snapshots all six vectors, identifies the candidate low14 word and calculates the exact +/-1 round-trip bytes. Zero writes; Full 100% remains locked.' 'Parses the validated six-vector candidate as 8-byte records, ranks u16 value slots, fingerprints candidate keys and reports key/value/tail samples per collection. Zero writes; Full 100% remains locked.'
Replace-Required 'src/ui/club_panel.rs' 'Run Probe Dry-Run' 'Run Semantic Mapper'
Replace-Required 'src/ui/club_panel.rs' 'Dry-run • exact target + round-trip bytes • zero writes' 'Read-only • stride/key/value inference • zero writes'
Replace-Required 'src/ui/club_panel.rs' 'DRY-RUN PROBE • FULL 100% WRITE STILL LOCKED' 'SEMANTIC MAPPER • FULL 100% WRITE STILL LOCKED'
Replace-Required 'src/ui/club_panel.rs' 'for line in r.candidate_lines.iter().take(18)' 'for line in r.candidate_lines.iter().take(30)'

Write-Host 'Element v3.1 Tactical Knowledge semantic mapper applied successfully.'
