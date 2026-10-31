from pathlib import Path

root = Path.cwd()

# Compatibility: the pinned upstream FmProcess exposes read_bytes/read_u32 but
# not read_u16. Keep the verified medical offsets and decode the two-byte
# values explicitly instead of changing any FM27 mapping.
bulk_path = root / "src" / "bridge" / "bulk_load.rs"
bulk = bulk_path.read_text(encoding="utf-8")
medical_marker = "fn element_fm27_medical_actions("
helper = '''fn element_read_u16(fm: &FmProcess, addr: u64) -> Option<u16> {
    let bytes = fm.read_bytes(addr, 2).ok()?;
    let pair: [u8; 2] = bytes.get(..2)?.try_into().ok()?;
    Some(u16::from_le_bytes(pair))
}

'''
if helper not in bulk:
    if medical_marker not in bulk:
        raise SystemExit("v4.7 fix: medical action marker missing")
    bulk = bulk.replace(medical_marker, helper + medical_marker, 1)
bulk = bulk.replace(
    "fm.read_u16(injury + INJURY_FULL).ok()",
    "element_read_u16(fm, injury + INJURY_FULL)",
)
bulk = bulk.replace(
    "fm.read_u16(injury + INJURY_LIGHT).ok()",
    "element_read_u16(fm, injury + INJURY_LIGHT)",
)
bulk = bulk.replace(
    "fm.read_u16(absence + ABSENCE_DAYS).ok()",
    "element_read_u16(fm, absence + ABSENCE_DAYS)",
)
bulk_path.write_text(bulk, encoding="utf-8")

# Borrow-check compatibility: do not capture the mutable override vectors in
# the filter closure whose iterator remains alive while the loop mutates them.
club_path = root / "src" / "ui" / "club_panel.rs"
club = club_path.read_text(encoding="utf-8")
old_heal = '''                    for player in cache.players.iter().filter(|p| selected.contains(&p.addr) && p.club_id == Some(club.uid) && !heal_overrides.contains(&p.addr)) {
                        for action in &player.heal_edits {
'''
new_heal = '''                    for player in cache.players.iter().filter(|p| selected.contains(&p.addr) && p.club_id == Some(club.uid)) {
                        if heal_overrides.contains(&player.addr) { continue; }
                        for action in &player.heal_edits {
'''
old_ban = '''                    for player in cache.players.iter().filter(|p| selected.contains(&p.addr) && p.club_id == Some(club.uid) && !ban_overrides.contains(&p.addr)) {
                        for action in &player.ban_edits {
'''
new_ban = '''                    for player in cache.players.iter().filter(|p| selected.contains(&p.addr) && p.club_id == Some(club.uid)) {
                        if ban_overrides.contains(&player.addr) { continue; }
                        for action in &player.ban_edits {
'''
if old_heal not in club or old_ban not in club:
    raise SystemExit("v4.7 fix: squad action loop markers missing")
club = club.replace(old_heal, new_heal, 1).replace(old_ban, new_ban, 1)
club_path.write_text(club, encoding="utf-8")

print("Element v4.7 compile compatibility fixes applied successfully.")
