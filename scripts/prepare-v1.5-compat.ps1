$ErrorActionPreference = 'Stop'
$SourceRoot = (Get-Location).Path
$p = Join-Path $SourceRoot 'src/ui/player_panel.rs'
$text = [IO.File]::ReadAllText($p)

# v1.5 removes the v0.5 horizontal navigation block itself. The normal build
# pipeline already creates that canonical block before this compatibility step.
# Do not try to infer a Rust insertion boundary here: earlier generated variants
# use different tab-dispatch syntax, and a guessed insertion can place executable
# code outside the live player panel function.
$marker = '    // Element profile navigation: compact, high-contrast editor tabs.'
if ($text.Contains($marker)) {
    Write-Host 'v1.5 compatibility: canonical player navigation boundary present.'
} else {
    # Fail with useful diagnostics only when the expected v0.5 transform is
    # genuinely absent. v1.5 depends on this exact block for a safe replacement.
    $legacy = '    // Sub-tab bar'
    if ($text.Contains($legacy)) {
        throw 'v1.5 compatibility: legacy player navigation still present; v0.5 transform did not apply.'
    }
    throw 'v1.5 compatibility: canonical player navigation boundary missing after v0.5; refusing unsafe inferred insertion.'
}
