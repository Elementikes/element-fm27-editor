from pathlib import Path
import shutil

root = Path.cwd()
repo = Path(__file__).resolve().parent.parent

src = repo / "config" / "element-v6" / "player-surface.json"
if not src.exists():
    raise SystemExit(f"v6.2.3: missing {src}")
dst = root / "src" / "element_data" / "player-surface.json"
dst.parent.mkdir(parents=True, exist_ok=True)
shutil.copy2(src, dst)

p = root / "src" / "element_config.rs"
t = p.read_text(encoding="utf-8")

if "pub fn player_surface()" not in t:
    marker = 'pub fn probe_targets() -> Value { load_value("probe-targets.json", include_str!("element_data/probe-targets.json")) }\n'
    add = marker + 'pub fn player_surface() -> Value { load_value("player-surface.json", include_str!("element_data/player-surface.json")) }\n'
    if marker not in t:
        raise SystemExit("v6.2.3: probe_targets marker missing")
    t = t.replace(marker, add, 1)

anchor = '    if let Some(targets) = probes.get("targets").and_then(Value::as_array) {\n'
if "PLAYER FULL SURFACE • v6.2.3" not in t:
    block = r'''
    egui::CollapsingHeader::new("PLAYER FULL SURFACE • v6.2.3").default_open(true).show(ui, |ui| {
        let surface = player_surface();
        ui.label(egui::RichText::new("Every FMRTE27-equivalent player area is represented below. Mapped/certified controls are live; probe-ready controls stay gated until cross-witnessed.").small().weak());
        ui.add_space(4.0);
        if let Some(sections) = surface.get("sections").and_then(Value::as_array) {
            for section in sections {
                let label = section.get("label").and_then(Value::as_str).unwrap_or("?");
                let mode = section.get("mode").and_then(Value::as_str).unwrap_or("unknown");
                egui::CollapsingHeader::new(format!("{}   [{}]", label, mode)).show(ui, |ui| {
                    if let Some(fields) = section.get("fields").and_then(Value::as_array) {
                        ui.horizontal_wrapped(|ui| {
                            for field in fields.iter().filter_map(Value::as_str) {
                                ui.label(egui::RichText::new(field).small());
                                ui.separator();
                            }
                        });
                    }
                });
            }
        }
        if let Some(rel) = surface.get("relationshipEditor") {
            ui.separator();
            ui.label(egui::RichText::new("Relationships editor target").strong());
            if let Some(cols) = rel.get("columns").and_then(Value::as_array) {
                ui.horizontal_wrapped(|ui| {
                    for col in cols.iter().filter_map(Value::as_str) {
                        ui.label(egui::RichText::new(col).small());
                    }
                });
            }
            if let Some(map) = rel.get("reasonMapping").and_then(Value::as_object) {
                for (raw, value) in map {
                    ui.label(format!("{} → {}", raw, value.as_str().unwrap_or("?")));
                }
            }
        }
    });

'''
    if anchor not in t:
        raise SystemExit("v6.2.3: semantic lab target anchor missing")
    t = t.replace(anchor, block + anchor, 1)

p.write_text(t, encoding="utf-8")
print("Element v6.2.3 Player Full Surface applied successfully.")
