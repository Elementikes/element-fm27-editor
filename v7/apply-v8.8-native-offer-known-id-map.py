from pathlib import Path

root=Path.cwd()
ui=root/'src/ui/player_panel.rs'
if ui.exists():
    s=ui.read_text(encoding='utf-8')
    s=s.replace('Native Offer Index/Interop Certifier • v8.7','Native Offer Known-ID Mapper • v8.8')
    s=s.replace('CERTIFY SELECTED PLAYER + CLUB INTEROP • SAFE','MAP PLAYER + CLUB ACTION KEYS • SAFE')
    s=s.replace('📋 FULL NATIVE OFFER INDEX / INTEROP REPORT','📋 FULL NATIVE OFFER KNOWN-ID REPORT')
    ui.write_text(s,encoding='utf-8')

helper=Path(__file__).with_name('native_offer_helper.rs')
t=helper.read_text(encoding='utf-8')

if 'unsafe fn v88_try_get_value' not in t:
    marker='unsafe fn run_probe() -> Result<String, String> {'
    insert=r'''
unsafe fn v88_try_get_value(
    label:&str,
    obj:*mut c_void,
    id:u32,
    object_get_class:ObjectGetClass,
    class_get_method:ClassGetMethodFromName,
    runtime_invoke:RuntimeInvoke,
    object_unbox:ObjectUnbox,
)->String{
    if obj.is_null(){return format!("{label}: object=<null>");}
    let class=object_get_class(obj); if class.is_null(){return format!("{label}: class=<null>");}
    let mn=CString::new("TryGetValue").unwrap();
    let m=class_get_method(class,mn.as_ptr(),2);
    if m.is_null(){return format!("{label}: TryGetValue not found");}
    let mut key=id; let mut value:i32=0; let mut args=[(&mut key as *mut u32).cast::<c_void>(),(&mut value as *mut i32).cast::<c_void>()]; let mut exc:*mut c_void=null_mut();
    let ret=runtime_invoke(m,obj,args.as_mut_ptr(),&mut exc);
    if !exc.is_null(){return format!("{label}: TryGetValue(0x{id:08X}) exception@0x{:X}",exc as usize);}
    let ok=if ret.is_null(){false}else{let p=object_unbox(ret);!p.is_null() && *(p as *const u8)!=0};
    format!("{label}: TryGetValue(0x{id:08X}) ok={ok} value={value}")
}

unsafe fn v88_construct_ref(
    namespace:&str,class_name:&str,index:i32,
    assemblies:*mut *const c_void,assembly_count:usize,
    assembly_get_image:AssemblyGetImage,class_from_name:ClassFromName,
    class_get_methods:ClassGetMethods,method_get_name:MethodGetName,
    method_get_param_count:MethodGetParamCount,method_get_param:MethodGetParam,
    type_get_name:TypeGetName,runtime_invoke:RuntimeInvoke,object_new:ObjectNew,
)->Result<*mut c_void,String>{
    let class=find_class(assemblies,assembly_count,assembly_get_image,class_from_name,namespace,class_name).ok_or_else(||format!("{class_name} not found"))?;
    let ctor=certifier_find_method_exact(class,".ctor",&["System.Int32"],class_get_methods,method_get_name,method_get_param_count,method_get_param,type_get_name).ok_or_else(||format!("{class_name} Int32 ctor not found"))?;
    let obj=object_new(class); if obj.is_null(){return Err(format!("{class_name} object_new null"));}
    let mut idx=index; let mut args=[(&mut idx as *mut i32).cast::<c_void>()]; let mut exc:*mut c_void=null_mut();
    runtime_invoke(ctor,obj,args.as_mut_ptr(),&mut exc);
    if !exc.is_null(){return Err(format!("{class_name} ctor exception@0x{:X}",exc as usize));}
    Ok(obj)
}

unsafe fn v88_singleton(
    namespace:&str,class_name:&str,
    assemblies:*mut *const c_void,assembly_count:usize,
    assembly_get_image:AssemblyGetImage,class_from_name:ClassFromName,
    class_get_method:ClassGetMethodFromName,runtime_invoke:RuntimeInvoke,
)->Result<*mut c_void,String>{
    let class=find_class(assemblies,assembly_count,assembly_get_image,class_from_name,namespace,class_name).ok_or_else(||format!("{class_name} not found"))?;
    let n=CString::new("GetInstance").unwrap(); let m=class_get_method(class,n.as_ptr(),0); if m.is_null(){return Err(format!("{class_name}.GetInstance not found"));}
    let mut exc:*mut c_void=null_mut(); let obj=runtime_invoke(m,null_mut(),null_mut(),&mut exc); if !exc.is_null(){return Err(format!("{class_name}.GetInstance exception@0x{:X}",exc as usize));}
    Ok(obj)
}
'''
    if marker not in t: raise SystemExit('v8.8 run_probe marker missing')
    t=t.replace(marker,insert+marker,1)

if '=== NATIVE OFFER KNOWN-ID MAPPER v8.8 ===' not in t:
    gate='            lines.push("V8.7 GATE: both m_index readbacks must match the request and persistent identities must be non-empty before native dispatch work continues.".to_string());\n'
    if gate not in t: raise SystemExit('v8.8 v8.7 gate marker missing')
    block=r'''            lines.push("\n=== NATIVE OFFER KNOWN-ID MAPPER v8.8 ===".to_string());
            lines.push("Read-only: asks InteropReference.TryGetValue for the PersonReference and ClubReference keys indicated by their native ReferenceID prefixes. No action is dispatched.".to_string());
            const PERSON_KEY:u32=0x44420001;
            const CLUB_KEY:u32=0x44420003;
            match v88_construct_ref("FM.UI","PersonReference",pi,assemblies,count,assembly_get_image,class_from_name,class_get_methods,method_get_name,method_get_param_count,method_get_param,type_get_name,runtime_invoke,object_new){
                Ok(o)=>{lines.push(v88_try_get_value("PLAYER/PERSON_KEY",o,PERSON_KEY,object_get_class,class_get_method,runtime_invoke,object_unbox));lines.push(v88_try_get_value("PLAYER/CLUB_KEY",o,CLUB_KEY,object_get_class,class_get_method,runtime_invoke,object_unbox));},
                Err(e)=>lines.push(format!("PLAYER KEY MAP ERROR: {e}")),
            }
            match v88_construct_ref("FM.UI","ClubReference",ci,assemblies,count,assembly_get_image,class_from_name,class_get_methods,method_get_name,method_get_param_count,method_get_param,type_get_name,runtime_invoke,object_new){
                Ok(o)=>{lines.push(v88_try_get_value("CLUB/PERSON_KEY",o,PERSON_KEY,object_get_class,class_get_method,runtime_invoke,object_unbox));lines.push(v88_try_get_value("CLUB/CLUB_KEY",o,CLUB_KEY,object_get_class,class_get_method,runtime_invoke,object_unbox));},
                Err(e)=>lines.push(format!("CLUB KEY MAP ERROR: {e}")),
            }
            match v88_singleton("FM.UI","ActionReference",assemblies,count,assembly_get_image,class_from_name,class_get_method,runtime_invoke){
                Ok(o)=>{lines.push(v88_try_get_value("ACTION/PERSON_KEY",o,PERSON_KEY,object_get_class,class_get_method,runtime_invoke,object_unbox));lines.push(v88_try_get_value("ACTION/CLUB_KEY",o,CLUB_KEY,object_get_class,class_get_method,runtime_invoke,object_unbox));},
                Err(e)=>lines.push(format!("ACTION KEY MAP ERROR: {e}")),
            }
            match v88_singleton("FM.UI","TransferOfferEditSessionReference",assemblies,count,assembly_get_image,class_from_name,class_get_method,runtime_invoke){
                Ok(o)=>{lines.push(v88_try_get_value("SESSION/PERSON_KEY",o,PERSON_KEY,object_get_class,class_get_method,runtime_invoke,object_unbox));lines.push(v88_try_get_value("SESSION/CLUB_KEY",o,CLUB_KEY,object_get_class,class_get_method,runtime_invoke,object_unbox));},
                Err(e)=>lines.push(format!("SESSION KEY MAP ERROR: {e}")),
            }
            lines.push("V8.8 GATE: PERSON_KEY should resolve to the selected player index and CLUB_KEY to the selected club index. Action/session hits tell us whether those references already carry transfer context.".to_string());
'''
    t=t.replace(gate,gate+block,1)

t=t.replace('Native Offer Payload Blueprint v8.6','Native Offer Known-ID Mapper v8.8')
helper.write_text(t,encoding='utf-8')
print('Element v8.8 Native Offer Known-ID Mapper applied.')
