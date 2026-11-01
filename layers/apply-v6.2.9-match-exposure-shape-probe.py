from pathlib import Path

root = Path.cwd()

def rd(path):
    p = root / path
    if not p.exists():
        raise SystemExit(f"v6.2.9 missing {path}")
    return p.read_text(encoding="utf-8")

def wr(path, text):
    (root / path).write_text(text, encoding="utf-8")

def one(text, old, new, label):
    if old not in text:
        raise SystemExit(f"v6.2.9 marker missing: {label}")
    return text.replace(old, new, 1)

plan_path = "src/bridge/tactical_max_plan.rs"
plan = rd(plan_path)

# Keep the exact First Team player objects alongside tactical blocks so we can
# probe player-level context that may feed FM27's derived Shape/Match Exposure UI.
if "matched_players" not in plan:
    plan = one(
        plan,
        "    let mut seen = HashSet::new();\n    let mut matched_blocks: Vec<u64> = Vec::new();\n",
        "    let mut seen = HashSet::new();\n    let mut matched_blocks: Vec<u64> = Vec::new();\n    let mut matched_players: Vec<u64> = Vec::new();\n",
        "matched player vector",
    )
    plan = one(
        plan,
        "        matched_blocks.push(block);\n\n        for category in 0..CATEGORIES {\n",
        "        matched_blocks.push(block);\n        matched_players.push(player);\n\n        for category in 0..CATEGORIES {\n",
        "matched player push",
    )

marker = '''    plan.scalar_candidates = scalar_candidates.into_iter().take(20).map(|(off, min, max, distinct, avg, score)| {
        format!("+0x{off:X}: min={min} max={max} avg={avg} distinct={distinct} score={score}")
    }).collect();
'''

probe = r'''    plan.scalar_candidates = scalar_candidates.into_iter().take(12).map(|(off, min, max, distinct, avg, score)| {
        format!("TK+0x{off:X}: min={min} max={max} avg={avg} distinct={distinct} score={score}")
    }).collect();

    // v6.2.9: read-only player-context probe. FM27's In/Out of Possession Shape
    // appears not to be a simple scalar in the tactical block, so inspect the
    // player object itself for plausible match-exposure/comprehension state.
    // We intentionally require a distribution across the selected club's First
    // Team and never write any candidate discovered here.
    let mut player_u16: Vec<(u64, u16, u16, usize, u64, u64)> = Vec::new();
    for off in (0x00u64..=0x3FEu64).step_by(2) {
        // Skip known pointer slots and nearby bytes; interpreting pointer halves
        // as scalar candidates only creates noise.
        if (0xF8..=0x108).contains(&off) || (0x128..=0x138).contains(&off) { continue; }
        let mut vals: Vec<u16> = Vec::with_capacity(matched_players.len());
        let mut valid = true;
        for &player in &matched_players {
            match fm.read_bytes(player + off, 2) {
                Ok(bytes) if bytes.len() == 2 => {
                    let v = u16::from_le_bytes([bytes[0], bytes[1]]);
                    if v > 10_000 { valid = false; break; }
                    vals.push(v);
                }
                _ => { valid = false; break; }
            }
        }
        if !valid || vals.len() != matched_players.len() || vals.iter().all(|&v| v == 0) { continue; }
        let min = *vals.iter().min().unwrap();
        let max = *vals.iter().max().unwrap();
        let mut distinct = vals.clone();
        distinct.sort_unstable();
        distinct.dedup();
        if distinct.len() < 4 || min == max || max < 500 { continue; }
        let avg = vals.iter().map(|&v| v as u64).sum::<u64>() / vals.len() as u64;
        let range = max.saturating_sub(min) as u64;
        let centered = if (500..=9_500).contains(&avg) { 4_000 } else { 0 };
        let score = range * 6 + distinct.len() as u64 * 400 + centered;
        player_u16.push((off, min, max, distinct.len(), avg, score));
    }
    player_u16.sort_by(|a, b| b.5.cmp(&a.5).then_with(|| a.0.cmp(&b.0)));
    for (off, min, max, distinct, avg, score) in player_u16.into_iter().take(12) {
        plan.scalar_candidates.push(format!(
            "P16+0x{off:X}: min={min} max={max} avg={avg} distinct={distinct} score={score}"
        ));
    }

    let mut player_u8: Vec<(u64, u8, u8, usize, u64, u64)> = Vec::new();
    for off in 0x00u64..=0x3FFu64 {
        if (0xF8..=0x108).contains(&off) || (0x128..=0x138).contains(&off) { continue; }
        let mut vals: Vec<u8> = Vec::with_capacity(matched_players.len());
        let mut valid = true;
        for &player in &matched_players {
            match fm.read_bytes(player + off, 1) {
                Ok(bytes) if bytes.len() == 1 => {
                    let v = bytes[0];
                    if v > 100 { valid = false; break; }
                    vals.push(v);
                }
                _ => { valid = false; break; }
            }
        }
        if !valid || vals.len() != matched_players.len() || vals.iter().all(|&v| v == 0) { continue; }
        let min = *vals.iter().min().unwrap();
        let max = *vals.iter().max().unwrap();
        let mut distinct = vals.clone();
        distinct.sort_unstable();
        distinct.dedup();
        if distinct.len() < 4 || min == max || max < 20 { continue; }
        let avg = vals.iter().map(|&v| v as u64).sum::<u64>() / vals.len() as u64;
        let range = (max - min) as u64;
        let centered = if (20..=95).contains(&avg) { 2_000 } else { 0 };
        let score = range * 80 + distinct.len() as u64 * 250 + centered;
        player_u8.push((off, min, max, distinct.len(), avg, score));
    }
    player_u8.sort_by(|a, b| b.5.cmp(&a.5).then_with(|| a.0.cmp(&b.0)));
    for (off, min, max, distinct, avg, score) in player_u8.into_iter().take(12) {
        plan.scalar_candidates.push(format!(
            "P8+0x{off:X}: min={min} max={max} avg={avg} distinct={distinct} score={score}"
        ));
    }
'''

if "v6.2.9: read-only player-context probe" not in plan:
    plan = one(plan, marker, probe, "player context probe insertion")
wr(plan_path, plan)

app_path = "src/app.rs"
app = rd(app_path)
app = app.replace(
    '"no familiarity-like scalar candidates in +0xE0..+0x5FE".to_owned()',
    '"no tactical-block or player-context scalar candidates".to_owned()',
    1,
)
wr(app_path, app)

club_path = "src/ui/club_panel.rs"
club = rd(club_path)
needle = "v6.2.8 performs a smarter read-only scalar scan (+0xE0..+0x5FE): low-range/binary candidates are rejected, at least four distinct player values are required, and wider familiarity-like 0..10000 distributions are ranked first for In/Out of Possession Shape and Build Up mapping."
replacement = needle + " v6.2.9 additionally probes the selected First Team player objects read-only for u16 0..10000 and u8 0..100 distributions that may represent Match Exposure / Shape comprehension. Candidate prefixes: TK=tactical block, P16=player u16, P8=player u8."
if needle in club and replacement not in club:
    club = club.replace(needle, replacement, 1)
wr(club_path, club)

print("Element v6.2.9 Match Exposure / Shape Probe applied.")
