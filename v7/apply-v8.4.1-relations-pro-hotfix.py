from pathlib import Path

root=Path.cwd()

# Relationship vector bounds hotfix.
p=root/'src/bridge/force_transfer.rs'
if not p.exists(): raise SystemExit('v8.4.1 missing force_transfer.rs')
t=p.read_text(encoding='utf-8')
old='''    let (_object,header,begin,end,cap)=relation_vector_bounds(fm,player_addr,person_shift)?;
    let stride=layout.relation_size as u64;
'''
new='''    let (header,begin,end,cap,stride_usize)=relation_vector_bounds(fm,player_addr,person_shift)?;
    let stride=stride_usize as u64;
'''
if old not in t: raise SystemExit('v8.4.1 relation bounds marker missing')
t=t.replace(old,new,1)
p.write_text(t,encoding='utf-8')

# Worker sibling module qualification.
p=root/'src/bridge/worker.rs'
if not p.exists(): raise SystemExit('v8.4.1 missing worker.rs')
t=p.read_text(encoding='utf-8')
old='native_offer_probe::probe(f.pid)'
if old not in t: raise SystemExit('v8.4.1 worker native probe marker missing')
t=t.replace(old,'super::native_offer_probe::probe(f.pid)',1)
p.write_text(t,encoding='utf-8')

# Use raw kernel32 CreateRemoteThread FFI. The windows crate feature-set used by
# the upstream editor does not expose this symbol at the imported path.
p=root/'src/bridge/native_offer_probe.rs'
if not p.exists(): raise SystemExit('v8.4.1 missing native_offer_probe.rs')
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
if old_extern not in t: raise SystemExit('v8.4.1 kernel32 extern marker missing')
t=t.replace(old_extern,new_extern,1)
old_call='''        let th=CreateRemoteThread(h,None,0,Some(start),Some(remote),0,None).map_err(|e|format!("CreateRemoteThread(LoadLibraryW): {e}"))?;
        let _=WaitForSingleObject(th,5000);let _=CloseHandle(th);let _=VirtualFreeEx(h,remote,0,MEM_RELEASE);let _=CloseHandle(h);
'''
new_call='''        let th=CreateRemoteThread(h,std::ptr::null(),0,Some(start),remote,0,std::ptr::null_mut());
        if th.0.is_null(){let _=VirtualFreeEx(h,remote,0,MEM_RELEASE);let _=CloseHandle(h);return Err("CreateRemoteThread(LoadLibraryW) failed".into());}
        let _=WaitForSingleObject(th,5000);let _=CloseHandle(th);let _=VirtualFreeEx(h,remote,0,MEM_RELEASE);let _=CloseHandle(h);
'''
if old_call not in t: raise SystemExit('v8.4.1 CreateRemoteThread call marker missing')
t=t.replace(old_call,new_call,1)
p.write_text(t,encoding='utf-8')

print('Element v8.4.1 relationship bounds + native probe compile hotfix applied.')
