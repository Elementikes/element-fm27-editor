from pathlib import Path

p = Path(__file__).with_name('native_offer_helper.rs')
t = p.read_text(encoding='utf-8')

needle = 'use std::convert::TryInto;\n'
if needle in t:
    print('Element v8.15.2 helper TryInto hotfix already applied.')
else:
    marker = 'use std::ffi::{c_char, c_void, CStr, CString};\n'
    if marker not in t:
        raise SystemExit('v8.15.2 helper import marker missing')
    t = t.replace(marker, marker + needle, 1)
    p.write_text(t, encoding='utf-8')
    print('Element v8.15.2 helper TryInto compile hotfix applied.')
