from pathlib import Path

root=Path.cwd()
ui=root/'src/ui/player_panel.rs'
if ui.exists():
    s=ui.read_text(encoding='utf-8')
    s=s.replace('Native Offer Native Property Code Map • v8.10','Native Offer Static PropertyID Decoder • v8.11')
    s=s.replace('DUMP NATIVE PROPERTY METHOD CODE • SAFE','DECODE NATIVE PROPERTY IDS • SAFE')
    s=s.replace('📋 FULL NATIVE PROPERTY CODE MAP','📋 FULL NATIVE PROPERTY ID MAP')
    ui.write_text(s,encoding='utf-8')

helper=Path(__file__).with_name('native_offer_helper.rs')
t=helper.read_text(encoding='utf-8')

if 'unsafe fn v811_decode_property_ids' not in t:
    marker='unsafe fn run_probe() -> Result<String, String> {'
    insert=r'''
fn v811_ascii4_le(v:u32)->String{
    let b=v.to_le_bytes();
    b.iter().map(|x| if x.is_ascii_graphic() || *x==b' ' {*x as char} else {'.'}).collect()
}

fn v811_ascii4_be(v:u32)->String{
    let b=v.to_be_bytes();
    b.iter().map(|x| if x.is_ascii_graphic() || *x==b' ' {*x as char} else {'.'}).collect()
}

unsafe fn v811_method_code_ptr(class:*mut c_void,name:&str,argc:i32,class_get_method:ClassGetMethodFromName)->Option<*const u8>{
    if class.is_null(){return None;}
    let cn=CString::new(name).ok()?;
    let m=class_get_method(class,cn.as_ptr(),argc);
    if m.is_null(){return None;}
    let p=*(m as *const *const u8);
    if p.is_null(){None}else{Some(p)}
}

unsafe fn v811_decode_return_count(class:*mut c_void,class_get_method:ClassGetMethodFromName)->Option<u32>{
    let p=v811_method_code_ptr(class,"GetPropertyCountInternal",0,class_get_method)?;
    let n=v810_memory_readable(p,32)?;
    if n<6{return None;}
    let b=std::slice::from_raw_parts(p,n);
    // Canonical IL2CPP tiny getter: mov eax, imm32 ; ret
    if b[0]==0xB8 && b[5]==0xC3{
        return Some(u32::from_le_bytes([b[1],b[2],b[3],b[4]]));
    }
    None
}

unsafe fn v811_decode_property_ids(
    label:&str,ns:&str,cn:&str,
    assemblies:*mut *const c_void,count:usize,
    assembly_get_image:AssemblyGetImage,class_from_name:ClassFromName,class_get_method:ClassGetMethodFromName,
)->Vec<String>{
    let mut out=Vec::new();
    let Some(class)=find_class(assemblies,count,assembly_get_image,class_from_name,ns,cn) else {
        out.push(format!("{label}: class {ns}.{cn} not found"));return out;
    };
    let expected=v811_decode_return_count(class,class_get_method);
    out.push(format!("{label}: class={ns}.{cn} expected_count={}",expected.map(|v|v.to_string()).unwrap_or_else(||"unknown".to_string())));
    let Some(code)=v811_method_code_ptr(class,"GetPropertiesInternal",1,class_get_method) else {
        out.push(format!("{label}: GetPropertiesInternal not found"));return out;
    };
    let wanted=128usize*1024;
    let Some(n)=v810_memory_readable(code,wanted) else {
        out.push(format!("{label}: GetPropertiesInternal page not readable"));return out;
    };
    let bytes=std::slice::from_raw_parts(code,n);
    let mut ids=Vec::<(usize,u32)>::new();
    // IL2CPP-generated Add(PropertyID) sequence observed on the exact FM27 build:
    // xor edx,edx ; mov ecx, imm32 ; call rel32
    if bytes.len()>=12{
        for i in 0..=bytes.len()-12{
            if bytes[i]==0x33 && bytes[i+1]==0xD2 && bytes[i+2]==0xB9 && bytes[i+7]==0xE8{
                let v=u32::from_le_bytes([bytes[i+3],bytes[i+4],bytes[i+5],bytes[i+6]]);
                ids.push((i+3,v));
                if let Some(e)=expected{
                    if ids.len()>=e as usize{break;}
                }
            }
            // Secondary shape seen when xor edx is separated from mov ecx by scheduling.
            if bytes[i]==0xB9 && bytes[i+5]==0xE8{
                let v=u32::from_le_bytes([bytes[i+1],bytes[i+2],bytes[i+3],bytes[i+4]]);
                let recent_xor = i>=2 && bytes[i-2]==0x33 && bytes[i-1]==0xD2;
                if recent_xor && !ids.iter().any(|(o,_)|*o==i+1){
                    ids.push((i+1,v));
                    if let Some(e)=expected{
                        if ids.len()>=e as usize{break;}
                    }
                }
            }
        }
    }
    out.push(format!("{label}: decoded_count={} scanned_bytes={}",ids.len(),n));
    for (idx,(off,v)) in ids.iter().enumerate(){
        out.push(format!("{label}: PROPERTY[{idx:03}] id=0x{v:08X} le=\"{}\" be=\"{}\" code_off=0x{off:X}",v811_ascii4_le(*v),v811_ascii4_be(*v)));
    }
    if let Some(e)=expected{
        out.push(format!("{label}: GATE expected={e} decoded={} match={}",ids.len(),ids.len()==e as usize));
    }else{
        out.push(format!("{label}: GATE expected=unknown decoded={}",ids.len()));
    }
    out
}
'''
    if marker not in t: raise SystemExit('v8.11 run_probe marker missing')
    t=t.replace(marker,insert+marker,1)

if '=== STATIC NATIVE PROPERTY ID DECODER v8.11 ===' not in t:
    gate='            lines.push("V8.10 GATE: inspect native bytes/FourCC immediates for property constants without executing GetProperties. Candidate constants become inputs for a later guarded static metadata probe only after cross-class correlation.".to_string());\n'
    if gate not in t: raise SystemExit('v8.11 v8.10 gate marker missing')
    block=r'''            lines.push("\n=== STATIC NATIVE PROPERTY ID DECODER v8.11 ===".to_string());
            lines.push("Zero-invoke decoder. Reads GetPropertyCountInternal/GetPropertiesInternal machine code only, then decodes the IL2CPP Add(PropertyID) instruction pattern observed on this FM27 build.".to_string());
            for (label,ns,cn) in [
                ("ACTION","FM.UI","ActionReference"),
                ("SESSION","FM.UI","TransferOfferEditSessionReference"),
                ("PERSON_TRANSFER_OFFER","FM.UI","PersonTransferOfferReference"),
                ("PLAYER_TRANSFER_OFFER","FM.UI","PlayerTransferOfferReference"),
                ("TRANSFER_BUTTON_PROPS","FM.UI","TransferOfferActionButtonPropsReference"),
            ]{
                lines.extend(v811_decode_property_ids(label,ns,cn,assemblies,count,assembly_get_image,class_from_name,class_get_method));
            }
            lines.push("V8.11 GATE: classes with expected_count == decoded_count now have a complete ordered PropertyID list without invoking FM managed property APIs. Use cross-reference overlap and semantic FourCC-like IDs to build the next guarded payload map.".to_string());
'''
    t=t.replace(gate,gate+block,1)

t=t.replace('Native Offer Native Property Code Map v8.10','Native Offer Static PropertyID Decoder v8.11')
helper.write_text(t,encoding='utf-8')
print('Element v8.11 Static PropertyID Decoder applied.')
