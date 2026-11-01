from pathlib import Path
import runpy

here = Path(__file__).resolve().parent
patches = [
    'apply-v7.0-full-core.py',
    'apply-v7.0.1-compile-hotfix.py',
    'apply-v7.1-squad-power-tools.py',
    'apply-v7.2-player-power-tools.py',
    'apply-v7.3-force-buy.py',
    'apply-v7.4-data-hub.py',
    'apply-v7.4.1-data-hub-compile-hotfix.py',
    'apply-v7.4.3-data-hub-final-hotfix.py',
    'apply-v7.4.2-club-show-compat.py',
    'apply-v7.5-club-squads.py',
    'apply-v7.5.1-squads-compile-hotfix.py',
    'apply-v7.6-staff-power-tools.py',
    'apply-v7.7-club-power-tools.py',
    'apply-v7.7.1-club-power-compile-hotfix.py',
    'apply-v7.8-fmrte-premium-ui.py',
    'apply-v7.9-fmrte-player-surfaces.py',
    'apply-v7.9.1-relationships-borrow-hotfix.py',
    'apply-v8.0-fmrte-club-tactical.py',
    'apply-v8.1a-swap-navigation.py',
    'apply-v8.1b1-player-core.py',
    'apply-v8.1b2-player-extras.py',
    'apply-v8.1c-staff-club-surfaces.py',
    'apply-v8.1d-app-routing.py',
    'apply-v8.1.1-field-ref-hotfix.py',
    'apply-v8.2-full-write-engine.py',
    'apply-v8.2.1-club-schema-hotfix.py',
    'apply-v8.3-ai-transfer-relations.py',
    'apply-v8.4-native-offer-relations-pro.py',
    'apply-v8.4.1-relations-pro-hotfix.py',
    'apply-v8.4.2-embed-native-helper.py',
    'apply-v8.4.4-native-offer-inspector-ui.py',
    'apply-v8.5-native-transfer-event-mapper.py',
    'apply-v8.6-native-offer-payload-blueprint.py',
    'apply-v8.6.1-worker-probe-shape.py',
    'apply-v8.7-index-interop-certifier.py',
    'apply-v8.7.1-helper-resolver-hotfix.py',
    'apply-v8.8-native-offer-known-id-map.py',
]

for name in patches:
    print(f'=== APPLY {name} ===', flush=True)
    runpy.run_path(str(here / name), run_name='__main__')

print('Element v8.8 full stack applied.', flush=True)
