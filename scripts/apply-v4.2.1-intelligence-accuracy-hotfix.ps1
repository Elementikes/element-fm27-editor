$ErrorActionPreference='Stop'
$SourceRoot=(Get-Location).Path
function Read-Text([string]$RelativePath){$p=Join-Path $SourceRoot $RelativePath;if(-not(Test-Path -LiteralPath $p)){throw "Source file not found: $p"};[IO.File]::ReadAllText($p)}
function Write-Text([string]$RelativePath,[string]$Text){$p=Join-Path $SourceRoot $RelativePath;[IO.File]::WriteAllText($p,$Text,[Text.UTF8Encoding]::new($false))}
function Replace-Required([string]$Text,[string]$Old,[string]$New,[string]$Label){if(-not $Text.Contains($Old)){throw "v4.2.1: expected source fragment not found: $Label"};$Text.Replace($Old,$New)}

# -----------------------------------------------------------------------------
# Element v4.2.1 — PLAYER INTELLIGENCE ACCURACY HOTFIX
# 1) Decode FM's encoded 1–20 attributes before Role Fit / attribute filters.
# 2) Decode position familiarity through schema locations as well.
# 3) Make free-agent/unresolved gender explicit as UNKNOWN instead of silently
#    deleting those players when one known-gender checkbox is disabled.
# No new memory offsets and no writes.
# -----------------------------------------------------------------------------

$path='src/ui/pages/player_search.rs'
$text=Read-Text $path

$text=Replace-Required $text @'
            gender_mask: 0b11,
'@ @'
            gender_mask: 0b111,
'@ 'default gender mask includes unknown'

$text=Replace-Required $text @'
        self.gender_mask = 0b11;
'@ @'
        self.gender_mask = 0b111;
'@ 'clear gender mask includes unknown'

$text=Replace-Required $text @'
fn element_player_attr(schemas: &'static crate::fields::VersionedSchemas, p: &CachedPlayer, key: &str) -> u8 {
    schemas.offset_of(key)
        .and_then(|o| p.raw.get(o).copied())
        .filter(|v| (1..=20).contains(v))
        .unwrap_or(1)
}
'@ @'
fn element_player_attr(schemas: &'static crate::fields::VersionedSchemas, p: &CachedPlayer, key: &str) -> u8 {
    let Some(field) = schemas.field(key) else { return 1; };
    let Some(loc) = field.offset.as_ref() else { return 1; };
    let Some(raw) = p.raw.get(loc.offset() as usize).copied() else { return 1; };
    let value = loc.decode_u8(raw);
    if (1..=20).contains(&value) { value } else { 1 }
}
'@ 'decode encoded scouting attributes'

$text=Replace-Required $text @'
fn element_best_position(schemas: &'static crate::fields::VersionedSchemas, p: &CachedPlayer) -> Option<(usize, u8)> {
    let mut best: Option<(usize, u8)> = None;
    for (bit, &(key, _)) in POSITION_OFFSETS.iter().enumerate() {
        let value = schemas.offset_of(key).and_then(|o| p.raw.get(o).copied()).unwrap_or(0);
        if (1..=20).contains(&value) && best.map_or(true, |(_, old)| value > old) {
            best = Some((bit, value));
        }
    }
    best
}
'@ @'
fn element_best_position(schemas: &'static crate::fields::VersionedSchemas, p: &CachedPlayer) -> Option<(usize, u8)> {
    let mut best: Option<(usize, u8)> = None;
    for (bit, &(key, _)) in POSITION_OFFSETS.iter().enumerate() {
        let value = schemas.field(key)
            .and_then(|f| f.offset.as_ref())
            .and_then(|loc| p.raw.get(loc.offset() as usize).copied().map(|raw| loc.decode_u8(raw)))
            .unwrap_or(0);
        if (1..=20).contains(&value) && best.map_or(true, |(_, old)| value > old) {
            best = Some((bit, value));
        }
    }
    best
}
'@ 'decode best-position familiarity'

$text=Replace-Required $text @'
    let fam = pos.iter().filter_map(|&bit| {
        let key = POSITION_OFFSETS.get(bit)?.0;
        schemas.offset_of(key).and_then(|o| p.raw.get(o).copied())
    }).max().unwrap_or(1).clamp(1,20) as f32;
    (attr * (0.70 + 0.30 * fam / 20.0)).round().clamp(0.0,100.0) as u8
}
'@ @'
    let fam = pos.iter().filter_map(|&bit| {
        let key = POSITION_OFFSETS.get(bit)?.0;
        let field = schemas.field(key)?;
        let loc = field.offset.as_ref()?;
        p.raw.get(loc.offset() as usize).copied().map(|raw| loc.decode_u8(raw))
    }).filter(|v| (1..=20).contains(v)).max().unwrap_or(1).clamp(1,20) as f32;

    // Position suitability matters heavily for a role. At natural familiarity
    // the attribute score is preserved; unfamiliar players are penalised hard
    // enough that an elite CB cannot outrank a natural ST at Poacher simply from
    // generic physical/mental attributes.
    let position_factor = 0.35 + 0.65 * (fam / 20.0);
    (attr * position_factor).round().clamp(0.0,100.0) as u8
}
'@ 'role-fit position decoding and weighting'

$text=Replace-Required $text @'
                let mut men = state.gender_mask & 1 != 0;
                let mut women = state.gender_mask & 2 != 0;
                if ui.checkbox(&mut men, "♂ MEN").changed() { if men { state.gender_mask |= 1 } else { state.gender_mask &= !1 } }
                if ui.checkbox(&mut women, "♀ WOMEN").changed() { if women { state.gender_mask |= 2 } else { state.gender_mask &= !2 } }
                ui.separator();
'@ @'
                let mut men = state.gender_mask & 1 != 0;
                let mut women = state.gender_mask & 2 != 0;
                let mut unknown = state.gender_mask & 4 != 0;
                if ui.checkbox(&mut men, "♂ MEN").changed() { if men { state.gender_mask |= 1 } else { state.gender_mask &= !1 } }
                if ui.checkbox(&mut women, "♀ WOMEN").changed() { if women { state.gender_mask |= 2 } else { state.gender_mask &= !2 } }
                if ui.checkbox(&mut unknown, "? FREE / UNKNOWN").on_hover_text("Free agents have no current club gender to inherit. Keep this enabled so clubless players such as Benzema are not silently removed.").changed() { if unknown { state.gender_mask |= 4 } else { state.gender_mask &= !4 } }
                ui.separator();
'@ 'explicit unknown/free-agent gender control'

$text=Replace-Required $text @'
                    state.gender_mask=0b11; state.quick_mode=0; state.best_position=-1; state.role=0; state.role_min=0; state.attribute_filter=0; state.attribute_min=12;
'@ @'
                    state.gender_mask=0b111; state.quick_mode=0; state.best_position=-1; state.role=0; state.role_min=0; state.attribute_filter=0; state.attribute_min=12;
'@ 'reset includes unknown gender'

$text=Replace-Required $text @'
            if state.gender_mask != 0b11 {
                let allowed = match p.gender { Some(0) => state.gender_mask & 1 != 0, Some(1) => state.gender_mask & 2 != 0, _ => false };
                if !allowed { return false; }
            }
'@ @'
            let allowed_gender = match p.gender {
                Some(0) => state.gender_mask & 1 != 0,
                Some(1) => state.gender_mask & 2 != 0,
                _ => state.gender_mask & 4 != 0,
            };
            if !allowed_gender { return false; }
'@ 'three-state gender filtering'

$text=Replace-Required $text @'
                let gender=match p.gender{Some(0)=>"MEN",Some(1)=>"WOMEN",_=>"—"};
'@ @'
                let gender=match p.gender{Some(0)=>"MEN",Some(1)=>"WOMEN",_=>"FREE?"};
'@ 'show unresolved free-agent gender honestly'

$text=$text.Replace(
    'Element Deal Score / Role Fit are transparent heuristics, not native FM ratings. Gender is verified through current-club membership; free-agent gender is never guessed.',
    'Role Fit now decodes FM encoded attributes before scoring. Gender is verified through current-club membership; clubless players remain FREE/UNKNOWN until a direct player-gender field is certified.'
)

Write-Text $path $text
Write-Host 'Element v4.2.1 Intelligence Accuracy hotfix applied successfully.'
