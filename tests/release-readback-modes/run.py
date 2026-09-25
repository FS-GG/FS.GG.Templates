#!/usr/bin/env python3
"""Execute both release.yml readbacks against mode and ZIP-name aliases."""

from pathlib import Path
import json
import re
import stat
import subprocess
import tempfile
import textwrap
import warnings
import zipfile

ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = (ROOT / ".github/workflows/release.yml").read_text(encoding="utf-8")
MEMBER = "content/templates/fs-gg-fable-game/build.sh"

if "\n  gate:\n" not in WORKFLOW or "\n  publish:\n" not in WORKFLOW:
    raise AssertionError("release gate or publish job missing")
gate_job = WORKFLOW.split("\n  gate:\n", 1)[1].split("\n  publish:\n", 1)[0]
preflight = "      - name: Preflight feed readback members\n        run: python3 tests/release-readback-modes/run.py"
setup = "      - uses: actions/setup-dotnet@v6"
if gate_job.count(preflight) != 1 or setup not in gate_job or gate_job.index(preflight) > gate_job.index(setup):
    raise AssertionError("readback preflight must run once before costly release-gate setup")
if "needs: [route, pack, gate]" not in WORKFLOW.split("\n  publish:\n", 1)[1]:
    raise AssertionError("publish must still depend on the release gate")


def snippet(step: str) -> str:
    marker = f"      - name: Read back {step} payload\n"
    if WORKFLOW.count(marker) != 1:
        raise AssertionError(f"expected one release step named {step!r}")
    section = WORKFLOW.split(marker, 1)[1].split("\n      - name:", 1)[0]
    matched = re.search(r"python3 - .*? <<'PY'\n(.*?)\n          PY", section, re.S)
    if not matched:
        raise AssertionError(f"{step}: inline Python readback not found")
    return textwrap.dedent(matched.group(1))


def make_archive(path: Path, mode: int, *, signed=False, alias=None) -> None:
    with zipfile.ZipFile(path, "w") as archive, warnings.catch_warnings():
        warnings.simplefilter("ignore", UserWarning)
        info = zipfile.ZipInfo(MEMBER)
        info.create_system = 3
        info.external_attr = (stat.S_IFREG | mode) << 16
        archive.writestr(info, b"#!/bin/sh\n")
        if alias in {"duplicate", "case"}:
            extra = zipfile.ZipInfo(MEMBER if alias == "duplicate" else MEMBER.replace("build.sh", "BUILD.sh"))
            extra.create_system = 3
            extra.external_attr = (stat.S_IFREG | mode) << 16
            archive.writestr(extra, b"#!/bin/sh\n")
        if signed:
            signature = zipfile.ZipInfo(".signature.p7s")
            signature.create_system = 3
            signature.external_attr = (stat.S_IFREG | 0o644) << 16
            archive.writestr(signature, b"synthetic signature")
            if alias == "signature-duplicate":
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
        for alias in (["duplicate", "case", "signature-duplicate"] if feed == "nuget.org"
                      else ["duplicate", "case"]):
            alias_local = folder / f"{feed}-{alias}-local.nupkg"
            alias_remote = folder / f"{feed}-{alias}-remote.nupkg"
            make_archive(alias_local, 0o644, alias=alias if alias != "signature-duplicate" else None)
            make_archive(alias_remote, 0o644, signed=feed == "nuget.org", alias=alias)
            alias_result = run_block(code, alias_local, alias_remote, feed, folder)
            if alias_result.returncode == 0 or "duplicate or case-alias" not in alias_result.stderr:
                failures.append(f"{step}: {alias} admitted or wrong refusal: "
                                f"exit={alias_result.returncode}, stderr={alias_result.stderr!r}")
            if (folder / "artifacts" / receipt).exists():
                failures.append(f"{step}: {alias} wrote a success receipt")
                (folder / "artifacts" / receipt).unlink()
            print(f"CHECK {step}: {alias}={alias_result.returncode}")
        print(f"CHECK {step}: good={accepted.returncode}, mode-drift={rejected.returncode}")
    if failures:
        raise AssertionError("\n".join(failures))
    print("PASS both release readbacks bind member names, bytes and Unix modes")
