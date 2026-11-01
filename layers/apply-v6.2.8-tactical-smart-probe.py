from pathlib import Path

root = Path.cwd()

def rd(path):
    p = root / path
    if not p.exists():
        raise SystemExit(f"v6.2.8 missing {path}")
    return p.read_text(encoding="utf-8")

def wr(path, text):
    (root / path).write_text(text, encoding="utf-8")

def one(text, old, new, label):
    if old not in text:
        raise SystemExit(f"v6.2.8 marker missing: {label}")
    return text.replace(old, new, 1)

# Replace the broad v6.2.7 scalar candidate heuristic with a smarter familiarity-oriented scan.
plan_path = "src/bridge/tactical_max_plan.rs"
plan = rd(plan_path)
old = r'''    let mut scalar_candidates: Vec<(u64, u16, u16, usize, u64)> = Vec::new();
    for off in (0xE0u64..=0x1FEu64).step_by(2) {
        let mut vals: Vec<u16> = Vec::with_capacity(matched_blocks.len());
        let mut valid = true;
        for &block in &matched_blocks {
            match fm.read_bytes(block + off, 2) {
                Ok(bytes) if bytes.len() == 2 => {
                    let v = u16::from_le_bytes([bytes[0], bytes[1]]);
                    if v > 10_000 { valid = false; break; }
                    vals.push(v);
                }
                _ => { valid = false; break; }
            }
        }
        if !valid || vals.is_empty() || vals.iter().all(|&v| v == 0) { continue; }
        let min = *vals.iter().min().unwrap();
        let max = *vals.iter().max().unwrap();
        let mut distinct = vals.clone();
        distinct.sort_unstable();
        distinct.dedup();
        if distinct.len() < 2 || min == max { continue; }
        let sum: u64 = vals.iter().map(|&v| v as u64).sum();
        scalar_candidates.push((off, min, max, distinct.len(), sum / vals.len() as u64));
    }
    scalar_candidates.sort_by(|a, b| {
        let ar = a.2.saturating_sub(a.1);
        let br = b.2.saturating_sub(b.1);
        br.cmp(&ar).then_with(|| a.0.cmp(&b.0))
    });
    plan.scalar_candidates = scalar_candidates.into_iter().take(12).map(|(off, min, max, distinct, avg)| {
        format!("+0x{off:X}: min={min} max={max} avg={avg} distinct={distinct}")
    }).collect();
'''
new = r'''    let mut scalar_candidates: Vec<(u64, u16, u16, usize, u64, u64)> = Vec::new();
    // Scan farther than v6.2.7. We still stay close to the known tactical object and
    // only perform reads. Familiarity-like fields should have a meaningful numeric
    // range and more than a binary/flag-style distribution across 26 players.
    for off in (0xE0u64..=0x5FEu64).step_by(2) {
        let mut vals: Vec<u16> = Vec::with_capacity(matched_blocks.len());
        let mut valid = true;
        for &block in &matched_blocks {
            match fm.read_bytes(block + off, 2) {
                Ok(bytes) if bytes.len() == 2 => {
                    let v = u16::from_le_bytes([bytes[0], bytes[1]]);
                    if v > 10_000 { valid = false; break; }
                    vals.push(v);
                }
                _ => { valid = false; break; }
            }
        }
        if !valid || vals.is_empty() || vals.iter().all(|&v| v == 0) { continue; }
        let min = *vals.iter().min().unwrap();
        let max = *vals.iter().max().unwrap();
        if max < 1_000 { continue; }
        let mut distinct = vals.clone();
        distinct.sort_unstable();
        distinct.dedup();
        if distinct.len() < 4 || min == max { continue; }
        let sum: u64 = vals.iter().map(|&v| v as u64).sum();
        let avg = sum / vals.len() as u64;
        let range = max.saturating_sub(min) as u64;
        // Score prefers broad spread, several unique values and a center of mass
        // inside the common FM familiarity band rather than tiny counters/flags.
        let centered = if (1_500..=9_500).contains(&avg) { 5_000 } else { 0 };
        let score = range * 8 + distinct.len() as u64 * 500 + centered;
        scalar_candidates.push((off, min, max, distinct.len(), avg, score));
    }
    scalar_candidates.sort_by(|a, b| b.5.cmp(&a.5).then_with(|| a.0.cmp(&b.0)));
    plan.scalar_candidates = scalar_candidates.into_iter().take(20).map(|(off, min, max, distinct, avg, score)| {
        format!("+0x{off:X}: min={min} max={max} avg={avg} distinct={distinct} score={score}")
    }).collect();
'''
plan = one(plan, old, new, "smart scalar probe")
wr(plan_path, plan)

app_path = "src/app.rs"
app = rd(app_path)
app = app.replace(
    '"no scalar candidates in +0xE0..+0x1FE".to_owned()',
    '"no familiarity-like scalar candidates in +0xE0..+0x5FE".to_owned()',
    1,
)
wr(app_path, app)

club_path = "src/ui/club_panel.rs"
club = rd(club_path)
needle = "v6.2.7 also performs a read-only scalar scan of the unused tactical-block window (+0xE0..+0x1FE) and reports the strongest varying 0..10000 candidates for missing FM27 fields such as In/Out of Possession Shape and Build Up."
replacement = "v6.2.8 performs a smarter read-only scalar scan (+0xE0..+0x5FE): low-range/binary candidates are rejected, at least four distinct player values are required, and wider familiarity-like 0..10000 distributions are ranked first for In/Out of Possession Shape and Build Up mapping."
if needle in club:
    club = club.replace(needle, replacement, 1)
wr(club_path, club)

print("Element v6.2.8 Tactical Smart Probe applied.")
