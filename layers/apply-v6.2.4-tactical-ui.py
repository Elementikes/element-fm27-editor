from pathlib import Path

root = Path.cwd()
p = root / "src" / "element_config.rs"
t = p.read_text(encoding="utf-8")

old = '''        ui.add_space(4.0);
        ui.label(egui::RichText::new("Read/write remains gated until the FM27 tactical-understanding record is witnessed. Raw keys stay Developer-only.").small().weak());
'''
new = '''        ui.add_space(8.0);
        egui::Frame::group(ui.style()).show(ui, |ui| {
            ui.label(egui::RichText::new("FULL TACTICAL KNOWLEDGE").strong());
            ui.horizontal_wrapped(|ui| {
                ui.add_enabled(false, egui::Button::new("MAX CURRENT SQUAD • 100"));
                ui.add_enabled(false, egui::Button::new("MAX ALL SQUADS • 100"));
                ui.label(egui::RichText::new("LOCKED UNTIL 7/7 LIVE CERTIFICATION").small().weak());
            });
            ui.label(egui::RichText::new("Target: Passing Style, Build Up, Chance Creation, Line of Engagement, Pressing Intensity, Pressing Trap and Position/Role all become 100 with read-back verification and rollback on mismatch.").small());
        });
        ui.add_space(4.0);
        ui.label(egui::RichText::new("Certification workflow: capture current squad → apply Max Tactical Familiarity in FMRTE → compare. Once the seven fields are witnessed, the MAX buttons are enabled through Element's verified write path. Raw keys stay Developer-only.").small().weak());
'''
if old not in t:
    raise SystemExit("v6.2.4 tactical UI marker missing")
t = t.replace(old, new, 1)
p.write_text(t, encoding="utf-8")
print("Element v6.2.4 tactical max workflow UI applied successfully.")
