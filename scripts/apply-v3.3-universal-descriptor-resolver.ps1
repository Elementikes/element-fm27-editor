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
    if (-not $Text.Contains($Old)) { throw "v3.3: expected text not found in $RelativePath`n--- expected ---`n$Old" }
    Write-Text $RelativePath ($Text.Replace($Old, $New))
}

# -----------------------------------------------------------------------------
# Element v3.3 — UNIVERSAL DESCRIPTOR RESOLVER
#
# v3.2 proved that the same periodic family can exist across unrelated clubs,
# but semantic-first admission hid EMPTY/UNALLOCATED collections and sparse
# layouts. v3.3 resolves structure first. It scans the Senior Team object plus
# bounded one-hop heap roots, classifies raw MSVC vector descriptors as
# POPULATED / EMPTY / UNALLOCATED / INVALID, derives periodic six-slot families
# from descriptor geometry, then adds semantic evidence only as confidence.
# No club names, no fixed spans, no fixed base/step, ZERO writes.
# -----------------------------------------------------------------------------

$inspector = 'src/bridge/tactical_inspector.rs'
$text = Read-Text $inspector
if (-not $text.Contains('pub(super) fn adaptive_map(')) {
    throw 'v3.3: v3.2 adaptive resolver source not found; refusing to inspect an unknown layout'
}

if (-not $text.Contains('pub(super) fn descriptor_map(')) {
    $markers = @(
        "#[cfg(test)]`nmod element_adaptive_resolver_tests",
        "#[cfg(test)]`r`nmod element_adaptive_resolver_tests"
    )
    $at = -1
    foreach ($marker in $markers) {
        $at = $text.IndexOf($marker)
        if ($at -ge 0) { break }
    }
    if ($at -lt 0) { throw 'v3.3: v3.2 adaptive test boundary not found' }

    $descriptorCode = @'
const ELEMENT_DESCRIPTOR_SCAN_BYTES: usize = 0x900;
const ELEMENT_DESCRIPTOR_ROOT_BYTES: usize = 0x900;
const ELEMENT_DESCRIPTOR_MAX_ROOTS: usize = 96;
const ELEMENT_DESCRIPTOR_MAX_BYTES: usize = 0x20_000;

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
enum DescriptorState {
    Populated,
    Empty,
    Unallocated,
    Invalid,
}

#[derive(Clone, Copy, Debug)]
struct RawDescriptor {
    state: DescriptorState,
    data: u64,
    end: u64,
    cap: u64,
    span: usize,
    cap_span: usize,
}

#[derive(Clone, Debug)]
struct StructuralVector {
    slot_off: usize,
    desc: RawDescriptor,
    records: usize,
    plus2: SemanticOffsetStats,
    plus4: SemanticOffsetStats,
    unique_keys: usize,
    tail271: usize,
    semantic_ok: bool,
}

#[derive(Clone, Debug)]
struct StructuralContext {
    label: String,
    base_addr: u64,
    blob: Vec<u8>,
    vectors: Vec<StructuralVector>,
}

#[derive(Clone, Debug)]
struct DescriptorFamily {
    context_index: usize,
    base: usize,
    step: usize,
    populated: usize,
    empty: usize,
    unallocated: usize,
    invalid: usize,
    semantic_members: usize,
    score: isize,
}

fn raw_descriptor_at(buf: &[u8], off: usize) -> RawDescriptor {
    let Some(data) = qword(buf, off) else {
        return RawDescriptor { state: DescriptorState::Invalid, data: 0, end: 0, cap: 0, span: 0, cap_span: 0 };
    };
    let Some(end) = qword(buf, off + 8) else {
        return RawDescriptor { state: DescriptorState::Invalid, data, end: 0, cap: 0, span: 0, cap_span: 0 };
    };
    let Some(cap) = qword(buf, off + 16) else {
        return RawDescriptor { state: DescriptorState::Invalid, data, end, cap: 0, span: 0, cap_span: 0 };
    };

    if data == 0 && end == 0 && cap == 0 {
        return RawDescriptor { state: DescriptorState::Unallocated, data, end, cap, span: 0, cap_span: 0 };
    }
    if !valid_ptr(data) || !valid_ptr(end) || !valid_ptr(cap) || end < data || cap < end {
        return RawDescriptor { state: DescriptorState::Invalid, data, end, cap, span: 0, cap_span: 0 };
    }

    let Ok(span) = usize::try_from(end - data) else {
        return RawDescriptor { state: DescriptorState::Invalid, data, end, cap, span: 0, cap_span: 0 };
    };
    let Ok(cap_span) = usize::try_from(cap - data) else {
        return RawDescriptor { state: DescriptorState::Invalid, data, end, cap, span: 0, cap_span: 0 };
    };
    if span > ELEMENT_DESCRIPTOR_MAX_BYTES || cap_span > ELEMENT_DESCRIPTOR_MAX_BYTES * 4 {
        return RawDescriptor { state: DescriptorState::Invalid, data, end, cap, span, cap_span };
    }

    let state = if span == 0 { DescriptorState::Empty } else { DescriptorState::Populated };
    RawDescriptor { state, data, end, cap, span, cap_span }
}

fn descriptor_state_name(state: DescriptorState) -> &'static str {
    match state {
        DescriptorState::Populated => "POPULATED",
        DescriptorState::Empty => "EMPTY",
        DescriptorState::Unallocated => "UNALLOCATED",
        DescriptorState::Invalid => "INVALID",
    }
}

fn structural_vector_from_desc(
    fm: &FmProcess,
    slot_off: usize,
    desc: RawDescriptor,
) -> StructuralVector {
    let mut vector = StructuralVector {
        slot_off,
        desc,
        records: 0,
        plus2: SemanticOffsetStats::default(),
        plus4: SemanticOffsetStats::default(),
        unique_keys: 0,
        tail271: 0,
        semantic_ok: false,
    };

    if desc.state != DescriptorState::Populated
        || desc.span % ELEMENT_SEMANTIC_STRIDE != 0
        || desc.span == 0
    {
        return vector;
    }

    let records = desc.span / ELEMENT_SEMANTIC_STRIDE;
    if records == 0 || records > 4096 { return vector; }
    let Ok(bytes) = fm.read_bytes(desc.data, desc.span) else { return vector; };

    vector.records = records;
    vector.plus2 = semantic_offset_stats(&bytes, 2);
    vector.plus4 = semantic_offset_stats(&bytes, 4);
    vector.unique_keys = semantic_unique_keys(&bytes);
    vector.tail271 = adaptive_tail_count(&bytes, ELEMENT_ADAPTIVE_TAIL_SIGNATURE);
    let p2 = semantic_pct(vector.plus2.plausible, records);
    let p4 = semantic_pct(vector.plus4.plausible, records);
    vector.semantic_ok = p2 >= 55 || p4 >= 55 || vector.tail271 > 0;
    vector
}

fn scan_structural_context(
    fm: &FmProcess,
    label: String,
    base_addr: u64,
    blob: Vec<u8>,
) -> StructuralContext {
    let mut vectors = Vec::new();
    let mut seen = HashSet::new();
    for off in (0..=blob.len().saturating_sub(24)).step_by(8) {
        let desc = raw_descriptor_at(&blob, off);
        match desc.state {
            DescriptorState::Populated | DescriptorState::Empty => {
                let identity = (desc.data, desc.end, desc.cap, off);
                if seen.insert(identity) {
                    vectors.push(structural_vector_from_desc(fm, off, desc));
                }
            }
            DescriptorState::Unallocated | DescriptorState::Invalid => {}
        }
    }
    StructuralContext { label, base_addr, blob, vectors }
}

fn descriptor_contexts(
    fm: &FmProcess,
    senior_team_addr: u64,
) -> Result<Vec<StructuralContext>, String> {
    let team = fm
        .read_bytes(senior_team_addr, ELEMENT_DESCRIPTOR_SCAN_BYTES)
        .or_else(|_| fm.read_bytes(senior_team_addr, ELEMENT_DESCRIPTOR_SCAN_BYTES / 2))
        .map_err(|e| format!("descriptor resolver cannot read Senior Team object: {e}"))?;

    let mut contexts = Vec::new();
    contexts.push(scan_structural_context(
        fm,
        "senior_team".to_owned(),
        senior_team_addr,
        team.clone(),
    ));

    let mut seen_roots = HashSet::new();
    let mut roots = Vec::new();
    for off in (0..team.len().saturating_sub(8)).step_by(8) {
        let Some(ptr) = qword(&team, off) else { continue };
        if !valid_ptr(ptr)
            || (fm.gp_base..fm.gp_end).contains(&ptr)
            || !seen_roots.insert(ptr)
        {
            continue;
        }
        roots.push((off, ptr));
        if roots.len() >= ELEMENT_DESCRIPTOR_MAX_ROOTS { break; }
    }

    for (root_off, ptr) in roots {
        if let Ok(blob) = fm.read_bytes(ptr, ELEMENT_DESCRIPTOR_ROOT_BYTES) {
            contexts.push(scan_structural_context(
                fm,
                format!("team+0x{root_off:X}->root"),
                ptr,
                blob,
            ));
        }
    }
    Ok(contexts)
}

fn family_member_score(
    fm: &FmProcess,
    ctx: &StructuralContext,
    off: usize,
) -> (DescriptorState, usize, bool, isize) {
    if off + 24 > ctx.blob.len() {
        return (DescriptorState::Invalid, 0, false, -900);
    }
    let desc = raw_descriptor_at(&ctx.blob, off);
    match desc.state {
        DescriptorState::Populated => {
            let v = structural_vector_from_desc(fm, off, desc);
            let mut score = 1150isize;
            if desc.span % ELEMENT_SEMANTIC_STRIDE == 0 { score += 250; }
            if v.semantic_ok { score += 650; }
            if v.records > 0 {
                let p2 = semantic_pct(v.plus2.plausible, v.records);
                let p4 = semantic_pct(v.plus4.plausible, v.records);
                score += (p2.max(p4) as isize) * 5;
                if p2 >= p4 { score += 120; }
                if v.tail271 > 0 { score += 180; }
            }
            (DescriptorState::Populated, v.records, v.semantic_ok, score)
        }
        DescriptorState::Empty => (DescriptorState::Empty, 0, false, 850),
        // All-zero triples are useful only inside a family anchored by real
        // populated/allocated descriptors, so they receive a modest score.
        DescriptorState::Unallocated => (DescriptorState::Unallocated, 0, false, 220),
        DescriptorState::Invalid => (DescriptorState::Invalid, 0, false, -1000),
    }
}

fn evaluate_family(
    fm: &FmProcess,
    ctx: &StructuralContext,
    context_index: usize,
    base: usize,
    step: usize,
) -> DescriptorFamily {
    let mut family = DescriptorFamily {
        context_index,
        base,
        step,
        populated: 0,
        empty: 0,
        unallocated: 0,
        invalid: 0,
        semantic_members: 0,
        score: 0,
    };

    for n in 0..6usize {
        let off = base + n * step;
        let (state, _records, semantic_ok, score) = family_member_score(fm, ctx, off);
        family.score += score;
        match state {
            DescriptorState::Populated => family.populated += 1,
            DescriptorState::Empty => family.empty += 1,
            DescriptorState::Unallocated => family.unallocated += 1,
            DescriptorState::Invalid => family.invalid += 1,
        }
        if semantic_ok { family.semantic_members += 1; }
    }

    // Reward structurally complete families and semantic confirmation, but do
    // not require all six collections to be populated.
    let resolved = family.populated + family.empty + family.unallocated;
    family.score += (resolved as isize) * 300;
    family.score += (family.semantic_members as isize) * 450;
    if family.populated >= 2 { family.score += 1000; }
    if family.invalid == 0 { family.score += 700; }
    family
}

fn descriptor_best_family(
    fm: &FmProcess,
    contexts: &[StructuralContext],
) -> Option<DescriptorFamily> {
    let mut best: Option<DescriptorFamily> = None;

    for (context_index, ctx) in contexts.iter().enumerate() {
        let mut populated_offsets: Vec<usize> = ctx
            .vectors
            .iter()
            .filter(|v| v.desc.state == DescriptorState::Populated)
            .map(|v| v.slot_off)
            .collect();
        populated_offsets.sort_unstable();
        populated_offsets.dedup();
        if populated_offsets.len() < 2 { continue; }

        let mut tried = HashSet::new();
        for i in 0..populated_offsets.len() {
            for j in (i + 1)..populated_offsets.len() {
                let delta = populated_offsets[j] - populated_offsets[i];
                for gap in 1..=5usize {
                    if delta % gap != 0 { continue; }
                    let step = delta / gap;
                    if step < 0x20 || step > 0x300 || step % 8 != 0 { continue; }

                    // Any observed populated descriptor may be C1..C6. Try all
                    // legal bases so sparse families can still be reconstructed.
                    for position in 0..6usize {
                        let back = position * step;
                        if populated_offsets[i] < back { continue; }
                        let base = populated_offsets[i] - back;
                        if base + 5 * step + 24 > ctx.blob.len() { continue; }
                        if !tried.insert((base, step)) { continue; }

                        let family = evaluate_family(fm, ctx, context_index, base, step);
                        // At least two real populated descriptors anchor a family;
                        // EMPTY/UNALLOCATED slots may fill the remainder.
                        if family.populated < 2 { continue; }
                        let replace = best.as_ref().map(|b| family.score > b.score).unwrap_or(true);
                        if replace { best = Some(family); }
                    }
                }
            }
        }
    }
    best
}

fn descriptor_member_line(
    fm: &FmProcess,
    ctx: &StructuralContext,
    index: usize,
    off: usize,
) -> String {
    let desc = raw_descriptor_at(&ctx.blob, off);
    match desc.state {
        DescriptorState::Populated => {
            let v = structural_vector_from_desc(fm, off, desc);
            let p2 = semantic_pct(v.plus2.plausible, v.records);
            let p4 = semantic_pct(v.plus4.plausible, v.records);
            format!(
                "C{index} {}+0x{off:X}: POPULATED records={} span={}B cap={}B +2={}%(pos={}) +4={}%(pos={}) keys={} tail271={} semantic={}",
                ctx.label,
                v.records,
                desc.span,
                desc.cap_span,
                p2,
                v.plus2.positive,
                p4,
                v.plus4.positive,
                v.unique_keys,
                v.tail271,
                if v.semantic_ok { "PASS" } else { "WEAK" },
            )
        }
        DescriptorState::Empty => format!(
            "C{index} {}+0x{off:X}: EMPTY allocated data=0x{:X} cap={}B",
            ctx.label, desc.data, desc.cap_span,
        ),
        DescriptorState::Unallocated => format!(
            "C{index} {}+0x{off:X}: UNALLOCATED (0/0/0 descriptor)", ctx.label,
        ),
        DescriptorState::Invalid => format!(
            "C{index} {}+0x{off:X}: INVALID descriptor", ctx.label,
        ),
    }
}

pub(super) fn descriptor_map(
    fm: &FmProcess,
    club_addr: u64,
    senior_team_addr: u64,
) -> Result<TacticalInspectorReport, String> {
    let mut report = adaptive_map(fm, club_addr, senior_team_addr)?;
    let mut lines = Vec::new();
    lines.push("UNIVERSAL DESCRIPTOR RESOLVER v3.3: STRUCTURE-FIRST • club-agnostic • ZERO WRITES".to_owned());
    lines.push("DESCRIPTOR POLICY: begin<=end<=capacity; span=0 is valid EMPTY; 0/0/0 is UNALLOCATED; populated semantic values are confidence only".to_owned());

    let contexts = descriptor_contexts(fm, senior_team_addr)?;
    let total_vectors: usize = contexts.iter().map(|c| c.vectors.len()).sum();
    let populated_vectors: usize = contexts.iter().map(|c| c.vectors.iter().filter(|v| v.desc.state == DescriptorState::Populated).count()).sum();
    let allocated_empty: usize = contexts.iter().map(|c| c.vectors.iter().filter(|v| v.desc.state == DescriptorState::Empty).count()).sum();
    lines.push(format!(
        "DISCOVERY: contexts={} structural_vectors={} populated={} allocated_empty={} (Senior Team + bounded one-hop roots)",
        contexts.len(), total_vectors, populated_vectors, allocated_empty,
    ));

    let Some(family) = descriptor_best_family(fm, &contexts) else {
        lines.push("DESCRIPTOR FAMILY: NO CERTIFIED FAMILY YET • fewer than two populated structural anchors in any scanned context".to_owned());
        for ctx in contexts.iter().take(6) {
            let semantic = ctx.vectors.iter().filter(|v| v.semantic_ok).count();
            lines.push(format!(
                "CONTEXT {} base=0x{:X}: vectors={} semantic={} (sparse/uninitialized layouts remain write-locked)",
                ctx.label, ctx.base_addr, ctx.vectors.len(), semantic,
            ));
        }
        prefix_probe_lines(&mut report, lines);
        return Ok(report);
    };

    let ctx = &contexts[family.context_index];
    let resolved = family.populated + family.empty + family.unallocated;
    lines.push(format!(
        "BEST DESCRIPTOR FAMILY: context={} base=+0x{:X} step=0x{:X} resolved={}/6 populated={} empty={} unallocated={} invalid={} semantic={} score={}",
        ctx.label,
        family.base,
        family.step,
        resolved,
        family.populated,
        family.empty,
        family.unallocated,
        family.invalid,
        family.semantic_members,
        family.score,
    ));
    for n in 0..6usize {
        lines.push(descriptor_member_line(fm, ctx, n + 1, family.base + n * family.step));
    }

    let structure_complete = resolved >= 5 && family.invalid <= 1;
    let semantic_supported = family.semantic_members >= 1;
    let universal_candidate = structure_complete && family.populated >= 2 && semantic_supported;
    lines.push(format!(
        "DESCRIPTOR VERDICT: {} • structure_complete={} semantic_supported={} • Full 100% remains LOCKED",
        if universal_candidate { "UNIVERSAL LAYOUT CANDIDATE" }
        else if structure_complete { "STRUCTURAL FAMILY CANDIDATE" }
        else { "MORE STRUCTURAL EVIDENCE REQUIRED" },
        structure_complete,
        semantic_supported,
    ));
    lines.push("CERTIFICATION TARGET: same descriptor rules must classify populated, empty and unallocated collections across unrelated senior/reserve/U19 teams before any write path is considered.".to_owned());

    prefix_probe_lines(&mut report, lines);
    Ok(report)
}

#[cfg(test)]
mod element_descriptor_resolver_tests {
    use super::{raw_descriptor_at, DescriptorState};

    #[test]
    fn recognizes_unallocated_vector() {
        let buf = [0u8; 24];
        assert_eq!(raw_descriptor_at(&buf, 0).state, DescriptorState::Unallocated);
    }

    #[test]
    fn recognizes_allocated_empty_vector() {
        let mut buf = [0u8; 24];
        let p = 0x100000u64;
        buf[0..8].copy_from_slice(&p.to_le_bytes());
        buf[8..16].copy_from_slice(&p.to_le_bytes());
        buf[16..24].copy_from_slice(&(p + 0x80).to_le_bytes());
        let d = raw_descriptor_at(&buf, 0);
        assert_eq!(d.state, DescriptorState::Empty);
        assert_eq!(d.span, 0);
        assert_eq!(d.cap_span, 0x80);
    }

    #[test]
    fn recognizes_populated_vector_without_semantic_assumptions() {
        let mut buf = [0u8; 24];
        let p = 0x100000u64;
        buf[0..8].copy_from_slice(&p.to_le_bytes());
        buf[8..16].copy_from_slice(&(p + 0x40).to_le_bytes());
        buf[16..24].copy_from_slice(&(p + 0x80).to_le_bytes());
        let d = raw_descriptor_at(&buf, 0);
        assert_eq!(d.state, DescriptorState::Populated);
        assert_eq!(d.span, 0x40);
    }
}

'@

    $text = $text.Substring(0, $at) + $descriptorCode + $text.Substring($at)
    Write-Text $inspector $text
}

# Stable inspector protocol; structure-first resolver replaces v3.2 adaptive map.
Replace-Required 'src/bridge/worker.rs' '                    Some(f) => tactical_inspector::adaptive_map(f, club_addr, senior_team_addr),' '                    Some(f) => tactical_inspector::descriptor_map(f, club_addr, senior_team_addr),'

# UI wording.
Replace-Required 'src/ui/club_panel.rs' 'v3.2 • UNIVERSAL TACTICAL RESOLVER' 'v3.3 • UNIVERSAL DESCRIPTOR RESOLVER'
Replace-Required 'src/ui/club_panel.rs' 'Discovers tactical collections dynamically from the selected Senior Team object. No club names, no fixed vector sizes and no Barcelona-only root. Handles different record counts and empty collections. Zero writes.' 'Discovers vector descriptors structurally from Senior Team and bounded one-hop roots. EMPTY and UNALLOCATED collections are valid states; semantic values only add confidence. No club names, fixed spans, base or step. Zero writes.'
Replace-Required 'src/ui/club_panel.rs' 'Run Universal Resolver' 'Run Descriptor Resolver'
Replace-Required 'src/ui/club_panel.rs' 'Read-only • club-agnostic adaptive discovery • zero writes' 'Read-only • descriptor-first universal discovery • zero writes'
Replace-Required 'src/ui/club_panel.rs' 'UNIVERSAL RESOLVER • FULL 100% WRITE STILL LOCKED' 'DESCRIPTOR RESOLVER • FULL 100% WRITE STILL LOCKED'

Write-Host 'Element v3.3 universal descriptor resolver applied successfully.'
