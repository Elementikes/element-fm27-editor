from pathlib import Path
import shutil

root = Path.cwd()
repo = Path(__file__).resolve().parent.parent

for name in ["fm27-semantics.json", "probe-targets.json"]:
    src = repo / "config" / "element-v6" / name
    if not src.exists():
        raise SystemExit(f"v6.2 semantic lab: missing {src}")
    dst = root / "src" / "element_data" / name
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)

p = root / "src" / "element_config.rs"
t = p.read_text(encoding="utf-8")
if "pub fn fm27_semantics()" not in t:
    marker = 'pub fn tactics() -> Value { load_value("tactics.json", include_str!("element_data/tactics.json")) }\n'
    add = marker + 'pub fn fm27_semantics() -> Value { load_value("fm27-semantics.json", include_str!("element_data/fm27-semantics.json")) }\n' + 'pub fn probe_targets() -> Value { load_value("probe-targets.json", include_str!("element_data/probe-targets.json")) }\n'
    if marker not in t: raise SystemExit("v6.2: element_config tactics marker missing")
    t = t.replace(marker, add, 1)

if "show_semantic_lab" not in t:
    t += r'''

pub fn show_semantic_lab(ui: &mut egui::Ui) {
    let sem = fm27_semantics();
    let probes = probe_targets();
    ui.horizontal(|ui| {
        ui.label(egui::RichText::new("FM27 SEMANTIC LAB").strong().size(12.0));
        ui.separator();
        ui.label(egui::RichText::new("Independent Element mapping workspace").small().weak());
    });
    ui.add_space(6.0);
    ui.label("Controls marked MAPPED/CERTIFIED can be edited through existing Element tools. PROBE READY items have known FM27 semantics but remain write-locked until their memory layout is witnessed.");
    ui.add_space(6.0);

    if let Some(sections) = sem.get("playerSections").and_then(Value::as_array) {
        egui::CollapsingHeader::new("Player feature surface").default_open(true).show(ui, |ui| {
            egui::Grid::new("v62_player_feature_grid").striped(true).num_columns(3).show(ui, |ui| {
                ui.strong("Section"); ui.strong("Status"); ui.strong("Action"); ui.end_row();
                for row in sections {
                    let label = row.get("label").and_then(Value::as_str).unwrap_or("?");
                    let status = row.get("status").and_then(Value::as_str).unwrap_or("unknown");
                    ui.label(label);
                    ui.colored_label(confidence_color(match status {
                        "certified" => "certified",
                        "mapped" | "mapped-derived" | "element-native" => "certified-read",
                        "probe-ready" | "certified-direct/probe-native" => "mapping",
                        "partial" => "witnessed",
                        _ => "semantic-only",
                    }), status);
                    let caption = match status {
                        "certified" | "mapped" | "mapped-derived" | "element-native" => "AVAILABLE",
                        "partial" => "PARTIAL",
                        "probe-ready" | "certified-direct/probe-native" => "PROBE",
                        _ => "LOCKED",
                    };
                    ui.label(caption);
                    ui.end_row();
                }
            });
        });
    }

    if let Some(targets) = probes.get("targets").and_then(Value::as_array) {
        egui::CollapsingHeader::new("Probe targets").default_open(true).show(ui, |ui| {
            for target in targets {
                let label = target.get("label").and_then(Value::as_str).unwrap_or("?");
                let fields = target.get("fields").and_then(Value::as_array).map(|a| a.iter().filter_map(Value::as_str).collect::<Vec<_>>().join(" • ")).unwrap_or_default();
                let notes = target.get("notes").and_then(Value::as_str).unwrap_or("");
                egui::Frame::group(ui.style()).show(ui, |ui| {
                    ui.horizontal(|ui| {
                        ui.label(egui::RichText::new(label).strong());
                        ui.colored_label(confidence_color("mapping"), "PROBE READY");
                    });
                    ui.label(egui::RichText::new(fields).small());
                    ui.label(egui::RichText::new(notes).small().weak());
                });
                ui.add_space(3.0);
            }
        });
    }

    if let Some(entities) = sem.get("entities").and_then(Value::as_object) {
        egui::CollapsingHeader::new("Observed FM27 object/property vocabulary").show(ui, |ui| {
            for (entity, fields) in entities {
                let txt = fields.as_array().map(|a| a.iter().filter_map(Value::as_str).collect::<Vec<_>>().join(" • ")).unwrap_or_default();
                ui.label(egui::RichText::new(entity).strong());
                ui.label(egui::RichText::new(txt).small().weak());
                ui.add_space(4.0);
            }
        });
    }
}
'''
p.write_text(t, encoding="utf-8")

p = root / "src" / "app.rs"
t = p.read_text(encoding="utf-8")
if "show_element_semantic_lab" not in t:
    marker = "    show_element_capabilities: bool,\n"
    if marker not in t: raise SystemExit("v6.2: app capability state marker missing")
    t = t.replace(marker, marker + "    show_element_semantic_lab: bool,\n", 1)
    marker = "            show_element_capabilities: false,\n"
    if marker not in t: raise SystemExit("v6.2: app capability init marker missing")
    t = t.replace(marker, marker + "            show_element_semantic_lab: false,\n", 1)

if 'ui.button("Semantic Lab")' not in t:
    marker = '                if ui.button("Capabilities").clicked() { self.show_element_capabilities = true; }\n'
    if marker not in t: raise SystemExit("v6.2: toolbar capabilities marker missing")
    t = t.replace(marker, marker + '                if ui.button("Semantic Lab").clicked() { self.show_element_semantic_lab = true; }\n', 1)

if 'Window::new("Element v6 • Semantic Lab")' not in t:
    marker = '''        if self.show_element_capabilities {
            egui::Window::new("Element v6 • Capabilities")
                .open(&mut self.show_element_capabilities)
                .resizable(true)
                .default_width(760.0)
                .show(ctx, |ui| crate::element_config::show_capability_matrix(ui));
        }

'''
    add = marker + '''        if self.show_element_semantic_lab {
            egui::Window::new("Element v6 • Semantic Lab")
                .open(&mut self.show_element_semantic_lab)
                .resizable(true)
                .default_width(860.0)
                .default_height(680.0)
                .show(ctx, |ui| {
                    egui::ScrollArea::vertical().show(ui, |ui| crate::element_config::show_semantic_lab(ui));
                });
        }

'''
    if marker not in t: raise SystemExit("v6.2: capability window marker missing")
    t = t.replace(marker, add, 1)
p.write_text(t, encoding="utf-8")

print("Element v6.2 semantic lab applied successfully.")
