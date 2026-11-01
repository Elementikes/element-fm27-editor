from pathlib import Path

helper=Path(__file__).with_name('native_offer_helper.rs')
t=helper.read_text(encoding='utf-8')

# v8.6: read-only payload blueprint. We still do not dispatch any FM action.
if 'type ClassGetNestedTypes' not in t:
    t=t.replace(
        'type ClassGetParent = unsafe extern "C" fn(*mut c_void) -> *mut c_void;\n',
        'type ClassGetParent = unsafe extern "C" fn(*mut c_void) -> *mut c_void;\n'
        'type ClassGetNestedTypes = unsafe extern "C" fn(*mut c_void, *mut *mut c_void) -> *mut c_void;\n'
        'type ClassIsValueType = unsafe extern "C" fn(*const c_void) -> bool;\n'
    )
if 'type RuntimeInvoke' not in t:
    t=t.replace(
        'type TypeGetName = unsafe extern "C" fn(*const c_void) -> *mut c_char;\n',
        'type TypeGetName = unsafe extern "C" fn(*const c_void) -> *mut c_char;\n'
        'type RuntimeInvoke = unsafe extern "C" fn(*const c_void, *mut c_void, *mut *mut c_void, *mut *mut c_void) -> *mut c_void;\n'
        'type ObjectGetClass = unsafe extern "C" fn(*mut c_void) -> *mut c_void;\n'
        'type ObjectUnbox = unsafe extern "C" fn(*mut c_void) -> *mut c_void;\n'
    )

if 'unsafe fn blueprint_boxed_summary' not in t:
    marker='unsafe fn run_probe() -> Result<String, String> {'
    insert=r'''
unsafe fn blueprint_boxed_summary(
    obj: *mut c_void,
    object_get_class: ObjectGetClass,
    class_get_name: ClassGetName,
    class_get_namespace: ClassGetNamespace,
    class_is_valuetype: ClassIsValueType,
    object_unbox: ObjectUnbox,
) -> String {
    if obj.is_null(){return "<null>".to_string();}
    let class=object_get_class(obj);
    if class.is_null(){return format!("object@0x{:X} class=<null>",obj as usize);}
    let cn=cstr(class_get_name(class));
    let ns=cstr(class_get_namespace(class));
    if class_is_valuetype(class as *const c_void){
        let raw=object_unbox(obj);
        if raw.is_null(){return format!("{ns}.{cn} boxed@0x{:X} raw=<null>",obj as usize);}
        let bytes=std::slice::from_raw_parts(raw as *const u8,16);
        let hex=bytes.iter().map(|b|format!("{b:02X}")).collect::<Vec<_>>().join(" ");
        format!("{ns}.{cn} boxed@0x{:X} raw16=[{hex}]",obj as usize)
    }else{
        format!("{ns}.{cn} object@0x{:X}",obj as usize)
    }
}

unsafe fn blueprint_invoke_zero(
    class:*mut c_void,
    method_name:&str,
    instance:*mut c_void,
    class_get_method:ClassGetMethodFromName,
    method_get_flags:MethodGetFlags,
    runtime_invoke:RuntimeInvoke,
    object_get_class:ObjectGetClass,
    class_get_name:ClassGetName,
    class_get_namespace:ClassGetNamespace,
    class_is_valuetype:ClassIsValueType,
    object_unbox:ObjectUnbox,
) -> Option<String>{
    let mn=CString::new(method_name).ok()?;
    let method=class_get_method(class,mn.as_ptr(),0);
    if method.is_null(){return None;}
    let mut iflags=0u32;
    let flags=method_get_flags(method,&mut iflags);
    if instance.is_null() && flags & METHOD_ATTRIBUTE_STATIC == 0{return Some(format!("{method_name}: instance-required"));}
    let mut exc:*mut c_void=null_mut();
    let ret=runtime_invoke(method,instance,null_mut(),&mut exc);
    if !exc.is_null(){return Some(format!("{method_name}: EXCEPTION@0x{:X}",exc as usize));}
    Some(format!("{method_name}: {}",blueprint_boxed_summary(ret,object_get_class,class_get_name,class_get_namespace,class_is_valuetype,object_unbox)))
}

unsafe fn blueprint_candidate_classes(
    assemblies:*mut *const c_void,
    assembly_count:usize,
    assembly_get_image:AssemblyGetImage,
    image_get_class_count:ImageGetClassCount,
    image_get_class:ImageGetClass,
    class_get_name:ClassGetName,
    class_get_namespace:ClassGetNamespace,
)->Vec<*mut c_void>{
    let needles=["actionreference","playerreference","personreference","clubreference","teamreference","transferoffer","transferproposal","interopreference"];
    let mut out=Vec::new();
    let mut seen_names=std::collections::BTreeSet::new();
    for ai in 0..assembly_count{
        let asm=*assemblies.add(ai); if asm.is_null(){continue;}
        let image=assembly_get_image(asm); if image.is_null(){continue;}
        let cc=image_get_class_count(image);
        for ci in 0..cc{
            let class=image_get_class(image,ci); if class.is_null(){continue;}
            let cn=cstr(class_get_name(class)); let ns=cstr(class_get_namespace(class));
            let low=cn.to_ascii_lowercase();
            if !needles.iter().any(|n|low.contains(n)){continue;}
            let key=format!("{ns}.{cn}");
            if seen_names.insert(key){out.push(class);}
            if out.len()>=96{return out;}
        }
    }
    out
}

unsafe fn blueprint_selected_methods(
    class:*mut c_void,
    class_get_methods:ClassGetMethods,
    method_get_name:MethodGetName,
    method_get_param_count:MethodGetParamCount,
    method_get_param:MethodGetParam,
    method_get_param_name:MethodGetParamName,
    method_get_flags:MethodGetFlags,
    method_get_return_type:MethodGetReturnType,
    type_get_name:TypeGetName,
)->Vec<String>{
    let mut out=Vec::new(); let mut iter:*mut c_void=null_mut(); let mut seen=0usize;
    let keep=[".ctor","get_Identifier","GetInstance","get_ID","SetValue","TryGetValue","TryGetProperty","TryCreate","Create","Build","Make","Offer","Transfer"];
    loop{
        let method=class_get_methods(class,&mut iter); if method.is_null(){break;}
        seen+=1; if seen>256{break;}
        let name=cstr(method_get_name(method));
        if !keep.iter().any(|k|name.contains(k)){continue;}
        let argc=method_get_param_count(method); let mut args=Vec::new();
        for i in 0..argc{
            let ty=method_get_param(method,i);
            let tn=if ty.is_null(){"<null-type>".to_string()}else{cstr(type_get_name(ty))};
            args.push(format!("{}:{}",cstr(method_get_param_name(method,i)),tn));
        }
        let mut iflags=0u32; let flags=method_get_flags(method,&mut iflags);
        let ret=method_get_return_type(method);
        let rn=if ret.is_null(){"<null-type>".to_string()}else{cstr(type_get_name(ret))};
        out.push(format!("  METHOD {name}({}) -> {rn} flags=0x{flags:08X} static={}",args.join(", "),if flags & METHOD_ATTRIBUTE_STATIC != 0{"yes"}else{"no"}));
        if out.len()>=64{break;}
    }
    out
}

unsafe fn blueprint_nested(
    class:*mut c_void,
    class_get_nested_types:ClassGetNestedTypes,
    class_get_name:ClassGetName,
    class_get_namespace:ClassGetNamespace,
    class_get_fields:ClassGetFields,
    class_get_parent:ClassGetParent,
    field_get_name:FieldGetName,
    field_get_type:FieldGetType,
    field_get_offset:FieldGetOffset,
    field_get_flags:FieldGetFlags,
    type_get_name:TypeGetName,
    class_get_methods:ClassGetMethods,
    method_get_name:MethodGetName,
    method_get_param_count:MethodGetParamCount,
    method_get_param:MethodGetParam,
    method_get_param_name:MethodGetParamName,
    method_get_flags:MethodGetFlags,
    method_get_return_type:MethodGetReturnType,
)->Vec<String>{
    let mut out=Vec::new(); let mut iter:*mut c_void=null_mut();
    loop{
        let nested=class_get_nested_types(class,&mut iter); if nested.is_null(){break;}
        let cn=cstr(class_get_name(nested)); let ns=cstr(class_get_namespace(nested));
        out.push(format!("NESTED {ns}.{cn} @ 0x{:X}",nested as usize));
        out.extend(describe_class_fields(nested,class_get_fields,class_get_parent,class_get_name,class_get_namespace,field_get_name,field_get_type,field_get_offset,field_get_flags,type_get_name));
        out.extend(blueprint_selected_methods(nested,class_get_methods,method_get_name,method_get_param_count,method_get_param,method_get_param_name,method_get_flags,method_get_return_type,type_get_name));
    }
    out
}

'''
    if marker not in t: raise SystemExit('v8.6 run_probe marker missing')
    t=t.replace(marker,insert+marker,1)

# Resolve extra read-only IL2CPP exports.
if 'il2cpp_class_get_nested_types' not in t:
    t=t.replace(
        '    let class_get_parent: ClassGetParent = resolve!("il2cpp_class_get_parent", ClassGetParent);\n',
        '    let class_get_parent: ClassGetParent = resolve!("il2cpp_class_get_parent", ClassGetParent);\n'
        '    let class_get_nested_types: ClassGetNestedTypes = resolve!("il2cpp_class_get_nested_types", ClassGetNestedTypes);\n'
        '    let class_is_valuetype: ClassIsValueType = resolve!("il2cpp_class_is_valuetype", ClassIsValueType);\n'
    )
if 'il2cpp_runtime_invoke' not in t:
    t=t.replace(
        '    let type_get_name: TypeGetName = resolve!("il2cpp_type_get_name", TypeGetName);\n',
        '    let type_get_name: TypeGetName = resolve!("il2cpp_type_get_name", TypeGetName);\n'
        '    let runtime_invoke: RuntimeInvoke = resolve!("il2cpp_runtime_invoke", RuntimeInvoke);\n'
        '    let object_get_class: ObjectGetClass = resolve!("il2cpp_object_get_class", ObjectGetClass);\n'
        '    let object_unbox: ObjectUnbox = resolve!("il2cpp_object_unbox", ObjectUnbox);\n'
    )

# Append the blueprint after the v8.5 mapper section.
if '=== NATIVE OFFER PAYLOAD BLUEPRINT v8.6 ===' not in t:
    anchor='        lines.push("\\nMAPPER GOAL: identify a factory path for InteropReference + TypedValue and distinguish human PersonMakeOfferForPlayer from AI/club-side transfer actions before enabling SEND.".to_string());\n'
    block=r'''        lines.push("\n=== NATIVE OFFER PAYLOAD BLUEPRINT v8.6 ===".to_string());
        lines.push("Read-only runtime blueprint: reference classes, InteropReference nested Pair layout, selected constructors/factories, and identifier singleton probes. No FM action is dispatched.".to_string());

        if let Some(ir)=find_class(assemblies,count,assembly_get_image,class_from_name,"SI.Interop","InteropReference"){
            lines.push("\nINTEROPREFERENCE NESTED TYPES:".to_string());
            lines.extend(blueprint_nested(ir,class_get_nested_types,class_get_name,class_get_namespace,class_get_fields,class_get_parent,field_get_name,field_get_type,field_get_offset,field_get_flags,type_get_name,class_get_methods,method_get_name,method_get_param_count,method_get_param,method_get_param_name,method_get_flags,method_get_return_type));
        }

        let candidates=blueprint_candidate_classes(assemblies,count,assembly_get_image,image_get_class_count,image_get_class,class_get_name,class_get_namespace);
        lines.push(format!("\nREFERENCE / TRANSFER CANDIDATES FOUND: {}",candidates.len()));
        for class in candidates{
            let cn=cstr(class_get_name(class)); let ns=cstr(class_get_namespace(class));
            lines.push(format!("\nBLUEPRINT CLASS {ns}.{cn} @ 0x{:X}",class as usize));
            lines.extend(describe_class_fields(class,class_get_fields,class_get_parent,class_get_name,class_get_namespace,field_get_name,field_get_type,field_get_offset,field_get_flags,type_get_name));
            lines.extend(blueprint_selected_methods(class,class_get_methods,method_get_name,method_get_param_count,method_get_param,method_get_param_name,method_get_flags,method_get_return_type,type_get_name));

            if let Some(s)=blueprint_invoke_zero(class,"get_Identifier",null_mut(),class_get_method,method_get_flags,runtime_invoke,object_get_class,class_get_name,class_get_namespace,class_is_valuetype,object_unbox){
                lines.push(format!("  READONLY PROBE {s}"));
            }
            let gi=CString::new("GetInstance").unwrap();
            let gim=class_get_method(class,gi.as_ptr(),0);
            if !gim.is_null(){
                let mut iflags=0u32; let flags=method_get_flags(gim,&mut iflags);
                if flags & METHOD_ATTRIBUTE_STATIC != 0{
                    let mut exc:*mut c_void=null_mut();
                    let instance=runtime_invoke(gim,null_mut(),null_mut(),&mut exc);
                    if exc.is_null() && !instance.is_null(){
                        lines.push(format!("  READONLY PROBE GetInstance: {}",blueprint_boxed_summary(instance,object_get_class,class_get_name,class_get_namespace,class_is_valuetype,object_unbox)));
                        if let Some(id)=blueprint_invoke_zero(class,"get_ID",instance,class_get_method,method_get_flags,runtime_invoke,object_get_class,class_get_name,class_get_namespace,class_is_valuetype,object_unbox){
                            lines.push(format!("  READONLY PROBE {id}"));
                        }
                    }else if !exc.is_null(){lines.push(format!("  READONLY PROBE GetInstance: EXCEPTION@0x{:X}",exc as usize));}
                }
            }
        }
        lines.push("\nV8.6 NEXT GATE: identify exact player + club InteropReference pair IDs and the action data shape. Only after those are certified do we enable a guarded native action dispatch.".to_string());
'''
    if anchor not in t: raise SystemExit('v8.6 mapper goal anchor missing')
    t=t.replace(anchor,anchor+block,1)

t=t.replace('Native Transfer Event Mapper v8.5','Native Offer Payload Blueprint v8.6')
helper.write_text(t,encoding='utf-8')

ui=Path.cwd()/'src/ui/player_panel.rs'
if ui.exists():
    s=ui.read_text(encoding='utf-8')
    s=s.replace('Native Transfer Event Mapper • v8.5','Native Offer Payload Blueprint • v8.6')
    s=s.replace('📋 FULL NATIVE TRANSFER EVENT MAP','📋 FULL NATIVE OFFER PAYLOAD BLUEPRINT')
    s=s.replace('MAP NATIVE TRANSFER EVENTS • SAFE','MAP NATIVE OFFER PAYLOAD • SAFE')
    ui.write_text(s,encoding='utf-8')

print('Element v8.6 Native Offer Payload Blueprint applied.')
