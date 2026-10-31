from pathlib import Path

root = Path.cwd()

# v4.8 adds live medical/relationship state to PlayerRecord. The cached-player
# constructor (and one UI layout test fixture) are synthetic records, so they
# should explicitly mark those live lists as unmapped instead of attempting to
# fabricate process-backed data.
app_path = root / "src" / "app.rs"
app = app_path.read_text(encoding="utf-8")
old_app = '''        nationality: None,
        birthplace: None,
    }
}

fn cached_staff_view'''
new_app = '''        nationality: None,
        birthplace: None,
        game_date: None,
        injuries: crate::player::LiveList::Unmapped,
        absences: crate::player::LiveList::Unmapped,
        relations: crate::player::LiveList::Unmapped,
    }
}

fn cached_staff_view'''
if old_app not in app:
    raise SystemExit("v4.8 compile fix: cached PlayerRecord initializer marker missing")
app = app.replace(old_app, new_app, 1)
app_path.write_text(app, encoding="utf-8")

panel_path = root / "src" / "ui" / "player_panel.rs"
panel = panel_path.read_text(encoding="utf-8")
old_test = '''                    nationality: None,
                    birthplace: None,
                };
                for field in schemas.fields_for_category'''
new_test = '''                    nationality: None,
                    birthplace: None,
                    game_date: None,
                    injuries: LiveList::Unmapped,
                    absences: LiveList::Unmapped,
                    relations: LiveList::Unmapped,
                };
                for field in schemas.fields_for_category'''
if old_test not in panel:
    raise SystemExit("v4.8 compile fix: player panel test fixture marker missing")
panel = panel.replace(old_test, new_test, 1)
panel_path.write_text(panel, encoding="utf-8")

print("Element v4.8 PlayerRecord initializer compatibility fix applied successfully.")
