from pathlib import Path

path = Path.cwd() / "src" / "ui" / "pages" / "player_search.rs"
text = path.read_text(encoding="utf-8")

anchor = '''fn element_deal_score(schemas: &'static crate::fields::VersionedSchemas, p: &CachedPlayer) -> u8 {'''
helper = r'''fn element_is_elite_prospect(schemas: &'static crate::fields::VersionedSchemas, p: &CachedPlayer) -> bool {
    let Some(age) = player_age(schemas, p) else { return false; };
    let headroom = p.pa.saturating_sub(p.ca);
    match age {
        0..=19 => p.pa >= 175 && headroom >= 20,
        20..=21 => p.pa >= 180 && headroom >= 12,
        22 => p.pa >= 185 && headroom >= 8,
        _ => false,
    }
}

fn element_player_tier(schemas: &'static crate::fields::VersionedSchemas, p: &CachedPlayer) -> (&'static str, egui::Color32) {
    if element_is_elite_prospect(schemas, p) {
        return ("ELITE PROSPECT", egui::Color32::from_rgb(92, 210, 151));
    }
    let age = player_age(schemas, p).unwrap_or(99);
    let headroom = p.pa.saturating_sub(p.ca);
    if p.ca >= 185 {
        ("WORLD CLASS", egui::Color32::from_rgb(104, 177, 255))
    } else if p.ca >= 170 {
        ("ELITE", egui::Color32::from_rgb(123, 196, 255))
    } else if p.ca >= 155 {
        ("TOP LEVEL", egui::Color32::from_rgb(137, 205, 160))
    } else if age <= 23 && p.pa >= 170 && headroom >= 15 {
        ("HIGH POTENTIAL", egui::Color32::from_rgb(218, 181, 99))
    } else if p.ca >= 140 {
        ("FIRST TEAM", egui::Color32::from_rgb(170, 180, 195))
    } else {
        ("DEVELOPMENT", egui::Color32::from_rgb(130, 140, 158))
    }
}

'''
if helper not in text:
    if anchor not in text:
        raise SystemExit("v4.9.1: deal score anchor missing")
    text = text.replace(anchor, helper + anchor, 1)

old_labels = '''fn element_deal_label(score: u8) -> (&'static str, egui::Color32) {
    match score {
        90..=100 => ("MUST BUY", egui::Color32::from_rgb(72,210,132)),
        82..=89 => ("ELITE VALUE", egui::Color32::from_rgb(112,177,255)),
        72..=81 => ("GOOD DEAL", egui::Color32::from_rgb(121,205,148)),
        60..=71 => ("WATCHLIST", egui::Color32::from_rgb(216,181,99)),
        _ => ("FAIR", egui::Color32::from_rgb(135,145,165)),
    }
}
'''
new_labels = '''fn element_deal_label(score: u8) -> (&'static str, egui::Color32) {
    match score {
        90..=100 => ("MUST BUY", egui::Color32::from_rgb(72,210,132)),
        82..=89 => ("BARGAIN", egui::Color32::from_rgb(112,177,255)),
        72..=81 => ("GOOD VALUE", egui::Color32::from_rgb(121,205,148)),
        60..=71 => ("WATCHLIST", egui::Color32::from_rgb(216,181,99)),
        45..=59 => ("MARKET PRICE", egui::Color32::from_rgb(150,160,178)),
        _ => ("EXPENSIVE", egui::Color32::from_rgb(205,135,135)),
    }
}
'''
if old_labels not in text:
    raise SystemExit("v4.9.1: deal label block missing")
text = text.replace(old_labels, new_labels, 1)

old_filter = '''                12 => age_now.is_some_and(|a| a <= 23) && p.pa >= 170,'''
new_filter = '''                12 => element_is_elite_prospect(schemas, p),'''
if old_filter not in text:
    raise SystemExit("v4.9.1: elite filter marker missing")
text = text.replace(old_filter, new_filter, 1)

text = text.replace('v4.8 • PLAYER + SQUAD COMPLETION', 'v4.9.1 • RECRUITMENT CLARITY')
text = text.replace(
    'Recruitment Board: decoded role fit + best-role ranking + Deal Score v2 + live contract windows. Hover Role Fit for the top 3 roles. Contract-window filters do not claim universal pre-contract eligibility.',
    'Recruitment Board: Player Tier measures absolute level/potential; Deal Value measures transfer value-for-money. ELITE PROSPECT uses age-adjusted PA + development headroom. Contract-window filters use live remaining days.'
)

old_width = 'ui.set_min_width(1160.0);'
if old_width not in text:
    raise SystemExit("v4.9.1: table width marker missing")
text = text.replace(old_width, 'ui.set_min_width(1290.0);', 1)

old_header = '''            col(ui,"WAGE",82.0); col(ui,"EXPIRY",86.0);
            if ui.add_sized([112.0,H],egui::Button::new("ELEMENT DEAL").frame(false)).clicked(){clicked_sort=Some(SortColumn::Deal)}
            if ui.add_sized([122.0,H],egui::Button::new("BEST ROLE / FIT").frame(false)).clicked(){clicked_sort=Some(SortColumn::RoleFit)}
'''
new_header = '''            col(ui,"WAGE",82.0); col(ui,"EXPIRY",86.0); col(ui,"PLAYER TIER",112.0);
            if ui.add_sized([128.0,H],egui::Button::new("DEAL VALUE").frame(false)).clicked(){clicked_sort=Some(SortColumn::Deal)}
            if ui.add_sized([122.0,H],egui::Button::new("BEST ROLE / FIT").frame(false)).clicked(){clicked_sort=Some(SortColumn::RoleFit)}
'''
if old_header not in text:
    raise SystemExit("v4.9.1: table header marker missing")
text = text.replace(old_header, new_header, 1)

old_row_prep = '''                let deal=element_deal_score(schemas,p); let (deal_label,deal_color)=element_deal_label(deal);
                let (best_role,best_fit)=element_best_role(schemas,p);
'''
new_row_prep = '''                let deal=element_deal_score(schemas,p); let (deal_label,deal_color)=element_deal_label(deal);
                let (tier_label,tier_color)=element_player_tier(schemas,p);
                let (best_role,best_fit)=element_best_role(schemas,p);
'''
if old_row_prep not in text:
    raise SystemExit("v4.9.1: row prep marker missing")
text = text.replace(old_row_prep, new_row_prep, 1)

old_row = '''                    ui.add_sized([80.0,H],egui::Label::new(element_money(p.value))); ui.add_sized([82.0,H],egui::Label::new(wage)); ui.add_sized([86.0,H],egui::Label::new(expiry));
                    ui.add_sized([112.0,H],egui::Label::new(egui::RichText::new(format!("{} {}",deal_label,deal)).color(deal_color))).on_hover_text("Element Deal Score v2: quality + upside + age + relative market value + contract window + wage + reliability.");
                    ui.add_sized([122.0,H],egui::Label::new(role)).on_hover_text(format!("Top role fits: {role_tip}"));
'''
new_row = '''                    ui.add_sized([80.0,H],egui::Label::new(element_money(p.value))); ui.add_sized([82.0,H],egui::Label::new(wage)); ui.add_sized([86.0,H],egui::Label::new(expiry));
                    ui.add_sized([112.0,H],egui::Label::new(egui::RichText::new(tier_label).color(tier_color))).on_hover_text("Player Tier: absolute current level plus age-adjusted development ceiling. This is separate from transfer value-for-money.");
                    ui.add_sized([128.0,H],egui::Label::new(egui::RichText::new(format!("{} {}",deal_label,deal)).color(deal_color))).on_hover_text("Deal Value: Element value-for-money score using quality, upside, age, market value, contract window, wage and reliability. An elite player can still be expensive.");
                    ui.add_sized([122.0,H],egui::Label::new(role)).on_hover_text(format!("Top role fits: {role_tip}"));
'''
if old_row not in text:
    raise SystemExit("v4.9.1: row render marker missing")
text = text.replace(old_row, new_row, 1)

path.write_text(text, encoding="utf-8")
print("Element v4.9.1 recruitment clarity applied: strict elite prospects + Player Tier + Deal Value semantics.")
