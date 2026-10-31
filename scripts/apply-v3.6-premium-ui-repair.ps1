$ErrorActionPreference = 'Stop'
$SourceRoot = (Get-Location).Path

function Read-Text([string]$RelativePath) {
    $Path = Join-Path $SourceRoot $RelativePath
    if (-not (Test-Path -LiteralPath $Path)) { throw "Source file not found: $Path" }
    return [IO.File]::ReadAllText($Path)
}

# v3.6 core is now responsible for the complete Tactical Knowledge UI swap.
# This pass deliberately performs no mutation: it only verifies that the viewer
# landed and that the shared Club helpers/pages survived intact.
$inspector = Read-Text 'src/bridge/tactical_inspector.rs'
if (-not $inspector.Contains('pub(super) fn view_selected_tactical_knowledge(')) {
    throw 'v3.6 validator: premium tactical viewer core missing'
}

$worker = Read-Text 'src/bridge/worker.rs'
if (-not $worker.Contains('tactical_inspector::view_selected_tactical_knowledge(f, club_addr, senior_team_addr)')) {
    throw 'v3.6 validator: worker is not wired to selected-team viewer'
}

$ui = Read-Text 'src/ui/club_panel.rs'
foreach ($needle in @(
    'v3.6 • PREMIUM LIVE VIEWER',
    'fn locked_notice(ui: &mut egui::Ui, text: &str) {',
    'fn locked_field(ui: &mut egui::Ui, label: &str) {',
    'fn page_card(ui: &mut egui::Ui, title: &str, add: impl FnOnce(&mut egui::Ui)) {',
    'fn show_squads('
)) {
    if (-not $ui.Contains($needle)) {
        throw "v3.6 validator: required UI token missing: $needle"
    }
}

Write-Host 'v3.6 premium Tactical Knowledge viewer validated; shared Club helpers preserved.'
