from pathlib import Path

root = Path.cwd()
ui = root / 'src/ui/player_panel.rs'
if ui.exists():
    s = ui.read_text(encoding='utf-8')
    s = s.replace('Native Offer Real Property Map • v8.9', 'Native Offer Safe Property API Inspector • v8.9.1')
    s = s.replace('ENUMERATE REAL INTEROP PROPERTIES • SAFE', 'INSPECT PROPERTY API SIGNATURES • SAFE')
    s = s.replace('📋 FULL NATIVE OFFER PROPERTY MAP', '📋 FULL NATIVE OFFER SAFE PROPERTY API REPORT')
    ui.write_text(s, encoding='utf-8')

helper = Path(__file__).with_name('native_offer_helper.rs')
t = helper.read_text(encoding='utf-8')

if 'unsafe fn v891_describe_property_api_class' not in t:
    marker = 'unsafe fn run_probe() -> Result<String, String> {'
    insert = r'''
unsafe fn v891_describe_property_api_class(
    label:&str,
    namespace:&str,
    class_name:&str,
    assemblies:*mut *const c_void,
    assembly_count:usize,
    assembly_get_image:AssemblyGetImage,
    class_from_name:ClassFromName,
    class_get_methods:ClassGetMethods,
    method_get_name:MethodGetName,
    method_get_param_count:MethodGetParamCount,
    method_get_param:MethodGetParam,
    method_get_param_name:MethodGetParamName,
    method_get_flags:MethodGetFlags,
    type_get_name:TypeGetName,
)->Vec<String>{
    let mut out=Vec::new();
    let Some(class)=find_class(assemblies,assembly_count,assembly_get_image,class_from_name,namespace,class_name) else {
        out.push(format!("{label}: class {namespace}.{class_name} not found"));
        return out;
    };
    out.push(format!("{label}: CLASS {namespace}.{class_name} @0x{:X}",class as usize));
    let mut iter:*mut c_void=null_mut();
    let mut seen=0usize;
    loop{
        let m=class_get_methods(class,&mut iter);
        if m.is_null(){break;}
        seen+=1;
        if seen>512{out.push(format!("{label}: method scan truncated after 512 entries"));break;}
        let name=cstr(method_get_name(m));
        let low=name.to_ascii_lowercase();
        if low.contains("propert") || low.contains("trygetvalue") || low.contains("tryget") || low.contains("getproperties") || low.contains("accepts"){
            out.push(describe_method(
                &format!("{label}.{name}"),m,
                method_get_name,method_get_param_count,method_get_param,method_get_param_name,method_get_flags,type_get_name
            ));
        }
    }
    out
}
'''
    if marker not in t:
        raise SystemExit('v8.9.1 run_probe marker missing')
    t = t.replace(marker, insert + marker, 1)

start = '            lines.push("\\n=== REAL INTEROP PROPERTY MAP v8.9 ===".to_string());\n'
end = '            lines.push("V8.9 GATE: property IDs/descriptions are now sourced from FM\'s own GetProperties API. Transfer-related properties on ACTION/SESSION become the certified keys for payload construction.".to_string());\n'
if start not in t or end not in t:
    raise SystemExit('v8.9.1 v8.9 block markers missing')
si = t.index(start)
ei = t.index(end, si) + len(end)
safe_block = r'''            lines.push("\n=== SAFE PROPERTY API INSPECTOR v8.9.1 ===".to_string());
            lines.push("Metadata-only safety pass after v8.9 crashed FM while invoking GetProperties with a fabricated generic List<PropertyID>. This build DOES NOT call GetProperties/GetPropertiesInternal/TryGetValue/AcceptsPropertyInternal and DOES NOT construct a managed generic list.".to_string());
            for (label,ns,cn) in [
                ("PLAYER","FM.UI","PersonReference"),
                ("CLUB","FM.UI","ClubReference"),
                ("ACTION","FM.UI","ActionReference"),
                ("SESSION","FM.UI","TransferOfferEditSessionReference"),
                ("PERSON_TRANSFER_OFFER","FM.UI","PersonTransferOfferReference"),
                ("PLAYER_TRANSFER_OFFER","FM.UI","PlayerTransferOfferReference"),
            ]{
                lines.extend(v891_describe_property_api_class(
                    label,ns,cn,assemblies,count,assembly_get_image,class_from_name,
                    class_get_methods,method_get_name,method_get_param_count,method_get_param,
                    method_get_param_name,method_get_flags,type_get_name
                ));
            }
            lines.push("V8.9.1 GATE: use the exact method signatures/return types from this metadata-only report to choose a non-crashing property enumeration route. No managed property method is invoked in this build.".to_string());
'''
t = t[:si] + safe_block + t[ei:]

t = t.replace('Native Offer Real Property Map v8.9', 'Native Offer Safe Property API Inspector v8.9.1')
helper.write_text(t, encoding='utf-8')
print('Element v8.9.1 Safe Property API Inspector applied.')
