from pathlib import Path
import runpy

here = Path(__file__).resolve().parent
try:
    runpy.run_path(str(here / 'apply-v8.15-native-offer-payload-dry-run.py'), run_name='__main__')
except UnicodeEncodeError as e:
    # v8.15 performs all source/helper mutations before its final status print.
    # Windows hosted runners can expose a cp1252 stdout that rejects the Unicode
    # arrow in that final message. Treat only that post-apply console failure as
    # non-fatal; any real patch/marker error is a different exception and bubbles.
    if 'charmap' not in str(e) and 'encode' not in str(e):
        raise
    print('Element v8.15.1 hotfix: v8.15 applied; ignored post-apply cp1252 status-print failure.')
