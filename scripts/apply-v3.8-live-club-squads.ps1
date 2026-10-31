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
    if (-not $Text.Contains($Old)) { throw "v3.8: expected source fragment not found: $Label" }
    return $Text.Replace($Old, $New)
}

# -----------------------------------------------------------------------------
# Element v3.8 — LIVE CLUB SQUADS
#
# Read-side only. Backports the already-validated FM27 player -> team -> club
# membership chain into the bulk cache, then turns Club > Squads into a real
# roster browser with search/sort and click-through to the Player Editor.
#
# No squad writes. No guessed condition/morale/wage offsets. B/U19 remain
# visibly gated until team-type membership is independently validated.
# -----------------------------------------------------------------------------

# ======================== CACHE MEMBERSHIP ====================================
$bulkPath = 'src/bridge/bulk_load.rs'
$bulk = Read-Text $bulkPath
$clubNamesMarker = @'
    let club_names: HashMap<u32, String> = clubs
        .iter()
        .map(|c| (c.uid, c.name.clone()))
        .collect();
'@
$membershipBlock = @'
    // Element v3.8: resolve current club membership from the verified FM27
    // player -> team -> club chain. The cache stores the club UID so Club >
    // Squads can filter instantly without another process-memory round trip.
    // Game Pass stays gated because its RVAs/layout have not been certified.
    if fm.build == crate::game_version::GameBuild::Fm27Steam {
        let clubs_by_addr: HashMap<u64, u32> =
            clubs.iter().map(|c| (c.addr, c.uid)).collect();
        for player in &mut players {
            let phys = |off| {
                crate::player::player_phys_offset(schemas, off, player.person_shift)
            };
            player.club_id = crate::fields::resolve_sub_ptr_mapped(
                fm,
                player.addr,
                "club",
                schemas.player_sub_records,
                &phys,
            )
            .and_then(|club_addr| clubs_by_addr.get(&club_addr).copied());
        }
    }

    let club_names: HashMap<u32, String> = clubs
        .iter()
        .map(|c| (c.uid, c.name.clone()))
        .collect();
'@
$bulk = Replace-Required $bulk $clubNamesMarker $membershipBlock 'bulk club membership insertion'
Write-Text $bulkPath $bulk

# ======================== PLAYER CLICK-THROUGH ================================
$navPath = 'src/ui/navigation.rs'
$nav = Read-Text $navPath
$editMarker = '/// Editing availability is published once by the app; standalone panel previews are read-only.'
$playerNavigation = @'
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct PlayerTarget {
    pub addr: u64,
    pub index: usize,
    pub name: String,
}

/// Clone the published entity cache for detail pages that need cache-driven
/// related rows. Arc makes this cheap and keeps the source cache immutable.
pub fn entity_cache(ui: &egui::Ui) -> Option<Arc<EntityCache>> {
    ui.ctx()
        .data_mut(|d| d.get_temp::<Option<Arc<EntityCache>>>(egui::Id::new("entity_link_cache")))
        .flatten()
}

/// Render a cached player as an editor navigation link.
pub fn player_link(ui: &mut egui::Ui, player: &crate::cache::CachedPlayer) {
    let name = if player.name.trim().is_empty() {
        format!("Player {}", player.uid)
    } else {
        player.name.clone()
    };
    if ui
        .link(&name)
        .on_hover_text("Open player in Player Editor")
        .clicked()
    {
        ui.ctx().data_mut(|d| {
            d.insert_temp(
                egui::Id::new("open_related_player"),
                PlayerTarget {
                    addr: player.addr,
                    index: player.index,
                    name,
                },
            )
        });
    }
}

pub fn take_player_target(ctx: &egui::Context) -> Option<PlayerTarget> {
    ctx.data_mut(|d| {
        let id = egui::Id::new("open_related_player");
        let target = d.get_temp::<PlayerTarget>(id);
        d.remove::<PlayerTarget>(id);
        target
    })
}

'@
if (-not $nav.Contains($editMarker)) { throw 'v3.8: navigation insertion boundary not found' }
$nav = $nav.Replace($editMarker, $playerNavigation + $editMarker)
Write-Text $navPath $nav

# App-level navigation consumes the player target just like the existing club target.
$appPath = 'src/app.rs'
$app = Read-Text $appPath
$relatedClubMarker = @'
        // Related names open through the same path as tabs and history.
        if let Some(target) = navigation::take_club_target(ctx) {
'@
$relatedPlayerBlock = @'
        // Related names open through the same path as tabs and history.
        if let Some(target) = navigation::take_player_target(ctx) {
            let entry = HistoryEntry {
                entity_type: EntityTabType::Player,
                addr: target.addr,
                index: target.index,
                display_name: target.name,
            };
            self.push_history(entry.clone());
            self.activate_history_entry(entry);
        }
        if let Some(target) = navigation::take_club_target(ctx) {
'@
$app = Replace-Required $app $relatedClubMarker $relatedPlayerBlock 'related player navigation hook'
Write-Text $appPath $app

# ======================== PREMIUM LIVE SQUADS UI ==============================
$clubPath = 'src/ui/club_panel.rs'
$clubUi = Read-Text $clubPath
$clubUi = Replace-Required $clubUi 'ClubTab::Squads => show_squads(ui, club),' 'ClubTab::Squads => show_squads(schemas, ui, club),' 'Squads show signature call'

$squadStart = $clubUi.IndexOf('fn show_squads(')
$squadEnd = $clubUi.IndexOf('fn show_club_vision(', $squadStart)
if ($squadStart -lt 0 -or $squadEnd -lt 0) { throw 'v3.8: show_squads function boundaries not found' }

$newSquads = @'
fn element_squad_age(
    schemas: &'static crate::fields::VersionedSchemas,
    player: &crate::cache::CachedPlayer,
) -> Option<u16> {
    if player.dob_year == 0 { return None; }
    Some(schemas.age_reference_year.saturating_sub(player.dob_year))
}

fn element_squad_position(
    schemas: &'static crate::fields::VersionedSchemas,
    player: &crate::cache::CachedPlayer,
) -> (&'static str, u8) {
    let mut best = ("—", 0u8);
    for &(key, label) in crate::ui::pages::player_search::POSITION_OFFSETS.iter() {
        let Some(offset) = schemas.offset_of(key) else { continue; };
        let Some(value) = player.raw.get(offset).copied() else { continue; };
        if (1..=20).contains(&value) && value > best.1 {
            best = (label, value);
        }
    }
    best
}

fn show_squads(
    schemas: &'static crate::fields::VersionedSchemas,
    ui: &mut egui::Ui,
    club: &ClubView,
) {
    ui.spacing_mut().item_spacing = egui::vec2(6.0, 4.0);

    ui.horizontal(|ui| {
        ui.label(
            egui::RichText::new("LIVE CLUB SQUADS")
                .size(13.0)
                .strong()
                .color(egui::Color32::from_rgb(225, 232, 245)),
        );
        ui.separator();
        ui.label(
            egui::RichText::new("v3.8 • READ-SIDE")
                .size(8.0)
                .strong()
                .color(egui::Color32::from_rgb(72, 210, 132)),
        );
    });
    ui.label(
        egui::RichText::new("Real player membership from the verified FM27 player → team → club chain. Click any player name to open the Player Editor.")
            .size(8.5)
            .color(egui::Color32::from_rgb(154, 169, 194)),
    );
    ui.add_space(4.0);

    ui.horizontal(|ui| {
        ui.selectable_label(true, "FIRST TEAM / CLUB");
        ui.add_enabled(false, egui::Button::new("B / RESERVES"))
            .on_disabled_hover_text("Reserve-team type classification is not yet independently certified. Element will not guess it from pointers.");
        ui.add_enabled(false, egui::Button::new("U19 / YOUTH"))
            .on_disabled_hover_text("Youth-team type classification is not yet independently certified. Element will not guess it from pointers.");
    });
    ui.add_space(5.0);

    let Some(cache) = navigation::entity_cache(ui) else {
        locked_notice(ui, "Entity cache is not available. Reload the save while FM27 is connected.");
        return;
    };

    let mapped_memberships = cache.players.iter().filter(|p| p.club_id.is_some()).count();
    if mapped_memberships == 0 {
        locked_notice(ui, "No certified player→club memberships are present in this cache. Reload Save to rebuild the v3.8 membership index.");
        return;
    }

    let search_id = egui::Id::new(("element_live_squad_search", club.addr));
    let sort_id = egui::Id::new(("element_live_squad_sort", club.addr));
    let desc_id = egui::Id::new(("element_live_squad_desc", club.addr));
    let mut search = ui.ctx().data_mut(|d| d.get_temp::<String>(search_id).unwrap_or_default());
    let mut sort = ui.ctx().data_mut(|d| d.get_temp::<u8>(sort_id).unwrap_or(3));
    let mut descending = ui.ctx().data_mut(|d| d.get_temp::<bool>(desc_id).unwrap_or(true));

    ui.horizontal_wrapped(|ui| {
        ui.label(egui::RichText::new("FILTER").size(8.0).strong().color(egui::Color32::from_rgb(139, 157, 188)));
        let r = ui.add_sized(
            [250.0, 22.0],
            egui::TextEdit::singleline(&mut search).hint_text("Search this squad…"),
        );
        if r.changed() {
            ui.ctx().data_mut(|d| d.insert_temp(search_id, search.clone()));
        }
        ui.separator();
        ui.label(egui::RichText::new("SORT").size(8.0).strong().color(egui::Color32::from_rgb(139, 157, 188)));
        egui::ComboBox::from_id_salt(("element_live_squad_sort_combo", club.addr))
            .selected_text(match sort { 0 => "Name", 1 => "Position", 2 => "Age", 3 => "CA", _ => "PA" })
            .show_ui(ui, |ui| {
                ui.selectable_value(&mut sort, 0, "Name");
                ui.selectable_value(&mut sort, 1, "Position");
                ui.selectable_value(&mut sort, 2, "Age");
                ui.selectable_value(&mut sort, 3, "CA");
                ui.selectable_value(&mut sort, 4, "PA");
            });
        ui.checkbox(&mut descending, "Descending");
        ui.ctx().data_mut(|d| {
            d.insert_temp(sort_id, sort);
            d.insert_temp(desc_id, descending);
        });
    });

    let query = search.trim().to_lowercase();
    let mut rows: Vec<&crate::cache::CachedPlayer> = cache
        .players
        .iter()
        .filter(|p| p.club_id == Some(club.uid))
        .filter(|p| query.is_empty() || p.name.to_lowercase().contains(&query) || p.uid.to_string() == query)
        .collect();

    rows.sort_by(|a, b| {
        let ord = match sort {
            0 => a.name.to_lowercase().cmp(&b.name.to_lowercase()),
            1 => element_squad_position(schemas, a).0.cmp(element_squad_position(schemas, b).0),
            2 => element_squad_age(schemas, a).cmp(&element_squad_age(schemas, b)),
            3 => a.ca.cmp(&b.ca),
            _ => a.pa.cmp(&b.pa),
        };
        if descending { ord.reverse() } else { ord }
    });

    ui.add_space(4.0);
    egui::Frame::group(ui.style())
        .fill(egui::Color32::from_rgb(22, 28, 41))
        .stroke(egui::Stroke::new(1.0, egui::Color32::from_rgb(43, 52, 70)))
        .rounding(egui::Rounding::same(4))
        .inner_margin(egui::Margin::symmetric(7, 5))
        .show(ui, |ui| {
            ui.horizontal(|ui| {
                ui.label(egui::RichText::new(format!("{} PLAYERS", rows.len())).size(8.5).strong().color(egui::Color32::from_rgb(112, 177, 255)));
                ui.separator();
                ui.label(egui::RichText::new(&club.full_name).size(9.0).strong());
                ui.separator();
                ui.label(egui::RichText::new("LIVE MEMBERSHIP").size(7.5).strong().color(egui::Color32::from_rgb(72, 210, 132)));
            });
            ui.add_space(3.0);

            if rows.is_empty() {
                ui.label("No players match this club/filter in the certified membership cache.");
                return;
            }

            egui::ScrollArea::horizontal().show(ui, |ui| {
                egui::Grid::new(("element_live_squad_grid", club.addr))
                    .num_columns(9)
                    .striped(true)
                    .spacing([14.0, 4.0])
                    .show(ui, |ui| {
                        for h in ["Player", "Position", "Age", "CA", "PA", "Condition", "Morale", "Squad Status", "Wage"] {
                            ui.label(egui::RichText::new(h).size(8.0).strong().color(egui::Color32::from_rgb(170, 185, 210)));
                        }
                        ui.end_row();

                        for player in rows {
                            navigation::player_link(ui, player);
                            let (position, familiarity) = element_squad_position(schemas, player);
                            ui.label(position).on_hover_text(if familiarity > 0 { format!("Best mapped familiarity: {familiarity}/20") } else { "No mapped position familiarity".to_string() });
                            ui.label(element_squad_age(schemas, player).map(|v| v.to_string()).unwrap_or_else(|| "—".into()));
                            ui.label(egui::RichText::new(player.ca.to_string()).strong());
                            ui.label(egui::RichText::new(player.pa.to_string()).strong());
                            ui.label("—").on_hover_text("Condition is not cached from a certified FM27 field yet.");
                            ui.label("—").on_hover_text("Morale is not cached from a certified FM27 field yet.");
                            ui.label("—").on_hover_text("Squad-status collection is not certified yet.");
                            ui.label("—").on_hover_text("Wage lives in the player contract sub-record and is loaded when the Player Editor opens; v3.8 does not fabricate it in the bulk roster cache.");
                            ui.end_row();
                        }
                    });
            });
        });

    ui.add_space(5.0);
    ui.horizontal_wrapped(|ui| {
        ui.label(egui::RichText::new("READ-SIDE SAFE").size(7.5).strong().color(egui::Color32::from_rgb(72, 210, 132)));
        ui.separator();
        ui.label(egui::RichText::new("No squad membership writes • no transfer writes • Force Transfer remains locked").size(8.0).color(egui::Color32::from_rgb(139, 157, 188)));
    });
}

'@
$clubUi = $clubUi.Substring(0, $squadStart) + $newSquads + $clubUi.Substring($squadEnd)
Write-Text $clubPath $clubUi

Write-Host 'Element v3.8 LIVE CLUB SQUADS applied successfully.'
