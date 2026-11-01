from pathlib import Path
import re

root=Path.cwd()
def rd(path):
    p=root/path
    if not p.exists(): raise SystemExit(f"v8.7 missing {path}")
    return p.read_text(encoding="utf-8")
def wr(path,text): (root/path).write_text(text,encoding="utf-8")
def one(text,old,new,label):
    if old not in text: raise SystemExit(f"v8.7 marker missing: {label}")
    return text.replace(old,new,1)

# -----------------------------------------------------------------------------
# Bridge request now carries the exact 0-based DB array indexes already held by
# Element's PlayerRecord / CachedClub.  No FM action is dispatched in v8.7.
# -----------------------------------------------------------------------------
p='src/bridge/cmd.rs'; t=rd(p)
t=one(t,'    ProbeNativeOfferInterop,\n','    ProbeNativeOfferInterop { player_index: usize, club_index: usize },\n','probe command indexes')
wr(p,t)

p='src/bridge/worker.rs'; t=rd(p)
t=one(t,
'''            BridgeCmd::ProbeNativeOfferInterop => {
                let result=match &fm {Some(f)=>native_offer_probe::probe(f.pid),None=>Err("Cannot probe native offer interop: no process attached".into())};
''',
'''            BridgeCmd::ProbeNativeOfferInterop { player_index, club_index } => {
                let result=match &fm {Some(f)=>native_offer_probe::probe(f.pid,player_index,club_index),None=>Err("Cannot probe native offer interop: no process attached".into())};
''','worker indexed probe')
wr(p,t)

# The injector writes a tiny request file before loading the helper. This keeps
# the injected DLL generic while allowing it to certify the exact UI selection.
p='src/bridge/native_offer_probe.rs'; t=rd(p)
t=one(t,'    pub fn probe(pid:u32)->Result<String,String>{unsafe{\n','    pub fn probe(pid:u32,player_index:usize,club_index:usize)->Result<String,String>{unsafe{\n','windows probe signature')
needle='''        let report=std::env::temp_dir().join("ElementFM27-native-offer-probe.txt");let _=std::fs::remove_file(&report);
'''
replacement='''        let report=std::env::temp_dir().join("ElementFM27-native-offer-probe.txt");let _=std::fs::remove_file(&report);
        let request=std::env::temp_dir().join("ElementFM27-native-offer-request.txt");
        std::fs::write(&request,format!("player_index={player_index}\\nclub_index={club_index}\\n"))
            .map_err(|e|format!("write native offer certifier request: {e}"))?;
'''
t=one(t,needle,replacement,'write index request')
t=one(t,'#[cfg(windows)] pub fn probe(pid:u32)->Result<String,String>{imp::probe(pid)}\n','#[cfg(windows)] pub fn probe(pid:u32,player_index:usize,club_index:usize)->Result<String,String>{imp::probe(pid,player_index,club_index)}\n','windows wrapper')
t=one(t,'#[cfg(not(windows))] pub fn probe(_pid:u32)->Result<String,String>{Err("Native offer IL2CPP probe is Windows-only in this build".into())}\n','#[cfg(not(windows))] pub fn probe(_pid:u32,_player_index:usize,_club_index:usize)->Result<String,String>{Err("Native offer IL2CPP probe is Windows-only in this build".into())}\n','nonwindows wrapper')
wr(p,t)

# -----------------------------------------------------------------------------
# UI: the native certifier now uses the currently selected player and AI club.
# PlayerRecord.index and CachedClub.index are already the live 0-based DB arrays.
# -----------------------------------------------------------------------------
p='src/ui/player_panel.rs'; t=rd(p)
pattern=r'''if ui\.button\("🧬 MAP NATIVE OFFER PAYLOAD • SAFE"\).*?\.clicked\(\)\{ui\.ctx\(\)\.data_mut\(\|d\|d\.insert_temp\(egui::Id::new\("element_v84_native_offer_probe"\),true\)\);\}'''
replacement='''if let Some(target)=selected {
        ui.label(egui::RichText::new(format!("Selected native DB indexes • player={} • club={}",player.index,target.index)).small().weak());
        if ui.button("🧬 CERTIFY SELECTED PLAYER + CLUB INTEROP • SAFE").on_hover_text("Constructs FM27 PersonReference(index) and ClubReference(index) for the exact current selection, then reads identity/index back. No transfer action is dispatched.").clicked(){
            ui.ctx().data_mut(|d|d.insert_temp(egui::Id::new("element_v84_native_offer_probe"),(player.index,target.index)));
        }
    } else {
        ui.add_enabled(false,egui::Button::new("🧬 CERTIFY SELECTED PLAYER + CLUB INTEROP • SAFE"));
        ui.label(egui::RichText::new("Select an AI club above before running the Interop certifier.").small().weak());
    }'''
t2,n=re.subn(pattern,replacement,t,count=1)
if n!=1: raise SystemExit('v8.7 native certifier UI button marker missing')
t=t2
t=t.replace('Native Offer Payload Blueprint • v8.6','Native Offer Index/Interop Certifier • v8.7')
t=t.replace('📋 FULL NATIVE OFFER PAYLOAD BLUEPRINT','📋 FULL NATIVE OFFER INDEX / INTEROP REPORT')
wr(p,t)

# App consumes the selected indexes from egui temp storage and sends them to the
# bridge. This stays read-only; writable/editing mode is not required.
p='src/app.rs'; t=rd(p)
old='''        if ctx.data_mut(|d|{let id=egui::Id::new("element_v84_native_offer_probe");let v=d.get_temp::<bool>(id).unwrap_or(false);d.remove::<bool>(id);v}) {
            if self.conn.is_attached(){self.bridge.send(BridgeCmd::ProbeNativeOfferInterop);self.set_status("Probing live FM27 native offer dispatcher…".into());}
        }
'''
new='''        if let Some((player_index,club_index))=ctx.data_mut(|d|{let id=egui::Id::new("element_v84_native_offer_probe");let v=d.get_temp::<(usize,usize)>(id);d.remove::<(usize,usize)>(id);v}) {
            if self.conn.is_attached(){self.bridge.send(BridgeCmd::ProbeNativeOfferInterop{player_index,club_index});self.set_status(format!("Certifying FM27 PersonReference({player_index}) + ClubReference({club_index})…"));}
        }
'''
t=one(t,old,new,'app index request')
wr(p,t)

# -----------------------------------------------------------------------------
# Injected helper: construct the exact selected PersonReference / ClubReference
# through IL2CPP object allocation + their real Int32 constructors. Then read
# m_index and GetPersistentIdentity back. No HandleActionEvent / SendEvent call.
# -----------------------------------------------------------------------------
helper=Path(__file__).with_name('native_offer_helper.rs')
t=helper.read_text(encoding='utf-8')

if 'type ObjectNew' not in t:
    t=t.replace(
        'type ObjectUnbox = unsafe extern "C" fn(*mut c_void) -> *mut c_void;\n',
        'type ObjectUnbox = unsafe extern "C" fn(*mut c_void) -> *mut c_void;\n'
        'type ObjectNew = unsafe extern "C" fn(*mut c_void) -> *mut c_void;\n'
        'type StringChars = unsafe extern "C" fn(*mut c_void) -> *const u16;\n'
        'type StringLength = unsafe extern "C" fn(*mut c_void) -> i32;\n'
    )

if 'fn certifier_request_path()' not in t:
    marker='fn progress_path() -> std::path::PathBuf {'
    idx=t.find(marker)
    if idx<0: raise SystemExit('v8.7 helper path marker missing')
    insert='''fn certifier_request_path() -> std::path::PathBuf {
    std::env::temp_dir().join("ElementFM27-native-offer-request.txt")
}

fn read_certifier_request() -> Result<(i32,i32),String> {
    let text=fs::read_to_string(certifier_request_path()).map_err(|e|format!("read certifier request: {e}"))?;
    let mut player=None; let mut club=None;
    for line in text.lines(){
        if let Some(v)=line.strip_prefix("player_index="){player=v.trim().parse::<i32>().ok();}
        if let Some(v)=line.strip_prefix("club_index="){club=v.trim().parse::<i32>().ok();}
    }
    match (player,club){(Some(p),Some(c)) if p>=0 && c>=0=>Ok((p,c)),_=>Err("certifier request missing valid player_index / club_index".into())}
}

'''
    t=t[:idx]+insert+t[idx:]

if 'unsafe fn certifier_find_method_exact' not in t:
    marker='unsafe fn run_probe() -> Result<String, String> {'
    insert=r'''
unsafe fn certifier_find_method_exact(
    class:*mut c_void,
    name:&str,
    wanted:&[&str],
    class_get_methods:ClassGetMethods,
    method_get_name:MethodGetName,
    method_get_param_count:MethodGetParamCount,
    method_get_param:MethodGetParam,
    type_get_name:TypeGetName,
)->Option<*const c_void>{
    let mut iter:*mut c_void=null_mut();
    loop{
        let m=class_get_methods(class,&mut iter); if m.is_null(){break;}
        if cstr(method_get_name(m))!=name{continue;}
        if method_get_param_count(m) as usize!=wanted.len(){continue;}
        let mut ok=true;
        for (i,w) in wanted.iter().enumerate(){
            let ty=method_get_param(m,i as u32);
            let tn=if ty.is_null(){String::new()}else{cstr(type_get_name(ty))};
            if tn!=*w{ok=false;break;}
        }
        if ok{return Some(m);}
    }
    None
}

unsafe fn certifier_managed_string(obj:*mut c_void,string_chars:StringChars,string_length:StringLength)->String{
    if obj.is_null(){return "<null>".into();}
    let len=string_length(obj); if len<=0{return String::new();}
    let chars=string_chars(obj); if chars.is_null(){return "<null-chars>".into();}
    String::from_utf16_lossy(std::slice::from_raw_parts(chars,len as usize))
}

unsafe fn certifier_find_i32_field(
    class:*mut c_void,
    wanted:&str,
    class_get_fields:ClassGetFields,
    class_get_parent:ClassGetParent,
    field_get_name:FieldGetName,
    field_get_offset:FieldGetOffset,
)->Option<usize>{
    let mut current=class; let mut depth=0usize;
    while !current.is_null() && depth<8{
        let mut iter:*mut c_void=null_mut();
        loop{
            let f=class_get_fields(current,&mut iter); if f.is_null(){break;}
            if cstr(field_get_name(f))==wanted{return Some(field_get_offset(f));}
        }
        current=class_get_parent(current);depth+=1;
    }
    None
}

unsafe fn certifier_construct_db_ref(
    label:&str,
    namespace:&str,
    class_name:&str,
    index:i32,
    assemblies:*mut *const c_void,
    assembly_count:usize,
    assembly_get_image:AssemblyGetImage,
    class_from_name:ClassFromName,
    class_get_methods:ClassGetMethods,
    method_get_name:MethodGetName,
    method_get_param_count:MethodGetParamCount,
    method_get_param:MethodGetParam,
    type_get_name:TypeGetName,
    runtime_invoke:RuntimeInvoke,
    object_new:ObjectNew,
    class_get_method:ClassGetMethodFromName,
    class_get_fields:ClassGetFields,
    class_get_parent:ClassGetParent,
    field_get_name:FieldGetName,
    field_get_offset:FieldGetOffset,
    object_get_class:ObjectGetClass,
    class_get_name:ClassGetName,
    class_get_namespace:ClassGetNamespace,
    class_is_valuetype:ClassIsValueType,
    object_unbox:ObjectUnbox,
    string_chars:StringChars,
    string_length:StringLength,
)->Vec<String>{
    let mut out=Vec::new();
    let Some(class)=find_class(assemblies,assembly_count,assembly_get_image,class_from_name,namespace,class_name) else {out.push(format!("{label}: CLASS NOT FOUND"));return out;};
    let Some(ctor)=certifier_find_method_exact(class,".ctor",&["System.Int32"],class_get_methods,method_get_name,method_get_param_count,method_get_param,type_get_name) else {out.push(format!("{label}: Int32 constructor NOT FOUND"));return out;};
    let obj=object_new(class); if obj.is_null(){out.push(format!("{label}: il2cpp_object_new returned null"));return out;}
    let mut idx=index; let mut args=[(&mut idx as *mut i32).cast::<c_void>()]; let mut exc:*mut c_void=null_mut();
    runtime_invoke(ctor,obj,args.as_mut_ptr(),&mut exc);
    if !exc.is_null(){out.push(format!("{label}: ctor EXCEPTION@0x{:X}",exc as usize));return out;}
    out.push(format!("{label}: object={} requested_index={index}",blueprint_boxed_summary(obj,object_get_class,class_get_name,class_get_namespace,class_is_valuetype,object_unbox)));
    if let Some(off)=certifier_find_i32_field(class,"m_index",class_get_fields,class_get_parent,field_get_name,field_get_offset){
        let actual=*((obj as *const u8).add(off) as *const i32);
        out.push(format!("{label}: m_index offset=0x{off:X} readback={actual} match={}",actual==index));
    }else{out.push(format!("{label}: m_index field not found"));}
    let mn=CString::new("GetPersistentIdentity").unwrap(); let m=class_get_method(class,mn.as_ptr(),0);
    if !m.is_null(){let mut ex:*mut c_void=null_mut();let ret=runtime_invoke(m,obj,null_mut(),&mut ex);if ex.is_null(){out.push(format!("{label}: persistent_identity=\"{}\"",certifier_managed_string(ret,string_chars,string_length)));}else{out.push(format!("{label}: GetPersistentIdentity EXCEPTION@0x{:X}",ex as usize));}}
    let idn=CString::new("get_ID").unwrap(); let idm=class_get_method(class,idn.as_ptr(),0);
    if !idm.is_null(){let mut ex:*mut c_void=null_mut();let ret=runtime_invoke(idm,obj,null_mut(),&mut ex);if ex.is_null(){out.push(format!("{label}: ID={}",blueprint_boxed_summary(ret,object_get_class,class_get_name,class_get_namespace,class_is_valuetype,object_unbox)));}}
    out
}

'''
    if marker not in t: raise SystemExit('v8.7 helper run marker missing')
    t=t.replace(marker,insert+marker,1)

if 'il2cpp_object_new' not in t:
    t=t.replace(
        '    let object_unbox: ObjectUnbox = resolve!("il2cpp_object_unbox", ObjectUnbox);\n',
        '    let object_unbox: ObjectUnbox = resolve!("il2cpp_object_unbox", ObjectUnbox);\n'
        '    let object_new: ObjectNew = resolve!("il2cpp_object_new", ObjectNew);\n'
        '    let string_chars: StringChars = resolve!("il2cpp_string_chars", StringChars);\n'
        '    let string_length: StringLength = resolve!("il2cpp_string_length", StringLength);\n'
    )

if '=== SELECTED ENTITY INTEROP CERTIFIER v8.7 ===' not in t:
    anchor='        lines.push("\\nV8.6 NEXT GATE: identify exact player + club InteropReference pair IDs and the action data shape. Only after those are certified do we enable a guarded native action dispatch.".to_string());\n'
    block=r'''        lines.push("\n=== SELECTED ENTITY INTEROP CERTIFIER v8.7 ===".to_string());
        lines.push("Read-only: constructs PersonReference(index) and ClubReference(index) for Element's exact current selection. No HandleActionEvent or SendEvent call is made.".to_string());
        match read_certifier_request(){
            Ok((player_index,club_index))=>{
                lines.push(format!("REQUEST player_index={player_index} club_index={club_index}"));
                lines.extend(certifier_construct_db_ref("PLAYER","FM.UI","PersonReference",player_index,assemblies,count,assembly_get_image,class_from_name,class_get_methods,method_get_name,method_get_param_count,method_get_param,type_get_name,runtime_invoke,object_new,class_get_method,class_get_fields,class_get_parent,field_get_name,field_get_offset,object_get_class,class_get_name,class_get_namespace,class_is_valuetype,object_unbox,string_chars,string_length));
                lines.extend(certifier_construct_db_ref("CLUB","FM.UI","ClubReference",club_index,assemblies,count,assembly_get_image,class_from_name,class_get_methods,method_get_name,method_get_param_count,method_get_param,type_get_name,runtime_invoke,object_new,class_get_method,class_get_fields,class_get_parent,field_get_name,field_get_offset,object_get_class,class_get_name,class_get_namespace,class_is_valuetype,object_unbox,string_chars,string_length));
                lines.push("V8.7 GATE: both m_index readbacks must match the request and persistent identities must be non-empty before native dispatch work continues.".to_string());
            }
            Err(e)=>lines.push(format!("V8.7 REQUEST ERROR: {e}")),
        }
'''
    if anchor not in t: raise SystemExit('v8.7 v8.6 gate anchor missing')
    t=t.replace(anchor,block+anchor,1)

t=t.replace('Native Offer Payload Blueprint v8.6','Native Offer Index Interop Certifier v8.7')
helper.write_text(t,encoding='utf-8')

print('Element v8.7 selected entity Interop certifier applied.')
