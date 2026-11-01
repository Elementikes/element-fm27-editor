from pathlib import Path

root=Path.cwd()

def rd(path):
    p=root/path
    if not p.exists(): raise SystemExit(f"v8.3 missing {path}")
    return p.read_text(encoding="utf-8")

def wr(path,text): (root/path).write_text(text,encoding="utf-8")

def one(text,old,new,label):
    if old not in text: raise SystemExit(f"v8.3 marker missing: {label}")
    return text.replace(old,new,1)

# -----------------------------------------------------------------------------
# Bridge commands/results for transactional relationship add/remove.
# Add never allocates: it requires an existing favoured-club template record
# and spare vector capacity. Remove compacts in-place. Both read back and roll
# back on failure.
# -----------------------------------------------------------------------------
p='src/bridge/cmd.rs'; t=rd(p)
if 'pub struct RelationMutationReport' not in t:
    marker='#[derive(Clone, Debug)]\npub struct SwapPlayersReport'
    idx=t.find(marker)
    if idx<0: raise SystemExit('v8.3 relation report marker missing')
    defs='''#[derive(Clone, Debug)]\npub struct RelationMutationReport {\n    pub player_addr: u64,\n    pub relation_addr: u64,\n    pub target_addr: u64,\n    pub action: String,\n}\n\n'''
    t=t[:idx]+defs+t[idx:]
if 'AddFavouredClubRelation {' not in t:
    old='    SwapPlayers { player_a_addr: u64, person_a_shift: usize, contract_a_addr: u64, player_b_addr: u64, player_b_index: usize },\n'
    new=old+'    AddFavouredClubRelation { player_addr: u64, person_shift: usize, target_club_addr: u64, strength: u8, reason: u8 },\n    RemovePlayerRelation { player_addr: u64, person_shift: usize, relation_addr: u64 },\n'
    t=one(t,old,new,'relation commands')
if 'RelationMutationOk' not in t:
    old='    SwapPlayersFail { player_addr: u64, error: String },\n'
    new=old+'    RelationMutationOk(RelationMutationReport),\n    RelationMutationFail { player_addr: u64, error: String },\n'
    t=one(t,old,new,'relation results')
wr(p,t)

# -----------------------------------------------------------------------------
# Memory transaction implementation. Reuses the already verified FM27 build
# guard and rollback helpers in force_transfer.rs.
# -----------------------------------------------------------------------------
p='src/bridge/force_transfer.rs'; t=rd(p)
if 'RelationMutationReport' not in t.split('\n',3)[1]:
    t=t.replace('use super::cmd::{ForceBuyReport, ForceTransferReport, SwapPlayersReport};','use super::cmd::{ForceBuyReport, ForceTransferReport, SwapPlayersReport, RelationMutationReport};',1)
if 'pub(super) fn add_favoured_club_relation(' not in t:
    marker='fn club_field_addr('
    idx=t.find(marker)
    if idx<0: raise SystemExit('v8.3 relation function marker missing')
    funcs=r'''fn relation_vector_bounds(
    fm:&FmProcess,
    player_addr:u64,
    person_shift:usize,
)->Result<(u64,u64,u64,u64,usize),String>{
    verified_build(fm)?;
    let schemas=fm.schemas();
    let l=schemas.player_lists.ok_or_else(||"player relationship layout unavailable".to_owned())?;
    let physical=crate::player::player_phys_offset(schemas,l.relations_ptr as u64,person_shift);
    let object=fm.read_u64(player_addr+physical).map_err(|e|format!("relationship object pointer: {e}"))?;
    if !ptr_ok(object){return Err("relationship object pointer failed plausibility checks".into());}
    let header=object+l.relations_vec as u64;
    let begin=fm.read_u64(header).map_err(|e|format!("relationship vector begin: {e}"))?;
    let end=fm.read_u64(header+8).map_err(|e|format!("relationship vector end: {e}"))?;
    let cap=fm.read_u64(header+16).map_err(|e|format!("relationship vector capacity: {e}"))?;
    let stride=l.relation_size;
    if stride==0||!ptr_ok(begin)||!ptr_ok(end)||!ptr_ok(cap)||begin>end||end>cap||(end-begin)%(stride as u64)!=0{
        return Err(format!("invalid relationship vector header at 0x{header:X}"));
    }
    let count=((end-begin)/(stride as u64)) as usize;
    if count>64{return Err(format!("relationship vector implausibly large ({count})"));}
    Ok((header,begin,end,cap,stride))
}

pub(super) fn add_favoured_club_relation(
    fm:&FmProcess,
    player_addr:u64,
    person_shift:usize,
    target_club_addr:u64,
    strength:u8,
    reason:u8,
)->Result<RelationMutationReport,String>{
    if !ptr_ok(player_addr)||!ptr_ok(target_club_addr){return Err("player/club pointer failed plausibility checks".into());}
    let schemas=fm.schemas();
    let l=schemas.player_lists.ok_or_else(||"player relationship layout unavailable".to_owned())?;
    let (header,begin,end,cap,stride)=relation_vector_bounds(fm,player_addr,person_shift)?;
    if end.checked_add(stride as u64).map_or(true,|next|next>cap){return Err("relationship vector has no spare capacity; Element will not allocate inside FM".into());}
    let count=((end-begin)/(stride as u64)) as usize;
    if count==0{return Err("no existing relationship record is available as a safe FM27 template".into());}
    let raw=fm.read_bytes(begin,count*stride).map_err(|e|format!("relationship vector snapshot: {e}"))?;
    let mut template=None;
    for (i,entry) in raw.chunks_exact(stride).enumerate(){
        let target=u64::from_le_bytes(entry[l.relation_target..l.relation_target+8].try_into().unwrap());
        let kind=entry[l.relation_kind];let ty=entry[l.relation_type];
        if kind==l.kind_club&&ty==l.type_favoured_club{
            if target==target_club_addr{return Err("this favoured club relationship already exists".into());}
            if template.is_none(){template=Some((begin+i as u64*stride as u64,entry.to_vec()));}
        }
    }
    let (_,mut new_record)=template.ok_or_else(||"player has no existing favoured-club record to use as a certified template".to_owned())?;
    new_record[l.relation_target..l.relation_target+8].copy_from_slice(&target_club_addr.to_le_bytes());
    new_record[l.relation_reason]=if reason==2{2}else{1};
    new_record[l.relation_kind]=l.kind_club;
    new_record[l.relation_type]=l.type_favoured_club;
    new_record[l.relation_strength]=strength.min(100);
    let old_slot=fm.read_bytes(end,stride).map_err(|e|format!("relationship spare slot snapshot: {e}"))?;
    let old_end=fm.read_bytes(header+8,8).map_err(|e|format!("relationship end snapshot: {e}"))?;
    let rollback_data=vec![(end,old_slot),(header+8,old_end)];
    let write_result=(||->Result<(),String>{
        fm.write_bytes(end,&new_record).map_err(|e|format!("relationship record write: {e}"))?;
        fm.write_bytes(header+8,&(end+stride as u64).to_le_bytes()).map_err(|e|format!("relationship vector end write: {e}"))?;
        Ok(())
    })();
    if let Err(e)=write_result{rollback(fm,&rollback_data);return Err(format!("relationship add failed; rollback attempted: {e}"));}
    let verify=(||->Result<(),String>{
        if fm.read_u64(header+8).ok()!=Some(end+stride as u64){return Err("relationship vector end read-back mismatch".into());}
        let rec=fm.read_bytes(end,stride).map_err(|e|format!("relationship read-back: {e}"))?;
        let target=u64::from_le_bytes(rec[l.relation_target..l.relation_target+8].try_into().unwrap());
        if target!=target_club_addr||rec[l.relation_kind]!=l.kind_club||rec[l.relation_type]!=l.type_favoured_club||rec[l.relation_strength]!=strength.min(100){return Err("relationship record read-back mismatch".into());}
        Ok(())
    })();
    if let Err(e)=verify{rollback(fm,&rollback_data);return Err(format!("relationship add validation failed; rollback attempted: {e}"));}
    Ok(RelationMutationReport{player_addr,relation_addr:end,target_addr:target_club_addr,action:"Added favoured club".into()})
}

pub(super) fn remove_player_relation(
    fm:&FmProcess,
    player_addr:u64,
    person_shift:usize,
    relation_addr:u64,
)->Result<RelationMutationReport,String>{
    let (header,begin,end,_cap,stride)=relation_vector_bounds(fm,player_addr,person_shift)?;
    if relation_addr<begin||relation_addr>=end||(relation_addr-begin)%(stride as u64)!=0{return Err("selected relationship is not an aligned member of the live vector".into());}
    let old_record=fm.read_bytes(relation_addr,stride).map_err(|e|format!("relationship selected snapshot: {e}"))?;
    let target_addr=u64::from_le_bytes(old_record[0..8].try_into().unwrap());
    let span_len=(end-relation_addr) as usize;
    let old_span=fm.read_bytes(relation_addr,span_len).map_err(|e|format!("relationship compact snapshot: {e}"))?;
    let old_end=fm.read_bytes(header+8,8).map_err(|e|format!("relationship end snapshot: {e}"))?;
    let rollback_data=vec![(relation_addr,old_span),(header+8,old_end)];
    let tail_start=relation_addr+stride as u64;
    let tail_len=(end-tail_start) as usize;
    let tail=if tail_len>0{Some(fm.read_bytes(tail_start,tail_len).map_err(|e|format!("relationship tail snapshot: {e}"))?)}else{None};
    let write_result=(||->Result<(),String>{
        if let Some(tail)=tail.as_ref(){fm.write_bytes(relation_addr,tail).map_err(|e|format!("relationship compact write: {e}"))?;}
        fm.write_bytes(end-stride as u64,&vec![0u8;stride]).map_err(|e|format!("relationship trailing slot clear: {e}"))?;
        fm.write_bytes(header+8,&(end-stride as u64).to_le_bytes()).map_err(|e|format!("relationship vector shrink: {e}"))?;
        Ok(())
    })();
    if let Err(e)=write_result{rollback(fm,&rollback_data);return Err(format!("relationship remove failed; rollback attempted: {e}"));}
    if fm.read_u64(header+8).ok()!=Some(end-stride as u64){rollback(fm,&rollback_data);return Err("relationship remove read-back mismatch; rollback attempted".into());}
    Ok(RelationMutationReport{player_addr,relation_addr,target_addr,action:"Removed relationship".into()})
}

'''
    t=t[:idx]+funcs+t[idx:]
wr(p,t)

# Worker dispatch.
p='src/bridge/worker.rs'; t=rd(p)
if 'BridgeCmd::AddFavouredClubRelation' not in t:
    marker='            BridgeCmd::ForceBuy { player_addr, person_shift, contract_addr, target_club_addr, fee } => {'
    idx=t.find(marker)
    if idx<0: raise SystemExit('v8.3 worker insertion marker missing')
    arms=r'''            BridgeCmd::AddFavouredClubRelation { player_addr, person_shift, target_club_addr, strength, reason } => {
                let result=match &fm {Some(f)=>force_transfer::add_favoured_club_relation(f,player_addr,person_shift,target_club_addr,strength,reason),None=>Err("Cannot edit relationships: no process attached".into())};
                match result {Ok(report)=>{let _=tx.send(BridgeResult::RelationMutationOk(report));}Err(error)=>{let _=tx.send(BridgeResult::RelationMutationFail{player_addr,error});}}
            }
            BridgeCmd::RemovePlayerRelation { player_addr, person_shift, relation_addr } => {
                let result=match &fm {Some(f)=>force_transfer::remove_player_relation(f,player_addr,person_shift,relation_addr),None=>Err("Cannot edit relationships: no process attached".into())};
                match result {Ok(report)=>{let _=tx.send(BridgeResult::RelationMutationOk(report));}Err(error)=>{let _=tx.send(BridgeResult::RelationMutationFail{player_addr,error});}}
            }

'''
    t=t[:idx]+arms+t[idx:]
wr(p,t)

# -----------------------------------------------------------------------------
# Player UI: dedicated Transfer Proposals page + FMRTE-style relationship
# manager with club search, strength/reason, transactional add/remove.
# -----------------------------------------------------------------------------
p='src/ui/player_panel.rs'; t=rd(p)
if '    TransferProposals,\n' not in t:
    t=one(t,'    ScoutInfo,\n}','    ScoutInfo,\n    TransferProposals,\n}','transfer proposals tab enum')

scout_arm='''        PlayerTab::ScoutInfo => {
            egui::ScrollArea::vertical().id_salt("player_scout_v81").show(ui, |ui|
                show_scout_info(schemas,today,ui,player,entity_cache));
        }
'''
if 'PlayerTab::TransferProposals =>' not in t:
    extra=scout_arm+'''        PlayerTab::TransferProposals => {
            egui::ScrollArea::vertical().id_salt("player_transfer_proposals_v83").show(ui, |ui|
                show_transfer_proposals_v83(schemas,ui,player,addr,entity_cache,&mut edits));
        }
'''
    t=one(t,scout_arm,extra,'transfer proposals match arm')

old_rel='''.show(ui, |ui| show_relationships_panel(schemas, ui, player, &mut edits));'''
if 'show_relationships_extra_v83' not in t:
    t=one(t,old_rel,'''.show(ui, |ui| { show_relationships_panel(schemas, ui, player, &mut edits); show_relationships_extra_v83(ui,player,entity_cache); });''','relationship extra hook')

# Make existing relationship reason editable with the verified reason byte.
old_reason='''                        let reason=layout.favoured_club_reasons.iter().find(|(code,_)|*code==r.reason).map(|(_,name)|*name).unwrap_or("Unknown");
                        crate::ui::field_widget::info_label(ui,"Reason",reason);
'''
if 'Relationship reason:' not in t:
    new_reason=r'''                        let mut reason_code=r.reason;
                        egui::ComboBox::from_id_salt(("v83_relation_reason",r.addr)).selected_text(layout.favoured_club_reasons.iter().find(|(code,_)|*code==reason_code).map(|(_,name)|*name).unwrap_or("Unknown")).show_ui(ui,|ui|{
                            for (code,name) in layout.favoured_club_reasons { ui.selectable_value(&mut reason_code,*code,*name); }
                        });
                        if reason_code!=r.reason && crate::ui::navigation::editing_enabled(ui){
                            let old=r.reason;r.reason=reason_code;edits.push(FieldEdit{addr:r.addr+layout.relation_reason as u64,old_raw:vec![old],new_raw:vec![reason_code],description:format!("Relationship reason: {} → {}",old,reason_code),presentation:None});
                        }
'''
    t=one(t,old_reason,new_reason,'relationship reason editor')

# Replace old mapping-only footer with a concise pointer to the live manager.
old_footer='''            ui.add_space(8.0);
            ui.horizontal_wrapped(|ui|{
                ui.add_enabled(false,egui::Button::new("＋ ADD RELATIONSHIP • MAPPING"));
                ui.add_enabled(false,egui::Button::new("REMOVE SELECTED • MAPPING"));
                ui.label(egui::RichText::new("Vector allocation/deallocation remains locked; existing value edits are guarded and undoable.").small().weak());
            });
'''
if old_footer in t:
    t=t.replace(old_footer,'''            ui.add_space(6.0);ui.label(egui::RichText::new("v8.3 live Add / Remove controls are below. Add uses spare vector capacity only; no allocator is called.").small().weak());
''',1)

if 'fn show_relationships_extra_v83(' not in t:
    marker='fn push_max_category_edits(\n'; idx=t.find(marker)
    if idx<0: raise SystemExit('v8.3 player helper marker missing')
    funcs=r'''fn select_cached_club_v83<'a>(ui:&mut egui::Ui,player:&PlayerRecord,cache:Option<&'a crate::cache::EntityCache>,id_tag:&'static str)->Option<&'a crate::cache::CachedClub>{
    let cache=cache?;let qid=egui::Id::new((id_tag,"q",player.addr));let sid=egui::Id::new((id_tag,"club",player.addr));
    let mut q=ui.ctx().data(|d|d.get_temp::<String>(qid).unwrap_or_default());let selected=ui.ctx().data(|d|d.get_temp::<u64>(sid));
    ui.horizontal(|ui|{ui.label("Club:");if ui.add_sized([300.0,22.0],egui::TextEdit::singleline(&mut q).hint_text("Search club…")).changed(){ui.ctx().data_mut(|d|d.insert_temp(qid,q.clone()));}});
    if q.trim().len()>=2{let n=q.to_lowercase();let mut shown=0;for c in cache.clubs.iter().filter(|c|c.addr!=player.club_addr.unwrap_or(0)&&c.name.to_lowercase().contains(&n)){if ui.selectable_label(selected==Some(c.addr),format!("{} • UID {}",c.name,c.uid)).clicked(){ui.ctx().data_mut(|d|d.insert_temp(sid,c.addr));q.clear();ui.ctx().data_mut(|d|d.insert_temp(qid,String::new()));}shown+=1;if shown>=20{break;}}}
    let addr=ui.ctx().data(|d|d.get_temp::<u64>(sid))?;cache.clubs.iter().find(|c|c.addr==addr)
}

fn show_relationships_extra_v83(ui:&mut egui::Ui,player:&PlayerRecord,cache:Option<&crate::cache::EntityCache>){
    ui.add_space(10.0);ui.separator();ui.horizontal_wrapped(|ui|{ui.heading("Relationship Manager");ui.label(egui::RichText::new("ELEMENT v8.3 • LIVE ADD / REMOVE").strong().color(egui::Color32::from_rgb(96,178,255)));});
    ui.label(egui::RichText::new("FMRTE-style favoured-club management. Add clones an existing FM27 favoured-club record only when the live vector has spare capacity; Remove compacts in-place. Both use read-back + rollback.").weak());
    let Some(club)=select_cached_club_v83(ui,player,cache,"v83_relation_club") else{ui.label("Search and select a target club to add. You can still remove the currently selected relationship below.");
        let selected=ui.ctx().data(|d|d.get_temp::<u64>(egui::Id::new(("element_relationship_selected",player.addr))));
        if ui.add_enabled(crate::ui::navigation::editing_enabled(ui)&&selected.is_some(),egui::Button::new("− REMOVE SELECTED RELATIONSHIP • LIVE")).clicked(){ui.ctx().data_mut(|d|d.insert_temp(egui::Id::new("element_v83_remove_relation_request"),(player.addr,player.person_shift,selected.unwrap())));}return;};
    ui.label(format!("Target: {} • UID {}",club.name,club.uid));
    let strength_id=egui::Id::new(("v83_relation_strength",player.addr));let reason_id=egui::Id::new(("v83_relation_reason_add",player.addr));
    let mut strength=ui.ctx().data(|d|d.get_temp::<u8>(strength_id).unwrap_or(100));let mut reason=ui.ctx().data(|d|d.get_temp::<u8>(reason_id).unwrap_or(1));
    ui.horizontal_wrapped(|ui|{ui.label("Value");ui.add(egui::Slider::new(&mut strength,0..=100));egui::ComboBox::from_id_salt(("v83_relation_reason_combo",player.addr)).selected_text(if reason==2{"As a player"}else{"As a supporter"}).show_ui(ui,|ui|{ui.selectable_value(&mut reason,1,"As a supporter");ui.selectable_value(&mut reason,2,"As a player");});});
    ui.ctx().data_mut(|d|{d.insert_temp(strength_id,strength);d.insert_temp(reason_id,reason);});
    let selected=ui.ctx().data(|d|d.get_temp::<u64>(egui::Id::new(("element_relationship_selected",player.addr))));
    ui.horizontal_wrapped(|ui|{
        if ui.add_enabled(crate::ui::navigation::editing_enabled(ui),egui::Button::new("＋ ADD FAVOURED CLUB • LIVE")).clicked(){ui.ctx().data_mut(|d|d.insert_temp(egui::Id::new("element_v83_add_relation_request"),(player.addr,player.person_shift,club.addr,strength,reason)));}
        if ui.add_enabled(crate::ui::navigation::editing_enabled(ui)&&selected.is_some(),egui::Button::new("− REMOVE SELECTED • LIVE")).clicked(){ui.ctx().data_mut(|d|d.insert_temp(egui::Id::new("element_v83_remove_relation_request"),(player.addr,player.person_shift,selected.unwrap())));}
    });
    ui.label(egui::RichText::new("Currently certified relation family: Favoured Club / Likes Team, with As supporter / As player reason. FMRTE also exposes broader RelationTypes/FavouredPeople; those record layouts remain locked until independently witnessed.").small().weak());
}

fn set_player_u32_v83(schemas:&'static fields::VersionedSchemas,player:&mut PlayerRecord,addr:u64,key:&str,value:u32,label:&str,edits:&mut Vec<FieldEdit>)->bool{
    let Some(f)=schemas.field(key) else{return false;};let Some(loc)=f.offset else{return false;};let off=loc.offset() as usize;if off+4>player.raw.len(){return false;}let old_raw=player.raw[off..off+4].to_vec();let old=u32::from_le_bytes(old_raw.as_slice().try_into().unwrap());if old==value{return false;}let new_raw=value.to_le_bytes().to_vec();player.raw[off..off+4].copy_from_slice(&new_raw);let physical=addr+player::player_phys_offset(schemas,loc.offset(),player.person_shift);edits.push(FieldEdit{addr:physical,old_raw,new_raw,description:format!("{label}: {old} → {value}"),presentation:None});true
}

fn set_transfer_listing_v83(schemas:&'static fields::VersionedSchemas,player:&mut PlayerRecord,listed:bool,edits:&mut Vec<FieldEdit>)->usize{
    let today_raw=player.game_date.map(|d|d.raw);let Some(base)=player.contract_addr else{return 0;};let Some(raw)=player.contract_raw.as_mut() else{return 0;};let mut n=0usize;
    if let Some(off)=contract_offset(schemas,"p_list_flags"){if let Some(&old)=raw.get(off){let new=if listed{old|1}else{old&!1};if old!=new{raw[off]=new;edits.push(FieldEdit{addr:base+off as u64,old_raw:vec![old],new_raw:vec![new],description:format!("Transfer listed: {listed}"),presentation:None});n+=1;}}}
    if let Some(off)=contract_offset(schemas,"p_list_code"){if let Some(&old)=raw.get(off){let new=if listed{5}else{0};if old!=new{raw[off]=new;edits.push(FieldEdit{addr:base+off as u64,old_raw:vec![old],new_raw:vec![new],description:format!("Listing code: {old} → {new}"),presentation:None});n+=1;}}}
    if let Some(off)=contract_offset(schemas,"p_list_date"){if off+4<=raw.len(){let old_raw=raw[off..off+4].to_vec();let old=u32::from_le_bytes(old_raw.as_slice().try_into().unwrap());let new=if listed{today_raw.unwrap_or(old)}else{0x076C0001};if old!=new{let nr=new.to_le_bytes().to_vec();raw[off..off+4].copy_from_slice(&nr);edits.push(FieldEdit{addr:base+off as u64,old_raw,new_raw:nr,description:if listed{"Listed since → today".into()}else{"Listed since → cleared".into()},presentation:None});n+=1;}}}
    n
}

fn show_transfer_proposals_v83(schemas:&'static fields::VersionedSchemas,ui:&mut egui::Ui,player:&mut PlayerRecord,addr:u64,cache:Option<&crate::cache::EntityCache>,edits:&mut Vec<FieldEdit>){
    ui.horizontal_wrapped(|ui|{ui.heading("Transfer Proposals");ui.label(egui::RichText::new("ELEMENT v8.3 • AI TRANSFER POWER").strong().color(egui::Color32::from_rgb(96,178,255)));});
    ui.label(egui::RichText::new("Choose an AI club and control the market state. DIRECT DEAL uses Element's verified roster/contract/finance transaction: buyer pays seller and the player moves with read-back + rollback. It does not fabricate an FM Inbox offer.").weak());
    if player.contract_addr.is_none(){ui.colored_label(egui::Color32::YELLOW,"Player has no mapped contract; AI deal controls are unavailable.");return;}
    let selected=select_cached_club_v83(ui,player,cache,"v83_ai_transfer_club");
    let fee_id=egui::Id::new(("v83_ai_fee",player.addr));let mut fee=ui.ctx().data(|d|d.get_temp::<u32>(fee_id).unwrap_or(player.field_u32("p_asking_price").unwrap_or(25_000_000).min(2_000_000_000)));
    ui.horizontal_wrapped(|ui|{ui.label("Fee £");ui.add(egui::DragValue::new(&mut fee).range(0..=2_000_000_000u32).speed(100_000.0));if ui.add_enabled(crate::ui::navigation::editing_enabled(ui),egui::Button::new("SET ASKING PRICE")).clicked(){set_player_u32_v83(schemas,player,addr,"p_asking_price",fee,"Asking Price",edits);}});ui.ctx().data_mut(|d|d.insert_temp(fee_id,fee));
    ui.horizontal_wrapped(|ui|{if ui.add_enabled(crate::ui::navigation::editing_enabled(ui),egui::Button::new("🏷 TRANSFER LIST")).clicked(){set_transfer_listing_v83(schemas,player,true,edits);}if ui.add_enabled(crate::ui::navigation::editing_enabled(ui),egui::Button::new("UNLIST")).clicked(){set_transfer_listing_v83(schemas,player,false,edits);}});
    if let Some(club)=selected{
        ui.label(format!("AI buyer: {} • UID {}",club.name,club.uid));
        ui.horizontal_wrapped(|ui|{
            if ui.add_enabled(crate::ui::navigation::editing_enabled(ui),egui::Button::new("🤖 AI BUY • DIRECT SETTLEMENT")).on_hover_text("Moves the selected player to this AI club and settles the fee buyer→seller using the verified Force Buy transaction.").clicked(){ui.ctx().data_mut(|d|d.insert_temp(egui::Id::new("element_v7_force_buy_request"),(player.addr,player.person_shift,player.contract_addr.unwrap(),club.addr,fee)));}
            if ui.add_enabled(crate::ui::navigation::editing_enabled(ui),egui::Button::new("↪ AI MOVE • NO FEE")).clicked(){ui.ctx().data_mut(|d|d.insert_temp(egui::Id::new("element_v7_force_transfer_request"),(player.addr,player.person_shift,player.contract_addr.unwrap(),club.addr)));}
            if ui.add_enabled(crate::ui::navigation::editing_enabled(ui),egui::Button::new("🔥 LIST + ASKING PRICE + AI BUY")).clicked(){set_transfer_listing_v83(schemas,player,true,edits);set_player_u32_v83(schemas,player,addr,"p_asking_price",fee,"Asking Price",edits);ui.ctx().data_mut(|d|d.insert_temp(egui::Id::new("element_v7_force_buy_request"),(player.addr,player.person_shift,player.contract_addr.unwrap(),club.addr,fee)));}
        });
    }
    ui.add_space(10.0);ui.separator();ui.strong("Native AI proposal research");
    ui.label("FM27 IL2CPP exposes PersonMakeOfferForPlayer, PersonAskIntermediariesToOfferPlayerToClubs, PersonWithdrawPlayerTransferOffer and TransferOffer* objects. FMRTE exposes TransferProposals. Element now gives the same end-result transaction safely; native Inbox proposal injection remains locked until the TransferOffer allocation/ownership chain is witnessed.");
}

'''
    t=t[:idx]+funcs+t[idx:]
wr(p,t)

# -----------------------------------------------------------------------------
# App routing/results/requests.
# -----------------------------------------------------------------------------
p='src/app.rs'; t=rd(p)
t=t.replace('pnav!("⇄  Transfer Proposals", player_panel::PlayerTab::TransferPower);','pnav!("⇄  Transfer Proposals", player_panel::PlayerTab::TransferProposals);',1)
if 'BridgeResult::RelationMutationOk' not in t:
    marker='                BridgeResult::SwapPlayersOk(report) => {'
    idx=t.find(marker)
    if idx<0: raise SystemExit('v8.3 app result marker missing')
    arms=r'''                BridgeResult::RelationMutationOk(report) => {
                    self.set_status(format!("{} • player 0x{:X} • relation 0x{:X}",report.action,report.player_addr,report.relation_addr));
                    if let Some(p)=self.selected_player.as_ref().filter(|p|p.addr==report.player_addr){self.bridge.send(BridgeCmd::LoadPlayer(p.addr,p.index));}
                }
                BridgeResult::RelationMutationFail { player_addr:_, error } => self.set_status(format!("Relationship transaction aborted: {error}")),
'''
    t=t[:idx]+arms+t[idx:]
if 'element_v83_add_relation_request' not in t:
    marker='        if let Some((player_a_addr,person_a_shift,contract_a_addr,player_b_addr,player_b_index)) = ctx.data_mut(|d| {'
    idx=t.find(marker)
    if idx<0: raise SystemExit('v8.3 app request marker missing')
    block=r'''        if let Some((player_addr,person_shift,target_club_addr,strength,reason)) = ctx.data_mut(|d| {
            let id=egui::Id::new("element_v83_add_relation_request");let v=d.get_temp::<(u64,usize,u64,u8,u8)>(id);d.remove::<(u64,usize,u64,u8,u8)>(id);v
        }) { if self.conn.is_writable(){self.bridge.send(BridgeCmd::AddFavouredClubRelation{player_addr,person_shift,target_club_addr,strength,reason});self.set_status("Adding favoured club relationship • guarded vector transaction…".into());} }
        if let Some((player_addr,person_shift,relation_addr)) = ctx.data_mut(|d| {
            let id=egui::Id::new("element_v83_remove_relation_request");let v=d.get_temp::<(u64,usize,u64)>(id);d.remove::<(u64,usize,u64)>(id);v
        }) { if self.conn.is_writable(){self.bridge.send(BridgeCmd::RemovePlayerRelation{player_addr,person_shift,relation_addr});self.set_status("Removing relationship • guarded vector compaction…".into());} }

'''
    t=t[:idx]+block+t[idx:]
wr(p,t)

print('Element v8.3 AI Transfer Power + Relationships applied.')
