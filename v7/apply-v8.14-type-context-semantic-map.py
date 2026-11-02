from pathlib import Path

root=Path.cwd()
ui=root/'src/ui/player_panel.rs'
if ui.exists():
    s=ui.read_text(encoding='utf-8')
    s=s.replace('Native Offer Semantic Property Mapper • v8.13.1','Native Offer Type + Context Semantic Map • v8.14')
    s=s.replace('MAP OFFER PROPERTY SEMANTICS • PINNED','MAP PROPERTY TYPES + CONTEXTS • SAFE')
    s=s.replace('📋 FULL NATIVE OFFER SEMANTIC MAP','📋 FULL NATIVE OFFER TYPE / CONTEXT MAP')
    ui.write_text(s,encoding='utf-8')

helper=Path(__file__).with_name('native_offer_helper.rs')
t=helper.read_text(encoding='utf-8')

if 'type FieldStaticGetValueV814' not in t:
    marker='type TypeGetName = unsafe extern "C" fn(*const c_void) -> *mut c_char;\n'
    insert='type FieldStaticGetValueV814 = unsafe extern "C" fn(*mut c_void, *mut c_void);\n'
    if marker not in t: raise SystemExit('v8.14 type marker missing')
    t=t.replace(marker,marker+insert,1)

if 'unsafe fn v814_dump_binding_kind' not in t:
    marker='unsafe fn run_probe() -> Result<String, String> {'
    insert=r'''
unsafe fn v814_dump_binding_kind(
    assemblies:*mut *const c_void,count:usize,
    assembly_get_image:AssemblyGetImage,class_from_name:ClassFromName,
    class_get_fields:ClassGetFields,field_get_name:FieldGetName,field_get_type:FieldGetType,
    field_get_flags:FieldGetFlags,field_get_offset:FieldGetOffset,type_get_name:TypeGetName,
    field_static_get_value:FieldStaticGetValueV814,
)->Vec<String>{
    let mut out=Vec::new();
    let Some(class)=find_class(assemblies,count,assembly_get_image,class_from_name,"SI.Bindable.Reference.Core","BindingKind") else {
        out.push("BINDING_KIND: class SI.Bindable.Reference.Core.BindingKind not found".to_string());
        return out;
    };
    out.push(format!("BINDING_KIND: class@0x{:X}",class as usize));
    let mut iter:*mut c_void=null_mut();
    let mut seen=0usize;
    loop{
        let field=class_get_fields(class,&mut iter);
        if field.is_null(){break;}
        seen+=1;
        if seen>64{out.push("BINDING_KIND: stopped after 64 fields".to_string());break;}
        let name=cstr(field_get_name(field));
        let ty=field_get_type(field);
        let tn=if ty.is_null(){"<null-type>".to_string()}else{cstr(type_get_name(ty))};
        let flags=field_get_flags(field);
        let off=field_get_offset(field);
        if flags & FIELD_ATTRIBUTE_STATIC != 0 && tn.contains("BindingKind"){
            let mut value:i32=0x5A5A5A5A_u32 as i32;
            field_static_get_value(field,(&mut value as *mut i32).cast::<c_void>());
            out.push(format!("BINDING_KIND: FIELD name=\"{name}\" type=\"{tn}\" flags=0x{flags:08X} offset=0x{off:X} static_value={value}"));
        }else{
            out.push(format!("BINDING_KIND: FIELD name=\"{name}\" type=\"{tn}\" flags=0x{flags:08X} offset=0x{off:X}"));
        }
    }
    out
}

fn v814_hex_slice(bytes:&[u8],start:usize,end:usize)->String{
    bytes[start..end].iter().map(|b|format!("{b:02X}")).collect::<Vec<_>>().join(" ")
}

unsafe fn v814_context_windows(
    label:&str,ns:&str,cn:&str,ids:&[u32],
    assemblies:*mut *const c_void,count:usize,
    assembly_get_image:AssemblyGetImage,class_from_name:ClassFromName,class_get_method:ClassGetMethodFromName,
)->Vec<String>{
    let mut out=Vec::new();
    let Some(class)=find_class(assemblies,count,assembly_get_image,class_from_name,ns,cn) else {
        out.push(format!("{label}: class {ns}.{cn} not found"));return out;
    };
    let Some(code)=v811_method_code_ptr(class,"GetContextsInternal",2,class_get_method) else {
        out.push(format!("{label}: GetContextsInternal not found"));return out;
    };
    let Some(n)=v810_memory_readable(code,64usize*1024) else {
        out.push(format!("{label}: GetContextsInternal code not readable"));return out;
    };
    let bytes=std::slice::from_raw_parts(code,n);
    out.push(format!("{label}: GetContextsInternal methodPointer=0x{:X} readable_bytes={n}",code as usize));
    for id in ids{
        let needle=id.to_le_bytes();
        let mut hits=Vec::new();
        if n>=4{
            for i in 0..=n-4{
                if bytes[i..i+4]==needle{
                    hits.push(i);
                    if hits.len()>=12{break;}
                }
            }
        }
        out.push(format!("{label}: CONTEXT_PROPERTY id=0x{id:08X} be=\"{}\" immediate_hits={}",v811_ascii4_be(*id),hits.len()));
        for (hi,pos) in hits.iter().enumerate(){
            let start=pos.saturating_sub(32);
            let end=(*pos+192).min(n);
            out.push(format!("{label}: CONTEXT_WINDOW id=0x{id:08X} hit={hi} code_off=0x{pos:X} range=0x{start:X}..0x{end:X} bytes={}",v814_hex_slice(bytes,start,end)));
            let scan_end=(*pos+192).min(n);
            let mut candidates=0usize;
            let mut j=*pos;
            while j+5<=scan_end && candidates<24{
                let mut imm:Option<(usize,u32,&str)>=None;
                match bytes[j]{
                    0xB8|0xB9|0xBA|0xBB|0xBE|0xBF=>{
                        imm=Some((j+1,u32::from_le_bytes([bytes[j+1],bytes[j+2],bytes[j+3],bytes[j+4]]),"mov-r32-imm32"));
                    },
                    0x41 if j+6<=scan_end && matches!(bytes[j+1],0xB8|0xB9|0xBA|0xBB|0xBE|0xBF)=>{
                        imm=Some((j+2,u32::from_le_bytes([bytes[j+2],bytes[j+3],bytes[j+4],bytes[j+5]]),"mov-r8+-imm32"));
                    },
                    _=>{}
                }
                if let Some((off,v,kind))=imm{
                    if v!=*id{
                        out.push(format!("{label}: CONTEXT_CANDIDATE property=0x{id:08X} at=0x{off:X} op={kind} imm=0x{v:08X} be=\"{}\" le=\"{}\"",v811_ascii4_be(v),v811_ascii4_le(v)));
                        candidates+=1;
                    }
                }
                j+=1;
            }
        }
    }
    out
}
'''
    if marker not in t: raise SystemExit('v8.14 run_probe marker missing')
    t=t.replace(marker,insert+marker,1)

if 'let v814_field_static_get_value: FieldStaticGetValueV814' not in t:
    marker='    let type_get_name: TypeGetName = resolve!("il2cpp_type_get_name", TypeGetName);\n'
    insert='    let v814_field_static_get_value: FieldStaticGetValueV814 = resolve!("il2cpp_field_static_get_value", FieldStaticGetValueV814);\n'
    if marker not in t: raise SystemExit('v8.14 resolver marker missing')
    t=t.replace(marker,marker+insert,1)

if '=== TYPE + CONTEXT SEMANTIC MAP v8.14 ===' not in t:
    gate='                lines.push("V8.13 GATE: use exact desc + binding_kind values above to identify player/club/offer/status/fee-related properties. Do not enable native dispatch until semantic identities are certified.".to_string());\n'
    if gate not in t: raise SystemExit('v8.14 v8.13 gate marker missing')
    block=r'''                lines.push("\n=== TYPE + CONTEXT SEMANTIC MAP v8.14 ===".to_string());
                lines.push("Read-only semantic follow-up. Maps BindingKind enum metadata/values and reads GetContextsInternal machine code windows for reference-like transfer properties. No managed List<ContextID> is constructed; no action/write/dispatch occurs.".to_string());
                lines.extend(v814_dump_binding_kind(assemblies,count,assembly_get_image,class_from_name,class_get_fields,field_get_name,field_get_type,field_get_flags,field_get_offset,type_get_name,v814_field_static_get_value));
                if let Some(context_id_class)=find_class(assemblies,count,assembly_get_image,class_from_name,"SI.Bindable.Reference.Core","ContextID"){
                    lines.push("CONTEXT_ID METADATA:".to_string());
                    lines.extend(describe_class_fields(context_id_class,class_get_fields,class_get_parent,class_get_name,class_get_namespace,field_get_name,field_get_type,field_get_offset,field_get_flags,type_get_name));
                }else{
                    lines.push("CONTEXT_ID METADATA: class SI.Bindable.Reference.Core.ContextID not found".to_string());
                }
                let player_ref_ids:[u32;3]=[0x70657273,0x544F6274,0x544F7374];
                let person_ref_ids:[u32;1]=[0x31362020];
                lines.extend(v814_context_windows("PLAYER_TRANSFER_OFFER_CONTEXT","FM.UI","PlayerTransferOfferReference",&player_ref_ids,assemblies,count,assembly_get_image,class_from_name,class_get_method));
                lines.extend(v814_context_windows("SESSION_CONTEXT","FM.UI","TransferOfferEditSessionReference",&player_ref_ids,assemblies,count,assembly_get_image,class_from_name,class_get_method));
                lines.extend(v814_context_windows("PERSON_TRANSFER_OFFER_CONTEXT","FM.UI","PersonTransferOfferReference",&person_ref_ids,assemblies,count,assembly_get_image,class_from_name,class_get_method));
                lines.push("V8.14 GATE: correlate BindingKind names and GetContextsInternal immediate candidates for pers/TObt/TOst. Only certified reference contexts may enter the dry-run native offer payload builder.".to_string());
'''
    t=t.replace(gate,gate+block,1)

t=t.replace('Native Offer Semantic Property Mapper v8.13','Native Offer Type + Context Semantic Map v8.14')
helper.write_text(t,encoding='utf-8')
print('Element v8.14 Type + Context Semantic Map applied.')
