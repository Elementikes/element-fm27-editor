from pathlib import Path

p = Path.cwd() / "src/ui/club_panel.rs"
if not p.exists():
    raise SystemExit("v7.5.1: club_panel.rs missing")
t = p.read_text(encoding="utf-8")

# fields_for_category() returns owned Field values; read_field_u8 expects &Field.
t = t.replace("crate::fields::read_field_u8(p, &p.raw, f)", "crate::fields::read_field_u8(p, &p.raw, &f)")

p.write_text(t, encoding="utf-8")
print("Element v7.5.1 Squads compile hotfix applied.")
