from pathlib import Path

root = Path.cwd()

def rd(path):
    p = root / path
    if not p.exists():
        raise SystemExit(f"v6.2.7 missing {path}")
    return p.read_text(encoding="utf-8")

def wr(path, text):
    (root / path).write_text(text, encoding="utf-8")

def one(text, old, new, label):
    if old not in text:
        raise SystemExit(f"v6.2.7 marker missing: {label}")
    return text.replace(old, new, 1)

# Extend the prepared plan with a compact read-only candidate report.
cmd_path = "src/bridge/cmd.rs"
cmd = rd(cmd_path)
if "pub scalar_candidates: Vec<String>" not in cmd:
    cmd = one(
        cmd,
        "    pub already_maxed: usize,\n    pub edits: Vec<TacticalMaxPlannedEdit>,\n",
        "    pub already_maxed: usize,\n    pub scalar_candidates: Vec<String>,\n    pub edits: Vec<TacticalMaxPlannedEdit>,\n",
        "TacticalMaxPlan scalar candidates",
    )
wr(cmd_path, cmd)

plan_path = "src/bridge/tactical_max_plan.rs"
plan = rd(plan_path)
if "matched_blocks" not in plan:
    plan = one(
        plan,
        "    let mut seen = HashSet::new();\n\n    for &player in player_addrs {\n",
        "    let mut seen = HashSet::new();\n    let mut matched_blocks: Vec<u64> = Vec::new();\n\n    for &player in player_addrs {\n",
        "matched tactical block collection",
    )
    plan = one(
        plan,
        "        if !is_valid_ptr(block) {\n            return Err(format!(\"first-team player 0x{player:X} has no valid tactical block\"));\n        }\n\n        for category in 0..CATEGORIES {\n",
        "        if !is_valid_ptr(block) {\n            return Err(format!(\"first-team player 0x{player:X} has no valid tactical block\"));\n        }\n        matched_blocks.push(block);\n\n        for category in 0..CATEGORIES {\n",
        "store matched tactical block",
    )

probe = r'''
    // Read-only probe for FM27 tactical fields not covered by the six instruction
    // vectors or the formation/role vector. We scan a conservative scalar window
    // immediately after the known 0xE0-byte header. Candidate offsets must be
    // readable for every matched player, fit the familiar 0..10000 scale, be
    // non-zero somewhere, and vary across players. No writes are performed here.
    let mut scalar_candidates: Vec<(u64, u16, u16, usize, u64)> = Vec::new();
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

if "Read-only probe for FM27 tactical fields" not in plan:
    plan = one(
        plan,
        "    if plan.players_matched == 0 {\n        return Err(\"no cached player currently belongs to the selected club First Team; reload club/save\".into());\n    }\n    Ok(plan)\n",
        probe + "\n    if plan.players_matched == 0 {\n        return Err(\"no cached player currently belongs to the selected club First Team; reload club/save\".into());\n    }\n    Ok(plan)\n",
        "scalar probe insertion",
    )
wr(plan_path, plan)

# Surface the top candidates in the normal status line so the user can screenshot them.
app_path = "src/app.rs"
app = rd(app_path)
old = '''                    let total_entries = plan.instruction_entries + plan.formation_rows;
                    let summary = format!(
                        "Tactical MAX prepared: {} First Team players, {} edits | {} instruction + {} formation/role = {} entries | {} already read as MAX",
                        plan.players_matched,
                        plan.edits.len(),
                        plan.instruction_entries,
                        plan.formation_rows,
                        total_entries,
                        plan.already_maxed,
                    );
'''
new = '''                    let total_entries = plan.instruction_entries + plan.formation_rows;
                    let candidates = if plan.scalar_candidates.is_empty() {
                        "no scalar candidates in +0xE0..+0x1FE".to_owned()
                    } else {
                        plan.scalar_candidates.join(" ; ")
                    };
                    let summary = format!(
                        "Tactical MAX prepared: {} First Team players, {} edits | {} instruction + {} formation/role = {} entries | {} already MAX | missing-field probe: {}",
                        plan.players_matched,
                        plan.edits.len(),
                        plan.instruction_entries,
                        plan.formation_rows,
                        total_entries,
                        plan.already_maxed,
                        candidates,
                    );
'''
app = one(app, old, new, "status candidate report")
wr(app_path, app)

# Clarify the UI purpose of this build.
club_path = "src/ui/club_panel.rs"
club = rd(club_path)
needle = "A zero-edit plan now reports how many discovered entries already decode as MAX; if every discovered entry is MAX while FM27 still shows low Tactical Understanding, the per-player field semantics need remapping rather than forcing a write."
extra = needle + " v6.2.7 also performs a read-only scalar scan of the unused tactical-block window (+0xE0..+0x1FE) and reports the strongest varying 0..10000 candidates for missing FM27 fields such as In/Out of Possession Shape and Build Up."
if needle in club and extra not in club:
    club = club.replace(needle, extra, 1)
wr(club_path, club)

print("Element v6.2.7 Tactical Missing Fields Probe applied.")
