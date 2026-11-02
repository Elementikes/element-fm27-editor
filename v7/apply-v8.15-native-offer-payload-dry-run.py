from pathlib import Path

root=Path.cwd()

def rd(path):
    p=root/path
    if not p.exists(): raise SystemExit(f"v8.15 missing {path}")
    return p.read_text(encoding="utf-8")

def wr(path,text): (root/path).write_text(text,encoding="utf-8")

def one(text,old,new,label):
    if old not in text: raise SystemExit(f"v8.15 marker missing: {label}")
    return text.replace(old,new,1)

# -----------------------------------------------------------------------------
# Carry the complete dry-run selection from UI -> bridge -> injected helper.
# This remains read-only: no FM action or memory write is performed.
# -----------------------------------------------------------------------------
p='src/bridge/cmd.rs'; t=rd(p)
t=one(t,
    '    ProbeNativeOfferInterop { player_index: usize, club_index: usize },\n',
    '    ProbeNativeOfferInterop { player_index: usize, club_index: usize, player_addr: u64, contract_addr: u64, target_club_addr: u64, target_club_uid: u32, fee: u32 },\n',
    'bridge command payload')
wr(p,t)

p='src/bridge/worker.rs'; t=rd(p)
t=one(t,
'''            BridgeCmd::ProbeNativeOfferInterop { player_index, club_index } => {
                let result=match &fm {Some(f)=>native_offer_probe::probe(f.pid,player_index,club_index),None=>Err("Cannot probe native offer interop: no process attached".into())};
''',
'''            BridgeCmd::ProbeNativeOfferInterop { player_index, club_index, player_addr, contract_addr, target_club_addr, target_club_uid, fee } => {
                let result=match &fm {Some(f)=>native_offer_probe::probe(f.pid,player_index,club_index,player_addr,contract_addr,target_club_addr,target_club_uid,fee),None=>Err("Cannot probe native offer interop: no process attached".into())};
''',
    'worker payload')
wr(p,t)

p='src/bridge/native_offer_probe.rs'; t=rd(p)
t=one(t,
    '    pub fn probe(pid:u32,player_index:usize,club_index:usize)->Result<String,String>{unsafe{\n',
    '    pub fn probe(pid:u32,player_index:usize,club_index:usize,player_addr:u64,contract_addr:u64,target_club_addr:u64,target_club_uid:u32,fee:u32)->Result<String,String>{unsafe{\n',
    'probe signature')
t=one(t,
'''        std::fs::write(&request,format!("player_index={player_index}\\nclub_index={club_index}\\n"))
            .map_err(|e|format!("write native offer certifier request: {e}"))?;
''',
'''        std::fs::write(&request,format!("player_index={player_index}\\nclub_index={club_index}\\nplayer_addr={player_addr}\\ncontract_addr={contract_addr}\\ntarget_club_addr={target_club_addr}\\ntarget_club_uid={target_club_uid}\\nfee={fee}\\n"))
            .map_err(|e|format!("write native offer dry-run request: {e}"))?;
''',
    'request payload')
t=one(t,
    '#[cfg(windows)] pub fn probe(pid:u32,player_index:usize,club_index:usize)->Result<String,String>{imp::probe(pid,player_index,club_index)}\n',
    '#[cfg(windows)] pub fn probe(pid:u32,player_index:usize,club_index:usize,player_addr:u64,contract_addr:u64,target_club_addr:u64,target_club_uid:u32,fee:u32)->Result<String,String>{imp::probe(pid,player_index,club_index,player_addr,contract_addr,target_club_addr,target_club_uid,fee)}\n',
    'windows wrapper')
t=one(t,
    '#[cfg(not(windows))] pub fn probe(_pid:u32,_player_index:usize,_club_index:usize)->Result<String,String>{Err("Native offer IL2CPP probe is Windows-only in this build".into())}\n',
    '#[cfg(not(windows))] pub fn probe(_pid:u32,_player_index:usize,_club_index:usize,_player_addr:u64,_contract_addr:u64,_target_club_addr:u64,_target_club_uid:u32,_fee:u32)->Result<String,String>{Err("Native offer IL2CPP probe is Windows-only in this build".into())}\n',
    'nonwindows wrapper')
t=t.replace('ElementFM27-native-offer-probe-v8.14.1.txt','ElementFM27-native-offer-probe-v8.15.txt')
t=t.replace('ElementFM27-native-offer-probe-progress-v8.14.1.txt','ElementFM27-native-offer-probe-progress-v8.15.txt')
wr(p,t)

# UI: reuse the already-selected AI club and the existing fee control.
p='src/ui/player_panel.rs'; t=rd(p)
t=t.replace('Native Offer Type + Context Semantic Map • v8.14.1','Native Offer Payload Dry Run • v8.15')
t=t.replace('MAP PROPERTY TYPES + CONTEXTS • SAFE','BUILD NATIVE OFFER PAYLOAD • DRY RUN')
t=t.replace('📋 FULL NATIVE OFFER TYPE / CONTEXT MAP • v8.14.1','📋 FULL NATIVE OFFER PAYLOAD DRY RUN • v8.15')
old='d.insert_temp(egui::Id::new("element_v84_native_offer_probe"),(player.index,target.index))'
new='d.insert_temp(egui::Id::new("element_v84_native_offer_probe"),(player.index,target.index,player.addr,player.contract_addr.unwrap_or(0),target.addr,target.uid,fee))'
t=one(t,old,new,'UI dry-run tuple')
t=t.replace('Constructs FM27 PersonReference(index) and ClubReference(index) for the exact current selection, then reads identity/index back. No transfer action is dispatched.','Builds a read-only native offer payload plan from the selected player, AI club and fee. Resolves source/target senior-team pointers and certifies PersonReference/TeamReference semantics. No transfer action is dispatched.')
wr(p,t)

# App: consume the expanded tuple and bridge it unchanged.
p='src/app.rs'; t=rd(p)
old='''        if let Some((player_index,club_index))=ctx.data_mut(|d|{let id=egui::Id::new("element_v84_native_offer_probe");let v=d.get_temp::<(usize,usize)>(id);d.remove::<(usize,usize)>(id);v}) {
            if self.conn.is_attached(){self.bridge.send(BridgeCmd::ProbeNativeOfferInterop{player_index,club_index});self.set_status(format!("Certifying FM27 PersonReference({player_index}) + ClubReference({club_index})…"));}
        }
'''
new='''        if let Some((player_index,club_index,player_addr,contract_addr,target_club_addr,target_club_uid,fee))=ctx.data_mut(|d|{let id=egui::Id::new("element_v84_native_offer_probe");let v=d.get_temp::<(usize,usize,u64,u64,u64,u32,u32)>(id);d.remove::<(usize,usize,u64,u64,u64,u32,u32)>(id);v}) {
            if self.conn.is_attached(){self.bridge.send(BridgeCmd::ProbeNativeOfferInterop{player_index,club_index,player_addr,contract_addr,target_club_addr,target_club_uid,fee});self.set_status(format!("Dry-running FM27 native offer payload • player {player_index} • club {club_index} • fee £{fee}"));}
        }
'''
t=one(t,old,new,'app dry-run tuple')
wr(p,t)

# -----------------------------------------------------------------------------
# Injected helper: certify the semantic reference IDs and bridge selected Club
# objects to their live senior Team objects. All raw reads are VirtualQuery-
# guarded. No managed action dispatcher and no memory write are called.
# -----------------------------------------------------------------------------
helper=Path(__file__).with_name('native_offer_helper.rs')
t=helper.read_text(encoding='utf-8')

t=t.replace('ElementFM27-native-offer-probe-v8.14.1.txt','ElementFM27-native-offer-probe-v8.15.txt')
t=t.replace('ElementFM27-native-offer-probe-progress-v8.14.1.txt','ElementFM27-native-offer-probe-progress-v8.15.txt')

if 'struct V815Request' not in t:
    marker='unsafe fn run_probe() -> Result<String, String> {'
    insert=r'''
#[derive(Clone,Copy,Debug)]
struct V815Request {
    player_index:i32,
    club_index:i32,
    player_addr:u64,
    contract_addr:u64,
    target_club_addr:u64,
    target_club_uid:u32,
    fee:u32,
}

fn v815_read_request()->Result<V815Request,String>{
    let text=fs::read_to_string(certifier_request_path()).map_err(|e|format!("read v8.15 request: {e}"))?;
    let mut pidx=None;let mut cidx=None;let mut pa=None;let mut ca=None;let mut tc=None;let mut uid=None;let mut fee=None;
    for line in text.lines(){
        let Some((k,v))=line.split_once('=') else {continue};
        match k.trim(){
            "player_index"=>pidx=v.trim().parse::<i32>().ok(),
            "club_index"=>cidx=v.trim().parse::<i32>().ok(),
            "player_addr"=>pa=v.trim().parse::<u64>().ok(),
            "contract_addr"=>ca=v.trim().parse::<u64>().ok(),
            "target_club_addr"=>tc=v.trim().parse::<u64>().ok(),
            "target_club_uid"=>uid=v.trim().parse::<u32>().ok(),
            "fee"=>fee=v.trim().parse::<u32>().ok(),
            _=>{}
        }
    }
    match (pidx,cidx,pa,ca,tc,uid,fee){
        (Some(player_index),Some(club_index),Some(player_addr),Some(contract_addr),Some(target_club_addr),Some(target_club_uid),Some(fee))
            if player_index>=0 && club_index>=0 && player_addr!=0 && target_club_addr!=0 =>
            Ok(V815Request{player_index,club_index,player_addr,contract_addr,target_club_addr,target_club_uid,fee}),
        _=>Err("v8.15 request missing player/club indexes, addresses, uid or fee".into())
    }
}

unsafe fn v815_read_bytes(addr:u64,len:usize)->Option<Vec<u8>>{
    if addr<0x10000 || len==0{return None;}
    let p=addr as *const u8;
    let n=v810_memory_readable(p,len)?;
    if n<len{return None;}
    Some(std::slice::from_raw_parts(p,len).to_vec())
}
unsafe fn v815_u64(addr:u64)->Option<u64>{
    let b=v815_read_bytes(addr,8)?;Some(u64::from_le_bytes(b.try_into().ok()?))
}
unsafe fn v815_u32(addr:u64)->Option<u32>{
    let b=v815_read_bytes(addr,4)?;Some(u32::from_le_bytes(b.try_into().ok()?))
}
unsafe fn v815_u8(addr:u64)->Option<u8>{v815_read_bytes(addr,1).and_then(|b|b.first().copied())}
fn v815_ptr_ok(p:u64)->bool{(0x10000..0x0000_8000_0000_0000).contains(&p)}

unsafe fn v815_find_senior_team(club:u64)->Result<(u64,usize),String>{
    let header=club.checked_add(0x18).ok_or_else(||"club team-vector overflow".to_string())?;
    let begin=v815_u64(header).ok_or_else(||"club team-vector begin unreadable".to_string())?;
    let end=v815_u64(header+8).ok_or_else(||"club team-vector end unreadable".to_string())?;
    let cap=v815_u64(header+16).ok_or_else(||"club team-vector cap unreadable".to_string())?;
    if !v815_ptr_ok(begin)||!v815_ptr_ok(end)||!v815_ptr_ok(cap)||begin>end||end>cap||(end-begin)%8!=0{return Err("club team-vector header failed structural guard".into());}
    let count=((end-begin)/8) as usize;if count==0||count>128{return Err(format!("club team-vector count implausible: {count}"));}
    let mut fallback=None;
    for i in 0..count{
        let team=v815_u64(begin+i as u64*8).unwrap_or(0);if !v815_ptr_ok(team){continue;}
        if v815_u64(team+0x30)!=Some(club){continue;}
        let kind=v815_u8(team+0x28).unwrap_or(255);
        if kind==0{return Ok((team,i));}
        if fallback.is_none(){fallback=Some((team,i));}
    }
    fallback.ok_or_else(||"no readable team object with club back-pointer".into())
}

unsafe fn v815_reference_id(
    class_name:&str,
    assemblies:*mut *const c_void,count:usize,
    assembly_get_image:AssemblyGetImage,class_from_name:ClassFromName,class_get_method:ClassGetMethodFromName,
    runtime_invoke:RuntimeInvoke,object_unbox:ObjectUnbox,
)->Option<u32>{
    let class=find_class(assemblies,count,assembly_get_image,class_from_name,"FM.UI",class_name)?;
    let n=CString::new("get_Identifier").ok()?;let m=class_get_method(class,n.as_ptr(),0);if m.is_null(){return None;}
    let mut exc:*mut c_void=null_mut();let obj=runtime_invoke(m,null_mut(),null_mut(),&mut exc);if !exc.is_null()||obj.is_null(){return None;}
    let raw=object_unbox(obj);if raw.is_null(){return None;}Some(std::ptr::read_unaligned(raw as *const u32))
}

unsafe fn v815_team_header(label:&str,team:u64,club_hint:i32,uid_hint:u32)->Vec<String>{
    let mut out=Vec::new();
    out.push(format!("{label}: team_addr=0x{team:X} kind={:?} club_backptr={}",v815_u8(team+0x28),v815_u64(team+0x30).map(|v|format!("0x{v:X}")).unwrap_or_else(||"<unreadable>".into())));
    if let Some(raw)=v815_read_bytes(team,0x80){
        out.push(format!("{label}: HEADER_0x80={}",raw.iter().map(|b|format!("{b:02X}")).collect::<Vec<_>>().join(" ")));
        let mut candidates=Vec::new();
        for off in (0..=0x7C).step_by(4){
            let v=u32::from_le_bytes(raw[off..off+4].try_into().unwrap());
            if (v>0 && v<2_000_000) || v==club_hint as u32 || v==uid_hint{
                candidates.push(format!("+0x{off:02X}=0x{v:08X}({v}){}{}",if v==club_hint as u32{" [CLUB_INDEX_HINT]"}else{""},if v==uid_hint{" [CLUB_UID_HINT]"}else{""}));
            }
        }
        if candidates.is_empty(){out.push(format!("{label}: INDEX_CANDIDATES=<none in first 0x80>"));}
        else{out.push(format!("{label}: INDEX_CANDIDATES {}",candidates.join(" | ")));}
    }else{out.push(format!("{label}: HEADER_0x80=<unreadable>"));}
    out
}
'''
    if marker not in t: raise SystemExit('v8.15 helper run marker missing')
    t=t.replace(marker,insert+marker,1)

if '=== NATIVE OFFER PAYLOAD DRY RUN v8.15 ===' not in t:
    gate='                lines.push("V8.14 GATE: correlate BindingKind names and GetContextsInternal immediate candidates for pers/TObt/TOst. Only certified reference contexts may enter the dry-run native offer payload builder.".to_string());\n'
    if gate not in t: raise SystemExit('v8.15 v8.14 gate marker missing')
    block=r'''                lines.push("\n=== NATIVE OFFER PAYLOAD DRY RUN v8.15 ===".to_string());
                lines.push("READ-ONLY: captures selected player/club/fee, resolves live source + target senior Team objects, and certifies PersonReference/TeamReference identifiers. HandleActionEvent/SendEvent and all memory writes remain LOCKED.".to_string());
                let person_id=v815_reference_id("PersonReference",assemblies,count,assembly_get_image,class_from_name,class_get_method,runtime_invoke,object_unbox);
                let team_id=v815_reference_id("TeamReference",assemblies,count,assembly_get_image,class_from_name,class_get_method,runtime_invoke,object_unbox);
                let club_id=v815_reference_id("ClubReference",assemblies,count,assembly_get_image,class_from_name,class_get_method,runtime_invoke,object_unbox);
                lines.push(format!("SEMANTIC_CERT: pers expected PersonReference=0x44420001 runtime={}",person_id.map(|v|format!("0x{v:08X}")).unwrap_or_else(||"<unavailable>".into())));
                lines.push(format!("SEMANTIC_CERT: TObt/TOst expected TeamReference=0x44420018 runtime={}",team_id.map(|v|format!("0x{v:08X}")).unwrap_or_else(||"<unavailable>".into())));
                lines.push(format!("SEMANTIC_CERT: selected club UI reference remains ClubReference=0x44420003 runtime={}",club_id.map(|v|format!("0x{v:08X}")).unwrap_or_else(||"<unavailable>".into())));
                match v815_read_request(){
                    Ok(r)=>{
                        lines.push(format!("REQUEST: player_index={} club_index={} player_addr=0x{:X} contract_addr=0x{:X} target_club_addr=0x{:X} target_club_uid={} fee={}",r.player_index,r.club_index,r.player_addr,r.contract_addr,r.target_club_addr,r.target_club_uid,r.fee));
                        let source_team=v815_u64(r.player_addr+0x130);
                        let contract_team=if r.contract_addr!=0{v815_u64(r.contract_addr+0x10)}else{None};
                        lines.push(format!("LIVE_POINTERS: source_team={}",source_team.map(|v|format!("0x{v:X}")).unwrap_or_else(||"<unreadable>".into())));
                        lines.push(format!("LIVE_POINTERS: contract_team={}",contract_team.map(|v|format!("0x{v:X}")).unwrap_or_else(||"<unreadable>".into())));
                        lines.push(format!("LIVE_POINTERS: source_team_matches_contract={}",source_team.is_some()&&source_team==contract_team));
                        if let Some(st)=source_team.filter(|v|v815_ptr_ok(*v)){
                            let seller=v815_u64(st+0x30);
                            lines.push(format!("LIVE_POINTERS: seller_club_from_source_team={}",seller.map(|v|format!("0x{v:X}")).unwrap_or_else(||"<unreadable>".into())));
                            lines.extend(v815_team_header("SOURCE_TEAM",st,r.club_index,r.target_club_uid));
                        }
                        match v815_find_senior_team(r.target_club_addr){
                            Ok((tt,slot))=>{
                                lines.push(format!("LIVE_POINTERS: target_senior_team=0x{tt:X} club_team_vector_slot={slot} backptr_match={}",v815_u64(tt+0x30)==Some(r.target_club_addr)));
                                lines.extend(v815_team_header("TARGET_TEAM",tt,r.club_index,r.target_club_uid));
                            },
                            Err(e)=>lines.push(format!("LIVE_POINTERS: target senior team ERROR: {e}")),
                        }
                        lines.push("PAYLOAD_PLAN: pers = PersonReference(player_index) [CERTIFIED CONTEXT]".to_string());
                        lines.push("PAYLOAD_PLAN: TObt / TOst = TeamReference(source/target senior-team DB indexes) [REFERENCE TYPE CERTIFIED; ROLE ORDER + DB INDEX STILL GATED]".to_string());
                        lines.push(format!("PAYLOAD_PLAN: selected fee={} [CAPTURED; binding to exact scalar property still gated]",r.fee));
                        lines.push("PAYLOAD_PLAN: dispatch = LOCKED / NOT CALLED".to_string());
                        lines.extend(certifier_construct_db_ref("TEAM_SAME_INDEX_DIAGNOSTIC","FM.UI","TeamReference",r.club_index,assemblies,count,assembly_get_image,class_from_name,class_get_methods,method_get_name,method_get_param_count,method_get_param,type_get_name,runtime_invoke,object_new,class_get_method,class_get_fields,class_get_parent,field_get_name,field_get_offset,object_get_class,class_get_name,class_get_namespace,class_is_valuetype,object_unbox,string_chars,string_length));
                    },
                    Err(e)=>lines.push(format!("V8.15 REQUEST ERROR: {e}")),
                }
                lines.push("V8.15 GATE: identify exact TeamReference DB indexes for source/target senior-team objects and certify TObt vs TOst role ordering + fee scalar property before any native SEND is enabled.".to_string());
'''
    t=t.replace(gate,gate+block,1)

# Explicit version banner / filenames after the v8.14.1 freshness patch.
t=t.replace('REPORT_BUILD: Element FM27 Native Offer Type + Context Semantic Map v8.14.1.1','REPORT_BUILD: Element FM27 Native Offer Payload Dry Run v8.15')
t=t.replace('REPORT_BUILD: Element FM27 Native Offer Type + Context Semantic Map v8.14.1','REPORT_BUILD: Element FM27 Native Offer Payload Dry Run v8.15')
t=t.replace('Native Offer Type + Context Semantic Map v8.14.1','Native Offer Payload Dry Run v8.15')
helper.write_text(t,encoding='utf-8')

print('Element v8.15 Native Offer Payload Dry Run applied — semantic refs + club→senior-team bridge, zero dispatch.')
