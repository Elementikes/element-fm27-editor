from pathlib import Path

p = Path.cwd() / 'src/bridge/worker.rs'
t = p.read_text(encoding='utf-8')
old = 'native_offer_probe::probe(f.pid,player_index,club_index)'
new = 'super::native_offer_probe::probe(f.pid,player_index,club_index)'
if old not in t:
    if new in t:
        print('Element v8.7.2 worker module hotfix already applied.')
    else:
        raise SystemExit('v8.7.2 indexed probe call marker missing')
else:
    t = t.replace(old, new, 1)
    p.write_text(t, encoding='utf-8')
    print('Element v8.7.2 worker module scope hotfix applied.')
