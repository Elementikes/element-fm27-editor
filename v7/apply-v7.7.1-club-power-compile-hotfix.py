from pathlib import Path

p = Path.cwd() / "src/ui/club_panel.rs"
if not p.exists():
    raise SystemExit("v7.7.1: club_panel.rs missing")
t = p.read_text(encoding="utf-8")

old_call = "        ClubTab::PowerTools => show_power_tools(ui, club, &mut edits, writable, entity_cache),"
new_call = "        ClubTab::PowerTools => show_power_tools(schemas, ui, club, &mut edits, writable, entity_cache),"
if old_call in t:
    t = t.replace(old_call, new_call, 1)
elif new_call not in t:
    raise SystemExit("v7.7.1: PowerTools call marker missing")

old_sig = "fn show_power_tools(\n    ui: &mut egui::Ui,"
new_sig = "fn show_power_tools(\n    schemas: &'static crate::fields::VersionedSchemas,\n    ui: &mut egui::Ui,"
if old_sig in t:
    t = t.replace(old_sig, new_sig, 1)
elif new_sig not in t:
    raise SystemExit("v7.7.1: PowerTools signature marker missing")

t = t.replace("club.build.schemas()", "schemas")

p.write_text(t, encoding="utf-8")
print("Element v7.7.1 Club Power compile hotfix applied.")
