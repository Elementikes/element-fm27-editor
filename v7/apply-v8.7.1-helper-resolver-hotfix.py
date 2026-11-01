from pathlib import Path

p = Path(__file__).with_name('native_offer_helper.rs')
t = p.read_text(encoding='utf-8')

marker = '    let object_unbox: ObjectUnbox = resolve!("il2cpp_object_unbox", ObjectUnbox);\n'
if marker not in t:
    raise SystemExit('v8.7.1 helper resolver marker missing')

extra = ''
if 'let object_new: ObjectNew' not in t:
    extra += '    let object_new: ObjectNew = resolve!("il2cpp_object_new", ObjectNew);\n'
if 'let string_chars: StringChars' not in t:
    extra += '    let string_chars: StringChars = resolve!("il2cpp_string_chars", StringChars);\n'
if 'let string_length: StringLength' not in t:
    extra += '    let string_length: StringLength = resolve!("il2cpp_string_length", StringLength);\n'

if extra:
    t = t.replace(marker, marker + extra, 1)

p.write_text(t, encoding='utf-8')
print('Element v8.7.1 helper IL2CPP resolver hotfix applied.')
