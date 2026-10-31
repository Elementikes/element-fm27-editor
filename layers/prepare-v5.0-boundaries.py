from pathlib import Path

# The generated Transfer Lab must exist before v5.0, but the v5 core layer
# should not patch its large UI block. Player UI is applied by a dedicated,
# marker-based layer after the transaction/core layer.
path = Path.cwd() / "src" / "ui" / "player_panel.rs"
text = path.read_text(encoding="utf-8")
if "fn show_transfer_lab(" not in text:
    raise SystemExit("v5.0 boundary prep: show_transfer_lab not found")

layer = Path(__file__).resolve().parent / "apply-v5.0-force-transfer.py"
source = layer.read_text(encoding="utf-8")
start_marker = "# ---------- player_panel.rs ----------"
end_marker = "# ---------- club_panel squad layout ----------"
start = source.find(start_marker)
end = source.find(end_marker, start + 1)
if start < 0 or end < 0 or end <= start:
    raise SystemExit("v5.0 boundary prep: player UI section boundaries missing")
source = (
    source[:start]
    + "# ---------- player_panel.rs ----------\n# Player UI is applied by apply-v5.0-player-ui.py\n\n"
    + source[end:]
)
layer.write_text(source, encoding="utf-8")
print("v5.0 boundary prep completed: core transaction layer detached from Player UI patching.")
