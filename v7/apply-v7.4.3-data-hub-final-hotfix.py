from pathlib import Path

p = Path.cwd() / "src/ui/player_data_hub.rs"
if not p.exists():
    raise SystemExit("v7.4.3: player_data_hub.rs missing")
t = p.read_text(encoding="utf-8")

old = "schemas.fields_for_category(Entity::Player,category).find(|f|f.label==metric)"
new = "schemas.fields_for_category(Entity::Player,category).into_iter().find(|f|f.label==metric)"
if old in t:
    t = t.replace(old, new, 1)
elif new not in t:
    raise SystemExit("v7.4.3: Data Hub metric lookup marker missing")

p.write_text(t, encoding="utf-8")
print("Element v7.4.3 Data Hub final compile hotfix applied.")
