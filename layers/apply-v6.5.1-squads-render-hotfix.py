from pathlib import Path

root = Path.cwd()
path = root / "src/ui/club_panel.rs"
if not path.exists():
    raise SystemExit("v6.5.1: src/ui/club_panel.rs missing")

t = path.read_text(encoding="utf-8")
start = t.find("fn show_squad_action_bar(")
end = t.find("\nfn show_squads(", start)
if start < 0 or end < 0:
    raise SystemExit("v6.5.1: squad action bar boundaries not found")

block = t[start:end]
old_count = block.count("ui.horizontal_centered(|ui| {")
if old_count == 0:
    if "v6.5.1 compact squad action bar" not in block:
        raise SystemExit("v6.5.1: expected horizontal_centered layout not found")
else:
    # horizontal_centered can consume the parent's available cross-axis height in
    # this ScrollArea-adjacent layout. That made the action deck fill most of the
    # viewport and pushed the actual roster rows below the visible screen.
    # horizontal_wrapped sizes to content and preserves all existing controls.
    block = block.replace("ui.horizontal_centered(|ui| {", "ui.horizontal_wrapped(|ui| {")

    marker = "fn show_squad_action_bar(\n"
    comment = "// v6.5.1 compact squad action bar: never consume roster viewport height.\n"
    if comment not in block:
        block = block.replace(marker, comment + marker, 1)

    t = t[:start] + block + t[end:]
    path.write_text(t, encoding="utf-8")

print(f"Element v6.5.1 Squads render hotfix applied: replaced {old_count} horizontal_centered layouts.")
