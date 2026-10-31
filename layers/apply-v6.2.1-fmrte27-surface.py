from pathlib import Path

root = Path.cwd()
p = root / "src" / "element_config.rs"
t = p.read_text(encoding="utf-8")

# Treat read-mapped/write-probe relations as a first-class partial capability.
t = t.replace(
    '"partial" => "witnessed",',
    '"partial" | "mapped-read/probe-write" => "witnessed",',
    1,
)
t = t.replace(
    '"partial" => "PARTIAL",',
    '"partial" | "mapped-read/probe-write" => "PARTIAL / PROBE WRITE",',
    1,
)

# Insert the wider FM27 surface after the Player feature grid.
anchor = '''    if let Some(targets) = probes.get("targets").and_then(Value::as_array) {
'''
if "FMRTE27-equivalent surface catalog" not in t:
    block = r'''
    egui::CollapsingHeader::new("FMRTE27-equivalent surface catalog").default_open(true).show(ui, |ui| {
        for (key, label) in [
            ("clubSections", "Club"),
            ("staffSections", "Staff"),
            ("nationSections", "Nation"),
            ("competitionSections", "Competition"),
        ] {
            ui.label(egui::RichText::new(label).strong());
            if let Some(items) = sem.get(key).and_then(Value::as_array) {
                ui.horizontal_wrapped(|ui| {
                    for item in items.iter().filter_map(Value::as_str) {
                        ui.label(egui::RichText::new(item).small());
                        ui.separator();
                    }
                });
            }
            ui.add_space(4.0);
        }
    });

    egui::CollapsingHeader::new("Relationships • add/edit/remove target model").default_open(true).show(ui, |ui| {
        ui.label(egui::RichText::new("Read-side is already live in Element. The catalog below is the FM27 semantic target for native insertion/edit/removal.").small().weak());
        if let Some(items) = sem.get("relationshipTypes").and_then(Value::as_array) {
            ui.label(egui::RichText::new("Types").strong());
            ui.horizontal_wrapped(|ui| {
                for item in items.iter().filter_map(Value::as_str) {
                    ui.label(egui::RichText::new(item).small());
                }
            });
        }
        ui.add_space(4.0);
        if let Some(items) = sem.get("relationshipReasons").and_then(Value::as_array) {
            ui.label(egui::RichText::new("Reasons").strong());
            ui.horizontal_wrapped(|ui| {
                for item in items.iter().filter_map(Value::as_str) {
                    ui.label(egui::RichText::new(item).small());
                }
            });
        }
        ui.add_space(4.0);
        if let Some(items) = sem.get("registrationTypes").and_then(Value::as_array) {
            ui.label(egui::RichText::new(format!("Registration types ({})", items.len())).strong());
            egui::ScrollArea::vertical().max_height(150.0).show(ui, |ui| {
                ui.horizontal_wrapped(|ui| {
                    for item in items.iter().filter_map(Value::as_str) {
                        ui.label(egui::RichText::new(item).small());
                    }
                });
            });
        }
    });

    egui::CollapsingHeader::new("Player Stats • native FM27 target surface").default_open(true).show(ui, |ui| {
        if let Some(stats) = sem.get("statsSurface") {
            for (key, label) in [
                ("scopes", "Scopes"),
                ("comparisonPools", "Comparison pools"),
                ("positionGroups", "Position groups"),
                ("profiles", "Percentile profiles"),
                ("metrics", "Metrics"),
            ] {
                if let Some(items) = stats.get(key).and_then(Value::as_array) {
                    ui.label(egui::RichText::new(format!("{label} ({})", items.len())).strong());
                    ui.horizontal_wrapped(|ui| {
                        for item in items.iter().filter_map(Value::as_str) {
                            ui.label(egui::RichText::new(item).small());
                        }
                    });
                    ui.add_space(3.0);
                }
            }
        }
    });

'''
    if anchor not in t:
        raise SystemExit("v6.2.1: Semantic Lab probe anchor missing")
    t = t.replace(anchor, block + anchor, 1)

p.write_text(t, encoding="utf-8")
print("Element v6.2.1 FMRTE27 semantic surface catalog applied successfully.")
