$ErrorActionPreference = 'Stop'
$SourceRoot = (Get-Location).Path

function Read-Text([string]$RelativePath) {
    $Path = Join-Path $SourceRoot $RelativePath
    if (-not (Test-Path -LiteralPath $Path)) { throw "Source file not found: $Path" }
    [IO.File]::ReadAllText($Path)
}
function Write-Text([string]$RelativePath, [string]$Text) {
    $Path = Join-Path $SourceRoot $RelativePath
    [IO.File]::WriteAllText($Path, $Text, [Text.UTF8Encoding]::new($false))
}
function Replace-Required([string]$Text, [string]$Old, [string]$New, [string]$Label) {
    if (-not $Text.Contains($Old)) { throw "v4.2a: expected source fragment not found: $Label" }
    $Text.Replace($Old, $New)
}

# -----------------------------------------------------------------------------
# Element v4.2a — PLAYER INTELLIGENCE / SCOUTING HUB
# Read-side only. Gender comes from the verified current club record. Deal Score
# and Role Fit are explicitly Element heuristics built from verified cached data.
# -----------------------------------------------------------------------------

# Cached gender inherited from verified current club membership.
$cachePath = 'src/cache.rs'
$cache = Read-Text $cachePath
$cache = Replace-Required $cache @'
    pub club_id:   Option<u32>,
    pub value:     Option<u64>,
'@ @'
    pub club_id:   Option<u32>,
    /// Current-club gender: 0 MEN, 1 WOMEN. None for free agents/unresolved membership.
    pub gender:    Option<u8>,
    pub value:     Option<u64>,
'@ 'CachedPlayer gender'
Write-Text $cachePath $cache

$bulkPath = 'src/bridge/bulk_load.rs'
$bulk = Read-Text $bulkPath
$bulk = Replace-Required $bulk @'
            nation_id: None, club_id: None, value: None,
            wage: None, squad_status: None, morale: None,
'@ @'
            nation_id: None, club_id: None, gender: None, value: None,
            wage: None, squad_status: None, morale: None,
'@ 'CachedPlayer gender initializer'
$bulk = Replace-Required $bulk @'
        let clubs_by_addr: HashMap<u64, u32> =
            clubs.iter().map(|c| (c.addr, c.uid)).collect();
        for player in &mut players {
'@ @'
        let clubs_by_addr: HashMap<u64, u32> =
            clubs.iter().map(|c| (c.addr, c.uid)).collect();
        let club_genders: HashMap<u32, u8> =
            clubs.iter().map(|c| (c.uid, c.gender)).collect();
        for player in &mut players {
'@ 'club gender index'
$bulk = Replace-Required $bulk @'
            .and_then(|club_addr| clubs_by_addr.get(&club_addr).copied());

            // v3.8.3: morale is a verified direct player/person byte.
'@ @'
            .and_then(|club_addr| clubs_by_addr.get(&club_addr).copied());
            player.gender = player.club_id.and_then(|uid| club_genders.get(&uid).copied());

            // v3.8.3: morale is a verified direct player/person byte.
'@ 'gender assignment after membership'
Write-Text $bulkPath $bulk

$path = 'src/ui/pages/player_search.rs'
$text = Read-Text $path

$text = Replace-Required $text @'
pub enum SortColumn {
    #[default]
    Uid,
    Name,
    Ca,
    Pa,
    Age,
}
'@ @'
pub enum SortColumn {
    #[default]
    Uid,
    Name,
    Ca,
    Pa,
    Age,
    Value,
    Deal,
    RoleFit,
}
'@ 'sort enum'

$text = Replace-Required $text @'
    pub position_minimums: [u8; 15],
    // --- Sort state ---
'@ @'
    pub position_minimums: [u8; 15],
    // --- Element v4.2 intelligence ---
    pub gender_mask: u8,
    pub quick_mode: u8,
    pub best_position: i8,
    pub role: u8,
    pub role_min: u8,
    pub attribute_filter: u8,
    pub attribute_min: u8,
    // --- Sort state ---
'@ 'state fields'

$text = Replace-Required $text @'
            positions: 0,
            position_minimums: [2; 15],
            sort_col: SortColumn::Pa,
'@ @'
            positions: 0,
            position_minimums: [2; 15],
            gender_mask: 0b11,
            quick_mode: 0,
            best_position: -1,
            role: 0,
            role_min: 0,
            attribute_filter: 0,
            attribute_min: 12,
            sort_col: SortColumn::Pa,
'@ 'state defaults'

$text = Replace-Required $text @'
    pub fn clear_filters(&mut self) {
        self.query.clear();
        self.clear_advanced();
    }
'@ @'
    pub fn clear_filters(&mut self) {
        self.query.clear();
        self.clear_advanced();
        self.gender_mask = 0b11;
        self.quick_mode = 0;
        self.best_position = -1;
        self.role = 0;
        self.role_min = 0;
        self.attribute_filter = 0;
        self.attribute_min = 12;
    }
'@ 'clear filters'

$filterMarker = '/// Filter the full player slice down to matching entries.'
if (-not $text.Contains($filterMarker)) { throw 'v4.2a: filter marker missing' }
$helpers = @'
const ELEMENT_SCOUT_ATTRIBUTES: &[(&str, &str)] = &[
    ("", "Any Attribute"),
    ("finishing", "Finishing"), ("dribbling", "Dribbling"), ("first_touch", "First Touch"),
    ("passing", "Passing"), ("technique", "Technique"), ("crossing", "Crossing"),
    ("heading", "Heading"), ("tackling", "Tackling"), ("marking", "Marking"),
    ("anticipation", "Anticipation"), ("composure", "Composure"), ("concentration", "Concentration"),
    ("decisions", "Decisions"), ("flair", "Flair"), ("off_the_ball", "Off the Ball"),
    ("positioning", "Positioning"), ("vision", "Vision"), ("teamwork", "Teamwork"),
    ("work_rate", "Work Rate"), ("determination", "Determination"),
    ("acceleration", "Acceleration"), ("pace", "Pace"), ("stamina", "Stamina"),
    ("strength", "Strength"), ("agility", "Agility"), ("balance", "Balance"),
    ("jumping_reach", "Jumping Reach"), ("natural_fitness", "Natural Fitness"),
    ("handling", "Handling"), ("reflexes", "Reflexes"), ("one_on_ones", "One on Ones"),
    ("aerial_reach", "Aerial Reach"), ("command_of_area", "Command of Area"),
    ("consistency", "Consistency"), ("important_matches", "Important Matches"),
];

fn element_player_attr(schemas: &'static crate::fields::VersionedSchemas, p: &CachedPlayer, key: &str) -> u8 {
    schemas.offset_of(key)
        .and_then(|o| p.raw.get(o).copied())
        .filter(|v| (1..=20).contains(v))
        .unwrap_or(1)
}

fn element_best_position(schemas: &'static crate::fields::VersionedSchemas, p: &CachedPlayer) -> Option<(usize, u8)> {
    let mut best: Option<(usize, u8)> = None;
    for (bit, &(key, _)) in POSITION_OFFSETS.iter().enumerate() {
        let value = schemas.offset_of(key).and_then(|o| p.raw.get(o).copied()).unwrap_or(0);
        if (1..=20).contains(&value) && best.map_or(true, |(_, old)| value > old) {
            best = Some((bit, value));
        }
    }
    best
}

fn element_role_name(role: u8) -> &'static str {
    match role {
        1 => "Poacher", 2 => "Advanced Forward", 3 => "Complete Forward", 4 => "Inside Forward",
        5 => "Winger", 6 => "Advanced Playmaker", 7 => "Deep-Lying Playmaker", 8 => "Box-to-Box",
        9 => "Ball-Playing Defender", 10 => "Central Defender", 11 => "Wing-Back",
        12 => "Sweeper Keeper", 13 => "Pressing Forward", _ => "Any Role",
    }
}

fn element_role_fit(schemas: &'static crate::fields::VersionedSchemas, p: &CachedPlayer, role: u8) -> u8 {
    let (pos, weights): (&[usize], &[(&str, u16)]) = match role {
        1 => (&[12], &[("finishing",3),("off_the_ball",3),("anticipation",2),("composure",2),("acceleration",2),("pace",2),("first_touch",1)]),
        2 => (&[12], &[("finishing",3),("off_the_ball",3),("acceleration",2),("pace",2),("dribbling",2),("first_touch",2),("technique",2),("composure",2)]),
        3 => (&[12], &[("finishing",3),("first_touch",3),("technique",2),("passing",2),("heading",2),("strength",2),("off_the_ball",2),("composure",2)]),
        4 => (&[9,11], &[("dribbling",3),("finishing",3),("off_the_ball",2),("acceleration",2),("pace",2),("technique",2),("flair",1)]),
        5 => (&[6,8,9,11], &[("crossing",3),("dribbling",3),("acceleration",2),("pace",2),("technique",2),("off_the_ball",2)]),
        6 => (&[7,10], &[("passing",3),("vision",3),("technique",2),("first_touch",2),("decisions",2),("composure",2),("flair",2)]),
        7 => (&[5,7], &[("passing",3),("vision",3),("decisions",3),("composure",2),("positioning",2),("teamwork",2),("first_touch",2)]),
        8 => (&[7], &[("stamina",3),("work_rate",3),("teamwork",2),("passing",2),("off_the_ball",2),("tackling",2),("decisions",2)]),
        9 => (&[3], &[("passing",3),("composure",3),("technique",2),("decisions",2),("positioning",2),("marking",2),("tackling",2),("anticipation",2)]),
        10 => (&[3], &[("marking",3),("tackling",3),("heading",3),("positioning",3),("concentration",2),("strength",2),("jumping_reach",2)]),
        11 => (&[2,4,13,14], &[("crossing",3),("stamina",3),("work_rate",2),("pace",2),("acceleration",2),("tackling",2),("dribbling",2)]),
        12 => (&[0], &[("reflexes",3),("one_on_ones",3),("aerial_reach",2),("handling",2),("rushing_out",2),("kicking",2),("passing",2),("composure",2)]),
        13 => (&[12], &[("work_rate",3),("stamina",3),("off_the_ball",3),("acceleration",2),("pace",2),("finishing",2),("teamwork",2)]),
        _ => return 0,
    };
    let mut total = 0u32;
    let mut max = 0u32;
    for &(key, weight) in weights {
        total += element_player_attr(schemas, p, key) as u32 * weight as u32;
        max += 20 * weight as u32;
    }
    if max == 0 { return 0; }
    let attr = total as f32 * 100.0 / max as f32;
    let fam = pos.iter().filter_map(|&bit| {
        let key = POSITION_OFFSETS.get(bit)?.0;
        schemas.offset_of(key).and_then(|o| p.raw.get(o).copied())
    }).max().unwrap_or(1).clamp(1,20) as f32;
    (attr * (0.70 + 0.30 * fam / 20.0)).round().clamp(0.0,100.0) as u8
}

fn element_deal_score(schemas: &'static crate::fields::VersionedSchemas, p: &CachedPlayer) -> u8 {
    let age = player_age(schemas, p).unwrap_or(30);
    let mut score = p.ca as f32 * 0.30 + p.pa as f32 * 0.20;
    score += match age { 0..=20 => 10.0, 21..=23 => 8.0, 24..=27 => 4.0, 28..=30 => 1.0, 31..=32 => -2.0, _ => -6.0 };
    score += match p.value {
        None if p.club_id.is_none() => 15.0,
        Some(0..=5_000_000) => 13.0,
        Some(5_000_001..=15_000_000) => 9.0,
        Some(15_000_001..=30_000_000) => 5.0,
        Some(30_000_001..=60_000_000) => 1.0,
        Some(100_000_001..) => -6.0,
        _ => 0.0,
    };
    if let Some((_, year)) = p.contract_expiry {
        if year <= schemas.age_reference_year { score += 9.0; }
        else if year == schemas.age_reference_year.saturating_add(1) { score += 4.0; }
    }
    if p.wage.is_some_and(|w| w >= 300_000) { score -= 5.0; }
    score.round().clamp(0.0,100.0) as u8
}

fn element_deal_label(score: u8) -> (&'static str, egui::Color32) {
    match score {
        90..=100 => ("MUST BUY", egui::Color32::from_rgb(72,210,132)),
        82..=89 => ("ELITE VALUE", egui::Color32::from_rgb(112,177,255)),
        74..=81 => ("GOOD DEAL", egui::Color32::from_rgb(121,205,148)),
        66..=73 => ("WATCHLIST", egui::Color32::from_rgb(216,181,99)),
        _ => ("FAIR", egui::Color32::from_rgb(135,145,165)),
    }
}

fn element_money(value: Option<u64>) -> String {
    match value {
        Some(v) if v >= 1_000_000_000 => format!("£{:.2}B", v as f64 / 1_000_000_000.0),
        Some(v) if v >= 1_000_000 => format!("£{:.1}M", v as f64 / 1_000_000.0),
        Some(v) if v >= 1_000 => format!("£{:.0}K", v as f64 / 1_000.0),
        Some(v) => format!("£{v}"), None => "—".into(),
    }
}

pub fn intelligence_row(ui: &mut egui::Ui, state: &mut PlayerSearchState) {
    egui::Frame::group(ui.style())
        .fill(egui::Color32::from_rgb(19,24,35))
        .stroke(egui::Stroke::new(1.0, egui::Color32::from_rgb(42,50,68)))
        .rounding(egui::Rounding::same(4))
        .inner_margin(egui::Margin::symmetric(7,5))
        .show(ui, |ui| {
            ui.horizontal_wrapped(|ui| {
                ui.label(egui::RichText::new("PLAYER INTELLIGENCE").size(9.0).strong().color(egui::Color32::from_rgb(112,177,255)));
                ui.label(egui::RichText::new("v4.2 • SCOUTING HUB").size(7.5).strong().color(egui::Color32::from_rgb(72,210,132)));
                ui.separator();
                let mut men = state.gender_mask & 1 != 0;
                let mut women = state.gender_mask & 2 != 0;
                if ui.checkbox(&mut men, "♂ MEN").changed() { if men { state.gender_mask |= 1 } else { state.gender_mask &= !1 } }
                if ui.checkbox(&mut women, "♀ WOMEN").changed() { if women { state.gender_mask |= 2 } else { state.gender_mask &= !2 } }
                ui.separator();
                for (mode,label) in [(0,"ALL"),(1,"U21"),(2,"U23"),(3,"PRIME"),(4,"TRANSFER LISTED"),(5,"LOAN LISTED"),(6,"FREE AGENTS"),(7,"EXPIRING"),(8,"NEXT SEASON"),(9,"CHEAP DEALS"),(10,"GOOD DEALS"),(11,"MUST BUY"),(12,"ELITE PROSPECTS")] {
                    if ui.selectable_label(state.quick_mode == mode, label).clicked() { state.quick_mode = mode; }
                }
                ui.add_enabled(false, egui::Button::new("≤6M"))
                    .on_disabled_hover_text("Exact 6-month pre-contract filtering stays gated until the live save date + competition eligibility rules are mapped in this pinned build.");
                ui.add_enabled(false, egui::Button::new("≤12M"))
                    .on_disabled_hover_text("Exact 12-month filtering needs the live save date in the cache; season-horizon filters are safe today.");
            });
            ui.horizontal_wrapped(|ui| {
                ui.label(egui::RichText::new("BEST POSITION").size(7.5).strong());
                egui::ComboBox::from_id_salt("element_v42_best_position")
                    .selected_text(if state.best_position < 0 { "Any" } else { POSITION_OFFSETS[state.best_position as usize].1 })
                    .width(70.0)
                    .show_ui(ui, |ui| {
                        ui.selectable_value(&mut state.best_position, -1, "Any");
                        for (bit,&(_,label)) in POSITION_OFFSETS.iter().enumerate() { ui.selectable_value(&mut state.best_position, bit as i8, label); }
                    });
                ui.separator();
                ui.label(egui::RichText::new("ROLE FIT").size(7.5).strong());
                egui::ComboBox::from_id_salt("element_v42_role")
                    .selected_text(element_role_name(state.role)).width(155.0)
                    .show_ui(ui, |ui| { for role in 0..=13u8 { ui.selectable_value(&mut state.role, role, element_role_name(role)); } });
                if state.role > 0 {
                    ui.label("≥"); ui.add(egui::DragValue::new(&mut state.role_min).range(0..=100));
                    if ui.small_button("SORT FIT").clicked() { state.sort_col = SortColumn::RoleFit; state.sort_dir = SortDir::Desc; }
                }
                ui.separator();
                ui.label(egui::RichText::new("ATTRIBUTE").size(7.5).strong());
                egui::ComboBox::from_id_salt("element_v42_attribute")
                    .selected_text(ELEMENT_SCOUT_ATTRIBUTES.get(state.attribute_filter as usize).map(|x| x.1).unwrap_or("Any Attribute"))
                    .width(135.0)
                    .show_ui(ui, |ui| { for (idx,&(_,label)) in ELEMENT_SCOUT_ATTRIBUTES.iter().enumerate() { ui.selectable_value(&mut state.attribute_filter, idx as u8, label); } });
                if state.attribute_filter > 0 { ui.label("≥"); ui.add(egui::DragValue::new(&mut state.attribute_min).range(1..=20)); }
                ui.separator();
                if ui.small_button("RESET INTELLIGENCE").clicked() {
                    state.gender_mask=0b11; state.quick_mode=0; state.best_position=-1; state.role=0; state.role_min=0; state.attribute_filter=0; state.attribute_min=12;
                }
            });
            ui.label(egui::RichText::new("Element Deal Score / Role Fit are transparent heuristics, not native FM ratings. Gender is verified through current-club membership; free-agent gender is never guessed.").size(7.2).color(egui::Color32::from_rgb(132,146,170)));
        });
}

'@
$text = $text.Replace($filterMarker, $helpers + $filterMarker)

$text = Replace-Required $text @'
        .filter(|p| {
            if let Some(m) = ca_min {
'@ @'
        .filter(|p| {
            if state.gender_mask != 0b11 {
                let allowed = match p.gender { Some(0) => state.gender_mask & 1 != 0, Some(1) => state.gender_mask & 2 != 0, _ => false };
                if !allowed { return false; }
            }
            let age_now = player_age(schemas, p);
            let deal = if (9..=12).contains(&state.quick_mode) { element_deal_score(schemas, p) } else { 0 };
            let quick_ok = match state.quick_mode {
                1 => age_now.is_some_and(|a| a <= 21),
                2 => age_now.is_some_and(|a| a <= 23),
                3 => age_now.is_some_and(|a| (24..=29).contains(&a)),
                4 => p.list_flags.is_some_and(|f| f & 0x01 != 0),
                5 => p.list_flags.is_some_and(|f| f & 0x02 != 0),
                6 => p.club_id.is_none(),
                7 => p.contract_expiry.is_some_and(|(_,y)| y <= schemas.age_reference_year),
                8 => p.contract_expiry.is_some_and(|(_,y)| y == schemas.age_reference_year.saturating_add(1)),
                9 => deal >= 70 && p.value.is_some_and(|v| v <= 20_000_000),
                10 => deal >= 74,
                11 => deal >= 90,
                12 => age_now.is_some_and(|a| a <= 23) && p.pa >= 170,
                _ => true,
            };
            if !quick_ok { return false; }
            if state.best_position >= 0 {
                let selected = state.best_position as usize;
                let Some((_, best_value)) = element_best_position(schemas, p) else { return false; };
                let selected_value = schemas.offset_of(POSITION_OFFSETS[selected].0).and_then(|o| p.raw.get(o).copied()).unwrap_or(0);
                if selected_value == 0 || selected_value < best_value { return false; }
            }
            if state.role > 0 && state.role_min > 0 && element_role_fit(schemas, p, state.role) < state.role_min { return false; }
            if state.attribute_filter > 0 {
                let key = ELEMENT_SCOUT_ATTRIBUTES.get(state.attribute_filter as usize).map(|x| x.0).unwrap_or("");
                if key.is_empty() || element_player_attr(schemas, p, key) < state.attribute_min { return false; }
            }
            if let Some(m) = ca_min {
'@ 'intelligence predicates'

# Replace result grid with the intelligence table. Keep same public signature.
$start = $text.IndexOf('pub fn results_grid(')
$end = $text.IndexOf('fn compare_players(', $start)
if ($start -lt 0 -or $end -lt 0) { throw 'v4.2a: results grid boundaries missing' }
$grid = @'
pub fn results_grid(
    schemas: &'static crate::fields::VersionedSchemas,
    ui: &mut egui::Ui,
    state: &mut PlayerSearchState,
    results: &[&CachedPlayer],
) -> Option<usize> {
    if results.is_empty() { ui.label("No results. Adjust Player Intelligence / Advanced filters."); return None; }
    let mut clicked = None;
    let mut order: Vec<usize> = (0..results.len()).collect();
    order.sort_by(|&a,&b| compare_players(schemas, results[a], results[b], state.sort_col, state.sort_dir, state.role));
    const H:f32=22.0;

    egui::ScrollArea::horizontal().id_salt("element_v42_players_h").show(ui, |ui| {
        ui.set_min_width(1110.0);
        let mut clicked_sort: Option<SortColumn> = None;
        let col = |ui:&mut egui::Ui, label:&str, width:f32| { ui.add_sized([width,H], egui::Label::new(egui::RichText::new(label).small().strong())); };
        ui.horizontal(|ui| {
            if ui.add_sized([190.0,H],egui::Button::new("PLAYER").frame(false)).clicked(){clicked_sort=Some(SortColumn::Name)}
            if ui.add_sized([42.0,H],egui::Button::new("AGE").frame(false)).clicked(){clicked_sort=Some(SortColumn::Age)}
            col(ui,"SEX",46.0); col(ui,"BEST",54.0);
            if ui.add_sized([40.0,H],egui::Button::new("CA").frame(false)).clicked(){clicked_sort=Some(SortColumn::Ca)}
            if ui.add_sized([40.0,H],egui::Button::new("PA").frame(false)).clicked(){clicked_sort=Some(SortColumn::Pa)}
            if ui.add_sized([80.0,H],egui::Button::new("VALUE").frame(false)).clicked(){clicked_sort=Some(SortColumn::Value)}
            col(ui,"WAGE",82.0); col(ui,"EXPIRY",68.0);
            if ui.add_sized([112.0,H],egui::Button::new("ELEMENT DEAL").frame(false)).clicked(){clicked_sort=Some(SortColumn::Deal)}
            if ui.add_sized([92.0,H],egui::Button::new("ROLE FIT").frame(false)).clicked(){clicked_sort=Some(SortColumn::RoleFit)}
        });
        if let Some(sort) = clicked_sort {
            if state.sort_col == sort { state.sort_dir = if state.sort_dir==SortDir::Asc {SortDir::Desc}else{SortDir::Asc}; }
            else { state.sort_col=sort; state.sort_dir=SortDir::Desc; }
        }
        ui.separator();
        let selection_id=ui.make_persistent_id("player_selected");
        let mut selected:Option<u64>=ui.ctx().data_mut(|d|d.get_temp(selection_id));
        egui::ScrollArea::vertical().show_rows(ui,H,order.len(),|ui,range|{
            for visual in range {
                let orig=order[visual]; let p=results[orig];
                let age=player_age(schemas,p).map(|v|v.to_string()).unwrap_or_else(||"—".into());
                let gender=match p.gender{Some(0)=>"MEN",Some(1)=>"WOMEN",_=>"—"};
                let best=element_best_position(schemas,p).map(|(b,_)|POSITION_OFFSETS[b].1).unwrap_or("—");
                let wage=p.wage.map(|w|format!("£{}K/w",w/1000)).unwrap_or_else(||"—".into());
                let expiry=p.contract_expiry.map(|(_,y)|y.to_string()).unwrap_or_else(||"—".into());
                let deal=element_deal_score(schemas,p); let (deal_label,deal_color)=element_deal_label(deal);
                let role=if state.role>0{format!("{}%",element_role_fit(schemas,p,state.role))}else{"—".into()};
                let row=ui.horizontal(|ui|{
                    ui.add_sized([190.0,H],egui::Label::new(&*p.name).truncate());
                    ui.add_sized([42.0,H],egui::Label::new(age)); ui.add_sized([46.0,H],egui::Label::new(gender)); ui.add_sized([54.0,H],egui::Label::new(best));
                    ui.add_sized([40.0,H],egui::Label::new(egui::RichText::new(p.ca.to_string()).color(field_widget::ca_pa_color(p.ca))));
                    ui.add_sized([40.0,H],egui::Label::new(egui::RichText::new(p.pa.to_string()).color(field_widget::ca_pa_color(p.pa))));
                    ui.add_sized([80.0,H],egui::Label::new(element_money(p.value))); ui.add_sized([82.0,H],egui::Label::new(wage)); ui.add_sized([68.0,H],egui::Label::new(expiry));
                    ui.add_sized([112.0,H],egui::Label::new(egui::RichText::new(format!("{} {}",deal_label,deal)).color(deal_color)));
                    ui.add_sized([92.0,H],egui::Label::new(role));
                });
                let resp=ui.interact(row.response.rect,ui.make_persistent_id(("player_row_v42",p.addr)),egui::Sense::click());
                if resp.hovered()||selected==Some(p.addr){ui.painter().rect_filled(resp.rect,egui::CornerRadius::ZERO,if selected==Some(p.addr){ui.visuals().selection.bg_fill.gamma_multiply(0.5)}else{egui::Color32::from_rgba_unmultiplied(255,255,255,18)});}
                if resp.clicked(){selected=Some(p.addr);clicked=Some(orig);}
            }
        });
        if let Some(addr)=selected{ui.ctx().data_mut(|d|d.insert_temp(selection_id,addr));}
    });
    clicked
}

'@
$text = $text.Substring(0,$start) + $grid + $text.Substring($end)

# Comparator: extend the old signature with role and new columns.
$cmpStart=$text.IndexOf('fn compare_players(')
$cmpEnd=$text.IndexOf('#[cfg(test)]',$cmpStart)
if($cmpStart -lt 0 -or $cmpEnd -lt 0){throw 'v4.2a: comparator boundaries missing'}
$cmp=@'
fn compare_players(
    schemas: &'static crate::fields::VersionedSchemas,
    a: &CachedPlayer,
    b: &CachedPlayer,
    col: SortColumn,
    dir: SortDir,
    role: u8,
) -> std::cmp::Ordering {
    if col == SortColumn::Age {
        match (player_age(schemas,a).is_none(), player_age(schemas,b).is_none()) {
            (true,false)=>return std::cmp::Ordering::Greater,(false,true)=>return std::cmp::Ordering::Less,_=>{}
        }
    }
    let order=match col {
        SortColumn::Name=>a.name.cmp(&b.name), SortColumn::Uid=>a.uid.cmp(&b.uid), SortColumn::Ca=>a.ca.cmp(&b.ca), SortColumn::Pa=>a.pa.cmp(&b.pa),
        SortColumn::Age=>b.dob_year.cmp(&a.dob_year), SortColumn::Value=>a.value.cmp(&b.value),
        SortColumn::Deal=>element_deal_score(schemas,a).cmp(&element_deal_score(schemas,b)),
        SortColumn::RoleFit=>element_role_fit(schemas,a,role).cmp(&element_role_fit(schemas,b,role)),
    };
    let order=if dir==SortDir::Desc{order.reverse()}else{order}; order.then_with(||a.addr.cmp(&b.addr))
}

'@
$text=$text.Substring(0,$cmpStart)+$cmp+$text.Substring($cmpEnd)
Write-Text $path $text

# v2.0 deliberately removed the local player filter row. Put Player Intelligence
# directly beneath the global search area only on the Players page.
$appPath='src/app.rs'
$app=Read-Text $appPath
$app=Replace-Required $app @'
                    // v2.0: name/UID search lives exclusively in the global top bar.
                    // Entity-specific advanced state is preserved internally; Players
                    // expose it through the compact gear button beside Global Search.
                    ui.add_space(1.0);
'@ @'
                    // v2.0 global search + v4.2 Player Intelligence quick filters.
                    if self.active_page == Page::PlayerSearch {
                        pages::player_search::intelligence_row(ui, &mut self.player_search);
                        ui.add_space(3.0);
                    } else {
                        ui.add_space(1.0);
                    }
'@ 'app player intelligence row'
Write-Text $appPath $app

Write-Host 'Element v4.2a Player Intelligence / Scouting Hub applied successfully.'
