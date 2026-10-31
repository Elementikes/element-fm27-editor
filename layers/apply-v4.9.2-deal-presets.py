from pathlib import Path

path = Path.cwd() / "src" / "ui" / "pages" / "player_search.rs"
text = path.read_text(encoding="utf-8")

old = '''                9 => deal >= 65 && p.value.is_some_and(|v| v <= 20_000_000),
                10 => deal >= 72,
                11 => deal >= 90,
'''
new = '''                9 => deal >= 55
                    && (p.club_id.is_none() || p.value.is_some_and(|v| v <= 20_000_000))
                    && (p.ca >= 130 || p.pa >= 160),
                10 => deal >= 58 && (p.ca >= 145 || p.pa >= 170),
                11 => deal >= 62
                    && (element_is_elite_prospect(schemas, p)
                        || p.club_id.is_none()
                        || p.contract_days_remaining.is_some_and(|d| (0..=366).contains(&d))
                        || p.value.is_some_and(|v| v <= 30_000_000))
                    && (p.ca >= 140 || p.pa >= 175),
'''
if old not in text:
    raise SystemExit("v4.9.2: legacy deal-preset thresholds not found")
text = text.replace(old, new, 1)

text = text.replace('v4.9.1 • RECRUITMENT CLARITY', 'v4.9.2 • DEAL PRESETS CALIBRATED')
text = text.replace(
    'Recruitment Board: Player Tier measures absolute level/potential; Deal Value measures transfer value-for-money. ELITE PROSPECT uses age-adjusted PA + development headroom. Contract-window filters use live remaining days.',
    'Recruitment Board: Player Tier measures absolute level/potential; Deal Value measures transfer value-for-money. CHEAP / GOOD / MUST BUY presets are calibrated to Deal Value v3; MUST BUY also requires a concrete market trigger (elite prospect, free agent, <=12m contract or low fee).'
)

path.write_text(text, encoding="utf-8")
print("Element v4.9.2 deal preset calibration applied successfully.")
