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
    if (-not $Text.Contains($Old)) { throw "v3.2: expected text not found in $RelativePath`n--- expected ---`n$Old" }
    Write-Text $RelativePath ($Text.Replace($Old, $New))
}

# -----------------------------------------------------------------------------
# Element v3.2 — UNIVERSAL / CLUB-AGNOSTIC TACTICAL COLLECTION RESOLVER
#
# v3.1 proved the 8-byte record hypothesis strongly on Barcelona but also showed
# why the Barcelona six-adjacent-vector root cannot be treated as universal.
# v3.2 removes club-specific span/root assumptions. It scans the Senior Team
# object itself for vector descriptors, scores each vector semantically, detects
# recurring descriptor families from their spacing, and reports a portable
# collection layout. Empty/different-size collections are allowed. ZERO writes.
# -----------------------------------------------------------------------------

$inspector = 'src/bridge/tactical_inspector.rs'
$text = Read-Text $inspector
if (-not $text.Contains('pub(super) fn semantic_map(')) {
    throw 'v3.2: v3.1 semantic mapper source not found; refusing to resolve an unknown layout'
}

if (-not $text.Contains('pub(super) fn adaptive_map(')) {
    $markers = @(
        "#[cfg(test)]`nmod element_semantic_mapper_tests",
        "#[cfg(test)]`r`nmod element_semantic_mapper_tests"
    )
    $at = -1
    foreach ($marker in $markers) {
        $at = $text.IndexOf($marker)
        if ($at -ge 0) { break }
    }
    if ($at -lt 0) { throw 'v3.2: v3.1 semantic test boundary not found' }

    $adaptiveCode = @'
const ELEMENT_ADAPTIVE_SCAN_BYTES: usize = 0x700;
const ELEMENT_ADAPTIVE_MAX_VECTOR_BYTES: usize = 0x8000;
const ELEMENT_ADAPTIVE_TAIL_SIGNATURE: u32 = 0x0000_0271;

#[derive(Clone, Debug)]
struct AdaptiveCollection {
    slot_off: usize,
    data: u64,
    span: usize,
    records: usize,
    unique_keys: usize,
    tail271: usize,
    plus2: SemanticOffsetStats,
    plus4: SemanticOffsetStats,
    score: usize,
}

fn adaptive_tail_count(bytes: &[u8], value: u32) -> usize {
    bytes
        .chunks_exact(ELEMENT_SEMANTIC_STRIDE)
        .filter(|record| semantic_u32(record, 4) == Some(value))
        .count()
}

fn adaptive_collection_score(
    records: usize,
    unique_keys: usize,
    tail271: usize,
    plus2: SemanticOffsetStats,
    plus4: SemanticOffsetStats,
) -> usize {
    if records == 0 { return 0; }
    let p2 = semantic_pct(plus2.plausible, records);
    let p4 = semantic_pct(plus4.plausible, records);
    let tail = semantic_pct(tail271, records);

    // Tail 0x271 is strong evidence from two independently observed clubs, but
    // it is a bonus rather than a requirement so clubs/builds with a variant
    // tail can still be discovered from stride/key/value behavior.
    p2 * 30
        + plus2.positive * 3
        + unique_keys.min(records) * 4
        + tail * 20
        + if p2 >= p4 { 250 } else { 0 }
        + if records >= 2 { 100 } else { 0 }
}

fn adaptive_scan_collections(
    fm: &FmProcess,
    senior_team_addr: u64,
) -> Result<Vec<AdaptiveCollection>, String> {
    let team = fm
        .read_bytes(senior_team_addr, ELEMENT_ADAPTIVE_SCAN_BYTES)
        .map_err(|e| format!("universal resolver cannot read Senior Team scan window: {e}"))?;

    let mut seen_data = HashSet::new();
    let mut out = Vec::new();

    for off in (0..=ELEMENT_ADAPTIVE_SCAN_BYTES.saturating_sub(24)).step_by(8) {
        let Some(desc) = vector_desc_at(&team, off) else { continue };
        if desc.span == 0
            || desc.span > ELEMENT_ADAPTIVE_MAX_VECTOR_BYTES
            || desc.span % ELEMENT_SEMANTIC_STRIDE != 0
            || !seen_data.insert(desc.data)
        {
            continue;
        }

        let records = desc.span / ELEMENT_SEMANTIC_STRIDE;
        if records == 0 || records > 4096 { continue; }

        let Ok(bytes) = fm.read_bytes(desc.data, desc.span) else { continue };
        let plus2 = semantic_offset_stats(&bytes, 2);
        let plus4 = semantic_offset_stats(&bytes, 4);
        let unique_keys = semantic_unique_keys(&bytes);
        let tail271 = adaptive_tail_count(&bytes, ELEMENT_ADAPTIVE_TAIL_SIGNATURE);
        let p2 = semantic_pct(plus2.plausible, records);

        // Broad admission gate: enough low14 plausibility or enough known-tail
        // evidence. This intentionally avoids club-specific sizes/counts.
        if p2 < 55 && tail271 == 0 { continue; }

        let score = adaptive_collection_score(records, unique_keys, tail271, plus2, plus4);
        out.push(AdaptiveCollection {
            slot_off: off,
            data: desc.data,
            span: desc.span,
            records,
            unique_keys,
            tail271,
            plus2,
            plus4,
            score,
        });
    }

    out.sort_by(|a, b| {
        b.score
            .cmp(&a.score)
            .then_with(|| a.slot_off.cmp(&b.slot_off))
    });
    Ok(out)
}

fn adaptive_best_family(candidates: &[AdaptiveCollection]) -> Option<(usize, usize, usize)> {
    if candidates.len() < 2 { return None; }

    let mut offsets: Vec<usize> = candidates
        .iter()
        .filter(|c| semantic_pct(c.plus2.plausible, c.records) >= 70)
        .map(|c| c.slot_off)
        .collect();
    offsets.sort_unstable();
    offsets.dedup();
    if offsets.len() < 2 { return None; }

    let set: HashSet<usize> = offsets.iter().copied().collect();
    let mut best: Option<(usize, usize, usize)> = None; // base, step, resolved

    for i in 0..offsets.len() {
        for j in (i + 1)..offsets.len() {
            let step = offsets[j] - offsets[i];
            if step < 0x20 || step > 0x200 || step % 8 != 0 { continue; }

            // Normalize to the earliest observed member of this arithmetic family.
            let mut base = offsets[i];
            while base >= step && set.contains(&(base - step)) {
                base -= step;
            }

            let mut resolved = 0usize;
            for n in 0..6usize {
                if set.contains(&(base + n * step)) { resolved += 1; }
            }

            let replace = match best {
                None => true,
                Some((_, best_step, best_resolved)) => {
                    resolved > best_resolved || (resolved == best_resolved && step < best_step)
                }
            };
            if replace { best = Some((base, step, resolved)); }
        }
    }
    best
}

fn adaptive_find_slot<'a>(candidates: &'a [AdaptiveCollection], off: usize) -> Option<&'a AdaptiveCollection> {
    candidates.iter().find(|c| c.slot_off == off)
}

fn adaptive_candidate_line(prefix: &str, c: &AdaptiveCollection) -> String {
    format!(
        "{prefix} team+0x{:X}: records={} span={}B score={} +2={}/{}({}%) +4={}/{}({}%) keys={} tail271={}/{}({}%) data=0x{:X}",
        c.slot_off,
        c.records,
        c.span,
        c.score,
        c.plus2.plausible,
        c.records,
        semantic_pct(c.plus2.plausible, c.records),
        c.plus4.plausible,
        c.records,
        semantic_pct(c.plus4.plausible, c.records),
        c.unique_keys,
        c.tail271,
        c.records,
        semantic_pct(c.tail271, c.records),
        c.data,
    )
}

pub(super) fn adaptive_map(
    fm: &FmProcess,
    club_addr: u64,
    senior_team_addr: u64,
) -> Result<TacticalInspectorReport, String> {
    // Keep v3.1/v3.0 evidence underneath, but universal resolution no longer
    // depends on the Barcelona root or exact six-vector spans.
    let mut report = semantic_map(fm, club_addr, senior_team_addr)?;
    let mut lines = Vec::new();
    lines.push("UNIVERSAL RESOLVER v3.2: CLUB-AGNOSTIC • dynamic Senior Team discovery • ZERO WRITES".to_owned());
    lines.push(format!(
        "SCAN POLICY: {}B Senior Team window • descriptor stride search=8B • record stride hypothesis=8B • no club names / no fixed spans",
        ELEMENT_ADAPTIVE_SCAN_BYTES,
    ));

    let candidates = adaptive_scan_collections(fm, senior_team_addr)?;
    lines.push(format!("DISCOVERY: {} semantic vector candidates", candidates.len()));

    if candidates.is_empty() {
        lines.push("UNIVERSAL VERDICT: NO MATCH • this club layout needs more structural evidence; write remains locked".to_owned());
        prefix_probe_lines(&mut report, lines);
        return Ok(report);
    }

    if let Some((base, step, resolved)) = adaptive_best_family(&candidates) {
        lines.push(format!(
            "BEST PERIODIC FAMILY: base=team+0x{base:X} step=0x{step:X} resolved={resolved}/6 (discovered, not hardcoded)"
        ));
        for n in 0..6usize {
            let off = base + n * step;
            if let Some(c) = adaptive_find_slot(&candidates, off) {
                lines.push(adaptive_candidate_line(&format!("C{}", n + 1), c));
            } else {
                lines.push(format!("C{} team+0x{off:X}: empty / invalid / below semantic threshold", n + 1));
            }
        }
    } else {
        lines.push("BEST PERIODIC FAMILY: not enough repeated slots yet; using ranked semantic candidates".to_owned());
        for (i, c) in candidates.iter().take(6).enumerate() {
            lines.push(adaptive_candidate_line(&format!("RANK#{}", i + 1), c));
        }
    }

    let strong: Vec<&AdaptiveCollection> = candidates
        .iter()
        .filter(|c| {
            semantic_pct(c.plus2.plausible, c.records) >= 85
                && c.plus2.positive >= 1
                && c.unique_keys >= 1
        })
        .collect();
    let signature_hits = strong.iter().filter(|c| c.tail271 > 0).count();
    let total_records: usize = strong.iter().map(|c| c.records).sum();
    let total_p2: usize = strong.iter().map(|c| c.plus2.plausible).sum();
    let p2_pct = semantic_pct(total_p2, total_records);

    let family_resolved = adaptive_best_family(&candidates).map(|(_, _, r)| r).unwrap_or(0);
    let portable = strong.len() >= 2 && p2_pct >= 90;
    let family_portable = family_resolved >= 3 && portable;
    lines.push(format!(
        "UNIVERSAL EVIDENCE: strong_vectors={} family_resolved={}/6 +2_plausible={}/{}({}%) tail271_vectors={}",
        strong.len(), family_resolved, total_p2, total_records, p2_pct, signature_hits,
    ));
    lines.push(format!(
        "UNIVERSAL VERDICT: {} • no Barcelona/City special case • Full 100% remains LOCKED",
        if family_portable { "PORTABLE FAMILY CANDIDATE" }
        else if portable { "PORTABLE SEMANTIC CANDIDATE" }
        else { "MORE CLUB EVIDENCE REQUIRED" },
    ));
    lines.push("VALIDATION TARGET: the same resolver must succeed across large/small clubs, reserve/U19 teams and clubs with empty collections before any write path is considered.".to_owned());

    prefix_probe_lines(&mut report, lines);
    Ok(report)
}

#[cfg(test)]
mod element_adaptive_resolver_tests {
    use super::{adaptive_best_family, adaptive_collection_score, AdaptiveCollection, SemanticOffsetStats};

    fn fake(off: usize) -> AdaptiveCollection {
        let s = SemanticOffsetStats { records: 10, plausible: 10, positive: 9, full: 0, zero: 1, flagged: 0 };
        AdaptiveCollection {
            slot_off: off,
            data: 0x10000 + off as u64,
            span: 80,
            records: 10,
            unique_keys: 9,
            tail271: 8,
            plus2: s,
            plus4: s,
            score: adaptive_collection_score(10, 9, 8, s, s),
        }
    }

    #[test]
    fn discovers_periodic_family_without_fixed_base() {
        let c = vec![fake(0x38), fake(0xF0), fake(0x1A8), fake(0x260), fake(0x318), fake(0x3D0)];
        let (base, step, resolved) = adaptive_best_family(&c).unwrap();
        assert_eq!(base, 0x38);
        assert_eq!(step, 0xB8);
        assert_eq!(resolved, 6);
    }

    #[test]
    fn allows_partial_family_for_clubs_with_empty_collections() {
        let c = vec![fake(0x40), fake(0x100), fake(0x280)];
        let result = adaptive_best_family(&c);
        assert!(result.is_some());
    }
}

'@

    $text = $text.Substring(0, $at) + $adaptiveCode + $text.Substring($at)
    Write-Text $inspector $text
}

# Stable inspector protocol; only the resolver implementation changes.
Replace-Required 'src/bridge/worker.rs' '                    Some(f) => tactical_inspector::semantic_map(f, club_addr, senior_team_addr),' '                    Some(f) => tactical_inspector::adaptive_map(f, club_addr, senior_team_addr),'

# Club-agnostic UI wording.
Replace-Required 'src/ui/club_panel.rs' 'v3.1 • SEMANTIC TACTICAL MAPPER' 'v3.2 • UNIVERSAL TACTICAL RESOLVER'
Replace-Required 'src/ui/club_panel.rs' 'Parses the validated six-vector candidate as 8-byte records, ranks u16 value slots, fingerprints candidate keys and reports key/value/tail samples per collection. Zero writes; Full 100% remains locked.' 'Discovers tactical collections dynamically from the selected Senior Team object. No club names, no fixed vector sizes and no Barcelona-only root. Handles different record counts and empty collections. Zero writes.'
Replace-Required 'src/ui/club_panel.rs' 'Run Semantic Mapper' 'Run Universal Resolver'
Replace-Required 'src/ui/club_panel.rs' 'Read-only • stride/key/value inference • zero writes' 'Read-only • club-agnostic adaptive discovery • zero writes'
Replace-Required 'src/ui/club_panel.rs' 'SEMANTIC MAPPER • FULL 100% WRITE STILL LOCKED' 'UNIVERSAL RESOLVER • FULL 100% WRITE STILL LOCKED'

Write-Host 'Element v3.2 universal tactical resolver applied successfully.'
