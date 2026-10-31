from pathlib import Path

path = Path.cwd() / "src" / "ui" / "player_panel.rs"
text = path.read_text(encoding="utf-8")

anchor = "// ---------------------------------------------------------------------------\n// Transfer Lab — Element FM27\n// ---------------------------------------------------------------------------\n"
if anchor not in text:
    marker = "fn show_transfer_lab("
    pos = text.find(marker)
    if pos < 0:
        raise SystemExit("v5.0 boundary prep: show_transfer_lab not found")
    text = text[:pos] + anchor + text[pos:]

path.write_text(text, encoding="utf-8")
print("v5.0 boundary prep completed.")
