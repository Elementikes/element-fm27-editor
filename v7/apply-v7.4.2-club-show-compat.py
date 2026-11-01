from pathlib import Path

p = Path.cwd() / "src/ui/club_panel.rs"
if not p.exists():
    raise SystemExit("v7.4.2: src/ui/club_panel.rs missing")
t = p.read_text(encoding="utf-8")

# v7.5 historically searches for the literal `pub fn show`. Current upstream
# intentionally uses `pub(crate) fn show`; widening this one UI helper to pub is
# harmless and keeps the downstream patch idempotent without changing behavior.
if "pub fn show(" not in t:
    old = "pub(crate) fn show("
    if old not in t:
        raise SystemExit("v7.4.2: club show function marker missing")
    t = t.replace(old, "pub fn show(", 1)

p.write_text(t, encoding="utf-8")
print("Element v7.4.2 Club show compatibility shim applied.")
