from pathlib import Path
import base64
import hashlib
import io
import zipfile

repo = Path(__file__).resolve().parent.parent
parts = [repo / "patches" / f"v4.8-overlay.part{i}.b64" for i in range(1, 7)]
payload = "".join(path.read_text(encoding="utf-8").strip() for path in parts)
data = base64.b64decode(payload, validate=True)
expected_sha256 = "f0c10ec1f15a4df9c5a76499b3116432ba1f1f83e91012ff8657141abd1da889"
actual_sha256 = hashlib.sha256(data).hexdigest()
if actual_sha256 != expected_sha256:
    raise SystemExit(f"v4.8 overlay checksum mismatch: {actual_sha256}")

expected_files = {
    "src/app.rs",
    "src/player.rs",
    "src/ui/club_logo.rs",
    "src/ui/club_panel.rs",
    "src/ui/player_panel.rs",
    "src/ui/pages/player_search.rs",
}

with zipfile.ZipFile(io.BytesIO(data)) as archive:
    names = {name for name in archive.namelist() if not name.endswith("/")}
    if names != expected_files:
        missing = sorted(expected_files - names)
        extra = sorted(names - expected_files)
        raise SystemExit(f"v4.8 overlay file-set mismatch; missing={missing}, extra={extra}")
    root = Path.cwd().resolve()
    for name in sorted(names):
        dest = (root / name).resolve()
        if root not in dest.parents:
            raise SystemExit(f"unsafe overlay path: {name}")
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(archive.read(name))
        print(f"v4.8 overlay: {name}")

print(f"Element v4.8 source overlay applied successfully ({actual_sha256}).")
