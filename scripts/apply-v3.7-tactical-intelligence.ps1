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
    if (-not $Text.Contains($Old)) { throw "v3.7: expected UI fragment not found: $Label" }
    return $Text.Replace($Old, $New)
}

# -----------------------------------------------------------------------------
# Element v3.7 — TACTICAL KNOWLEDGE INTELLIGENCE
#
# Pure presentation/intelligence layer on top of the v3.6 certified live reader.
# No new memory assumptions and zero writes.
#
# Important: the six collection semantics have not been independently named yet.
# We therefore present them as Instruction Group A-F and retain raw FM key IDs in
# tooltips instead of inventing labels.
# -----------------------------------------------------------------------------

$panel = 'src/ui/club_panel.rs'
$ui = Read-Text $panel

if (-not $ui.Contains('v3.6 • PREMIUM LIVE VIEWER')) {
    throw 'v3.7: v3.6 premium Tactical Knowledge viewer not found'
}

$ui = Replace-Required $ui 'v3.6 • PREMIUM LIVE VIEWER' 'v3.7 • TACTICAL INTELLIGENCE' 'version label'
$ui = Replace-Required $ui 'Live tactical familiarity for the selected club • universal FM27 mapping certified across the complete save' 'Live tactical familiarity • certified universal mapping • semantic labels shown only when independently verified' 'viewer subtitle'

$anchor = @'
    let senior_team_ok = element_tactical_pointer_ok(club.senior_team_addr);
    let report = club.tactical_report.as_ref();
'@
$insert = @'
    let senior_team_ok = element_tactical_pointer_ok(club.senior_team_addr);
    let report = club.tactical_report.as_ref();

    // v3.7 intelligence layer. These labels describe familiarity strength only;
    // they do not claim undocumented FM semantics for the six internal groups.
    let familiarity_band = |value: u16| -> (&'static str, egui::Color32) {
        match value {
            0..=1_999 => ("LEARNING", egui::Color32::from_rgb(255, 184, 77)),
            2_000..=3_999 => ("DEVELOPING", egui::Color32::from_rgb(255, 205, 110)),
            4_000..=5_999 => ("FAMILIAR", egui::Color32::from_rgb(112, 177, 255)),
            6_000..=7_999 => ("STRONG", egui::Color32::from_rgb(88, 214, 141)),
            8_000..=9_499 => ("EXCELLENT", egui::Color32::from_rgb(72, 210, 132)),
            _ => ("ELITE", egui::Color32::from_rgb(151, 126, 255)),
        }
    };
    let group_names = [
        "INSTRUCTION GROUP A",
        "INSTRUCTION GROUP B",
        "INSTRUCTION GROUP C",
        "INSTRUCTION GROUP D",
        "INSTRUCTION GROUP E",
        "INSTRUCTION GROUP F",
    ];
'@
$ui = Replace-Required $ui $anchor $insert 'intelligence helpers'

$oldOverview = @'
                ui.label(egui::RichText::new("OVERALL FAMILIARITY").size(8.0).color(egui::Color32::from_rgb(139, 157, 188)));
                ui.label(egui::RichText::new(format!("{:.1}%", overview_avg as f32 / 100.0)).size(20.0).strong());
                ui.add_sized([ui.available_width(), 14.0], egui::ProgressBar::new((overview_avg as f32 / 10_000.0).clamp(0.0, 1.0)));
'@
$newOverview = @'
                ui.label(egui::RichText::new("OVERALL FAMILIARITY").size(8.0).color(egui::Color32::from_rgb(139, 157, 188)));
                let (overall_band, overall_band_color) = familiarity_band(overview_avg);
                ui.horizontal(|ui| {
                    ui.label(egui::RichText::new(format!("{:.1}%", overview_avg as f32 / 100.0)).size(20.0).strong());
                    ui.label(egui::RichText::new(overall_band).size(7.5).strong().color(overall_band_color));
                });
                ui.add_sized([ui.available_width(), 14.0], egui::ProgressBar::new((overview_avg as f32 / 10_000.0).clamp(0.0, 1.0)));
'@
$ui = Replace-Required $ui $oldOverview $newOverview 'overall familiarity intelligence badge'

$oldHeading = '                            ui.label(egui::RichText::new(format!("COLLECTION {}", idx + 1)).size(10.0).strong());'
$newHeading = @'
                            ui.label(egui::RichText::new(group_names[idx]).size(10.0).strong())
                                .on_hover_text(format!(
                                    "FM internal tactical collection {}. Its structural mapping is certified; its human-readable semantic name is intentionally not guessed.",
                                    idx + 1
                                ));
'@
$ui = Replace-Required $ui $oldHeading $newHeading.TrimEnd("`r", "`n") 'collection heading'

$oldAverage = @'
                        ui.horizontal(|ui| {
                            ui.label(egui::RichText::new(format!("{:.1}%", averages[idx] as f32 / 100.0)).size(18.0).strong());
                            ui.label(egui::RichText::new(format!("{} records", records[idx])).size(8.0).color(egui::Color32::from_rgb(139, 157, 188)));
                        });
'@
$newAverage = @'
                        ui.horizontal(|ui| {
                            ui.label(egui::RichText::new(format!("{:.1}%", averages[idx] as f32 / 100.0)).size(18.0).strong());
                            let (band, band_color) = familiarity_band(averages[idx]);
                            ui.label(egui::RichText::new(band).size(7.0).strong().color(band_color));
                            ui.label(egui::RichText::new(format!("{} records", records[idx])).size(8.0).color(egui::Color32::from_rgb(139, 157, 188)));
                        });
'@
$ui = Replace-Required $ui $oldAverage $newAverage 'per-group familiarity intelligence badge'

$oldExtremes = @'
                        if let Some((key, value)) = lows[idx] {
                            ui.label(egui::RichText::new(format!("LOW  key 0x{key:04X}   {:.1}%", value as f32 / 100.0)).size(7.5).color(egui::Color32::from_rgb(255, 184, 77)));
                        }
                        if let Some((key, value)) = highs[idx] {
                            ui.label(egui::RichText::new(format!("HIGH key 0x{key:04X}   {:.1}%", value as f32 / 100.0)).size(7.5).color(egui::Color32::from_rgb(88, 214, 141)));
                        }
'@
$newExtremes = @'
                        if let Some((key, value)) = lows[idx] {
                            ui.label(
                                egui::RichText::new(format!("LOWEST  {:.1}%", value as f32 / 100.0))
                                    .size(7.5)
                                    .color(egui::Color32::from_rgb(255, 184, 77)),
                            )
                            .on_hover_text(format!(
                                "Raw FM key: 0x{key:04X}\nThe key is retained for verification; Element will show a friendly instruction name only after the semantic mapping is proven."
                            ));
                        }
                        if let Some((key, value)) = highs[idx] {
                            ui.label(
                                egui::RichText::new(format!("HIGHEST {:.1}%", value as f32 / 100.0))
                                    .size(7.5)
                                    .color(egui::Color32::from_rgb(88, 214, 141)),
                            )
                            .on_hover_text(format!(
                                "Raw FM key: 0x{key:04X}\nThe key is retained for verification; Element will show a friendly instruction name only after the semantic mapping is proven."
                            ));
                        }
'@
$ui = Replace-Required $ui $oldExtremes $newExtremes 'lowest/highest intelligent labels'

# Add a compact semantic integrity note without bringing back the old debug wall.
$footerNeedle = 'ui.label(egui::RichText::new("UNIVERSAL MAPPING CERTIFIED")'
if ($ui.Contains($footerNeedle) -and -not $ui.Contains('RAW KEY TOOLTIP')) {
    $ui = $ui.Replace(
        $footerNeedle,
        'ui.label(egui::RichText::new("RAW KEY TOOLTIP").size(7.0).color(egui::Color32::from_rgb(139, 157, 188))); ui.separator(); ' + $footerNeedle
    )
}

Write-Text $panel $ui
Write-Host 'Element v3.7 Tactical Knowledge intelligence polish applied successfully.'
