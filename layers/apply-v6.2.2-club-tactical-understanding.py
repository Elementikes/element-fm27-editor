from pathlib import Path
import shutil

root = Path.cwd()
repo = Path(__file__).resolve().parent.parent

for name in ["club-surface.json", "tactical-understanding.json"]:
    src = repo / "config" / "element-v6" / name
    if not src.exists():
        raise SystemExit(f"v6.2.2: missing {src}")
    dst = root / "src" / "element_data" / name
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)

p = root / "src" / "element_config.rs"
t = p.read_text(encoding="utf-8")
marker = 'pub fn probe_targets() -> Value { load_value("probe-targets.json", include_str!("element_data/probe-targets.json")) }\n'
if 'pub fn club_surface()' not in t:
    add = marker + 'pub fn club_surface() -> Value { load_value("club-surface.json", include_str!("element_data/club-surface.json")) }\n' + 'pub fn tactical_understanding() -> Value { load_value("tactical-understanding.json", include_str!("element_data/tactical-understanding.json")) }\n'
    if marker not in t: raise SystemExit("v6.2.2: config marker missing")
    t = t.replace(marker, add, 1)

if 'Club surface' not in t:
    needle = '    if let Some(targets) = probes.get("targets").and_then(Value::as_array) {'
    block = r'''
    let club = club_surface();
    egui::CollapsingHeader::new("Club surface").default_open(true).show(ui, |ui| {
        if let Some(tabs) = club.get("tabs").and_then(Value::as_array) {
            egui::Grid::new("v622_club_surface_grid").striped(true).num_columns(3).show(ui, |ui| {
                ui.strong("Club tab"); ui.strong("Status"); ui.strong("Element"); ui.end_row();
                for row in tabs {
                    let label = row.get("label").and_then(Value::as_str).unwrap_or("?");
                    let status = row.get("status").and_then(Value::as_str).unwrap_or("unknown");
                    ui.label(label);
                    ui.label(status);
                    ui.label(match status { "mapped" => "AVAILABLE", "partial" => "PARTIAL", _ => "PROBE READY" });
                    ui.end_row();
                }
            });
        }
    });

    let tu = tactical_understanding();
    egui::CollapsingHeader::new("Tactical Understanding").default_open(true).show(ui, |ui| {
        if let Some(scopes) = tu.get("squadScopes").and_then(Value::as_array) {
            ui.horizontal_wrapped(|ui| {
                ui.strong("Squads:");
                for s in scopes.iter().filter_map(Value::as_str) { ui.label(s); }
            });
        }
        if let Some(groups) = tu.get("groups").and_then(Value::as_array) {
            for group in groups {
                let label = group.get("label").and_then(Value::as_str).unwrap_or("?");
                ui.add_space(4.0); ui.strong(label);
                if let Some(metrics) = group.get("metrics").and_then(Value::as_array) {
                    for metric in metrics {
                        let name = metric.get("label").and_then(Value::as_str).unwrap_or("?");
                        let status = metric.get("status").and_then(Value::as_str).unwrap_or("probe-ready");
                        ui.horizontal(|ui| { ui.label(name); ui.separator(); ui.label(status); ui.separator(); ui.label("0..100"); });
                    }
                }
            }
        }
        ui.add_space(4.0);
        ui.label(egui::RichText::new("Read/write remains gated until the FM27 tactical-understanding record is witnessed. Raw keys stay Developer-only.").small().weak());
    });

'''
    if needle not in t: raise SystemExit("v6.2.2: semantic lab insertion marker missing")
    t = t.replace(needle, block + needle, 1)

p.write_text(t, encoding="utf-8")
print("Element v6.2.2 club surface + tactical understanding applied successfully.")
