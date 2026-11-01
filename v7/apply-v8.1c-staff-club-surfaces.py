from pathlib import Path

root=Path.cwd()

def rd(path):
    p=root/path
    if not p.exists(): raise SystemExit(f"v8.1 missing {path}")
    return p.read_text(encoding='utf-8')

def wr(path,text): (root/path).write_text(text,encoding='utf-8')

def one(text,old,new,label):
    if old not in text: raise SystemExit(f"v8.1 marker missing: {label}")
    return text.replace(old,new,1)

# -----------------------------------------------------------------------------
# Staff: every FMRTE-style sidebar item opens a real workspace. Mapped staff
# knowledge remains editable; training rating/languages/formations are live.
# -----------------------------------------------------------------------------
p='src/ui/staff_panel.rs'; t=rd(p)
if '    CareerPlans,\n' not in t:
    t=one(t,'    PowerTools,\n}','    PowerTools,\n    CareerPlans,\n    Promises,\n    SwapStaff,\n    TrainingRating,\n    Formations,\n    Relationships,\n    Knowledge,\n    Retirement,\n    Languages,\n}', 'staff tab expansion')
if 'StaffTab::CareerPlans =>' not in t:
    arm='''        StaffTab::PowerTools => show_staff_power_tools(schemas, ui, staff, &mut edits),\n'''
    repl=arm+'''        StaffTab::CareerPlans => show_staff_mapping_surface(ui,"Career Plans","FM27 Career Plans UI types are present; staff career-plan record chain is not mapped."),\n        StaffTab::Promises => show_staff_mapping_surface(ui,"Promises","PromiseReference exists in FM27 metadata; staff promise storage/semantics are not certified."),\n        StaffTab::SwapStaff => show_staff_mapping_surface(ui,"Swap Staff","Direct staff employment/roster transaction is not mapped. No contract/team pointer is guessed."),\n        StaffTab::TrainingRating => show_staff_training_rating(schemas,ui,staff),\n        StaffTab::Formations => show_staff_formations(schemas,ui,staff),\n        StaffTab::Relationships => show_staff_mapping_surface(ui,"Relationships","Staff/person relationship vector is not independently mapped on FM27 yet."),\n        StaffTab::Knowledge => categories(schemas,ui,staff,&[("Knowledge",Category::Knowledge)],&mut edits),\n        StaffTab::Retirement => show_staff_mapping_surface(ui,"Retire Date","RetiredPerson concepts are visible in FM27 metadata; storage and reversible write are not certified."),\n        StaffTab::Languages => show_staff_languages(ui,staff),\n'''
    t=one(t,arm,repl,'staff match arms')
if 'fn show_staff_training_rating(' not in t:
    marker='fn header(\n'; idx=t.find(marker)
    if idx<0: raise SystemExit('v8.1 staff helper marker missing')
    funcs=r'''fn staff_category_score_v81(schemas:&'static crate::fields::VersionedSchemas,staff:&StaffView,category:Category)->f32{
    let mut total=0.0;let mut n=0usize;for f in schemas.fields_for_category(Entity::Staff,category){if let Some(v)=crate::fields::read_field_u8(&staff.record,&staff.record.raw,f){if (1..=20).contains(&v){total+=v as f32;n+=1;}}}if n==0{0.0}else{total/n as f32}
}
fn show_staff_training_rating(schemas:&'static crate::fields::VersionedSchemas,ui:&mut egui::Ui,staff:&StaffView){
    ui.heading("Training Rating");ui.label(egui::RichText::new("Element derived from mapped coaching attributes").weak());
    for (label,cat) in [("Coaching",Category::Coaching),("Mental",Category::Mental),("Knowledge",Category::Knowledge),("Medical",Category::Medical)]{let s=staff_category_score_v81(schemas,staff,cat);ui.horizontal(|ui|{ui.set_min_width(430.0);ui.label(label);ui.add(egui::ProgressBar::new((s/20.0).clamp(0.0,1.0)).desired_width(280.0).text(format!("{s:.1}/20")));});}
    ui.add_space(6.0);roles(schemas,ui,staff,false);
}
fn show_staff_formations(schemas:&'static crate::fields::VersionedSchemas,ui:&mut egui::Ui,staff:&StaffView){ui.heading("Formations / Tendencies");profile_labels(schemas,ui,staff);ui.add_space(8.0);ui.label("Preferred in/out-of-possession formations and coaching licence are live read-side. Tactical tendencies remain on the editable Overview where mapped.");}
fn show_staff_languages(ui:&mut egui::Ui,staff:&StaffView){ui.heading("Languages");match staff.languages.as_ref(){Some(v) if !v.is_empty()=>{egui::Grid::new(("staff_lang_v81",staff.record.addr)).striped(true).show(ui,|ui|{ui.strong("Language");ui.strong("Level");ui.end_row();for l in v{ui.label(&l.name);ui.label(l.level);ui.end_row();}});},Some(_)=>{ui.label("No languages loaded.");},None=>{ui.label("Language chain unavailable.");}}ui.label(egui::RichText::new("Insert/remove language records remains mapping-only; read side is live.").small().weak());}
fn show_staff_mapping_surface(ui:&mut egui::Ui,title:&str,note:&str){ui.heading(title);ui.label(egui::RichText::new("FMRTE-equivalent workspace is active").strong().color(egui::Color32::from_rgb(96,178,255)));ui.add_space(6.0);egui::Frame::group(ui.style()).inner_margin(10.0).show(ui,|ui|{ui.label(note);ui.label(egui::RichText::new("No blind memory write is exposed until the FM27 object chain is witnessed and read-back/undo semantics are known.").small().weak());});}

'''
    t=t[:idx]+funcs+t[idx:]
wr(p,t)

# -----------------------------------------------------------------------------
# Club: functional recruitment/transfer/staff/clauses workspaces + click-through
# surfaces for every remaining FMRTE-style club destination.
# -----------------------------------------------------------------------------
p='src/ui/club_panel.rs'; t=rd(p)
if '    Vision,\n' not in t:
    t=one(t,'    PowerTools,\n}','    PowerTools,\n    Vision,\n    Recruitment,\n    PlayerClauses,\n    TransferCenter,\n    Kits,\n    Staff,\n    Affiliations,\n    RegionalDivisions,\n    Ownership,\n    Relationships,\n}', 'club tab expansion')
if 'ClubTab::Vision =>' not in t:
    arm='''        ClubTab::PowerTools => show_power_tools(schemas, ui, club, &mut edits, writable, entity_cache),\n'''
    repl=arm+'''        ClubTab::Vision => show_club_vision(schemas,ui,club),\n        ClubTab::Recruitment => show_possible_signings(ui,club,entity_cache,today),\n        ClubTab::PlayerClauses => show_player_clauses(ui,club,entity_cache),\n        ClubTab::TransferCenter => show_transfer_center(ui,club,entity_cache,today),\n        ClubTab::Kits => show_club_mapping_surface(ui,"Kits and Colours","FM27 kit/style types are identified in game metadata.",&["Home / Away / Third kits","Primary / secondary / trim colours","Shirt / shorts / socks","Pattern/style IDs"]),\n        ClubTab::Staff => show_club_staff(ui,club,entity_cache),\n        ClubTab::Affiliations => show_club_mapping_surface(ui,"Affiliations","ClubAffiliates / AffiliateEditSession types are present in FM27 metadata.",&["Parent / senior affiliate","Feeder / loan affiliate","Commercial link","Youth / recruitment link","Cancellation / negotiation"]),\n        ClubTab::RegionalDivisions => show_club_mapping_surface(ui,"Regional Divisions","Regional placement is a real FM concept but its club/competition record chain is not mapped.",&["Current regional division","Preferred regional division","Competition placement"]),\n        ClubTab::Ownership => show_club_mapping_surface(ui,"Ownership","Ownership and takeover semantics are catalogued but not independently mapped.",&["Ownership status/type","Benefactor / funding","Takeover state","Chairperson / board","Staff allowances"]),\n        ClubTab::Relationships => show_club_mapping_surface(ui,"Relationships","Club relationships/supporter concepts are visible in FM27; writable vectors remain unmapped.",&["Rivals","Favoured clubs","Favoured people","Supporter profile","Club morale / identity"]),\n'''
    t=one(t,arm,repl,'club match arms')
if 'fn show_possible_signings(' not in t:
    marker='fn show_power_tools(\n'; idx=t.find(marker)
    if idx<0: raise SystemExit('v8.1 club helper insertion marker missing')
    funcs=r'''fn show_club_vision(schemas:&'static crate::fields::VersionedSchemas,ui:&mut egui::Ui,club:&ClubView){
    ui.horizontal_wrapped(|ui|{ui.heading("Club Vision");ui.label(egui::RichText::new("ELEMENT v8.1 • LIVE CLUB HEALTH").strong().color(egui::Color32::from_rgb(96,178,255)));});
    let rep=schemas.field("c_reputation").and_then(|f|fields::read_field_u16(club,&club.raw,f)).unwrap_or(0);let bal=schemas.field("c_balance").and_then(|f|fields::read_field_u32(club,&club.raw,f)).unwrap_or(0);let tb=schemas.field("c_transfer_budget").and_then(|f|fields::read_field_u32(club,&club.raw,f)).unwrap_or(0);
    egui::Grid::new(("club_vision_v81",club.addr)).striped(true).spacing([20.0,6.0]).show(ui,|ui|{ui.strong("Area");ui.strong("Live signal");ui.strong("Element reading");ui.end_row();ui.label("Reputation");ui.label(rep.to_string());ui.label(if rep>=9000{"Elite global club"}else if rep>=7000{"High reputation"}else{"Developing reputation"});ui.end_row();ui.label("Balance");ui.label(format!("£{:.1}m",bal as f64/1_000_000.0));ui.label(if bal>=100_000_000{"Strong liquidity"}else{"Budget discipline"});ui.end_row();ui.label("Transfer budget");ui.label(format!("£{:.1}m",tb as f64/1_000_000.0));ui.label("Mapped editable budget");ui.end_row();});
    ui.add_space(8.0);ui.label("Native FM ClubVision principles/board objectives are not yet independently mapped; this workspace gives a live operational summary without inventing those records.");
}
fn show_possible_signings(ui:&mut egui::Ui,club:&ClubView,cache:Option<&crate::cache::EntityCache>,today:Option<crate::game_date::GameDate>){
    ui.horizontal_wrapped(|ui|{ui.heading("Possible Signings");ui.label(egui::RichText::new("ELEMENT RECRUITMENT LAB • LIVE CACHE").strong().color(egui::Color32::from_rgb(96,178,255)));});
    let Some(cache)=cache else{ui.label("Entity cache unavailable.");return;};let qid=egui::Id::new(("recruit_q_v81",club.addr));let mut q=ui.ctx().data(|d|d.get_temp::<String>(qid).unwrap_or_default());if ui.add_sized([300.0,22.0],egui::TextEdit::singleline(&mut q).hint_text("Filter name…")).changed(){ui.ctx().data_mut(|d|d.insert_temp(qid,q.clone()));}
    let needle=q.trim().to_lowercase();let mut rows:Vec<_>=cache.players.iter().filter(|p|p.club_id!=Some(club.uid)&&(needle.is_empty()||p.name.to_lowercase().contains(&needle))).collect();rows.sort_by(|a,b|b.pa.cmp(&a.pa).then_with(||b.ca.cmp(&a.ca)));rows.truncate(80);
    egui::Grid::new(("recruit_grid_v81",club.addr)).striped(true).min_col_width(55.0).spacing([12.0,5.0]).show(ui,|ui|{for h in ["Player","Club","Age~","CA","PA","Value"]{ui.strong(h);}ui.end_row();for p in rows{if ui.link(&p.name).clicked(){crate::ui::navigation::request_player_target(ui,p.addr,p.index,p.name.clone());}ui.label(p.club_id.and_then(|id|cache.club_names.get(&id)).cloned().unwrap_or_else(||"Free / unknown".into()));ui.label(today.and_then(|d|(p.dob_year>0&&d.year>=p.dob_year).then_some(d.year-p.dob_year)).map(|v|v.to_string()).unwrap_or_else(||"—".into()));ui.label(p.ca.to_string());ui.label(p.pa.to_string());ui.label(squad_money(p.value));ui.end_row();}});
}
fn show_player_clauses(ui:&mut egui::Ui,club:&ClubView,cache:Option<&crate::cache::EntityCache>){
    ui.heading("Player Clauses");ui.label(egui::RichText::new("Open each squad member directly on Contract / Clauses. Clause records themselves are loaded only in the full Player record, not the bulk cache.").weak());let Some(cache)=cache else{return;};let mut rows:Vec<_>=cache.players.iter().filter(|p|p.club_id==Some(club.uid)).collect();rows.sort_by(|a,b|b.ca.cmp(&a.ca));for p in rows{ui.horizontal(|ui|{ui.label(format!("{} • CA {} / PA {}",p.name,p.ca,p.pa));if ui.button("CONTRACT / CLAUSES").clicked(){ui.ctx().data_mut(|d|d.insert_temp(egui::Id::new("element_open_player_contract_after_nav"),true));crate::ui::navigation::request_player_target(ui,p.addr,p.index,p.name.clone());}});}
}
fn show_transfer_center(ui:&mut egui::Ui,club:&ClubView,cache:Option<&crate::cache::EntityCache>,today:Option<crate::game_date::GameDate>){
    ui.horizontal_wrapped(|ui|{ui.heading("Transfer Center");ui.label(egui::RichText::new("ELEMENT v8.1 • MARKET WORKSPACE").strong().color(egui::Color32::from_rgb(96,178,255)));});let Some(cache)=cache else{return;};
    ui.strong("Squad market");let mut squad:Vec<_>=cache.players.iter().filter(|p|p.club_id==Some(club.uid)).collect();squad.sort_by(|a,b|b.value.unwrap_or(0).cmp(&a.value.unwrap_or(0)));egui::Grid::new(("transfer_squad_v81",club.addr)).striped(true).show(ui,|ui|{for h in ["Player","CA","PA","Value"]{ui.strong(h);}ui.end_row();for p in squad.iter().take(30){if ui.link(&p.name).clicked(){crate::ui::navigation::request_player_target(ui,p.addr,p.index,p.name.clone());}ui.label(p.ca.to_string());ui.label(p.pa.to_string());ui.label(squad_money(p.value));ui.end_row();}});
    ui.add_space(10.0);ui.strong("High-potential external targets");let mut ext:Vec<_>=cache.players.iter().filter(|p|p.club_id!=Some(club.uid)).collect();ext.sort_by(|a,b|b.pa.cmp(&a.pa).then_with(||b.ca.cmp(&a.ca)));egui::Grid::new(("transfer_targets_v81",club.addr)).striped(true).show(ui,|ui|{for h in ["Player","Age~","CA","PA","Value"]{ui.strong(h);}ui.end_row();for p in ext.iter().take(25){if ui.link(&p.name).clicked(){crate::ui::navigation::request_player_target(ui,p.addr,p.index,p.name.clone());}ui.label(today.and_then(|d|(p.dob_year>0&&d.year>=p.dob_year).then_some(d.year-p.dob_year)).map(|v|v.to_string()).unwrap_or_else(||"—".into()));ui.label(p.ca.to_string());ui.label(p.pa.to_string());ui.label(squad_money(p.value));ui.end_row();}});
    ui.label(egui::RichText::new("Native FM TransferProposal/EditSession creation remains separately gated; open a player → Move to club for Element's guarded direct transaction.").small().weak());
}
fn show_club_staff(ui:&mut egui::Ui,club:&ClubView,cache:Option<&crate::cache::EntityCache>){
    ui.heading("Staff");let Some(cache)=cache else{return;};let mut rows:Vec<_>=cache.staff.iter().filter(|s|s.club_id==Some(club.uid)).collect();rows.sort_by(|a,b|b.ca.cmp(&a.ca).then_with(||a.name.cmp(&b.name)));egui::Grid::new(("club_staff_v81",club.addr)).striped(true).show(ui,|ui|{for h in ["Staff","CA","PA"]{ui.strong(h);}ui.end_row();for s in rows{if ui.link(&s.name).clicked(){crate::ui::navigation::request_staff_target(ui,s.addr,s.index,s.name.clone());}ui.label(s.ca.to_string());ui.label(s.pa.to_string());ui.end_row();}});
}
fn show_club_mapping_surface(ui:&mut egui::Ui,title:&str,note:&str,options:&[&str]){ui.heading(title);ui.label(egui::RichText::new("FMRTE-equivalent workspace active • native record mapping in progress").strong().color(egui::Color32::from_rgb(96,178,255)));ui.add_space(6.0);ui.label(note);egui::Frame::group(ui.style()).inner_margin(10.0).show(ui,|ui|{ui.strong("Target options");for o in options{ui.label(format!("• {o}"));}});ui.label(egui::RichText::new("These options are surfaced now so the UI is complete, but Element will not turn them into blind writes before the FM27 object chain and rollback semantics are certified.").small().weak());}

'''
    t=t[:idx]+funcs+t[idx:]
wr(p,t)


print("Element v8.1c staff/club surfaces applied.")
