from pathlib import Path
import json
import sys

root = Path(__file__).resolve().parent.parent / "config" / "element-v6"
errors = []

def load(name):
    path = root / name
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        errors.append(f"{name}: invalid JSON: {exc}")
        return {}

caps = load("capabilities.json")
seen = set()
for i, row in enumerate(caps.get("capabilities", [])):
    cid = row.get("id")
    if not cid or cid in seen:
        errors.append(f"capabilities.json row {i}: missing/duplicate id {cid!r}")
    seen.add(cid)
    if row.get("confidence") not in caps.get("confidenceOrder", []):
        if row.get("confidence") != "mapping":
            errors.append(f"capabilities.json {cid}: unknown confidence {row.get('confidence')!r}")
    if row.get("write") and not row.get("read"):
        errors.append(f"capabilities.json {cid}: write=true requires read=true")

presets = load("presets.json")
preset_ids = set()
allowed_actions = {"set", "set-many", "set-category", "custom"}
for i, preset in enumerate(presets.get("presets", [])):
    pid = preset.get("id")
    if not pid or pid in preset_ids:
        errors.append(f"presets.json row {i}: missing/duplicate id {pid!r}")
    preset_ids.add(pid)
    for j, action in enumerate(preset.get("actions", [])):
        if action.get("type") not in allowed_actions:
            errors.append(f"presets.json {pid} action {j}: unsupported type {action.get('type')!r}")
        if not action.get("requires"):
            errors.append(f"presets.json {pid} action {j}: every action must declare a safety requirement")

ratings = load("ratings.json")
for role, profile in ratings.get("roleProfiles", {}).items():
    if not profile.get("key"):
        errors.append(f"ratings.json {role}: missing key attributes")

formations = load("tactics.json").get("formations", [])
for i, formation in enumerate(formations):
    positions = formation.get("positions", [])
    if len(positions) != 11:
        errors.append(f"tactics.json row {i} ({formation.get('name')}): expected 11 positions, got {len(positions)}")

sem = load("fm27-semantics.json")
section_ids = set()
allowed_status = {"mapped","probe-ready","partial","semantic-only","certified","certified-direct/probe-native","mapped-derived","element-native","mapped-read/probe-write"}
for i, row in enumerate(sem.get("playerSections", [])):
    sid = row.get("id")
    if not sid or sid in section_ids:
        errors.append(f"fm27-semantics.json row {i}: missing/duplicate player section id {sid!r}")
    section_ids.add(sid)
    if row.get("status") not in allowed_status:
        errors.append(f"fm27-semantics.json {sid}: unsupported status {row.get('status')!r}")
for entity, fields in sem.get("entities", {}).items():
    if not isinstance(fields, list) or not all(isinstance(v, str) and v for v in fields):
        errors.append(f"fm27-semantics.json entity {entity}: expected non-empty string field list")

probes = load("probe-targets.json")
probe_ids = set()
for i, row in enumerate(probes.get("targets", [])):
    pid = row.get("id")
    if not pid or pid in probe_ids:
        errors.append(f"probe-targets.json row {i}: missing/duplicate id {pid!r}")
    probe_ids.add(pid)
    if not row.get("fields"):
        errors.append(f"probe-targets.json {pid}: no fields")

if errors:
    print("Element v6 config validation FAILED")
    for error in errors:
        print(" -", error)
    sys.exit(1)

print(f"Element v6 config validation OK: {len(seen)} capabilities, {len(preset_ids)} presets, {len(ratings.get('roleProfiles', {}))} role profiles, {len(formations)} formations, {len(section_ids)} player sections, {len(probe_ids)} probe targets")
