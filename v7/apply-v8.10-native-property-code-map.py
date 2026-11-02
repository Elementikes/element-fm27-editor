from pathlib import Path

root=Path.cwd()
ui=root/'src/ui/player_panel.rs'
if ui.exists():
    s=ui.read_text(encoding='utf-8')
    s=s.replace('Native Offer Safe Property API Inspector • v8.9.1','Native Offer Native Property Code Map • v8.10')
    s=s.replace('INSPECT PROPERTY API SIGNATURES • SAFE','DUMP NATIVE PROPERTY METHOD CODE • SAFE')
    s=s.replace('📋 FULL NATIVE OFFER SAFE PROPERTY API REPORT','📋 FULL NATIVE PROPERTY CODE MAP')
    ui.write_text(s,encoding='utf-8')

helper=Path(__file__).with_name('native_offer_helper.rs')
t=helper.read_text(encoding='utf-8')

if 'struct V810MemoryBasicInformation' not in t:
    marker='const FIELD_ATTRIBUTE_STATIC: u32 = 0x0010;\n'
    insert=r'''

#[repr(C)]
struct V810MemoryBasicInformation {
    base_address: *mut c_void,
    allocation_base: *mut c_void,
    allocation_protect: u32,
    partition_id: u16,
    _alignment1: u16,
    region_size: usize,
    state: u32,
    protect: u32,
    typ: u32,
}

const V810_MEM_COMMIT:u32=0x1000;
const V810_PAGE_NOACCESS:u32=0x01;
const V810_PAGE_GUARD:u32=0x100;
'''
    if marker not in t: raise SystemExit('v8.10 constants marker missing')
    t=t.replace(marker,marker+insert,1)

if 'fn VirtualQuery(' not in t:
    marker='    fn CloseHandle(hObject: Handle) -> i32;\n'
    insert='    fn VirtualQuery(lpAddress: *const c_void, lpBuffer: *mut V810MemoryBasicInformation, dwLength: usize) -> usize;\n'
    if marker not in t: raise SystemExit('v8.10 kernel32 marker missing')
    t=t.replace(marker,marker+insert,1)

if 'unsafe fn v810_dump_native_method_code' not in t:
    marker='unsafe fn run_probe() -> Result<String, String> {'
    insert=r'''
unsafe fn v810_memory_readable(ptr:*const u8, wanted:usize)->Option<usize>{
    if ptr.is_null(){return None;}
    let mut mbi=V810MemoryBasicInformation{
        base_address:null_mut(), allocation_base:null_mut(), allocation_protect:0,
        partition_id:0, _alignment1:0, region_size:0, state:0, protect:0, typ:0,
    };
    let n=VirtualQuery(ptr.cast::<c_void>(), &mut mbi, std::mem::size_of::<V810MemoryBasicInformation>());
    if n==0 || mbi.state!=V810_MEM_COMMIT || (mbi.protect & V810_PAGE_NOACCESS)!=0 || (mbi.protect & V810_PAGE_GUARD)!=0{return None;}
    let base=mbi.base_address as usize;
    let p=ptr as usize;
    if p<base{return None;}
    let off=p-base;
    if off>=mbi.region_size{return None;}
    Some(std::cmp::min(wanted,mbi.region_size-off))
}

unsafe fn v810_dump_native_method_code(
    label:&str,
    class:*mut c_void,
    method_name:&str,
    argc:i32,
    class_get_method:ClassGetMethodFromName,
)->Vec<String>{
    let mut out=Vec::new();
    if class.is_null(){out.push(format!("{label}: class=<null>"));return out;}
    let Ok(cn)=CString::new(method_name) else {out.push(format!("{label}: invalid method name"));return out;};
    let method=class_get_method(class,cn.as_ptr(),argc);
    if method.is_null(){out.push(format!("{label}: {method_name}/{argc} not found"));return out;}
    let code=*(method as *const *const u8);
    let virtual_code=*((method as *const *const u8).add(1));
    out.push(format!("{label}: MethodInfo=0x{:X} methodPointer=0x{:X} virtualMethodPointer=0x{:X}",method as usize,code as usize,virtual_code as usize));
    let Some(n)=v810_memory_readable(code,256) else {out.push(format!("{label}: methodPointer page is not safely readable; skipped"));return out;};
    if n==0{return out;}
    let bytes=std::slice::from_raw_parts(code,n);
    out.push(format!("{label}: CODE_BYTES={n}"));
    for (row,ch) in bytes.chunks(16).enumerate(){
        let hex=ch.iter().map(|b|format!("{b:02X}")).collect::<Vec<_>>().join(" ");
        out.push(format!("{label}: +0x{:03X}: {hex}",row*16));
    }
    let mut fourcc=Vec::<(usize,u32,String)>::new();
    if bytes.len()>=4{
        for i in 0..=bytes.len()-4{
            let s=&bytes[i..i+4];
            if s.iter().all(|b|b.is_ascii_alphanumeric() || matches!(*b,b'_'|b'-'|b' ')){
                let v=u32::from_le_bytes([s[0],s[1],s[2],s[3]]);
                let txt=String::from_utf8_lossy(s).into_owned();
                if !fourcc.iter().any(|(_,x,_)|*x==v){fourcc.push((i,v,txt));}
            }
        }
    }
    for (off,v,txt) in fourcc.into_iter().take(64){out.push(format!("{label}: FOURCC_CANDIDATE +0x{off:03X} 0x{v:08X} \"{txt}\""));}
    out
}

unsafe fn v810_dump_class_methods(
    label:&str, ns:&str, cn:&str,
    assemblies:*mut *const c_void, count:usize,
    assembly_get_image:AssemblyGetImage,class_from_name:ClassFromName,class_get_method:ClassGetMethodFromName,
)->Vec<String>{
    let mut out=Vec::new();
    let Some(class)=find_class(assemblies,count,assembly_get_image,class_from_name,ns,cn) else {out.push(format!("{label}: class {ns}.{cn} not found"));return out;};
    for (mn,argc) in [("GetPropertyCountInternal",0),("GetPropertiesInternal",1),("GetPropertyDescriptionInternal",1),("GetPropertyTypeInternal",1),("AcceptsPropertyInternal",1)]{
        out.extend(v810_dump_native_method_code(&format!("{label}.{mn}"),class,mn,argc,class_get_method));
    }
    out
}
'''
    if marker not in t: raise SystemExit('v8.10 run_probe marker missing')
    t=t.replace(marker,insert+marker,1)

if '=== NATIVE PROPERTY CODE MAP v8.10 ===' not in t:
    gate='            lines.push("V8.9.1 GATE: use the exact method signatures/return types from this metadata-only report to choose a non-crashing property enumeration route. No managed property method is invoked in this build.".to_string());\n'
    if gate not in t: raise SystemExit('v8.10 v8.9.1 gate marker missing')
    block=r'''            lines.push("\n=== NATIVE PROPERTY CODE MAP v8.10 ===".to_string());
            lines.push("Read-only machine-code inspection. No managed property method is invoked. MethodInfo method pointers are page-checked with VirtualQuery before reading up to 256 bytes.".to_string());
            for (label,ns,cn) in [
                ("PLAYER","FM.UI","PersonReference"),
                ("CLUB","FM.UI","ClubReference"),
                ("ACTION","FM.UI","ActionReference"),
                ("SESSION","FM.UI","TransferOfferEditSessionReference"),
                ("PERSON_TRANSFER_OFFER","FM.UI","PersonTransferOfferReference"),
                ("PLAYER_TRANSFER_OFFER","FM.UI","PlayerTransferOfferReference"),
            ]{
                lines.extend(v810_dump_class_methods(label,ns,cn,assemblies,count,assembly_get_image,class_from_name,class_get_method));
            }
            lines.push("V8.10 GATE: inspect native bytes/FourCC immediates for property constants without executing GetProperties. Candidate constants become inputs for a later guarded static metadata probe only after cross-class correlation.".to_string());
'''
    t=t.replace(gate,gate+block,1)

t=t.replace('Native Offer Safe Property API Inspector v8.9.1','Native Offer Native Property Code Map v8.10')
helper.write_text(t,encoding='utf-8')
print('Element v8.10 Native Property Code Map applied.')
