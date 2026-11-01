from pathlib import Path

root = Path.cwd()

def rd(path):
    p = root / path
    if not p.exists():
        raise SystemExit(f"v6.5.0 missing {path}")
    return p.read_text(encoding="utf-8")

def wr(path, text):
    (root / path).write_text(text, encoding="utf-8")

# --- Product identity / toolbar -------------------------------------------------
app_path = "src/app.rs"
app = rd(app_path)
app = app.replace('egui::RichText::new("ELEMENT v6").strong()',
                  'egui::RichText::new("ELEMENT v6.5 • FUNCTIONAL CORE").strong()', 1)
wr(app_path, app)

# --- Capability matrix becomes the source of truth -----------------------------
cfg_path = "src/element_config.rs"
cfg = rd(cfg_path)
cfg = cfg.replace('"ELEMENT v6 CAPABILITY MATRIX"', '"ELEMENT v6.5 • FUNCTIONAL CORE"', 1)

anchor = '    ui.add_space(6.0);\n    egui::Grid::new("element_v6_capability_matrix")'
if "Functional Core = verified features only" not in cfg and anchor in cfg:
    summary = r'''    let mut live_read = 0usize;
    let mut live_write = 0usize;
    let mut locked = 0usize;
    if let Some(rows) = rows {
        for row in rows {
            if row.get("read").and_then(Value::as_bool).unwrap_or(false) { live_read += 1; }
            if row.get("write").and_then(Value::as_bool).unwrap_or(false) { live_write += 1; } else { locked += 1; }
        }
    }
    ui.horizontal_wrapped(|ui| {
        ui.colored_label(egui::Color32::from_rgb(72, 210, 132), format!("{live_write} LIVE WRITE"));
        ui.separator();
        ui.colored_label(egui::Color32::from_rgb(96, 180, 255), format!("{live_read} LIVE READ"));
        ui.separator();
        ui.colored_label(egui::Color32::from_rgb(255, 193, 92), format!("{locked} LOCKED / READ-ONLY"));
    });
    ui.label(egui::RichText::new("Functional Core = verified features only. Mapping/probe features stay visible for development but cannot perform blind writes.").small().weak());
    ui.add_space(6.0);
'''
    cfg = cfg.replace(anchor, summary + '    egui::Grid::new("element_v6_capability_matrix")', 1)
wr(cfg_path, cfg)

# --- Tactical Knowledge: stable user surface, diagnostics only in Developer -----
club_path = "src/ui/club_panel.rs"
club = rd(club_path)
club = club.replace("v6.4.3 • FMRTE COHESION MAPPER", "v6.5.0 • TACTICAL KNOWLEDGE", 1)
club = club.replace("FMRTE27 TEAM COHESION MAPPER", "FUNCTIONAL CORE • FMRTE-INFORMED", 1)
club = club.replace("FAMILIARITY VERIFIED • COHESION READ-ONLY", "FIRST TEAM FAMILIARITY LIVE • COHESION LOCKED", 1)

# Candidate matrices are diagnostic, not part of the normal editor surface.
old = '    if !club.tactical_probe_matrix.is_empty() {'
new = '''    let element_developer_mode = ui.ctx().data_mut(|d| {
        d.get_temp::<bool>(egui::Id::new("element_developer_mode")).unwrap_or(false)
    });
    if element_developer_mode && !club.tactical_probe_matrix.is_empty() {'''
if old in club and "element_developer_mode && !club.tactical_probe_matrix.is_empty()" not in club:
    club = club.replace(old, new, 1)

# Clear product wording: familiar writer is usable; cohesion is not.
club = club.replace(
    "FMRTE resource chain is MaxTacticalFamiliarity → ImproveTeamCohesion. v6.4.3 now maps bounded SeniorTeam candidates read-only; write remains locked until one TeamCohesion field is independently certified.",
    "Max Tactical Familiarity is LIVE for the selected club First Team. Improve Team Cohesion remains locked until its FM27 record is certified; no blind writes are performed.",
    1,
)
club = club.replace("⚡ FULL FMRTE CHAIN • COHESION MAPPING", "🔒 IMPROVE TEAM COHESION • LOCKED", 1)
wr(club_path, club)

# --- Data Hub: make the boundary explicit ---------------------------------------
hub_path = "src/ui/player_data_hub.rs"
if (root / hub_path).exists():
    hub = rd(hub_path)
    hub = hub.replace("ELEMENT ANALYTICS • DATA HUB", "ELEMENT DATA HUB • FUNCTIONAL CORE")
    wr(hub_path, hub)

print("Element v6.5.0 Functional Core stabilization applied.")
