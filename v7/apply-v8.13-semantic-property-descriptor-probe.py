from pathlib import Path

root=Path.cwd()
ui=root/'src/ui/player_panel.rs'
if ui.exists():
    s=ui.read_text(encoding='utf-8')
    s=s.replace('Native Offer Inheritance PropertyID Decoder • v8.12','Native Offer Semantic Property Mapper • v8.13')
    s=s.replace('DECODE COMPLETE PROPERTY IDS • SAFE','MAP OFFER PROPERTY SEMANTICS • GUARDED')
    s=s.replace('📋 FULL INHERITANCE PROPERTY ID MAP','📋 FULL NATIVE OFFER SEMANTIC MAP')
    ui.write_text(s,encoding='utf-8')

helper=Path(__file__).with_name('native_offer_helper.rs')
t=helper.read_text(encoding='utf-8')

if 'type RuntimeInvokeV813' not in t:
    marker='type TypeGetName = unsafe extern "C" fn(*const c_void) -> *mut c_char;\n'
    insert='''type RuntimeInvokeV813 = unsafe extern "C" fn(*const c_void, *mut c_void, *mut *mut c_void, *mut *mut c_void) -> *mut c_void;\ntype StringCharsV813 = unsafe extern "C" fn(*mut c_void) -> *const u16;\ntype StringLengthV813 = unsafe extern "C" fn(*mut c_void) -> i32;\ntype ObjectUnboxV813 = unsafe extern "C" fn(*mut c_void) -> *mut c_void;\n'''
    if marker not in t: raise SystemExit('v8.13 type marker missing')
    t=t.replace(marker,marker+insert,1)

if 'unsafe fn v813_semantic_probe_one' not in t:
    marker='unsafe fn run_probe() -> Result<String, String> {'
    insert=r'''
unsafe fn v813_il2cpp_string(
    obj:*mut c_void,
    string_chars:StringCharsV813,
    string_length:StringLengthV813,
)->Result<String,String>{
    if obj.is_null(){return Err("null string object".to_string());}
    let n=string_length(obj);
    if n<0 || n>8192{return Err(format!("invalid string length {n}"));}
    let p=string_chars(obj);
    if p.is_null() && n>0{return Err("null string chars".to_string());}
    let s=std::slice::from_raw_parts(p,n as usize);
    Ok(String::from_utf16_lossy(s))
}

unsafe fn v813_semantic_probe_one(
    class:*mut c_void,
    property:u32,
    class_get_method:ClassGetMethodFromName,
    runtime_invoke:RuntimeInvokeV813,
    string_chars:StringCharsV813,
    string_length:StringLengthV813,
    object_unbox:ObjectUnboxV813,
)->Result<(String,i32),String>{
    if class.is_null(){return Err("null class".to_string());}
    let desc_name=CString::new("GetPropertyDescriptionInternal").unwrap();
    let type_name=CString::new("GetPropertyTypeInternal").unwrap();
    let desc_method=class_get_method(class,desc_name.as_ptr(),1);
    let type_method=class_get_method(class,type_name.as_ptr(),1);
    if desc_method.is_null(){return Err("GetPropertyDescriptionInternal missing".to_string());}
    if type_method.is_null(){return Err("GetPropertyTypeInternal missing".to_string());}

    let mut p0=property;
    let mut args=[&mut p0 as *mut u32 as *mut c_void];
    let mut exc:*mut c_void=null_mut();
    let desc_obj=runtime_invoke(desc_method,null_mut(),args.as_mut_ptr(),&mut exc);
    if !exc.is_null(){return Err(format!("description invoke exception@0x{:X}",exc as usize));}
    let desc=v813_il2cpp_string(desc_obj,string_chars,string_length)?;

    let mut p1=property;
    let mut args2=[&mut p1 as *mut u32 as *mut c_void];
    let mut exc2:*mut c_void=null_mut();
    let type_obj=runtime_invoke(type_method,null_mut(),args2.as_mut_ptr(),&mut exc2);
    if !exc2.is_null(){return Err(format!("type invoke exception@0x{:X}",exc2 as usize));}
    if type_obj.is_null(){return Err("type invoke returned null".to_string());}
    let raw=object_unbox(type_obj);
    if raw.is_null(){return Err("type object unbox returned null".to_string());}
    let binding_kind=*(raw as *const i32);
    Ok((desc,binding_kind))
}

unsafe fn v813_map_class(
    label:&str,ns:&str,cn:&str,ids:&[u32],
    assemblies:*mut *const c_void,count:usize,
    assembly_get_image:AssemblyGetImage,class_from_name:ClassFromName,class_get_method:ClassGetMethodFromName,
    runtime_invoke:RuntimeInvokeV813,string_chars:StringCharsV813,string_length:StringLengthV813,object_unbox:ObjectUnboxV813,
)->Vec<String>{
    let mut out=Vec::new();
    let Some(class)=find_class(assemblies,count,assembly_get_image,class_from_name,ns,cn) else {
        out.push(format!("{label}: class {ns}.{cn} not found"));return out;
    };
    for (i,id) in ids.iter().enumerate(){
        match v813_semantic_probe_one(class,*id,class_get_method,runtime_invoke,string_chars,string_length,object_unbox){
            Ok((desc,kind))=>out.push(format!("{label}: SEMANTIC[{i:02}] id=0x{id:08X} be=\"{}\" binding_kind={kind} desc=\"{}\"",v811_ascii4_be(*id),desc.replace('\\',"\\\\").replace('"',"\\\""))),
            Err(e)=>out.push(format!("{label}: SEMANTIC[{i:02}] id=0x{id:08X} be=\"{}\" ERROR={e}",v811_ascii4_be(*id))),
        }
    }
    out
}
'''
    if marker not in t: raise SystemExit('v8.13 run_probe marker missing')
    t=t.replace(marker,insert+marker,1)

# Resolve only the four exports needed by the guarded semantic probe.
if 'let v813_runtime_invoke: RuntimeInvokeV813' not in t:
    marker='    let type_get_name: TypeGetName = resolve!("il2cpp_type_get_name", TypeGetName);\n'
    insert='''    let v813_runtime_invoke: RuntimeInvokeV813 = resolve!("il2cpp_runtime_invoke", RuntimeInvokeV813);\n    let v813_string_chars: StringCharsV813 = resolve!("il2cpp_string_chars", StringCharsV813);\n    let v813_string_length: StringLengthV813 = resolve!("il2cpp_string_length", StringLengthV813);\n    let v813_object_unbox: ObjectUnboxV813 = resolve!("il2cpp_object_unbox", ObjectUnboxV813);\n'''
    if marker not in t: raise SystemExit('v8.13 resolver marker missing')
    t=t.replace(marker,marker+insert,1)

if '=== GUARDED SEMANTIC PROPERTY MAPPER v8.13 ===' not in t:
    gate='            lines.push("V8.12 GATE: SESSION must report own_match=true and COMPLETE_COUNT == expected_total. Once green, use COMPLETE_PROPERTY overlap across session/player-offer/action references for the semantic payload map.".to_string());\n'
    if gate not in t: raise SystemExit('v8.13 v8.12 gate marker missing')
    block=r'''            lines.push("\n=== GUARDED SEMANTIC PROPERTY MAPPER v8.13 ===".to_string());
            lines.push("Read-only guarded runtime descriptor probe. No HandleActionEvent/SendEvent/write is performed. First invokes one known TransferOfferActionButtonPropsReference description as a canary; semantic mapping continues only if the canary succeeds.".to_string());

            let mut semantic_canary_ok=false;
            if let Some(canary_class)=find_class(assemblies,count,assembly_get_image,class_from_name,"FM.UI","TransferOfferActionButtonPropsReference"){
                match v813_semantic_probe_one(canary_class,0x64657363,class_get_method,v813_runtime_invoke,v813_string_chars,v813_string_length,v813_object_unbox){
                    Ok((desc,kind))=>{
                        lines.push(format!("V8.13 CANARY: id=0x64657363 be=\"desc\" binding_kind={kind} desc=\"{}\" OK",desc.replace('\\',"\\\\").replace('"',"\\\"")));
                        semantic_canary_ok=true;
                    }
                    Err(e)=>lines.push(format!("V8.13 CANARY: FAIL {e}")),
                }
            }else{
                lines.push("V8.13 CANARY: class missing".to_string());
            }

            if semantic_canary_ok{
                let player_offer_ids:[u32;10]=[
                    0x70657273,0x544F6274,0x544F7374,0x6F355445,0x544F6F74,
                    0x336C7144,0x74727374,0x646F754B,0x4449337A,0x61774D7A,
                ];
                let person_offer_ids:[u32;5]=[0x31362020,0x43714D41,0x54497463,0x61686937,0x544F6F74];
                let session_overlap_ids:[u32;5]=[0x70657273,0x544F6274,0x544F7374,0x544F6F74,0x54497463];
                lines.extend(v813_map_class("PLAYER_TRANSFER_OFFER","FM.UI","PlayerTransferOfferReference",&player_offer_ids,assemblies,count,assembly_get_image,class_from_name,class_get_method,v813_runtime_invoke,v813_string_chars,v813_string_length,v813_object_unbox));
                lines.extend(v813_map_class("PERSON_TRANSFER_OFFER","FM.UI","PersonTransferOfferReference",&person_offer_ids,assemblies,count,assembly_get_image,class_from_name,class_get_method,v813_runtime_invoke,v813_string_chars,v813_string_length,v813_object_unbox));
                lines.extend(v813_map_class("SESSION_OVERLAP","FM.UI","TransferOfferEditSessionReference",&session_overlap_ids,assemblies,count,assembly_get_image,class_from_name,class_get_method,v813_runtime_invoke,v813_string_chars,v813_string_length,v813_object_unbox));
                lines.push("V8.13 GATE: use exact desc + binding_kind values above to identify player/club/offer/status/fee-related properties. Do not enable native dispatch until semantic identities are certified.".to_string());
            }else{
                lines.push("V8.13 GATE: CLOSED — canary failed; no further semantic runtime calls were attempted.".to_string());
            }
'''
    t=t.replace(gate,gate+block,1)

t=t.replace('Native Offer Inheritance PropertyID Decoder v8.12','Native Offer Semantic Property Mapper v8.13')
helper.write_text(t,encoding='utf-8')
print('Element v8.13 Guarded Semantic Property Mapper applied.')
