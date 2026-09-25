#!/usr/bin/env python3
"""Independent offline controls for selected NuGet archive identity and custody fields."""

from hashlib import sha256
import json
from pathlib import Path
import stat
import subprocess
import tempfile
import warnings
import zipfile

ROOT = Path(__file__).resolve().parents[2]
GATE = ROOT / "scripts/verify-svg-selected-archive.py"
HEAD = "a" * 40
MEMBER = "content/templates/fs-gg-fable-game/Asset.txt"
NUSPEC = "FS.GG.Workspace.Template.nuspec"


def nuspec(package_id="FS.GG.Workspace.Template", commit=HEAD, dtd=False):
    declaration = '<!DOCTYPE package [<!ENTITY marker "bad">]>' if dtd else ""
    return (f'{declaration}<package><metadata><id>{package_id}</id><version>0.14.0</version>'
            f'<repository type="git" commit="{commit}" /></metadata></package>').encode()


def archive(path, *, package_id="FS.GG.Workspace.Template", commit=HEAD,
            member=True, duplicate=False, symlink=False, dtd=False):
    with zipfile.ZipFile(path, "w") as package:
        rows = [(NUSPEC, nuspec(package_id, commit, dtd)), (MEMBER, b"selected bytes")]
        if not member:
            rows.pop()
        if duplicate:
            rows.append((MEMBER, b"duplicate"))
        if symlink:
            rows.append(("foreign-link", b"outside"))
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", UserWarning)
            for name, data in rows:
                info = zipfile.ZipInfo(name)
                info.create_system = 3
                info.external_attr = ((stat.S_IFLNK if name == "foreign-link" else stat.S_IFREG) | 0o644) << 16
                package.writestr(info, data)


def baseline(path, digest, *, head=HEAD, duplicate=False, ambiguous=False):
    candidate = {"version": "0.14.0", "sourceHead": head, "nativeArchiveSha256": digest}
    data = {"schema": "fsgg.svg-complete-adoption-manifest/v1", "managedPaths": ["Asset.txt"],
            "sourceCandidates": [candidate, candidate] if ambiguous else [candidate]}
    value = json.dumps(data)
    if duplicate:
        value = value.replace('"sourceCandidates":', '"sourceCandidates": [], "sourceCandidates":', 1)
    path.write_text(value, encoding="utf-8")


def run(name, *, accepted=False, expected="", archive_options=None, baseline_options=None,
        repin=True, link=False):
    archive_options = archive_options or {}
    baseline_options = baseline_options or {}
    with tempfile.TemporaryDirectory(prefix="fsc05-selected-archive-") as folder:
        folder = Path(folder)
        package = folder / "candidate.nupkg"
        manifest = folder / "baseline.json"
        archive(package, **archive_options)
        digest = sha256(package.read_bytes()).hexdigest() if repin else "0" * 64
        baseline(manifest, digest, **baseline_options)
        if link:
            alias = folder / "link.nupkg"
            alias.symlink_to(package)
            package = alias
        result = subprocess.run(["python3", str(GATE), str(package), "--manifest", str(manifest)],
                                capture_output=True, text=True)
        output = result.stdout + result.stderr
        if accepted and (result.returncode != 0 or "selected archive verified" not in output):
            raise AssertionError(f"{name}: selected package refused: {output}")
        if not accepted and (result.returncode == 0 or expected not in output):
            raise AssertionError(f"{name}: unsafe package admitted or wrong refusal: {output}")
        print(f"PASS {name}")


run("exact selected package", accepted=True)
run("other archive with same package version", expected="selected archive SHA-256 mismatch", repin=False)
run("source commit drift", expected="source commit mismatch", archive_options={"commit": "b" * 40})
run("wrong package id", expected="package id, version or source commit mismatch",
    archive_options={"package_id": "Foreign.Package"})
run("missing managed member", expected="managed archive member missing", archive_options={"member": False})
run("duplicate archive member", expected="duplicate or aliased archive member", archive_options={"duplicate": True})
run("symlink archive member", expected="nonregular archive member", archive_options={"symlink": True})
run("nuspec DTD", expected="nuspec DTD or entity unsupported", archive_options={"dtd": True})
run("duplicate baseline key", expected="duplicate baseline key", baseline_options={"duplicate": True})
run("ambiguous selected candidate", expected="selected candidate must be unique",
    baseline_options={"ambiguous": True})
run("archive path symlink", expected="archive open refused", link=True)
