from pathlib import Path

root = Path.cwd()
p = root / 'src/bridge/native_offer_probe.rs'
if not p.exists():
    raise SystemExit('v8.13.1 missing native_offer_probe.rs')

t = p.read_text(encoding='utf-8')

old = '''        let exe=std::env::current_exe().map_err(|e|format!("current exe: {e}"))?;
        let sidecar=exe.parent().unwrap_or(Path::new(".")).join("Element-FM27-NativeOffer.dll");
        let dll=if sidecar.exists(){
            sidecar
        }else{
            // Loaded DLLs are file-locked by Windows. Older builds reused one fixed
            // temp filename, so a newer embedded helper could not overwrite it while
            // FM27 was still running (os error 32). Use an editor-process-specific
            // filename plus embedded length, so every launch/build gets a fresh path.
            let embedded=std::env::temp_dir().join(format!(
                "Element-FM27-NativeOffer-{}-{}.dll",
                std::process::id(),
                EMBEDDED_NATIVE_OFFER_HELPER.len()
            ));
            if !embedded.exists(){
                std::fs::write(&embedded,EMBEDDED_NATIVE_OFFER_HELPER)
                    .map_err(|e|format!("extract embedded native offer helper: {e}"))?;
            }
            embedded
        };
'''

new = '''        // v8.13.1 freshness pin: ALWAYS inject the helper embedded into this exact
        // editor build. Never prefer a sidecar DLL from an older extracted build.
        // This prevents stale helper/report mismatches when users replace only the EXE
        // or reuse an existing folder containing Element-FM27-NativeOffer.dll.
        let dll=std::env::temp_dir().join(format!(
            "Element-FM27-NativeOffer-pinned-{}-{}.dll",
            std::process::id(),
            EMBEDDED_NATIVE_OFFER_HELPER.len()
        ));
        if !dll.exists(){
            std::fs::write(&dll,EMBEDDED_NATIVE_OFFER_HELPER)
                .map_err(|e|format!("extract pinned embedded native offer helper: {e}"))?;
        }
'''

if old not in t:
    raise SystemExit('v8.13.1 stale-sidecar selector marker missing')

t = t.replace(old, new, 1)

# Make the UI/version string explicit so screenshots identify the pinned build.
ui = root / 'src/ui/player_panel.rs'
if ui.exists():
    s = ui.read_text(encoding='utf-8')
    s = s.replace('Native Offer Semantic Property Mapper • v8.13', 'Native Offer Semantic Property Mapper • v8.13.1')
    s = s.replace('MAP OFFER PROPERTY SEMANTICS • GUARDED', 'MAP OFFER PROPERTY SEMANTICS • PINNED')
    ui.write_text(s, encoding='utf-8')

p.write_text(t, encoding='utf-8')
print('Element v8.13.1 helper freshness pin applied: embedded helper always wins.')
