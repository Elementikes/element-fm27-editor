from pathlib import Path
import base64
import subprocess
import zlib

repo = Path(__file__).resolve().parent.parent
parts = [
    repo / "patches" / "v4.7-all.part1.b64",
    repo / "patches" / "v4.7-all.part2.b64",
]
payload = "".join(path.read_text(encoding="utf-8").strip() for path in parts)
patch = zlib.decompress(base64.b64decode(payload))
temp = repo / "patches" / ".v4.7-all.generated.patch"
temp.write_bytes(patch)
print(f"==> applying Element v4.2.3 -> v4.7 generated patch ({len(patch)} bytes)")
subprocess.run(
    ["git", "apply", "--ignore-space-change", "--whitespace=nowarn", str(temp)],
    check=True,
)
temp.unlink(missing_ok=True)
print("Element generated-source stack applied through v4.7 successfully.")
