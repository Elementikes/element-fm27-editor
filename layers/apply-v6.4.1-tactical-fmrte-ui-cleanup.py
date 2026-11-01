from pathlib import Path

root = Path.cwd()

def rd(path):
    p = root / path
    if not p.exists():
        raise SystemExit(f"v6.4.1 missing {path}")
    return p.read_text(encoding="utf-8")

def wr(path, text):
    (root / path).write_text(text, encoding="utf-8")

p = root / "src" / "ui" / "club_panel.rs"
t = rd("src/ui/club_panel.rs")

# Promote the FMRTE-style surface as the primary Tactical Knowledge UI.
t = t.replace("v6.4.0 • FMRTE-STYLE TACTICAL KNOWLEDGE", "v6.4.1 • FMRTE-STYLE TACTICAL KNOWLEDGE", 1)
t = t.replace("FMRTE27 RESOURCE + LIVE MAP", "FMRTE27 LIVE BULK MODEL", 1)
t = t.replace("FIRST TEAM BULK WRITE CERTIFIED", "FIRST TEAM BULK WRITE LIVE", 1)

# Clarify the seven exposed FMRTE-style axes and the separate cohesion action.
old = 'ui.label(egui::RichText::new("(semantic found; cohesion writer not certified yet)").small().weak());'
new = 'ui.label(egui::RichText::new("(familiarity writer live • cohesion action mapped semantically, write still locked)").small().weak());'
t = t.replace(old, new, 1)

# Add a compact primary summary above the legacy raw viewer.
anchor = '    let mut overview_records = 0usize;\n'
if "FMRTE PRIMARY VIEW" not in t and anchor in t:
    block = r'''
    egui::Frame::group(ui.style()).show(ui, |ui| {
        ui.horizontal_wrapped(|ui| {
            ui.label(egui::RichText::new("FMRTE PRIMARY VIEW").strong().color(egui::Color32::from_rgb(112, 177, 255)));
            ui.separator();
            ui.label(egui::RichText::new("Selected club only • First Team").small().weak());
        });
        ui.add_space(4.0);
        ui.label(egui::RichText::new("The seven FMRTE-style Tactical Understanding axes are the supported bulk-edit surface. Legacy Instruction Group A–F cards below are raw diagnostics and should not be used as the user-facing familiarity source.").small());
        ui.add_space(4.0);
        ui.horizontal_wrapped(|ui| {
            ui.label(egui::RichText::new("MAX Tactical Familiarity").strong().color(egui::Color32::from_rgb(88, 214, 141)));
            ui.label("→");
            ui.label("6 instruction families + Position/Role");
            ui.separator();
            ui.label(egui::RichText::new("Improve Team Cohesion").strong().color(egui::Color32::from_rgb(255, 184, 77)));
            ui.label("→ write locked until independently mapped");
        });
    });
    ui.add_space(6.0);

'''
    t = t.replace(anchor, block + anchor, 1)

# Make legacy/raw section explicit rather than looking like the main feature.
for old_txt, new_txt in [
    ("OVERALL FAMILIARITY", "LEGACY RAW FAMILIARITY"),
    ("LIVE RECORDS", "RAW LIVE RECORDS"),
    ("COLLECTIONS", "RAW COLLECTIONS"),
]:
    t = t.replace(old_txt, new_txt)

# Update button tooltip/status language if present.
t = t.replace("Only the selected club. Planner verifies each player's live team pointer equals this club's SeniorTeam before creating normal undoable edits.",
              "Selected club only. Applies the mapped FMRTE-style familiarity writer to players whose live team pointer equals this club's SeniorTeam; edits remain undoable through Element.")

wr("src/ui/club_panel.rs", t)
print("Element v6.4.1 Tactical FMRTE UI cleanup applied.")
