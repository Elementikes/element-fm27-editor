from pathlib import Path

root=Path.cwd()
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
print('Element v8.4.1 relationship vector bounds hotfix applied.')
