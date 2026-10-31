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

$p = 'src/ui/player_panel.rs'
$pp = Join-Path $SourceRoot $p

# -----------------------------------------------------------------------------
# Full FMRTE-inspired player navigation model + Element/FM27 extras.
# Existing proven pages remain intact; unsupported record collections are visible
# but locked until their FM27 memory structures are validated.
# -----------------------------------------------------------------------------
Replace-Required $p @'
#[derive(PartialEq)]
pub enum PlayerTab {
    Overview,
    PositionsTraits,
    Contract,
    TransferLab,
}
'@ @'
#[derive(PartialEq)]
pub enum PlayerTab {
    Overview,
    Stats,
    Comparison,
    Contract,
    CareerPlans,
    SwapPlayer,
    CloneCenter,
    TransferLab,
    SwapNationalCallUp,
    FutureTransfer,
    Injury,
    WorkPermit,
    Promises,
    Unavailability,
    TransferProposals,
    RetireDate,
    Positions,
    PreferredMoves,
    Relationships,
    Languages,
    ScoutInformation,
    RoleRatings,
    Development,
    RegistrationEligibility,
    International,
    MatchReadiness,
    TacticalFit,
    PlayerCoach,
    PositionsTraits,
}
'@

Replace-Required $p @'
        PlayerTab::PositionsTraits => show_positions_traits(schemas, ui, player, addr, &mut edits),
        PlayerTab::Contract => show_contract(schemas, ui, player, &mut edits),
        PlayerTab::TransferLab => show_transfer_lab(schemas, ui, player, &mut edits),
'@ @'
        PlayerTab::Stats => show_player_stats(ui, player, wage_period),
        PlayerTab::Comparison => show_locked_player_page(ui, "Comparison", "Compare two players side-by-side with attributes, positions, role highlights and contract context.", &["Compare With", "Highlight Role / Duty", "Attribute Differences", "Position Familiarity"]),
        PlayerTab::Contract => show_contract(schemas, ui, player, &mut edits),
        PlayerTab::CareerPlans => show_locked_player_page(ui, "Career Plans", "Long-term future jobs, preferred clubs/competitions and career conditions require the FM27 career-plan collection.", &["Plan Type", "Club / Nation / Competition", "Job / Role", "Start / End Conditions"]),
        PlayerTab::SwapPlayer => show_locked_player_page(ui, "Swap Player", "Atomic player swaps will unlock only after both clubs' squad, contract and registration chains pass live validation.", &["Swap With", "Source Club", "Destination Club", "Contracts", "Registrations"]),
        PlayerTab::CloneCenter => show_locked_player_page(ui, "Clone Center", "Clone Center will copy selected player data through verified fields only; identity/contract linking will never be guessed.", &["Clone Attributes", "Clone Personality", "Clone Positions", "Clone Traits", "Clone Appearance", "Clone Contract (unsafe until mapped)"]),
        PlayerTab::TransferLab => show_transfer_lab(schemas, ui, player, &mut edits),
        PlayerTab::SwapNationalCallUp => show_locked_player_page(ui, "Swap National Call Up", "National-squad membership records are not yet mapped for this FM27 build.", &["National Team", "Replace Player", "Replacement Player", "Competition / Squad"]),
        PlayerTab::FutureTransfer => show_locked_player_page(ui, "Future Transfer", "Existing/agreed future-transfer records need their FM27 linked transfer and contract structures before editing can be enabled.", &["Destination Club", "Transfer Fee", "Move Date", "Contract Length", "Wage", "Bonuses / Clauses"]),
        PlayerTab::Injury => show_locked_player_page(ui, "Injury", "Injury collection mapping is still required. Once validated this page will support type, severity and recovery dates.", &["Injury Type", "Start Date", "Expected Recovery", "Treatment / Rehab", "Recurring"]),
        PlayerTab::WorkPermit => show_locked_player_page(ui, "Work Permit", "FMRTE-style add/edit/remove work permits. The FM27 permit record collection is not yet validated.", &["Status", "Nation / Competition", "Start Date", "End Date", "Appeal / Exemption"]),
        PlayerTab::Promises => show_locked_player_page(ui, "Promises", "Promise records will support add, edit and remove when the FM27 promise collection is validated.", &["Promise Type", "Manager", "Competition / Person", "Playing Time / Value", "Made On", "Deadline"]),
        PlayerTab::Unavailability => show_locked_player_page(ui, "Unavailability", "Bans, suspensions, holidays and other availability records require the FM27 unavailability collection.", &["Reason", "Competition", "Start Date", "End Date", "Matches Remaining"]),
        PlayerTab::TransferProposals => show_locked_player_page(ui, "Transfer Proposals", "Existing transfer offers will be listed and editable after proposal records are mapped.", &["Interested Club", "Type", "Fee", "Clauses", "Status", "Deadline"]),
        PlayerTab::RetireDate => show_locked_player_page(ui, "Retire Date", "Scheduled retirement is conditional in Football Manager and needs a validated FM27 retirement record.", &["Retirement Date", "Retire From International Football", "Retire After Current Club"]),
        PlayerTab::Positions => show_positions_only(schemas, ui, player, addr, &mut edits),
        PlayerTab::PreferredMoves => show_preferred_moves_only(schemas, ui, player, addr, &mut edits),
        PlayerTab::Relationships => show_locked_player_page(ui, "Relationships", "People, club and nation relationship vectors are not yet mapped for FM27.", &["Person / Club / Nation", "Relationship Type", "Level", "Start / End Date", "Second Nationality"]),
        PlayerTab::Languages => show_locked_player_page(ui, "Languages", "Language entries and proficiency are not yet mapped for FM27.", &["Language", "Speaking", "Understanding", "Fluency"]),
        PlayerTab::ScoutInformation => show_locked_player_page(ui, "Scout Information", "General and positional scout ratings will be exposed when the scouting report structures are validated.", &["Current Ability", "Potential Ability", "Role Ratings", "Pros / Cons", "Recommendation", "Knowledge"]),
        PlayerTab::RoleRatings => show_locked_player_page(ui, "Role Ratings", "Element/FM27 extra: role suitability using the game's role model. The UI is ready for verified role-rating inputs.", &["Best Role", "Current Rating", "Potential Rating", "Key Attributes", "Preferred Attributes", "Weak Attributes"]),
        PlayerTab::Development => show_player_development(ui, player),
        PlayerTab::RegistrationEligibility => show_player_registration(ui, player),
        PlayerTab::International => show_player_international(ui, player),
        PlayerTab::MatchReadiness => show_locked_player_page(ui, "Match Readiness", "Fitness, sharpness, fatigue, jadedness, morale, injury and ban states will become live once the FM27 condition records are validated.", &["Condition", "Match Sharpness", "Fatigue / Jadedness", "Morale", "Injury", "Suspension / Ban"]),
        PlayerTab::TacticalFit => show_locked_player_page(ui, "Tactical Fit", "FM27 Tactical Effectiveness links recruitment, training and tactics. This player view will combine role fit, ability, buy-in and tactical understanding.", &["Role Fit", "Player Ability", "Player Buy-In", "Tactical Understanding", "Next Match Fit", "Overall Tactical Fit"]),
        PlayerTab::PlayerCoach => show_locked_player_page(ui, "Player-Coach Details", "For player-coaches this page will expose staff attributes, job, coaching qualifications and staff contract data when the linked staff record is validated.", &["Staff Job", "Coaching Attributes", "Judging Ability / Potential", "Tactical Knowledge", "Qualifications", "Staff Contract"]),
        PlayerTab::PositionsTraits => show_positions_traits(schemas, ui, player, addr, &mut edits),
'@

# Better terminology: the two 1-20 values describe ability with each foot, not
# a generic "footedness" boolean and not shot power.
Replace-Required $p '("Footedness", Category::Footedness),' '("Foot Ability", Category::Footedness),'

# -----------------------------------------------------------------------------
# Insert player workspaces before Transfer Lab. Mapped values are shown live;
# unknown linked collections are explicit and never fabricated.
# -----------------------------------------------------------------------------
$text = [IO.File]::ReadAllText($pp)
$insertAt = $text.IndexOf('// Transfer Lab — Element FM27')
if ($insertAt -lt 0) { throw 'v1.9: player workspace insertion boundary not found' }
$insertAt = $text.LastIndexOf('// ---------------------------------------------------------------------------', $insertAt)
if ($insertAt -lt 0) { throw 'v1.9: player section header boundary not found' }
$pages = @'
fn player_page_card(ui: &mut egui::Ui, title: &str, add: impl FnOnce(&mut egui::Ui)) {
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

fn show_locked_player_page(ui: &mut egui::Ui, title: &str, note: &str, fields: &[&str]) {
    ui.label(egui::RichText::new(title).size(15.0).strong());
    ui.label(egui::RichText::new(note).small().color(egui::Color32::from_rgb(255, 184, 77)));
    ui.add_space(6.0);
    player_page_card(ui, title, |ui| {
        for label in fields {
            field_widget::stub_field(ui, label, "Not available in this FM27 memory profile yet");
        }
    });
}

fn show_player_stats(ui: &mut egui::Ui, player: &PlayerRecord, wage_period: WagePeriod) {
    ui.label(egui::RichText::new("Stats").size(15.0).strong());
    ui.label(egui::RichText::new("Read-only season/international snapshot. Full competition-by-competition statistics and league ranks require the FM27 statistics collections.").small().color(egui::Color32::from_rgb(139, 157, 188)));
    ui.add_space(6.0);
    ui.columns(2, |cols| {
        player_page_card(&mut cols[0], "Career / International", |ui| {
            if let (Some(caps), Some(goals)) = (player.field_int("p_intl_caps"), player.field_int("p_intl_goals")) {
                field_widget::info_label(ui, "International Caps / Goals", format!("{caps} / {goals}"));
            }
            if let (Some(caps), Some(goals)) = (player.field_int("p_u21_caps"), player.field_int("p_u21_goals")) {
                field_widget::info_label(ui, "U21 Caps / Goals", format!("{caps} / {goals}"));
            }
            if let Some(v) = player.field_u32("p_value") { field_widget::info_label(ui, "Market Value", v); }
            if let Some(v) = player.field_u16("p_current_rep") { field_widget::info_label(ui, "Current Reputation", v); }
        });
        player_page_card(&mut cols[1], "Contract Snapshot", |ui| {
            if let Some(v) = player.field_u32("p_contract_wage") { field_widget::info_label(ui, "Wage", format_wage(v, wage_period)); }
            if let Some(v) = player.field_u32("p_asking_price") { field_widget::info_label(ui, "Asking Price", if v == u32::MAX { "—".into() } else { v.to_string() }); }
            field_widget::stub_field(ui, "Season Apps / Goals", "Statistics collection not mapped yet");
            field_widget::stub_field(ui, "League Rank / Percentile", "Statistics collection not mapped yet");
        });
    });
}

fn show_positions_only(
    schemas: &'static crate::fields::VersionedSchemas,
    ui: &mut egui::Ui,
    player: &mut PlayerRecord,
    addr: u64,
    edits: &mut Vec<FieldEdit>,
) {
    ui.label(egui::RichText::new("Positions").size(15.0).strong());
    ui.label(egui::RichText::new("Edit positional familiarity live (1-20).").small().color(egui::Color32::from_rgb(139, 157, 188)));
    ui.add_space(6.0);
    show_positions_formation(schemas, ui, player, addr, edits);
}

fn show_preferred_moves_only(
    schemas: &'static crate::fields::VersionedSchemas,
    ui: &mut egui::Ui,
    player: &mut PlayerRecord,
    addr: u64,
    edits: &mut Vec<FieldEdit>,
) {
    ui.label(egui::RichText::new("Preferred Moves").size(15.0).strong());
    ui.label(egui::RichText::new("Add/remove mapped player traits live.").small().color(egui::Color32::from_rgb(139, 157, 188)));
    ui.add_space(6.0);
    show_traits_checkboxes(schemas, ui, player, addr, edits);
}

fn show_player_development(ui: &mut egui::Ui, player: &PlayerRecord) {
    ui.label(egui::RichText::new("Development & Growth").size(15.0).strong());
    ui.label(egui::RichText::new("Element/FM27 extra: quick development view using currently verified player values.").small().color(egui::Color32::from_rgb(139, 157, 188)));
    ui.add_space(6.0);
    ui.columns(2, |cols| {
        player_page_card(&mut cols[0], "Ability", |ui| {
            if let Some(v) = player.field_u8("p_ca") { field_widget::info_label(ui, "Current Ability", v); }
            if let Some(v) = player.field_u8("p_pa") { field_widget::info_label(ui, "Potential Ability", v); }
            if let Some(v) = player.field_u8("natural_fitness") { field_widget::info_label(ui, "Natural Fitness", v); }
            if let Some(v) = player.field_u8("p_professionalism") { field_widget::info_label(ui, "Professionalism", v); }
            if let Some(v) = player.field_u8("p_ambition") { field_widget::info_label(ui, "Ambition", v); }
            if let Some(v) = player.field_u8("p_determination") { field_widget::info_label(ui, "Determination", v); }
        });
        player_page_card(&mut cols[1], "Development Tools", |ui| {
            field_widget::stub_field(ui, "Training Progress", "Training history collection not mapped yet");
            field_widget::stub_field(ui, "Attribute Change History", "Development history collection not mapped yet");
            field_widget::stub_field(ui, "Expected Peak", "Requires verified development model inputs");
            field_widget::stub_field(ui, "Make Wonderkid Preset", "Preset engine planned");
        });
    });
}

fn show_player_registration(ui: &mut egui::Ui, player: &PlayerRecord) {
    ui.label(egui::RichText::new("Registration & Eligibility").size(15.0).strong());
    ui.add_space(6.0);
    player_page_card(ui, "Eligibility Snapshot", |ui| {
        field_widget::info_label(ui, "Nationality", player.nationality.as_deref().unwrap_or("Unknown"));
        if let Some(v) = player.field_u8("p_squad_number") { field_widget::info_label(ui, "Squad Number", if v == 255 { "—".into() } else { v.to_string() }); }
        if let Some(v) = player.field_u8("p_squad_status") { field_widget::info_label(ui, "Squad Status Code", v); }
        field_widget::stub_field(ui, "Competition Registration", "Registration vectors not mapped yet");
        field_widget::stub_field(ui, "Home-Grown at Club / Nation", "Eligibility records not mapped yet");
        field_widget::stub_field(ui, "Work Permit", "Permit record not mapped yet");
    });
}

fn show_player_international(ui: &mut egui::Ui, player: &PlayerRecord) {
    ui.label(egui::RichText::new("International").size(15.0).strong());
    ui.add_space(6.0);
    player_page_card(ui, "International Status", |ui| {
        field_widget::info_label(ui, "Nationality", player.nationality.as_deref().unwrap_or("Unknown"));
        if let (Some(caps), Some(goals)) = (player.field_int("p_intl_caps"), player.field_int("p_intl_goals")) {
            field_widget::info_label(ui, "Senior Caps / Goals", format!("{caps} / {goals}"));
        }
        if let (Some(caps), Some(goals)) = (player.field_int("p_u21_caps"), player.field_int("p_u21_goals")) {
            field_widget::info_label(ui, "U21 Caps / Goals", format!("{caps} / {goals}"));
        }
        field_widget::stub_field(ui, "Declared Nation", "International eligibility record not mapped yet");
        field_widget::stub_field(ui, "National Squad", "National squad membership not mapped yet");
        field_widget::stub_field(ui, "International Retirement", "Retirement record not mapped yet");
    });
}

'@
$text = $text.Substring(0, $insertAt) + $pages + $text.Substring($insertAt)
[IO.File]::WriteAllText($pp, $text, [Text.UTF8Encoding]::new($false))

# -----------------------------------------------------------------------------
# Player contextual rail: every FMRTE 27 player page navigable + Element extras.
# -----------------------------------------------------------------------------
$a = 'src/app.rs'
$ap = Join-Path $SourceRoot $a
$app = [IO.File]::ReadAllText($ap)
$playerStart = $app.IndexOf('                    if nav(ui, self.player_tab == player_panel::PlayerTab::Overview, "▣  Information")')
$playerEndMarker = '                    ui.add_space(6.0); ui.separator(); ui.add_space(4.0);'
$playerEnd = $app.IndexOf($playerEndMarker, $playerStart)
if ($playerStart -lt 0 -or $playerEnd -lt 0) { throw 'v1.9: player sidebar boundaries not found' }
$newPlayerNav = @'
                    if nav(ui, self.player_tab == player_panel::PlayerTab::Overview, "▣  Information") { self.player_tab = player_panel::PlayerTab::Overview; }
                    if nav(ui, self.player_tab == player_panel::PlayerTab::Stats, "▥  Stats") { self.player_tab = player_panel::PlayerTab::Stats; }
                    if nav(ui, self.player_tab == player_panel::PlayerTab::Comparison, "⇄  Comparison") { self.player_tab = player_panel::PlayerTab::Comparison; }
                    if nav(ui, self.player_tab == player_panel::PlayerTab::Contract, "▤  Contract") { self.player_tab = player_panel::PlayerTab::Contract; }
                    if nav(ui, self.player_tab == player_panel::PlayerTab::CareerPlans, "◎  Career Plans") { self.player_tab = player_panel::PlayerTab::CareerPlans; }
                    if nav(ui, self.player_tab == player_panel::PlayerTab::SwapPlayer, "⇄  Swap Player") { self.player_tab = player_panel::PlayerTab::SwapPlayer; }
                    if nav(ui, self.player_tab == player_panel::PlayerTab::CloneCenter, "⧉  Clone Center") { self.player_tab = player_panel::PlayerTab::CloneCenter; }
                    if nav(ui, self.player_tab == player_panel::PlayerTab::TransferLab, "→  Move to Club") { self.player_tab = player_panel::PlayerTab::TransferLab; }
                    ui.add_enabled(false, egui::Button::new("⚡  Force Transfer — safety lock"));
                    if nav(ui, self.player_tab == player_panel::PlayerTab::SwapNationalCallUp, "⇄  Swap National Call Up") { self.player_tab = player_panel::PlayerTab::SwapNationalCallUp; }
                    if nav(ui, self.player_tab == player_panel::PlayerTab::FutureTransfer, "◷  Future Transfer") { self.player_tab = player_panel::PlayerTab::FutureTransfer; }
                    if nav(ui, self.player_tab == player_panel::PlayerTab::Injury, "✚  Injury") { self.player_tab = player_panel::PlayerTab::Injury; }
                    if nav(ui, self.player_tab == player_panel::PlayerTab::WorkPermit, "▧  Work Permit") { self.player_tab = player_panel::PlayerTab::WorkPermit; }
                    if nav(ui, self.player_tab == player_panel::PlayerTab::Promises, "✓  Promises") { self.player_tab = player_panel::PlayerTab::Promises; }
                    if nav(ui, self.player_tab == player_panel::PlayerTab::Unavailability, "⊘  Unavailability") { self.player_tab = player_panel::PlayerTab::Unavailability; }
                    if nav(ui, self.player_tab == player_panel::PlayerTab::TransferProposals, "⇆  Transfer Proposals") { self.player_tab = player_panel::PlayerTab::TransferProposals; }
                    if nav(ui, self.player_tab == player_panel::PlayerTab::RetireDate, "◷  Retire Date") { self.player_tab = player_panel::PlayerTab::RetireDate; }
                    if nav(ui, self.player_tab == player_panel::PlayerTab::Positions, "⌖  Positions") { self.player_tab = player_panel::PlayerTab::Positions; }
                    if nav(ui, self.player_tab == player_panel::PlayerTab::PreferredMoves, "★  Preferred Moves") { self.player_tab = player_panel::PlayerTab::PreferredMoves; }
                    if nav(ui, self.player_tab == player_panel::PlayerTab::Relationships, "♟  Relationships") { self.player_tab = player_panel::PlayerTab::Relationships; }
                    if nav(ui, self.player_tab == player_panel::PlayerTab::Languages, "A  Languages") { self.player_tab = player_panel::PlayerTab::Languages; }
                    if nav(ui, self.player_tab == player_panel::PlayerTab::ScoutInformation, "⌕  Scout Information") { self.player_tab = player_panel::PlayerTab::ScoutInformation; }
                    ui.add_space(4.0);
                    ui.label(egui::RichText::new("FM27 / ELEMENT").size(8.5).strong().color(egui::Color32::from_rgb(112,130,158)));
                    if nav(ui, self.player_tab == player_panel::PlayerTab::RoleRatings, "◫  Role Ratings") { self.player_tab = player_panel::PlayerTab::RoleRatings; }
                    if nav(ui, self.player_tab == player_panel::PlayerTab::Development, "↗  Development & Growth") { self.player_tab = player_panel::PlayerTab::Development; }
                    if nav(ui, self.player_tab == player_panel::PlayerTab::RegistrationEligibility, "✓  Registration & Eligibility") { self.player_tab = player_panel::PlayerTab::RegistrationEligibility; }
                    if nav(ui, self.player_tab == player_panel::PlayerTab::International, "⚑  International") { self.player_tab = player_panel::PlayerTab::International; }
                    if nav(ui, self.player_tab == player_panel::PlayerTab::MatchReadiness, "♥  Match Readiness") { self.player_tab = player_panel::PlayerTab::MatchReadiness; }
                    if nav(ui, self.player_tab == player_panel::PlayerTab::TacticalFit, "⌗  Tactical Fit") { self.player_tab = player_panel::PlayerTab::TacticalFit; }
                    if nav(ui, self.player_tab == player_panel::PlayerTab::PlayerCoach, "♟  Player-Coach Details") { self.player_tab = player_panel::PlayerTab::PlayerCoach; }
'@
$app = $app.Substring(0, $playerStart) + $newPlayerNav + $app.Substring($playerEnd)
[IO.File]::WriteAllText($ap, $app, [Text.UTF8Encoding]::new($false))

# -----------------------------------------------------------------------------
# LOAD GAME becomes a one-shot Connect & Load All control. Once Ready, the
# button becomes a non-clickable live-session indicator so users are not asked
# to repeatedly reload the save. Auto-reconnect remains enabled by default.
# -----------------------------------------------------------------------------
Replace-Required $a @'
                        let load = egui::Button::new(egui::RichText::new("LOAD GAME").strong().color(egui::Color32::WHITE))
                            .fill(egui::Color32::from_rgb(230,0,126));
                        if ui.add(load).clicked() { attach_requested = true; }
'@ @'
                        match self.conn {
                            ConnState::Ready(_) => {
                                ui.add_enabled(false, egui::Button::new(egui::RichText::new("LIVE • LOADED").strong().color(egui::Color32::WHITE))
                                    .fill(egui::Color32::from_rgb(31,157,74)));
                            }
                            ConnState::WaitingForSave(_) => {
                                ui.add_enabled(false, egui::Button::new(egui::RichText::new("LOADING ALL…").strong().color(egui::Color32::WHITE))
                                    .fill(egui::Color32::from_rgb(201,162,39)));
                            }
                            ConnState::ReadOnly(_) => {
                                let reconnect = egui::Button::new(egui::RichText::new("RECONNECT").strong().color(egui::Color32::WHITE))
                                    .fill(egui::Color32::from_rgb(230,0,126));
                                if ui.add(reconnect).clicked() { attach_requested = true; }
                            }
                            ConnState::Disconnected => {
                                let load = egui::Button::new(egui::RichText::new("LOAD GAME • ALL").strong().color(egui::Color32::WHITE))
                                    .fill(egui::Color32::from_rgb(230,0,126));
                                if ui.add(load).clicked() { attach_requested = true; }
                            }
                        }
'@

# User-facing terminology: persistent connection, not repeated loading.
Replace-Required $a '                    ui.checkbox(&mut self.auto_connect,"Auto-connect");' '                    ui.checkbox(&mut self.auto_connect,"Auto-reconnect live session");'

Write-Host 'Element v1.9 full FMRTE-inspired player editor + persistent live-session UX applied successfully.'
