from pathlib import Path

repo = Path(__file__).resolve().parent.parent
source = repo / "layers" / "apply-v6.1-player-data-hub.py"
text = source.read_text(encoding="utf-8")
marker = "# Add Data Hub as a native Player sub-tab."
if marker not in text:
    raise SystemExit("v6.1 core: source boundary missing")
prefix = text.split(marker, 1)[0]
exec(compile(prefix, str(source), "exec"), {"__file__": str(source), "__name__": "__element_v61_core__"})
print("Element v6.1 Player Data Hub core installed successfully.")
