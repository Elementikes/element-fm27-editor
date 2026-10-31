from pathlib import Path

p = Path.cwd() / "src" / "ui" / "player_panel.rs"
t = p.read_text(encoding="utf-8")

# Native enum entry.
if "    DataHub,\n" not in t:
    marker = "    Overview,\n"
    if marker not in t:
        start = t.find("pub enum PlayerTab")
        raise SystemExit("v6.1 nav: PlayerTab Overview missing\n" + t[start:start+1200])
    t = t.replace(marker, marker + "    DataHub,\n", 1)

# The v4.8+ Element player shell owns a custom navigation row, so avoid
# depending on upstream selectable_value labels. Insert a compact analytics
# switch immediately before the detail scroll area; this survives UI restyles.
if "ELEMENT ANALYTICS • DATA HUB" not in t:
    scroll = t.find("egui::ScrollArea::vertical")
    if scroll < 0:
        raise SystemExit("v6.1 nav: player detail ScrollArea missing")
    line = t.rfind("\n", 0, scroll) + 1
    nav = r'''    ui.horizontal(|ui| {
        let selected = *tab == PlayerTab::DataHub;
        if ui.selectable_label(selected, "📊 Data Hub").on_hover_text("Element v6 analytics: percentiles, league-cohort pipeline, dribbling profile, radar and comparison charts.").clicked() {
            *tab = PlayerTab::DataHub;
        }
        ui.separator();
        ui.label(egui::RichText::new("ELEMENT ANALYTICS • DATA HUB").size(7.5).weak());
    });
    ui.separator();

'''
    t = t[:line] + nav + t[line:]

# Render arm. Anchor on Overview arm rather than the cosmetics of the tab row.
if "PlayerTab::DataHub =>" not in t:
    scroll = t.find("egui::ScrollArea::vertical")
    arm = t.find("PlayerTab::Overview =>", scroll)
    if arm < 0:
        # Some Element shells render an explicit `match *tab`; dump useful context.
        raise SystemExit("v6.1 nav: Overview render arm missing\n" + t[scroll:scroll+2200])
    line = t.rfind("\n", 0, arm) + 1
    render = "        PlayerTab::DataHub => crate::ui::player_data_hub::show(schemas, ui, player),\n"
    t = t[:line] + render + t[line:]

p.write_text(t, encoding="utf-8")
print("Element v6.1 resilient Data Hub navigation applied successfully.")
