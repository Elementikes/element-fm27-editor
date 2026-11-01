from pathlib import Path

root=Path.cwd()

# worker sibling module qualification
p=root/'src/bridge/worker.rs'
if not p.exists(): raise SystemExit('v8.4.2 missing worker.rs')
t=p.read_text(encoding='utf-8')
old='native_offer_probe::probe(f.pid)'
if old not in t: raise SystemExit('v8.4.2 worker native probe marker missing')
t=t.replace(old,'super::native_offer_probe::probe(f.pid)',1)
p.write_text(t,encoding='utf-8')

# CreateRemoteThread is intentionally raw-FFI here; the windows crate feature
# surface used by upstream does not expose this symbol under Threading.
p=root/'src/bridge/native_offer_probe.rs'
if not p.exists(): raise SystemExit('v8.4.2 missing native_offer_probe.rs')
t=p.read_text(encoding='utf-8')
t=t.replace(
    'use windows::Win32::System::Threading::{CreateRemoteThread,OpenProcess,WaitForSingleObject,PROCESS_ALL_ACCESS};',
    'use windows::Win32::System::Threading::{OpenProcess,WaitForSingleObject,PROCESS_ALL_ACCESS};',
    1,
)
old_extern='''        #[link(name="kernel32")]
        unsafe extern "system" { fn GetModuleHandleW(lpModuleName:PCWSTR)->HANDLE; fn GetProcAddress(hModule:HANDLE,lpProcName:*const u8)->*const c_void; }
'''
new_extern='''        #[link(name="kernel32")]
        unsafe extern "system" {
            fn GetModuleHandleW(lpModuleName:PCWSTR)->HANDLE;
            fn GetProcAddress(hModule:HANDLE,lpProcName:*const u8)->*const c_void;
            fn CreateRemoteThread(
                hProcess:HANDLE,
                lpThreadAttributes:*const c_void,
                dwStackSize:usize,
                lpStartAddress:Option<unsafe extern "system" fn(*mut c_void)->u32>,
                lpParameter:*mut c_void,
                dwCreationFlags:u32,
                lpThreadId:*mut u32,
            )->HANDLE;
        }
'''
if old_extern not in t: raise SystemExit('v8.4.2 kernel32 extern marker missing')
t=t.replace(old_extern,new_extern,1)
old_call='''        let th=CreateRemoteThread(h,None,0,Some(start),Some(remote),0,None).map_err(|e|format!("CreateRemoteThread(LoadLibraryW): {e}"))?;
        let _=WaitForSingleObject(th,5000);let _=CloseHandle(th);let _=VirtualFreeEx(h,remote,0,MEM_RELEASE);let _=CloseHandle(h);
'''
new_call='''        let th=CreateRemoteThread(h,std::ptr::null(),0,Some(start),remote,0,std::ptr::null_mut());
        if th.0.is_null(){let _=VirtualFreeEx(h,remote,0,MEM_RELEASE);let _=CloseHandle(h);return Err("CreateRemoteThread(LoadLibraryW) failed".into());}
        let _=WaitForSingleObject(th,5000);let _=CloseHandle(th);let _=VirtualFreeEx(h,remote,0,MEM_RELEASE);let _=CloseHandle(h);
'''
if old_call not in t: raise SystemExit('v8.4.2 CreateRemoteThread call marker missing')
t=t.replace(old_call,new_call,1)
p.write_text(t,encoding='utf-8')

print('Element v8.4.2 native probe compile hotfix applied.')
