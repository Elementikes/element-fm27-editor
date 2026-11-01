from pathlib import Path
import re

root = Path.cwd()


def rd(path):
    p = root / path
    if not p.exists():
        raise SystemExit(f"v7.8 missing {path}")
    return p.read_text(encoding="utf-8")


def wr(path, text):
    (root / path).write_text(text, encoding="utf-8")


def one(text, old, new, label):
    if old not in text:
        raise SystemExit(f"v7.8 marker missing: {label}")
    return text.replace(old, new, 1)


# -----------------------------------------------------------------------------
# FMRTE-inspired Element palette: dark navy shell + strong entity blue.
# -----------------------------------------------------------------------------
p = "src/settings.rs"
t = rd(p)
if "ELEMENT_FMRTE_PREMIUM_V78" not in t:
    old = '''fn element_visuals() -> egui::Visuals {
    let mut v = egui::Visuals::dark();
    v.window_fill = egui::Color32::from_rgb(13, 16, 23);
    v.panel_fill = egui::Color32::from_rgb(17, 21, 30);
    v.faint_bg_color = egui::Color32::from_rgb(25, 30, 43);
    v.extreme_bg_color = egui::Color32::from_rgb(8, 10, 15);
    v.hyperlink_color = egui::Color32::from_rgb(116, 145, 255);
    v.selection.bg_fill = egui::Color32::from_rgb(75, 96, 210);
    v.widgets.inactive.bg_fill = egui::Color32::from_rgb(28, 34, 47);
    v.widgets.hovered.bg_fill = egui::Color32::from_rgb(40, 49, 68);
    v.widgets.active.bg_fill = egui::Color32::from_rgb(52, 65, 96);
    v
}
'''
    new = '''fn element_visuals() -> egui::Visuals {
    // ELEMENT_FMRTE_PREMIUM_V78 — layout inspiration only; all branding/assets are Element.
    let mut v = egui::Visuals::dark();
    v.window_fill = egui::Color32::from_rgb(12, 17, 26);
    v.panel_fill = egui::Color32::from_rgb(17, 23, 34);
    v.faint_bg_color = egui::Color32::from_rgb(25, 32, 46);
    v.extreme_bg_color = egui::Color32::from_rgb(8, 12, 19);
    v.hyperlink_color = egui::Color32::from_rgb(88, 145, 255);
    v.selection.bg_fill = egui::Color32::from_rgb(39, 96, 220);
    v.selection.stroke.color = egui::Color32::from_rgb(150, 190, 255);
    v.widgets.inactive.bg_fill = egui::Color32::from_rgb(27, 35, 49);
    v.widgets.inactive.weak_bg_fill = egui::Color32::from_rgb(24, 31, 44);
    v.widgets.hovered.bg_fill = egui::Color32::from_rgb(38, 51, 72);
    v.widgets.active.bg_fill = egui::Color32::from_rgb(45, 70, 118);
    v.window_corner_radius = egui::CornerRadius::same(4);
    v.menu_corner_radius = egui::CornerRadius::same(3);
    v
}
'''
    t = one(t, old, new, "Element premium palette")
wr(p, t)


# -----------------------------------------------------------------------------
# Shared entity banner. Keeps the existing public API, so Player/Staff/Club all
# receive the premium shell without changing memory/edit code.
# -----------------------------------------------------------------------------
p = "src/ui/entity_header.rs"
t = rd(p)
if "ELEMENT_ENTITY_BANNER_V78" not in t:
    start = t.index("pub fn show(\n")
    end = t.index("\n/// Age on the attached game's date", start)
    new_show = r'''pub fn show(
    ui: &mut egui::Ui,
    name: &str,
    kind: &str,
    uid: impl std::fmt::Display,
    age: Option<u8>,
    club: Option<&str>,
    club_addr: Option<u64>,
    nation: Option<&str>,
) {
    // ELEMENT_ENTITY_BANNER_V78 — FMRTE-inspired information density with Element branding.
    let blue = egui::Color32::from_rgb(38, 101, 221);
    let pale = egui::Color32::from_rgb(214, 228, 255);
    egui::Frame::new()
        .fill(blue)
        .corner_radius(egui::CornerRadius::same(4))
        .inner_margin(egui::Margin::symmetric(14, 10))
        .show(ui, |ui| {
            ui.horizontal_wrapped(|ui| {
                let badge = match kind {
                    "Player" => "P",
                    "Staff" | "Human Manager" => "S",
                    "Club" => "C",
                    _ => "E",
                };
                egui::Frame::new()
                    .fill(egui::Color32::from_rgba_unmultiplied(5, 18, 45, 120))
                    .corner_radius(egui::CornerRadius::same(5))
                    .inner_margin(egui::Margin::symmetric(11, 8))
                    .show(ui, |ui| {
                        ui.label(egui::RichText::new(badge).size(20.0).strong().color(egui::Color32::WHITE));
                    });
                ui.vertical(|ui| {
                    ui.horizontal_wrapped(|ui| {
                        ui.label(egui::RichText::new(name).size(22.0).strong().color(egui::Color32::WHITE));
                        ui.label(egui::RichText::new(kind.to_uppercase()).size(9.0).strong().color(pale));
                    });
                    ui.horizontal_wrapped(|ui| {
                        ui.label(egui::RichText::new(format!("UID {uid}")).small().color(pale));
                        if let Some(age) = age {
                            ui.label(egui::RichText::new(format!("• {age} years")).small().color(pale));
                        }
                        if kind != "Club" {
                            if club.is_some() {
                                ui.label(egui::RichText::new("•").color(pale));
                                crate::ui::navigation::club_link(ui, club, club_addr);
                            }
                        }
                        ui.label(egui::RichText::new(format!("• {}", nation.filter(|s| !s.trim().is_empty()).unwrap_or("Unknown"))).small().color(pale));
                    });
                });
            });
        });
    ui.add_space(7.0);
}
'''
    t = t[:start] + new_show + t[end:]
wr(p, t)


# -----------------------------------------------------------------------------
# Player: remove the duplicated horizontal sub-tab ribbon; left entity sidebar
# becomes the primary navigation. Add compact FMRTE-like CA/PA/Morale cards.
# -----------------------------------------------------------------------------
p = "src/ui/player_panel.rs"
t = rd(p)
if "ELEMENT_PLAYER_HEADER_CARDS_V78" not in t:
    marker = '''    crate::ui::entity_header::show(
        ui,
        player.name.as_deref().unwrap_or("Unknown"),
        "Player",
'''
    idx = t.find(marker)
    if idx < 0:
        raise SystemExit("v7.8 marker missing: player entity header")
    # Insert cards after the complete entity_header::show(...); call.
    call_end = t.find("    );", idx)
    if call_end < 0:
        raise SystemExit("v7.8 player header call end missing")
    call_end += len("    );")
    cards = r'''
    // ELEMENT_PLAYER_HEADER_CARDS_V78
    ui.horizontal_wrapped(|ui| {
        let tile = |ui: &mut egui::Ui, label: &str, value: String| {
            egui::Frame::group(ui.style()).inner_margin(egui::Margin::symmetric(10, 5)).show(ui, |ui| {
                ui.horizontal(|ui| {
                    ui.label(egui::RichText::new(label).size(8.0).strong().weak());
                    ui.label(egui::RichText::new(value).size(15.0).strong());
                });
            });
        };
        tile(ui, "CA", player.field_u16("p_ca").map(|v| v.to_string()).unwrap_or_else(|| "—".into()));
        tile(ui, "PA", player.field_u16("p_pa").map(|v| v.to_string()).unwrap_or_else(|| "—".into()));
        tile(ui, "MORALE", player.field_u8("p_morale").map(|v| format!("{v}/20")).unwrap_or_else(|| "—".into()));
        tile(ui, "STATUS", if player.contract_addr.is_some() { "CONTRACTED".into() } else { "FREE / UNMAPPED".into() });
    });
    ui.add_space(5.0);
'''
    t = t[:call_end] + cards + t[call_end:]

    # Remove the old horizontal ribbon after all v7 tabs have been injected.
    pattern = re.compile(r'''    // Sub-tab bar\n    ui\.horizontal\(\|ui\| \{.*?\n    \}\);\n    ui\.separator\(\);\n''', re.S)
    t, n = pattern.subn('''    // Primary entity navigation lives in the FMRTE-inspired left sidebar.\n    ui.separator();\n''', t, count=1)
    if n != 1:
        raise SystemExit("v7.8 player tab ribbon marker missing")
wr(p, t)


# -----------------------------------------------------------------------------
# Staff: same sidebar-first navigation model.
# -----------------------------------------------------------------------------
p = "src/ui/staff_panel.rs"
t = rd(p)
if "ELEMENT_STAFF_SIDEBAR_NAV_V78" not in t:
    old = '''    ui.horizontal(|ui| {
        ui.selectable_value(tab, StaffTab::Overview, "Overview");
        if has_contract {
            ui.selectable_value(tab, StaffTab::Contract, "Contract");
        }
        ui.selectable_value(tab, StaffTab::PowerTools, "Power Tools");
    });
    ui.separator();
'''
    new = '''    // ELEMENT_STAFF_SIDEBAR_NAV_V78 — primary navigation is in app sidebar.
    let _ = has_contract;
    ui.separator();
'''
    t = one(t, old, new, "staff tab ribbon")
wr(p, t)


# -----------------------------------------------------------------------------
# Club: keep functionality but remove the horizontal tab ribbon and restyle the
# Squads workspace with FMRTE-style squad selector affordances.
# -----------------------------------------------------------------------------
p = "src/ui/club_panel.rs"
t = rd(p)
if "ELEMENT_CLUB_SIDEBAR_NAV_V78" not in t:
    # Replace the unique club tab ribbon from Overview through optional policy.
    pattern = re.compile(r'''    ui\.horizontal_wrapped\(\|ui\| \{\n        ui\.selectable_value\(tab, ClubTab::Overview, "Overview"\);.*?\n    \}\);\n    ui\.separator\(\);''', re.S)
    t, n = pattern.subn('''    // ELEMENT_CLUB_SIDEBAR_NAV_V78 — primary navigation is in app sidebar.
    let _ = show_policy;
    ui.separator();''', t, count=1)
    if n != 1:
        raise SystemExit("v7.8 club tab ribbon marker missing")

    t = t.replace('ui.heading("Live Club Squads");', 'ui.heading("Squads");', 1)
    t = t.replace('"ELEMENT v7.5 • ENTITY CACHE LIVE"', '"ELEMENT v7.8 • LIVE ROSTER"', 1)
    squad_anchor = '''    ui.label(egui::RichText::new("Roster rows come directly from the current FM27 entity cache. Click a player to open the full Player editor.").weak());
    ui.add_space(6.0);
'''
    squad_nav = squad_anchor + r'''    ui.horizontal_wrapped(|ui| {
        ui.selectable_label(true, "ALL CLUB");
        ui.add_enabled(false, egui::Button::new("FIRST TEAM 🔒")).on_disabled_hover_text("Team-type membership filtering is visible but stays locked until the team-kind chain is certified on this FM27 build.");
        ui.add_enabled(false, egui::Button::new("B / RESERVES 🔒")).on_disabled_hover_text("Visible for FMRTE parity; no fake membership filtering is used.");
        ui.add_enabled(false, egui::Button::new("U19 / YOUTH 🔒")).on_disabled_hover_text("Visible for FMRTE parity; no fake membership filtering is used.");
    });
    ui.add_space(5.0);
'''
    t = one(t, squad_anchor, squad_nav, "squad selector")
wr(p, t)


# -----------------------------------------------------------------------------
# App shell: contextual FMRTE-equivalent entity navigation. Every FMRTE surface
# is visible. Supported pages navigate to live Element features; unsupported
# pages are explicitly locked rather than pretending to write game memory.
# -----------------------------------------------------------------------------
p = "src/app.rs"
t = rd(p)
if "ELEMENT_CONTEXT_SIDEBAR_V78" not in t:
    anchor = '''                ui.separator();
                ui.add_space(8.0);
                ui.label(egui::RichText::new("BROWSE").small().strong().weak());
'''
    block = r'''                ui.separator();
                ui.add_space(7.0);

                // ELEMENT_CONTEXT_SIDEBAR_V78
                if let Some(entity_type) = self.active_tab.and_then(|i| self.open_tabs.get(i)).map(|t| t.entity_type) {
                    let live = egui::Color32::from_rgb(96, 178, 255);
                    let locked = |ui: &mut egui::Ui, label: &str| {
                        ui.add_enabled(false, egui::Button::new(format!("{label}   🔒")).min_size(egui::vec2(ui.available_width(), 25.0)))
                            .on_disabled_hover_text("FMRTE-equivalent surface is catalogued, but this write/read chain is not yet independently certified in Element FM27.");
                    };
                    match entity_type {
                        EntityTabType::Player => {
                            ui.label(egui::RichText::new("PLAYER").small().strong().color(live));
                            macro_rules! pnav { ($label:expr,$variant:expr) => {{
                                let selected=self.player_tab==$variant;
                                if ui.add_sized([ui.available_width(),25.0],egui::Button::new($label).selected(selected).frame(selected)).clicked(){self.player_tab=$variant;}
                            }}; }
                            pnav!("ⓘ  Information", player_panel::PlayerTab::Overview);
                            pnav!("▥  Stats / Data Hub", player_panel::PlayerTab::DataHub);
                            locked(ui,"⇄  Comparison");
                            pnav!("▣  Contract", player_panel::PlayerTab::Contract);
                            locked(ui,"⚑  Career Plans");
                            locked(ui,"↔  Swap Player");
                            locked(ui,"▣  Clone Center");
                            pnav!("⇥  Move to club", player_panel::PlayerTab::TransferPower);
                            pnav!("✚  Injury", player_panel::PlayerTab::Overview);
                            locked(ui,"▣  Work Permit");
                            locked(ui,"☑  Promises");
                            pnav!("⊘  Unavailability", player_panel::PlayerTab::Overview);
                            pnav!("⇄  Transfer Proposals", player_panel::PlayerTab::TransferPower);
                            locked(ui,"⌛  Retire Date");
                            pnav!("⌘  Positions", player_panel::PlayerTab::PositionsTraits);
                            pnav!("★  Preferred Moves", player_panel::PlayerTab::PositionsTraits);
                            pnav!("♟  Relationships", player_panel::PlayerTab::Overview);
                            pnav!("A  Languages", player_panel::PlayerTab::Overview);
                            pnav!("⌕  Scout Information", player_panel::PlayerTab::DataHub);
                            ui.add_space(5.0);
                            pnav!("⚡  Power Tools", player_panel::PlayerTab::PowerTools);
                        }
                        EntityTabType::Staff => {
                            ui.label(egui::RichText::new("STAFF").small().strong().color(live));
                            macro_rules! snav { ($label:expr,$variant:expr) => {{
                                let selected=self.staff_tab==$variant;
                                if ui.add_sized([ui.available_width(),25.0],egui::Button::new($label).selected(selected).frame(selected)).clicked(){self.staff_tab=$variant;}
                            }}; }
                            snav!("ⓘ  Information", staff_panel::StaffTab::Overview);
                            snav!("▣  Contract", staff_panel::StaffTab::Contract);
                            locked(ui,"⚑  Career Plans");
                            locked(ui,"☑  Promises");
                            locked(ui,"↔  Swap Staff");
                            locked(ui,"★  Training Rating");
                            snav!("⌁  Formations / Tendencies", staff_panel::StaffTab::Overview);
                            locked(ui,"♟  Relationships");
                            snav!("⌕  Knowledge", staff_panel::StaffTab::Overview);
                            locked(ui,"⌛  Retire Date");
                            snav!("A  Languages", staff_panel::StaffTab::Overview);
                            ui.add_space(5.0);
                            snav!("⚡  Power Tools", staff_panel::StaffTab::PowerTools);
                        }
                        EntityTabType::Club => {
                            ui.label(egui::RichText::new("CLUB").small().strong().color(live));
                            macro_rules! cnav { ($label:expr,$variant:expr) => {{
                                let selected=self.club_tab==$variant;
                                if ui.add_sized([ui.available_width(),25.0],egui::Button::new($label).selected(selected).frame(selected)).clicked(){self.club_tab=$variant;}
                            }}; }
                            cnav!("ⓘ  Information", club_panel::ClubTab::Overview);
                            cnav!("♟  Squads", club_panel::ClubTab::Squads);
                            cnav!("▣  Finances", club_panel::ClubTab::Finance);
                            locked(ui,"◉  Club Vision");
                            locked(ui,"＋  Possible Signings");
                            locked(ui,"§  Player Clauses");
                            locked(ui,"⇄  Transfer Center");
                            locked(ui,"▱  Kits and Colours");
                            cnav!("⌘  Tactics", club_panel::ClubTab::Tactical);
                            locked(ui,"♟  Staff");
                            locked(ui,"⌁  Affiliations");
                            locked(ui,"▰  Regional Divisions");
                            locked(ui,"▦  Ownership");
                            locked(ui,"♟  Relationships");
                            cnav!("⚙  Tactical Understanding", club_panel::ClubTab::Tactical);
                            cnav!("♥  Supporters / Facilities", club_panel::ClubTab::Facilities);
                            cnav!("⌂  Stadium", club_panel::ClubTab::Stadium);
                            ui.add_space(5.0);
                            cnav!("⚡  Club Power", club_panel::ClubTab::Overview);
                        }
                    }
                    ui.add_space(10.0);
                    ui.separator();
                }

                ui.add_space(4.0);
                ui.label(egui::RichText::new("BROWSE / SWITCH ENTITY").small().strong().weak());
'''
    t = one(t, anchor, block, "context sidebar anchor")

    # Widen sidebar slightly to match FMRTE left navigation and dense labels.
    t = t.replace('.default_width(196.0)\n            .min_width(176.0)', '.default_width(210.0)\n            .min_width(196.0)', 1)
wr(p, t)

print("Element v7.8 FMRTE-inspired premium UI applied.")
