from pathlib import Path

root = Path.cwd()

# Pin the editor-side reader to a versioned report/progress filename so an old
# %TEMP% report can never masquerade as output from the current build.
bridge = root / 'src/bridge/native_offer_probe.rs'
if not bridge.exists():
    raise SystemExit('v8.14.1 missing native_offer_probe.rs')

t = bridge.read_text(encoding='utf-8')
old_report = 'ElementFM27-native-offer-probe.txt'
new_report = 'ElementFM27-native-offer-probe-v8.14.1.txt'
if old_report not in t:
    raise SystemExit('v8.14.1 bridge report filename marker missing')
t = t.replace(old_report, new_report)

old_progress = 'ElementFM27-native-offer-probe-progress.txt'
new_progress = 'ElementFM27-native-offer-probe-progress-v8.14.1.txt'
if old_progress in t:
    t = t.replace(old_progress, new_progress)

bridge.write_text(t, encoding='utf-8')

# Pin the injected helper to the exact same versioned filenames and stamp the
# generated report itself with an unambiguous build marker.
helper = Path(__file__).with_name('native_offer_helper.rs')
h = helper.read_text(encoding='utf-8')

if old_report not in h:
    raise SystemExit('v8.14.1 helper report filename marker missing')
h = h.replace(old_report, new_report)
if old_progress in h:
    h = h.replace(old_progress, new_progress)

banner_marker = '        progress(&format!("07 assemblies acquired: {count}"));\n\n        let mut lines = Vec::new();\n'
banner_replacement = '''        progress(&format!("07 assemblies acquired: {count}"));

        let mut lines = Vec::new();
        lines.push("REPORT_BUILD: Element FM27 Native Offer Type + Context Semantic Map v8.14.1".to_string());
        lines.push(format!("REPORT_FILE: {}", report_path().display()));
        lines.push("REPORT_FRESHNESS_PIN: versioned temp filename + embedded helper pin active".to_string());
'''
if 'REPORT_BUILD: Element FM27 Native Offer Type + Context Semantic Map v8.14.1' not in h:
    if banner_marker not in h:
        raise SystemExit('v8.14.1 report banner marker missing')
    h = h.replace(banner_marker, banner_replacement, 1)

h = h.replace('Native Offer Type + Context Semantic Map v8.14', 'Native Offer Type + Context Semantic Map v8.14.1')
helper.write_text(h, encoding='utf-8')

# Make screenshots identify the freshness-pinned build too.
ui = root / 'src/ui/player_panel.rs'
if ui.exists():
    s = ui.read_text(encoding='utf-8')
    s = s.replace('Native Offer Type + Context Semantic Map • v8.14', 'Native Offer Type + Context Semantic Map • v8.14.1')
    s = s.replace('📋 FULL NATIVE OFFER TYPE / CONTEXT MAP', '📋 FULL NATIVE OFFER TYPE / CONTEXT MAP • v8.14.1')
    ui.write_text(s, encoding='utf-8')

print('Element v8.14.1 report freshness pin applied: versioned report path + explicit report banner.')
