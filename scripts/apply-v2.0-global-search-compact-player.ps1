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
# v2.0 GLOBAL SEARCH
# One persistent search query feeds Players + Staff + Clubs. Page-local search
# rows are removed to reclaim vertical space. Player advanced filters remain
# accessible through a compact gear button next to the global search.
# -----------------------------------------------------------------------------
$a = 'src/app.rs'
$ap = Join-Path $SourceRoot $a

Replace-Required $a @'
    // Navigation
    active_page: Page,
'@ @'
    // Navigation
    active_page: Page,
    // One query shared by Players / Staff / Clubs. Entity-specific advanced
    // filters remain in their existing state objects.
    global_search: String,
'@

Replace-Required $a @'
            active_page: Page::HumanManager,
'@ @'
            active_page: Page::HumanManager,
            global_search: String::new(),
'@

Replace-Required $a @'
                        let search = ui.add_sized([250.0, 27.0], egui::TextEdit::singleline(&mut self.player_search.query).hint_text("Search player name / UID…"));
                        if search.changed() {
                            self.active_page = Page::PlayerSearch;
                            self.active_tab = None;
                            nav_page_clicked = true;
                        }
'@ @'
                        let search = ui.add_sized(
                            [330.0, 27.0],
                            egui::TextEdit::singleline(&mut self.global_search)
                                .hint_text("Search players, staff, clubs / UID…"),
                        );
                        if search.changed() {
                            let q = self.global_search.clone();
                            self.player_search.query = q.clone();
                            self.staff_search.query = q.clone();
                            self.club_search.query = q;
                            self.active_tab = None;
                            nav_page_clicked = true;
                        }
                        if !self.global_search.is_empty() && ui.small_button("×").on_hover_text("Clear global search").clicked() {
                            self.global_search.clear();
                            self.player_search.query.clear();
                            self.staff_search.query.clear();
                            self.club_search.query.clear();
                            self.active_tab = None;
                            nav_page_clicked = true;
                        }
                        if self.active_page == Page::PlayerSearch {
                            if ui.small_button("⚙").on_hover_text("Advanced player filters").clicked() && !self.advanced_open {
                                self.advanced_snapshot = Some(self.player_search.clone());
                                self.advanced_open = true;
                            }
                        }
'@

# Remove the three page-local filter rows. The global top search is now the
# only name/UID field; this saves roughly two toolbar rows on every search page.
$app = [IO.File]::ReadAllText($ap)
$filterStart = $app.IndexOf('                    // Filter row — always rendered, live filtering each frame.')
$spaceMarker = '                    ui.add_space(4.0);'
$filterEnd = if ($filterStart -ge 0) { $app.IndexOf($spaceMarker, $filterStart) } else { -1 }
if ($filterStart -lt 0 -or $filterEnd -lt 0) { throw 'v2.0: local search/filter block boundary not found' }
$filterEnd += $spaceMarker.Length
$newFilter = @'
                    // v2.0: name/UID search lives exclusively in the global top bar.
                    // Entity-specific advanced state is preserved internally; Players
                    // expose it through the compact gear button beside Global Search.
                    ui.add_space(1.0);
'@
$app = $app.Substring(0, $filterStart) + $newFilter + $app.Substring($filterEnd)
[IO.File]::WriteAllText($ap, $app, [Text.UTF8Encoding]::new($false))

# -----------------------------------------------------------------------------
# v2.0 PLAYER DENSITY
# Keep every proven live-write path, but compress controls and render all major
# attribute families in a single six-column row so Information fits without
# scrolling on a normal maximized desktop window.
# -----------------------------------------------------------------------------
$fw = 'src/ui/field_widget.rs'
Replace-Required $fw 'const VALUE_SIZE: [f32; 2] = [36.0, 18.0];' 'const VALUE_SIZE: [f32; 2] = [30.0, 16.0];'
Replace-Required $fw @'
    ui.allocate_ui_with_layout(
        egui::vec2(108.0, VALUE_SIZE[1]),
        egui::Layout::left_to_right(egui::Align::Center),
        |ui| {
            ui.set_min_size(egui::vec2(108.0, VALUE_SIZE[1]));
            ui.add(egui::Label::new(label).truncate())
        },
    )
'@ @'
    ui.allocate_ui_with_layout(
        egui::vec2(92.0, VALUE_SIZE[1]),
        egui::Layout::left_to_right(egui::Align::Center),
        |ui| {
            ui.set_min_size(egui::vec2(92.0, VALUE_SIZE[1]));
            ui.add(egui::Label::new(label).truncate())
        },
    )
'@
Replace-Required $fw @'
    ui.strong(heading);
    ui.add_space(3.0);
    ui.spacing_mut().item_spacing.y = 2.0;
'@ @'
    if !heading.is_empty() {
        ui.label(egui::RichText::new(heading).size(10.5).strong());
        ui.add_space(1.0);
    }
    ui.spacing_mut().item_spacing.y = 0.5;
'@

$p = 'src/ui/player_panel.rs'
$pp = Join-Path $SourceRoot $p
$text = [IO.File]::ReadAllText($pp)
$attrTitle = $text.IndexOf('PLAYER ATTRIBUTES')
$attrStart = if ($attrTitle -ge 0) { $text.IndexOf('    for groups in [', $attrTitle) } else { -1 }
$positionsMarker = $text.IndexOf('// Positions & Traits', $attrStart)
$functionEnd = if ($positionsMarker -ge 0) { $text.LastIndexOf("`n}", $positionsMarker) } else { -1 }
if ($attrStart -lt 0 -or $positionsMarker -lt 0 -or $functionEnd -lt 0) {
    throw 'v2.0: player attribute grid boundaries not found'
}

$newGrid = @'
    // Element v2.0 one-page player attribute matrix. All categories remain
    // live-editable; the old second row is folded into stacked compact cards.
    ui.spacing_mut().item_spacing = egui::vec2(4.0, 2.0);
    ui.columns(6, |cols| {
        compact_player_attribute_card(schemas, &mut cols[0], "Technical", Category::Technical, &mut player.raw, addr, edits);
        cols[0].add_space(3.0);
        compact_player_attribute_card(schemas, &mut cols[0], "Set Pieces", Category::SetPieces, &mut player.raw, addr, edits);

        compact_player_attribute_card(schemas, &mut cols[1], "Mental", Category::Mental, &mut player.raw, addr, edits);
        compact_player_attribute_card(schemas, &mut cols[2], "Physical", Category::Physical, &mut player.raw, addr, edits);

        compact_player_attribute_card(schemas, &mut cols[3], "Hidden", Category::Hidden, &mut player.raw, addr, edits);
        cols[3].add_space(3.0);
        compact_player_attribute_card(schemas, &mut cols[3], "Foot Ability", Category::Footedness, &mut player.raw, addr, edits);

        compact_player_attribute_card(schemas, &mut cols[4], "Personality", Category::Personality, &mut player.raw, addr, edits);
        compact_player_attribute_card(schemas, &mut cols[5], "Goalkeeping", Category::Goalkeeping, &mut player.raw, addr, edits);
    });
'@
$text = $text.Substring(0, $attrStart) + $newGrid + $text.Substring($functionEnd)

# Add the compact card helper immediately before the Positions & Traits section.
$positionsMarker = $text.IndexOf('// Positions & Traits')
if ($positionsMarker -lt 0) { throw 'v2.0: Positions & Traits marker missing after grid rewrite' }
$sectionStart = $text.LastIndexOf('// ---------------------------------------------------------------------------', $positionsMarker)
if ($sectionStart -lt 0) { throw 'v2.0: Positions section header boundary missing' }
$helper = @'
fn compact_player_attribute_card(
    schemas: &'static crate::fields::VersionedSchemas,
    ui: &mut egui::Ui,
    heading: &str,
    category: Category,
    raw: &mut [u8],
    addr: u64,
    edits: &mut Vec<FieldEdit>,
) {
    egui::Frame::group(ui.style())
        .fill(egui::Color32::from_rgb(25, 31, 45))
        .stroke(egui::Stroke::new(1.0, egui::Color32::from_rgb(41, 49, 66)))
        .rounding(egui::Rounding::same(3))
        .inner_margin(egui::Margin::symmetric(5, 3))
        .show(ui, |ui| {
            ui.label(
                egui::RichText::new(heading)
                    .size(11.0)
                    .strong()
                    .color(egui::Color32::from_rgb(225, 232, 245)),
            );
            ui.separator();
            field_widget::category_column(
                schemas,
                ui,
                "",
                Entity::Player,
                category,
                raw,
                addr,
                edits,
            );
        });
}

'@
$text = $text.Substring(0, $sectionStart) + $helper + $text.Substring($sectionStart)
[IO.File]::WriteAllText($pp, $text, [Text.UTF8Encoding]::new($false))

Write-Host 'Element v2.0 unified global search + compact one-page player attributes applied successfully.'
