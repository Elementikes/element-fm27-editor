from pathlib import Path

root = Path.cwd()

def rd(path):
    p = root / path
    if not p.exists():
        raise SystemExit(f"v6.4.2 missing {path}")
    return p.read_text(encoding="utf-8")

def wr(path, text):
    (root / path).write_text(text, encoding="utf-8")

path = "src/ui/club_panel.rs"
t = rd(path)

# Version / status language.
t = t.replace("v6.4.1 • FMRTE-STYLE TACTICAL KNOWLEDGE", "v6.4.2 • FMRTE TACTICAL CHAIN", 1)
t = t.replace("FMRTE27 LIVE BULK MODEL", "FMRTE27 VERIFIED + DERIVED MODEL", 1)
t = t.replace("FIRST TEAM BULK WRITE LIVE", "FAMILIARITY WRITE VERIFIED", 1)

# The seven FMRTE-style rows were previously labelled uniformly as MAPPED BULK.
# The live FM27 witnesses show that three UI indicators remain derived/contextual
# after the underlying familiarity vectors are maxed. Make that distinction explicit.
old_rows = '''                    for axis in [
                        "Passing Style", "Build Up", "Chance Creation",
                        "Line of Engagement", "Pressing Intensity", "Pressing Trap", "Position/Role",
                    ] {
                        ui.label(axis);
                        ui.label("100");
                        ui.label(egui::RichText::new("MAPPED BULK").small().color(egui::Color32::from_rgb(255, 184, 77)));
                        ui.end_row();
                    }
'''
new_rows = '''                    for (axis, status, color) in [
                        ("Passing Style", "FAMILIARITY WRITE / FM27 DERIVED DISPLAY", egui::Color32::from_rgb(255, 184, 77)),
                        ("Build Up", "FAMILIARITY WRITE / FM27 DERIVED DISPLAY", egui::Color32::from_rgb(255, 184, 77)),
                        ("Chance Creation", "WRITE VERIFIED", egui::Color32::from_rgb(88, 214, 141)),
                        ("Line of Engagement", "WRITE VERIFIED", egui::Color32::from_rgb(88, 214, 141)),
                        ("Pressing Intensity", "WRITE VERIFIED", egui::Color32::from_rgb(88, 214, 141)),
                        ("Pressing Trap", "WRITE VERIFIED", egui::Color32::from_rgb(88, 214, 141)),
                        ("Position/Role", "WRITE VERIFIED", egui::Color32::from_rgb(88, 214, 141)),
                    ] {
                        ui.label(axis);
                        ui.label("100");
                        ui.label(egui::RichText::new(status).small().color(color));
                        ui.end_row();
                    }
'''
if old_rows in t:
    t = t.replace(old_rows, new_rows, 1)

# Clarify FMRTE chain and avoid implying cohesion is already writable.
t = t.replace(
    '(familiarity writer live • cohesion action mapped semantically, write still locked)',
    '(MaxTacticalFamiliarity verified • ImproveTeamCohesion identified from FMRTE resources, write intentionally locked)',
    1,
)

# Better button naming: this is the verified action we actually execute.
t = t.replace("⚡ FMRTE MAX FIRST TEAM • 100", "⚡ MAX TACTICAL FAMILIARITY • FIRST TEAM", 1)

# Add an explicit full-chain button next to the verified MAX if not already present.
needle = 'ui.add_enabled(false, egui::Button::new("MAX B TEAM • 100"))'
if "FULL FMRTE CHAIN" not in t and needle in t:
    add = '''ui.add_enabled(false, egui::Button::new("⚡ FULL FMRTE CHAIN • COHESION LOCKED"))
                    .on_disabled_hover_text("FMRTE resource chain is MaxTacticalFamiliarity → ImproveTeamCohesion. Familiarity is verified; cohesion has no certified FM27 write mapping yet, so Element refuses a blind write.");
                '''
    t = t.replace(needle, add + needle, 1)

# Primary-view explanation based on the three independent FM27 witnesses.
t = t.replace(
    "The seven FMRTE-style Tactical Understanding axes are the supported bulk-edit surface. Legacy Instruction Group A–F cards below are raw diagnostics and should not be used as the user-facing familiarity source.",
    "FMRTE exposes seven Tactical Understanding axes. Element writes the verified underlying familiarity vectors; FM27 still derives some visible In-Possession indicators from additional context. Blind writes to unknown context fields remain blocked.",
    1,
)
t = t.replace(
    "6 instruction families + Position/Role",
    "verified familiarity vectors • selected First Team only",
    1,
)

# Make the observed FM27 gap visible in the primary view.
anchor = '        ui.horizontal_wrapped(|ui| {\n            ui.label(egui::RichText::new("MAX Tactical Familiarity")'
if "Observed FM27 after MAX:" not in t and anchor in t:
    block = '''        ui.horizontal_wrapped(|ui| {
            ui.label(egui::RichText::new("Observed FM27 after MAX:").strong());
            ui.label(egui::RichText::new("Chance Creation • Line of Engagement • Pressing Intensity • Pressing Trap • Position/Role").color(egui::Color32::from_rgb(88, 214, 141)));
            ui.label("write-verified;");
            ui.label(egui::RichText::new("In Possession Shape • Passing Style • Build Up").color(egui::Color32::from_rgb(255, 184, 77)));
            ui.label("remain context-derived / partial in FM27.");
        });
        ui.add_space(3.0);
'''
    t = t.replace(anchor, block + anchor, 1)

wr(path, t)
print("Element v6.4.2 FMRTE tactical chain hardening applied.")
