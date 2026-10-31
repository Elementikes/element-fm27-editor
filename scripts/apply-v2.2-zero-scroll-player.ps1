$ErrorActionPreference = 'Stop'
$SourceRoot = (Get-Location).Path
$changes = 0

function Replace-Optional {
    param([string]$RelativePath, [string]$Old, [string]$New)
    $Path = Join-Path $SourceRoot $RelativePath
    if (-not (Test-Path -LiteralPath $Path)) { throw "Source file not found: $Path" }
    $text = [IO.File]::ReadAllText($Path)
    if ($text.Contains($Old)) {
        $text = $text.Replace($Old, $New)
        [IO.File]::WriteAllText($Path, $text, [Text.UTF8Encoding]::new($false))
        $script:changes++
        Write-Host "v2.2: updated $RelativePath"
        return $true
    }
    Write-Host "v2.2: optional pattern already changed / not present in $RelativePath"
    return $false
}

# -----------------------------------------------------------------------------
# Element v2.2 ZERO-SCROLL PLAYER PASS
# Pure density polish. No live-memory addresses, schemas or write paths change.
# Target: full Player Information + complete attribute matrix visible at the
# user's maximized desktop resolution without needing vertical scrolling.
# -----------------------------------------------------------------------------

# 1) Attribute rows: 16px -> 14px, narrower labels, zero vertical row spacing.
$fw = 'src/ui/field_widget.rs'
Replace-Optional $fw 'const VALUE_SIZE: [f32; 2] = [30.0, 16.0];' 'const VALUE_SIZE: [f32; 2] = [28.0, 14.0];' | Out-Null
Replace-Optional $fw 'egui::vec2(92.0, VALUE_SIZE[1])' 'egui::vec2(86.0, VALUE_SIZE[1])' | Out-Null
Replace-Optional $fw 'ui.set_min_size(egui::vec2(92.0, VALUE_SIZE[1]));' 'ui.set_min_size(egui::vec2(86.0, VALUE_SIZE[1]));' | Out-Null
Replace-Optional $fw 'ui.spacing_mut().item_spacing.y = 0.5;' 'ui.spacing_mut().item_spacing.y = 0.0;' | Out-Null

# 2) Player hero: keep the face and metrics, but shave ~12px from the header.
$p = 'src/ui/player_panel.rs'
Replace-Optional $p '.inner_margin(egui::Margin::symmetric(10, 8)).show(ui, |ui| {' '.inner_margin(egui::Margin::symmetric(8, 5)).show(ui, |ui| {' | Out-Null
Replace-Optional $p 'egui::vec2(64.0,64.0)' 'egui::vec2(56.0,56.0)' | Out-Null
Replace-Optional $p 'egui::vec2(64.0, 64.0)' 'egui::vec2(56.0, 56.0)' | Out-Null
Replace-Optional $p '.size(22.0).strong().color(egui::Color32::WHITE)' '.size(20.0).strong().color(egui::Color32::WHITE)' | Out-Null
Replace-Optional $p '.inner_margin(egui::Margin::symmetric(10, 6)).show(ui, |ui| {' '.inner_margin(egui::Margin::symmetric(8, 4)).show(ui, |ui| {' | Out-Null

# Hero tail is immediately followed by PLAYER DATA in v2.1; make the gap tiny.
Replace-Optional $p @'
    });
    ui.add_space(6.0);

    // Navigation is rendered in the contextual application rail (Element v1.5).
'@ @'
    });
    ui.add_space(2.0);

    // Navigation is rendered in the contextual application rail (Element v1.5).
'@ | Out-Null

# 3) PLAYER DATA + action strip: one compact visual cluster.
Replace-Optional $p @'
    ui.horizontal(|ui| {
        ui.label(egui::RichText::new("PLAYER DATA").size(11.0).strong().color(egui::Color32::from_rgb(176, 191, 218)));
        ui.separator();
        ui.label(egui::RichText::new("LIVE PROFILE").size(9.0).strong().color(egui::Color32::from_rgb(72, 210, 132)));
    });
    ui.add_space(3.0);
'@ @'
    ui.horizontal(|ui| {
        ui.label(egui::RichText::new("PLAYER DATA").size(9.5).strong().color(egui::Color32::from_rgb(176, 191, 218)));
        ui.separator();
        ui.label(egui::RichText::new("LIVE").size(8.5).strong().color(egui::Color32::from_rgb(72, 210, 132)));
    });
    ui.add_space(1.0);
'@ | Out-Null

Replace-Optional $p '.inner_margin(egui::Margin::symmetric(7, 4))' '.inner_margin(egui::Margin::symmetric(6, 2))' | Out-Null
Replace-Optional $p 'egui::RichText::new("ACTIONS").size(9.5)' 'egui::RichText::new("ACTIONS").size(8.5)' | Out-Null
Replace-Optional $p 'egui::RichText::new(label).size(9.5)).min_size(egui::vec2(0.0, 20.0))' 'egui::RichText::new(label).size(9.0)).min_size(egui::vec2(0.0, 18.0))' | Out-Null

# Only the post-actions gap; leave unrelated add_space calls untouched.
Replace-Optional $p @'
        });
    ui.add_space(4.0);

    // Element v2.1 premium compact information matrix.
'@ @'
        });
    ui.add_space(2.0);

    // Element v2.1 premium compact information matrix.
'@ | Out-Null

# 4) Top information cards: tighter frame/headers and no extra vertical padding.
Replace-Optional $p '.inner_margin(egui::Margin::symmetric(6, 4))' '.inner_margin(egui::Margin::symmetric(5, 2))' | Out-Null
Replace-Optional $p 'egui::RichText::new(title).size(10.5).strong()' 'egui::RichText::new(title).size(9.5).strong()' | Out-Null
Replace-Optional $p 'ui.spacing_mut().item_spacing.y = 1.0;' 'ui.spacing_mut().item_spacing.y = 0.0;' | Out-Null

Replace-Optional $p @'
    });
    ui.add_space(4.0);

    egui::Frame::none()
        .fill(egui::Color32::from_rgb(11, 14, 20))
'@ @'
    });
    ui.add_space(2.0);

    egui::Frame::none()
        .fill(egui::Color32::from_rgb(11, 14, 20))
'@ | Out-Null

# 5) PLAYER ATTRIBUTES title + cards: compress headers and stacked mini-cards.
Replace-Optional $p '.inner_margin(egui::Margin::symmetric(8, 4))' '.inner_margin(egui::Margin::symmetric(6, 2))' | Out-Null
Replace-Optional $p 'egui::RichText::new("PLAYER ATTRIBUTES").size(12.0)' 'egui::RichText::new("PLAYER ATTRIBUTES").size(10.5)' | Out-Null
Replace-Optional $p '.inner_margin(egui::Margin::symmetric(5, 3))' '.inner_margin(egui::Margin::symmetric(4, 2))' | Out-Null
Replace-Optional $p 'egui::RichText::new(heading)`n                    .size(11.0)' 'egui::RichText::new(heading)`n                    .size(10.0)' | Out-Null
Replace-Optional $p 'cols[0].add_space(3.0);' 'cols[0].add_space(1.0);' | Out-Null
Replace-Optional $p 'cols[3].add_space(3.0);' 'cols[3].add_space(1.0);' | Out-Null

# 6) Sidebar: a final small width gain; keep all labels/features intact.
$a = 'src/app.rs'
Replace-Optional $a '.default_width(158.0).min_width(152.0).max_width(172.0)' '.default_width(148.0).min_width(144.0).max_width(160.0)' | Out-Null

if ($changes -lt 8) {
    throw "v2.2 safety check: only $changes expected density patterns were updated; refusing a partial transform."
}

Write-Host "Element v2.2 zero-scroll player density pass applied successfully ($changes transforms)."
