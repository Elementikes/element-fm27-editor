from pathlib import Path

root=Path.cwd()

def rd(path):
    p=root/path
    if not p.exists(): raise SystemExit(f"v8.0 missing {path}")
    return p.read_text(encoding="utf-8")

def wr(path,text): (root/path).write_text(text,encoding="utf-8")

def one(text,old,new,label):
    if old not in text: raise SystemExit(f"v8.0 marker missing: {label}")
    return text.replace(old,new,1)

# -----------------------------------------------------------------------------
# Bridge: read-only tactical summary for FMRTE-style bars.
# -----------------------------------------------------------------------------
p="src/bridge/cmd.rs"
t=rd(p)
if "pub struct TacticalKnowledgeSummary" not in t:
    marker="#[derive(Clone, Debug)]\npub struct TacticalMaxPlannedEdit"
    idx=t.find(marker)
    if idx<0: raise SystemExit("v8.0 tactical struct marker missing")
    defs='''#[derive(Clone, Debug, Default)]
pub struct TacticalKnowledgeSummary {
    pub club_addr: u64,
    pub senior_team_addr: u64,
    pub players_matched: usize,
    pub groups: [u16; 6],
    pub formation_role: u16,
}

'''
    t=t[:idx]+defs+t[idx:]
if "ReadSelectedClubTacticalSummary" not in t:
    t=one(t,
        "    PlanSelectedClubTacticalMax { club_addr: u64, senior_team_addr: u64, player_addrs: Vec<u64> },\n",
        "    ReadSelectedClubTacticalSummary { club_addr: u64, senior_team_addr: u64, player_addrs: Vec<u64> },\n    PlanSelectedClubTacticalMax { club_addr: u64, senior_team_addr: u64, player_addrs: Vec<u64> },\n",
        "tactical summary command")
if "TacticalKnowledgeSummaryReady" not in t:
    t=one(t,
        "    TacticalMaxPlanReady { club_addr: u64, plan: TacticalMaxPlan },\n",
        "    TacticalKnowledgeSummaryReady { club_addr: u64, summary: TacticalKnowledgeSummary },\n    TacticalMaxPlanReady { club_addr: u64, plan: TacticalMaxPlan },\n",
        "tactical summary result")
wr(p,t)

p="src/bridge/mod.rs"
t=rd(p)
if "TacticalKnowledgeSummary" not in t:
    t=one(t,
        "    TacticalMaxPlan, TacticalMaxPlannedEdit, TeamCohesionDeltaReport,\n",
        "    TacticalMaxPlan, TacticalMaxPlannedEdit, TacticalKnowledgeSummary, TeamCohesionDeltaReport,\n",
        "tactical summary export")
wr(p,t)

p="src/bridge/tactical_max_plan.rs"
t=rd(p)
if "pub(super) fn read_first_team_summary" not in t:
    t += r'''

pub(super) fn read_first_team_summary(
    fm: &FmProcess,
    club_addr: u64,
    senior_team_addr: u64,
    player_addrs: &[u64],
) -> Result<super::cmd::TacticalKnowledgeSummary, String> {
    if fm.build != crate::game_version::GameBuild::Fm27Steam {
        return Err("Tactical Knowledge read is certified only for FM27 Steam".into());
    }
    if !is_valid_ptr(club_addr) || !is_valid_ptr(senior_team_addr) {
        return Err("selected Club/SeniorTeam pointer is invalid; reload club".into());
    }
    let mut sums=[0u64;CATEGORIES];
    let mut counts=[0u64;CATEGORIES];
    let mut form_sum=0u64;
    let mut form_count=0u64;
    let mut matched=0usize;
    for &player in player_addrs {
        if !is_valid_ptr(player) {continue;}
        if u64_at(fm,player+PLAYER_TEAM_PTR)?!=senior_team_addr {continue;}
        let block=u64_at(fm,player+PLAYER_TACTICAL_PTR)?;
        if !is_valid_ptr(block) {continue;}
        matched+=1;
        for category in 0..CATEGORIES {
            let (data,count)=vec_info(fm,block+category as u64*CATEGORY_STRIDE,4,4096)?;
            for i in 0..count {
                let b=fm.read_bytes(data+i as u64*4,4)?;
                let raw=u32::from_le_bytes(b.as_slice().try_into().unwrap());
                let knowledge=(raw&KNOWLEDGE_MASK).min(MAX_KNOWLEDGE) as u64;
                sums[category]+=knowledge; counts[category]+=1;
            }
        }
        let (data,count)=vec_info(fm,block+FORMATION_VECTOR,FORMATION_ROW,1024)?;
        for i in 0..count {
            let b=fm.read_bytes(data+i as u64*FORMATION_ROW as u64+FORMATION_VALUE,2)?;
            let raw=u16::from_le_bytes(b.as_slice().try_into().unwrap()).min(MAX_KNOWLEDGE as u16) as u64;
            form_sum+=raw; form_count+=1;
        }
    }
    if matched==0 {return Err("no cached player currently belongs to this SeniorTeam; reload save/club".into());}
    let mut groups=[0u16;6];
    for i in 0..CATEGORIES { if counts[i]>0 {groups[i]=(sums[i]/counts[i]).min(10_000) as u16;} }
    Ok(super::cmd::TacticalKnowledgeSummary{
        club_addr,senior_team_addr,players_matched:matched,groups,
        formation_role:if form_count>0{(form_sum/form_count).min(10_000) as u16}else{0},
    })
}
'''
wr(p,t)

p="src/bridge/worker.rs"
t=rd(p)
if "BridgeCmd::ReadSelectedClubTacticalSummary" not in t:
    marker="            BridgeCmd::PlanSelectedClubTacticalMax { club_addr, senior_team_addr, player_addrs } => {\n"
    idx=t.find(marker)
    if idx<0: raise SystemExit("v8.0 worker tactical marker missing")
    arm='''            BridgeCmd::ReadSelectedClubTacticalSummary { club_addr, senior_team_addr, player_addrs } => {
                let result=match &fm {
                    Some(f)=>tactical_max_plan::read_first_team_summary(f,club_addr,senior_team_addr,&player_addrs),
                    None=>Err("Cannot read Tactical Understanding: no process attached".into()),
                };
                match result {
                    Ok(summary)=>{let _=tx.send(BridgeResult::TacticalKnowledgeSummaryReady{club_addr,summary});}
                    Err(error)=>{let _=tx.send(BridgeResult::Error(format!("Tactical Understanding read: {error}")));}
                }
            }

'''
    t=t[:idx]+arm+t[idx:]
wr(p,t)

# -----------------------------------------------------------------------------
# Club UI: FMRTE-style header cards, live tactical bars, First Team roster filter.
# -----------------------------------------------------------------------------
p="src/ui/club_panel.rs"
t=rd(p)
if "ELEMENT_CLUB_HEADER_CARDS_V80" not in t:
    marker='''    entity_header::show(
        ui,
        &club.full_name,
        "Club",
'''
    idx=t.find(marker)
    if idx<0: raise SystemExit("v8.0 club header marker missing")
    end=t.find("    );",idx)
    if end<0: raise SystemExit("v8.0 club header end missing")
    end+=len("    );")
    cards=r'''
    // ELEMENT_CLUB_HEADER_CARDS_V80
    ui.horizontal_wrapped(|ui| {
        let tile=|ui:&mut egui::Ui,label:&str,value:String|{
            egui::Frame::group(ui.style()).inner_margin(egui::Margin::symmetric(10,5)).show(ui,|ui|{
                ui.horizontal(|ui|{ui.label(egui::RichText::new(label).size(8.0).strong().weak());ui.label(egui::RichText::new(value).size(14.0).strong());});
            });
        };
        let rep=schemas.field("c_reputation").and_then(|f|fields::read_field_u16(club,&club.raw,f));
        let bal=schemas.field("c_balance").and_then(|f|fields::read_field_u32(club,&club.raw,f));
        let budget=schemas.field("c_transfer_budget").and_then(|f|fields::read_field_u32(club,&club.raw,f));
        tile(ui,"REPUTATION",rep.map(|v|v.to_string()).unwrap_or_else(||"—".into()));
        tile(ui,"BALANCE",bal.map(|v|format!("£{:.1}m",v as f64/1_000_000.0)).unwrap_or_else(||"—".into()));
        tile(ui,"TRANSFER",budget.map(|v|format!("£{:.1}m",v as f64/1_000_000.0)).unwrap_or_else(||"—".into()));
    });
    ui.add_space(4.0);
'''
    t=t[:end]+cards+t[end:]

# Replace Tactical function wholesale, preserving all underlying commands and guarded write behavior.
start=t.find("fn show_tactical(\n")
end=t.find("fn show_overview(\n",start)
if start<0 or end<0: raise SystemExit("v8.0 tactical function bounds missing")
new_tactical=r'''fn tactical_bar(ui:&mut egui::Ui,label:&str,value:u16,note:&str){
    ui.horizontal(|ui|{
        ui.set_min_width(620.0);
        ui.label(egui::RichText::new(label).strong()).on_hover_text(note);
        let pct=(value as f32/10_000.0).clamp(0.0,1.0);
        ui.add(egui::ProgressBar::new(pct).desired_width(360.0).text(format!("{:.0}%",value as f32/100.0)));
        ui.label(egui::RichText::new(if value>=9500{"ELITE"}else if value>=8000{"EXCELLENT"}else if value>=6000{"GOOD"}else if value>=3500{"DEVELOPING"}else{"POOR"}).small().strong());
    });
}

fn show_tactical(
    ui: &mut egui::Ui,
    club: &mut ClubView,
    edits: &mut Vec<FieldEdit>,
    writable: bool,
    entity_cache: Option<&crate::cache::EntityCache>,
) {
    ui.horizontal_wrapped(|ui| {
        ui.heading("Tactical Understanding");
        ui.label(egui::RichText::new("ELEMENT v8.0 • LIVE FM27 FAMILIARITY").strong().color(egui::Color32::from_rgb(96,178,255)));
    });
    ui.label(egui::RichText::new("FMRTE-inspired presentation over Element's independently mapped FM27 tactical blocks. Team Cohesion remains differential-only until its scalar is certified.").weak());
    ui.add_space(7.0);

    let player_addrs:Vec<u64>=entity_cache.map(|cache|cache.players.iter().filter(|p|p.club_id==Some(club.uid)).map(|p|p.addr).collect()).unwrap_or_default();
    let team=club.senior_team_addr;
    let can_read=team.is_some()&&!player_addrs.is_empty();
    let summary_id=egui::Id::new(("element_v80_tactical_summary",club.addr));
    let requested_id=egui::Id::new(("element_v80_tactical_summary_requested",club.addr));
    let summary=ui.ctx().data(|d|d.get_temp::<crate::bridge::TacticalKnowledgeSummary>(summary_id));
    let requested=ui.ctx().data(|d|d.get_temp::<bool>(requested_id).unwrap_or(false));
    if summary.is_none()&&can_read&&!requested {
        ui.ctx().data_mut(|d|{
            d.insert_temp(requested_id,true);
            d.insert_temp(egui::Id::new("element_v80_read_tactical_summary_request"),(club.addr,team.unwrap(),player_addrs.clone()));
        });
    }

    ui.horizontal_wrapped(|ui|{
        ui.selectable_label(true,"FIRST TEAM");
        ui.add_enabled(false,egui::Button::new("B / RESERVES 🔒")).on_disabled_hover_text("Team-kind mapping is not yet certified.");
        ui.add_enabled(false,egui::Button::new("U19 / YOUTH 🔒")).on_disabled_hover_text("Team-kind mapping is not yet certified.");
        if ui.add_enabled(can_read,egui::Button::new("↻ REFRESH")).clicked(){
            ui.ctx().data_mut(|d|{
                d.insert_temp(requested_id,true);
                d.insert_temp(egui::Id::new("element_v80_read_tactical_summary_request"),(club.addr,team.unwrap(),player_addrs.clone()));
            });
        }
    });
    ui.add_space(6.0);

    egui::Frame::group(ui.style()).inner_margin(10.0).show(ui,|ui|{
        if let Some(s)=summary {
            ui.label(egui::RichText::new(format!("{} First Team player(s) sampled",s.players_matched)).small().weak());
            tactical_bar(ui,"Passing Style",s.groups[0],"FM27 familiarity group 1; game UI can derive presentation from tactical context.");
            tactical_bar(ui,"Build Up",s.groups[1],"FM27 familiarity group 2; game UI can derive presentation from tactical context.");
            tactical_bar(ui,"Chance Creation",s.groups[2],"Verified lower-14-bit tactical knowledge values, averaged across First Team.");
            tactical_bar(ui,"Line of Engagement",s.groups[3],"Verified lower-14-bit tactical knowledge values, averaged across First Team.");
            tactical_bar(ui,"Pressing Intensity",s.groups[4],"Verified lower-14-bit tactical knowledge values, averaged across First Team.");
            tactical_bar(ui,"Pressing Trap",s.groups[5],"Verified lower-14-bit tactical knowledge values, averaged across First Team.");
            tactical_bar(ui,"Position / Role",s.formation_role,"Formation/role familiarity rows at the verified FM27 tactical block.");
        } else {
            ui.horizontal(|ui|{ui.spinner();ui.label("Reading First Team tactical familiarity…");});
        }
    });

    ui.add_space(8.0);
    let can_plan=writable&&can_read;
    if ui.add_enabled(can_plan,egui::Button::new("⚡ MAX TACTICAL FAMILIARITY • FIRST TEAM"))
        .on_hover_text("Verified FM27 writer. Every candidate is checked against this club's live SeniorTeam pointer and enters Change History / Undo.").clicked()
    {
        ui.ctx().data_mut(|d|d.insert_temp(egui::Id::new("element_v7_plan_tactical_max_request"),(club.addr,team.unwrap(),player_addrs.clone())));
    }
    let plan_id=egui::Id::new(("element_v7_tactical_max_plan",club.addr));
    if let Some(plan)=ui.ctx().data_mut(|d|{let p=d.get_temp::<crate::bridge::TacticalMaxPlan>(plan_id);d.remove::<crate::bridge::TacticalMaxPlan>(plan_id);p}){
        ui.colored_label(egui::Color32::from_rgb(88,214,141),format!("Prepared {} guarded edits for {} First Team players.",plan.edits.len(),plan.players_matched));
        for e in plan.edits{edits.push(FieldEdit{addr:e.addr,old_raw:e.old_raw,new_raw:e.new_raw,description:e.description,presentation:None});}
        ui.ctx().data_mut(|d|d.remove::<crate::bridge::TacticalKnowledgeSummary>(summary_id));
    }

    ui.add_space(12.0);ui.separator();
    ui.horizontal_wrapped(|ui|{ui.strong("Team Cohesion");ui.label(egui::RichText::new("MAPPING • READ-ONLY DIFFERENTIAL").small().weak());});
    ui.label("Capture → run only Improve Team Cohesion in FMRTE → Compare. Reputation +0xA8 is excluded from candidate ranking.");
    if let Some(team)=team {
        ui.horizontal_wrapped(|ui|{
            if ui.add_enabled(writable,egui::Button::new("1 • CAPTURE BASELINE")).clicked(){ui.ctx().data_mut(|d|d.insert_temp(egui::Id::new("element_v7_capture_cohesion_request"),(club.addr,team)));}
            if ui.add_enabled(writable,egui::Button::new("2 • COMPARE AFTER FMRTE")).clicked(){ui.ctx().data_mut(|d|d.insert_temp(egui::Id::new("element_v7_compare_cohesion_request"),(club.addr,team)));}
            ui.add_enabled(false,egui::Button::new("IMPROVE TEAM COHESION 🔒")).on_disabled_hover_text("Native ActionID is known, but direct target/payload + rollback are not yet certified.");
        });
    }
    if let Some((team_addr,bytes))=ui.ctx().data(|d|d.get_temp::<(u64,usize)>(egui::Id::new(("element_v7_cohesion_baseline_ready",club.addr)))){
        ui.label(format!("Baseline ready • SeniorTeam 0x{team_addr:X} • {bytes} bytes"));
    }
    if let Some(report)=ui.ctx().data(|d|d.get_temp::<crate::bridge::TeamCohesionDeltaReport>(egui::Id::new(("element_v7_cohesion_report",club.addr)))){
        ui.colored_label(egui::Color32::from_rgb(255,193,92),format!("{} byte(s) changed",report.changed_bytes));
        egui::ScrollArea::vertical().max_height(220.0).show(ui,|ui|{for row in &report.rows{ui.monospace(row);}});
    }
}

'''
t=t[:start]+new_tactical+t[end:]

# First Team becomes a real roster filter using the same verified +0x130 team pointer.
if "fn squad_live_team_ptr(" not in t:
    marker="fn squad_primary_position(\n"
    idx=t.find(marker)
    if idx<0: raise SystemExit("v8.0 squad helper marker missing")
    helper='''fn squad_live_team_ptr(p:&crate::cache::CachedPlayer)->Option<u64>{
    let b=p.raw.get(0x130..0x138)?;
    Some(u64::from_le_bytes(b.try_into().ok()?))
}

'''
    t=t[:idx]+helper+t[idx:]

old_nav='''    ui.horizontal_wrapped(|ui| {
        ui.selectable_label(true, "ALL CLUB");
        ui.add_enabled(false, egui::Button::new("FIRST TEAM 🔒")).on_disabled_hover_text("Team-type membership filtering is visible but stays locked until the team-kind chain is certified on this FM27 build.");
        ui.add_enabled(false, egui::Button::new("B / RESERVES 🔒")).on_disabled_hover_text("Visible for FMRTE parity; no fake membership filtering is used.");
        ui.add_enabled(false, egui::Button::new("U19 / YOUTH 🔒")).on_disabled_hover_text("Visible for FMRTE parity; no fake membership filtering is used.");
    });
    ui.add_space(5.0);
'''
new_nav='''    let squad_view_id=egui::Id::new(("element_v80_squad_view",club.addr));
    let mut squad_view=ui.ctx().data_mut(|d|d.get_temp::<String>(squad_view_id).unwrap_or_else(||"ALL".into()));
    ui.horizontal_wrapped(|ui| {
        if ui.selectable_label(squad_view=="ALL", "ALL CLUB").clicked(){squad_view="ALL".into();ui.ctx().data_mut(|d|d.insert_temp(squad_view_id,squad_view.clone()));}
        if ui.add_enabled(club.senior_team_addr.is_some(),egui::Button::new("FIRST TEAM").selected(squad_view=="FIRST")).clicked(){squad_view="FIRST".into();ui.ctx().data_mut(|d|d.insert_temp(squad_view_id,squad_view.clone()));}
        ui.add_enabled(false, egui::Button::new("B / RESERVES 🔒")).on_disabled_hover_text("Reserve-team kind/address discovery is not yet certified.");
        ui.add_enabled(false, egui::Button::new("U19 / YOUTH 🔒")).on_disabled_hover_text("Youth-team kind/address discovery is not yet certified.");
    });
    ui.add_space(5.0);
'''
if old_nav in t:t=t.replace(old_nav,new_nav,1)
else: raise SystemExit("v8.0 squad nav marker missing")
old_rows='''    let mut rows:Vec<&crate::cache::CachedPlayer>=cache.players.iter()
        .filter(|p|p.club_id==Some(club.uid))
        .filter(|p|q.is_empty()||p.name.to_lowercase().contains(&q))
        .collect();
'''
new_rows='''    let mut rows:Vec<&crate::cache::CachedPlayer>=cache.players.iter()
        .filter(|p|p.club_id==Some(club.uid))
        .filter(|p|squad_view!="FIRST"||club.senior_team_addr.is_some_and(|team|squad_live_team_ptr(p)==Some(team)))
        .filter(|p|q.is_empty()||p.name.to_lowercase().contains(&q))
        .collect();
'''
t=one(t,old_rows,new_rows,"squad First Team filter")
wr(p,t)

# -----------------------------------------------------------------------------
# App: tactical summary result/request + correct Club Power destination.
# -----------------------------------------------------------------------------
p="src/app.rs"
t=rd(p)
if "BridgeResult::TacticalKnowledgeSummaryReady" not in t:
    marker="                BridgeResult::TacticalMaxPlanReady { club_addr, plan } => {\n"
    arm='''                BridgeResult::TacticalKnowledgeSummaryReady { club_addr, summary } => {
                    let players=summary.players_matched;
                    ctx.data_mut(|d|{
                        d.insert_temp(egui::Id::new(("element_v80_tactical_summary",club_addr)),summary);
                        d.insert_temp(egui::Id::new(("element_v80_tactical_summary_requested",club_addr)),false);
                    });
                    self.set_status(format!("Tactical Understanding read • {players} First Team player(s)"));
                }
'''
    t=one(t,marker,arm+marker,"app tactical summary result")
if "element_v80_read_tactical_summary_request" not in t:
    marker="        if let Some((club_addr,senior_team_addr,player_addrs)) = ctx.data_mut(|d| {\n"
    idx=t.find(marker)
    if idx<0: raise SystemExit("v8.0 app tactical request marker missing")
    block=r'''        if let Some((club_addr,senior_team_addr,player_addrs))=ctx.data_mut(|d|{
            let id=egui::Id::new("element_v80_read_tactical_summary_request");
            let v=d.get_temp::<(u64,u64,Vec<u64>)>(id);d.remove::<(u64,u64,Vec<u64>)>(id);v
        }){
            if self.conn.is_ready(){self.bridge.send(BridgeCmd::ReadSelectedClubTacticalSummary{club_addr,senior_team_addr,player_addrs});}
        }
'''
    t=t[:idx]+block+t[idx:]
t=t.replace('cnav!("⚡  Club Power", club_panel::ClubTab::Overview);','cnav!("⚡  Club Power", club_panel::ClubTab::PowerTools);',1)
wr(p,t)

print("Element v8.0 FMRTE-style Club/Tactical surfaces applied.")
