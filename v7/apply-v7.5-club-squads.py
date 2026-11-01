from pathlib import Path

root=Path.cwd()

def rd(path):
    p=root/path
    if not p.exists(): raise SystemExit(f"v7.5 missing {path}")
    return p.read_text(encoding="utf-8")

def wr(path,text): (root/path).write_text(text,encoding="utf-8")

def one(text,old,new,label):
    if old not in text: raise SystemExit(f"v7.5 marker missing: {label}")
    return text.replace(old,new,1)

# -----------------------------------------------------------------------------
# Player navigation target from club roster rows.
# -----------------------------------------------------------------------------
p="src/ui/navigation.rs"
t=rd(p)
if "pub struct PlayerTarget" not in t:
    marker='''#[derive(Clone, Debug, PartialEq, Eq)]
pub struct ClubTarget {
'''
    defs='''#[derive(Clone, Debug, PartialEq, Eq)]
pub struct PlayerTarget {
    pub addr: u64,
    pub index: usize,
    pub name: String,
}

'''
    t=one(t,marker,defs+marker,"PlayerTarget struct")
if "pub fn request_player_target" not in t:
    marker="pub fn take_club_target(ctx: &egui::Context) -> Option<ClubTarget> {\n"
    idx=t.find(marker)
    if idx<0: raise SystemExit("v7.5 marker missing: take_club_target")
    # insert functions immediately before club take function
    funcs='''pub fn request_player_target(ui: &egui::Ui, addr: u64, index: usize, name: String) {
    ui.ctx().data_mut(|d| d.insert_temp(
        egui::Id::new("open_related_player"),
        PlayerTarget { addr, index, name },
    ));
}

pub fn take_player_target(ctx: &egui::Context) -> Option<PlayerTarget> {
    ctx.data_mut(|d| {
        let id = egui::Id::new("open_related_player");
        let target = d.get_temp::<PlayerTarget>(id);
        d.remove::<PlayerTarget>(id);
        target
    })
}

'''
    t=t[:idx]+funcs+t[idx:]
wr(p,t)

# -----------------------------------------------------------------------------
# Club Squads tab.
# -----------------------------------------------------------------------------
p="src/ui/club_panel.rs"
t=rd(p)
if "    Squads,\n" not in t:
    t=one(t,"    Overview,\n","    Overview,\n    Squads,\n","Squads enum")
    t=one(t,'        ui.selectable_value(tab, ClubTab::Overview, "Overview");\n','        ui.selectable_value(tab, ClubTab::Overview, "Overview");\n        ui.selectable_value(tab, ClubTab::Squads, "Squads");\n',"Squads tab button")
    t=one(t,"        ClubTab::Overview => show_overview(schemas, ui, club, &mut edits),\n","        ClubTab::Overview => show_overview(schemas, ui, club, &mut edits),\n        ClubTab::Squads => show_squads(schemas, ui, club, entity_cache, today),\n","Squads match arm")

# Add in-game date argument to show() after entity cache.
if "today: Option<crate::game_date::GameDate>" not in t.split("pub fn show",1)[1].split("{",1)[0]:
    t=one(t,
        "    entity_cache: Option<&crate::cache::EntityCache>,\n) -> (Vec<FieldEdit>, Option<crate::ui::club_policy::Action>) {",
        "    entity_cache: Option<&crate::cache::EntityCache>,\n    today: Option<crate::game_date::GameDate>,\n) -> (Vec<FieldEdit>, Option<crate::ui::club_policy::Action>) {",
        "club show date arg")

if "fn show_squads(" not in t:
    marker="fn show_power_tools(\n"
    idx=t.find(marker)
    if idx<0: raise SystemExit("v7.5 marker missing: show_power_tools")
    fn=r'''fn squad_primary_position(
    schemas: &'static crate::fields::VersionedSchemas,
    p: &crate::cache::CachedPlayer,
) -> String {
    let mut best: Option<(&'static str, u8)> = None;
    for f in schemas.fields_for_category(crate::fields::Entity::Player, crate::fields::Category::Positions) {
        if let Some(v) = crate::fields::read_field_u8(p, &p.raw, f) {
            if v > best.map(|(_,b)|b).unwrap_or(0) {
                best = Some((f.label, v));
            }
        }
    }
    best.map(|(name,v)| format!("{} ({})", name.replace("Position: ", ""), v)).unwrap_or_else(|| "—".into())
}

fn squad_morale(
    schemas: &'static crate::fields::VersionedSchemas,
    p: &crate::cache::CachedPlayer,
) -> Option<u8> {
    schemas.field("p_morale").and_then(|f| crate::fields::read_field_u8(p, &p.raw, f))
}

fn squad_money(v: Option<u64>) -> String {
    match v {
        Some(n) if n >= 1_000_000 => format!("£{:.1}m", n as f64 / 1_000_000.0),
        Some(n) if n >= 1_000 => format!("£{:.0}k", n as f64 / 1_000.0),
        Some(n) => format!("£{n}"),
        None => "—".into(),
    }
}

fn show_squads(
    schemas: &'static crate::fields::VersionedSchemas,
    ui: &mut egui::Ui,
    club: &ClubView,
    cache: Option<&crate::cache::EntityCache>,
    today: Option<crate::game_date::GameDate>,
) {
    ui.horizontal_wrapped(|ui| {
        ui.heading("Live Club Squads");
        ui.label(egui::RichText::new("ELEMENT v7.5 • ENTITY CACHE LIVE").strong().color(egui::Color32::from_rgb(116,145,255)));
    });
    ui.label(egui::RichText::new("Roster rows come directly from the current FM27 entity cache. Click a player to open the full Player editor.").weak());
    ui.add_space(6.0);

    let Some(cache)=cache else { ui.label("Entity cache unavailable — reload the save."); return; };
    let search_id=egui::Id::new(("element_v7_squad_search",club.addr));
    let sort_id=egui::Id::new(("element_v7_squad_sort",club.addr));
    let mut query=ui.ctx().data_mut(|d|d.get_temp::<String>(search_id).unwrap_or_default());
    let mut sort=ui.ctx().data_mut(|d|d.get_temp::<String>(sort_id).unwrap_or_else(||"CA".into()));
    ui.horizontal_wrapped(|ui|{
        ui.label("Search:");
        if ui.add_sized([220.0,22.0],egui::TextEdit::singleline(&mut query).hint_text("Player name…")).changed(){ui.ctx().data_mut(|d|d.insert_temp(search_id,query.clone()));}
        ui.separator();
        egui::ComboBox::from_id_salt(("element_v7_squad_sort_combo",club.addr)).selected_text(format!("Sort: {sort}")).show_ui(ui,|ui|{
            for s in ["CA","PA","Name","Value","Morale"]{if ui.selectable_value(&mut sort,s.to_owned(),s).changed(){ui.ctx().data_mut(|d|d.insert_temp(sort_id,sort.clone()));}}
        });
    });

    let q=query.trim().to_lowercase();
    let mut rows:Vec<&crate::cache::CachedPlayer>=cache.players.iter()
        .filter(|p|p.club_id==Some(club.uid))
        .filter(|p|q.is_empty()||p.name.to_lowercase().contains(&q))
        .collect();
    match sort.as_str(){
        "PA"=>rows.sort_by(|a,b|b.pa.cmp(&a.pa).then_with(||a.name.cmp(&b.name))),
        "Name"=>rows.sort_by(|a,b|a.name.cmp(&b.name)),
        "Value"=>rows.sort_by(|a,b|b.value.unwrap_or(0).cmp(&a.value.unwrap_or(0))),
        "Morale"=>rows.sort_by_key(|p|std::cmp::Reverse(squad_morale(schemas,p).unwrap_or(0))),
        _=>rows.sort_by(|a,b|b.ca.cmp(&a.ca).then_with(||a.name.cmp(&b.name))),
    }
    let loans=rows.iter().filter(|p|p.owning_club_id.is_some()&&p.owning_club_id!=p.club_id).count();
    let high_pa=rows.iter().filter(|p|p.pa>=150).count();
    ui.horizontal_wrapped(|ui|{
        ui.label(egui::RichText::new(format!("{} PLAYER(S)",rows.len())).strong());
        ui.separator();ui.label(format!("{loans} LOANED IN / DIFFERENT OWNER"));
        ui.separator();ui.label(format!("{high_pa} PA ≥ 150"));
    });
    ui.add_space(4.0);

    egui::ScrollArea::vertical().max_height(ui.available_height().max(260.0)).show(ui,|ui|{
        egui::Grid::new(("element_v7_squad_grid",club.addr)).striped(true).min_col_width(52.0).spacing([10.0,5.0]).show(ui,|ui|{
            for h in ["Player","Position","Age~","CA","PA","Morale","Value","Status"]{ui.label(egui::RichText::new(h).strong());}
            ui.end_row();
            for p in rows{
                let name=if p.name.is_empty(){format!("UID {}",p.uid)}else{p.name.clone()};
                if ui.link(&name).on_hover_text("Open Player editor").clicked(){
                    crate::ui::navigation::request_player_target(ui,p.addr,p.index,name.clone());
                }
                ui.label(squad_primary_position(schemas,p));
                let age=today.and_then(|d|(p.dob_year>0&&d.year>=p.dob_year).then_some(d.year-p.dob_year));
                ui.label(age.map(|a|a.to_string()).unwrap_or_else(||"—".into()));
                ui.label(egui::RichText::new(p.ca.to_string()).strong());
                ui.label(egui::RichText::new(p.pa.to_string()).strong());
                ui.label(squad_morale(schemas,p).map(|m|format!("{m}/20")).unwrap_or_else(||"—".into()));
                ui.label(squad_money(p.value));
                let status=if p.owning_club_id.is_some()&&p.owning_club_id!=p.club_id{"LOAN / OTHER OWNER"}else{"CLUB"};
                ui.label(status);
                ui.end_row();
            }
        });
    });
}

'''
    t=t[:idx]+fn+t[idx:]
wr(p,t)

# -----------------------------------------------------------------------------
# App: pass date to Club panel + consume player target.
# -----------------------------------------------------------------------------
p="src/app.rs"
t=rd(p)
# v7.0 already added cache argument; add date after it.
old='''                                        self.conn.is_writable() && !self.change_history.is_pending() && edits.is_empty(),
                                        cache_arc.as_deref());'''
new='''                                        self.conn.is_writable() && !self.change_history.is_pending() && edits.is_empty(),
                                        cache_arc.as_deref(), self.game_date);'''
if old in t:
    t=t.replace(old,new,1)
elif "cache_arc.as_deref(), self.game_date);" not in t:
    raise SystemExit("v7.5 marker missing: club_panel app call")

if "navigation::take_player_target(ctx)" not in t:
    marker='''        if let Some(target) = navigation::take_club_target(ctx) {
            let entry = HistoryEntry {
                entity_type: EntityTabType::Club,
                addr: target.addr,
                index: target.index,
                display_name: target.name,
            };
            self.push_history(entry.clone());
            self.activate_history_entry(entry);
        }
'''
    repl=marker+'''        if let Some(target) = navigation::take_player_target(ctx) {
            let entry = HistoryEntry {
                entity_type: EntityTabType::Player,
                addr: target.addr,
                index: target.index,
                display_name: target.name,
            };
            self.push_history(entry.clone());
            self.activate_history_entry(entry);
        }
'''
    t=one(t,marker,repl,"player navigation consume")
wr(p,t)

print("Element v7.5 Club Squads workspace applied.")
