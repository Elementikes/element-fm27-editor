$ErrorActionPreference = 'Stop'
$SourceRoot = (Get-Location).Path

function Replace-Required {
    param([string]$RelativePath, [string]$Old, [string]$New)
    $Path = Join-Path $SourceRoot $RelativePath
    if (-not (Test-Path -LiteralPath $Path)) { throw "Source file not found: $Path" }
    $text = [IO.File]::ReadAllText($Path)
    if (-not $text.Contains($Old)) { throw "Expected text not found in $RelativePath`n--- expected ---`n$Old" }
    $text = $text.Replace($Old, $New)
    [IO.File]::WriteAllText($Path, $text, [Text.UTF8Encoding]::new($false))
}

$c = 'src/ui/club_panel.rs'
$cp = Join-Path $SourceRoot $c

# -----------------------------------------------------------------------------
# Full club navigation model: every documented FMRTE 27 club page + Element FM27 extras.
# -----------------------------------------------------------------------------
Replace-Required $c @'
#[derive(PartialEq)]
pub enum ClubTab {
    Overview,
    Facilities,
    Finance,
    TransferCenter,
    TacticalUnderstanding,
    Stadium,
}
'@ @'
#[derive(PartialEq)]
pub enum ClubTab {
    Overview,
    Squads,
    Facilities,
    Finance,
    ClubVision,
    PossibleSignings,
    PlayerClauses,
    TransferCenter,
    KitsColours,
    Tactics,
    Staff,
    Affiliations,
    RegionalDivisions,
    Ownership,
    Relationships,
    TacticalUnderstanding,
    Supporters,
    StadiumMove,
    TacticalEffectiveness,
    RegistrationEligibility,
    RecruitmentFit,
    Stadium,
}
'@

Replace-Required $c @'
    egui::ScrollArea::vertical().show(ui, |ui| match tab {
        ClubTab::Overview => show_overview(schemas, ui, club, &mut edits),
        ClubTab::Facilities => show_facilities(schemas, ui, club, &mut edits),
        ClubTab::Finance => show_finance(schemas, ui, club, &mut edits),
        ClubTab::TransferCenter => show_transfer_center(ui, club),
        ClubTab::TacticalUnderstanding => show_tactical_understanding(ui, club),
        ClubTab::Stadium => show_stadium(schemas, ui, club),
    });
'@ @'
    egui::ScrollArea::vertical().show(ui, |ui| match tab {
        ClubTab::Overview => show_overview(schemas, ui, club, &mut edits),
        ClubTab::Squads => show_squads(ui, club),
        ClubTab::Facilities => show_facilities(schemas, ui, club, &mut edits),
        ClubTab::Finance => show_finance(schemas, ui, club, &mut edits),
        ClubTab::ClubVision => show_club_vision(ui),
        ClubTab::PossibleSignings => show_possible_signings(ui),
        ClubTab::PlayerClauses => show_player_clauses(ui),
        ClubTab::TransferCenter => show_transfer_center(ui, club),
        ClubTab::KitsColours => show_kits_colours(ui),
        ClubTab::Tactics => show_tactics(ui),
        ClubTab::Staff => show_staff(ui),
        ClubTab::Affiliations => show_affiliations(ui),
        ClubTab::RegionalDivisions => show_regional_divisions(ui),
        ClubTab::Ownership => show_ownership(ui),
        ClubTab::Relationships => show_relationships(ui),
        ClubTab::TacticalUnderstanding => show_tactical_understanding(ui, club),
        ClubTab::Supporters => show_supporters(schemas, ui, club, &mut edits),
        ClubTab::StadiumMove => show_stadium_move(ui),
        ClubTab::TacticalEffectiveness => show_tactical_effectiveness(ui),
        ClubTab::RegistrationEligibility => show_registration_eligibility(ui),
        ClubTab::RecruitmentFit => show_recruitment_fit(ui),
        ClubTab::Stadium => show_stadium(schemas, ui, club),
    });
'@

# -----------------------------------------------------------------------------
# Insert the full club-page implementations immediately before show_stadium().
# Pages with unknown FM27 structures expose the real FMRTE fields but stay locked.
# Supporters uses verified FM27 fields and is live-editable.
# -----------------------------------------------------------------------------
$text = [IO.File]::ReadAllText($cp)
$insertAt = $text.IndexOf('fn show_stadium(')
if ($insertAt -lt 0) { throw 'v1.8: show_stadium insertion boundary not found' }
$pages = @'
fn locked_notice(ui: &mut egui::Ui, text: &str) {
    ui.label(
        egui::RichText::new(text)
            .small()
            .color(egui::Color32::from_rgb(255, 184, 77)),
    );
}

fn locked_field(ui: &mut egui::Ui, label: &str) {
    field_widget::stub_field(ui, label, "FM27 structure not mapped/validated yet");
}

fn page_card(ui: &mut egui::Ui, title: &str, add: impl FnOnce(&mut egui::Ui)) {
    egui::Frame::group(ui.style())
        .fill(egui::Color32::from_rgb(26, 32, 48))
        .stroke(egui::Stroke::new(1.0, egui::Color32::from_rgb(42, 50, 69)))
        .rounding(egui::Rounding::same(4))
        .inner_margin(egui::Margin::symmetric(8, 6))
        .show(ui, |ui| {
            ui.strong(title);
            ui.separator();
            add(ui);
        });
}

fn show_squads(ui: &mut egui::Ui, club: &ClubView) {
    ui.horizontal(|ui| {
        ui.selectable_label(true, &club.full_name);
        ui.add_enabled(false, egui::Button::new(format!("{} U19", club.short_name)));
        ui.add_enabled(false, egui::Button::new(format!("{} B", club.short_name)));
    });
    ui.add_space(5.0);
    locked_notice(ui, "Squad membership vectors are not yet mapped for FM27. The complete workspace is ready and will unlock after validation.");
    page_card(ui, "Squad Players", |ui| {
        egui::Grid::new("club_squad_players").num_columns(9).striped(true).spacing([12.0, 4.0]).show(ui, |ui| {
            for h in ["Player", "Position", "Age", "CA", "PA", "Condition", "Morale", "Squad Status", "Wage"] {
                ui.label(egui::RichText::new(h).small().strong());
            }
            ui.end_row();
            ui.label("No mapped squad rows");
            for _ in 0..8 { ui.label("—"); }
            ui.end_row();
        });
    });
    ui.add_space(6.0);
    ui.horizontal_wrapped(|ui| {
        for label in ["Open Selected", "Heal", "Max Condition", "Max Morale", "Remove Bans", "Freeze", "Unfreeze", "+1 Year Contract", "-1 Year Contract"] {
            ui.add_enabled(false, egui::Button::new(label));
        }
    });
}

fn show_club_vision(ui: &mut egui::Ui) {
    locked_notice(ui, "FMRTE-equivalent Club Culture record layout. Editing unlocks when FM27 club-vision records are mapped.");
    page_card(ui, "Club Culture", |ui| {
        egui::Grid::new("club_vision_table").num_columns(7).striped(true).spacing([14.0, 4.0]).show(ui, |ui| {
            for h in ["Type", "Source Type", "Importance", "Item Name", "For Competition", "Start Date", "End Date"] { ui.label(egui::RichText::new(h).small().strong()); }
            ui.end_row();
            ui.label("No mapped vision records"); for _ in 0..6 { ui.label("—"); } ui.end_row();
        });
    });
    ui.add_space(6.0);
    page_card(ui, "Options", |ui| {
        for label in ["Type", "Source Type", "Importance (0-10)", "Referenced Competition / Nation / Continent / Club", "Start Date", "End Date"] { locked_field(ui, label); }
    });
}

fn show_possible_signings(ui: &mut egui::Ui) {
    locked_notice(ui, "Players the club is interested in signing. FM27 interest-list records still need mapping.");
    page_card(ui, "Possible Signings", |ui| {
        egui::Grid::new("possible_signings").num_columns(6).striped(true).spacing([14.0, 4.0]).show(ui, |ui| {
            for h in ["Player", "Age", "Position", "Current Club", "Interest", "Priority"] { ui.label(egui::RichText::new(h).small().strong()); }
            ui.end_row();
            ui.label("No mapped interest records"); for _ in 0..5 { ui.label("—"); } ui.end_row();
        });
    });
}

fn show_player_clauses(ui: &mut egui::Ui) {
    locked_notice(ui, "FMRTE 27 clause types mirrored here; edits remain disabled until the FM27 clause collection is mapped.");
    page_card(ui, "Player Clauses", |ui| {
        egui::Grid::new("player_clauses").num_columns(4).striped(true).spacing([14.0, 4.0]).show(ui, |ui| {
            for h in ["Player", "Clause Type", "Club", "Value / Status"] { ui.label(egui::RichText::new(h).small().strong()); }
            ui.end_row();
            ui.label("No mapped clauses"); ui.label("—"); ui.label("—"); ui.label("—"); ui.end_row();
        });
        ui.add_space(5.0);
        ui.label(egui::RichText::new("Supported model").small().strong());
        for label in [
            "Sell On Clause — Percentage / Signed For",
            "Appearance Money — Type / Fee / Total so far / Total",
            "Player Buy Back — Value / Start Date / End Date",
            "Competition Bonus — Competition / End Date / Value",
            "Arrange Friendly — Valid Until",
        ] { ui.label(format!("• {label}")); }
    });
}

fn show_kits_colours(ui: &mut egui::Ui) {
    locked_notice(ui, "Kit records require their FM27 collection offsets. Layout covers home, away, third and goalkeeper records.");
    ui.horizontal(|ui| {
        for label in ["Home", "Away", "Third", "Goalkeeper"] { ui.add_enabled(false, egui::Button::new(label)); }
    });
    ui.add_space(5.0);
    ui.columns(2, |cols| {
        page_card(&mut cols[0], "Kit Record", |ui| {
            for label in ["Kit Type", "Year", "Style", "Shirt Style", "Shorts Style", "Socks Style", "Allow Licensed Kit"] { locked_field(ui, label); }
        });
        page_card(&mut cols[1], "Colours", |ui| {
            for label in ["Background Colour", "Foreground Colour", "Trim Colour", "Number Colour", "Name Colour"] { locked_field(ui, label); }
        });
    });
}

fn show_tactics(ui: &mut egui::Ui) {
    locked_notice(ui, "FMRTE-style tactic comparison is read-only against the game. Element will keep formation experiments local until tactic structures are validated.");
    ui.horizontal(|ui| {
        ui.add_enabled(false, egui::Button::new("Current / Last Match"));
        ui.add_enabled(false, egui::Button::new("Suggested"));
        ui.add_enabled(false, egui::Button::new("Formation"));
        ui.add_enabled(false, egui::Button::new("Edit Positions"));
    });
    ui.add_space(6.0);
    ui.columns(3, |cols| {
        page_card(&mut cols[0], "In Possession", |ui| { locked_field(ui, "Formation pitch + player selection scores (0-100)"); });
        page_card(&mut cols[1], "Out of Possession", |ui| { locked_field(ui, "Formation pitch + role/selection scores (0-100)"); });
        page_card(&mut cols[2], "Starting XI / Substitutes", |ui| {
            locked_field(ui, "Team Rating"); locked_field(ui, "Starting XI"); locked_field(ui, "Bench places");
        });
    });
}

fn show_staff(ui: &mut egui::Ui) {
    locked_notice(ui, "Club staff membership and contract collections still need FM27 mapping.");
    page_card(ui, "Club Staff", |ui| {
        egui::Grid::new("club_staff").num_columns(6).striped(true).spacing([14.0, 4.0]).show(ui, |ui| {
            for h in ["Name", "Job", "Age", "CA", "PA", "Contract Until"] { ui.label(egui::RichText::new(h).small().strong()); }
            ui.end_row(); ui.label("No mapped staff rows"); for _ in 0..5 { ui.label("—"); } ui.end_row();
        });
    });
    ui.add_space(6.0);
    ui.horizontal_wrapped(|ui| {
        for label in ["Open Selected", "Apply Preset", "Freeze", "Unfreeze", "+1 Year Contract", "-1 Year Contract"] { ui.add_enabled(false, egui::Button::new(label)); }
    });
}

fn show_affiliations(ui: &mut egui::Ui) {
    locked_notice(ui, "Affiliate vectors and benefit flags are not mapped yet; all fields from the FMRTE workflow are represented.");
    ui.columns(2, |cols| {
        page_card(&mut cols[0], "Affiliations", |ui| {
            egui::Grid::new("affiliations_table").num_columns(2).striped(true).spacing([14.0, 4.0]).show(ui, |ui| {
                ui.label(egui::RichText::new("Team").small().strong()); ui.label(egui::RichText::new("Type").small().strong()); ui.end_row();
                ui.label("No mapped affiliations"); ui.label("—"); ui.end_row();
            });
        });
        page_card(&mut cols[1], "Information", |ui| {
            for label in ["Parent Club", "Feeder Club", "Start Date", "End Date", "Affiliation Type", "Annual Fee", "% Chance Of Friendly", "Maximum No. Players Loaned", "% Loan Wage Paid By Parent Club"] { locked_field(ui, label); }
        });
    });
    ui.add_space(6.0);
    page_card(ui, "Friendship Benefits", |ui| {
        ui.columns(2, |cols| {
            for label in ["Players Move Freely", "First Option To Buy", "Youth Players Training", "Same Board", "Help With Facilities", "Marketing Relations", "Cannot Play In Same Division", "Loan Players From Sub Team", "Uses Same Kit"] { cols[0].add_enabled(false, egui::Checkbox::new(&mut false, label)); }
            for label in ["Players Go On Loan", "Player Friendlies", "Permanent Deal", "Financial Help", "Renewable", "Scouting Knowledge Shared", "Uses All Parent Club Facilities", "Uses Sub Team Training"] { cols[1].add_enabled(false, egui::Checkbox::new(&mut false, label)); }
        });
    });
}

fn show_regional_divisions(ui: &mut egui::Ui) {
    locked_notice(ui, "Regional-division records can be listed, edited, added and removed once the FM27 vector is mapped.");
    page_card(ui, "Regional Divisions", |ui| {
        egui::Grid::new("regional_divisions").num_columns(3).striped(true).spacing([14.0, 4.0]).show(ui, |ui| {
            for h in ["Competition", "Level", "Year"] { ui.label(egui::RichText::new(h).small().strong()); } ui.end_row();
            ui.label("No mapped regional division records"); ui.label("—"); ui.label("—"); ui.end_row();
        });
        ui.add_space(4.0);
        ui.add_enabled(false, egui::Button::new("+ Add Division")); ui.add_enabled(false, egui::Button::new("− Remove Selected"));
    });
}

fn show_ownership(ui: &mut egui::Ui) {
    locked_notice(ui, "Ownership/election record not mapped for FM27 yet.");
    ui.columns(2, |cols| {
        page_card(&mut cols[0], "Ownership", |ui| {
            for label in ["Election Date", "Max Length Of Term", "Max Number Of Terms", "Current Number Of Terms", "Minimum Turnout", "Maximum Turnout"] { locked_field(ui, label); }
        });
        page_card(&mut cols[1], "Promises", |ui| {
            for label in ["Promise New Manager", "Promise New Players", "Promise More Money", "Promise Promotion", "Promise New Stadium"] { ui.add_enabled(false, egui::Checkbox::new(&mut false, label)); }
        });
    });
}

fn show_relationships(ui: &mut egui::Ui) {
    locked_notice(ui, "Club relationship collection is not yet mapped.");
    page_card(ui, "Relationships", |ui| {
        egui::Grid::new("club_relationships").num_columns(5).striped(true).spacing([14.0, 4.0]).show(ui, |ui| {
            for h in ["Type", "Person / Club / Nation", "Value", "Reason", "Permanent"] { ui.label(egui::RichText::new(h).small().strong()); } ui.end_row();
            ui.label("No mapped relationships"); for _ in 0..4 { ui.label("—"); } ui.end_row();
        });
        ui.add_space(4.0); ui.add_enabled(false, egui::Button::new("+ Add")); ui.add_enabled(false, egui::Button::new("− Remove"));
    });
}

fn show_supporters(
    schemas: &'static crate::fields::VersionedSchemas,
    ui: &mut egui::Ui,
    club: &mut ClubView,
    edits: &mut Vec<FieldEdit>,
) {
    ui.label(egui::RichText::new("LIVE FM27 MAPPING").small().strong().color(egui::Color32::from_rgb(61, 214, 140)));
    ui.columns(2, |cols| {
        page_card(&mut cols[0], "Supporters Profile Distribution", |ui| {
            for (label, key) in [
                ("Hardcore %", "c_sup_hardcore"),
                ("Core %", "c_sup_core"),
                ("Family %", "c_sup_family"),
                ("Fair Weather %", "c_sup_fair_weather"),
                ("Casual %", "c_sup_casual"),
                ("Corporate / Other %", "c_sup_other"),
            ] {
                let Some((container, offset)) = sub_location(schemas, key) else { continue };
                if let Some((buf, base)) = club.sub_record_mut(container) {
                    u8_drag_0_100(ui, label, buf, offset, base, edits);
                }
            }
            let total: u16 = ["c_sup_hardcore", "c_sup_core", "c_sup_family", "c_sup_fair_weather", "c_sup_casual", "c_sup_other"]
                .iter()
                .filter_map(|key| schemas.field(key).and_then(|f| fields::read_field_u8(club, &club.raw, &f)))
                .map(|v| v as u16)
                .sum();
            if total == 100 {
                ui.colored_label(egui::Color32::from_rgb(61, 214, 140), format!("Total: {total}% ✓"));
            } else {
                ui.colored_label(egui::Color32::from_rgb(255, 104, 104), format!("Total: {total}% — should equal 100%"));
            }
        });
        page_card(&mut cols[1], "Supporter Profile", |ui| {
            for (label, key) in [
                ("Loyalty", "c_sup_loyalty"),
                ("Passion", "c_sup_passion"),
                ("Patience", "c_sup_patience"),
                ("Affluence", "c_sup_affluence"),
                ("Temperament", "c_sup_temperament"),
                ("Expectations", "c_sup_expectations"),
            ] {
                let Some((container, offset)) = sub_location(schemas, key) else { continue };
                if let Some((buf, base)) = club.sub_record_mut(container) {
                    u8_drag_1_20(ui, label, buf, offset, base, edits);
                }
            }
        });
    });
}

fn show_stadium_move(ui: &mut egui::Ui) {
    locked_notice(ui, "This page appears when a planned stadium move record exists. FM27 move-record offsets are not mapped yet.");
    page_card(ui, "Stadium Move", |ui| {
        for label in ["New / Alternative Stadium", "Move Type", "Start Date", "Move Date", "End Date", "Expected Attendance", "Likelihood / Probability", "Reason / Status"] { locked_field(ui, label); }
    });
}

fn show_tactical_effectiveness(ui: &mut egui::Ui) {
    locked_notice(ui, "Element FM27 extra: dedicated dashboard for FM27 Tactical Effectiveness. Values remain read-only until the new FM27 structures are mapped.");
    page_card(ui, "Tactical Effectiveness", |ui| {
        for label in ["Player Ability", "Next Match Information", "Player Buy-In", "Tactical Understanding", "Overall Tactical Effectiveness", "Tactical Complexity"] {
            ui.horizontal(|ui| {
                ui.add_sized([150.0, 18.0], egui::Label::new(label));
                ui.add(egui::ProgressBar::new(0.0).desired_width((ui.available_width() - 40.0).max(120.0)).text("Mapping required"));
            });
        }
    });
    ui.add_space(6.0);
    page_card(ui, "Training / Match Preparation", |ui| {
        for label in ["Next Match Focus", "Opposition Preparation", "Team Focus", "Individual Training Load", "Tactical Complexity Load"] { locked_field(ui, label); }
    });
}

fn show_registration_eligibility(ui: &mut egui::Ui) {
    locked_notice(ui, "Element FM27 extra: one place for registration and eligibility problems across the whole squad.");
    page_card(ui, "Registration & Eligibility", |ui| {
        egui::Grid::new("registration_eligibility").num_columns(7).striped(true).spacing([12.0, 4.0]).show(ui, |ui| {
            for h in ["Player", "Competition", "Registered", "Home-Grown", "Work Permit", "Squad No.", "Issue"] { ui.label(egui::RichText::new(h).small().strong()); } ui.end_row();
            ui.label("Squad membership/registration mapping required"); for _ in 0..6 { ui.label("—"); } ui.end_row();
        });
        ui.add_space(5.0);
        ui.horizontal_wrapped(|ui| {
            for label in ["Register Selected", "Unregister", "Set Squad Number", "Grant Work Permit", "Mark Trained At Club", "Mark Trained In Nation"] { ui.add_enabled(false, egui::Button::new(label)); }
        });
    });
}

fn show_recruitment_fit(ui: &mut egui::Ui) {
    locked_notice(ui, "Element FM27 extra: recruitment dashboard designed around FM27 Tactical Effectiveness and registration constraints.");
    page_card(ui, "Recruitment Fit", |ui| {
        egui::Grid::new("recruitment_fit").num_columns(9).striped(true).spacing([12.0, 4.0]).show(ui, |ui| {
            for h in ["Player", "CA", "PA", "Tactical Fit", "Buy-In Risk", "Transfer Cost", "Wage", "Registration Risk", "Injury Risk"] { ui.label(egui::RichText::new(h).small().strong()); } ui.end_row();
            ui.label("Recruitment-fit sources not mapped yet"); for _ in 0..8 { ui.label("—"); } ui.end_row();
        });
    });
}

fn u8_drag_0_100(
    ui: &mut egui::Ui,
    label: &str,
    raw: &mut [u8],
    offset: usize,
    base_addr: u64,
    edits: &mut Vec<FieldEdit>,
) {
    if offset >= raw.len() { return; }
    let old = raw[offset];
    let mut val = old as i32;
    let enabled = navigation::editing_enabled(ui);
    let mut changed = false;
    ui.horizontal(|ui| {
        ui.add_sized([150.0, 18.0], egui::Label::new(label));
        changed = ui.add_enabled_ui(enabled, |ui| {
            ui.add_sized([40.0, 18.0], egui::DragValue::new(&mut val).update_while_editing(false).range(0..=100).suffix("%").speed(0.2)).changed()
        }).inner;
    });
    if enabled && changed {
        let new_val = val.clamp(0, 100) as u8;
        if new_val != old {
            raw[offset] = new_val;
            edits.push(FieldEdit {
                addr: base_addr + offset as u64,
                old_raw: vec![old],
                new_raw: vec![new_val],
                description: format!("{label}: {old} → {new_val}"),
            });
        }
    }
}

'@
$text = $text.Substring(0, $insertAt) + $pages + $text.Substring($insertAt)
[IO.File]::WriteAllText($cp, $text, [Text.UTF8Encoding]::new($false))

# -----------------------------------------------------------------------------
# Activate every club page in the contextual left rail.
# -----------------------------------------------------------------------------
$a = 'src/app.rs'
Replace-Required $a '                    ui.add_enabled(false, egui::Button::new("♟  Squads"));' '                    if nav(ui, self.club_tab == club_panel::ClubTab::Squads, "♟  Squads") { self.club_tab = club_panel::ClubTab::Squads; }'
Replace-Required $a '                    ui.add_enabled(false, egui::Button::new("◎  Club Vision"));' '                    if nav(ui, self.club_tab == club_panel::ClubTab::ClubVision, "◎  Club Vision") { self.club_tab = club_panel::ClubTab::ClubVision; }'
Replace-Required $a '                    ui.add_enabled(false, egui::Button::new("⌕  Possible Signings"));' '                    if nav(ui, self.club_tab == club_panel::ClubTab::PossibleSignings, "⌕  Possible Signings") { self.club_tab = club_panel::ClubTab::PossibleSignings; }'
Replace-Required $a '                    ui.add_enabled(false, egui::Button::new("§  Player Clauses"));' '                    if nav(ui, self.club_tab == club_panel::ClubTab::PlayerClauses, "§  Player Clauses") { self.club_tab = club_panel::ClubTab::PlayerClauses; }'
Replace-Required $a '                    ui.add_enabled(false, egui::Button::new("◈  Kits and Colours"));' '                    if nav(ui, self.club_tab == club_panel::ClubTab::KitsColours, "◈  Kits and Colours") { self.club_tab = club_panel::ClubTab::KitsColours; }'
Replace-Required $a '                    ui.add_enabled(false, egui::Button::new("⌗  Tactics"));' '                    if nav(ui, self.club_tab == club_panel::ClubTab::Tactics, "⌗  Tactics") { self.club_tab = club_panel::ClubTab::Tactics; }'
Replace-Required $a '                    ui.add_enabled(false, egui::Button::new("♟  Staff"));' '                    if nav(ui, self.club_tab == club_panel::ClubTab::Staff, "♟  Staff") { self.club_tab = club_panel::ClubTab::Staff; }'
Replace-Required $a '                    ui.add_enabled(false, egui::Button::new("◇  Affiliations"));' '                    if nav(ui, self.club_tab == club_panel::ClubTab::Affiliations, "◇  Affiliations") { self.club_tab = club_panel::ClubTab::Affiliations; }'
Replace-Required $a '                    ui.add_enabled(false, egui::Button::new("▦  Regional Divisions"));' '                    if nav(ui, self.club_tab == club_panel::ClubTab::RegionalDivisions, "▦  Regional Divisions") { self.club_tab = club_panel::ClubTab::RegionalDivisions; }'
Replace-Required $a '                    ui.add_enabled(false, egui::Button::new("◆  Ownership"));' '                    if nav(ui, self.club_tab == club_panel::ClubTab::Ownership, "◆  Ownership") { self.club_tab = club_panel::ClubTab::Ownership; }'
Replace-Required $a '                    ui.add_enabled(false, egui::Button::new("♧  Relationships"));' '                    if nav(ui, self.club_tab == club_panel::ClubTab::Relationships, "♧  Relationships") { self.club_tab = club_panel::ClubTab::Relationships; }'
Replace-Required $a '                    ui.add_enabled(false, egui::Button::new("♥  Supporters"));' '                    if nav(ui, self.club_tab == club_panel::ClubTab::Supporters, "♥  Supporters") { self.club_tab = club_panel::ClubTab::Supporters; }'

# Insert FMRTE Stadium Move plus FM27-native Element pages before existing Facilities shortcut.
Replace-Required $a @'
                    if nav(ui, self.club_tab == club_panel::ClubTab::Supporters, "♥  Supporters") { self.club_tab = club_panel::ClubTab::Supporters; }
                    if nav(ui, self.club_tab == club_panel::ClubTab::Facilities, "⌂  Facilities") { self.club_tab = club_panel::ClubTab::Facilities; }
'@ @'
                    if nav(ui, self.club_tab == club_panel::ClubTab::Supporters, "♥  Supporters") { self.club_tab = club_panel::ClubTab::Supporters; }
                    if nav(ui, self.club_tab == club_panel::ClubTab::StadiumMove, "⇥  Stadium Move") { self.club_tab = club_panel::ClubTab::StadiumMove; }
                    ui.add_space(4.0);
                    ui.label(egui::RichText::new("FM27 / ELEMENT").size(8.5).strong().color(egui::Color32::from_rgb(112,130,158)));
                    if nav(ui, self.club_tab == club_panel::ClubTab::TacticalEffectiveness, "◫  Tactical Effectiveness") { self.club_tab = club_panel::ClubTab::TacticalEffectiveness; }
                    if nav(ui, self.club_tab == club_panel::ClubTab::RegistrationEligibility, "✓  Registration & Eligibility") { self.club_tab = club_panel::ClubTab::RegistrationEligibility; }
                    if nav(ui, self.club_tab == club_panel::ClubTab::RecruitmentFit, "⌕  Recruitment Fit") { self.club_tab = club_panel::ClubTab::RecruitmentFit; }
                    if nav(ui, self.club_tab == club_panel::ClubTab::Facilities, "⌂  Facilities") { self.club_tab = club_panel::ClubTab::Facilities; }
'@

Write-Host 'Element v1.8 full FMRTE-inspired club editor + FM27-native workspaces applied successfully.'
