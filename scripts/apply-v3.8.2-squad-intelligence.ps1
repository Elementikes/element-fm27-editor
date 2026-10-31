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
    if (-not $Text.Contains($Old)) { throw "v3.8.2: expected source fragment not found: $Label" }
    return $Text.Replace($Old, $New)
}

# -----------------------------------------------------------------------------
# Element v3.8.2 — SQUAD INTELLIGENCE
# Read-side only. Promote already-certified FM27 contract fields into the live
# club roster cache. No new offsets are guessed here.
# -----------------------------------------------------------------------------

$cachePath = 'src/cache.rs'
$cache = Read-Text $cachePath
$cache = Replace-Required $cache @'
    pub value:     Option<u64>,
'@ @'
    pub value:     Option<u64>,
    /// Verified FM27 contract wage (weekly), cached for live squad rows.
    pub wage:      Option<u32>,
    /// Verified FM27 agreed playing-time / squad-status code.
    pub squad_status: Option<u8>,
'@ 'CachedPlayer contract summary fields'
Write-Text $cachePath $cache

$bulkPath = 'src/bridge/bulk_load.rs'
$bulk = Read-Text $bulkPath
$bulk = Replace-Required $bulk @'
            nation_id: None, club_id: None, value: None,
'@ @'
            nation_id: None, club_id: None, value: None,
            wage: None, squad_status: None,
'@ 'CachedPlayer initializer contract summary'

$oldMembership = @'
            player.club_id = crate::fields::resolve_sub_ptr_mapped(
                fm,
                player.addr,
                "club",
                schemas.player_sub_records,
                &phys,
            )
            .and_then(|club_addr| clubs_by_addr.get(&club_addr).copied());
'@
$newMembership = @'
            player.club_id = crate::fields::resolve_sub_ptr_mapped(
                fm,
                player.addr,
                "club",
                schemas.player_sub_records,
                &phys,
            )
            .and_then(|club_addr| clubs_by_addr.get(&club_addr).copied());

            // v3.8.2: contract summary for the roster table. The contract
            // pointer and both field offsets are already certified by the
            // FM27 schema; resolve them generically instead of hardcoding.
            if let Some(contract_addr) = crate::fields::resolve_sub_ptr_mapped(
                fm,
                player.addr,
                "contract",
                schemas.player_sub_records,
                &phys,
            ) {
                if let Some(offset) = schemas.offset_of("p_contract_wage") {
                    player.wage = fm.read_u32(contract_addr + offset as u64).ok();
                }
                if let Some(offset) = schemas.offset_of("p_squad_status") {
                    player.squad_status = fm.read_u8(contract_addr + offset as u64).ok();
                }
            }
'@
$bulk = Replace-Required $bulk $oldMembership $newMembership 'membership loop contract cache'
Write-Text $bulkPath $bulk

$clubPath = 'src/ui/club_panel.rs'
$club = Read-Text $clubPath

$helperAnchor = @'
fn show_squads(
'@
$helpers = @'
fn element_squad_status_name(code: u8) -> Option<&'static str> {
    Some(match code {
        1 => "Star Player",
        2 => "Important Player",
        3 => "Regular Starter",
        4 | 6 => "Squad Player",
        5 => "Impact Sub",
        7 | 8 => "Fringe Player",
        9 | 21 => "Emergency Backup",
        10 => "Breakthrough Prospect",
        11 => "Future Prospect",
        12 => "Hot Prospect",
        13 => "Youngster",
        14 => "Regular",
        15 => "First-Choice GK",
        16 | 19 => "Cup Goalkeeper",
        17 => "Domestic Cup GK",
        18 => "Continental Cup GK",
        20 => "Backup",
        22 => "Surplus",
        23 => "Scouting Required",
        24 => "Out On Loan",
        _ => return None,
    })
}

fn element_format_weekly_wage(value: u32) -> String {
    let raw = value.to_string();
    let mut grouped = String::with_capacity(raw.len() + raw.len() / 3);
    for (i, ch) in raw.chars().enumerate() {
        if i > 0 && (raw.len() - i) % 3 == 0 {
            grouped.push(',');
        }
        grouped.push(ch);
    }
    format!("£{grouped}/w")
}

fn show_squads(
'@
$club = Replace-Required $club $helperAnchor $helpers 'squad intelligence helper insertion'

$club = Replace-Required $club @'
            egui::RichText::new("v3.8 • READ-SIDE")
'@ @'
            egui::RichText::new("v3.8.2 • SQUAD INTELLIGENCE")
'@ 'squad intelligence version badge'

# Subtitle wording changed during earlier premium UI passes, so this polish is
# intentionally best-effort instead of a build-blocking source boundary.
$club = $club.Replace(
    'Real player membership from the verified FM27 player → team → club chain. Click any player name to open the Player Editor.',
    'Live membership + verified contract wage + squad status. Click any player name to open the Player Editor.'
)

$club = Replace-Required $club @'
            .selected_text(match sort { 0 => "Name", 1 => "Position", 2 => "Age", 3 => "CA", _ => "PA" })
'@ @'
            .selected_text(match sort { 0 => "Name", 1 => "Position", 2 => "Age", 3 => "CA", 4 => "PA", 5 => "Squad Status", _ => "Wage" })
'@ 'squad sort selected text'

$club = Replace-Required $club @'
                ui.selectable_value(&mut sort, 4, "PA");
'@ @'
                ui.selectable_value(&mut sort, 4, "PA");
                ui.selectable_value(&mut sort, 5, "Squad Status");
                ui.selectable_value(&mut sort, 6, "Wage");
'@ 'squad sort new options'

$club = Replace-Required $club @'
            3 => a.ca.cmp(&b.ca),
            _ => a.pa.cmp(&b.pa),
'@ @'
            3 => a.ca.cmp(&b.ca),
            4 => a.pa.cmp(&b.pa),
            5 => a.squad_status.cmp(&b.squad_status),
            _ => a.wage.cmp(&b.wage),
'@ 'squad sort contract values'

$club = Replace-Required $club @'
                            ui.label("—").on_hover_text("Squad-status collection is not certified yet.");
                            ui.label("—").on_hover_text("Wage lives in the player contract sub-record and is loaded when the Player Editor opens; v3.8 does not fabricate it in the bulk roster cache.");
'@ @'
                            match player.squad_status {
                                Some(0) | None => {
                                    ui.label("—").on_hover_text("No agreed playing-time status is stored on this contract.");
                                }
                                Some(code) => {
                                    let label = element_squad_status_name(code)
                                        .map(str::to_owned)
                                        .unwrap_or_else(|| format!("Code {code}"));
                                    ui.label(label).on_hover_text(format!("Verified contract squad-status code: {code}"));
                                }
                            }
                            match player.wage {
                                Some(wage) => {
                                    ui.label(egui::RichText::new(element_format_weekly_wage(wage)).strong())
                                        .on_hover_text("Verified FM27 contract wage; weekly value from the live contract record.");
                                }
                                None => {
                                    ui.label("—").on_hover_text("No readable contract wage for this player.");
                                }
                            }
'@ 'live squad status and wage cells'

# Footer wording is cosmetic and may differ after premium UI passes.
$club = $club.Replace(
    'No squad membership writes • no transfer writes • Force Transfer remains locked',
    'Verified contract read-side • no squad writes • no transfer writes • Force Transfer remains locked'
)

Write-Text $clubPath $club

# Continue with verified live morale. This remains read-side only; condition /
# fitness / sharpness stay gated until their FM27 locations are certified.
$moralePatch = Join-Path $PSScriptRoot 'apply-v3.8.3-squad-morale.ps1'
if (-not (Test-Path -LiteralPath $moralePatch)) {
    throw "v3.8.3 squad morale patch missing: $moralePatch"
}
& $moralePatch

# Continue with the certified FM27 staff employer + contract job chain.
$staffPatch = Join-Path $PSScriptRoot 'apply-v3.9-live-club-staff.ps1'
if (-not (Test-Path -LiteralPath $staffPatch)) {
    throw "v3.9 live club staff patch missing: $staffPatch"
}
& $staffPatch

Write-Host 'Element v3.8.2 Squad Intelligence + v3.8.3 Squad Morale + v3.9 Club Staff Live applied successfully.'
