from pathlib import Path

root=Path.cwd()

# ---------- cmd.rs ----------
p=root/'src/bridge/cmd.rs'
t=p.read_text()
anchor='''#[derive(Clone, Debug, Default)]\npub struct TacticalInspectorReport {'''
insert='''#[derive(Clone, Debug)]\npub struct ForceTransferReport {\n    pub player_addr: u64,\n    pub source_team_addr: u64,\n    pub target_team_addr: u64,\n    pub target_club_addr: u64,\n    pub roster_entry: u64,\n    pub roster_mode: String,\n    pub contract_updated: bool,\n}\n\n'''
if insert not in t:
    assert anchor in t
    t=t.replace(anchor,insert+anchor,1)
old='''    InspectTacticalKnowledge { club_addr: u64, senior_team_addr: u64 },\n    WriteBytes { id: u64, addr: u64, data: Vec<u8> },'''
new='''    InspectTacticalKnowledge { club_addr: u64, senior_team_addr: u64 },\n    ForceTransfer { player_addr: u64, person_shift: usize, contract_addr: u64, target_club_addr: u64 },\n    WriteBytes { id: u64, addr: u64, data: Vec<u8> },'''
assert old in t
t=t.replace(old,new,1)
old='''    TacticalInspectorDone { club_addr: u64, report: TacticalInspectorReport },\n    HumanManagerLoaded(StaffView),'''
new='''    TacticalInspectorDone { club_addr: u64, report: TacticalInspectorReport },\n    ForceTransferOk(ForceTransferReport),\n    ForceTransferFail { player_addr: u64, error: String },\n    HumanManagerLoaded(StaffView),'''
assert old in t
t=t.replace(old,new,1)
p.write_text(t)

# ---------- worker.rs ----------
p=root/'src/bridge/worker.rs'
t=p.read_text()
t=t.replace('use super::cmd::{BridgeCmd, BridgeResult, EntityCounts};','use super::cmd::{BridgeCmd, BridgeResult, EntityCounts, ForceTransferReport};',1)
anchor='''// ---------------------------------------------------------------------------\n// Worker loop\n// ---------------------------------------------------------------------------\n'''
helper=r'''// ---------------------------------------------------------------------------
// Element v5.0 — guarded FM27 force-transfer transaction
// ---------------------------------------------------------------------------

fn element_v5_ptr_ok(ptr: u64) -> bool {
    (0x10000..0x7fff_ffff_ffff).contains(&ptr)
}

fn element_v5_vector(fm: &FmProcess, header: u64, max: usize) -> Result<(u64,u64,u64,Vec<u64>),String> {
    let begin=fm.read_u64(header).map_err(|e|format!("vector begin: {e}"))?;
    let end=fm.read_u64(header+8).map_err(|e|format!("vector end: {e}"))?;
    let cap=fm.read_u64(header+16).map_err(|e|format!("vector capacity: {e}"))?;
    if !element_v5_ptr_ok(begin)||!element_v5_ptr_ok(end)||!element_v5_ptr_ok(cap)||begin>end||end>cap||(end-begin)%8!=0 {
        return Err(format!("invalid vector header at 0x{header:X}"));
    }
    let count=((end-begin)/8) as usize;
    if count>max{return Err(format!("vector at 0x{header:X} is implausibly large ({count})"));}
    let raw=fm.read_bytes(begin,count*8).map_err(|e|format!("vector data: {e}"))?;
    let mut entries=Vec::with_capacity(count);
    for chunk in raw.chunks_exact(8){entries.push(u64::from_le_bytes(chunk.try_into().unwrap()));}
    Ok((begin,end,cap,entries))
}

fn element_v5_entry_mode(fm:&FmProcess, entry:u64, player:u64, person:u64)->Option<&'static str>{
    if entry==player||entry==person{return Some("direct");}
    if !element_v5_ptr_ok(entry){return None;}
    for off in (0u64..=0x80).step_by(8){
        if let Ok(p)=fm.read_u64(entry+off){if p==player||p==person{return Some("wrapper");}}
    }
    None
}

fn element_v5_find_senior_team(fm:&FmProcess, club:u64)->Result<u64,String>{
    let (_,_,_,teams)=element_v5_vector(fm,club+0x18,128)?;
    let mut fallback=None;
    for team in teams{
        if !element_v5_ptr_ok(team){continue;}
        if fm.read_u64(team+0x30).ok()!=Some(club){continue;}
        let kind=fm.read_u8(team+0x28).unwrap_or(255);
        if kind==0{return Ok(team);}
        fallback.get_or_insert(team);
    }
    fallback.ok_or_else(||"target club has no readable team object".to_owned())
}

fn element_v5_rollback(fm:&FmProcess, patches:&[(u64,Vec<u8>)]){
    for (addr,old) in patches.iter().rev(){let _=fm.write_bytes(*addr,old);}
}

fn element_v5_force_transfer(
    fm:&FmProcess,
    player_addr:u64,
    person_shift:usize,
    contract_addr:u64,
    target_club_addr:u64,
)->Result<ForceTransferReport,String>{
    if fm.build!=crate::game_version::GameBuild::Fm27Steam{
        return Err("Force Transfer v5.0 is enabled only for the verified FM27 Steam layout".into());
    }
    if !element_v5_ptr_ok(player_addr)||!element_v5_ptr_ok(contract_addr)||!element_v5_ptr_ok(target_club_addr){
        return Err("player/contract/target pointer failed plausibility checks".into());
    }
    let schemas=fm.schemas();
    let person=player_addr
        .checked_add(schemas.player_person_offset as u64)
        .and_then(|v|v.checked_add(person_shift as u64))
        .ok_or_else(||"player person pointer overflow".to_owned())?;
    let back=fm.read_u64(contract_addr+0x08).map_err(|e|format!("contract back-pointer: {e}"))?;
    if back!=person{return Err(format!("contract ownership guard failed: expected person 0x{person:X}, got 0x{back:X}"));}

    let source_team=fm.read_u64(player_addr+0x130).map_err(|e|format!("current team pointer: {e}"))?;
    if !element_v5_ptr_ok(source_team){return Err("player has no writable current-team roster (free agents require contract creation, still unmapped)".into());}
    let target_team=element_v5_find_senior_team(fm,target_club_addr)?;
    if source_team==target_team{return Err("player is already in the selected target team".into());}

    let source_header=source_team+0x38;
    let target_header=target_team+0x38;
    let (s_begin,s_end,_s_cap,s_entries)=element_v5_vector(fm,source_header,2000)?;
    let (_t_begin,t_end,t_cap,t_entries)=element_v5_vector(fm,target_header,2000)?;
    let mut source_hit=None;
    let mut mode="unknown";
    for (i,entry) in s_entries.iter().copied().enumerate(){
        if let Some(m)=element_v5_entry_mode(fm,entry,player_addr,person){source_hit=Some((i,entry));mode=m;break;}
    }
    let (source_index,roster_entry)=source_hit.ok_or_else(||"player was not found in the current team's explicit roster vector; transaction aborted".to_owned())?;
    if t_entries.iter().copied().any(|e|element_v5_entry_mode(fm,e,player_addr,person).is_some()){
        return Err("target roster already contains this player".into());
    }
    if t_end.checked_add(8).map_or(true,|next|next>t_cap){return Err("target roster vector has no spare capacity; Element will not allocate inside FM".into());}

    let source_raw=fm.read_bytes(s_begin,s_entries.len()*8).map_err(|e|format!("source roster snapshot: {e}"))?;
    let target_slot_old=fm.read_bytes(t_end,8).map_err(|e|format!("target spare slot snapshot: {e}"))?;
    let old_player_team=fm.read_bytes(player_addr+0x130,8).map_err(|e|format!("player team snapshot: {e}"))?;
    let old_contract_team=fm.read_bytes(contract_addr+0x10,8).map_err(|e|format!("contract team snapshot: {e}"))?;
    let old_transfer_date=fm.read_bytes(player_addr+0x204,4).map_err(|e|format!("transfer date snapshot: {e}"))?;
    let old_source_end=fm.read_bytes(source_header+8,8).map_err(|e|format!("source end snapshot: {e}"))?;
    let old_target_end=fm.read_bytes(target_header+8,8).map_err(|e|format!("target end snapshot: {e}"))?;
    let rollback=vec![
        (t_end,target_slot_old.clone()),
        (target_header+8,old_target_end.clone()),
        (s_begin,source_raw.clone()),
        (source_header+8,old_source_end.clone()),
        (player_addr+0x130,old_player_team.clone()),
        (contract_addr+0x10,old_contract_team.clone()),
        (player_addr+0x204,old_transfer_date.clone()),
    ];

    let mut compact=s_entries.clone();
    compact.remove(source_index);
    let compact_raw:Vec<u8>=compact.iter().flat_map(|v|v.to_le_bytes()).collect();
    let write_result=(||->Result<(),String>{
        fm.write_bytes(t_end,&roster_entry.to_le_bytes()).map_err(|e|format!("append target roster entry: {e}"))?;
        fm.write_bytes(target_header+8,&(t_end+8).to_le_bytes()).map_err(|e|format!("advance target roster end: {e}"))?;
        if !compact_raw.is_empty(){fm.write_bytes(s_begin,&compact_raw).map_err(|e|format!("compact source roster: {e}"))?;}
        fm.write_bytes(source_header+8,&(s_end-8).to_le_bytes()).map_err(|e|format!("shrink source roster end: {e}"))?;
        fm.write_bytes(player_addr+0x130,&target_team.to_le_bytes()).map_err(|e|format!("player current team: {e}"))?;
        fm.write_bytes(contract_addr+0x10,&target_team.to_le_bytes()).map_err(|e|format!("contract employer team: {e}"))?;
        const RVA_CURRENT_DATE:u64=0x56AD378;
        if let Ok(today)=fm.read_u32(fm.gp_base+RVA_CURRENT_DATE){
            let year=(today>>16) as u16;let doy=(today&0x01ff) as u16;
            if (1900..=2200).contains(&year)&&(1..=366).contains(&doy){
                fm.write_bytes(player_addr+0x204,&today.to_le_bytes()).map_err(|e|format!("transfer date: {e}"))?;
            }
        }
        Ok(())
    })();
    if let Err(e)=write_result{element_v5_rollback(fm,&rollback);return Err(format!("transaction write failed and was rolled back: {e}"));}

    let verify=(||->Result<(),String>{
        if fm.read_u64(player_addr+0x130).ok()!=Some(target_team){return Err("player team read-back mismatch".into());}
        if fm.read_u64(contract_addr+0x10).ok()!=Some(target_team){return Err("contract employer read-back mismatch".into());}
        let (_,_,_,s_after)=element_v5_vector(fm,source_header,2000)?;
        if s_after.iter().copied().any(|e|element_v5_entry_mode(fm,e,player_addr,person).is_some()){return Err("source roster still contains player".into());}
        let (_,_,_,t_after)=element_v5_vector(fm,target_header,2000)?;
        if !t_after.iter().copied().any(|e|element_v5_entry_mode(fm,e,player_addr,person).is_some()){return Err("target roster does not contain player".into());}
        Ok(())
    })();
    if let Err(e)=verify{element_v5_rollback(fm,&rollback);return Err(format!("read-back validation failed; rollback attempted: {e}"));}

    Ok(ForceTransferReport{
        player_addr,source_team_addr:source_team,target_team_addr:target_team,target_club_addr,
        roster_entry,roster_mode:mode.to_owned(),contract_updated:true,
    })
}

'''
if helper not in t:
    assert anchor in t
    t=t.replace(anchor,helper+anchor,1)
old='''            BridgeCmd::WriteBytes { id, addr, data } => {'''
new='''            BridgeCmd::ForceTransfer { player_addr, person_shift, contract_addr, target_club_addr } => {
                match &fm {
                    Some(f) => match element_v5_force_transfer(f, player_addr, person_shift, contract_addr, target_club_addr) {
                        Ok(report) => { let _ = tx.send(BridgeResult::ForceTransferOk(report)); }
                        Err(error) => { let _ = tx.send(BridgeResult::ForceTransferFail { player_addr, error }); }
                    },
                    None => { let _ = tx.send(BridgeResult::ForceTransferFail { player_addr, error: "Cannot force transfer: no process attached".into() }); }
                }
            }

            BridgeCmd::WriteBytes { id, addr, data } => {'''
assert old in t
t=t.replace(old,new,1)
p.write_text(t)

# ---------- player_panel.rs ----------
p=root/'src/ui/player_panel.rs'
t=p.read_text()
anchor='''// ---------------------------------------------------------------------------\n// Transfer Lab — Element FM27\n// ---------------------------------------------------------------------------\n'''
helper=r'''fn element_v5_listing_now(
    schemas: &'static crate::fields::VersionedSchemas,
    player: &mut PlayerRecord,
    edits: &mut Vec<FieldEdit>,
) -> bool {
    let (Some(raw),Some(base),Some(today))=(player.contract_raw.as_mut(),player.contract_addr,player.game_date) else{return false;};
    let Some(date_off)=schemas.offset_of("p_list_date") else{return false;};
    let Some(flags_off)=schemas.offset_of("p_list_flags") else{return false;};
    let Some(code_off)=schemas.offset_of("p_list_code") else{return false;};
    if date_off+4>raw.len()||flags_off>=raw.len()||code_off>=raw.len(){return false;}
    let start=date_off;let end=code_off+1;
    if end>raw.len()||flags_off<start||flags_off>=end{return false;}
    let old=raw[start..end].to_vec();let mut new=old.clone();
    new[0..4].copy_from_slice(&today.raw.to_le_bytes());
    new[flags_off-start]=raw[flags_off]|1;
    new[code_off-start]=5;
    if new==old{return true;}
    raw[start..end].copy_from_slice(&new);
    edits.push(FieldEdit{addr:base+start as u64,old_raw:old,new_raw:new,description:"Sell Assist — transfer list now".into()});
    true
}

fn element_v5_offer_magnet(
    schemas: &'static crate::fields::VersionedSchemas,
    player: &mut PlayerRecord,
    edits: &mut Vec<FieldEdit>,
    percent: u32,
) {
    let _=element_v5_listing_now(schemas,player,edits);
    let Some(field)=schemas.field("p_value") else{return;};
    let Some(loc)=field.offset.as_ref() else{return;};
    let off=loc.offset() as usize;
    let Some(bytes)=player.raw.get(off..off+4) else{return;};
    let old=u32::from_le_bytes(bytes.try_into().unwrap());
    if old==0||old==u32::MAX{return;}
    let new=((u64::from(old)*u64::from(percent))/100).clamp(1,u64::from(u32::MAX)) as u32;
    if new==old{return;}
    player.raw[off..off+4].copy_from_slice(&new.to_le_bytes());
    edits.push(FieldEdit{addr:player.addr+off as u64,old_raw:old.to_le_bytes().to_vec(),new_raw:new.to_le_bytes().to_vec(),description:format!("Offer Magnet — transfer value {old} → {new} ({percent}%)")});
}

'''
if helper not in t:
    assert anchor in t
    t=t.replace(anchor,helper+anchor,1)
old='''    ui.label(egui::RichText::new("Transfer/loan listing, listing metadata, value, asking price and mapped contract fields are live. Force/Future Transfer stays locked until all linked membership records are verified.").size(8.5).color(egui::Color32::from_rgb(150, 166, 194)));'''
new='''    ui.label(egui::RichText::new("v5.0: verified market writes + guarded roster/ownership transaction. Offer Magnet uses listing/value writes to stimulate FM's AI market; it does not fabricate an unmapped proposal record.").size(8.5).color(egui::Color32::from_rgb(150, 166, 194)));'''
assert old in t
t=t.replace(old,new,1)
anchor='''    ui.add_space(5.0);\n    egui::Frame::group(ui.style())\n        .fill(egui::Color32::from_rgb(20, 25, 36))'''
sell=r'''    ui.add_space(5.0);
    egui::Frame::group(ui.style())
        .fill(egui::Color32::from_rgb(23, 34, 35))
        .stroke(egui::Stroke::new(1.0, egui::Color32::from_rgb(48, 88, 72)))
        .rounding(egui::Rounding::same(4))
        .inner_margin(egui::Margin::symmetric(7, 5))
        .show(ui, |ui| {
            ui.horizontal(|ui| {
                ui.label(egui::RichText::new("SELL / OFFER MAGNET").size(9.0).strong().color(egui::Color32::from_rgb(72,210,132)));
                ui.label(egui::RichText::new("AI MARKET TRIGGER • VERIFIED WRITES").size(7.5).color(egui::Color32::from_rgb(139,157,188)));
            });
            ui.horizontal_wrapped(|ui| {
                let enabled=crate::ui::navigation::editing_enabled(ui)&&player.contract_raw.is_some()&&player.game_date.is_some();
                if ui.add_enabled(enabled,egui::Button::new("LIST NOW")).on_hover_text("Transfer-list the player with today's live FM date and verified listing code 5.").clicked(){let _=element_v5_listing_now(schemas,player,edits);}
                if ui.add_enabled(enabled,egui::Button::new("OFFER MAGNET • 75%")).on_hover_text("List now + reduce verified transfer value to 75%. FM AI still decides whether/when to bid.").clicked(){element_v5_offer_magnet(schemas,player,edits,75);}
                if ui.add_enabled(enabled,egui::Button::new("OFFER MAGNET • 50%")).on_hover_text("Aggressive sale: list now + 50% transfer value.").clicked(){element_v5_offer_magnet(schemas,player,edits,50);}
                if ui.add_enabled(enabled,egui::Button::new("FIRE SALE • 25%")).on_hover_text("Extreme market trigger: list now + 25% transfer value. Use Undo to restore after bids arrive.").clicked(){element_v5_offer_magnet(schemas,player,edits,25);}
            });
            ui.label(egui::RichText::new("Incoming proposal vectors are not publicly mapped for FM27, so Element never invents a fake offer. Continue the game after applying a preset; restore value later with Undo if desired.").size(7.5).color(egui::Color32::from_rgb(180,190,205)));
        });

    ui.add_space(5.0);
    egui::Frame::group(ui.style())
        .fill(egui::Color32::from_rgb(20, 25, 36))'''
assert anchor in t
t=t.replace(anchor,sell,1)
old='''                        ui.columns(2,|cols|{\n                            player_page_card(&mut cols[0],"Verified",|ui|{\n                                field_widget::info_label(ui,"Current player team pointer","READ-SIDE VERIFIED");\n                                field_widget::info_label(ui,"Target club entity","CACHE VERIFIED");\n                                field_widget::info_label(ui,"Contract ownership chain","PARTIALLY MAPPED");\n                            });\n                            player_page_card(&mut cols[1],"Still required before write",|ui|{\n                                field_widget::info_label(ui,"Source squad removal","UNMAPPED");\n                                field_widget::info_label(ui,"Destination team membership","UNMAPPED");\n                                field_widget::info_label(ui,"Registration/eligibility update","UNMAPPED");\n                                field_widget::info_label(ui,"Atomic read-back","NOT CERTIFIED");\n                            });\n                        });\n                        ui.add_enabled(false,egui::Button::new("FORCE TRANSFER • SAFETY GATE 2/5").min_size(egui::vec2(ui.available_width(),24.0))).on_disabled_hover_text("Element refuses a partial team-pointer-only transfer because it can leave squad, contract and registration records inconsistent.");'''
new='''                        ui.columns(2,|cols|{
                            player_page_card(&mut cols[0],"v5.0 transaction guards",|ui|{
                                field_widget::info_label(ui,"Current team pointer","VERIFIED");
                                field_widget::info_label(ui,"Source roster vector","RUNTIME VERIFIED");
                                field_widget::info_label(ui,"Target senior team / roster","RUNTIME VERIFIED");
                                field_widget::info_label(ui,"Contract employer chain","VERIFIED");
                            });
                            player_page_card(&mut cols[1],"Transaction behaviour",|ui|{
                                field_widget::info_label(ui,"Roster remove + append","ATOMIC GUARD");
                                field_widget::info_label(ui,"Team + contract ownership","WRITE + READ-BACK");
                                field_widget::info_label(ui,"Failure handling","ROLLBACK");
                                field_widget::info_label(ui,"Competition registration","FM RECALC / NOT DIRECTLY WRITTEN");
                            });
                        });
                        let ack_id=egui::Id::new(("element_force_transfer_ack",player.addr));
                        let mut ack=ui.data_mut(|d|d.get_temp::<bool>(ack_id).unwrap_or(false));
                        ui.checkbox(&mut ack,"I understand: experimental live transfer; make a save backup first");
                        ui.data_mut(|d|d.insert_temp(ack_id,ack));
                        let can_force=crate::ui::navigation::editing_enabled(ui)&&ack&&player.contract_addr.is_some()&&player.club_addr!=Some(club.addr);
                        if ui.add_enabled(can_force,egui::Button::new("⚡ FORCE TRANSFER TO SELECTED CLUB").min_size(egui::vec2(ui.available_width(),28.0))).on_hover_text("FM27 Steam only. Moves the exact source roster entry, appends it to the target senior roster, updates player team + contract employer + transfer date, then reads every link back. Any failed read-back triggers rollback.").clicked(){
                            if let Some(contract_addr)=player.contract_addr{
                                let req_id=egui::Id::new("element_force_transfer_request_v5");
                                ui.ctx().data_mut(|d|d.insert_temp(req_id,(player.addr,player.person_shift,contract_addr,club.addr)));
                            }
                        }'''
assert old in t
t=t.replace(old,new,1)
old='''            ui.label(egui::RichText::new("Force Transfer Lab is now interactive and target-aware. Execution unlocks only when source removal + destination membership + ownership + registration + read-back are all FM27-certified.").size(8.0).color(egui::Color32::from_rgb(154, 169, 194)));'''
new='''            ui.label(egui::RichText::new("v5.0 Force Transfer is a guarded FM27 Steam transaction. Competition-specific registration is not directly rewritten; FM may recalculate eligibility after Continue/reload.").size(8.0).color(egui::Color32::from_rgb(154, 169, 194)));'''
assert old in t
t=t.replace(old,new,1)
p.write_text(t)

# ---------- club_panel squad layout ----------
p=root/'src/ui/club_panel.rs'
t=p.read_text()
old='''            ui.vertical_centered(|ui| {'''
new='''            ui.vertical(|ui| {'''
idx=t.index('fn show_squad_action_bar(')
pos=t.find(old,idx)
assert pos!=-1
t=t[:pos]+t[pos:].replace(old,new,1)
if 'v4.8 • SMART SQUAD CONTROL' in t:
    t=t.replace('v4.8 • SMART SQUAD CONTROL','v5.0 • COMPACT LIVE SQUAD CONTROL',1)
needle='''                ui.label(egui::RichText::new("LIVE MEMBERSHIP").size(7.5).strong().color(egui::Color32::from_rgb(72, 210, 132)));\n                ui.label(egui::RichText::new("LIVE MEMBERSHIP").size(7.5).strong().color(egui::Color32::from_rgb(72, 210, 132)));'''
if needle in t:t=t.replace(needle,needle.split('\n')[0],1)
p.write_text(t)

# ---------- app.rs ----------
p=root/'src/app.rs'
t=p.read_text()
old='''                BridgeResult::WriteOk { id } => self.complete_write(id, true, None),'''
new='''                BridgeResult::ForceTransferOk(report) => {
                    let msg=format!("Force Transfer OK • source 0x{:X} → target team 0x{:X} • {} roster entry • contract ownership updated",report.source_team_addr,report.target_team_addr,report.roster_mode);
                    self.set_status(msg);
                    self.entity_cache=None;
                    self.cache_load_state=CacheLoadState::Loading{done:0,total:0};
                    self.bridge.send(BridgeCmd::LoadEntityCache);
                    if let Some(player)=self.selected_player.as_ref().filter(|p|p.addr==report.player_addr){self.bridge.send(BridgeCmd::LoadPlayer(player.addr,player.index));}
                }
                BridgeResult::ForceTransferFail { player_addr: _, error } => {
                    self.set_status(format!("Force Transfer aborted: {error}"));
                }
                BridgeResult::WriteOk { id } => self.complete_write(id, true, None),'''
assert old in t
t=t.replace(old,new,1)
anchor='''        // Element v2.8 read-only Tactical Knowledge inspector request.\n        let tactical_request = ctx.data_mut(|d| {'''
insert='''        // Element v5.0 guarded Force Transfer request. The worker owns the
        // entire multi-write transaction and rolls back on any failed read-back.
        let force_transfer_request = ctx.data_mut(|d| {
            let id=egui::Id::new("element_force_transfer_request_v5");
            let request=d.get_temp::<(u64,usize,u64,u64)>(id);
            d.remove::<(u64,usize,u64,u64)>(id);
            request
        });
        if let Some((player_addr,person_shift,contract_addr,target_club_addr))=force_transfer_request{
            if self.conn.is_writable(){
                self.bridge.send(BridgeCmd::ForceTransfer{player_addr,person_shift,contract_addr,target_club_addr});
                self.set_status("Force Transfer transaction running — roster + ownership + read-back…".into());
            }else{self.set_status("Force Transfer requires a live writable FM27 session".into());}
        }

'''
assert anchor in t
t=t.replace(anchor,insert+anchor,1)
p.write_text(t)

print('Element v5.0 Force Transfer + Sell Assist + compact Squads applied.')
