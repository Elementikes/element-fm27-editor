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
    if (-not $Text.Contains($Old)) { throw "v3.9: expected source fragment not found: $Label" }
    return $Text.Replace($Old, $New)
}

# -----------------------------------------------------------------------------
# Element v3.9 — CLUB STAFF LIVE
# Read-side only. Uses the certified FM27 staff contract -> team -> club chain
# and the verified contract job code. No new offsets are guessed.
# -----------------------------------------------------------------------------

# ======================== CACHE: STAFF MEMBERSHIP + JOB ========================
$cachePath = 'src/cache.rs'
$cache = Read-Text $cachePath
$cache = Replace-Required $cache @'
    pub nation_id: Option<u32>,
    pub club_id:   Option<u32>,
}
'@ @'
    pub nation_id: Option<u32>,
    pub club_id:   Option<u32>,
    /// Verified FM27 contract job code (`s_job`).
    pub job:       Option<u8>,
}
'@ 'CachedStaff job field'
Write-Text $cachePath $cache

$bulkPath = 'src/bridge/bulk_load.rs'
$bulk = Read-Text $bulkPath
$bulk = Replace-Required $bulk @'
            nation_id: None, club_id: None,
        });
'@ @'
            nation_id: None, club_id: None, job: None,
        });
'@ 'CachedStaff initializer'

$clubNamesAnchor = @'
    let club_names: HashMap<u32, String> = clubs
        .iter()
        .map(|c| (c.uid, c.name.clone()))
        .collect();
'@
$staffMembership = @'
    // Element v3.9: resolve staff employer through the verified FM27 chain
    // staff -> contract -> team -> club and cache the verified contract job.
    if fm.build == crate::game_version::GameBuild::Fm27Steam {
        let clubs_by_addr: HashMap<u64, u32> =
            clubs.iter().map(|c| (c.addr, c.uid)).collect();
        for member in &mut staff {
            let phys = |off| off;
            member.club_id = crate::fields::resolve_sub_ptr_mapped(
                fm,
                member.addr,
                "club",
                schemas.staff_sub_records,
                &phys,
            )
            .and_then(|club_addr| clubs_by_addr.get(&club_addr).copied());

            if let Some(contract_addr) = crate::fields::resolve_sub_ptr_mapped(
                fm,
                member.addr,
                "contract",
                schemas.staff_sub_records,
                &phys,
            ) {
                if let Some(offset) = schemas.offset_of("s_job") {
                    member.job = fm.read_u8(contract_addr + offset as u64).ok();
                }
            }
        }
    }

    let club_names: HashMap<u32, String> = clubs
        .iter()
        .map(|c| (c.uid, c.name.clone()))
        .collect();
'@
$bulk = Replace-Required $bulk $clubNamesAnchor $staffMembership 'staff membership insertion'
Write-Text $bulkPath $bulk

# ======================== STAFF CLICK-THROUGH ==================================
$navPath = 'src/ui/navigation.rs'
$nav = Read-Text $navPath
$staffAnchor = @'
pub fn take_player_target(ctx: &egui::Context) -> Option<PlayerTarget> {
    ctx.data_mut(|d| {
        let id = egui::Id::new("open_related_player");
        let target = d.get_temp::<PlayerTarget>(id);
        d.remove::<PlayerTarget>(id);
        target
    })
}

'@
$staffNav = @'
pub fn take_player_target(ctx: &egui::Context) -> Option<PlayerTarget> {
    ctx.data_mut(|d| {
        let id = egui::Id::new("open_related_player");
        let target = d.get_temp::<PlayerTarget>(id);
        d.remove::<PlayerTarget>(id);
        target
    })
}

#[derive(Clone, Debug, PartialEq, Eq)]
pub struct StaffTarget {
    pub addr: u64,
    pub index: usize,
    pub name: String,
}

pub fn staff_link(ui: &mut egui::Ui, staff: &crate::cache::CachedStaff) {
    let name = if staff.name.trim().is_empty() {
        format!("Staff {}", staff.uid)
    } else {
        staff.name.clone()
    };
    if ui
        .link(&name)
        .on_hover_text("Open staff member in Staff Editor")
        .clicked()
    {
        ui.ctx().data_mut(|d| {
            d.insert_temp(
                egui::Id::new("open_related_staff"),
                StaffTarget {
                    addr: staff.addr,
                    index: staff.index,
                    name,
                },
            )
        });
    }
}

pub fn take_staff_target(ctx: &egui::Context) -> Option<StaffTarget> {
    ctx.data_mut(|d| {
        let id = egui::Id::new("open_related_staff");
        let target = d.get_temp::<StaffTarget>(id);
        d.remove::<StaffTarget>(id);
        target
    })
}

'@
$nav = Replace-Required $nav $staffAnchor $staffNav 'staff navigation helpers'
Write-Text $navPath $nav

$appPath = 'src/app.rs'
$app = Read-Text $appPath
$playerHook = @'
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
'@
$staffHook = @'
        if let Some(target) = navigation::take_staff_target(ctx) {
            let entry = HistoryEntry {
                entity_type: EntityTabType::Staff,
                addr: target.addr,
                index: target.index,
                display_name: target.name,
            };
            self.push_history(entry.clone());
            self.activate_history_entry(entry);
        }
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
'@
$app = Replace-Required $app $playerHook $staffHook 'staff app navigation hook'
Write-Text $appPath $app

# ======================== CLUB > STAFF LIVE UI =================================
$clubPath = 'src/ui/club_panel.rs'
$club = Read-Text $clubPath
$club = Replace-Required $club 'ClubTab::Staff => show_staff(ui),' 'ClubTab::Staff => show_staff(schemas, ui, club),' 'club staff show call'

$staffStart = $club.IndexOf('fn show_staff(')
$staffEnd = $club.IndexOf('fn show_affiliations(', $staffStart)
if ($staffStart -lt 0 -or $staffEnd -lt 0) { throw 'v3.9: show_staff function boundaries not found' }

$newStaff = @'
fn element_staff_age(
    schemas: &'static crate::fields::VersionedSchemas,
    staff: &crate::cache::CachedStaff,
) -> Option<u16> {
    if staff.dob_year == 0 { return None; }
    Some(schemas.age_reference_year.saturating_sub(staff.dob_year))
}

fn element_staff_job(staff: &crate::cache::CachedStaff) -> String {
    staff.job
        .and_then(crate::staff::job_name)
        .map(str::to_owned)
        .or_else(|| staff.job.map(|code| format!("Job {code}")))
        .unwrap_or_else(|| "—".to_owned())
}

fn element_staff_group(job: Option<u8>) -> &'static str {
    match job {
        Some(16) => "MANAGER",
        Some(2 | 20 | 22 | 26 | 34 | 64) => "COACHING",
        Some(14 | 44 | 58 | 60) => "RECRUITMENT & ANALYSIS",
        Some(12 | 40 | 48 | 50) => "MEDICAL & SCIENCE",
        Some(4 | 6 | 86 | 88) => "DIRECTORS & OPERATIONS",
        _ => "OTHER STAFF",
    }
}

fn show_staff(
    schemas: &'static crate::fields::VersionedSchemas,
    ui: &mut egui::Ui,
    club: &ClubView,
) {
    ui.spacing_mut().item_spacing = egui::vec2(6.0, 4.0);
    ui.horizontal(|ui| {
        ui.label(
            egui::RichText::new("LIVE CLUB STAFF")
                .size(13.0)
                .strong()
                .color(egui::Color32::from_rgb(225, 232, 245)),
        );
        ui.separator();
        ui.label(
            egui::RichText::new("v3.9 • STAFF LIVE")
                .size(8.0)
                .strong()
                .color(egui::Color32::from_rgb(72, 210, 132)),
        );
    });
    ui.label(
        egui::RichText::new("Verified FM27 employer + contract job chain. Click any staff name to open the Staff Editor.")
            .size(8.5)
            .color(egui::Color32::from_rgb(154, 169, 194)),
    );
    ui.add_space(5.0);

    let Some(cache) = navigation::entity_cache(ui) else {
        locked_notice(ui, "Entity cache is unavailable. Reload the save while FM27 is connected.");
        return;
    };
    let mapped = cache.staff.iter().filter(|s| s.club_id.is_some()).count();
    if mapped == 0 {
        locked_notice(ui, "No certified staff→club memberships are present in this cache. Reload Save to rebuild the v3.9 staff index.");
        return;
    }

    let search_id = egui::Id::new(("element_live_staff_search", club.addr));
    let sort_id = egui::Id::new(("element_live_staff_sort", club.addr));
    let desc_id = egui::Id::new(("element_live_staff_desc", club.addr));
    let mut search = ui.ctx().data_mut(|d| d.get_temp::<String>(search_id).unwrap_or_default());
    let mut sort = ui.ctx().data_mut(|d| d.get_temp::<u8>(sort_id).unwrap_or(3));
    let mut descending = ui.ctx().data_mut(|d| d.get_temp::<bool>(desc_id).unwrap_or(true));

    ui.horizontal_wrapped(|ui| {
        ui.label(egui::RichText::new("FILTER").size(8.0).strong().color(egui::Color32::from_rgb(139, 157, 188)));
        let r = ui.add_sized([250.0, 22.0], egui::TextEdit::singleline(&mut search).hint_text("Search club staff…"));
        if r.changed() { ui.ctx().data_mut(|d| d.insert_temp(search_id, search.clone())); }
        ui.separator();
        ui.label(egui::RichText::new("SORT").size(8.0).strong().color(egui::Color32::from_rgb(139, 157, 188)));
        egui::ComboBox::from_id_salt(("element_live_staff_sort_combo", club.addr))
            .selected_text(match sort { 0 => "Name", 1 => "Role", 2 => "Age", 3 => "CA", _ => "PA" })
            .show_ui(ui, |ui| {
                ui.selectable_value(&mut sort, 0, "Name");
                ui.selectable_value(&mut sort, 1, "Role");
                ui.selectable_value(&mut sort, 2, "Age");
                ui.selectable_value(&mut sort, 3, "CA");
                ui.selectable_value(&mut sort, 4, "PA");
            });
        ui.checkbox(&mut descending, "Descending");
        ui.ctx().data_mut(|d| { d.insert_temp(sort_id, sort); d.insert_temp(desc_id, descending); });
    });

    let query = search.trim().to_lowercase();
    let mut rows: Vec<&crate::cache::CachedStaff> = cache
        .staff
        .iter()
        .filter(|s| s.club_id == Some(club.uid))
        .filter(|s| {
            query.is_empty()
                || s.name.to_lowercase().contains(&query)
                || s.uid.to_string() == query
                || element_staff_job(s).to_lowercase().contains(&query)
        })
        .collect();

    rows.sort_by(|a, b| {
        let ord = match sort {
            0 => a.name.to_lowercase().cmp(&b.name.to_lowercase()),
            1 => element_staff_job(a).cmp(&element_staff_job(b)),
            2 => element_staff_age(schemas, a).cmp(&element_staff_age(schemas, b)),
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
                ui.label(egui::RichText::new(format!("{} STAFF", rows.len())).size(8.5).strong().color(egui::Color32::from_rgb(112, 177, 255)));
                ui.separator();
                ui.label(egui::RichText::new(&club.full_name).size(9.0).strong());
                ui.separator();
                ui.label(egui::RichText::new("LIVE EMPLOYMENT").size(7.5).strong().color(egui::Color32::from_rgb(72, 210, 132)));
            });
            ui.add_space(3.0);

            if rows.is_empty() {
                ui.label("No staff match this club/filter in the certified employment cache.");
                return;
            }

            let groups = ["MANAGER", "COACHING", "RECRUITMENT & ANALYSIS", "MEDICAL & SCIENCE", "DIRECTORS & OPERATIONS", "OTHER STAFF"];
            for group in groups {
                let group_rows: Vec<_> = rows.iter().copied().filter(|s| element_staff_group(s.job) == group).collect();
                if group_rows.is_empty() { continue; }
                ui.add_space(4.0);
                ui.label(egui::RichText::new(format!("{group} • {}", group_rows.len())).size(8.0).strong().color(egui::Color32::from_rgb(139, 157, 188)));
                egui::Grid::new(("element_live_staff_grid", club.addr, group))
                    .num_columns(5)
                    .striped(true)
                    .spacing([16.0, 4.0])
                    .show(ui, |ui| {
                        for h in ["Name", "Role", "Age", "CA", "PA"] {
                            ui.label(egui::RichText::new(h).size(8.0).strong().color(egui::Color32::from_rgb(170, 185, 210)));
                        }
                        ui.end_row();
                        for member in group_rows {
                            navigation::staff_link(ui, member);
                            ui.label(element_staff_job(member));
                            ui.label(element_staff_age(schemas, member).map(|v| v.to_string()).unwrap_or_else(|| "—".into()));
                            ui.label(egui::RichText::new(member.ca.to_string()).strong());
                            ui.label(egui::RichText::new(member.pa.to_string()).strong());
                            ui.end_row();
                        }
                    });
            }
        });

    ui.add_space(5.0);
    ui.label(
        egui::RichText::new("READ-SIDE SAFE • no staff contract writes added in v3.9")
            .size(8.0)
            .color(egui::Color32::from_rgb(139, 157, 188)),
    );
}

'@
$club = $club.Substring(0, $staffStart) + $newStaff + $club.Substring($staffEnd)
Write-Text $clubPath $club

Write-Host 'Element v3.9 LIVE CLUB STAFF applied successfully.'
