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
    if (-not $Text.Contains($Old)) { throw "v3.8.2: expected source fragment not found: $Label" }
    return $Text.Replace($Old, $New)
}

# -----------------------------------------------------------------------------
# Element v3.8.2 — GLOBAL CLUB GENDER FILTER
#
# v2.0 intentionally removed all page-local search/filter rows, so the v3.8.1
# MEN/WOMEN controls existed in club_search::filter_row() but were not rendered.
# Surface the certified gender toggles in the persistent top bar whenever the
# Clubs page is active. The filter state remains owned by ClubSearchState.
# -----------------------------------------------------------------------------

$path = 'src/app.rs'
$app = Read-Text $path

$old = @'
                        if self.active_page == Page::PlayerSearch {
                            if ui.small_button("⚙").on_hover_text("Advanced player filters").clicked() && !self.advanced_open {
                                self.advanced_snapshot = Some(self.player_search.clone());
                                self.advanced_open = true;
                            }
                        }
'@

$new = @'
                        if self.active_page == Page::ClubSearch {
                            ui.separator();
                            ui.label(
                                egui::RichText::new("GENDER")
                                    .size(8.0)
                                    .strong()
                                    .color(egui::Color32::from_rgb(139, 157, 188)),
                            );
                            ui.checkbox(&mut self.club_search.men, "♂ MEN")
                                .on_hover_text("Show men's clubs in Club Search.");
                            ui.checkbox(&mut self.club_search.women, "♀ WOMEN")
                                .on_hover_text("Show women's clubs in Club Search.");
                            if !self.club_search.men && !self.club_search.women {
                                ui.label(
                                    egui::RichText::new("NONE")
                                        .size(8.0)
                                        .strong()
                                        .color(ui.visuals().warn_fg_color),
                                )
                                .on_hover_text("Enable MEN and/or WOMEN to show club results.");
                            }
                        } else if self.active_page == Page::PlayerSearch {
                            if ui.small_button("⚙").on_hover_text("Advanced player filters").clicked() && !self.advanced_open {
                                self.advanced_snapshot = Some(self.player_search.clone());
                                self.advanced_open = true;
                            }
                        }
'@

$app = Replace-Required $app $old $new 'global search trailing controls'
Write-Text $path $app

Write-Host 'Element v3.8.2 global MEN / WOMEN Club Search controls applied successfully.'
