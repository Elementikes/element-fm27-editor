from pathlib import Path

root = Path.cwd()

def rd(path):
    p = root / path
    if not p.exists():
        raise SystemExit(f"v6.2.6.2 missing {path}")
    return p.read_text(encoding="utf-8")

def wr(path, text):
    (root / path).write_text(text, encoding="utf-8")

def one(text, old, new, label):
    if old not in text:
        raise SystemExit(f"v6.2.6.2 marker missing: {label}")
    return text.replace(old, new, 1)

# Surface the already-existing planner diagnostics so zero-edit plans are explainable.
app_path = "src/app.rs"
app = rd(app_path)
old = '''                    let summary = format!(
                        "Tactical MAX prepared: {} First Team players, {} edits ({} instruction entries, {} formation/role rows)",
                        plan.players_matched, plan.edits.len(), plan.instruction_entries, plan.formation_rows,
                    );
'''
new = '''                    let total_entries = plan.instruction_entries + plan.formation_rows;
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
app = one(app, old, new, "tactical MAX status diagnostics")
wr(app_path, app)

# Make the tactical page explain what a 0-edit plan means.
club_path = "src/ui/club_panel.rs"
club = rd(club_path)
needle = "MAX FIRST TEAM uses the live per-player FM27 tactical block and the normal Element compare-before-write + Undo pipeline. It only accepts players whose live team pointer equals the selected club SeniorTeam. B Team/U19 stay locked until team-type mapping is certified."
replacement = needle + " A zero-edit plan now reports how many discovered entries already decode as MAX; if every discovered entry is MAX while FM27 still shows low Tactical Understanding, the per-player field semantics need remapping rather than forcing a write."
if needle in club and replacement not in club:
    club = club.replace(needle, replacement, 1)
wr(club_path, club)

print("Element v6.2.6.2 Tactical MAX diagnostics applied.")
