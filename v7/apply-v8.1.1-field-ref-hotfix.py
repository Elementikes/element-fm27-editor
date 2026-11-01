from pathlib import Path

root = Path.cwd()

fixes = [
    (
        "src/ui/player_panel.rs",
        "fields::read_field_u8(obj,raw,f)",
        "fields::read_field_u8(obj,raw,&f)",
        "player category score Field reference",
    ),
    (
        "src/ui/staff_panel.rs",
        "crate::fields::read_field_u8(&staff.record,&staff.record.raw,f)",
        "crate::fields::read_field_u8(&staff.record,&staff.record.raw,&f)",
        "staff category score Field reference",
    ),
]

for rel, old, new, label in fixes:
    path = root / rel
    if not path.exists():
        raise SystemExit(f"v8.1.1 missing {rel}")
    text = path.read_text(encoding="utf-8")
    if new in text:
        print(f"v8.1.1 already applied: {label}")
        continue
    if old not in text:
        raise SystemExit(f"v8.1.1 marker missing: {label}")
    path.write_text(text.replace(old, new, 1), encoding="utf-8")
    print(f"v8.1.1 fixed: {label}")

print("Element v8.1.1 Field-reference compile hotfix applied.")
