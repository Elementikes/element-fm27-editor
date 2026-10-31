from pathlib import Path

# Validate the generated Player Transfer Lab boundary.
path = Path.cwd() / "src" / "ui" / "player_panel.rs"
text = path.read_text(encoding="utf-8")
if "fn show_transfer_lab(" not in text:
    raise SystemExit("v5.0 boundary prep: show_transfer_lab not found")

# The v5 layer originally compared the entire helper block byte-for-byte.
# Generated overlays can preserve equivalent code with different surrounding
# comments/line endings, so normalize that one insertion rule to a function
# marker check before executing the layer.
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
layer.write_text(head + tail, encoding="utf-8")

print("v5.0 boundary prep completed: Transfer Lab helper insertion is marker-based.")
