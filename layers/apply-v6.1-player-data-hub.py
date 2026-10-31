from pathlib import Path
import shutil

root = Path.cwd()
repo = Path(__file__).resolve().parent.parent

# Ship the Data Hub metric registry as an embedded fallback too.
src_data = root / "src" / "element_data"
src_data.mkdir(parents=True, exist_ok=True)
source = repo / "config" / "element-v6" / "datahub.json"
if not source.exists():
    raise SystemExit(f"v6.1 data hub: missing {source}")
shutil.copy2(source, src_data / "datahub.json")

module = r'''//! Element v6.1 Player Data Hub.
//!
//! Attribute analytics are live against the loaded player cache. Match-event
//! metrics (xG, xA, dribbles/90, key passes, etc.) are represented in the JSON
//! registry but stay visibly gated until their FM27 record chains are certified.

use std::sync::Arc;
use eframe::egui;
use serde_json::Value;

use crate::cache::{CachedPlayer, EntityCache};
use crate::fields::{self, HasSubRecords, SubRecordId};
use crate::player::PlayerRecord;

impl HasSubRecords for CachedPlayer {
    fn sub_record(&self, _id: SubRecordId) -> Option<&[u8]> { None }
}

#[derive(Clone, Default)]
struct DomainScore {
    id: String,
    label: String,
    score: f32,
    cohort_avg: f32,
    percentile: f32,
    metrics: Vec<MetricScore>,
}

#[derive(Clone, Default)]
struct MetricScore {
    label: String,
    value: f32,
    cohort_avg: f32,
    percentile: f32,
}

#[derive(Clone, Default)]
struct HubAnalytics {
    ca: f32,
    pa: f32,
    ca_percentile: f32,
    pa_percentile: f32,
    cohort_size: usize,
    sampled: bool,
    domains: Vec<DomainScore>,
}

fn registry() -> Value {
    let external = std::env::current_exe().ok()
        .and_then(|p| p.parent().map(|p| p.join("element-data").join("datahub.json")))
        .and_then(|p| std::fs::read_to_string(p).ok())
        .and_then(|s| serde_json::from_str::<Value>(&s).ok());
    external.unwrap_or_else(|| serde_json::from_str(include_str!("../element_data/datahub.json")).unwrap_or(Value::Null))
}

fn cache(ui: &egui::Ui) -> Option<Arc<EntityCache>> {
    ui.ctx().data_mut(|d| {
        d.get_temp::<Option<Arc<EntityCache>>>(egui::Id::new("entity_link_cache"))
    }).flatten()
}

fn percentile(value: f32, values: &[f32]) -> f32 {
    if values.is_empty() { return 0.0; }
    let below = values.iter().filter(|v| **v <= value).count();
    (below as f32 / values.len() as f32) * 100.0
}

fn field_value_player(player: &PlayerRecord, key: &str) -> Option<f32> {
    player.field_u8(key).map(|v| v as f32)
}

fn field_value_cached(
    schemas: &'static crate::fields::VersionedSchemas,
    player: &CachedPlayer,
    key: &str,
) -> Option<f32> {
    let field = schemas.field(key)?;
    fields::read_field_u8(player, &player.raw, field).map(|v| v as f32)
}

fn section_attribute_metrics(section: &Value) -> Vec<(String, String, f32)> {
    section.get("metrics").and_then(Value::as_array).into_iter().flatten()
        .filter(|m| m.get("source").and_then(Value::as_str) == Some("attribute"))
        .filter_map(|m| {
            Some((
                m.get("field")?.as_str()?.to_owned(),
                m.get("label")?.as_str()?.to_owned(),
                m.get("weight").and_then(Value::as_f64).unwrap_or(1.0) as f32,
            ))
        }).collect()
}

fn weighted_score_player(player: &PlayerRecord, metrics: &[(String, String, f32)]) -> Option<f32> {
    let mut total = 0.0;
    let mut weights = 0.0;
    for (key, _, weight) in metrics {
        if let Some(v) = field_value_player(player, key) {
            total += (v / 20.0 * 100.0) * *weight;
            weights += *weight;
        }
    }
    (weights > 0.0).then_some(total / weights)
}

fn weighted_score_cached(
    schemas: &'static crate::fields::VersionedSchemas,
    player: &CachedPlayer,
    metrics: &[(String, String, f32)],
) -> Option<f32> {
    let mut total = 0.0;
    let mut weights = 0.0;
    for (key, _, weight) in metrics {
        if let Some(v) = field_value_cached(schemas, player, key) {
            total += (v / 20.0 * 100.0) * *weight;
            weights += *weight;
        }
    }
    (weights > 0.0).then_some(total / weights)
}

fn compute(
    schemas: &'static crate::fields::VersionedSchemas,
    player: &PlayerRecord,
    cache: Option<&EntityCache>,
) -> HubAnalytics {
    let reg = registry();
    let all = cache.map(|c| c.players.as_slice()).unwrap_or(&[]);
    let cap = 20_000usize;
    let step = (all.len() / cap).max(1);
    let cohort: Vec<&CachedPlayer> = all.iter().step_by(step).collect();
    let sampled = step > 1;

    let ca = player.field_u8("p_ca").unwrap_or(0) as f32;
    let pa = player.field_u8("p_pa").unwrap_or(0) as f32;
    let ca_values: Vec<f32> = cohort.iter().map(|p| p.ca as f32).collect();
    let pa_values: Vec<f32> = cohort.iter().map(|p| p.pa as f32).collect();

    let mut domains = Vec::new();
    if let Some(sections) = reg.get("sections").and_then(Value::as_array) {
        for section in sections {
            let id = section.get("id").and_then(Value::as_str).unwrap_or("unknown").to_owned();
            // Goalkeeping is kept as a detailed section but omitted from the main
            // outfield radar unless the caller later adds a position-aware mode.
            let label = section.get("label").and_then(Value::as_str).unwrap_or("Profile").to_owned();
            let attrs = section_attribute_metrics(section);
            if attrs.is_empty() { continue; }
            let score = weighted_score_player(player, &attrs).unwrap_or(0.0);
            let cohort_scores: Vec<f32> = cohort.iter()
                .filter_map(|p| weighted_score_cached(schemas, p, &attrs))
                .collect();
            let avg = if cohort_scores.is_empty() { 0.0 } else { cohort_scores.iter().sum::<f32>() / cohort_scores.len() as f32 };

            let mut metric_rows = Vec::new();
            for (key, metric_label, _) in attrs.iter().take(6) {
                let value = field_value_player(player, key).unwrap_or(0.0);
                let values: Vec<f32> = cohort.iter().filter_map(|p| field_value_cached(schemas, p, key)).collect();
                let metric_avg = if values.is_empty() { 0.0 } else { values.iter().sum::<f32>() / values.len() as f32 };
                metric_rows.push(MetricScore {
                    label: metric_label.clone(),
                    value,
                    cohort_avg: metric_avg,
                    percentile: percentile(value, &values),
                });
            }

            domains.push(DomainScore {
                id,
                label,
                score,
                cohort_avg: avg,
                percentile: percentile(score, &cohort_scores),
                metrics: metric_rows,
            });
        }
    }

    HubAnalytics {
        ca,
        pa,
        ca_percentile: percentile(ca, &ca_values),
        pa_percentile: percentile(pa, &pa_values),
        cohort_size: cohort.len(),
        sampled,
        domains,
    }
}

fn analytics(
    schemas: &'static crate::fields::VersionedSchemas,
    ui: &egui::Ui,
    player: &PlayerRecord,
) -> Arc<HubAnalytics> {
    let c = cache(ui);
    let count = c.as_ref().map(|c| c.players.len()).unwrap_or(0);
    let id = egui::Id::new(("element_v61_player_hub", player.addr, count));
    if let Some(existing) = ui.ctx().data_mut(|d| d.get_temp::<Arc<HubAnalytics>>(id)) {
        return existing;
    }
    let computed = Arc::new(compute(schemas, player, c.as_deref()));
    ui.ctx().data_mut(|d| d.insert_temp(id, computed.clone()));
    computed
}

fn card(ui: &mut egui::Ui, title: &str, value: String, sub: String) {
    egui::Frame::group(ui.style())
        .inner_margin(egui::Margin::same(8))
        .show(ui, |ui| {
            ui.set_min_width(112.0);
            ui.label(egui::RichText::new(title).size(8.5).strong().weak());
            ui.label(egui::RichText::new(value).size(20.0).strong());
            ui.label(egui::RichText::new(sub).size(8.0).weak());
        });
}

fn donut(ui: &mut egui::Ui, label: &str, score: f32, percentile: f32) {
    let (rect, _) = ui.allocate_exact_size(egui::vec2(112.0, 122.0), egui::Sense::hover());
    let painter = ui.painter_at(rect);
    let center = egui::pos2(rect.center().x, rect.top() + 48.0);
    let radius = 31.0;
    painter.circle_stroke(center, radius, egui::Stroke::new(8.0, egui::Color32::from_gray(48)));
    let n = 48usize;
    let sweep = (score.clamp(0.0, 100.0) / 100.0) * std::f32::consts::TAU;
    if sweep > 0.01 {
        let mut pts = Vec::with_capacity(n + 1);
        for i in 0..=n {
            let t = -std::f32::consts::FRAC_PI_2 + sweep * (i as f32 / n as f32);
            pts.push(center + egui::vec2(t.cos() * radius, t.sin() * radius));
        }
        painter.add(egui::Shape::line(pts, egui::Stroke::new(8.0, egui::Color32::from_rgb(211, 54, 80))));
    }
    painter.text(center, egui::Align2::CENTER_CENTER, format!("{score:.0}"), egui::FontId::proportional(18.0), egui::Color32::WHITE);
    painter.text(egui::pos2(rect.center().x, rect.top() + 88.0), egui::Align2::CENTER_CENTER, label, egui::FontId::proportional(9.0), egui::Color32::LIGHT_GRAY);
    painter.text(egui::pos2(rect.center().x, rect.top() + 104.0), egui::Align2::CENTER_CENTER, format!("P{percentile:.0}"), egui::FontId::proportional(9.0), egui::Color32::from_rgb(148, 180, 255));
}

fn comparison_bar(ui: &mut egui::Ui, metric: &MetricScore) {
    ui.horizontal(|ui| {
        ui.set_min_width(470.0);
        ui.label(egui::RichText::new(&metric.label).size(9.0)).on_hover_text(format!("Loaded-database percentile: {:.0}", metric.percentile));
        let width = 210.0;
        let (rect, _) = ui.allocate_exact_size(egui::vec2(width, 11.0), egui::Sense::hover());
        let p = ui.painter_at(rect);
        p.rect_filled(rect, 3.0, egui::Color32::from_gray(42));
        let current_w = width * (metric.value / 20.0).clamp(0.0, 1.0);
        let avg_w = width * (metric.cohort_avg / 20.0).clamp(0.0, 1.0);
        p.rect_filled(egui::Rect::from_min_size(rect.min, egui::vec2(current_w, rect.height())), 3.0, egui::Color32::from_rgb(211, 54, 80));
        let x = rect.left() + avg_w;
        p.line_segment([egui::pos2(x, rect.top()-2.0), egui::pos2(x, rect.bottom()+2.0)], egui::Stroke::new(1.5, egui::Color32::WHITE));
        ui.label(egui::RichText::new(format!("{:.0} /20", metric.value)).size(9.0).strong());
        ui.label(egui::RichText::new(format!("P{:.0}", metric.percentile)).size(8.5).color(egui::Color32::from_rgb(148, 180, 255)));
    });
}

fn radar(ui: &mut egui::Ui, domains: &[DomainScore]) {
    let axes: Vec<&DomainScore> = domains.iter().filter(|d| d.id != "goalkeeping").take(5).collect();
    if axes.len() < 3 { return; }
    let (rect, _) = ui.allocate_exact_size(egui::vec2(330.0, 250.0), egui::Sense::hover());
    let p = ui.painter_at(rect);
    let center = rect.center();
    let radius = 92.0;
    let n = axes.len();
    for ring in [0.25f32, 0.5, 0.75, 1.0] {
        let pts: Vec<egui::Pos2> = (0..n).map(|i| {
            let a = -std::f32::consts::FRAC_PI_2 + i as f32 / n as f32 * std::f32::consts::TAU;
            center + egui::vec2(a.cos(), a.sin()) * radius * ring
        }).collect();
        let mut closed = pts.clone();
        closed.push(pts[0]);
        p.add(egui::Shape::line(closed, egui::Stroke::new(1.0, egui::Color32::from_gray(62))));
    }
    let cohort_pts: Vec<egui::Pos2> = axes.iter().enumerate().map(|(i,d)| {
        let a = -std::f32::consts::FRAC_PI_2 + i as f32 / n as f32 * std::f32::consts::TAU;
        center + egui::vec2(a.cos(), a.sin()) * radius * (d.cohort_avg / 100.0).clamp(0.0,1.0)
    }).collect();
    let player_pts: Vec<egui::Pos2> = axes.iter().enumerate().map(|(i,d)| {
        let a = -std::f32::consts::FRAC_PI_2 + i as f32 / n as f32 * std::f32::consts::TAU;
        center + egui::vec2(a.cos(), a.sin()) * radius * (d.score / 100.0).clamp(0.0,1.0)
    }).collect();
    p.add(egui::Shape::convex_polygon(cohort_pts.clone(), egui::Color32::from_rgba_unmultiplied(105,135,180,30), egui::Stroke::new(1.5, egui::Color32::from_rgb(130,160,205))));
    p.add(egui::Shape::convex_polygon(player_pts.clone(), egui::Color32::from_rgba_unmultiplied(211,54,80,42), egui::Stroke::new(2.0, egui::Color32::from_rgb(235,75,100))));
    for (i,d) in axes.iter().enumerate() {
        let a = -std::f32::consts::FRAC_PI_2 + i as f32 / n as f32 * std::f32::consts::TAU;
        let label_pos = center + egui::vec2(a.cos(), a.sin()) * (radius + 24.0);
        p.text(label_pos, egui::Align2::CENTER_CENTER, d.label.replace(" & Carrying", ""), egui::FontId::proportional(8.5), egui::Color32::LIGHT_GRAY);
    }
}

pub fn show(
    schemas: &'static crate::fields::VersionedSchemas,
    ui: &mut egui::Ui,
    player: &PlayerRecord,
) {
    let a = analytics(schemas, ui, player);
    ui.horizontal(|ui| {
        ui.label(egui::RichText::new("PLAYER DATA HUB").size(13.0).strong());
        ui.separator();
        ui.label(egui::RichText::new("LIVE ATTRIBUTE ANALYTICS • MATCH DATA PIPELINE READY").size(8.0).weak());
    });
    ui.add_space(6.0);

    ui.horizontal_wrapped(|ui| {
        card(ui, "CURRENT ABILITY", format!("{:.0}", a.ca), format!("P{:.0} vs database", a.ca_percentile));
        card(ui, "POTENTIAL ABILITY", format!("{:.0}", a.pa), format!("P{:.0} vs database", a.pa_percentile));
        card(ui, "COMPARISON COHORT", a.cohort_size.to_string(), if a.sampled { "sampled loaded players".into() } else { "loaded players".into() });
        let overall = if a.domains.is_empty() { 0.0 } else { a.domains.iter().filter(|d| d.id != "goalkeeping").map(|d| d.score).sum::<f32>() / a.domains.iter().filter(|d| d.id != "goalkeeping").count().max(1) as f32 };
        card(ui, "PROFILE INDEX", format!("{overall:.0}"), "weighted attributes /100".into());
    });

    ui.add_space(8.0);
    ui.horizontal(|ui| {
        ui.vertical(|ui| {
            ui.label(egui::RichText::new("PROFILE RADAR").strong().size(9.0));
            ui.label(egui::RichText::new("Red = player • blue = cohort average").size(7.5).weak());
            radar(ui, &a.domains);
        });
        ui.separator();
        ui.vertical(|ui| {
            ui.label(egui::RichText::new("DOMAIN PERCENTILES").strong().size(9.0));
            ui.horizontal_wrapped(|ui| {
                for d in a.domains.iter().filter(|d| d.id != "goalkeeping").take(5) {
                    donut(ui, &d.label, d.score, d.percentile);
                }
            });
        });
    });

    ui.add_space(8.0);
    for d in &a.domains {
        egui::CollapsingHeader::new(format!("{}  •  {:.0}/100  •  P{:.0}", d.label, d.score, d.percentile))
            .default_open(matches!(d.id.as_str(), "dribbling" | "attacking" | "creation"))
            .show(ui, |ui| {
                for metric in &d.metrics { comparison_bar(ui, metric); }
            });
    }

    ui.add_space(8.0);
    egui::Frame::group(ui.style())
        .fill(egui::Color32::from_rgb(30, 28, 34))
        .stroke(egui::Stroke::new(1.0, egui::Color32::from_rgb(92, 74, 80)))
        .inner_margin(egui::Margin::same(8))
        .show(ui, |ui| {
            ui.label(egui::RichText::new("MATCH PERFORMANCE DATA").strong().size(9.0));
            ui.label("Goals/90 • xG/90 • Assists/90 • xA/90 • Successful Dribbles/90 • Dribble Success % • Key Passes/90 • Pass % • Tackles Won/90 • Interceptions/90 • Aerial Win % • Save %");
            ui.label(egui::RichText::new("Pipeline and JSON definitions are installed. Values remain locked until FM27 match-stat/history record chains are certified; Element does not fabricate performance numbers.").size(8.0).weak());
        });

    ui.add_space(6.0);
    ui.horizontal_wrapped(|ui| {
        ui.label(egui::RichText::new("COHORTS").strong().size(8.5));
        ui.label("✓ Loaded Database");
        ui.label("🔒 Same League").on_hover_text("Unlocks when player → competition/league membership is certified.");
        ui.label("🔒 Same Position").on_hover_text("Position-filtered cache cohort is queued for the next mapping pass.");
        ui.label("🔒 Season / Competition").on_hover_text("Requires native match-history/stat rows.");
    });
}
'''

(root / "src" / "ui" / "player_data_hub.rs").write_text(module, encoding="utf-8")

# Register module.
p = root / "src" / "ui" / "mod.rs"
t = p.read_text(encoding="utf-8")
if "pub mod player_data_hub;" not in t:
    marker = "pub mod player_panel;\n"
    if marker not in t:
        raise SystemExit("v6.1 data hub: ui/mod.rs player_panel marker missing")
    t = t.replace(marker, marker + "pub mod player_data_hub;\n", 1)
p.write_text(t, encoding="utf-8")

# Add Data Hub as a native Player sub-tab.
p = root / "src" / "ui" / "player_panel.rs"
t = p.read_text(encoding="utf-8")

if "DataHub," not in t:
    enum_marker = "    Overview,\n"
    if enum_marker not in t:
        start = t.find("pub enum PlayerTab")
        raise SystemExit("v6.1 data hub: PlayerTab Overview marker missing\n" + t[start:start+900])
    t = t.replace(enum_marker, enum_marker + "    DataHub,\n", 1)

if 'PlayerTab::DataHub, "Data Hub"' not in t:
    tab_marker = '        ui.selectable_value(tab, PlayerTab::Overview, "Overview");\n'
    if tab_marker not in t:
        start = t.find("// Sub-tab bar")
        raise SystemExit("v6.1 data hub: tab bar marker missing\n" + t[start:start+1200])
    t = t.replace(tab_marker, tab_marker + '        ui.selectable_value(tab, PlayerTab::DataHub, "Data Hub");\n', 1)

if "PlayerTab::DataHub =>" not in t:
    match_marker = "        PlayerTab::PositionsTraits =>"
    pos = t.find(match_marker)
    if pos < 0:
        start = t.find("egui::ScrollArea::vertical")
        raise SystemExit("v6.1 data hub: PlayerTab render match marker missing\n" + t[start:start+1800])
    t = t[:pos] + "        PlayerTab::DataHub => crate::ui::player_data_hub::show(schemas, ui, player),\n" + t[pos:]

p.write_text(t, encoding="utf-8")
print("Element v6.1 Player Data Hub analytics layer applied successfully.")
