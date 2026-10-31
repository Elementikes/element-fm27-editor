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
    if (-not $Text.Contains($Old)) { throw "v3.0: expected text not found in $RelativePath`n--- expected ---`n$Old" }
    Write-Text $RelativePath ($Text.Replace($Old, $New))
}

# -----------------------------------------------------------------------------
# Element v3.0 — TACTICAL KNOWLEDGE DRY-RUN PROBE LAB
#
# The v2.9 cross-validator repeatedly identified this Barcelona candidate:
#   senior_team +0x30 -> heap object +0x18 -> six adjacent vector descriptors
#   spans [16, 8, 832, 128, 248, 136]
#
# v3.0 validates that exact chain, snapshots all six vectors, identifies the
# candidate low-14-bit word, and calculates the exact +1/-1 round-trip bytes.
# It performs ZERO writes to the FM process. Full Tactical Knowledge stays locked.
# -----------------------------------------------------------------------------

$inspector = 'src/bridge/tactical_inspector.rs'
$text = Read-Text $inspector
if (-not $text.Contains('Element v2.9 read-only Tactical Knowledge cross validator')) {
    throw 'v3.0: v2.9 tactical cross validator source not found; refusing to inspect an unknown layout'
}
if (-not $text.Contains('pub(super) fn probe_plan(')) {
    $marker = '#[cfg(test)]'
    $at = $text.IndexOf($marker)
    if ($at -lt 0) { throw 'v3.0: tactical inspector test boundary not found' }

    $probeCode = @'
const ELEMENT_PROBE_ROOT_PTR_OFFSET: u64 = 0x30;
const ELEMENT_PROBE_VECTOR_RUN_OFFSET: u64 = 0x18;
const ELEMENT_PROBE_EXPECTED_SPANS: [usize; 6] = [16, 8, 832, 128, 248, 136];
const ELEMENT_PROBE_VALUE_OFFSET: u64 = 2;

fn probe_mutation(raw: u16) -> Option<(u16, u16, u16)> {
    let value = raw & 0x3FFF;
    if value == 0 || value > 10_000 {
        return None;
    }
    let next = if value < 10_000 { value + 1 } else { value - 1 };
    let mutated = (raw & 0xC000) | next;
    Some((value, next, mutated))
}

fn prefix_probe_lines(report: &mut TacticalInspectorReport, mut lines: Vec<String>) {
    let old = std::mem::take(&mut report.candidate_lines);
    lines.extend(old);
    report.candidate_lines = lines;
    report.ready_for_write = false;
}

pub(super) fn probe_plan(
    fm: &FmProcess,
    club_addr: u64,
    senior_team_addr: u64,
) -> Result<TacticalInspectorReport, String> {
    let mut report = inspect(fm, club_addr, senior_team_addr)?;
    let mut evidence = Vec::new();
    evidence.push("DRY-RUN PROBE: exact target planning only; ZERO WRITES; Full 100% remains LOCKED".to_owned());

    let root_ptr_raw = fm
        .read_bytes(senior_team_addr + ELEMENT_PROBE_ROOT_PTR_OFFSET, 8)
        .map_err(|e| format!("probe plan cannot read senior_team+0x30 pointer: {e}"))?;
    let root_addr = qword(&root_ptr_raw, 0)
        .ok_or_else(|| "probe plan cannot decode senior_team+0x30 pointer".to_owned())?;
    if !valid_ptr(root_addr) {
        evidence.push(format!("PROBE GATE: FAIL invalid team+0x30 root 0x{root_addr:X}"));
        prefix_probe_lines(&mut report, evidence);
        return Ok(report);
    }

    let descriptor_addr = root_addr + ELEMENT_PROBE_VECTOR_RUN_OFFSET;
    let descriptor_bytes = fm
        .read_bytes(descriptor_addr, 6 * 24)
        .map_err(|e| format!("probe plan cannot read six-vector descriptor table: {e}"))?;

    let mut descs = Vec::with_capacity(6);
    for i in 0..6 {
        let Some(desc) = vector_desc_at(&descriptor_bytes, i * 24) else {
            evidence.push(format!("PROBE GATE: FAIL V{} descriptor invalid", i + 1));
            prefix_probe_lines(&mut report, evidence);
            return Ok(report);
        };
        descs.push(desc);
    }

    let spans = [
        descs[0].span,
        descs[1].span,
        descs[2].span,
        descs[3].span,
        descs[4].span,
        descs[5].span,
    ];
    if spans != ELEMENT_PROBE_EXPECTED_SPANS {
        evidence.push(format!(
            "PROBE GATE: FAIL signature team+0x30+0x18 spans={:?}; expected {:?}",
            spans,
            ELEMENT_PROBE_EXPECTED_SPANS,
        ));
        prefix_probe_lines(&mut report, evidence);
        return Ok(report);
    }

    let mut total_snapshot_bytes = 0usize;
    for (i, desc) in descs.iter().enumerate() {
        match fm.read_bytes(desc.data, desc.span) {
            Ok(bytes) => {
                total_snapshot_bytes += bytes.len();
                evidence.push(format!(
                    "SNAPSHOT V{}: PASS addr=0x{:X} span={}B",
                    i + 1,
                    desc.data,
                    desc.span,
                ));
            }
            Err(e) => {
                evidence.push(format!("SNAPSHOT V{}: FAIL {e}", i + 1));
                prefix_probe_lines(&mut report, evidence);
                return Ok(report);
            }
        }
    }

    let target_addr = descs[0].data + ELEMENT_PROBE_VALUE_OFFSET;
    let target = fm
        .read_bytes(target_addr, 2)
        .map_err(|e| format!("probe plan cannot read candidate target u16: {e}"))?;
    let raw = u16::from_le_bytes([target[0], target[1]]);
    let Some((old_value, new_value, mutated_raw)) = probe_mutation(raw) else {
        evidence.push(format!(
            "TARGET GATE: FAIL V1 record0 +2 raw=0x{raw:04X} is not a safe low14 value in 1..10000"
        ));
        prefix_probe_lines(&mut report, evidence);
        return Ok(report);
    };

    let original_bytes = raw.to_le_bytes();
    let planned_bytes = mutated_raw.to_le_bytes();
    evidence.insert(1, format!(
        "PROBE GATE: PASS team+0x30+0x18 spans={:?} root=0x{root_addr:X}",
        spans,
    ));
    evidence.insert(2, format!(
        "TARGET: V1 record0 +2 @0x{target_addr:X} raw=0x{raw:04X} low14={old_value}"
    ));
    evidence.insert(3, format!(
        "PLANNED ROUND-TRIP: {:02X} {:02X} -> {:02X} {:02X} (low14 {old_value}->{new_value}) -> {:02X} {:02X}",
        original_bytes[0], original_bytes[1],
        planned_bytes[0], planned_bytes[1],
        original_bytes[0], original_bytes[1],
    ));
    evidence.insert(4, format!(
        "SNAPSHOT PLAN: {}B across 6 vectors + 144B descriptor table",
        total_snapshot_bytes,
    ));
    evidence.insert(5, "PROBE PLAN VERIFIED: YES • actual write intentionally not executed".to_owned());

    prefix_probe_lines(&mut report, evidence);
    Ok(report)
}

#[cfg(test)]
mod element_probe_plan_tests {
    use super::probe_mutation;

    #[test]
    fn probe_plan_preserves_high_flags() {
        let raw = 0x8000u16 | 2397u16;
        let (old, new, mutated) = probe_mutation(raw).unwrap();
        assert_eq!(old, 2397);
        assert_eq!(new, 2398);
        assert_eq!(mutated & 0xC000, raw & 0xC000);
        assert_eq!(mutated & 0x3FFF, 2398);
    }

    #[test]
    fn probe_plan_rejects_zero_and_out_of_range() {
        assert!(probe_mutation(0).is_none());
        assert!(probe_mutation(10_001).is_none());
    }
}

'@

    $text = $text.Substring(0, $at) + $probeCode + $text.Substring($at)
    Write-Text $inspector $text
}

# Reuse the existing Inspect command so the app protocol remains stable.
Replace-Required 'src/bridge/worker.rs' '                    Some(f) => tactical_inspector::inspect(f, club_addr, senior_team_addr),' '                    Some(f) => tactical_inspector::probe_plan(f, club_addr, senior_team_addr),'

# UI wording.
Replace-Required 'src/ui/club_panel.rs' 'v2.9 • CROSS VALIDATOR' 'v3.0 • DRY-RUN PROBE LAB'
Replace-Required 'src/ui/club_panel.rs' 'Ranks six-vector runs first, emits stable path signatures and bounded per-vector dumps, then shows formation +14 and packed14 evidence. Zero writes.' 'Validates the exact Barcelona candidate, snapshots all six vectors, identifies the candidate low14 word and calculates the exact +/-1 round-trip bytes. Zero writes; Full 100% remains locked.'
Replace-Required 'src/ui/club_panel.rs' 'Run Cross Validator' 'Run Probe Dry-Run'
Replace-Required 'src/ui/club_panel.rs' 'Read-only • bounded scan • no memory writes' 'Dry-run • exact target + round-trip bytes • zero writes'
Replace-Required 'src/ui/club_panel.rs' 'STRUCTURAL CANDIDATE FOUND • WRITE STILL LOCKED' 'DRY-RUN PROBE • FULL 100% WRITE STILL LOCKED'

Write-Host 'Element v3.0 Tactical Knowledge dry-run probe lab applied successfully.'
