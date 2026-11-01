from pathlib import Path

root=Path.cwd()
def rd(path):
    p=root/path
    if not p.exists(): raise SystemExit(f"v8.4 missing {path}")
    return p.read_text(encoding="utf-8")
def wr(path,text): (root/path).write_text(text,encoding="utf-8")
def one(text,old,new,label):
    if old not in text: raise SystemExit(f"v8.4 marker missing: {label}")
    return text.replace(old,new,1)

# -----------------------------------------------------------------------------
# Read every relation record, not only the two families already named by FM27.
# Unknown records retain their raw target and kind/type/reason so the UI can
# resolve them against live club/player/staff caches and use them as templates.
# -----------------------------------------------------------------------------
p='src/player.rs';t=rd(p)
old='''        let name_offset = if kind == l.kind_club && relation_type == l.type_favoured_club {
            l.club_name
        } else if kind == l.kind_nation && relation_type == l.type_other_nationality {
            l.nation_name
        } else {
            continue;
        };
        let target = le_u64(entry, l.relation_target)?;
        let name = name_at(read, target, name_offset)?;
'''
if old in t:
    new='''        let target = le_u64(entry, l.relation_target)?;
        let name = if kind == l.kind_club && relation_type == l.type_favoured_club {
            name_at(read, target, l.club_name).unwrap_or_else(|| format!("Club @ 0x{target:X}"))
        } else if kind == l.kind_nation && relation_type == l.type_other_nationality {
            name_at(read, target, l.nation_name).unwrap_or_else(|| format!("Nation @ 0x{target:X}"))
        } else {
            // v8.4: preserve unknown-but-structurally-valid records. The live UI
            // resolves target pointers against EntityCache where possible.
            format!("Target @ 0x{target:X}")
        };
'''
    t=t.replace(old,new,1)
wr(p,t)

# -----------------------------------------------------------------------------
# Bridge command/result additions.
# -----------------------------------------------------------------------------
p='src/bridge/cmd.rs';t=rd(p)
if 'ClonePlayerRelation {' not in t:
    t=one(t,
        '    RemovePlayerRelation { player_addr: u64, person_shift: usize, relation_addr: u64 },\n',
        '    RemovePlayerRelation { player_addr: u64, person_shift: usize, relation_addr: u64 },\n'
        '    ClonePlayerRelation { player_addr: u64, person_shift: usize, template_relation_addr: u64, target_addr: u64, strength: Option<u8> },\n'
        '    ProbeNativeOfferInterop,\n',
        'bridge commands')
if 'NativeOfferProbeOk' not in t:
    t=one(t,
        '    RelationMutationFail { player_addr: u64, error: String },\n',
        '    RelationMutationFail { player_addr: u64, error: String },\n'
        '    NativeOfferProbeOk { report: String },\n'
        '    NativeOfferProbeFail { error: String },\n',
        'bridge results')
wr(p,t)

# -----------------------------------------------------------------------------
# Generic relation template clone. No relation enum values are invented: the
# full 16-byte FM record is copied and only target (+ optional strength) change.
# -----------------------------------------------------------------------------
p='src/bridge/force_transfer.rs';t=rd(p)
if 'pub(super) fn clone_player_relation(' not in t:
    marker='pub(super) fn remove_player_relation('
    idx=t.find(marker)
    if idx<0: raise SystemExit('v8.4 clone relation insertion marker missing')
    fn=r'''pub(super) fn clone_player_relation(
    fm:&FmProcess,
    player_addr:u64,
    person_shift:usize,
    template_relation_addr:u64,
    target_addr:u64,
    strength:Option<u8>,
)->Result<RelationMutationReport,String>{
    verified_build(fm)?;
    if !ptr_ok(target_addr){return Err("target relationship pointer failed plausibility checks".into());}
    let layout=fm.schemas().player_lists.ok_or_else(||"FM27 relationship layout unavailable".to_owned())?;
    let (_object,header,begin,end,cap)=relation_vector_bounds(fm,player_addr,person_shift)?;
    let stride=layout.relation_size as u64;
    if template_relation_addr<begin || template_relation_addr>=end || (template_relation_addr-begin)%stride!=0 {
        return Err("selected relationship is not an aligned member of this player's live vector".into());
    }
    if end.checked_add(stride).map_or(true,|v|v>cap){
        return Err("relationship vector has no spare capacity; Element will not allocate inside FM".into());
    }
    let template=fm.read_bytes(template_relation_addr,layout.relation_size)
        .map_err(|e|format!("relationship template snapshot: {e}"))?;
    let kind=*template.get(layout.relation_kind).ok_or_else(||"template kind offset invalid".to_owned())?;
    let relation_type=*template.get(layout.relation_type).ok_or_else(||"template type offset invalid".to_owned())?;
    // Reject exact duplicates of same relation family + target.
    let count=((end-begin)/stride) as usize;
    for i in 0..count{
        let a=begin+i as u64*stride;
        let raw=fm.read_bytes(a,layout.relation_size).map_err(|e|format!("relationship duplicate scan: {e}"))?;
        let p=u64::from_le_bytes(raw[layout.relation_target..layout.relation_target+8].try_into().unwrap());
        if p==target_addr && raw[layout.relation_kind]==kind && raw[layout.relation_type]==relation_type{
            return Err("an identical relationship type already targets this object".into());
        }
    }
    let old_slot=fm.read_bytes(end,layout.relation_size).map_err(|e|format!("relationship spare slot snapshot: {e}"))?;
    let old_end=fm.read_bytes(header+8,8).map_err(|e|format!("relationship end snapshot: {e}"))?;
    let mut new=template.clone();
    new[layout.relation_target..layout.relation_target+8].copy_from_slice(&target_addr.to_le_bytes());
    if let Some(v)=strength { new[layout.relation_strength]=v.min(100); }
    let rollback_data=vec![(end,old_slot),(header+8,old_end)];
    let write=(||->Result<(),String>{
        fm.write_bytes(end,&new).map_err(|e|format!("clone relationship record: {e}"))?;
        fm.write_bytes(header+8,&(end+stride).to_le_bytes()).map_err(|e|format!("advance relationship vector end: {e}"))?;
        Ok(())
    })();
    if let Err(e)=write{rollback(fm,&rollback_data);return Err(format!("relationship clone write failed; rollback attempted: {e}"));}
    let verify=fm.read_bytes(end,layout.relation_size).map_err(|e|format!("relationship clone read-back: {e}"))?;
    let verify_target=u64::from_le_bytes(verify[layout.relation_target..layout.relation_target+8].try_into().unwrap());
    if verify_target!=target_addr || fm.read_u64(header+8).ok()!=Some(end+stride) || verify[layout.relation_kind]!=kind || verify[layout.relation_type]!=relation_type {
        rollback(fm,&rollback_data);
        return Err("relationship clone read-back mismatch; rollback attempted".into());
    }
    Ok(RelationMutationReport{player_addr,relation_addr:end,target_addr,action:format!("Cloned relation kind {kind} / type {relation_type}")})
}

'''
    t=t[:idx]+fn+t[idx:]
wr(p,t)

# -----------------------------------------------------------------------------
# Native offer live probe. On Windows this injects the staged helper DLL into
# fm.exe. The helper resolves IL2CPP by exported API and reports the exact live
# HandleActionEvent signature; no game action is invoked by the probe.
# -----------------------------------------------------------------------------
p='src/bridge/native_offer_probe.rs'
wr(p,r'''#[cfg(windows)]
mod imp {
    use std::{ffi::c_void, path::Path, time::{Duration,Instant}};
    use windows::core::PCWSTR;
    use windows::Win32::Foundation::{CloseHandle,HANDLE};
    use windows::Win32::System::Diagnostics::Debug::WriteProcessMemory;
    use windows::Win32::System::Memory::{VirtualAllocEx,VirtualFreeEx,MEM_COMMIT,MEM_RELEASE,MEM_RESERVE,PAGE_READWRITE};
    use windows::Win32::System::Threading::{CreateRemoteThread,OpenProcess,WaitForSingleObject,PROCESS_ALL_ACCESS};
    use windows::Win32::System::Diagnostics::ToolHelp::{CreateToolhelp32Snapshot,Module32FirstW,Module32NextW,MODULEENTRY32W,TH32CS_SNAPMODULE,TH32CS_SNAPMODULE32};

    fn wide(s:&std::ffi::OsStr)->Vec<u16>{use std::os::windows::ffi::OsStrExt;s.encode_wide().chain(Some(0)).collect()}
    fn module_base(pid:u32,name:&str)->Result<u64,String>{unsafe{
        let snap=CreateToolhelp32Snapshot(TH32CS_SNAPMODULE|TH32CS_SNAPMODULE32,pid).map_err(|e|format!("module snapshot: {e}"))?;
        let mut e=MODULEENTRY32W{dwSize:std::mem::size_of::<MODULEENTRY32W>() as u32,..Default::default()};
        let mut found=None;
        if Module32FirstW(snap,&mut e).is_ok(){loop{
            let n=String::from_utf16_lossy(&e.szModule[..e.szModule.iter().position(|&c|c==0).unwrap_or(e.szModule.len())]);
            if n.eq_ignore_ascii_case(name){found=Some(e.modBaseAddr as u64);break;}
            if Module32NextW(snap,&mut e).is_err(){break;}
        }}
        let _=CloseHandle(snap);found.ok_or_else(||format!("{name} not loaded in FM"))
    }}
    pub fn probe(pid:u32)->Result<String,String>{unsafe{
        let exe=std::env::current_exe().map_err(|e|format!("current exe: {e}"))?;
        let dll=exe.parent().unwrap_or(Path::new(".")).join("Element-FM27-NativeOffer.dll");
        if !dll.exists(){return Err(format!("native offer helper missing: {}",dll.display()));}
        let report=std::env::temp_dir().join("ElementFM27-native-offer-probe.txt");let _=std::fs::remove_file(&report);
        let h=OpenProcess(PROCESS_ALL_ACCESS,false,pid).map_err(|e|format!("OpenProcess for native probe: {e}"))?;
        let w=wide(dll.as_os_str());let bytes=w.len()*2;
        let remote=VirtualAllocEx(h,None,bytes,MEM_COMMIT|MEM_RESERVE,PAGE_READWRITE);
        if remote.is_null(){let _=CloseHandle(h);return Err("VirtualAllocEx failed".into());}
        let mut written=0usize;WriteProcessMemory(h,remote,w.as_ptr() as *const c_void,bytes,Some(&mut written)).map_err(|e|format!("write helper path: {e}"))?;
        if written!=bytes{let _=VirtualFreeEx(h,remote,0,MEM_RELEASE);let _=CloseHandle(h);return Err("short helper-path write".into());}
        // kernel32 is mapped at a system-wide base for the current boot. Resolve
        // LoadLibraryW locally and translate by module RVA to the FM copy.
        #[link(name="kernel32")]
        unsafe extern "system" { fn GetModuleHandleW(lpModuleName:PCWSTR)->HANDLE; fn GetProcAddress(hModule:HANDLE,lpProcName:*const u8)->*const c_void; }
        let kw:Vec<u16>="kernel32.dll\0".encode_utf16().collect();let local_k=GetModuleHandleW(PCWSTR(kw.as_ptr()));
        if local_k.0.is_null(){return Err("GetModuleHandleW(kernel32) failed".into());}
        let local_load=GetProcAddress(local_k,b"LoadLibraryW\0".as_ptr());if local_load.is_null(){return Err("GetProcAddress(LoadLibraryW) failed".into());}
        let local_base=local_k.0 as u64;let remote_base=module_base(pid,"kernel32.dll")?;let remote_load=remote_base+(local_load as u64-local_base);
        let start:unsafe extern "system" fn(*mut c_void)->u32=std::mem::transmute(remote_load as usize);
        let th=CreateRemoteThread(h,None,0,Some(start),Some(remote),0,None).map_err(|e|format!("CreateRemoteThread(LoadLibraryW): {e}"))?;
        let _=WaitForSingleObject(th,5000);let _=CloseHandle(th);let _=VirtualFreeEx(h,remote,0,MEM_RELEASE);let _=CloseHandle(h);
        let started=Instant::now();while started.elapsed()<Duration::from_secs(5){if let Ok(s)=std::fs::read_to_string(&report){if !s.trim().is_empty(){return Ok(s);}}std::thread::sleep(Duration::from_millis(80));}
        Err("helper loaded but no IL2CPP probe report arrived".into())
    }}
}
#[cfg(windows)] pub fn probe(pid:u32)->Result<String,String>{imp::probe(pid)}
#[cfg(not(windows))] pub fn probe(_pid:u32)->Result<String,String>{Err("Native offer IL2CPP probe is Windows-only in this build".into())}
''')

p='src/bridge/mod.rs';t=rd(p)
if 'mod native_offer_probe;' not in t:
    t=one(t,'mod force_transfer;\n','mod force_transfer;\nmod native_offer_probe;\n','native offer module')
wr(p,t)

p='src/bridge/worker.rs';t=rd(p)
if 'BridgeCmd::ClonePlayerRelation' not in t:
    marker='            BridgeCmd::ForceBuy { player_addr, person_shift, contract_addr, target_club_addr, fee } => {'
    idx=t.find(marker)
    if idx<0: raise SystemExit('v8.4 worker marker missing')
    arms=r'''            BridgeCmd::ClonePlayerRelation { player_addr, person_shift, template_relation_addr, target_addr, strength } => {
                let result=match &fm {Some(f)=>force_transfer::clone_player_relation(f,player_addr,person_shift,template_relation_addr,target_addr,strength),None=>Err("Cannot clone relationship: no process attached".into())};
                match result {Ok(report)=>{let _=tx.send(BridgeResult::RelationMutationOk(report));}Err(error)=>{let _=tx.send(BridgeResult::RelationMutationFail{player_addr,error});}}
            }
            BridgeCmd::ProbeNativeOfferInterop => {
                let result=match &fm {Some(f)=>native_offer_probe::probe(f.pid),None=>Err("Cannot probe native offer interop: no process attached".into())};
                match result {Ok(report)=>{let _=tx.send(BridgeResult::NativeOfferProbeOk{report});}Err(error)=>{let _=tx.send(BridgeResult::NativeOfferProbeFail{error});}}
            }

'''
    t=t[:idx]+arms+t[idx:]
wr(p,t)

# -----------------------------------------------------------------------------
# Relationships Pro UI and Native Offer Lab button.
# -----------------------------------------------------------------------------
p='src/ui/player_panel.rs';t=rd(p)
t=t.replace('show_relationships_extra_v83(ui,player,entity_cache);','show_relationships_extra_v84(schemas,ui,player,entity_cache);')
if 'fn show_relationships_extra_v84(' not in t:
    start=t.find('fn show_relationships_extra_v83(')
    end=t.find('fn set_player_u32_v83(',start)
    if start<0 or end<0: raise SystemExit('v8.4 relationship manager function markers missing')
    funcs=r'''fn relation_target_v84(schemas:&'static fields::VersionedSchemas,cache:Option<&crate::cache::EntityCache>,target:u64)->(String,&'static str){
    let Some(c)=cache else{return(format!("0x{target:X}"),"Unknown")};
    if let Some(club)=c.clubs.iter().find(|x|x.addr==target){return(club.name.clone(),"Club")}
    if let Some(p)=c.players.iter().find(|x|x.addr+schemas.player_person_offset as u64+x.person_shift as u64==target){return(p.name.clone(),"Player")}
    if let Some(s)=c.staff.iter().find(|x|x.addr+0x100+x.identity_shift as u64==target){return(s.name.clone(),"Staff")}
    (format!("0x{target:X}"),"Unknown")
}

fn select_person_target_v84(ui:&mut egui::Ui,schemas:&'static fields::VersionedSchemas,player:&PlayerRecord,cache:Option<&crate::cache::EntityCache>)->Option<(u64,String)>{
    let cache=cache?;let qid=egui::Id::new(("v84_person_q",player.addr));let sid=egui::Id::new(("v84_person_target",player.addr));
    let mut q=ui.ctx().data(|d|d.get_temp::<String>(qid).unwrap_or_default());let selected=ui.ctx().data(|d|d.get_temp::<u64>(sid));
    ui.horizontal(|ui|{ui.label("Person:");if ui.add_sized([320.0,22.0],egui::TextEdit::singleline(&mut q).hint_text("Search player or staff…")).changed(){ui.ctx().data_mut(|d|d.insert_temp(qid,q.clone()));}});
    if q.trim().len()>=2{let n=q.to_lowercase();let mut shown=0usize;
        for p in cache.players.iter().filter(|x|x.addr!=player.addr&&x.name.to_lowercase().contains(&n)){
            let ptr=p.addr+schemas.player_person_offset as u64+p.person_shift as u64;if ui.selectable_label(selected==Some(ptr),format!("P • {} • UID {}",p.name,p.uid)).clicked(){ui.ctx().data_mut(|d|d.insert_temp(sid,ptr));q.clear();ui.ctx().data_mut(|d|d.insert_temp(qid,String::new()));}shown+=1;if shown>=12{break;}
        }
        if shown<18{for s in cache.staff.iter().filter(|x|x.name.to_lowercase().contains(&n)){
            let ptr=s.addr+0x100+s.identity_shift as u64;if ui.selectable_label(selected==Some(ptr),format!("S • {} • UID {}",s.name,s.uid)).clicked(){ui.ctx().data_mut(|d|d.insert_temp(sid,ptr));q.clear();ui.ctx().data_mut(|d|d.insert_temp(qid,String::new()));}shown+=1;if shown>=18{break;}
        }}
    }
    let ptr=ui.ctx().data(|d|d.get_temp::<u64>(sid))?;let (name,_)=relation_target_v84(schemas,Some(cache),ptr);Some((ptr,name))
}

fn show_relationships_extra_v84(schemas:&'static fields::VersionedSchemas,ui:&mut egui::Ui,player:&PlayerRecord,cache:Option<&crate::cache::EntityCache>){
    ui.add_space(10.0);ui.separator();ui.horizontal_wrapped(|ui|{ui.heading("Relationship Manager Pro");ui.label(egui::RichText::new("ELEMENT v8.4 • FMRTE-STYLE TEMPLATE ENGINE").strong().color(egui::Color32::from_rgb(96,178,255)));});
    ui.label(egui::RichText::new("All structurally valid 16-byte relation records are now visible. Known mappings stay friendly; unknown families expose kind/type/reason bytes. Clone copies the exact native template and only changes the target (and optionally Value), so Element never invents an unknown relation code.").weak());
    let Some(layout)=schemas.player_lists else{return;};
    let selected=ui.ctx().data(|d|d.get_temp::<u64>(egui::Id::new(("element_relationship_selected",player.addr))));
    let template=match &player.relations{crate::player::ListState::Items(items)=>selected.and_then(|a|items.iter().find(|r|r.addr==a)),_=>None};
    if let Some(r)=template{
        let (target_name,target_family)=relation_target_v84(schemas,cache,r.target_addr);
        egui::Frame::group(ui.style()).inner_margin(8.0).show(ui,|ui|{
            ui.strong("Selected native template");
            ui.label(format!("Target: {target_name} • {target_family}"));
            ui.label(format!("kind={} • type={} • reason={} • value={} • record=0x{:X}",r.kind,r.relation_type,r.reason,r.strength,r.addr));
            if r.kind==layout.kind_club&&r.relation_type==layout.type_favoured_club{ui.label("Certified semantic: Likes Team / Favoured Club");}
            else if r.kind==layout.kind_nation&&r.relation_type==layout.type_other_nationality{ui.label("Certified semantic: Other Nationality");}
            else{ui.label(egui::RichText::new("Semantic name not guessed — raw FM code preserved.").weak());}
        });
        let preserve_id=egui::Id::new(("v84_preserve_relation_value",player.addr));let mut preserve=ui.ctx().data(|d|d.get_temp::<bool>(preserve_id).unwrap_or(true));
        ui.checkbox(&mut preserve,"Preserve template Value byte");ui.ctx().data_mut(|d|d.insert_temp(preserve_id,preserve));
        let val_id=egui::Id::new(("v84_clone_relation_value",player.addr));let mut value=ui.ctx().data(|d|d.get_temp::<u8>(val_id).unwrap_or(r.strength.min(100)));if !preserve{ui.horizontal(|ui|{ui.label("New Value");ui.add(egui::Slider::new(&mut value,0..=100));});}ui.ctx().data_mut(|d|d.insert_temp(val_id,value));
        let mut target:Option<(u64,String)>=None;
        if target_family=="Club" || (r.kind==layout.kind_club){if let Some(c)=select_cached_club_v83(ui,player,cache,"v84_clone_club"){target=Some((c.addr,c.name.clone()));}}
        else if target_family=="Player"||target_family=="Staff"{target=select_person_target_v84(ui,schemas,player,cache);}
        else if r.kind==layout.kind_nation{ui.colored_label(egui::Color32::YELLOW,"Nation target: nation entity cache is not available yet, so cloning this family stays locked.");}
        else{ui.colored_label(egui::Color32::YELLOW,"Unknown target family. Select a record whose existing target resolves to Club / Player / Staff before cloning.");}
        if let Some((ptr,name))=target{ui.label(format!("Clone target: {name} • 0x{ptr:X}"));if ui.add_enabled(crate::ui::navigation::editing_enabled(ui),egui::Button::new("⧉ CLONE SELECTED RELATION TYPE → TARGET • LIVE")).clicked(){ui.ctx().data_mut(|d|d.insert_temp(egui::Id::new("element_v84_clone_relation_request"),(player.addr,player.person_shift,r.addr,ptr,if preserve{None}else{Some(value)})));}}
    }else{ui.label("Select any relationship above to inspect/clone its exact native type.");}

    ui.add_space(8.0);ui.strong("Certified direct Add: Likes Team");
    if let Some(club)=select_cached_club_v83(ui,player,cache,"v84_relation_club"){
        let strength_id=egui::Id::new(("v84_relation_strength",player.addr));let reason_id=egui::Id::new(("v84_relation_reason",player.addr));let mut strength=ui.ctx().data(|d|d.get_temp::<u8>(strength_id).unwrap_or(100));let mut reason=ui.ctx().data(|d|d.get_temp::<u8>(reason_id).unwrap_or(1));
        ui.horizontal_wrapped(|ui|{ui.label("Value");ui.add(egui::Slider::new(&mut strength,0..=100));egui::ComboBox::from_id_salt(("v84_reason",player.addr)).selected_text(if reason==2{"As a player"}else{"As a supporter"}).show_ui(ui,|ui|{ui.selectable_value(&mut reason,1,"As a supporter");ui.selectable_value(&mut reason,2,"As a player");});});ui.ctx().data_mut(|d|{d.insert_temp(strength_id,strength);d.insert_temp(reason_id,reason);});
        if ui.add_enabled(crate::ui::navigation::editing_enabled(ui),egui::Button::new("＋ ADD LIKES TEAM • LIVE")).clicked(){ui.ctx().data_mut(|d|d.insert_temp(egui::Id::new("element_v83_add_relation_request"),(player.addr,player.person_shift,club.addr,strength,reason)));}
    }
    if ui.add_enabled(crate::ui::navigation::editing_enabled(ui)&&selected.is_some(),egui::Button::new("− REMOVE SELECTED RELATIONSHIP • LIVE")).clicked(){ui.ctx().data_mut(|d|d.insert_temp(egui::Id::new("element_v83_remove_relation_request"),(player.addr,player.person_shift,selected.unwrap())));}

    ui.add_space(8.0);ui.separator();ui.strong("FMRTE relation catalog discovered");
    ui.label(egui::RichText::new("Preference / rivalry: Likes Person • Dislikes Person • Likes Team • Dislikes Team • Rival • Rival Nation. Identity / eligibility: Other Nationality • Developed at Country • Formed at Club • Formed at Country • Settled Status • Cannot Apply for Work Permit. Registration / career: Competition Registration • Competition Unregistration • Played UEFA Game • Games Played in Division Level • International Retirement • International Withdrawal • Invited to represent nation • Other Nation Caps • Other Nation Youth Caps.").small());
    ui.label(egui::RichText::new("FMRTE reason vocabulary: No Reason • Supporter • Teammate • Friend • Idol • Parent • Child • Sibling • Owner • Chairperson • Backroom Staff • Youth Staff • Player And Manager • Competitive • Historic • Local • Founder • Relationship. Only Supporter/Player codes on Likes Team are numerically certified today; all other reason bytes are preserved by the template engine until witnessed.").small().weak());
}

'''
    t=t[:start]+funcs+t[end:]

# Upgrade native section with probe button but keep direct settlement as fallback.
old='''    ui.add_space(10.0);ui.separator();ui.strong("Native AI proposal research");
    ui.label("FM27 IL2CPP exposes PersonMakeOfferForPlayer, PersonAskIntermediariesToOfferPlayerToClubs, PersonWithdrawPlayerTransferOffer and TransferOffer* objects. FMRTE exposes TransferProposals. Element now gives the same end-result transaction safely; native Inbox proposal injection remains locked until the TransferOffer allocation/ownership chain is witnessed.");
'''
if old in t:
    new='''    ui.add_space(10.0);ui.separator();ui.strong("Native AI Offer Lab • v8.4");
    ui.label("FM27's ActionID table identifies PersonMakeOfferForPlayer (native constant 0x73414278). Element v8.4 probes the live IL2CPP dispatcher instead of hardcoding a method RVA. The probe does NOT move the player or create an offer; it reports the exact runtime argument types needed for the guarded native-send adapter.");
    if ui.button("🧬 PROBE NATIVE OFFER DISPATCHER • SAFE").on_hover_text("Injects the staged Element helper, resolves IL2CPP exports and inspects PluginContextActionsModule.HandleActionEvent. No FM action is invoked.").clicked(){ui.ctx().data_mut(|d|d.insert_temp(egui::Id::new("element_v84_native_offer_probe"),true));}
    ui.label(egui::RichText::new("Direct Settlement remains available above as fallback. Native Inbox SEND stays locked until this live signature is certified on your exact FM27 build.").small().weak());
'''
    t=t.replace(old,new,1)
wr(p,t)

# App result/request handling.
p='src/app.rs';t=rd(p)
if 'BridgeResult::NativeOfferProbeOk' not in t:
    marker='                BridgeResult::RelationMutationOk(report) => {'
    idx=t.find(marker)
    if idx<0: raise SystemExit('v8.4 app result marker missing')
    arms=r'''                BridgeResult::NativeOfferProbeOk { report } => self.set_status(format!("NATIVE OFFER PROBE OK • {}",report.replace('\n'," | "))),
                BridgeResult::NativeOfferProbeFail { error } => self.set_status(format!("Native offer probe failed: {error}")),
'''
    t=t[:idx]+arms+t[idx:]
if 'element_v84_clone_relation_request' not in t:
    marker='        if let Some((player_addr,person_shift,target_club_addr,strength,reason)) = ctx.data_mut(|d| {'
    idx=t.find(marker)
    if idx<0: raise SystemExit('v8.4 app request marker missing')
    block=r'''        if let Some((player_addr,person_shift,template_relation_addr,target_addr,strength)) = ctx.data_mut(|d| {
            let id=egui::Id::new("element_v84_clone_relation_request");let v=d.get_temp::<(u64,usize,u64,u64,Option<u8>)>(id);d.remove::<(u64,usize,u64,u64,Option<u8>)>(id);v
        }) { if self.conn.is_writable(){self.bridge.send(BridgeCmd::ClonePlayerRelation{player_addr,person_shift,template_relation_addr,target_addr,strength});self.set_status("Cloning native relationship template • guarded vector transaction…".into());} }
        if ctx.data_mut(|d|{let id=egui::Id::new("element_v84_native_offer_probe");let v=d.get_temp::<bool>(id).unwrap_or(false);d.remove::<bool>(id);v}) {
            if self.conn.is_attached(){self.bridge.send(BridgeCmd::ProbeNativeOfferInterop);self.set_status("Probing live FM27 native offer dispatcher…".into());}
        }

'''
    t=t[:idx]+block+t[idx:]
wr(p,t)

# Add LibraryLoader feature needed only for Windows native-probe APIs if absent.
p='Cargo.toml';t=rd(p)
if '"Win32_System_LibraryLoader"' not in t:
    t=t.replace('    "Win32_System_Memory",\n','    "Win32_System_Memory",\n    "Win32_System_LibraryLoader",\n',1)
wr(p,t)

print('Element v8.4 Native Offer Probe + Relationships Pro applied.')
