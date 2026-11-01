from pathlib import Path

root = Path.cwd()


def rd(path):
    p = root / path
    if not p.exists():
        raise SystemExit(f"v7.3 missing {path}")
    return p.read_text(encoding="utf-8")


def wr(path, text):
    (root / path).write_text(text, encoding="utf-8")


def one(text, old, new, label):
    if old not in text:
        raise SystemExit(f"v7.3 marker missing: {label}")
    return text.replace(old, new, 1)


# -----------------------------------------------------------------------------
# Bridge reports / commands
# -----------------------------------------------------------------------------
p = "src/bridge/cmd.rs"
t = rd(p)
if "pub struct ForceTransferReport" not in t:
    marker = "#[derive(Clone, Debug)]\npub struct TacticalMaxPlannedEdit"
    idx = t.find(marker)
    if idx < 0:
        raise SystemExit("v7.3 marker missing: tactical planned edit")
    defs = '''#[derive(Clone, Debug)]
pub struct ForceTransferReport {
    pub player_addr: u64,
    pub source_team_addr: u64,
    pub target_team_addr: u64,
    pub target_club_addr: u64,
    pub roster_entry: u64,
    pub roster_mode: String,
    pub contract_updated: bool,
}

#[derive(Clone, Debug)]
pub struct ForceBuyReport {
    pub transfer: ForceTransferReport,
    pub fee: u32,
    pub seller_balance_before: u32,
    pub seller_balance_after: u32,
    pub buyer_balance_before: u32,
    pub buyer_balance_after: u32,
}

'''
    t = t[:idx] + defs + t[idx:]
if "ForceTransfer {" not in t:
    t = one(
        t,
        "    PlanClubSquadPower { club_addr: u64, club_uid: u32, players: Vec<(u64, usize)>, max_morale: bool, heal_injuries: bool, lift_bans: bool },\n",
        "    PlanClubSquadPower { club_addr: u64, club_uid: u32, players: Vec<(u64, usize)>, max_morale: bool, heal_injuries: bool, lift_bans: bool },\n"
        "    ForceTransfer { player_addr: u64, person_shift: usize, contract_addr: u64, target_club_addr: u64 },\n"
        "    ForceBuy { player_addr: u64, person_shift: usize, contract_addr: u64, target_club_addr: u64, fee: u32 },\n",
        "force commands",
    )
if "ForceTransferOk" not in t:
    t = one(
        t,
        "    SquadPowerPlanReady { club_addr: u64, plan: SquadPowerPlan },\n",
        "    SquadPowerPlanReady { club_addr: u64, plan: SquadPowerPlan },\n"
        "    ForceTransferOk(ForceTransferReport),\n"
        "    ForceTransferFail { player_addr: u64, error: String },\n"
        "    ForceBuyOk(ForceBuyReport),\n"
        "    ForceBuyFail { player_addr: u64, error: String },\n",
        "force results",
    )
wr(p, t)

p = "src/bridge/mod.rs"
t = rd(p)
if "mod force_transfer;" not in t:
    t = one(t, "mod squad_power_tools;\n", "mod squad_power_tools;\nmod force_transfer;\n", "force module")
if "ForceTransferReport" not in t:
    t = one(
        t,
        "    SquadPowerPlan, SquadPowerPlannedEdit,\n",
        "    SquadPowerPlan, SquadPowerPlannedEdit, ForceTransferReport, ForceBuyReport,\n",
        "force report exports",
    )
wr(p, t)

# -----------------------------------------------------------------------------
# Transaction implementation — ported from Element v6 verified FM27 path.
# The user's supplied game_plugin.dll exactly matches upstream's documented
# SHA-256 bc940e...; runtime still performs strong structural guards + readback.
# -----------------------------------------------------------------------------
(root / "src/bridge/force_transfer.rs").write_text(r'''use crate::process::FmProcess;
use super::cmd::{ForceBuyReport, ForceTransferReport};

const VERIFIED_GAME_PLUGIN_FILE_SIZE: u64 = 433_986_560;

fn verified_build(fm: &FmProcess) -> Result<(), String> {
    if fm.build != crate::game_version::GameBuild::Fm27Steam {
        return Err("Force Transfer is enabled only for FM27 Steam".into());
    }
    let size = std::fs::metadata(&fm.module_path)
        .map_err(|e| format!("cannot stat game_plugin.dll: {e}"))?
        .len();
    if size != VERIFIED_GAME_PLUGIN_FILE_SIZE {
        return Err(format!("game_plugin.dll size mismatch: {size}; Force Transfer is locked until this build is re-certified"));
    }
    Ok(())
}

fn ptr_ok(ptr: u64) -> bool {
    (0x10000..0x7fff_ffff_ffff).contains(&ptr)
}

fn vector(fm: &FmProcess, header: u64, max: usize) -> Result<(u64,u64,u64,Vec<u64>),String> {
    let begin=fm.read_u64(header).map_err(|e|format!("vector begin: {e}"))?;
    let end=fm.read_u64(header+8).map_err(|e|format!("vector end: {e}"))?;
    let cap=fm.read_u64(header+16).map_err(|e|format!("vector capacity: {e}"))?;
    if !ptr_ok(begin)||!ptr_ok(end)||!ptr_ok(cap)||begin>end||end>cap||(end-begin)%8!=0 {
        return Err(format!("invalid vector header at 0x{header:X}"));
    }
    let count=((end-begin)/8) as usize;
    if count>max{return Err(format!("vector at 0x{header:X} is implausibly large ({count})"));}
    let raw=fm.read_bytes(begin,count*8).map_err(|e|format!("vector data: {e}"))?;
    let mut entries=Vec::with_capacity(count);
    for chunk in raw.chunks_exact(8){entries.push(u64::from_le_bytes(chunk.try_into().unwrap()));}
    Ok((begin,end,cap,entries))
}

fn entry_mode(fm:&FmProcess, entry:u64, player:u64, person:u64)->Option<&'static str>{
    if entry==player||entry==person{return Some("direct");}
    if !ptr_ok(entry){return None;}
    for off in (0u64..=0x80).step_by(8){
        if let Ok(p)=fm.read_u64(entry+off){if p==player||p==person{return Some("wrapper");}}
    }
    None
}

fn find_senior_team(fm:&FmProcess, club:u64)->Result<u64,String>{
    let (_,_,_,teams)=vector(fm,club+0x18,128)?;
    let mut fallback=None;
    for team in teams{
        if !ptr_ok(team){continue;}
        if fm.read_u64(team+0x30).ok()!=Some(club){continue;}
        let kind=fm.read_u8(team+0x28).unwrap_or(255);
        if kind==0{return Ok(team);}
        fallback.get_or_insert(team);
    }
    fallback.ok_or_else(||"target club has no readable team object".to_owned())
}

fn rollback(fm:&FmProcess, patches:&[(u64,Vec<u8>)]){
    for (addr,old) in patches.iter().rev(){let _=fm.write_bytes(*addr,old);}
}

pub(super) fn force_transfer(
    fm:&FmProcess,
    player_addr:u64,
    person_shift:usize,
    contract_addr:u64,
    target_club_addr:u64,
)->Result<ForceTransferReport,String>{
    verified_build(fm)?;
    if !ptr_ok(player_addr)||!ptr_ok(contract_addr)||!ptr_ok(target_club_addr){
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
    if !ptr_ok(source_team){return Err("player has no writable current-team roster (free agents require contract creation, still unmapped)".into());}
    let target_team=find_senior_team(fm,target_club_addr)?;
    if source_team==target_team{return Err("player is already in the selected target team".into());}

    let source_header=source_team+0x38;
    let target_header=target_team+0x38;
    let (s_begin,s_end,_s_cap,s_entries)=vector(fm,source_header,2000)?;
    let (_t_begin,t_end,t_cap,t_entries)=vector(fm,target_header,2000)?;
    let mut source_hit=None;
    let mut mode="unknown";
    for (i,entry) in s_entries.iter().copied().enumerate(){
        if let Some(m)=entry_mode(fm,entry,player_addr,person){source_hit=Some((i,entry));mode=m;break;}
    }
    let (source_index,roster_entry)=source_hit.ok_or_else(||"player was not found in the current team's explicit roster vector; transaction aborted".to_owned())?;
    if t_entries.iter().copied().any(|e|entry_mode(fm,e,player_addr,person).is_some()){
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
    let rollback_data=vec![
        (t_end,target_slot_old.clone()),
        (target_header+8,old_target_end.clone()),
        (s_begin,source_raw.clone()),
        (source_header+8,old_source_end.clone()),
        (player_addr+0x130,old_player_team.clone()),
        (contract_addr+0x10,old_contract_team.clone()),
        (player_addr+0x204,old_transfer_date.clone()),
    ];

    let mut compact=s_entries.clone(); compact.remove(source_index);
    let compact_raw:Vec<u8>=compact.iter().flat_map(|v|v.to_le_bytes()).collect();
    let write_result=(||->Result<(),String>{
        fm.write_bytes(t_end,&roster_entry.to_le_bytes()).map_err(|e|format!("append target roster entry: {e}"))?;
        fm.write_bytes(target_header+8,&(t_end+8).to_le_bytes()).map_err(|e|format!("advance target roster end: {e}"))?;
        if !compact_raw.is_empty(){fm.write_bytes(s_begin,&compact_raw).map_err(|e|format!("compact source roster: {e}"))?;}
        fm.write_bytes(source_header+8,&(s_end-8).to_le_bytes()).map_err(|e|format!("shrink source roster end: {e}"))?;
        fm.write_bytes(player_addr+0x130,&target_team.to_le_bytes()).map_err(|e|format!("player current team: {e}"))?;
        fm.write_bytes(contract_addr+0x10,&target_team.to_le_bytes()).map_err(|e|format!("contract employer team: {e}"))?;
        let rva=schemas.rva_current_date;
        if rva!=0 {
            if let Ok(today)=fm.read_u32(fm.gp_base+rva){
                let year=(today>>16) as u16; let doy=(today&0x01ff) as u16;
                if (1900..=2200).contains(&year)&&(1..=366).contains(&doy){
                    fm.write_bytes(player_addr+0x204,&today.to_le_bytes()).map_err(|e|format!("transfer date: {e}"))?;
                }
            }
        }
        Ok(())
    })();
    if let Err(e)=write_result{rollback(fm,&rollback_data);return Err(format!("transaction write failed and was rolled back: {e}"));}

    let verify=(||->Result<(),String>{
        if fm.read_u64(player_addr+0x130).ok()!=Some(target_team){return Err("player team read-back mismatch".into());}
        if fm.read_u64(contract_addr+0x10).ok()!=Some(target_team){return Err("contract employer read-back mismatch".into());}
        let (_,_,_,s_after)=vector(fm,source_header,2000)?;
        if s_after.iter().copied().any(|e|entry_mode(fm,e,player_addr,person).is_some()){return Err("source roster still contains player".into());}
        let (_,_,_,t_after)=vector(fm,target_header,2000)?;
        if !t_after.iter().copied().any(|e|entry_mode(fm,e,player_addr,person).is_some()){return Err("target roster does not contain player".into());}
        Ok(())
    })();
    if let Err(e)=verify{rollback(fm,&rollback_data);return Err(format!("read-back validation failed; rollback attempted: {e}"));}

    Ok(ForceTransferReport{
        player_addr,source_team_addr:source_team,target_team_addr:target_team,target_club_addr,
        roster_entry,roster_mode:mode.to_owned(),contract_updated:true,
    })
}

fn club_field_addr(fm:&FmProcess,club_addr:u64,key:&str)->Result<u64,String>{
    let schema=fm.schemas();
    let field=schema.field(key).ok_or_else(||format!("missing field {key}"))?;
    let loc=field.offset.as_ref().ok_or_else(||format!("field {key} is unmapped"))?;
    match loc {
        crate::fields::FieldLocation::Direct{offset,..}=>Ok(club_addr+*offset),
        crate::fields::FieldLocation::SubRecord{container,offset,..}=>{
            let ptr=crate::fields::resolve_sub_ptr(fm,club_addr,container,schema.club_sub_records)
                .ok_or_else(||format!("could not resolve {container} for club 0x{club_addr:X}"))?;
            if *container=="finance" && schema.full_finance_vtable_rva!=0 {
                let expected=fm.gp_base+schema.full_finance_vtable_rva;
                let actual=fm.read_u64(ptr).map_err(|e|format!("finance vtable: {e}"))?;
                if actual!=expected{return Err(format!("club finance object is not the verified full FM27 finance class (0x{actual:X})"));}
            }
            Ok(ptr+*offset)
        }
    }
}

pub(super) fn force_buy(
    fm:&FmProcess,
    player_addr:u64,
    person_shift:usize,
    contract_addr:u64,
    target_club_addr:u64,
    fee:u32,
)->Result<ForceBuyReport,String>{
    verified_build(fm)?;
    if fee==0{return Err("Force Buy fee must be greater than zero".into());}
    let source_team=fm.read_u64(player_addr+0x130).map_err(|e|format!("current team pointer: {e}"))?;
    if !ptr_ok(source_team){return Err("player has no valid source team".into());}
    let source_club_addr=fm.read_u64(source_team+0x30).map_err(|e|format!("source club pointer: {e}"))?;
    if !ptr_ok(source_club_addr)||source_club_addr==target_club_addr{return Err("invalid source/target club for Force Buy".into());}

    let seller_balance_addr=club_field_addr(fm,source_club_addr,"c_balance")?;
    let buyer_balance_addr=club_field_addr(fm,target_club_addr,"c_balance")?;
    let seller_before=fm.read_u32(seller_balance_addr).map_err(|e|format!("seller balance: {e}"))?;
    let buyer_before=fm.read_u32(buyer_balance_addr).map_err(|e|format!("buyer balance: {e}"))?;
    if buyer_before<fee{return Err(format!("target club balance is too low: has £{buyer_before}, needs £{fee}"));}
    let seller_after=seller_before.checked_add(fee).ok_or_else(||"seller balance would overflow u32".to_owned())?;
    let buyer_after=buyer_before-fee;

    let transfer=force_transfer(fm,player_addr,person_shift,contract_addr,target_club_addr)?;

    let seller_old=seller_before.to_le_bytes(); let buyer_old=buyer_before.to_le_bytes();
    if let Err(e)=fm.write_bytes(seller_balance_addr,&seller_after.to_le_bytes()){
        return Err(format!("player moved, but seller balance write failed: {e}; use save backup before continuing"));
    }
    if let Err(e)=fm.write_bytes(buyer_balance_addr,&buyer_after.to_le_bytes()){
        let _=fm.write_bytes(seller_balance_addr,&seller_old);
        return Err(format!("player moved, buyer balance write failed and seller balance was restored: {e}"));
    }
    let seller_rb=fm.read_u32(seller_balance_addr).map_err(|e|format!("seller balance read-back: {e}"))?;
    let buyer_rb=fm.read_u32(buyer_balance_addr).map_err(|e|format!("buyer balance read-back: {e}"))?;
    if seller_rb!=seller_after||buyer_rb!=buyer_after{
        let _=fm.write_bytes(seller_balance_addr,&seller_old); let _=fm.write_bytes(buyer_balance_addr,&buyer_old);
        return Err("finance read-back failed; finance values were restored (player move remains validated)".into());
    }

    Ok(ForceBuyReport{transfer,fee,seller_balance_before:seller_before,seller_balance_after:seller_after,buyer_balance_before:buyer_before,buyer_balance_after:buyer_after})
}
''', encoding="utf-8")

# -----------------------------------------------------------------------------
# Worker wiring
# -----------------------------------------------------------------------------
p = "src/bridge/worker.rs"
t = rd(p)
if "use super::force_transfer;" not in t:
    t = one(t, "use super::squad_power_tools;\n", "use super::squad_power_tools;\nuse super::force_transfer;\n", "worker import")
if "BridgeCmd::ForceBuy" not in t:
    marker = "            BridgeCmd::PlanClubSquadPower { club_addr, club_uid, players, max_morale, heal_injuries, lift_bans } => {\n"
    idx = t.find(marker)
    if idx < 0:
        raise SystemExit("v7.3 marker missing: squad power worker arm")
    arms = '''            BridgeCmd::ForceBuy { player_addr, person_shift, contract_addr, target_club_addr, fee } => {
                match &fm {
                    Some(f) => match force_transfer::force_buy(f, player_addr, person_shift, contract_addr, target_club_addr, fee) {
                        Ok(report) => { let _=tx.send(BridgeResult::ForceBuyOk(report)); }
                        Err(error) => { let _=tx.send(BridgeResult::ForceBuyFail{player_addr,error}); }
                    },
                    None => { let _=tx.send(BridgeResult::ForceBuyFail{player_addr,error:"Cannot Force Buy: no process attached".into()}); }
                }
            }
            BridgeCmd::ForceTransfer { player_addr, person_shift, contract_addr, target_club_addr } => {
                match &fm {
                    Some(f) => match force_transfer::force_transfer(f, player_addr, person_shift, contract_addr, target_club_addr) {
                        Ok(report) => { let _=tx.send(BridgeResult::ForceTransferOk(report)); }
                        Err(error) => { let _=tx.send(BridgeResult::ForceTransferFail{player_addr,error}); }
                    },
                    None => { let _=tx.send(BridgeResult::ForceTransferFail{player_addr,error:"Cannot Force Transfer: no process attached".into()}); }
                }
            }

'''
    t = t[:idx] + arms + t[idx:]
wr(p, t)

# -----------------------------------------------------------------------------
# Player Transfer Power UI + entity-cache target selector
# -----------------------------------------------------------------------------
p = "src/ui/player_panel.rs"
t = rd(p)
# Add cache argument to show().
if "entity_cache: Option<&crate::cache::EntityCache>" not in t:
    t = one(
        t,
        "    names: &mut crate::ui::name_picker::NamePicker,\n) -> Vec<FieldEdit> {",
        "    names: &mut crate::ui::name_picker::NamePicker,\n    entity_cache: Option<&crate::cache::EntityCache>,\n) -> Vec<FieldEdit> {",
        "player show cache arg",
    )
if "    TransferPower,\n" not in t:
    t = one(t, "    PowerTools,\n}", "    PowerTools,\n    TransferPower,\n}", "TransferPower enum")
    t = one(
        t,
        '        ui.selectable_value(tab, PlayerTab::PowerTools, "Power Tools");\n',
        '        ui.selectable_value(tab, PlayerTab::PowerTools, "Power Tools");\n        ui.selectable_value(tab, PlayerTab::TransferPower, "Transfer Power");\n',
        "TransferPower tab button",
    )
    power_arm = '''        PlayerTab::PowerTools => {
            egui::ScrollArea::vertical()
                .id_salt("player_power_tools")
                .show(ui, |ui| {
                    show_player_power_tools(schemas, ui, player, addr, &mut edits);
                });
        }
'''
    transfer_arm = power_arm + '''        PlayerTab::TransferPower => {
            egui::ScrollArea::vertical()
                .id_salt("player_transfer_power")
                .show(ui, |ui| {
                    show_transfer_power(ui, player, entity_cache);
                });
        }
'''
    t = one(t, power_arm, transfer_arm, "TransferPower match arm")

if "fn show_transfer_power(" not in t:
    marker = "fn show_player_power_tools(\n"
    idx = t.find(marker)
    if idx < 0:
        raise SystemExit("v7.3 marker missing: player power function")
    fn = r'''fn show_transfer_power(
    ui: &mut egui::Ui,
    player: &PlayerRecord,
    entity_cache: Option<&crate::cache::EntityCache>,
) {
    ui.horizontal_wrapped(|ui| {
        ui.heading("Transfer Power");
        ui.label(egui::RichText::new("ELEMENT v7.3 • GUARDED DIRECT TRANSACTION").strong().color(egui::Color32::from_rgb(116,145,255)));
    });
    ui.label(egui::RichText::new("Direct Move updates explicit team rosters + player team + contract employer + transfer date with rollback/read-back. Force Buy additionally settles the fee against verified club balances. It does NOT create a native FM bid, Inbox item or transfer-history record.").weak());
    ui.add_space(8.0);

    let Some(cache)=entity_cache else { ui.label("Entity cache unavailable."); return; };
    if player.contract_addr.is_none() { ui.colored_label(egui::Color32::YELLOW,"Player has no mapped current contract; direct transfer is unavailable."); return; }

    let search_id=egui::Id::new(("element_v7_transfer_club_search",player.addr));
    let selected_id=egui::Id::new(("element_v7_transfer_club_selected",player.addr));
    let mut query=ui.ctx().data_mut(|d|d.get_temp::<String>(search_id).unwrap_or_default());
    ui.horizontal(|ui|{
        ui.label("Target club:");
        if ui.add_sized([260.0,22.0],egui::TextEdit::singleline(&mut query).hint_text("Search club…")).changed(){
            ui.ctx().data_mut(|d|d.insert_temp(search_id,query.clone()));
        }
    });
    if query.trim().len()>=2 {
        let q=query.to_lowercase();
        let mut shown=0usize;
        for c in &cache.clubs {
            if Some(c.addr)==player.club_addr {continue;}
            if !(c.name.to_lowercase().contains(&q)||c.full_name.to_lowercase().contains(&q)){continue;}
            let label=if c.full_name.is_empty(){c.name.clone()}else{format!("{} • {}",c.name,c.full_name)};
            if ui.selectable_label(false,&label).clicked(){
                ui.ctx().data_mut(|d|d.insert_temp(selected_id,(c.addr,c.uid,label.clone())));
                query.clear(); ui.ctx().data_mut(|d|d.insert_temp(search_id,String::new()));
            }
            shown+=1; if shown>=15{break;}
        }
        if shown==0{ui.label("No matching clubs.");}
    }

    let selected=ui.ctx().data(|d|d.get_temp::<(u64,u32,String)>(selected_id));
    let Some((target_addr,_target_uid,target_name))=selected else {
        ui.label(egui::RichText::new("Select a target club before enabling transfer actions.").weak());
        return;
    };
    ui.colored_label(egui::Color32::from_rgb(88,214,141),format!("Selected: {target_name}"));

    let fee_id=egui::Id::new(("element_v7_force_buy_fee",player.addr));
    let mut fee_text=ui.ctx().data_mut(|d|d.get_temp::<String>(fee_id).unwrap_or_else(||"25000000".into()));
    ui.horizontal(|ui|{
        ui.label("Fee (£):");
        if ui.add_sized([180.0,22.0],egui::TextEdit::singleline(&mut fee_text)).changed(){ui.ctx().data_mut(|d|d.insert_temp(fee_id,fee_text.clone()));}
    });
    let clean=fee_text.replace([',','.',' ','£','€','$'],"");
    let fee=clean.parse::<u32>().ok().filter(|v|*v>0);

    let ack_id=egui::Id::new(("element_v7_force_transfer_ack",player.addr));
    let mut ack=ui.ctx().data_mut(|d|d.get_temp::<bool>(ack_id).unwrap_or(false));
    if ui.checkbox(&mut ack,"I made a save backup and understand this is a direct live transaction").changed(){ui.ctx().data_mut(|d|d.insert_temp(ack_id,ack));}
    let enabled=can_edit(ui)&&ack&&player.club_addr!=Some(target_addr);

    ui.add_space(6.0);
    ui.horizontal_wrapped(|ui|{
        if ui.add_enabled(enabled,egui::Button::new("⚡ DIRECT MOVE • NO FEE / HISTORY"))
            .on_hover_text("Guarded roster + ownership move. Internal rollback runs if any write/read-back fails.")
            .clicked()
        {
            ui.ctx().data_mut(|d|d.insert_temp(egui::Id::new("element_v7_force_transfer_request"),(player.addr,player.person_shift,player.contract_addr.unwrap(),target_addr)));
        }
        if ui.add_enabled(enabled&&fee.is_some(),egui::Button::new("💰 FORCE BUY • DIRECT SETTLEMENT"))
            .on_hover_text("Runs the guarded direct move, then transfers the entered fee from buyer balance to seller balance with finance read-back.")
            .clicked()
        {
            ui.ctx().data_mut(|d|d.insert_temp(egui::Id::new("element_v7_force_buy_request"),(player.addr,player.person_shift,player.contract_addr.unwrap(),target_addr,fee.unwrap())));
        }
    });

    ui.add_space(10.0);
    ui.separator();
    ui.strong("Native FM transfer workflow");
    ui.add_enabled(false,egui::Button::new("📨 CREATE NATIVE BID • MAPPING"))
        .on_disabled_hover_text("FM27 TransferOffer/EditSession types and ActionIDs are identified, but creation/rollback of a native proposal is not independently certified yet.");
    ui.label(egui::RichText::new("Native Inbox/history/interest remains locked until its record chain is certified. Direct Settlement is usable now and is deliberately labelled non-native.").weak());
}

'''
    t = t[:idx] + fn + t[idx:]
wr(p, t)

# -----------------------------------------------------------------------------
# App: pass cache, process results, dispatch requests
# -----------------------------------------------------------------------------
p = "src/app.rs"
t = rd(p)
# Current call ends with names; add cache.
old = '''                                        schemas, self.game_date, ui, p, &mut self.player_tab, addr,
                                        wage_period, face_pack_path.as_deref(), &mut self.names,
                                    );'''
new = '''                                        schemas, self.game_date, ui, p, &mut self.player_tab, addr,
                                        wage_period, face_pack_path.as_deref(), &mut self.names,
                                        cache_arc.as_deref(),
                                    );'''
if old in t:
    t=t.replace(old,new,1)
elif "cache_arc.as_deref(),\n                                    );" not in t:
    raise SystemExit("v7.3 marker missing: player_panel app call")

if "BridgeResult::ForceBuyOk" not in t:
    marker = "                BridgeResult::SquadPowerPlanReady { club_addr, plan } => {\n"
    idx=t.find(marker)
    if idx<0: raise SystemExit("v7.3 marker missing: squad power result")
    arms = r'''                BridgeResult::ForceBuyOk(report) => {
                    let player_addr=report.transfer.player_addr;
                    self.set_status(format!("Force Buy DIRECT SETTLEMENT OK • fee £{} • seller £{} → £{} • buyer £{} → £{} • non-native transfer history",report.fee,report.seller_balance_before,report.seller_balance_after,report.buyer_balance_before,report.buyer_balance_after));
                    self.entity_cache=None;
                    self.cache_load_state=CacheLoadState::Loading{done:0,total:0};
                    self.bridge.send(BridgeCmd::LoadEntityCache);
                    if let Some(p)=self.selected_player.as_ref().filter(|p|p.addr==player_addr){self.bridge.send(BridgeCmd::LoadPlayer(p.addr,p.index));}
                }
                BridgeResult::ForceBuyFail { player_addr:_, error } => self.set_status(format!("Force Buy aborted: {error}")),
                BridgeResult::ForceTransferOk(report) => {
                    let player_addr=report.player_addr;
                    self.set_status(format!("Direct Move OK • source team 0x{:X} → target 0x{:X} • {} roster entry • contract ownership updated",report.source_team_addr,report.target_team_addr,report.roster_mode));
                    self.entity_cache=None;
                    self.cache_load_state=CacheLoadState::Loading{done:0,total:0};
                    self.bridge.send(BridgeCmd::LoadEntityCache);
                    if let Some(p)=self.selected_player.as_ref().filter(|p|p.addr==player_addr){self.bridge.send(BridgeCmd::LoadPlayer(p.addr,p.index));}
                }
                BridgeResult::ForceTransferFail { player_addr:_, error } => self.set_status(format!("Direct Move aborted: {error}")),
'''
    t=t[:idx]+arms+t[idx:]

if "element_v7_force_buy_request" not in t:
    marker = "        if let Some((club_addr,club_uid,players,max_morale,heal_injuries,lift_bans)) = ctx.data_mut(|d| {\n"
    idx=t.find(marker)
    if idx<0: raise SystemExit("v7.3 marker missing: squad request")
    block = r'''        if let Some((player_addr,person_shift,contract_addr,target_club_addr,fee)) = ctx.data_mut(|d| {
            let id=egui::Id::new("element_v7_force_buy_request");
            let v=d.get_temp::<(u64,usize,u64,u64,u32)>(id); d.remove::<(u64,usize,u64,u64,u32)>(id); v
        }) {
            if self.conn.is_writable(){
                self.bridge.send(BridgeCmd::ForceBuy{player_addr,person_shift,contract_addr,target_club_addr,fee});
                self.set_status(format!("Force Buy running • £{fee} • roster + ownership + balances + read-back…"));
            }
        }
        if let Some((player_addr,person_shift,contract_addr,target_club_addr)) = ctx.data_mut(|d| {
            let id=egui::Id::new("element_v7_force_transfer_request");
            let v=d.get_temp::<(u64,usize,u64,u64)>(id); d.remove::<(u64,usize,u64,u64)>(id); v
        }) {
            if self.conn.is_writable(){
                self.bridge.send(BridgeCmd::ForceTransfer{player_addr,person_shift,contract_addr,target_club_addr});
                self.set_status("Direct Move running • roster + ownership + transfer date + read-back…".into());
            }
        }
'''
    t=t[:idx]+block+t[idx:]
wr(p,t)

print("Element v7.3 guarded Force Transfer / Force Buy applied.")
