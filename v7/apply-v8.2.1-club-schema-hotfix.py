from pathlib import Path

root=Path.cwd()
p=root/'src/ui/club_panel.rs'
if not p.exists(): raise SystemExit('v8.2.1 missing club_panel.rs')
t=p.read_text(encoding='utf-8')
old='club.build.schemas()'
count=t.count(old)
if count==0:
    raise SystemExit('v8.2.1 marker missing: club.build.schemas()')
t=t.replace(old,'schemas')
p.write_text(t,encoding='utf-8')
print(f'Element v8.2.1 club schema hotfix applied: {count} replacements.')
