from pathlib import Path

root=Path.cwd()
ui=root/'src/ui/player_panel.rs'
if ui.exists():
    s=ui.read_text(encoding='utf-8')
    s=s.replace('Native Offer Known-ID Mapper • v8.8','Native Offer Real Property Map • v8.9')
    s=s.replace('MAP PLAYER + CLUB ACTION KEYS • SAFE','ENUMERATE REAL INTEROP PROPERTIES • SAFE')
    s=s.replace('📋 FULL NATIVE OFFER KNOWN-ID REPORT','📋 FULL NATIVE OFFER PROPERTY MAP')
    ui.write_text(s,encoding='utf-8')

helper=Path(__file__).with_name('native_offer_helper.rs')
t=helper.read_text(encoding='utf-8')

if 'type ClassFromType' not in t:
    t=t.replace(
        'type ClassFromName = unsafe extern "C" fn(*const c_void, *const c_char, *const c_char) -> *mut c_void;\n',
        'type ClassFromName = unsafe extern "C" fn(*const c_void, *const c_char, *const c_char) -> *mut c_void;\n'
        'type ClassFromType = unsafe extern "C" fn(*const c_void) -> *mut c_void;\n'
    )

if 'unsafe fn v89_boxed_i32' not in t:
    marker='unsafe fn run_probe() -> Result<String, String> {'
    insert=r'''
unsafe fn v89_boxed_i32(obj:*mut c_void,object_unbox:ObjectUnbox)->Option<i32>{
    if obj.is_null(){return None;}
    let p=object_unbox(obj); if p.is_null(){return None;}
    Some(*(p as *const i32))
}

unsafe fn v89_boxed_bool(obj:*mut c_void,object_unbox:ObjectUnbox)->Option<bool>{
    if obj.is_null(){return None;}
    let p=object_unbox(obj); if p.is_null(){return None;}
    Some(*(p as *const u8)!=0)
}

unsafe fn v89_boxed_u32(obj:*mut c_void,object_unbox:ObjectUnbox)->Option<u32>{
    if obj.is_null(){return None;}
    let p=object_unbox(obj); if p.is_null(){return None;}
    Some(*(p as *const u32))
}

unsafe fn v89_enumerate_properties(
    label:&str,
    obj:*mut c_void,
    object_get_class:ObjectGetClass,
    class_get_method:ClassGetMethodFromName,
    method_get_param:MethodGetParam,
    class_from_type:ClassFromType,
    object_new:ObjectNew,
    runtime_invoke:RuntimeInvoke,
    object_unbox:ObjectUnbox,
    class_get_name:ClassGetName,
    class_get_namespace:ClassGetNamespace,
    class_is_valuetype:ClassIsValueType,
    string_chars:StringChars,
    string_length:StringLength,
)->Vec<String>{
    let mut out=Vec::new();
    if obj.is_null(){out.push(format!("{label}: object=<null>"));return out;}
    let class=object_get_class(obj); if class.is_null(){out.push(format!("{label}: class=<null>"));return out;}

    let mut chosen_name="GetPropertiesInternal";
    let mut mn=CString::new(chosen_name).unwrap();
    let mut get_props=class_get_method(class,mn.as_ptr(),1);
    if get_props.is_null(){
        chosen_name="GetProperties";
        mn=CString::new(chosen_name).unwrap();
        get_props=class_get_method(class,mn.as_ptr(),1);
    }
    if get_props.is_null(){out.push(format!("{label}: GetProperties/Internal(list) not found"));return out;}

    let list_ty=method_get_param(get_props,0);
    if list_ty.is_null(){out.push(format!("{label}: properties list param type=<null>"));return out;}
    let list_class=class_from_type(list_ty);
    if list_class.is_null(){out.push(format!("{label}: il2cpp_class_from_type(list) returned null"));return out;}
    let list_obj=object_new(list_class);
    if list_obj.is_null(){out.push(format!("{label}: properties list object_new returned null"));return out;}
    let ctor_name=CString::new(".ctor").unwrap();
    let ctor=class_get_method(list_class,ctor_name.as_ptr(),0);
    if ctor.is_null(){out.push(format!("{label}: properties list .ctor() not found"));return out;}
    let mut exc:*mut c_void=null_mut();
    runtime_invoke(ctor,list_obj,null_mut(),&mut exc);
    if !exc.is_null(){out.push(format!("{label}: properties list ctor exception@0x{:X}",exc as usize));return out;}

    let mut list_arg=list_obj;
    let mut args=[(&mut list_arg as *mut *mut c_void).cast::<c_void>()];
    exc=null_mut();
    runtime_invoke(get_props,obj,args.as_mut_ptr(),&mut exc);
    if !exc.is_null(){out.push(format!("{label}: {chosen_name} exception@0x{:X}",exc as usize));return out;}

    let count_name=CString::new("get_Count").unwrap();
    let get_count=class_get_method(list_class,count_name.as_ptr(),0);
    let item_name=CString::new("get_Item").unwrap();
    let get_item=class_get_method(list_class,item_name.as_ptr(),1);
    if get_count.is_null() || get_item.is_null(){out.push(format!("{label}: List get_Count/get_Item not found"));return out;}
    exc=null_mut();
    let count_obj=runtime_invoke(get_count,list_obj,null_mut(),&mut exc);
    if !exc.is_null(){out.push(format!("{label}: List.get_Count exception@0x{:X}",exc as usize));return out;}
    let count=v89_boxed_i32(count_obj,object_unbox).unwrap_or(-1);
    out.push(format!("{label}: {chosen_name} count={count}"));
    if count<=0{return out;}

    let desc_name=CString::new("GetPropertyDescriptionInternal").unwrap();
    let desc_method=class_get_method(class,desc_name.as_ptr(),1);
    let type_name=CString::new("GetPropertyTypeInternal").unwrap();
    let type_method=class_get_method(class,type_name.as_ptr(),1);
    let accepts_name=CString::new("AcceptsPropertyInternal").unwrap();
    let accepts_method=class_get_method(class,accepts_name.as_ptr(),1);

    let limit=std::cmp::min(count,128);
    for i in 0..limit{
        let mut idx=i;
        let mut item_args=[(&mut idx as *mut i32).cast::<c_void>()];
        exc=null_mut();
        let item=runtime_invoke(get_item,list_obj,item_args.as_mut_ptr(),&mut exc);
        if !exc.is_null(){out.push(format!("{label}: property[{i}] get_Item exception@0x{:X}",exc as usize));continue;}
        let Some(pid)=v89_boxed_u32(item,object_unbox) else {out.push(format!("{label}: property[{i}] unbox failed"));continue;};

        let mut desc="<no-description>".to_string();
        if !desc_method.is_null(){
            let mut p=pid; let mut a=[(&mut p as *mut u32).cast::<c_void>()]; exc=null_mut();
            let ret=runtime_invoke(desc_method,obj,a.as_mut_ptr(),&mut exc);
            if exc.is_null(){desc=certifier_managed_string(ret,string_chars,string_length);}else{desc=format!("<desc-exception@0x{:X}>",exc as usize);}
        }

        let mut typ="<no-type>".to_string();
        if !type_method.is_null(){
            let mut p=pid; let mut a=[(&mut p as *mut u32).cast::<c_void>()]; exc=null_mut();
            let ret=runtime_invoke(type_method,obj,a.as_mut_ptr(),&mut exc);
            if exc.is_null(){typ=blueprint_boxed_summary(ret,object_get_class,class_get_name,class_get_namespace,class_is_valuetype,object_unbox);}else{typ=format!("<type-exception@0x{:X}>",exc as usize);}
        }

        let mut accepts="<n/a>".to_string();
        if !accepts_method.is_null(){
            let mut p=pid; let mut a=[(&mut p as *mut u32).cast::<c_void>()]; exc=null_mut();
            let ret=runtime_invoke(accepts_method,obj,a.as_mut_ptr(),&mut exc);
            if exc.is_null(){accepts=v89_boxed_bool(ret,object_unbox).map(|v|v.to_string()).unwrap_or_else(||"<unbox-failed>".into());}else{accepts=format!("<accepts-exception@0x{:X}>",exc as usize);}
        }
        out.push(format!("{label}: PROPERTY[{i}] id=0x{pid:08X} ({pid}) accepts={accepts} desc=\"{desc}\" type={typ}"));
    }
    if count>limit{out.push(format!("{label}: truncated property output at {limit}/{count}"));}
    out
}
'''
    if marker not in t: raise SystemExit('v8.9 run_probe marker missing')
    t=t.replace(marker,insert+marker,1)

if 'let class_from_type: ClassFromType' not in t:
    marker='    let class_from_name: ClassFromName = resolve!("il2cpp_class_from_name", ClassFromName);\n'
    if marker not in t: raise SystemExit('v8.9 class_from_name resolver marker missing')
    t=t.replace(marker,marker+'    let class_from_type: ClassFromType = resolve!("il2cpp_class_from_type", ClassFromType);\n',1)

if '=== REAL INTEROP PROPERTY MAP v8.9 ===' not in t:
    gate='            lines.push("V8.8 GATE: PERSON_KEY should resolve to the selected player index and CLUB_KEY to the selected club index. Action/session hits tell us whether those references already carry transfer context.".to_string());\n'
    if gate not in t: raise SystemExit('v8.9 v8.8 gate marker missing')
    block=r'''            lines.push("\n=== REAL INTEROP PROPERTY MAP v8.9 ===".to_string());
            lines.push("Read-only: asks each InteropReference implementation to populate its native List<PropertyID>, then reads Count/Item and descriptions/types through managed APIs. No action is dispatched.".to_string());
            match read_certifier_request(){
                Ok((pidx,cidx))=>{
                    match v88_construct_ref("FM.UI","PersonReference",pidx,assemblies,count,assembly_get_image,class_from_name,class_get_methods,method_get_name,method_get_param_count,method_get_param,type_get_name,runtime_invoke,object_new){
                        Ok(o)=>lines.extend(v89_enumerate_properties("PLAYER",o,object_get_class,class_get_method,method_get_param,class_from_type,object_new,runtime_invoke,object_unbox,class_get_name,class_get_namespace,class_is_valuetype,string_chars,string_length)),
                        Err(e)=>lines.push(format!("PLAYER PROPERTY MAP ERROR: {e}")),
                    }
                    match v88_construct_ref("FM.UI","ClubReference",cidx,assemblies,count,assembly_get_image,class_from_name,class_get_methods,method_get_name,method_get_param_count,method_get_param,type_get_name,runtime_invoke,object_new){
                        Ok(o)=>lines.extend(v89_enumerate_properties("CLUB",o,object_get_class,class_get_method,method_get_param,class_from_type,object_new,runtime_invoke,object_unbox,class_get_name,class_get_namespace,class_is_valuetype,string_chars,string_length)),
                        Err(e)=>lines.push(format!("CLUB PROPERTY MAP ERROR: {e}")),
                    }
                    match v88_singleton("FM.UI","ActionReference",assemblies,count,assembly_get_image,class_from_name,class_get_method,runtime_invoke){
                        Ok(o)=>lines.extend(v89_enumerate_properties("ACTION",o,object_get_class,class_get_method,method_get_param,class_from_type,object_new,runtime_invoke,object_unbox,class_get_name,class_get_namespace,class_is_valuetype,string_chars,string_length)),
                        Err(e)=>lines.push(format!("ACTION PROPERTY MAP ERROR: {e}")),
                    }
                    match v88_singleton("FM.UI","TransferOfferEditSessionReference",assemblies,count,assembly_get_image,class_from_name,class_get_method,runtime_invoke){
                        Ok(o)=>lines.extend(v89_enumerate_properties("SESSION",o,object_get_class,class_get_method,method_get_param,class_from_type,object_new,runtime_invoke,object_unbox,class_get_name,class_get_namespace,class_is_valuetype,string_chars,string_length)),
                        Err(e)=>lines.push(format!("SESSION PROPERTY MAP ERROR: {e}")),
                    }
                }
                Err(e)=>lines.push(format!("V8.9 REQUEST ERROR: {e}")),
            }
            lines.push("V8.9 GATE: property IDs/descriptions are now sourced from FM's own GetProperties API. Transfer-related properties on ACTION/SESSION become the certified keys for payload construction.".to_string());
'''
    t=t.replace(gate,gate+block,1)

t=t.replace('Native Offer Known-ID Mapper v8.8','Native Offer Real Property Map v8.9')
helper.write_text(t,encoding='utf-8')
print('Element v8.9 Real Interop Property Map applied.')
