from pathlib import Path
import shutil

root = Path.cwd()
repo = Path(__file__).resolve().parent.parent

src_data = root / "src" / "element_data"
src_data.mkdir(parents=True, exist_ok=True)
for name in ["capabilities.json", "presets.json", "ratings.json", "tactics.json"]:
    source = repo / "config" / "element-v6" / name
    if not source.exists():
        raise SystemExit(f"v6 offline foundation: missing {source}")
    shutil.copy2(source, src_data / name)

module = r'''//! Element v6 data-driven configuration layer.
use eframe::egui;
use serde_json::Value;
use std::path::PathBuf;

fn external_data_dir() -> Option<PathBuf> {
    let exe = std::env::current_exe().ok()?;
    Some(exe.parent()?.join("element-data"))
}

fn load_value(name: &str, embedded: &str) -> Value {
    if let Some(dir) = external_data_dir() {
        if let Ok(text) = std::fs::read_to_string(dir.join(name)) {
            if let Ok(value) = serde_json::from_str::<Value>(&text) { return value; }
        }
    }
    serde_json::from_str(embedded).unwrap_or(Value::Null)
}

pub fn capabilities() -> Value { load_value("capabilities.json", include_str!("element_data/capabilities.json")) }
pub fn presets() -> Value { load_value("presets.json", include_str!("element_data/presets.json")) }
pub fn ratings() -> Value { load_value("ratings.json", include_str!("element_data/ratings.json")) }
pub fn tactics() -> Value { load_value("tactics.json", include_str!("element_data/tactics.json")) }

pub fn external_data_path() -> String {
    external_data_dir().map(|p| p.display().to_string()).unwrap_or_else(|| "element-data (embedded fallback only)".to_owned())
}

pub fn config_health() -> (usize, usize, usize, usize) {
    let c = capabilities();
    let p = presets();
    let r = ratings();
    let t = tactics();
    (
        c.get("capabilities").and_then(Value::as_array).map_or(0, Vec::len),
        p.get("presets").and_then(Value::as_array).map_or(0, Vec::len),
        r.get("roleProfiles").and_then(Value::as_object).map_or(0, |v| v.len()),
        t.get("formations").and_then(Value::as_array).map_or(0, Vec::len),
    )
}

fn confidence_color(conf: &str) -> egui::Color32 {
    match conf {
        "certified" => egui::Color32::from_rgb(72, 210, 132),
        "certified-read" | "cross-witnessed" => egui::Color32::from_rgb(96, 180, 255),
        "witnessed" => egui::Color32::from_rgb(181, 151, 255),
        "mapping" | "candidate" => egui::Color32::from_rgb(255, 193, 92),
        "semantic-only" => egui::Color32::from_rgb(210, 164, 84),
        _ => egui::Color32::from_rgb(150, 160, 178),
    }
}

pub fn show_capability_matrix(ui: &mut egui::Ui) {
    let value = capabilities();
    let rows = value.get("capabilities").and_then(Value::as_array);
    ui.horizontal(|ui| {
        ui.label(egui::RichText::new("ELEMENT v6 CAPABILITY MATRIX").strong().size(12.0));
        ui.separator();
        ui.label(egui::RichText::new(external_data_path()).small().weak());
    });
    ui.add_space(6.0);
    egui::Grid::new("element_v6_capability_matrix").striped(true).num_columns(5).spacing([12.0, 4.0]).show(ui, |ui| {
        for h in ["Feature", "Entity", "Read", "Write", "Confidence"] { ui.label(egui::RichText::new(h).strong().size(9.0)); }
        ui.end_row();
        if let Some(rows) = rows {
            for row in rows {
                let label = row.get("label").and_then(Value::as_str).unwrap_or("?");
                let entity = row.get("entity").and_then(Value::as_str).unwrap_or("?");
                let read = row.get("read").and_then(Value::as_bool).unwrap_or(false);
                let write = row.get("write").and_then(Value::as_bool).unwrap_or(false);
                let conf = row.get("confidence").and_then(Value::as_str).unwrap_or("unknown");
                let gate = row.get("gate").and_then(Value::as_str);
                ui.label(label); ui.label(entity); ui.label(if read { "YES" } else { "—" });
                let resp = ui.label(if write { "YES" } else { "LOCKED" });
                if let Some(gate) = gate { resp.on_hover_text(format!("Gate: {gate}")); }
                ui.colored_label(confidence_color(conf), conf); ui.end_row();
            }
        }
    });
}
'''
(root / "src" / "element_config.rs").write_text(module, encoding="utf-8")

p = root / "src" / "lib.rs"
t = p.read_text(encoding="utf-8")
if "pub mod element_config;" not in t:
    marker = "pub mod cache;\n"
    if marker not in t: raise SystemExit("v6 offline foundation: lib.rs marker missing")
    t = t.replace(marker, marker + "pub mod element_config;\n", 1)
p.write_text(t, encoding="utf-8")

p = root / "src" / "settings.rs"
t = p.read_text(encoding="utf-8")
if "pub safe_mode: bool" not in t:
    marker = '''    #[serde(default = "default_true")]
    pub reload_on_tab_switch: bool,
'''
    extra = '''    #[serde(default = "default_true")]
    pub reload_on_tab_switch: bool,
    #[serde(default)]
    pub safe_mode: bool,
    #[serde(default)]
    pub developer_mode: bool,
'''
    if marker not in t: raise SystemExit("v6 offline foundation: settings struct marker missing")
    t = t.replace(marker, extra, 1)
p.write_text(t, encoding="utf-8")

p = root / "src" / "app.rs"
t = p.read_text(encoding="utf-8")

if "show_element_capabilities" not in t:
    marker = "    show_history: bool,\n"
    if marker not in t: raise SystemExit("v6 offline foundation: app state marker missing")
    t = t.replace(marker, marker + "    show_element_capabilities: bool,\n", 1)
    marker = "            show_history: false,\n"
    if marker not in t: raise SystemExit("v6 offline foundation: app init marker missing")
    t = t.replace(marker, marker + "            show_element_capabilities: false,\n", 1)

old_gate = "navigation::set_editing_enabled(ctx, self.conn.is_writable() && !self.writes.is_pending());"
new_gate = "navigation::set_editing_enabled(ctx, self.conn.is_writable() && !self.writes.is_pending() && !self.settings.safe_mode);"
if old_gate in t: t = t.replace(old_gate, new_gate, 1)
elif new_gate not in t: raise SystemExit("v6 offline foundation: editing gate marker missing")

publish_marker = "        ctx.data_mut(|d| d.insert_temp(theme_data_id(), self.settings.theme));\n"
if "element_developer_mode" not in t:
    if publish_marker in t:
        t = t.replace(publish_marker, publish_marker
            + '        ctx.data_mut(|d| d.insert_temp(egui::Id::new("element_developer_mode"), self.settings.developer_mode));\n'
            + '        ctx.data_mut(|d| d.insert_temp(egui::Id::new("element_safe_mode"), self.settings.safe_mode));\n', 1)

# Add an independent Element toolbar immediately before the cache/sidebar phase.
# This survives v4.8+ menu rewrites and avoids legacy Settings menu assumptions.
toolbar_anchor = "        // Clone the Arc so we can borrow entity data inside egui closures\n"
if 'TopBottomPanel::top("element_v6_toolbar")' not in t:
    if toolbar_anchor not in t: raise SystemExit("v6 offline foundation: toolbar anchor missing")
    toolbar = '''        egui::TopBottomPanel::top("element_v6_toolbar").show(ctx, |ui| {
            ui.horizontal(|ui| {
                ui.label(egui::RichText::new("ELEMENT v6").strong());
                ui.separator();
                let mut safe = self.settings.safe_mode;
                if ui.checkbox(&mut safe, "Safe Mode").on_hover_text("Block every live write while keeping read-only inspection available.").changed() {
                    self.settings.safe_mode = safe;
                    self.settings.save();
                }
                let mut dev = self.settings.developer_mode;
                if ui.checkbox(&mut dev, "Developer").changed() {
                    self.settings.developer_mode = dev;
                    self.settings.save();
                }
                if ui.button("Capabilities").clicked() { self.show_element_capabilities = true; }
                let (caps, presets, roles, tactics) = crate::element_config::config_health();
                ui.separator();
                ui.label(egui::RichText::new(format!("{caps} caps • {presets} presets • {roles} roles • {tactics} tactics")).small().weak());
            });
        });

        if self.show_element_capabilities {
            egui::Window::new("Element v6 • Capabilities")
                .open(&mut self.show_element_capabilities)
                .resizable(true)
                .default_width(760.0)
                .show(ctx, |ui| crate::element_config::show_capability_matrix(ui));
        }

'''
    t = t.replace(toolbar_anchor, toolbar + toolbar_anchor, 1)

# Status indicator is optional; toolbar remains the source of truth.
status_anchor = '''                ui.separator();
                if let Some(ref c) = self.entity_counts {
'''
if '"SAFE MODE"' not in t and status_anchor in t:
    status = '''                ui.separator();
                if self.settings.safe_mode {
                    ui.colored_label(egui::Color32::from_rgb(255, 193, 92), "SAFE MODE");
                    ui.separator();
                }
                if self.settings.developer_mode {
                    ui.label(egui::RichText::new("DEV").strong());
                    ui.separator();
                }
                if let Some(ref c) = self.entity_counts {
'''
    t = t.replace(status_anchor, status, 1)

p.write_text(t, encoding="utf-8")
print("Element v6.0 offline foundation applied successfully.")
