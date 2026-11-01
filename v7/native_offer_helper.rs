#![allow(non_snake_case)]

use std::ffi::{c_char, c_void, CStr, CString};
use std::fs;
use std::ptr::null_mut;

const DLL_PROCESS_ATTACH: u32 = 1;
const METHOD_ATTRIBUTE_STATIC: u32 = 0x0010;
const FIELD_ATTRIBUTE_STATIC: u32 = 0x0010;

type Handle = *mut c_void;
type DomainGet = unsafe extern "C" fn() -> *mut c_void;
type ThreadAttach = unsafe extern "C" fn(*mut c_void) -> *mut c_void;
type ThreadDetach = unsafe extern "C" fn(*mut c_void);
type DomainGetAssemblies = unsafe extern "C" fn(*const c_void, *mut usize) -> *mut *const c_void;
type AssemblyGetImage = unsafe extern "C" fn(*const c_void) -> *const c_void;
type ClassFromName = unsafe extern "C" fn(*const c_void, *const c_char, *const c_char) -> *mut c_void;
type ClassGetMethodFromName = unsafe extern "C" fn(*mut c_void, *const c_char, i32) -> *const c_void;
type ClassGetFields = unsafe extern "C" fn(*mut c_void, *mut *mut c_void) -> *mut c_void;
type ClassGetParent = unsafe extern "C" fn(*mut c_void) -> *mut c_void;
type ClassGetName = unsafe extern "C" fn(*mut c_void) -> *const c_char;
type ClassGetNamespace = unsafe extern "C" fn(*mut c_void) -> *const c_char;
type MethodGetName = unsafe extern "C" fn(*const c_void) -> *const c_char;
type MethodGetParamCount = unsafe extern "C" fn(*const c_void) -> u32;
type MethodGetParam = unsafe extern "C" fn(*const c_void, u32) -> *const c_void;
type MethodGetParamName = unsafe extern "C" fn(*const c_void, u32) -> *const c_char;
type MethodGetFlags = unsafe extern "C" fn(*const c_void, *mut u32) -> u32;
type FieldGetName = unsafe extern "C" fn(*mut c_void) -> *const c_char;
type FieldGetType = unsafe extern "C" fn(*mut c_void) -> *const c_void;
type FieldGetOffset = unsafe extern "C" fn(*mut c_void) -> usize;
type FieldGetFlags = unsafe extern "C" fn(*mut c_void) -> u32;
type TypeGetName = unsafe extern "C" fn(*const c_void) -> *mut c_char;

#[link(name = "kernel32")]
extern "system" {
    fn GetModuleHandleA(lpModuleName: *const c_char) -> Handle;
    fn GetProcAddress(hModule: Handle, lpProcName: *const c_char) -> *mut c_void;
    fn CreateThread(
        lpThreadAttributes: *mut c_void,
        dwStackSize: usize,
        lpStartAddress: Option<unsafe extern "system" fn(*mut c_void) -> u32>,
        lpParameter: *mut c_void,
        dwCreationFlags: u32,
        lpThreadId: *mut u32,
    ) -> Handle;
    fn CloseHandle(hObject: Handle) -> i32;
}

fn report_path() -> std::path::PathBuf {
    std::env::temp_dir().join("ElementFM27-native-offer-probe.txt")
}

fn progress_path() -> std::path::PathBuf {
    std::env::temp_dir().join("ElementFM27-native-offer-probe-progress.txt")
}

fn progress(stage: &str) {
    let path = progress_path();
    let previous = fs::read_to_string(&path).unwrap_or_default();
    let mut text = previous;
    if !text.is_empty() && !text.ends_with('\n') {
        text.push('\n');
    }
    text.push_str(stage);
    let _ = fs::write(path, text.as_bytes());
}

unsafe fn proc_addr(module: Handle, name: &str) -> Result<*mut c_void, String> {
    let c = CString::new(name).map_err(|_| format!("invalid export name {name}"))?;
    let p = GetProcAddress(module, c.as_ptr());
    if p.is_null() {
        Err(format!("missing GameAssembly export: {name}"))
    } else {
        Ok(p)
    }
}

unsafe fn cstr(ptr: *const c_char) -> String {
    if ptr.is_null() {
        "<null>".to_string()
    } else {
        CStr::from_ptr(ptr).to_string_lossy().into_owned()
    }
}

unsafe fn find_class(
    assemblies: *mut *const c_void,
    assembly_count: usize,
    assembly_get_image: AssemblyGetImage,
    class_from_name: ClassFromName,
    namespace: &str,
    class_name: &str,
) -> Option<*mut c_void> {
    let ns = CString::new(namespace).ok()?;
    let cn = CString::new(class_name).ok()?;
    for i in 0..assembly_count {
        let asm = *assemblies.add(i);
        if asm.is_null() {
            continue;
        }
        let image = assembly_get_image(asm);
        if image.is_null() {
            continue;
        }
        let class = class_from_name(image, ns.as_ptr(), cn.as_ptr());
        if !class.is_null() {
            return Some(class);
        }
    }
    None
}

unsafe fn describe_method(
    label: &str,
    method: *const c_void,
    method_get_name: MethodGetName,
    method_get_param_count: MethodGetParamCount,
    method_get_param: MethodGetParam,
    method_get_param_name: MethodGetParamName,
    method_get_flags: MethodGetFlags,
    type_get_name: TypeGetName,
) -> String {
    let count = method_get_param_count(method);
    let mut parts = Vec::with_capacity(count as usize);
    for i in 0..count {
        let ty = method_get_param(method, i);
        let type_name = if ty.is_null() {
            "<null-type>".to_string()
        } else {
            cstr(type_get_name(ty))
        };
        let param_name = cstr(method_get_param_name(method, i));
        parts.push(format!("arg{i} {param_name}:{type_name}"));
    }
    let mut iflags = 0u32;
    let flags = method_get_flags(method, &mut iflags);
    format!(
        "{label}\n  method={}\n  ptr=0x{:X}\n  flags=0x{flags:08X} iflags=0x{iflags:08X} static={}\n  argc={count}\n  {}",
        cstr(method_get_name(method)),
        method as usize,
        if flags & METHOD_ATTRIBUTE_STATIC != 0 { "yes" } else { "no" },
        parts.join("\n  ")
    )
}

unsafe fn describe_class_fields(
    class: *mut c_void,
    class_get_fields: ClassGetFields,
    class_get_parent: ClassGetParent,
    class_get_name: ClassGetName,
    class_get_namespace: ClassGetNamespace,
    field_get_name: FieldGetName,
    field_get_type: FieldGetType,
    field_get_offset: FieldGetOffset,
    field_get_flags: FieldGetFlags,
    type_get_name: TypeGetName,
) -> Vec<String> {
    let mut lines = Vec::new();
    let mut current = class;
    let mut depth = 0usize;
    while !current.is_null() && depth < 6 {
        let class_name = cstr(class_get_name(current));
        let namespace = cstr(class_get_namespace(current));
        lines.push(format!("CLASS depth={depth} {namespace}.{class_name} @ 0x{:X}", current as usize));
        let mut iter: *mut c_void = null_mut();
        let mut seen = 0usize;
        loop {
            let field = class_get_fields(current, &mut iter);
            if field.is_null() {
                break;
            }
            seen += 1;
            if seen > 256 {
                lines.push("  field scan stopped after 256 entries".to_string());
                break;
            }
            let name = cstr(field_get_name(field));
            let ty = field_get_type(field);
            let type_name = if ty.is_null() {
                "<null-type>".to_string()
            } else {
                cstr(type_get_name(ty))
            };
            let offset = field_get_offset(field);
            let flags = field_get_flags(field);
            let static_tag = if flags & FIELD_ATTRIBUTE_STATIC != 0 { " STATIC" } else { "" };
            lines.push(format!(
                "  FIELD{name_sep}{name} type={type_name} offset=0x{offset:X} flags=0x{flags:08X}{static_tag}",
                name_sep = " "
            ));
        }
        current = class_get_parent(current);
        depth += 1;
    }
    lines
}

unsafe fn run_probe() -> Result<String, String> {
    progress("01 worker entered");
    let ga_name = CString::new("GameAssembly.dll").unwrap();
    let ga = GetModuleHandleA(ga_name.as_ptr());
    if ga.is_null() {
        return Err("GameAssembly.dll is not loaded".into());
    }
    progress("02 GameAssembly.dll found");

    macro_rules! resolve {
        ($name:literal, $ty:ty) => {{
            let p = proc_addr(ga, $name)?;
            progress(concat!("03 export resolved: ", $name));
            std::mem::transmute::<*mut c_void, $ty>(p)
        }};
    }

    let domain_get: DomainGet = resolve!("il2cpp_domain_get", DomainGet);
    let thread_attach: ThreadAttach = resolve!("il2cpp_thread_attach", ThreadAttach);
    let thread_detach: ThreadDetach = resolve!("il2cpp_thread_detach", ThreadDetach);
    let domain_get_assemblies: DomainGetAssemblies = resolve!("il2cpp_domain_get_assemblies", DomainGetAssemblies);
    let assembly_get_image: AssemblyGetImage = resolve!("il2cpp_assembly_get_image", AssemblyGetImage);
    let class_from_name: ClassFromName = resolve!("il2cpp_class_from_name", ClassFromName);
    let class_get_method: ClassGetMethodFromName = resolve!("il2cpp_class_get_method_from_name", ClassGetMethodFromName);
    let class_get_fields: ClassGetFields = resolve!("il2cpp_class_get_fields", ClassGetFields);
    let class_get_parent: ClassGetParent = resolve!("il2cpp_class_get_parent", ClassGetParent);
    let class_get_name: ClassGetName = resolve!("il2cpp_class_get_name", ClassGetName);
    let class_get_namespace: ClassGetNamespace = resolve!("il2cpp_class_get_namespace", ClassGetNamespace);
    let method_get_name: MethodGetName = resolve!("il2cpp_method_get_name", MethodGetName);
    let method_get_param_count: MethodGetParamCount = resolve!("il2cpp_method_get_param_count", MethodGetParamCount);
    let method_get_param: MethodGetParam = resolve!("il2cpp_method_get_param", MethodGetParam);
    let method_get_param_name: MethodGetParamName = resolve!("il2cpp_method_get_param_name", MethodGetParamName);
    let method_get_flags: MethodGetFlags = resolve!("il2cpp_method_get_flags", MethodGetFlags);
    let field_get_name: FieldGetName = resolve!("il2cpp_field_get_name", FieldGetName);
    let field_get_type: FieldGetType = resolve!("il2cpp_field_get_type", FieldGetType);
    let field_get_offset: FieldGetOffset = resolve!("il2cpp_field_get_offset", FieldGetOffset);
    let field_get_flags: FieldGetFlags = resolve!("il2cpp_field_get_flags", FieldGetFlags);
    let type_get_name: TypeGetName = resolve!("il2cpp_type_get_name", TypeGetName);
    progress("04 required IL2CPP exports resolved");

    let domain = domain_get();
    if domain.is_null() {
        return Err("il2cpp_domain_get returned null".into());
    }
    progress("05 IL2CPP domain acquired");

    let il2cpp_thread = thread_attach(domain);
    if il2cpp_thread.is_null() {
        return Err("il2cpp_thread_attach returned null".into());
    }
    progress("06 helper thread attached to IL2CPP domain");

    let result = (|| -> Result<String, String> {
        let mut count = 0usize;
        let assemblies = domain_get_assemblies(domain, &mut count);
        if assemblies.is_null() || count == 0 {
            return Err("il2cpp_domain_get_assemblies returned no assemblies".into());
        }
        progress(&format!("07 assemblies acquired: {count}"));

        let mut lines = Vec::new();
        lines.push(format!("Element FM27 Native Offer Inspector v8.4.4 | assemblies={count} | PersonMakeOfferForPlayer ActionID=0x73414278"));
        lines.push("Goal: certify dispatcher signature + instance/static ownership before enabling SEND NATIVE AI OFFER.".to_string());

        let targets = [
            ("PluginContextActionsModule.HandleActionEvent", "FM.Game", "PluginContextActionsModule", "HandleActionEvent", 6),
            ("PluginContextActionsModule.PerformDefaultActionHandling", "FM.Game", "PluginContextActionsModule", "PerformDefaultActionHandling", 3),
            ("GameInteropSubsystem.SendEvent", "FM.GamePlugin", "GameInteropSubsystem", "SendEvent", 3),
            ("GamePlugin.SendEvent", "FM.GamePlugin", "GamePlugin", "SendEvent", 3),
        ];

        for (idx, &(label, ns, class_name, method_name, argc)) in targets.iter().enumerate() {
            progress(&format!("08.{} scanning {label}", idx + 1));
            match find_class(assemblies, count, assembly_get_image, class_from_name, ns, class_name) {
                Some(class) => {
                    let mn = CString::new(method_name).unwrap();
                    let method = class_get_method(class, mn.as_ptr(), argc);
                    if method.is_null() {
                        lines.push(format!("{label} => METHOD NOT FOUND"));
                    } else {
                        progress(&format!("09.{} found {label}", idx + 1));
                        lines.push(describe_method(
                            label,
                            method,
                            method_get_name,
                            method_get_param_count,
                            method_get_param,
                            method_get_param_name,
                            method_get_flags,
                            type_get_name,
                        ));
                        if idx == 0 {
                            lines.push("\nPluginContextActionsModule field / parent inspection:".to_string());
                            lines.extend(describe_class_fields(
                                class,
                                class_get_fields,
                                class_get_parent,
                                class_get_name,
                                class_get_namespace,
                                field_get_name,
                                field_get_type,
                                field_get_offset,
                                field_get_flags,
                                type_get_name,
                            ));
                        }
                    }
                }
                None => lines.push(format!("{label} => CLASS NOT FOUND")),
            }
        }

        lines.push("\nCERTIFICATION CHECKLIST:".to_string());
        lines.push("- HandleActionEvent exact six argument names/types: inspect above".to_string());
        lines.push("- static=no requires a live PluginContextActionsModule instance candidate".to_string());
        lines.push("- static=yes allows direct guarded runtime/native invocation once arguments are mapped".to_string());
        lines.push("- no offer is sent by this inspector".to_string());
        Ok(lines.join("\n"))
    })();

    thread_detach(il2cpp_thread);
    progress("10 helper thread detached from IL2CPP domain");
    result
}

fn write_report(text: &str) {
    let _ = fs::write(report_path(), text.as_bytes());
}

unsafe extern "system" fn worker(_: *mut c_void) -> u32 {
    progress("00 worker thread started");
    let report = match run_probe() {
        Ok(s) => s,
        Err(e) => format!("ERROR: {e}"),
    };
    write_report(&report);
    progress("11 final report written");
    0
}

#[no_mangle]
pub unsafe extern "system" fn DllMain(_: Handle, reason: u32, _: *mut c_void) -> i32 {
    if reason == DLL_PROCESS_ATTACH {
        let _ = fs::remove_file(progress_path());
        let thread = CreateThread(null_mut(), 0, Some(worker), null_mut(), 0, null_mut());
        if !thread.is_null() {
            let _ = CloseHandle(thread);
        } else {
            write_report("ERROR: CreateThread failed in native offer helper");
        }
    }
    1
}
