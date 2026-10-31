from pathlib import Path
import shutil

root = Path.cwd()
repo = Path(__file__).resolve().parent.parent

# ---------------------------------------------------------------------------
# 1) Ship Element-owned JSON data inside the source tree for fallback loading.
# ---------------------------------------------------------------------------
src_data = root / "src" / "element_data"
src_data.mkdir(parents=True, exist_ok=True)
for name in ["capabilities.json", "presets.json", "ratings.json", "tactics.json"]:
    source = repo / "config" / "element-v6" / name
    if not source.exists():
        raise SystemExit(f"v6 offline foundation: missing {source}")
    shutil.copy2(source, src_data / name)

# ---------------------------------------------------------------------------
# 2) Data loader + capability matrix UI.
#    External element-data/*.json wins; embedded files are safe fallbacks.
# ---------------------------------------------------------------------------
module = r'''//! Element v6 data-driven configuration layer.
//!
//! Memory safety is never delegated to JSON. JSON describes UX/presets and
//! capability state; actual writes remain guarded by certified Rust mappings.

use eframe::egui;
use serde_json::Value;
use std::path::PathBuf;

fn external_data_dir() -> Option<PathBuf> {
    let exe = std::env::current_exe().ok()?;
    Some(exe.parent()?.join("element-data"))
}

fn load_value(name: &str, embedded: &str) -> Value {
    if let Some(dir) = external_data_dir() {
        let path = dir.join(name);
        if let Ok(text) = std::fs::read_to_string(path) {
            if let Ok(value) = serde_json::from_str::<Value>(&text) {
                return value;
            }
        }
    }
    serde_json::from_str(embedded).unwrap_or(Value::Null)
}

pub fn capabilities() -> Value {
    load_value("capabilities.json", include_str!("element_data/capabilities.json"))
}

pub fn presets() -> Value {
    load_value("presets.json", include_str!("element_data/presets.json"))
}

pub fn ratings() -> Value {
    load_value("ratings.json", include_str!("element_data/ratings.json"))
}

pub fn tactics() -> Value {
    load_value("tactics.json", include_str!("element_data/tactics.json"))
}

pub fn external_data_path() -> String {
    external_data_dir()
        .map(|p| p.display().to_string())
        .unwrap_or_else(|| "element-data (embedded fallback only)".to_owned())
}

pub fn config_health() -> (usize, usize, usize, usize) {
    let caps = capabilities().get("capabilities").and_then(Value::as_array).map_or(0, Vec::len);
    let presets = presets().get("presets").and_then(Value::as_array).map_or(0, Vec::len);
    let roles = ratings().get("roleProfiles").and_then(Value::as_object).map_or(0, |v| v.len());
    let tactics = tactics().get("formations").and_then(Value::as_array).map_or(0, Vec::len);
    (caps, presets, roles, tactics)
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
    egui::Grid::new("element_v6_capability_matrix")
        .striped(true)
        .num_columns(5)
        .spacing([12.0, 4.0])
        .show(ui, |ui| {
            for h in ["Feature", "Entity", "Read", "Write", "Confidence"] {
                ui.label(egui::RichText::new(h).strong().size(9.0));
            }
            ui.end_row();
            if let Some(rows) = rows {
                for row in rows {
                    let label = row.get("label").and_then(Value::as_str).unwrap_or("?");
                    let entity = row.get("entity").and_then(Value::as_str).unwrap_or("?");
                    let read = row.get("read").and_then(Value::as_bool).unwrap_or(false);
                    let write = row.get("write").and_then(Value::as_bool).unwrap_or(false);
                    let conf = row.get("confidence").and_then(Value::as_str).unwrap_or("unknown");
                    let gate = row.get("gate").and_then(Value::as_str);
                    ui.label(label);
                    ui.label(entity);
                    ui.label(if read { "✓" } else { "—" });
                    let write_text = if write { "✓" } else { "🔒" };
                    let resp = ui.label(write_text);
                    if let Some(gate) = gate { resp.on_hover_text(format!("Gate: {gate}")); }
                    ui.colored_label(confidence_color(conf), conf);
                    ui.end_row();
                }
            }
        });
}
'''
(root / "src" / "element_config.rs").write_text(module, encoding="utf-8")

# ---------------------------------------------------------------------------
# 3) Register module.
# ---------------------------------------------------------------------------
p = root / "src" / "lib.rs"
t = p.read_text(encoding="utf-8")
if "pub mod element_config;" not in t:
    marker = "pub mod cache;\n"
    if marker not in t:
        raise SystemExit("v6 offline foundation: lib.rs cache marker missing")
    t = t.replace(marker, marker + "pub mod element_config;\n", 1)
p.write_text(t, encoding="utf-8")

# ---------------------------------------------------------------------------
# 4) Persistent Safe Mode + Developer Mode.
# ---------------------------------------------------------------------------
p = root / "src" / "settings.rs"
t = p.read_text(encoding="utf-8")
if "pub safe_mode: bool" not in t:
    marker = '''    #[serde(default = "default_true")]
    pub reload_on_tab_switch: bool,
'''
    extra = '''    #[serde(default = "default_true")]
    pub reload_on_tab_switch: bool,
    /// Blocks every live write while preserving read-only inspection.
    #[serde(default)]
    pub safe_mode: bool,
    /// Shows raw mapping addresses, diagnostics and research tooling.
    #[serde(default)]
    pub developer_mode: bool,
'''
    if marker not in t:
        raise SystemExit("v6 offline foundation: settings marker missing")
    t = t.replace(marker, extra, 1)
p.write_text(t, encoding="utf-8")

# ---------------------------------------------------------------------------
# 5) App integration: settings, write gate, status, capability window.
# ---------------------------------------------------------------------------
p = root / "src" / "app.rs"
t = p.read_text(encoding="utf-8")

if "show_element_capabilities" not in t:
    marker = "    show_history: bool,\n"
    if marker not in t:
        raise SystemExit("v6 offline foundation: app state marker missing")
    t = t.replace(marker, marker + "    show_element_capabilities: bool,\n", 1)
    marker = "            show_history: false,\n"
    if marker not in t:
        raise SystemExit("v6 offline foundation: app init marker missing")
    t = t.replace(marker, marker + "            show_element_capabilities: false,\n", 1)

old_gate = "navigation::set_editing_enabled(ctx, self.conn.is_writable() && !self.writes.is_pending());"
new_gate = "navigation::set_editing_enabled(ctx, self.conn.is_writable() && !self.writes.is_pending() && !self.settings.safe_mode);"
if old_gate in t:
    t = t.replace(old_gate, new_gate, 1)
elif new_gate not in t:
    raise SystemExit("v6 offline foundation: editing gate marker missing")

publish_marker = "        ctx.data_mut(|d| d.insert_temp(theme_data_id(), self.settings.theme));\n"
if "element_developer_mode" not in t:
    if publish_marker not in t:
        raise SystemExit("v6 offline foundation: theme publish marker missing")
    t = t.replace(
        publish_marker,
        publish_marker
        + '        ctx.data_mut(|d| d.insert_temp(egui::Id::new("element_developer_mode"), self.settings.developer_mode));\n'
        + '        ctx.data_mut(|d| d.insert_temp(egui::Id::new("element_safe_mode"), self.settings.safe_mode));\n',
        1,
    )

settings_anchor = '''                    let mut rts = self.settings.reload_on_tab_switch;
                    if ui.checkbox(&mut rts, "Reload on tab switch").changed() {
                        self.settings.reload_on_tab_switch = rts;
                        self.settings.save();
                    }
'''
if "Safe Mode (block all writes)" not in t:
    if settings_anchor not in t:
        raise SystemExit("v6 offline foundation: settings UI anchor missing")
    settings_extra = settings_anchor + '''                    ui.separator();
                    let mut safe = self.settings.safe_mode;
                    if ui.checkbox(&mut safe, "Safe Mode (block all writes)").changed() {
                        self.settings.safe_mode = safe;
                        self.settings.save();
                    }
                    let mut dev = self.settings.developer_mode;
                    if ui.checkbox(&mut dev, "Developer Mode").changed() {
                        self.settings.developer_mode = dev;
                        self.settings.save();
                    }
'''
    t = t.replace(settings_anchor, settings_extra, 1)

menu_tail = '''                });
            });
        });

        // Clone the Arc so we can borrow entity data inside egui closures
'''
if 'ui.menu_button("Element"' not in t:
    if menu_tail not in t:
        raise SystemExit("v6 offline foundation: menu tail marker missing")
    insert = '''                });
                ui.menu_button("Element", |ui| {
                    if ui.button("Capability Matrix").clicked() {
                        self.show_element_capabilities = true;
                        ui.close_menu();
                    }
                    let (caps, presets, roles, tactics) = crate::element_config::config_health();
                    ui.separator();
                    ui.label(format!("Config: {caps} capabilities • {presets} presets • {roles} role profiles • {tactics} formations"));
                    ui.label(egui::RichText::new(crate::element_config::external_data_path()).small().weak());
                });
            });
        });

        if self.show_element_capabilities {
            egui::Window::new("Element v6 • Capabilities")
                .open(&mut self.show_element_capabilities)
                .resizable(true)
                .default_width(760.0)
                .show(ctx, |ui| crate::element_config::show_capability_matrix(ui));
        }

        // Clone the Arc so we can borrow entity data inside egui closures
'''
    t = t.replace(menu_tail, insert, 1)

status_anchor = '''                ui.separator();
                if let Some(ref c) = self.entity_counts {
'''
if '"SAFE MODE"' not in t:
    if status_anchor not in t:
        raise SystemExit("v6 offline foundation: status anchor missing")
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
