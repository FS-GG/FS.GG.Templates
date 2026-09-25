#!/usr/bin/env python3
"""Black-box structure controls for the live provider-floor gate."""

from pathlib import Path
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts/check-provider-floors.py"
PIN = "1.4.0-preview.1"
REGISTRY = (
    "schemaVersion: 2\ncontracts:\n  - id: fs-gg-ui-template\n"
    f"    minimum-fsgg-sdd:\n      version: \"{PIN}\"\n"
)
PROVIDER = (
    "schemaVersion: 1\nproviders:\n  - name: web\n"
    "    contractVersion: \"1.1.0\"\n    templateId: fs-gg-web\n"
    "    source: FS.GG.Web.Template::1.0.0\n"
)
FLOOR = f"    minimumFsggSdd:\n      version: \"{PIN}\"\n"
CASES = [
    ("valid descriptor", PROVIDER + FLOOR, True),
    ("missing actual provider floor", PROVIDER, False),
    ("floor moved under another root key", PROVIDER + "extra:\n" + FLOOR, False),
    ("malformed providers flow", (PROVIDER + FLOOR).replace("providers:\n", "providers: [\n", 1), False),
    ("duplicate providers root key", PROVIDER + FLOOR + "providers: []\n", False),
    ("duplicate floor mapping", PROVIDER + FLOOR + FLOOR, False),
    ("duplicate floor version", PROVIDER + FLOOR + f"      version: \"{PIN}\"\n", False),
    ("duplicate provider field", PROVIDER + "    source: Another.Template::1.0.0\n" + FLOOR, False),
]

with tempfile.TemporaryDirectory() as folder:
    temporary = Path(folder)
    (temporary / "providers").mkdir()
    registry = temporary / "registry.yml"
    registry.write_text(REGISTRY)
    failures = []
    for label, descriptor, should_pass in CASES:
        (temporary / "providers/web.providers.yml").write_text(descriptor)
        result = subprocess.run(
            ["python3", str(SCRIPT), "--providers", str(temporary / "providers"),
             "--registry", str(registry)], capture_output=True, text=True, timeout=30,
        )
        if (result.returncode == 0) != should_pass:
            failures.append(label)
            print(f"FAIL {label}: exit={result.returncode}, expected {'green' if should_pass else 'red'}")
        else:
            print(f"PASS {label}")
if failures:
    raise SystemExit(f"provider-floor-structure: {len(CASES) - len(failures)} passed, {len(failures)} false greens")
print(f"provider-floor-structure: {len(CASES)} passed")
