from pathlib import Path

root=Path.cwd()
ui=root/'src/ui/player_panel.rs'
if ui.exists():
    s=ui.read_text(encoding='utf-8')
    s=s.replace('Native Offer Static PropertyID Decoder • v8.11','Native Offer Inheritance PropertyID Decoder • v8.12')
    s=s.replace('DECODE NATIVE PROPERTY IDS • SAFE','DECODE COMPLETE PROPERTY IDS • SAFE')
    s=s.replace('📋 FULL NATIVE PROPERTY ID MAP','📋 FULL INHERITANCE PROPERTY ID MAP')
    ui.write_text(s,encoding='utf-8')

helper=Path(__file__).with_name('native_offer_helper.rs')
t=helper.read_text(encoding='utf-8')

if 'struct V812CountPlan' not in t:
    marker='unsafe fn run_probe() -> Result<String, String> {'
    insert=r'''
#[derive(Clone,Copy)]
struct V812CountPlan {
    total:u32,
    own:u32,
    inherited:bool,
}

unsafe fn v812_count_plan(
    class:*mut c_void,
    class_get_method:ClassGetMethodFromName,
    class_get_parent:ClassGetParent,
    depth:usize,
)->Option<V812CountPlan>{
    if class.is_null() || depth>8{return None;}
    let p=v811_method_code_ptr(class,"GetPropertyCountInternal",0,class_get_method)?;
    let n=v810_memory_readable(p,64)?;
    if n<6{return None;}
    let b=std::slice::from_raw_parts(p,n);
    // Direct tiny getter: mov eax, imm32 ; ret
    if b[0]==0xB8 && b[5]==0xC3{
        let v=u32::from_le_bytes([b[1],b[2],b[3],b[4]]);
        return Some(V812CountPlan{total:v,own:v,inherited:false});
    }
    // Inherited IL2CPP shape observed on TransferOfferEditSessionReference:
    // ... call parent_count ; add eax, imm32 ; ... ret
    let mut add_imm=None;
    for i in 0..b.len().saturating_sub(5){
        if b[i]==0x05 {
            add_imm=Some(u32::from_le_bytes([b[i+1],b[i+2],b[i+3],b[i+4]]));
            break;
        }
    }
    if let Some(own)=add_imm{
        let parent=class_get_parent(class);
        if !parent.is_null(){
            if let Some(pp)=v812_count_plan(parent,class_get_method,class_get_parent,depth+1){
                return Some(V812CountPlan{total:pp.total.saturating_add(own),own,inherited:true});
            }
        }
    }
    None
}

unsafe fn v812_decode_own_ids(
    class:*mut c_void,
    own_expected:u32,
    class_get_method:ClassGetMethodFromName,
)->Vec<(usize,u32)>{
    let mut ids=Vec::<(usize,u32)>::new();
    let Some(code)=v811_method_code_ptr(class,"GetPropertiesInternal",1,class_get_method) else {return ids;};
    let wanted=128usize*1024;
    let Some(n)=v810_memory_readable(code,wanted) else {return ids;};
    let bytes=std::slice::from_raw_parts(code,n);
    if bytes.len()<12{return ids;}
    for i in 0..=bytes.len()-12{
        if bytes[i]==0x33 && bytes[i+1]==0xD2 && bytes[i+2]==0xB9 && bytes[i+7]==0xE8{
            let v=u32::from_le_bytes([bytes[i+3],bytes[i+4],bytes[i+5],bytes[i+6]]);
            ids.push((i+3,v));
            if ids.len()>=own_expected as usize{break;}
        }
    }
    ids
}

unsafe fn v812_decode_hierarchy(
    label:&str,
    class:*mut c_void,
    class_get_method:ClassGetMethodFromName,
    class_get_parent:ClassGetParent,
    class_get_name:ClassGetName,
    class_get_namespace:ClassGetNamespace,
    depth:usize,
)->(Vec<String>,Vec<u32>,Option<u32>){
    let mut out=Vec::new();
    if class.is_null() || depth>8{return (out,Vec::new(),None);}
    let ns=cstr(class_get_namespace(class));
    let cn=cstr(class_get_name(class));
    let plan=v812_count_plan(class,class_get_method,class_get_parent,0);
    let Some(plan)=plan else {
        out.push(format!("{label}: depth={depth} class={ns}.{cn} count_plan=unknown"));
        return (out,Vec::new(),None);
    };
    out.push(format!("{label}: depth={depth} class={ns}.{cn} total_count={} own_count={} inherited={}",plan.total,plan.own,plan.inherited));

    let mut combined=Vec::<u32>::new();
    if plan.inherited{
        let parent=class_get_parent(class);
        if !parent.is_null(){
            let (mut parent_lines,parent_ids,parent_total)=v812_decode_hierarchy(
                &format!("{label}.PARENT"),parent,class_get_method,class_get_parent,class_get_name,class_get_namespace,depth+1
            );
            out.append(&mut parent_lines);
            if let Some(pt)=parent_total{
                out.push(format!("{label}: inherited_count={pt}"));
            }
            combined.extend(parent_ids);
        }
    }

    let own=v812_decode_own_ids(class,plan.own,class_get_method);
    out.push(format!("{label}: own_decoded={} own_expected={} own_match={}",own.len(),plan.own,own.len()==plan.own as usize));
    for (idx,(off,v)) in own.iter().enumerate(){
        out.push(format!("{label}: OWN_PROPERTY[{idx:03}] id=0x{v:08X} le=\"{}\" be=\"{}\" code_off=0x{off:X}",v811_ascii4_le(*v),v811_ascii4_be(*v)));
        combined.push(*v);
    }
    out.push(format!("{label}: COMPLETE_COUNT={} expected_total={} match={}",combined.len(),plan.total,combined.len()==plan.total as usize));
    for (idx,v) in combined.iter().enumerate(){
        out.push(format!("{label}: COMPLETE_PROPERTY[{idx:03}] id=0x{v:08X} le=\"{}\" be=\"{}\"",v811_ascii4_le(*v),v811_ascii4_be(*v)));
    }
    (out,combined,Some(plan.total))
}

unsafe fn v812_decode_class(
    label:&str,ns:&str,cn:&str,
    assemblies:*mut *const c_void,count:usize,
    assembly_get_image:AssemblyGetImage,class_from_name:ClassFromName,class_get_method:ClassGetMethodFromName,
    class_get_parent:ClassGetParent,class_get_name:ClassGetName,class_get_namespace:ClassGetNamespace,
)->Vec<String>{
    let Some(class)=find_class(assemblies,count,assembly_get_image,class_from_name,ns,cn) else {
        return vec![format!("{label}: class {ns}.{cn} not found")];
    };
    let (mut lines,_,_)=v812_decode_hierarchy(label,class,class_get_method,class_get_parent,class_get_name,class_get_namespace,0);
    lines
}
'''
    if marker not in t: raise SystemExit('v8.12 run_probe marker missing')
    t=t.replace(marker,insert+marker,1)

if '=== INHERITANCE-AWARE PROPERTY ID DECODER v8.12 ===' not in t:
    gate='            lines.push("V8.11 GATE: classes with expected_count == decoded_count now have a complete ordered PropertyID list without invoking FM managed property APIs. Use cross-reference overlap and semantic FourCC-like IDs to build the next guarded payload map.".to_string());\n'
    if gate not in t: raise SystemExit('v8.12 v8.11 gate marker missing')
    block=r'''            lines.push("\n=== INHERITANCE-AWARE PROPERTY ID DECODER v8.12 ===".to_string());
            lines.push("Zero-invoke inheritance decoder. Supports direct constant counts and parent-count + ADD EAX,imm32 IL2CPP getters, then decodes only each class own PropertyIDs and concatenates parent maps.".to_string());
            for (label,ns,cn) in [
                ("ACTION","FM.UI","ActionReference"),
                ("SESSION","FM.UI","TransferOfferEditSessionReference"),
                ("PERSON_TRANSFER_OFFER","FM.UI","PersonTransferOfferReference"),
                ("PLAYER_TRANSFER_OFFER","FM.UI","PlayerTransferOfferReference"),
                ("TRANSFER_BUTTON_PROPS","FM.UI","TransferOfferActionButtonPropsReference"),
            ]{
                lines.extend(v812_decode_class(label,ns,cn,assemblies,count,assembly_get_image,class_from_name,class_get_method,class_get_parent,class_get_name,class_get_namespace));
            }
            lines.push("V8.12 GATE: SESSION must report own_match=true and COMPLETE_COUNT == expected_total. Once green, use COMPLETE_PROPERTY overlap across session/player-offer/action references for the semantic payload map.".to_string());
'''
    t=t.replace(gate,gate+block,1)

t=t.replace('Native Offer Static PropertyID Decoder v8.11','Native Offer Inheritance PropertyID Decoder v8.12')
helper.write_text(t,encoding='utf-8')
print('Element v8.12 Inheritance-aware PropertyID Decoder applied.')
