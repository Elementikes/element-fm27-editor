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
# Bridge: transactional player swap using the already verified roster/contract
# ownership chain. Unlike Force Transfer, a swap replaces roster slots in place,
# so it needs no vector allocation/capacity changes.
# -----------------------------------------------------------------------------
p='src/bridge/cmd.rs'; t=rd(p)
if 'pub struct SwapPlayersReport' not in t:
    marker='#[derive(Clone, Debug)]\npub struct ForceBuyReport'
    idx=t.find(marker)
    if idx<0: raise SystemExit('v8.1 swap report marker missing')
    defs='''#[derive(Clone, Debug)]\npub struct SwapPlayersReport {\n    pub player_a_addr: u64,\n    pub player_b_addr: u64,\n    pub team_a_before: u64,\n    pub team_b_before: u64,\n}\n\n'''
    t=t[:idx]+defs+t[idx:]
if 'SwapPlayers {' not in t:
    t=one(t,
        '    ForceBuy { player_addr: u64, person_shift: usize, contract_addr: u64, target_club_addr: u64, fee: u32 },\n',
        '    ForceBuy { player_addr: u64, person_shift: usize, contract_addr: u64, target_club_addr: u64, fee: u32 },\n    SwapPlayers { player_a_addr: u64, person_a_shift: usize, contract_a_addr: u64, player_b_addr: u64, player_b_index: usize },\n',
        'swap command')
if 'SwapPlayersOk' not in t:
    t=one(t,
        '    ForceBuyFail { player_addr: u64, error: String },\n',
        '    ForceBuyFail { player_addr: u64, error: String },\n    SwapPlayersOk(SwapPlayersReport),\n    SwapPlayersFail { player_addr: u64, error: String },\n',
        'swap result')
wr(p,t)

p='src/bridge/force_transfer.rs'; t=rd(p)
if 'SwapPlayersReport' not in t.split('\n',3)[1]:
    t=t.replace('use super::cmd::{ForceBuyReport, ForceTransferReport};','use super::cmd::{ForceBuyReport, ForceTransferReport, SwapPlayersReport};',1)
if 'pub(super) fn swap_players(' not in t:
    marker='fn club_field_addr('
    idx=t.find(marker)
    if idx<0: raise SystemExit('v8.1 force transfer insertion marker missing')
    fn=r'''pub(super) fn swap_players(
    fm:&FmProcess,
    player_a:u64,
    shift_a:usize,
    contract_a:u64,
    player_b:u64,
    shift_b:usize,
    contract_b:u64,
)->Result<SwapPlayersReport,String>{
    verified_build(fm)?;
    for ptr in [player_a,contract_a,player_b,contract_b] { if !ptr_ok(ptr){return Err("swap player/contract pointer failed plausibility checks".into());} }
    if player_a==player_b{return Err("cannot swap a player with himself".into());}
    let schemas=fm.schemas();
    let person_a=player_a.checked_add(schemas.player_person_offset as u64).and_then(|v|v.checked_add(shift_a as u64)).ok_or("player A person pointer overflow")?;
    let person_b=player_b.checked_add(schemas.player_person_offset as u64).and_then(|v|v.checked_add(shift_b as u64)).ok_or("player B person pointer overflow")?;
    if fm.read_u64(contract_a+0x08).ok()!=Some(person_a){return Err("player A contract ownership guard failed".into());}
    if fm.read_u64(contract_b+0x08).ok()!=Some(person_b){return Err("player B contract ownership guard failed".into());}
    let team_a=fm.read_u64(player_a+0x130).map_err(|e|format!("player A team: {e}"))?;
    let team_b=fm.read_u64(player_b+0x130).map_err(|e|format!("player B team: {e}"))?;
    if !ptr_ok(team_a)||!ptr_ok(team_b)||team_a==team_b{return Err("players must belong to two different readable teams".into());}
    if fm.read_u64(contract_a+0x10).ok()!=Some(team_a){return Err("player A contract team does not match current team; reload player before swap".into());}
    if fm.read_u64(contract_b+0x10).ok()!=Some(team_b){return Err("player B contract team does not match current team; reload save before swap".into());}
    let (a_begin,_,_,a_entries)=vector(fm,team_a+0x38,2000)?;
    let (b_begin,_,_,b_entries)=vector(fm,team_b+0x38,2000)?;
    let a_hit=a_entries.iter().copied().enumerate().find(|(_,e)|entry_mode(fm,*e,player_a,person_a).is_some()).ok_or("player A missing from source roster")?;
    let b_hit=b_entries.iter().copied().enumerate().find(|(_,e)|entry_mode(fm,*e,player_b,person_b).is_some()).ok_or("player B missing from source roster")?;
    let a_slot=a_begin+a_hit.0 as u64*8; let b_slot=b_begin+b_hit.0 as u64*8;
    let mut rollback_data=Vec::new();
    for (addr,len) in [(a_slot,8usize),(b_slot,8),(player_a+0x130,8),(player_b+0x130,8),(contract_a+0x10,8),(contract_b+0x10,8),(player_a+0x204,4),(player_b+0x204,4)] {
        rollback_data.push((addr,fm.read_bytes(addr,len).map_err(|e|format!("swap snapshot 0x{addr:X}: {e}"))?));
    }
    let write_result=(||->Result<(),String>{
        fm.write_bytes(a_slot,&b_hit.1.to_le_bytes()).map_err(|e|format!("team A roster slot: {e}"))?;
        fm.write_bytes(b_slot,&a_hit.1.to_le_bytes()).map_err(|e|format!("team B roster slot: {e}"))?;
        fm.write_bytes(player_a+0x130,&team_b.to_le_bytes()).map_err(|e|format!("player A team: {e}"))?;
        fm.write_bytes(player_b+0x130,&team_a.to_le_bytes()).map_err(|e|format!("player B team: {e}"))?;
        fm.write_bytes(contract_a+0x10,&team_b.to_le_bytes()).map_err(|e|format!("player A contract team: {e}"))?;
        fm.write_bytes(contract_b+0x10,&team_a.to_le_bytes()).map_err(|e|format!("player B contract team: {e}"))?;
        let rva=schemas.rva_current_date;
        if rva!=0 { if let Ok(today)=fm.read_u32(fm.gp_base+rva){
            let year=(today>>16) as u16; let doy=(today&0x01ff) as u16;
            if (1900..=2200).contains(&year)&&(1..=366).contains(&doy){
                fm.write_bytes(player_a+0x204,&today.to_le_bytes()).map_err(|e|format!("player A transfer date: {e}"))?;
                fm.write_bytes(player_b+0x204,&today.to_le_bytes()).map_err(|e|format!("player B transfer date: {e}"))?;
            }
        }}
        Ok(())
    })();
    if let Err(e)=write_result{rollback(fm,&rollback_data);return Err(format!("swap write failed; rollback attempted: {e}"));}
    let verify=(||->Result<(),String>{
        if fm.read_u64(player_a+0x130).ok()!=Some(team_b)||fm.read_u64(contract_a+0x10).ok()!=Some(team_b){return Err("player A ownership read-back mismatch".into());}
        if fm.read_u64(player_b+0x130).ok()!=Some(team_a)||fm.read_u64(contract_b+0x10).ok()!=Some(team_a){return Err("player B ownership read-back mismatch".into());}
        let (_,_,_,a_after)=vector(fm,team_a+0x38,2000)?; let (_,_,_,b_after)=vector(fm,team_b+0x38,2000)?;
        if !a_after.iter().copied().any(|e|entry_mode(fm,e,player_b,person_b).is_some()){return Err("team A does not contain player B after swap".into());}
        if !b_after.iter().copied().any(|e|entry_mode(fm,e,player_a,person_a).is_some()){return Err("team B does not contain player A after swap".into());}
        Ok(())
    })();
    if let Err(e)=verify{rollback(fm,&rollback_data);return Err(format!("swap read-back failed; rollback attempted: {e}"));}
    Ok(SwapPlayersReport{player_a_addr:player_a,player_b_addr:player_b,team_a_before:team_a,team_b_before:team_b})
}

'''
    t=t[:idx]+fn+t[idx:]
wr(p,t)

p='src/bridge/worker.rs'; t=rd(p)
if 'BridgeCmd::SwapPlayers' not in t:
    marker='            BridgeCmd::ForceBuy { player_addr, person_shift, contract_addr, target_club_addr, fee } => {'
    idx=t.find(marker)
    if idx<0: raise SystemExit('v8.1 worker force marker missing')
    arm=r'''            BridgeCmd::SwapPlayers { player_a_addr, person_a_shift, contract_a_addr, player_b_addr, player_b_index } => {
                let result=match &fm {
                    Some(f)=>match crate::player::read_player_at(f,player_b_addr,player_b_index){
                        Ok(b)=>match b.contract_addr {
                            Some(contract_b)=>force_transfer::swap_players(f,player_a_addr,person_a_shift,contract_a_addr,player_b_addr,b.person_shift,contract_b),
                            None=>Err("selected swap target has no mapped contract".into()),
                        },
                        Err(e)=>Err(format!("could not load swap target: {e}")),
                    },
                    None=>Err("Cannot swap players: no process attached".into()),
                };
                match result {
                    Ok(report)=>{let _=tx.send(BridgeResult::SwapPlayersOk(report));}
                    Err(error)=>{let _=tx.send(BridgeResult::SwapPlayersFail{player_addr:player_a_addr,error});}
                }
            }

'''
    t=t[:idx]+arm+t[idx:]
wr(p,t)

# -----------------------------------------------------------------------------
# Navigation: staff links from Club > Staff.
# -----------------------------------------------------------------------------
p='src/ui/navigation.rs'; t=rd(p)
if 'pub struct StaffTarget' not in t:
    marker='#[derive(Clone, Debug, PartialEq, Eq)]\npub struct ClubTarget'
    idx=t.find(marker)
    if idx<0: raise SystemExit('v8.1 staff target marker missing')
    defs='''#[derive(Clone, Debug, PartialEq, Eq)]\npub struct StaffTarget {\n    pub addr: u64,\n    pub index: usize,\n    pub name: String,\n}\n\n'''
    t=t[:idx]+defs+t[idx:]
if 'pub fn request_staff_target' not in t:
    marker='pub fn take_club_target(ctx: &egui::Context) -> Option<ClubTarget> {'
    idx=t.find(marker)
    if idx<0: raise SystemExit('v8.1 staff navigation marker missing')
    funcs='''pub fn request_staff_target(ui: &egui::Ui, addr: u64, index: usize, name: String) {\n    ui.ctx().data_mut(|d| d.insert_temp(egui::Id::new("open_related_staff"), StaffTarget { addr, index, name }));\n}\n\npub fn take_staff_target(ctx: &egui::Context) -> Option<StaffTarget> {\n    ctx.data_mut(|d| {\n        let id=egui::Id::new("open_related_staff");\n        let target=d.get_temp::<StaffTarget>(id);\n        d.remove::<StaffTarget>(id);\n        target\n    })\n}\n\n'''
    t=t[:idx]+funcs+t[idx:]
wr(p,t)


print("Element v8.1a swap/navigation applied.")
