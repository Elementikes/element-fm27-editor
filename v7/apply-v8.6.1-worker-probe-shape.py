from pathlib import Path
import re

p = Path.cwd() / 'src/bridge/worker.rs'
if not p.exists():
    raise SystemExit('v8.6.1 missing src/bridge/worker.rs')

t = p.read_text(encoding='utf-8')

# Normalize the v8.4/v8.5 generated probe arm so v8.7 can extend it with
# player_index + club_index regardless of whether the module is referenced as
# native_offer_probe or super::native_offer_probe.
pattern = re.compile(
    r'            BridgeCmd::ProbeNativeOfferInterop\s*=>\s*\{\s*\n'
    r'                let result=match &fm \{Some\(f\)=>(?:super::)?native_offer_probe::probe\(f\.pid\),None=>Err\("Cannot probe native offer interop: no process attached"\.into\(\)\)\};\s*\n'
)
canonical = (
    '            BridgeCmd::ProbeNativeOfferInterop => {\n'
    '                let result=match &fm {Some(f)=>native_offer_probe::probe(f.pid),None=>Err("Cannot probe native offer interop: no process attached".into())};\n'
)

t2, n = pattern.subn(canonical, t, count=1)
if n == 0:
    # Already canonical is fine; otherwise fail closed so CI tells us the new shape.
    if canonical not in t:
        raise SystemExit('v8.6.1 could not locate ProbeNativeOfferInterop worker arm')
    t2 = t

p.write_text(t2, encoding='utf-8')
print('Element v8.6.1 normalized native offer worker probe arm.')
