from pathlib import Path

root = Path.cwd()


def rd(path):
    p = root / path
    if not p.exists():
        raise SystemExit(f"v6.6.1 missing {path}")
    return p.read_text(encoding="utf-8")


def wr(path, text):
    (root / path).write_text(text, encoding="utf-8")


# process_results needs egui Context because v6.6 stores differential results
# in egui temp data for the selected Club Tactical Knowledge surface.
p = "src/app.rs"
t = rd(p)
if "fn process_results(&mut self, ctx: &egui::Context)" not in t:
    old = "    fn process_results(&mut self) {"
    if old not in t:
        raise SystemExit("v6.6.1: process_results signature marker missing")
    t = t.replace(old, "    fn process_results(&mut self, ctx: &egui::Context) {", 1)

if "self.process_results(ctx);" not in t:
    old = "        self.process_results();"
    if old not in t:
        raise SystemExit("v6.6.1: process_results call marker missing")
    t = t.replace(old, "        self.process_results(ctx);", 1)
wr(p, t)

# Re-export the report type used by club_panel.rs.
p = "src/bridge/mod.rs"
t = rd(p)
if "pub use cmd::TeamCohesionDeltaReport;" not in t:
    t = t.rstrip() + "\n\npub use cmd::TeamCohesionDeltaReport;\n"
wr(p, t)

print("Element v6.6.1 IL2CPP certifier compile hotfix applied.")
