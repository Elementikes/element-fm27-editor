$ErrorActionPreference='Stop'
$SourceRoot=(Get-Location).Path
function Read-Text([string]$RelativePath){$p=Join-Path $SourceRoot $RelativePath;if(-not(Test-Path -LiteralPath $p)){throw "Source file not found: $p"};[IO.File]::ReadAllText($p)}
function Write-Text([string]$RelativePath,[string]$Text){$p=Join-Path $SourceRoot $RelativePath;[IO.File]::WriteAllText($p,$Text,[Text.UTF8Encoding]::new($false))}
function Replace-Required([string]$Text,[string]$Old,[string]$New,[string]$Label){if(-not $Text.Contains($Old)){throw "v4.2.2: expected source fragment not found: $Label"};$Text.Replace($Old,$New)}

# -----------------------------------------------------------------------------
# Element v4.2.2 — MORALE UX ACCURACY
# Keeps the verified FM27 morale write unchanged. Adds an optimistic UI overlay
# so bulk MAX MORALE is visible immediately, before the immutable entity cache
# is rebuilt. Unwitnessed semantic morale labels stay numeric rather than being
# invented.
# -----------------------------------------------------------------------------

$path='src/ui/club_panel.rs'
$text=Read-Text $path

# Do not present an uncertified semantic phrase as native FM wording.
$text=Replace-Required $text '_ => format!("Level {level}"),' '_ => format!("{level}/20"),' 'numeric morale fallback'

# Persistent per-club optimistic overlay, scoped only to rows successfully queued
# for a morale write. A later cache refresh naturally makes the overlay redundant.
$text=Replace-Required $text @'
    let selected_id = egui::Id::new(("element_squad_bulk_selected", club.addr));
    let mut selected = ui.ctx().data_mut(|d| d.get_temp::<Vec<u64>>(selected_id).unwrap_or_default());
    selected.retain(|addr| cache.players.iter().any(|p| p.addr == *addr && p.club_id == Some(club.uid)));
'@ @'
    let selected_id = egui::Id::new(("element_squad_bulk_selected", club.addr));
    let mut selected = ui.ctx().data_mut(|d| d.get_temp::<Vec<u64>>(selected_id).unwrap_or_default());
    selected.retain(|addr| cache.players.iter().any(|p| p.addr == *addr && p.club_id == Some(club.uid)));
    let morale_override_id = egui::Id::new(("element_squad_morale_override", club.addr));
    let mut morale_overrides = ui.ctx().data_mut(|d| d.get_temp::<Vec<u64>>(morale_override_id).unwrap_or_default());
    morale_overrides.retain(|addr| cache.players.iter().any(|p| p.addr == *addr && p.club_id == Some(club.uid)));
'@ 'morale optimistic overlay state'

$text=Replace-Required $text @'
                            edits.push(FieldEdit {
                                addr: player.addr + physical,
                                old_raw: vec![old_raw],
                                new_raw: vec![20],
                                description: format!("{} — Morale: {} → 20", player.name, old_raw),
                            });
'@ @'
                            edits.push(FieldEdit {
                                addr: player.addr + physical,
                                old_raw: vec![old_raw],
                                new_raw: vec![20],
                                description: format!("{} — Morale: {} → 20", player.name, old_raw),
                            });
                            if !morale_overrides.contains(&player.addr) {
                                morale_overrides.push(player.addr);
                            }
'@ 'record optimistic morale write'

$text=Replace-Required $text @'
            ui.label(egui::RichText::new("Bulk actions target exactly the checked players. SELECT VISIBLE follows the current squad search/filter. Reload Save after writes to refresh cached morale labels.").size(7.2).color(egui::Color32::from_rgb(132,146,170)));
        });
    ui.ctx().data_mut(|d| d.insert_temp(selected_id, selected.clone()));
'@ @'
            ui.label(egui::RichText::new("Bulk actions target exactly the checked players. MAX MORALE shows Perfect immediately after the write is queued; Reload Save re-reads the authoritative FM value into cache.").size(7.2).color(egui::Color32::from_rgb(132,146,170)));
        });
    ui.ctx().data_mut(|d| d.insert_temp(selected_id, selected.clone()));
    ui.ctx().data_mut(|d| d.insert_temp(morale_override_id, morale_overrides.clone()));
'@ 'persist morale optimistic overlay'

$text=Replace-Required $text 'match player.morale {' 'match if morale_overrides.contains(&player.addr) { Some(20) } else { player.morale } {' 'render optimistic morale value'

# Clarify tooltip: known labels are native-witnessed; numeric fallbacks are not guessed.
$text=$text.Replace(
    'Verified FM27 squad morale: level {level}/20. Only independently witnessed levels receive semantic labels.',
    'Verified FM27 squad morale: level {level}/20. Native wording is shown only for independently witnessed levels; otherwise Element shows the numeric level.'
)

# Update squad badge to make the hotfix visible in screenshots.
$text=$text.Replace('egui::RichText::new("v4.2 • SQUAD ACTIONS")','egui::RichText::new("v4.2.2 • SQUAD ACTIONS")')

Write-Text $path $text
Write-Host 'Element v4.2.2 Morale UX accuracy hotfix applied successfully.'
