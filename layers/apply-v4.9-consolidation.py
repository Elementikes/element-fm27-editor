from pathlib import Path
import base64
import hashlib
import subprocess
import zlib

repo = Path(__file__).resolve().parent.parent

patch_payload = (repo / "patches" / "v4.9-consolidation.b64").read_text(encoding="utf-8").strip()
patch = zlib.decompress(base64.b64decode(patch_payload, validate=True))
patch_expected = "1ed3a18b33391a3ac21655a94bcb81232e1029e68b9737105b6cb87171c03807"
patch_actual = hashlib.sha256(patch).hexdigest()
if patch_actual != patch_expected:
    raise SystemExit(f"v4.9 patch checksum mismatch: {patch_actual}")

temp = repo / "patches" / ".v4.9-consolidation.generated.patch"
temp.write_bytes(patch)
print(f"==> applying Element v4.9 mapping consolidation ({len(patch)} bytes)")
subprocess.run(["git", "apply", "--ignore-space-change", "--whitespace=nowarn", str(temp)], check=True)
temp.unlink(missing_ok=True)

logo_payload = (repo / "patches" / "v4.9-club-logo.b64").read_text(encoding="utf-8").strip()
logo = zlib.decompress(base64.b64decode(logo_payload, validate=True))
logo_expected = "5b4e83efe74a35ac6fc544cedce196784b4770be51e6fca0d3c7fc39f3bf2079"
logo_actual = hashlib.sha256(logo).hexdigest()
if logo_actual != logo_expected:
    raise SystemExit(f"v4.9 club-logo checksum mismatch: {logo_actual}")
Path("src/ui/club_logo.rs").write_bytes(logo)

for layer_name in [
    "apply-v4.9.1-recruitment-clarity.py",
    "apply-v4.9.2-deal-presets.py",
]:
    layer = repo / "layers" / layer_name
    if not layer.is_file():
        raise SystemExit(f"release layer missing: {layer}")
    subprocess.run(["python", str(layer)], check=True)

print("Element v4.9.2 mapping consolidation + recruitment clarity + calibrated deal presets + async crest indexer applied successfully.")
