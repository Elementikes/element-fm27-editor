$ErrorActionPreference = 'Stop'

# GitHub Actions invokes this script while the shell is in source/, but
# PowerShell resolves relative .NET file paths from the process working dir.
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

# Theme: make the normal Dark theme Element's graphite/indigo palette.
$settings = 'src/settings.rs'
Replace-Required $settings '            Theme::Dark     => egui::Visuals::dark(),' '            Theme::Dark     => element_visuals(),'
$marker = @'
/// Navy/steel-blue dark theme.
fn dark_blue_visuals() -> egui::Visuals {
'@
$insert = @'
/// Element graphite/indigo theme.
fn element_visuals() -> egui::Visuals {
    let mut v = egui::Visuals::dark();
    v.window_fill = egui::Color32::from_rgb(13, 16, 23);
    v.panel_fill = egui::Color32::from_rgb(17, 21, 30);
    v.faint_bg_color = egui::Color32::from_rgb(25, 30, 43);
    v.extreme_bg_color = egui::Color32::from_rgb(8, 10, 15);
    v.hyperlink_color = egui::Color32::from_rgb(116, 145, 255);
    v.selection.bg_fill = egui::Color32::from_rgb(75, 96, 210);
    v.widgets.inactive.bg_fill = egui::Color32::from_rgb(28, 34, 47);
    v.widgets.hovered.bg_fill = egui::Color32::from_rgb(40, 49, 68);
    v.widgets.active.bg_fill = egui::Color32::from_rgb(52, 65, 96);
    v
}

/// Navy/steel-blue dark theme.
fn dark_blue_visuals() -> egui::Visuals {
'@
Replace-Required $settings $marker $insert

# Bigger default workspace and roomier controls.
$main = 'src/main.rs'
Replace-Required $main '.with_inner_size([1280.0 * f, 800.0 * f])' '.with_inner_size([1440.0 * f, 900.0 * f])'
$old = @'
        Box::new(move |cc| {
            let app = FmEditorApp::new(cc).with_branch(branch);
'@
$new = @'
        Box::new(move |cc| {
            cc.egui_ctx.style_mut(|style| {
                style.spacing.item_spacing = eframe::egui::vec2(10.0, 8.0);
                style.spacing.button_padding = eframe::egui::vec2(12.0, 7.0);
                style.spacing.indent = 20.0;
                style.spacing.interact_size.y = 28.0;
                style.visuals = settings.theme.visuals();
            });
            let app = FmEditorApp::new(cc).with_branch(branch);
'@
Replace-Required $main $old $new

# Transfer Lab polish without changing the proven write paths.
$player = 'src/ui/player_panel.rs'
Replace-Required $player '    ui.heading("Transfer Lab");' @'
    ui.horizontal(|ui| {
        ui.heading("Transfer Lab");
        ui.label(egui::RichText::new("ELEMENT").strong().color(egui::Color32::from_rgb(116, 145, 255)));
    });
'@
Replace-Required $player '    ui.label("Safe, mapped FM27 transfer controls. Advanced operations stay locked until their linked records are verified.");' '    ui.label(egui::RichText::new("Market status, asking price and contract controls. Advanced transfer writes remain locked until FM27 linked records are verified.").weak());'
Replace-Required $player 'ui.add_enabled(false, egui::Button::new("Move Player Now"));' 'ui.add_enabled(false, egui::Button::new("Force Transfer"));'

Write-Host 'Element v0.3 UI transform applied successfully.'
