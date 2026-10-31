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

# Add real navigation destinations for the three priority club workspaces.
Replace-Required $c @'
#[derive(PartialEq)]
pub enum ClubTab {
    Overview,
    Facilities,
    Finance,
    Stadium,
}
'@ @'
#[derive(PartialEq)]
pub enum ClubTab {
    Overview,
    Facilities,
    Finance,
    TransferCenter,
    TacticalUnderstanding,
    Stadium,
}
'@

Replace-Required $c @'
    egui::ScrollArea::vertical().show(ui, |ui| match tab {
        ClubTab::Overview => show_overview(schemas, ui, club, &mut edits),
        ClubTab::Facilities => show_facilities(schemas, ui, club, &mut edits),
        ClubTab::Finance => show_finance(schemas, ui, club, &mut edits),
        ClubTab::Stadium => show_stadium(schemas, ui, club),
    });
'@ @'
    egui::ScrollArea::vertical().show(ui, |ui| match tab {
        ClubTab::Overview => show_overview(schemas, ui, club, &mut edits),
        ClubTab::Facilities => show_facilities(schemas, ui, club, &mut edits),
        ClubTab::Finance => show_finance(schemas, ui, club, &mut edits),
        ClubTab::TransferCenter => show_transfer_center(ui, club),
        ClubTab::TacticalUnderstanding => show_tactical_understanding(ui, club),
        ClubTab::Stadium => show_stadium(schemas, ui, club),
    });
'@

# Replace Finance with a denser FMRTE-style workspace. Only validated fields are editable.
$text = [IO.File]::ReadAllText($cp)
$financeStart = $text.IndexOf('fn show_finance(')
$stadiumStart = $text.IndexOf('fn show_stadium(', $financeStart)
if ($financeStart -lt 0 -or $stadiumStart -lt 0) { throw 'v1.7: finance/stadium boundaries not found' }
$newFinance = @'
fn show_finance(
    schemas: &'static crate::fields::VersionedSchemas,
    ui: &mut egui::Ui,
    club: &mut ClubView,
    edits: &mut Vec<FieldEdit>,
) {
    ui.spacing_mut().item_spacing = egui::vec2(7.0, 4.0);
    ui.horizontal(|ui| {
        ui.selectable_label(true, "Overview");
        ui.add_enabled(false, egui::Button::new("Sponsors and Other"));
        ui.add_enabled(false, egui::Button::new("Debt and Loans"));
        ui.add_enabled(false, egui::Button::new("Income Statement"));
    });
    ui.add_space(4.0);

    egui::Frame::group(ui.style())
        .fill(egui::Color32::from_rgb(26, 32, 48))
        .stroke(egui::Stroke::new(1.0, egui::Color32::from_rgb(42, 50, 69)))
        .rounding(egui::Rounding::same(4))
        .inner_margin(egui::Margin::symmetric(8, 6))
        .show(ui, |ui| {
            ui.strong("Finances");
            ui.separator();

            for key in ["c_balance", "c_transfer_budget", "c_wage_budget"] {
                let Some((container, offset)) = sub_location(schemas, key) else { continue };
                let Some(field) = schemas.field(key) else { continue };
                let label = match key {
                    "c_transfer_budget" => "Transfer Budget (Season)",
                    "c_wage_budget" => "Wage Budget",
                    _ => field.label,
                };
                if let Some((buf, base)) = club.sub_record_mut(container) {
                    u32_drag(ui, label, buf, offset, base, edits);
                }
            }

            field_widget::stub_field(ui, "Transfer Budget Remaining", "FM27 offset not validated yet");
            field_widget::stub_field(ui, "% of transfer revenue made available", "FM27 offset not validated yet");

            if let Some(v) = schemas
                .field("c_wage_total")
                .and_then(|f| fields::read_field_u32(club, &club.raw, &f))
            {
                field_widget::info_label(ui, "Total Wage Budget", v);
            } else {
                field_widget::stub_field(ui, "Wage Used", "FM27 wage-use field not validated yet");
            }
            field_widget::stub_field(ui, "Max Wage (approx.)", "FM27 max-wage field not validated yet");
            field_widget::stub_field(ui, "Rich Benefactor", "FM27 owner/benefactor field not validated yet");

            if let Some((container, offset)) = sub_location(schemas, "c_avg_ticket") {
                if let Some((buf, base)) = club.sub_record_mut(container) {
                    f32_drag(ui, "Average Match Ticket Price", buf, offset, base, edits);
                }
            } else {
                field_widget::stub_field(ui, "Average Match Ticket Price", "FM27 offset not available");
            }
            field_widget::stub_field(ui, "Stadium Rental Per Year", "FM27 rental field not validated yet");
        });

    ui.add_space(8.0);
    egui::Frame::group(ui.style())
        .fill(egui::Color32::from_rgb(26, 32, 48))
        .stroke(egui::Stroke::new(1.0, egui::Color32::from_rgb(42, 50, 69)))
        .rounding(egui::Rounding::same(4))
        .inner_margin(egui::Margin::symmetric(8, 6))
        .show(ui, |ui| {
            ui.strong("Transfer embargo");
            ui.separator();
            field_widget::stub_field(ui, "Reason", "FM27 embargo structure not mapped yet");
            field_widget::stub_field(ui, "Start Date", "FM27 embargo structure not mapped yet");
            field_widget::stub_field(ui, "End Date", "FM27 embargo structure not mapped yet");
            field_widget::stub_field(ui, "Appeal date", "FM27 embargo structure not mapped yet");
            field_widget::stub_field(ui, "Age restriction", "FM27 embargo structure not mapped yet");
        });
}

fn show_transfer_center(ui: &mut egui::Ui, club: &ClubView) {
    ui.spacing_mut().item_spacing = egui::vec2(6.0, 4.0);
    ui.label(egui::RichText::new("Transfer Center").size(14.0).strong());
    ui.label(egui::RichText::new("FMRTE-style transfer workspace. FM27 transfer-record offsets still require validation before editing is enabled.").small().color(egui::Color32::from_rgb(255, 184, 77)));
    ui.add_space(4.0);

    egui::Frame::group(ui.style())
        .fill(egui::Color32::from_rgb(20, 25, 36))
        .stroke(egui::Stroke::new(1.0, egui::Color32::from_rgb(42, 50, 69)))
        .rounding(egui::Rounding::same(4))
        .inner_margin(egui::Margin::symmetric(6, 5))
        .show(ui, |ui| {
            egui::Grid::new("element_transfer_center_table")
                .num_columns(6)
                .spacing([16.0, 4.0])
                .striped(true)
                .show(ui, |ui| {
                    for h in ["Type", "Name", "From", "To", "Transfer Fee", "Status"] {
                        ui.label(egui::RichText::new(h).strong().small());
                    }
                    ui.end_row();
                    ui.label("—");
                    ui.label("No mapped transfer records");
                    ui.label("—");
                    ui.label(&club.full_name);
                    ui.label("—");
                    ui.label("Mapping required");
                    ui.end_row();
                });
        });

    ui.add_space(8.0);
    egui::Frame::group(ui.style())
        .fill(egui::Color32::from_rgb(26, 32, 48))
        .stroke(egui::Stroke::new(1.0, egui::Color32::from_rgb(42, 50, 69)))
        .rounding(egui::Rounding::same(4))
        .inner_margin(egui::Margin::symmetric(8, 6))
        .show(ui, |ui| {
            ui.strong("Information"); ui.separator();
            field_widget::info_label(ui, "To", &club.full_name);
            field_widget::stub_field(ui, "Value", "Transfer record fee offset not mapped yet");
        });

    ui.add_space(6.0);
    egui::Frame::group(ui.style())
        .fill(egui::Color32::from_rgb(26, 32, 48))
        .stroke(egui::Stroke::new(1.0, egui::Color32::from_rgb(42, 50, 69)))
        .rounding(egui::Rounding::same(4))
        .inner_margin(egui::Margin::symmetric(8, 6))
        .show(ui, |ui| {
            ui.strong(format!("Contract Details ({})", club.full_name)); ui.separator();
            field_widget::stub_field(ui, "Type", "Transfer contract structure not mapped yet");
            field_widget::stub_field(ui, "Wages", "Transfer contract structure not mapped yet");
            field_widget::stub_field(ui, "Started", "Transfer contract structure not mapped yet");
            field_widget::stub_field(ui, "Expires", "Transfer contract structure not mapped yet");
            field_widget::stub_field(ui, "On Rolling Contract", "Transfer contract structure not mapped yet");
        });
}

fn show_tactical_understanding(ui: &mut egui::Ui, club: &ClubView) {
    ui.spacing_mut().item_spacing = egui::vec2(6.0, 5.0);
    ui.horizontal(|ui| {
        ui.selectable_label(true, &club.full_name);
        ui.add_enabled(false, egui::Button::new(format!("{} U19", club.short_name)));
        ui.add_enabled(false, egui::Button::new(format!("{} B", club.short_name)));
    });
    ui.add_space(4.0);

    egui::Frame::group(ui.style())
        .fill(egui::Color32::from_rgb(26, 32, 48))
        .stroke(egui::Stroke::new(1.0, egui::Color32::from_rgb(42, 50, 69)))
        .rounding(egui::Rounding::same(4))
        .inner_margin(egui::Margin::symmetric(8, 7))
        .show(ui, |ui| {
            ui.strong("Tactical Understanding");
            ui.separator();
            ui.label(egui::RichText::new("Match Exposure").small().strong());
            ui.add_space(5.0);
            ui.label(egui::RichText::new("In Possession").small().strong().color(egui::Color32::from_rgb(139, 157, 188)));
            for label in ["Passing Style", "Build Up", "Chance Creation"] {
                ui.horizontal(|ui| {
                    ui.set_min_width(ui.available_width());
                    ui.add_sized([115.0, 18.0], egui::Label::new(label));
                    ui.add(egui::ProgressBar::new(0.0).desired_width((ui.available_width() - 75.0).max(120.0)).text("Not mapped"));
                });
            }
            ui.add_space(6.0);
            ui.label(egui::RichText::new("Out of Possession").small().strong().color(egui::Color32::from_rgb(139, 157, 188)));
            for label in ["Line of Engagement", "Pressing Intensity", "Pressing Trap", "Position/Role"] {
                ui.horizontal(|ui| {
                    ui.set_min_width(ui.available_width());
                    ui.add_sized([115.0, 18.0], egui::Label::new(label));
                    ui.add(egui::ProgressBar::new(0.0).desired_width((ui.available_width() - 75.0).max(120.0)).text("Not mapped"));
                });
            }
        });
    ui.add_space(6.0);
    ui.label(egui::RichText::new("These bars are intentionally locked until the FM27 team tactical-familiarity structure is identified and verified with live read-back.").small().color(egui::Color32::from_rgb(255, 184, 77)));
}

'@
$text = $text.Substring(0, $financeStart) + $newFinance + $text.Substring($stadiumStart)
[IO.File]::WriteAllText($cp, $text, [Text.UTF8Encoding]::new($false))

# Make the priority club pages live in the contextual left rail.
$a = 'src/app.rs'
Replace-Required $a '                    ui.add_enabled(false, egui::Button::new("⇆  Transfer Center"));' '                    if nav(ui, self.club_tab == club_panel::ClubTab::TransferCenter, "⇆  Transfer Center") { self.club_tab = club_panel::ClubTab::TransferCenter; }'
Replace-Required $a '                    ui.add_enabled(false, egui::Button::new("◉  Tactical Understanding"));' '                    if nav(ui, self.club_tab == club_panel::ClubTab::TacticalUnderstanding, "◉  Tactical Understanding") { self.club_tab = club_panel::ClubTab::TacticalUnderstanding; }'

Write-Host 'Element v1.7 FMRTE-inspired finance, transfer center and tactical-understanding workspaces applied successfully.'
