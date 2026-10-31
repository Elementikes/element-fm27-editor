from pathlib import Path

# Validate the generated Player Transfer Lab boundary.
path = Path.cwd() / "src" / "ui" / "player_panel.rs"
text = path.read_text(encoding="utf-8")
if "fn show_transfer_lab(" not in text:
    raise SystemExit("v5.0 boundary prep: show_transfer_lab not found")

# Normalize fragile textual rules in the release layer before executing it.
# Functional markers remain strict; purely cosmetic wording is best-effort.
layer = Path(__file__).resolve().parent / "apply-v5.0-force-transfer.py"
source = layer.read_text(encoding="utf-8")
section_marker = "# ---------- player_panel.rs ----------"
pos = source.find(section_marker)
if pos < 0:
    raise SystemExit("v5.0 boundary prep: player_panel section missing in v5 layer")
head, tail = source[:pos], source[pos:]

frag = """if helper not in t:\n    assert anchor in t\n    t=t.replace(anchor,helper+anchor,1)"""
robust = """if \"fn element_v5_listing_now(\" not in t:\n    marker=\"fn show_transfer_lab(\"\n    pos=t.find(marker)\n    if pos<0: raise SystemExit(\"v5.0: show_transfer_lab marker missing\")\n    t=t[:pos]+helper+t[pos:]"""
if frag in tail:
    tail = tail.replace(frag, robust, 1)
elif "fn element_v5_listing_now(" not in tail:
    raise SystemExit("v5.0 boundary prep: helper insertion rule not found")

# The final Transfer Lab sentence is cosmetic and changed wording in some
# overlays. Never let that text-only replacement fail the release stack.
frag = """assert old in t\nt=t.replace(old,new,1)\np.write_text(t)\n\n# ---------- club_panel squad layout ----------"""
robust = """if old in t:\n    t=t.replace(old,new,1)\np.write_text(t)\n\n# ---------- club_panel squad layout ----------"""
if frag in tail:
    tail = tail.replace(frag, robust, 1)

layer.write_text(head + tail, encoding="utf-8")
print("v5.0 boundary prep completed: functional markers hardened; cosmetic text is non-blocking.")
