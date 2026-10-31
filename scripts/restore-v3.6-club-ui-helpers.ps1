$ErrorActionPreference = 'Stop'
$SourceRoot = (Get-Location).Path
$Path = Join-Path $SourceRoot 'src/ui/club_panel.rs'
if (-not (Test-Path -LiteralPath $Path)) { throw "Source file not found: $Path" }
$text = [IO.File]::ReadAllText($Path)

# v3.6 premium viewer replaces the old Tactical Knowledge function. In the
# transformed v1.8 source, the shared club UI helpers sit between that function
# and show_squads(). Restore only those helpers if the repair pass removed them.
if ($text.Contains('fn locked_notice(ui: &mut egui::Ui, text: &str) {') -and
    $text.Contains('fn locked_field(ui: &mut egui::Ui, label: &str) {') -and
    $text.Contains('fn page_card(ui: &mut egui::Ui, title: &str, add: impl FnOnce(&mut egui::Ui)) {')) {
    Write-Host 'v3.6 club UI helpers already present; no restore needed.'
    exit 0
}

$insertAt = $text.IndexOf('fn show_squads(')
if ($insertAt -lt 0) { throw 'v3.6 helper restore: show_squads boundary not found' }

$helpers = @'
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

'@

$text = $text.Substring(0, $insertAt) + $helpers + $text.Substring($insertAt)
[IO.File]::WriteAllText($Path, $text, [Text.UTF8Encoding]::new($false))

# Safety checks: all three helpers must exist exactly once after the restore.
foreach ($needle in @(
    'fn locked_notice(ui: &mut egui::Ui, text: &str) {',
    'fn locked_field(ui: &mut egui::Ui, label: &str) {',
    'fn page_card(ui: &mut egui::Ui, title: &str, add: impl FnOnce(&mut egui::Ui)) {'
)) {
    $count = ([regex]::Matches($text, [regex]::Escape($needle))).Count
    if ($count -ne 1) { throw "v3.6 helper restore safety check failed for '$needle': count=$count" }
}

Write-Host 'v3.6 club UI helpers restored successfully.'
