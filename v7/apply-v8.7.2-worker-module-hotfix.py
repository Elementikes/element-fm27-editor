from pathlib import Path

p = Path.cwd() / 'src/bridge/worker.rs'
t = p.read_text(encoding='utf-8')

# Keep this compatibility shim shape-agnostic. v8.15 extends the native offer
# probe with addresses/UID/fee, so matching the old 3-argument call is brittle.
old = 'native_offer_probe::probe('
new = 'super::native_offer_probe::probe('

if new in t:
    print('Element worker module hotfix already applied.')
elif old in t:
    t = t.replace(old, new, 1)
    p.write_text(t, encoding='utf-8')
    print('Element worker module scope hotfix applied to current native-offer probe shape.')
else:
    raise SystemExit('worker native-offer probe call marker missing')
