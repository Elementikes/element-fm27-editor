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

# -----------------------------------------------------------------------------
# Element v2.7 — TACTICAL KNOWLEDGE ENGINE CORE
#
# This pass turns the v2.6 tactical specification into compiled engine guards
# and a live validation dashboard. It intentionally does NOT guess the missing
# FM27 player-training pointer chain or cache-refresh address. The actual write
# button remains locked until those two ownership paths are available and can
# be read back safely on the supported game build.
#
# Confirmed external/public FM27 research used as specification only:
#   * six learned-instruction collections
#   * instruction knowledge is a 14-bit value
#   * formation/role row knowledge is a u16 at row +14
#   * 10,000 represents 100%
#   * existing entries only; keys and ownership links must be preserved
# -----------------------------------------------------------------------------

$c = 'src/ui/club_panel.rs'
$clubText = Read-Text $c
$tuStart = $clubText.IndexOf('fn show_tactical_understanding(')
$lockedStart = $clubText.IndexOf('fn locked_notice(', $tuStart)
if ($tuStart -lt 0 -or $lockedStart -lt 0) {
    throw 'v2.7: tactical-understanding boundaries not found'
}

$newTacticalEngine = @'
const ELEMENT_TACTICAL_MAX_KNOWLEDGE: u16 = 10_000;
const ELEMENT_TACTICAL_INSTRUCTION_COLLECTIONS: usize = 6;
const ELEMENT_TACTICAL_FORMATION_VALUE_OFFSET: usize = 14;

fn element_tactical_percent(value: u16) -> f32 {
    (value.min(ELEMENT_TACTICAL_MAX_KNOWLEDGE) as f32
        / ELEMENT_TACTICAL_MAX_KNOWLEDGE as f32)
        .clamp(0.0, 1.0)
}

fn element_tactical_row_value_bytes(value: u16) -> [u8; 2] {
    value.min(ELEMENT_TACTICAL_MAX_KNOWLEDGE).to_le_bytes()
}

fn element_tactical_pointer_ok(addr: Option<u64>) -> bool {
    addr.is_some_and(crate::player::is_valid_ptr)
}

fn element_tactical_status(
    ui: &mut egui::Ui,
    label: &str,
    ok: bool,
    ready_text: &str,
    blocked_text: &str,
) {
    ui.horizontal(|ui| {
        ui.add_sized([150.0, 17.0], egui::Label::new(egui::RichText::new(label).size(8.5)));
        let (text, color) = if ok {
            (ready_text, egui::Color32::from_rgb(72, 210, 132))
        } else {
            (blocked_text, egui::Color32::from_rgb(255, 184, 77))
        };
        ui.label(egui::RichText::new(text).size(8.5).strong().color(color));
    });
}

fn show_tactical_understanding(ui: &mut egui::Ui, club: &ClubView) {
    ui.spacing_mut().item_spacing = egui::vec2(6.0, 3.0);

    let club_ptr_ok = crate::player::is_valid_ptr(club.addr);
    let senior_team_ok = element_tactical_pointer_ok(club.senior_team_addr);
    let target_bytes = element_tactical_row_value_bytes(ELEMENT_TACTICAL_MAX_KNOWLEDGE);
    let target_percent = element_tactical_percent(ELEMENT_TACTICAL_MAX_KNOWLEDGE) * 100.0;

    ui.horizontal(|ui| {
        ui.label(egui::RichText::new("TACTICAL KNOWLEDGE ENGINE").size(13.0).strong());
        ui.separator();
        ui.label(
            egui::RichText::new("v2.7 • VALIDATION FIRST")
                .size(8.0)
                .strong()
                .color(egui::Color32::from_rgb(112, 177, 255)),
        );
    });
    ui.label(
        egui::RichText::new(
            "The 100% mutation rules are compiled into Element. Live writes stay gated until the player-training ownership chain and FM knowledge-cache refresh record are ported and verified; no guessed offsets are used.",
        )
        .size(8.5)
        .color(egui::Color32::from_rgb(154, 169, 194)),
    );
    ui.add_space(4.0);

    ui.horizontal(|ui| {
        ui.selectable_label(true, format!("{} • First Team", club.short_name));
        ui.add_enabled(false, egui::Button::new("All Club Squads"));
        ui.add_enabled(false, egui::Button::new("Selected Players"));
    });
    ui.add_space(4.0);

    ui.columns(3, |cols| {
        egui::Frame::group(cols[0].style())
            .fill(egui::Color32::from_rgb(25, 31, 45))
            .stroke(egui::Stroke::new(1.0, egui::Color32::from_rgb(41, 49, 66)))
            .rounding(egui::Rounding::same(4))
            .inner_margin(egui::Margin::symmetric(7, 5))
            .show(&mut cols[0], |ui| {
                ui.label(egui::RichText::new("ENGINE SPEC").size(9.0).strong());
                ui.separator();
                field_widget::info_label(ui, "Instruction collections", ELEMENT_TACTICAL_INSTRUCTION_COLLECTIONS);
                field_widget::info_label(ui, "Instruction value width", "14-bit");
                field_widget::info_label(ui, "Formation/role value", "u16 @ row +14");
                field_widget::info_label(ui, "100% value", ELEMENT_TACTICAL_MAX_KNOWLEDGE);
                field_widget::info_label(ui, "100% bytes (LE)", format!("{:02X} {:02X}", target_bytes[0], target_bytes[1]));
                field_widget::info_label(ui, "Preview", format!("{target_percent:.0}%"));
            });

        egui::Frame::group(cols[1].style())
            .fill(egui::Color32::from_rgb(25, 31, 45))
            .stroke(egui::Stroke::new(1.0, egui::Color32::from_rgb(41, 49, 66)))
            .rounding(egui::Rounding::same(4))
            .inner_margin(egui::Margin::symmetric(7, 5))
            .show(&mut cols[1], |ui| {
                ui.label(egui::RichText::new("LIVE ROOT CHECK").size(9.0).strong());
                ui.separator();
                element_tactical_status(ui, "Club object", club_ptr_ok, "AVAILABLE", "INVALID");
                element_tactical_status(ui, "Senior team object", senior_team_ok, "AVAILABLE", "UNAVAILABLE");
                element_tactical_status(ui, "Instruction format", true, "SPEC READY", "BLOCKED");
                element_tactical_status(ui, "Formation row +14", true, "SPEC READY", "BLOCKED");
                element_tactical_status(ui, "Player-training chain", false, "READY", "NOT PORTED");
                element_tactical_status(ui, "Knowledge-cache refresh", false, "READY", "NOT PORTED");
            });

        egui::Frame::group(cols[2].style())
            .fill(egui::Color32::from_rgb(25, 31, 45))
            .stroke(egui::Stroke::new(1.0, egui::Color32::from_rgb(41, 49, 66)))
            .rounding(egui::Rounding::same(4))
            .inner_margin(egui::Margin::symmetric(7, 5))
            .show(&mut cols[2], |ui| {
                ui.label(egui::RichText::new("WRITE CONTRACT").size(9.0).strong());
                ui.separator();
                ui.label(egui::RichText::new("1. Read every existing learned entry").size(8.3));
                ui.label(egui::RichText::new("2. Validate ownership + bounds").size(8.3));
                ui.label(egui::RichText::new("3. Preserve instruction/formation keys").size(8.3));
                ui.label(egui::RichText::new("4. Stage old/new bytes for Undo").size(8.3));
                ui.label(egui::RichText::new("5. Write all entries or reject batch").size(8.3));
                ui.label(egui::RichText::new("6. Refresh FM knowledge cache").size(8.3));
                ui.label(egui::RichText::new("7. Read back every changed record").size(8.3));
            });
    });

    ui.add_space(5.0);
    egui::Frame::group(ui.style())
        .fill(egui::Color32::from_rgb(20, 25, 36))
        .stroke(egui::Stroke::new(1.0, egui::Color32::from_rgb(53, 61, 78)))
        .rounding(egui::Rounding::same(4))
        .inner_margin(egui::Margin::symmetric(7, 5))
        .show(ui, |ui| {
            let preview_id = egui::Id::new(("element_tactical_batch_preview", club.addr));
            let mut preview = ui.data_mut(|d| d.get_temp::<bool>(preview_id).unwrap_or(false));
            ui.horizontal(|ui| {
                if ui.checkbox(&mut preview, "100% batch preview").changed() {
                    ui.data_mut(|d| d.insert_temp(preview_id, preview));
                }
                ui.separator();
                ui.add_enabled(false, egui::Button::new("Apply Full Tactical Knowledge (100%)"))
                    .on_disabled_hover_text("Unavailable for this FM27 build until the player-training chain and cache-refresh record are verified in Element.");
                ui.label(
                    egui::RichText::new("WRITE LOCK ACTIVE")
                        .size(8.0)
                        .strong()
                        .color(egui::Color32::from_rgb(255, 184, 77)),
                );
            });
            if preview {
                ui.add_space(3.0);
                egui::Grid::new("element_tactical_preview_v27")
                    .num_columns(3)
                    .spacing([14.0, 3.0])
                    .striped(true)
                    .show(ui, |ui| {
                        for h in ["Record group", "Target", "Safety rule"] {
                            ui.label(egui::RichText::new(h).size(8.0).strong());
                        }
                        ui.end_row();
                        ui.label("6 learned-instruction collections");
                        ui.label("10,000 / 100%");
                        ui.label("Existing entries only; preserve keys");
                        ui.end_row();
                        ui.label("Formation / role familiarity rows");
                        ui.label("u16 10,000 @ +14");
                        ui.label("Preserve ownership links");
                        ui.end_row();
                        ui.label("Knowledge cache");
                        ui.label("Refresh after batch");
                        ui.label("Required before success/read-back");
                        ui.end_row();
                    });
            }
        });

    ui.add_space(4.0);
    ui.label(
        egui::RichText::new(
            "Element will not substitute staff Tactical Knowledge, player CA/PA, Player Buy-In or team cohesion for this feature. Those are separate values. This engine targets learned tactical familiarity only.",
        )
        .size(8.0)
        .color(egui::Color32::from_rgb(154, 169, 194)),
    );
}

#[cfg(test)]
mod element_tactical_engine_tests {
    use super::{
        element_tactical_percent, element_tactical_row_value_bytes,
        ELEMENT_TACTICAL_MAX_KNOWLEDGE,
    };

    #[test]
    fn tactical_max_is_exactly_one_hundred_percent() {
        assert_eq!(element_tactical_percent(ELEMENT_TACTICAL_MAX_KNOWLEDGE), 1.0);
        assert_eq!(element_tactical_percent(0), 0.0);
    }

    #[test]
    fn tactical_formation_value_is_little_endian_u16() {
        assert_eq!(element_tactical_row_value_bytes(10_000), [0x10, 0x27]);
    }

    #[test]
    fn tactical_preview_clamps_above_valid_max() {
        assert_eq!(element_tactical_percent(u16::MAX), 1.0);
        assert_eq!(element_tactical_row_value_bytes(u16::MAX), [0x10, 0x27]);
    }
}

'@

$clubText = $clubText.Substring(0, $tuStart) + $newTacticalEngine + $clubText.Substring($lockedStart)
Write-Text $c $clubText
Write-Host 'v2.7: tactical knowledge engine guards + live validation dashboard applied'

# Keep the contextual rail wording aligned with the feature name.
$a = 'src/app.rs'
$appText = Read-Text $a
$appText = $appText.Replace('⚙  Tactical Understanding', '⚙  Tactical Knowledge')
Write-Text $a $appText

# Add a concise status note to the generated roadmap without duplicating it.
$roadmap = 'ELEMENT_ROADMAP.md'
$roadmapPath = Join-Path $SourceRoot $roadmap
if (Test-Path -LiteralPath $roadmapPath) {
    $roadmapText = [IO.File]::ReadAllText($roadmapPath)
    if (-not $roadmapText.Contains('v2.7 tactical engine core')) {
        $roadmapText += @'

## v2.7 tactical engine core
- Compiled FM27 tactical-knowledge invariants: 6 learned-instruction collections, 14-bit instruction knowledge, formation/role u16 at row +14, 10,000 = 100%.
- Added live club/senior-team root validation and exact all-or-nothing write contract.
- Full Tactical Knowledge remains write-locked until the player-training ownership chain and knowledge-cache refresh record are ported and read-back validated. No guessed pointer writes.
'@
        [IO.File]::WriteAllText($roadmapPath, $roadmapText, [Text.UTF8Encoding]::new($false))
    }
}

Write-Host 'Element v2.7 tactical knowledge engine core applied successfully.'
