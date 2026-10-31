$ErrorActionPreference = 'Stop'
$SourceRoot = (Get-Location).Path
$p = Join-Path $SourceRoot 'src/ui/player_panel.rs'
$text = [IO.File]::ReadAllText($p)

# v0.8 deliberately replaces the v0.5 navigation block with its own
# document-style variant. v1.5 removes the navigation strip entirely because
# player navigation moves to the contextual left rail. Normalize the known
# v0.8 block back to the canonical v0.5 block expected by the v1.5 transform.
$v08 = @'
    // Element v0.8 document-style navigation strip.
    egui::Frame::none()
        .fill(egui::Color32::from_rgb(11, 14, 20))
        .inner_margin(egui::Margin::symmetric(10, 7))
        .show(ui, |ui| {
            ui.horizontal_wrapped(|ui| {
                ui.spacing_mut().item_spacing.x = 4.0;
                ui.selectable_value(tab, PlayerTab::Overview, "  Information  ");
                ui.selectable_value(tab, PlayerTab::PositionsTraits, "  Positions & Traits  ");
                if player.contract_raw.is_some() {
                    ui.selectable_value(tab, PlayerTab::Contract, "  Contract  ");
                    ui.selectable_value(tab, PlayerTab::TransferLab, "  Move to Club  ");
                }
            });
        });
    ui.add_space(6.0);
'@

$canonical = @'
    // Element profile navigation: compact, high-contrast editor tabs.
    egui::Frame::none()
        .fill(egui::Color32::from_rgb(20, 25, 36))
        .inner_margin(egui::Margin::symmetric(10, 8))
        .show(ui, |ui| {
            ui.horizontal_wrapped(|ui| {
                ui.selectable_value(tab, PlayerTab::Overview, "Information");
                ui.selectable_value(tab, PlayerTab::PositionsTraits, "Positions & Traits");
                if player.contract_raw.is_some() {
                    ui.selectable_value(tab, PlayerTab::Contract, "Contract");
                    ui.selectable_value(tab, PlayerTab::TransferLab, "Move to Club");
                }
            });
        });
    ui.add_space(6.0);
'@

if ($text.Contains($canonical)) {
    Write-Host 'v1.5 compatibility: canonical player navigation already present.'
} elseif ($text.Contains($v08)) {
    $text = $text.Replace($v08, $canonical)
    [IO.File]::WriteAllText($p, $text, [Text.UTF8Encoding]::new($false))
    Write-Host 'v1.5 compatibility: normalized v0.8 player navigation for v1.5.'
} else {
    throw 'v1.5 compatibility: neither the known v0.8 nor canonical v0.5 player navigation block was found.'
}

# v1.5 removes the blue banner by slicing from the banner marker to the
# navigation-rail marker. In the v0.9-generated app.rs, the cache/filter
# declarations live between those two markers, so that slice would also delete
# schemas, filtered result vectors, wage_period and face_pack_path. Move that
# declaration block immediately before the banner so the v1.5 slice removes
# only presentation code and preserves the live app scope.
$appPath = Join-Path $SourceRoot 'src/app.rs'
$app = [IO.File]::ReadAllText($appPath)
$bannerMarker = '        // ===== Element blue workspace banner ====='
$declMarker = '        // Clone the Arc so we can borrow entity data inside egui closures'
$railMarker = '        // ===== Element navigation rail ====='
$bannerStart = $app.IndexOf($bannerMarker)
$declStart = $app.IndexOf($declMarker, $bannerStart)
$railStart = $app.IndexOf($railMarker, $declStart)
if ($bannerStart -lt 0 -or $declStart -lt 0 -or $railStart -lt 0) {
    throw 'v1.5 compatibility: could not locate banner/cache/rail boundaries in app.rs.'
}
if (-not ($bannerStart -lt $declStart -and $declStart -lt $railStart)) {
    throw 'v1.5 compatibility: unexpected app.rs boundary ordering.'
}
$declarations = $app.Substring($declStart, $railStart - $declStart)
$banner = $app.Substring($bannerStart, $declStart - $bannerStart)
$app = $app.Substring(0, $bannerStart) + $declarations + $banner + $app.Substring($railStart)
[IO.File]::WriteAllText($appPath, $app, [Text.UTF8Encoding]::new($false))
Write-Host 'v1.5 compatibility: preserved cache/filter declarations outside banner-removal slice.'
