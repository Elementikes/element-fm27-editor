from pathlib import Path

root = Path.cwd()
p = root / 'src/bridge/native_offer_probe.rs'
if not p.exists():
    raise SystemExit('v8.4.2 missing native_offer_probe.rs')
t = p.read_text(encoding='utf-8')

needle = '''#[cfg(windows)]\nmod imp {\n    use std::{ffi::c_void, path::Path, time::{Duration,Instant}};\n'''
replacement = '''#[cfg(windows)]\nmod imp {\n    use std::{ffi::c_void, path::Path, time::{Duration,Instant}};\n\n    // The helper is built by CI immediately before the editor. Embed that exact\n    // DLL into the EXE so Native Offer Lab still works when Windows launches the\n    // editor from a ZIP/temp folder and does not extract the sidecar DLL.\n    static EMBEDDED_NATIVE_OFFER_HELPER: &[u8] = include_bytes!(concat!(env!(\"CARGO_MANIFEST_DIR\"), \"/Element-FM27-NativeOffer.dll\"));\n'''
if 'EMBEDDED_NATIVE_OFFER_HELPER' not in t:
    if needle not in t:
        raise SystemExit('v8.4.2 module marker missing')
    t = t.replace(needle, replacement, 1)

old = '''        let exe=std::env::current_exe().map_err(|e|format!(\"current exe: {e}\"))?;\n        let dll=exe.parent().unwrap_or(Path::new(\".\")).join(\"Element-FM27-NativeOffer.dll\");\n        if !dll.exists(){return Err(format!(\"native offer helper missing: {}\",dll.display()));}\n        let report=std::env::temp_dir().join(\"ElementFM27-native-offer-probe.txt\");let _=std::fs::remove_file(&report);\n'''
new = '''        let exe=std::env::current_exe().map_err(|e|format!(\"current exe: {e}\"))?;\n        let sidecar=exe.parent().unwrap_or(Path::new(\".\")).join(\"Element-FM27-NativeOffer.dll\");\n        let dll=if sidecar.exists(){\n            sidecar\n        }else{\n            // Loaded DLLs are file-locked by Windows. Older builds reused one fixed\n            // temp filename, so a newer embedded helper could not overwrite it while\n            // FM27 was still running (os error 32). Use an editor-process-specific\n            // filename plus embedded length, so every launch/build gets a fresh path.\n            let embedded=std::env::temp_dir().join(format!(\n                \"Element-FM27-NativeOffer-{}-{}.dll\",\n                std::process::id(),\n                EMBEDDED_NATIVE_OFFER_HELPER.len()\n            ));\n            if !embedded.exists(){\n                std::fs::write(&embedded,EMBEDDED_NATIVE_OFFER_HELPER)\n                    .map_err(|e|format!(\"extract embedded native offer helper: {e}\"))?;\n            }\n            embedded\n        };\n        let report=std::env::temp_dir().join(\"ElementFM27-native-offer-probe.txt\");let _=std::fs::remove_file(&report);\n'''
if old not in t:
    # Also support rebuilding on top of a previously patched source template.
    old2 = '''        let exe=std::env::current_exe().map_err(|e|format!(\"current exe: {e}\"))?;\n        let sidecar=exe.parent().unwrap_or(Path::new(\".\")).join(\"Element-FM27-NativeOffer.dll\");\n        let dll=if sidecar.exists(){\n            sidecar\n        }else{\n            let embedded=std::env::temp_dir().join(\"Element-FM27-NativeOffer-v8.4.2.dll\");\n            let rewrite=std::fs::metadata(&embedded).map(|m|m.len()!=EMBEDDED_NATIVE_OFFER_HELPER.len() as u64).unwrap_or(true);\n            if rewrite{std::fs::write(&embedded,EMBEDDED_NATIVE_OFFER_HELPER).map_err(|e|format!(\"extract embedded native offer helper: {e}\"))?;}\n            embedded\n        };\n        let report=std::env::temp_dir().join(\"ElementFM27-native-offer-probe.txt\");let _=std::fs::remove_file(&report);\n'''
    if old2 not in t:
        raise SystemExit('v8.4.2 helper path marker missing')
    t = t.replace(old2, new, 1)
else:
    t = t.replace(old, new, 1)

p.write_text(t, encoding='utf-8')
print('Element native helper fallback applied with lock-safe per-process temp DLL path.')
