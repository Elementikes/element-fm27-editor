from pathlib import Path
import shutil

root = Path.cwd()
repo = Path(__file__).resolve().parent.parent

def rd(path):
    p = root / path
    if not p.exists():
        raise SystemExit(f"v6.4.0 missing {path}")
    return p.read_text(encoding="utf-8")

def wr(path, text):
    (root / path).write_text(text, encoding="utf-8")

def one(text, old, new, label):
    if old not in text:
        raise SystemExit(f"v6.4.0 marker missing: {label}")
    return text.replace(old, new, 1)

# Ship the independent FMRTE27 interoperability/reference catalog with Element.
src = repo / "config" / "element-v6" / "fmrte-reference.json"
if not src.exists():
    raise SystemExit(f"v6.4.0 missing {src}")
dst = root / "src" / "element_data" / "fmrte-reference.json"
dst.parent.mkdir(parents=True, exist_ok=True)
shutil.copy2(src, dst)

cfg_path = "src/element_config.rs"
cfg = rd(cfg_path)
if "pub fn fmrte_reference()" not in cfg:
    marker = 'pub fn player_surface() -> Value { load_value("player-surface.json", include_str!("element_data/player-surface.json")) }\n'
    if marker not in cfg:
        raise SystemExit("v6.4.0: player_surface loader marker missing")
    cfg = cfg.replace(marker, marker + 'pub fn fmrte_reference() -> Value { load_value("fmrte-reference.json", include_str!("element_data/fmrte-reference.json")) }\n', 1)

# Add a dense, useful reference/integration section to Semantic Lab.
if "FMRTE27 RESOURCE INTEGRATION • v6.4.0" not in cfg:
    anchor = '    if let Some(targets) = probes.get("targets").and_then(Value::as_array) {\n'
    block = r'''
    egui::CollapsingHeader::new("FMRTE27 RESOURCE INTEGRATION • v6.4.0").default_open(true).show(ui, |ui| {
        let reference = fmrte_reference();
        ui.label(egui::RichText::new("Independent Element implementation informed by user-provided FMRTE27 resources/observable metadata. No proprietary implementation code is copied.").small().weak());
        ui.add_space(4.0);

        if let Some(chain) = reference.get("presetSemantics").and_then(Value::as_object) {
            ui.label(egui::RichText::new("Preset action chains").strong());
            for key in ["TacticalUnderstanding", "Heal", "Inspire", "Destroy", "AllInOne"] {
                if let Some(actions) = chain.get(key).and_then(Value::as_array) {
                    let text = actions.iter().filter_map(Value::as_str).collect::<Vec<_>>().join(" → ");
                    ui.label(egui::RichText::new(format!("{key}: {text}")).small());
                }
            }
        }

        if let Some(weights) = reference.get("teamSelectionWeights").and_then(Value::as_object) {
            ui.separator();
            ui.label(egui::RichText::new("Team Selection weights").strong());
            ui.horizontal_wrapped(|ui| {
                for key in ["PositionAbility","Role","CurrentAbility","PotentialAbility","Fitness","Reputation","Morale"] {
                    if let Some(v) = weights.get(key) { ui.label(format!("{key}={v}")); }
                }
            });
        }

        if let Some(role) = reference.get("roleModel").and_then(Value::as_object) {
            ui.separator();
            let groups = role.get("positionGroups").and_then(Value::as_u64).unwrap_or(0);
            let defs = role.get("roleDefinitions").and_then(Value::as_u64).unwrap_or(0);
            ui.label(egui::RichText::new(format!("Role model: {defs} role definitions across {groups} position groups")).strong());
        }
        if let Some(tactics) = reference.get("tacticTemplates").and_then(Value::as_object) {
            let count = tactics.get("count").and_then(Value::as_u64).unwrap_or(0);
            ui.label(format!("Tactic templates discovered: {count}"));
        }

        if let Some(items) = reference.get("integrationPriorities").and_then(Value::as_array) {
            ui.separator();
            egui::Grid::new("v640_fmrte_integration_grid").striped(true).num_columns(3).show(ui, |ui| {
                ui.strong("Feature"); ui.strong("Element status"); ui.strong("Next binding"); ui.end_row();
                for item in items {
                    let feature = item.get("feature").and_then(Value::as_str).unwrap_or("?");
                    let status = item.get("status").and_then(Value::as_str).unwrap_or("?");
                    let next = item.get("next").and_then(Value::as_str).unwrap_or("");
                    ui.label(feature); ui.label(status); ui.label(next); ui.end_row();
                }
            });
        }
    });
    ui.add_space(6.0);

'''
    if anchor not in cfg:
        raise SystemExit("v6.4.0 semantic lab anchor missing")
    cfg = cfg.replace(anchor, block + anchor, 1)
wr(cfg_path, cfg)

# Tactical Knowledge: reflect what is now actually known from FMRTE resources + live Element mapping.
club_path = "src/ui/club_panel.rs"
club = rd(club_path)
club = club.replace("v6.2.5 • TACTICAL UNDERSTANDING CERTIFIER", "v6.4.0 • FMRTE-STYLE TACTICAL KNOWLEDGE", 1)
club = club.replace("FMRTE27 SEMANTIC WITNESS", "FMRTE27 RESOURCE + LIVE MAP", 1)
club = club.replace("READ-ONLY UNTIL 7/7", "FIRST TEAM BULK WRITE CERTIFIED", 1)
club = club.replace("WITNESS REQUIRED", "MAPPED BULK", 7)
club = club.replace("⚡ MAX FIRST TEAM • 100", "⚡ FMRTE MAX FIRST TEAM • 100", 1)

# Insert the observed custom action chain and explain the remaining cohesion gap.
needle = '            ui.add_space(5.0);\n            egui::Grid::new(format!("element_v625_tactical_axes_{}", club.addr))\n'
if "FMRTE preset chain:" not in club and needle in club:
    add = '''            ui.add_space(4.0);\n            ui.horizontal_wrapped(|ui| {\n                ui.label(egui::RichText::new("FMRTE preset chain:").strong());\n                ui.label(egui::RichText::new("MaxTacticalFamiliarity").color(egui::Color32::from_rgb(88, 214, 141)));\n                ui.label("→");\n                ui.label(egui::RichText::new("ImproveTeamCohesion").color(egui::Color32::from_rgb(255, 184, 77)));\n                ui.label(egui::RichText::new("(semantic found; cohesion writer not certified yet)").small().weak());\n            });\n\n'''
    club = club.replace(needle, add + needle, 1)

# Remove stale FMRTE-license-test wording if still present.
club = club.replace("② COMPARE AFTER FMRTE MAX", "② COMPARE LIVE SNAPSHOT", 1)
club = club.replace("Capture here → in FMRTE use Max Tactical Familiarity", "Capture/compare is now diagnostic only; Element's First Team familiarity writer is live", 1)
wr(club_path, club)

print("Element v6.4.0 FMRTE reference integration applied.")
