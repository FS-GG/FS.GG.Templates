#!/usr/bin/env python3
"""Execute both release.yml readback snippets against mode-only ZIP mutations."""

from pathlib import Path
import json
import re
import stat
import subprocess
import tempfile
import textwrap
import zipfile

ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = (ROOT / ".github/workflows/release.yml").read_text(encoding="utf-8")
MEMBER = "content/templates/fs-gg-fable-game/build.sh"


def snippet(step: str) -> str:
    marker = f"      - name: Read back {step} payload\n"
    if WORKFLOW.count(marker) != 1:
        raise AssertionError(f"expected one release step named {step!r}")
    section = WORKFLOW.split(marker, 1)[1].split("\n      - name:", 1)[0]
    matched = re.search(r"python3 - .*? <<'PY'\n(.*?)\n          PY", section, re.S)
    if not matched:
        raise AssertionError(f"{step}: inline Python readback not found")
    return textwrap.dedent(matched.group(1))


def make_archive(path: Path, mode: int, *, signed=False) -> None:
    with zipfile.ZipFile(path, "w") as archive:
        info = zipfile.ZipInfo(MEMBER)
        info.create_system = 3
        info.external_attr = (stat.S_IFREG | mode) << 16
        archive.writestr(info, b"#!/bin/sh\n")
        if signed:
            signature = zipfile.ZipInfo(".signature.p7s")
            signature.create_system = 3
            signature.external_attr = (stat.S_IFREG | 0o644) << 16
            archive.writestr(signature, b"synthetic signature")


def run_block(code: str, local: Path, remote: Path, feed: str, folder: Path):
    (folder / "artifacts").mkdir(exist_ok=True)
    return subprocess.run(["python3", "-", str(local), str(remote), feed], input=code,
                          text=True, capture_output=True, cwd=folder)


with tempfile.TemporaryDirectory(prefix="fsc05-release-modes-") as folder_name:
    folder = Path(folder_name)
    local = folder / "release.nupkg"
    same = folder / "same.nupkg"
    changed = folder / "changed-mode.nupkg"
    signed_same = folder / "signed-same.nupkg"
    signed_changed = folder / "signed-changed-mode.nupkg"
    make_archive(local, 0o644)
    make_archive(same, 0o644)
    make_archive(changed, 0o755)
    make_archive(signed_same, 0o644, signed=True)
    make_archive(signed_changed, 0o755, signed=True)

    failures = []
    for step, feed, good, bad, receipt in [
        ("GitHub Packages", "github-packages", same, changed, "github-packages-readback.json"),
        ("nuget.org", "nuget.org", signed_same, signed_changed, "nuget-org-readback.json"),
    ]:
        code = snippet(step)
        accepted = run_block(code, local, good, feed, folder)
        if accepted.returncode != 0:
            failures.append(f"{step}: equal payload refused: {accepted.stderr}")
            continue
        value = json.loads((folder / "artifacts" / receipt).read_text())
        if value.get("payloadExact") is not True or value.get("payloadModeExact") is not True:
            failures.append(f"{step}: receipt did not record exact modes: {value}")
        (folder / "artifacts" / receipt).unlink()
        rejected = run_block(code, local, bad, feed, folder)
        if rejected.returncode == 0 or "mode" not in rejected.stderr.lower():
            failures.append(f"{step}: mode-only drift admitted: exit={rejected.returncode}, "
                            f"stderr={rejected.stderr!r}")
        if (folder / "artifacts" / receipt).exists():
            failures.append(f"{step}: mode-only drift wrote a success receipt")
        print(f"CHECK {step}: good={accepted.returncode}, mode-drift={rejected.returncode}")
    if failures:
        raise AssertionError("\n".join(failures))
    print("PASS both release readbacks bind member bytes and Unix modes")
