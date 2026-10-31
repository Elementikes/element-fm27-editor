$ErrorActionPreference = 'Stop'
$SourceRoot = (Get-Location).Path

function Read-Text([string]$RelativePath) {
    $Path = Join-Path $SourceRoot $RelativePath
    if (-not (Test-Path -LiteralPath $Path)) { throw "Source file not found: $Path" }
    return [IO.File]::ReadAllText($Path)
}

function Write-Text([string]$RelativePath, [string]$Text) {
    $Path = Join-Path $SourceRoot $RelativePath
    [IO.File]::WriteAllText($Path, $Text, [Text.UTF8Encoding]::new($false))
}

function Replace-Required([string]$Text, [string]$Old, [string]$New, [string]$Label) {
    if (-not $Text.Contains($Old)) { throw "v3.8.3: expected source fragment not found: $Label" }
    return $Text.Replace($Old, $New)
}

# -----------------------------------------------------------------------------
# Element v3.8.3 — SQUAD MORALE INTELLIGENCE
#
# Read-side only. FM27 Steam morale is independently witnessed at p_morale
# (schema offset +0x26C), level 1..20. read_player_raw normalizes the person
# block for player-coaches, so the schema-layout raw cache is safe to read.
#
# Fitness / condition / sharpness remain intentionally unmapped. Reserve-team
# vectors are known upstream, but B-vs-U19 classification is not yet certified.
# -----------------------------------------------------------------------------

# ======================== CACHE MORALE ========================================
$cachePath = 'src/cache.rs'
$cache = Read-Text $cachePath
$cache = Replace-Required $cache @'
    pub squad_status: Option<u8>,
'@ @'
    pub squad_status: Option<u8>,
    /// Verified FM27 morale level (1..20), cached for live squad rows.
    pub morale: Option<u8>,
'@ 'CachedPlayer morale field'
Write-Text $cachePath $cache

$bulkPath = 'src/bridge/bulk_load.rs'
$bulk = Read-Text $bulkPath
$bulk = Replace-Required $bulk @'
            wage: None, squad_status: None,
'@ @'
            wage: None, squad_status: None, morale: None,
'@ 'CachedPlayer morale initializer'

$moraleAnchor = @'
            // v3.8.2: contract summary for the roster table. The contract
'@
$moraleRead = @'
            // v3.8.3: morale is a verified direct player/person byte. The
            // cached raw record is already normalized to schema layout.
            if let Some(offset) = schemas.offset_of("p_morale") {
                player.morale = player
                    .raw
                    .get(offset)
                    .copied()
                    .filter(|level| (1..=20).contains(level));
            }

            // v3.8.2: contract summary for the roster table. The contract
'@
$bulk = Replace-Required $bulk $moraleAnchor $moraleRead 'morale read insertion'
Write-Text $bulkPath $bulk

# ======================== PREMIUM MORALE UI ===================================
$clubPath = 'src/ui/club_panel.rs'
$club = Read-Text $clubPath

$helperAnchor = @'
fn show_squads(
'@
$moraleHelpers = @'
fn element_morale_name(level: u8) -> String {
    match level {
        2 => "Extremely Poor".into(),
        3 => "Very Poor".into(),
        5 => "Quite Poor".into(),
        6 => "Fairly Poor".into(),
        7 => "Slightly Poor".into(),
        8 => "Fair".into(),
        9 => "Fairly Okay".into(),
        10 => "Okay".into(),
        11 => "Fairly Good".into(),
        12 => "Quite Good".into(),
        13 => "Good".into(),
        14 => "Really Good".into(),
        20 => "Perfect".into(),
        _ => format!("Level {level}"),
    }
}

fn element_morale_color(level: u8) -> egui::Color32 {
    match level {
        1..=7 => egui::Color32::from_rgb(235, 112, 112),
        8..=10 => egui::Color32::from_rgb(216, 181, 99),
        11..=14 => egui::Color32::from_rgb(121, 205, 148),
        _ => egui::Color32::from_rgb(72, 210, 132),
    }
}

fn show_squads(
'@
$club = Replace-Required $club $helperAnchor $moraleHelpers 'morale helper insertion'

$club = Replace-Required $club @'
            egui::RichText::new("v3.8.2 • SQUAD INTELLIGENCE")
'@ @'
            egui::RichText::new("v3.8.3 • SQUAD HEALTH")
'@ 'v3.8.3 version badge'

# Subtitle is cosmetic; keep it non-fragile across premium layout passes.
$club = $club.Replace(
    'Live membership + verified contract wage + squad status. Click any player name to open the Player Editor.',
    'Live membership + wage + squad status + verified FM27 morale. Click any player name to open the Player Editor.'
)

$club = Replace-Required $club @'
            .selected_text(match sort { 0 => "Name", 1 => "Position", 2 => "Age", 3 => "CA", 4 => "PA", 5 => "Squad Status", _ => "Wage" })
'@ @'
            .selected_text(match sort { 0 => "Name", 1 => "Position", 2 => "Age", 3 => "CA", 4 => "PA", 5 => "Squad Status", 6 => "Wage", _ => "Morale" })
'@ 'morale sort selected text'

$club = Replace-Required $club @'
                ui.selectable_value(&mut sort, 6, "Wage");
'@ @'
                ui.selectable_value(&mut sort, 6, "Wage");
                ui.selectable_value(&mut sort, 7, "Morale");
'@ 'morale sort option'

$club = Replace-Required $club @'
            5 => a.squad_status.cmp(&b.squad_status),
            _ => a.wage.cmp(&b.wage),
'@ @'
            5 => a.squad_status.cmp(&b.squad_status),
            6 => a.wage.cmp(&b.wage),
            _ => a.morale.cmp(&b.morale),
'@ 'morale sort comparator'

$club = Replace-Required $club @'
                            ui.label("—").on_hover_text("Morale is not cached from a certified FM27 field yet.");
'@ @'
                            match player.morale {
                                Some(level) => {
                                    let label = element_morale_name(level);
                                    ui.label(
                                        egui::RichText::new(label)
                                            .strong()
                                            .color(element_morale_color(level)),
                                    )
                                    .on_hover_text(format!("Verified FM27 squad morale: level {level}/20. Only independently witnessed levels receive semantic labels."));
                                }
                                None => {
                                    ui.label("—").on_hover_text("No valid FM27 morale level was readable for this player.");
                                }
                            }
'@ 'live morale cell'

# Make the remaining condition placeholder explicit rather than implying the
# roster failed to load it.
$club = $club.Replace(
    'Condition is not cached from a certified FM27 field yet.',
    'Condition/Fitness/Sharpness remain unmapped in FM27; Element will not guess these values.'
)

# Explain why the reserve buttons stay gated even though the club family vector
# itself is now known from independent upstream validation.
$club = $club.Replace(
    'Reserve-team type classification is not yet independently certified. Element will not guess it from pointers.',
    'The reserve-team vector is known, but B/Reserve vs U19 team-type classification is not independently certified yet.'
)
$club = $club.Replace(
    'Youth-team type classification is not yet independently certified. Element will not guess it from pointers.',
    'The reserve-team vector is known, but B/Reserve vs U19 team-type classification is not independently certified yet.'
)

Write-Text $clubPath $club
Write-Host 'Element v3.8.3 Squad Morale Intelligence applied successfully.'
