from pathlib import Path

helper=Path(__file__).with_name('native_offer_helper.rs')
t=helper.read_text(encoding='utf-8')

# Extend the live IL2CPP inspector with class/method enumeration and ActionID discovery.
if 'type ImageGetClassCount' not in t:
    t=t.replace(
        'type AssemblyGetImage = unsafe extern "C" fn(*const c_void) -> *const c_void;\n',
        'type AssemblyGetImage = unsafe extern "C" fn(*const c_void) -> *const c_void;\n'
        'type ImageGetClassCount = unsafe extern "C" fn(*const c_void) -> usize;\n'
        'type ImageGetClass = unsafe extern "C" fn(*const c_void, usize) -> *mut c_void;\n'
    )
if 'type ClassGetMethods' not in t:
    t=t.replace(
        'type ClassGetMethodFromName = unsafe extern "C" fn(*mut c_void, *const c_char, i32) -> *const c_void;\n',
        'type ClassGetMethodFromName = unsafe extern "C" fn(*mut c_void, *const c_char, i32) -> *const c_void;\n'
        'type ClassGetMethods = unsafe extern "C" fn(*mut c_void, *mut *mut c_void) -> *const c_void;\n'
    )
if 'type MethodGetReturnType' not in t:
    t=t.replace(
        'type MethodGetFlags = unsafe extern "C" fn(*const c_void, *mut u32) -> u32;\n',
        'type MethodGetFlags = unsafe extern "C" fn(*const c_void, *mut u32) -> u32;\n'
        'type MethodGetReturnType = unsafe extern "C" fn(*const c_void) -> *const c_void;\n'
    )
if 'type FieldStaticGetValue' not in t:
    t=t.replace(
        'type FieldGetFlags = unsafe extern "C" fn(*mut c_void) -> u32;\n',
        'type FieldGetFlags = unsafe extern "C" fn(*mut c_void) -> u32;\n'
        'type FieldStaticGetValue = unsafe extern "C" fn(*mut c_void, *mut c_void);\n'
    )

if 'unsafe fn mapper_describe_methods' not in t:
    marker='unsafe fn run_probe() -> Result<String, String> {'
    insert=r'''
unsafe fn mapper_describe_methods(
    class: *mut c_void,
    class_get_methods: ClassGetMethods,
    method_get_name: MethodGetName,
    method_get_param_count: MethodGetParamCount,
    method_get_param: MethodGetParam,
    method_get_param_name: MethodGetParamName,
    method_get_flags: MethodGetFlags,
    method_get_return_type: MethodGetReturnType,
    type_get_name: TypeGetName,
) -> Vec<String> {
    let mut out=Vec::new();
    let mut iter: *mut c_void = null_mut();
    let mut seen=0usize;
    loop {
        let method=class_get_methods(class,&mut iter);
        if method.is_null(){break;}
        seen+=1;
        if seen>192 { out.push("  METHOD scan stopped after 192 entries".to_string()); break; }
        let name=cstr(method_get_name(method));
        let argc=method_get_param_count(method);
        let mut iflags=0u32;
        let flags=method_get_flags(method,&mut iflags);
        let ret=method_get_return_type(method);
        let ret_name=if ret.is_null(){"<null-type>".to_string()}else{cstr(type_get_name(ret))};
        let mut args=Vec::new();
        for i in 0..argc {
            let ty=method_get_param(method,i);
            let tn=if ty.is_null(){"<null-type>".to_string()}else{cstr(type_get_name(ty))};
            args.push(format!("{}:{}",cstr(method_get_param_name(method,i)),tn));
        }
        out.push(format!("  METHOD {name}({}) -> {ret_name} flags=0x{flags:08X} static={}",args.join(", "),if flags & METHOD_ATTRIBUTE_STATIC != 0{"yes"}else{"no"}));
    }
    out
}

unsafe fn mapper_find_classes(
    assemblies: *mut *const c_void,
    assembly_count: usize,
    assembly_get_image: AssemblyGetImage,
    image_get_class_count: ImageGetClassCount,
    image_get_class: ImageGetClass,
    class_get_name: ClassGetName,
    wanted: &[&str],
) -> Vec<*mut c_void> {
    let mut out=Vec::new();
    for ai in 0..assembly_count {
        let asm=*assemblies.add(ai);
        if asm.is_null(){continue;}
        let image=assembly_get_image(asm);
        if image.is_null(){continue;}
        let count=image_get_class_count(image);
        for ci in 0..count {
            let class=image_get_class(image,ci);
            if class.is_null(){continue;}
            let name=cstr(class_get_name(class));
            if wanted.iter().any(|x|*x==name){out.push(class);}
        }
    }
    out
}

unsafe fn mapper_action_ids(
    class: *mut c_void,
    class_get_fields: ClassGetFields,
    field_get_name: FieldGetName,
    field_get_flags: FieldGetFlags,
    field_static_get_value: FieldStaticGetValue,
) -> Vec<String> {
    let mut out=Vec::new();
    let mut iter: *mut c_void=null_mut();
    let needles=["offer","transfer","proposal","loan","intermediar","exchange","sell","buy","player"];
    loop {
        let field=class_get_fields(class,&mut iter);
        if field.is_null(){break;}
        let name=cstr(field_get_name(field));
        let low=name.to_ascii_lowercase();
        if !needles.iter().any(|n|low.contains(n)){continue;}
        let flags=field_get_flags(field);
        let mut value=0u32;
        field_static_get_value(field,(&mut value as *mut u32).cast::<c_void>());
        out.push(format!("  ACTION {name} = 0x{value:08X} ({value}) flags=0x{flags:08X}"));
    }
    out.sort();
    out
}

'''
    if marker not in t: raise SystemExit('v8.5 helper run_probe marker missing')
    t=t.replace(marker,insert+marker,1)

# Resolve mapper exports.
if 'il2cpp_image_get_class_count' not in t:
    t=t.replace(
        '    let assembly_get_image: AssemblyGetImage = resolve!("il2cpp_assembly_get_image", AssemblyGetImage);\n',
        '    let assembly_get_image: AssemblyGetImage = resolve!("il2cpp_assembly_get_image", AssemblyGetImage);\n'
        '    let image_get_class_count: ImageGetClassCount = resolve!("il2cpp_image_get_class_count", ImageGetClassCount);\n'
        '    let image_get_class: ImageGetClass = resolve!("il2cpp_image_get_class", ImageGetClass);\n'
    )
if 'il2cpp_class_get_methods' not in t:
    t=t.replace(
        '    let class_get_method: ClassGetMethodFromName = resolve!("il2cpp_class_get_method_from_name", ClassGetMethodFromName);\n',
        '    let class_get_method: ClassGetMethodFromName = resolve!("il2cpp_class_get_method_from_name", ClassGetMethodFromName);\n'
        '    let class_get_methods: ClassGetMethods = resolve!("il2cpp_class_get_methods", ClassGetMethods);\n'
    )
if 'il2cpp_method_get_return_type' not in t:
    t=t.replace(
        '    let method_get_flags: MethodGetFlags = resolve!("il2cpp_method_get_flags", MethodGetFlags);\n',
        '    let method_get_flags: MethodGetFlags = resolve!("il2cpp_method_get_flags", MethodGetFlags);\n'
        '    let method_get_return_type: MethodGetReturnType = resolve!("il2cpp_method_get_return_type", MethodGetReturnType);\n'
    )
if 'il2cpp_field_static_get_value' not in t:
    t=t.replace(
        '    let field_get_flags: FieldGetFlags = resolve!("il2cpp_field_get_flags", FieldGetFlags);\n',
        '    let field_get_flags: FieldGetFlags = resolve!("il2cpp_field_get_flags", FieldGetFlags);\n'
        '    let field_static_get_value: FieldStaticGetValue = resolve!("il2cpp_field_static_get_value", FieldStaticGetValue);\n'
    )

if 'NATIVE TRANSFER EVENT MAPPER' not in t:
    anchor='        lines.push("Goal: certify dispatcher signature + instance/static ownership before enabling SEND NATIVE AI OFFER.".to_string());\n'
    block=r'''        lines.push("\n=== NATIVE TRANSFER EVENT MAPPER v8.5 ===".to_string());
        lines.push("Enumerating runtime factories/value wrappers/transfer reference types and transfer-related ActionID constants. No action is invoked.".to_string());
        let wanted=[
            "FMInteropReferenceFactory","IInteropReferenceFactory","InteropReference","GenericActionEvent",
            "TypedValue","TypedValueVisualFunctionLibrary","TransferOfferEditSession","TransferOfferClientContext",
            "PlayerTransferOfferReference","PersonTransferOfferReference","TransferOfferActionButtonPropsReference","ActionID"
        ];
        let classes=mapper_find_classes(assemblies,count,assembly_get_image,image_get_class_count,image_get_class,class_get_name,&wanted);
        for class in classes {
            let cn=cstr(class_get_name(class));
            let ns=cstr(class_get_namespace(class));
            lines.push(format!("\nMAPPER CLASS {ns}.{cn} @ 0x{:X}",class as usize));
            if cn=="ActionID" {
                lines.extend(mapper_action_ids(class,class_get_fields,field_get_name,field_get_flags,field_static_get_value));
            } else {
                lines.extend(describe_class_fields(class,class_get_fields,class_get_parent,class_get_name,class_get_namespace,field_get_name,field_get_type,field_get_offset,field_get_flags,type_get_name));
                lines.extend(mapper_describe_methods(class,class_get_methods,method_get_name,method_get_param_count,method_get_param,method_get_param_name,method_get_flags,method_get_return_type,type_get_name));
            }
        }
        lines.push("\nMAPPER GOAL: identify a factory path for InteropReference + TypedValue and distinguish human PersonMakeOfferForPlayer from AI/club-side transfer actions before enabling SEND.".to_string());
'''
    if anchor not in t: raise SystemExit('v8.5 helper header anchor missing')
    t=t.replace(anchor,anchor+block,1)

# Version stamp.
t=t.replace('Native Offer Inspector v8.4.4','Native Transfer Event Mapper v8.5')
helper.write_text(t,encoding='utf-8')

# UI wording; existing multiline report viewer remains reusable.
ui=Path.cwd()/'src/ui/player_panel.rs'
if ui.exists():
    s=ui.read_text(encoding='utf-8')
    s=s.replace('Native AI Offer Inspector • v8.4.4','Native Transfer Event Mapper • v8.5')
    s=s.replace('📋 FULL NATIVE OFFER INSPECTOR REPORT','📋 FULL NATIVE TRANSFER EVENT MAP')
    s=s.replace('PROBE NATIVE OFFER DISPATCHER • SAFE','MAP NATIVE TRANSFER EVENTS • SAFE')
    ui.write_text(s,encoding='utf-8')

print('Element v8.5 Native Transfer Event Mapper applied.')