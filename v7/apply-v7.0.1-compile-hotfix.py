from pathlib import Path

p = Path.cwd() / "src/ui/club_panel.rs"
t = p.read_text(encoding="utf-8")
old = 'edits.push(FieldEdit { addr:e.addr, old_raw:e.old_raw, new_raw:e.new_raw, description:e.description });'
new = 'edits.push(FieldEdit { addr:e.addr, old_raw:e.old_raw, new_raw:e.new_raw, description:e.description, presentation: None });'
if old not in t:
    if new in t:
        print("Element v7.0.1 hotfix already applied.")
        raise SystemExit(0)
    raise SystemExit("v7.0.1: Tactical FieldEdit initializer marker not found")
t = t.replace(old, new, 1)
p.write_text(t, encoding="utf-8")
print("Element v7.0.1 compile hotfix applied.")
