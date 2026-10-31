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
    if (-not $Text.Contains($Old)) { throw "v3.8.1: expected source fragment not found: $Label" }
    return $Text.Replace($Old, $New)
}

# -----------------------------------------------------------------------------
# Element v3.8.1 — MEN / WOMEN CLUB FILTER
#
# FM27 club gender is already certified in the cache: 0 = men, 1 = women.
# Replace the legacy one-way "Female" checkbox with two explicit independent
# visibility toggles. Both are enabled by default, so existing search behavior
# remains unchanged until the user filters by gender.
# -----------------------------------------------------------------------------

$path = 'src/ui/pages/club_search.rs'
$ui = Read-Text $path

$oldState = @'
#[derive(Default)]
pub struct ClubSearchState {
    pub query: String,
    pub female: bool,
}
'@
$newState = @'
pub struct ClubSearchState {
    pub query: String,
    pub men: bool,
    pub women: bool,
}

impl Default for ClubSearchState {
    fn default() -> Self {
        Self {
            query: String::new(),
            men: true,
            women: true,
        }
    }
}
'@
$ui = Replace-Required $ui $oldState $newState 'ClubSearchState gender toggles'

$oldFilter = @'
            if state.female && club.gender != 1 {
                return false;
            }
'@
$newFilter = @'
            match club.gender {
                0 if !state.men => return false,
                1 if !state.women => return false,
                0 | 1 => {}
                // FM27's certified gender field is binary. Hide unexpected
                // values rather than silently assigning them to either team.
                _ => return false,
            }
'@
$ui = Replace-Required $ui $oldFilter $newFilter 'gender filter logic'

$oldToolbar = @'
    ui.horizontal_wrapped(|ui| {
        ui.checkbox(&mut state.female, "Female")
            .on_hover_text("Only female clubs; unchecked includes all clubs.");
        if ui
            .button("Reset all")
            .on_hover_text("Clear every club filter.")
            .clicked()
        {
            state.reset();
        }
    });
'@
$newToolbar = @'
    ui.horizontal_wrapped(|ui| {
        ui.label(egui::RichText::new("GENDER").small().strong().weak());
        ui.checkbox(&mut state.men, "♂ MEN")
            .on_hover_text("Show men's clubs. Disable to hide MEN teams from Club Search.");
        ui.checkbox(&mut state.women, "♀ WOMEN")
            .on_hover_text("Show women's clubs. Disable to hide WOMEN teams from Club Search.");
        if !state.men && !state.women {
            ui.label(
                egui::RichText::new("No gender selected")
                    .small()
                    .color(ui.visuals().warn_fg_color),
            );
        }
        if ui
            .button("Reset all")
            .on_hover_text("Clear search and restore MEN + WOMEN.")
            .clicked()
        {
            state.reset();
        }
    });
'@
$ui = Replace-Required $ui $oldToolbar $newToolbar 'club gender toolbar'

$oldTest = @'
        state.query = " 12 ".into();
        assert_eq!(filter(&clubs, &state).len(), 1);
        state.female = true;
        assert!(filter(&clubs, &state).is_empty());
'@
$newTest = @'
        state.query = " 12 ".into();
        assert_eq!(filter(&clubs, &state).len(), 1);
        state.men = false;
        state.women = true;
        assert!(filter(&clubs, &state).is_empty());
'@
$ui = Replace-Required $ui $oldTest $newTest 'existing gender filter test'

$oldReset = @'
        let mut state = ClubSearchState {
            query: "12".into(),
            female: true,
        };
        state.reset();
        assert!(state.query.is_empty());
        assert!(!state.female);
'@
$newReset = @'
        let mut state = ClubSearchState {
            query: "12".into(),
            men: false,
            women: false,
        };
        state.reset();
        assert!(state.query.is_empty());
        assert!(state.men);
        assert!(state.women);
'@
$ui = Replace-Required $ui $oldReset $newReset 'reset gender defaults test'

$testAnchor = @'
    #[test]
    fn reset_clears_all_filters() {
'@
$newGenderTest = @'
    #[test]
    fn men_and_women_can_be_filtered_independently() {
        let mut men = club(1, 12, "Barcelona", Some(100));
        men.gender = 0;
        let mut women = club(2, 13, "Barcelona Women", Some(100));
        women.gender = 1;
        let clubs = [men, women];

        let mut state = ClubSearchState::default();
        assert_eq!(filter(&clubs, &state).len(), 2);

        state.women = false;
        assert_eq!(filter(&clubs, &state).iter().map(|c| c.uid).collect::<Vec<_>>(), [12]);

        state.men = false;
        state.women = true;
        assert_eq!(filter(&clubs, &state).iter().map(|c| c.uid).collect::<Vec<_>>(), [13]);

        state.women = false;
        assert!(filter(&clubs, &state).is_empty());
    }

    #[test]
    fn reset_clears_all_filters() {
'@
$ui = Replace-Required $ui $testAnchor $newGenderTest 'independent gender test insertion'

Write-Text $path $ui
Write-Host 'Element v3.8.1 MEN / WOMEN Club Search filter applied successfully.'
