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

# -----------------------------------------------------------------------------
# Element v2.1 premium polish
# Goal: reclaim vertical space without touching proven live-memory write paths.
# -----------------------------------------------------------------------------
$p = 'src/ui/player_panel.rs'
$pp = Join-Path $SourceRoot $p

# Compact the redundant Player Information title; CA/PA already live in the hero.
Replace-Required $p @'
    ui.horizontal(|ui| {
        ui.heading(egui::RichText::new("Player Information").size(22.0).strong());
        if let (Some(ca), Some(pa)) = (player.field_u8("p_ca"), player.field_u8("p_pa")) {
            ui.separator();
            ui.label(egui::RichText::new(format!("CA {ca} / PA {pa}")).strong().color(egui::Color32::from_rgb(116, 145, 255)));
        }
    });
    ui.add_space(8.0);
'@ @'
    ui.horizontal(|ui| {
        ui.label(egui::RichText::new("PLAYER DATA").size(11.0).strong().color(egui::Color32::from_rgb(176, 191, 218)));
        ui.separator();
        ui.label(egui::RichText::new("LIVE PROFILE").size(9.0).strong().color(egui::Color32::from_rgb(72, 210, 132)));
    });
    ui.add_space(3.0);
'@

# Slim Quick Actions into a premium command strip.
Replace-Required $p @'
    egui::Frame::group(ui.style())
        .fill(egui::Color32::from_rgb(18, 23, 33))
        .inner_margin(egui::Margin::symmetric(12, 9))
        .show(ui, |ui| {
            ui.horizontal_wrapped(|ui| {
                ui.label(egui::RichText::new("QUICK ACTIONS").strong().color(egui::Color32::from_rgb(232, 236, 244)));
                ui.separator();
                ui.add_enabled(false, egui::Button::new("Heal"));
                ui.add_enabled(false, egui::Button::new("Max Condition"));
                ui.add_enabled(false, egui::Button::new("Max Morale"));
                ui.add_enabled(false, egui::Button::new("Remove Ban"));
                ui.add_enabled(false, egui::Button::new("Freeze"));
                ui.add_enabled(false, egui::Button::new("Move to Club"));
            });
        });
    ui.add_space(10.0);
'@ @'
    egui::Frame::none()
        .fill(egui::Color32::from_rgb(15, 20, 29))
        .stroke(egui::Stroke::new(1.0, egui::Color32::from_rgb(39, 47, 64)))
        .rounding(egui::Rounding::same(3))
        .inner_margin(egui::Margin::symmetric(7, 4))
        .show(ui, |ui| {
            ui.horizontal_wrapped(|ui| {
                ui.spacing_mut().item_spacing.x = 4.0;
                ui.label(egui::RichText::new("ACTIONS").size(9.5).strong().color(egui::Color32::from_rgb(154, 172, 204)));
                ui.separator();
                for label in ["Heal", "Condition 100", "Morale 100", "Remove Ban", "Freeze", "Move to Club"] {
                    ui.add_enabled(false, egui::Button::new(egui::RichText::new(label).size(9.5)).min_size(egui::vec2(0.0, 20.0)));
                }
            });
        });
    ui.add_space(4.0);
'@

# Replace the tall flat Personal / Appearance / Ability / Reputation / Stats row
# with five compact premium cards. Every existing mapped editor remains live.
$text = [IO.File]::ReadAllText($pp)
$infoStart = $text.IndexOf('    // Top info row: Personal | Ability | Reputation')
$attrTitle = $text.IndexOf('PLAYER ATTRIBUTES', $infoStart)
$attrFrame = if ($attrTitle -ge 0) { $text.LastIndexOf('    egui::Frame::none()', $attrTitle) } else { -1 }
if ($infoStart -lt 0 -or $attrTitle -lt 0 -or $attrFrame -lt $infoStart) {
    throw 'v2.1: compact information row boundaries not found'
}
$newInfo = @'
    // Element v2.1 premium compact information matrix.
    ui.spacing_mut().item_spacing = egui::vec2(5.0, 2.0);
    ui.columns(5, |cols| {
        let card = |ui: &mut egui::Ui, title: &str, add: &mut dyn FnMut(&mut egui::Ui)| {
            egui::Frame::group(ui.style())
                .fill(egui::Color32::from_rgb(23, 29, 42))
                .stroke(egui::Stroke::new(1.0, egui::Color32::from_rgb(40, 49, 67)))
                .rounding(egui::Rounding::same(3))
                .inner_margin(egui::Margin::symmetric(6, 4))
                .show(ui, |ui| {
                    ui.label(egui::RichText::new(title).size(10.5).strong().color(egui::Color32::from_rgb(215, 225, 242)));
                    ui.separator();
                    ui.spacing_mut().item_spacing.y = 1.0;
                    add(ui);
                });
        };

        let mut identity = |ui: &mut egui::Ui| {
            edits.extend(field_widget::dob_edit(ui, &mut player.raw, &p_dob, addr));
            if let Some(f) = schemas.field("p_height") {
                edits.extend(field_widget::raw_u16_edit(ui, &f, &mut player.raw, 250, addr));
            }
            if let Some(birthplace) = &player.birthplace {
                field_widget::info_label(ui, "Birth Place", birthplace);
            }
        };
        card(&mut cols[0], "Identity", &mut identity);

        let mut appearance = |ui: &mut egui::Ui| {
            if let Some(f) = schemas.field("p_ethnicity") {
                edits.extend(field_widget::choice_u8_edit(ui, "Ethnicity", &mut player.raw, &f, addr, ETHNICITIES));
            }
            for (key, max) in [("p_skin_tone", 19), ("p_hair_colour", 18), ("p_hair_length", 6)] {
                if let Some(f) = schemas.field(key) {
                    edits.extend(field_widget::raw_u8_edit(ui, &f, &mut player.raw, max, addr));
                }
            }
        };
        card(&mut cols[1], "Appearance", &mut appearance);

        let mut ability = |ui: &mut egui::Ui| {
            edits.extend(field_widget::ca_pa_edit(ui, &mut player.raw, &p_ca, &p_pa, addr));
            if let Some(value) = player.field_u32("p_value") {
                field_widget::info_label(ui, "Market Value", value);
            }
        };
        card(&mut cols[2], "Ability", &mut ability);

        let mut reputation = |ui: &mut egui::Ui| {
            if let Some(e) = field_widget::raw_u16_edit(ui, &p_current_rep, &mut player.raw, 10000, addr) { edits.push(e); }
            if let Some(e) = field_widget::raw_u16_edit(ui, &p_home_rep, &mut player.raw, 10000, addr) { edits.push(e); }
            if let Some(e) = field_widget::raw_u16_edit(ui, &p_world_rep, &mut player.raw, 10000, addr) { edits.push(e); }
        };
        card(&mut cols[3], "Reputation", &mut reputation);

        let mut career = |ui: &mut egui::Ui| {
            if let (Some(caps), Some(goals)) = (player.field_int("p_intl_caps"), player.field_int("p_intl_goals")) {
                field_widget::info_label(ui, "Intl Caps / Goals", format!("{caps} / {goals}"));
            }
            if let (Some(caps), Some(goals)) = (player.field_int("p_u21_caps"), player.field_int("p_u21_goals")) {
                field_widget::info_label(ui, "U21 Caps / Goals", format!("{caps} / {goals}"));
            }
            if let Some(wage) = player.field_u32("p_contract_wage") {
                field_widget::info_label(ui, "Wage", format_wage(wage, wage_period));
            }
        };
        card(&mut cols[4], "Career", &mut career);
    });
    ui.add_space(4.0);

'@
$text = $text.Substring(0, $infoStart) + $newInfo + $text.Substring($attrFrame)
[IO.File]::WriteAllText($pp, $text, [Text.UTF8Encoding]::new($false))

# -----------------------------------------------------------------------------
# Shell density: narrower rail, smaller nav rows, tighter central padding.
# -----------------------------------------------------------------------------
$a = 'src/app.rs'
Replace-Required $a '.default_width(172.0).min_width(164.0).max_width(190.0)' '.default_width(158.0).min_width(152.0).max_width(172.0)'
Replace-Required $a 'ui.add_sized([ui.available_width(), 25.0], egui::Button::new(egui::RichText::new(label).size(11.0)' 'ui.add_sized([ui.available_width(), 23.0], egui::Button::new(egui::RichText::new(label).size(10.5)'
Replace-Required $a '.inner_margin(egui::Margin::symmetric(14,12)))' '.inner_margin(egui::Margin::symmetric(11,8)))'

# Make the global command bar slightly slimmer while retaining the single search.
Replace-Required $a '.inner_margin(egui::Margin::symmetric(12, 8)))' '.inner_margin(egui::Margin::symmetric(12, 6)))'

Write-Host 'Element v2.1 premium player polish applied successfully.'
