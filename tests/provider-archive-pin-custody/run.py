#!/usr/bin/env python3
"""Disposable proof that floor-green does not establish selected archive provider parity."""

from hashlib import sha256
import json
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
from zipfile import ZIP_DEFLATED, ZipFile
from zipfile import ZipInfo

from check import OWNER_FILES, assess, strict_json

ROOT = Path(__file__).resolve().parents[2]
PROJECT = ROOT / "src/FS.GG.Templates.ProviderTool/FS.GG.Templates.ProviderTool.fsproj"
CHECKER = ROOT / "scripts/check-provider-floors.py"
PIN = "1.4.0-preview.1"
VERSION = "0.14.0"


def package_baseline(path: Path) -> dict:
    return {"sourceCandidates": [{"version": VERSION,
                                   "nativeArchiveSha256": sha256(path.read_bytes()).hexdigest()}]}


def package(path: Path, duplicate_game: bool = False) -> dict:
    with ZipFile(path, "w", ZIP_DEFLATED) as archive:
        archive.writestr("FS.GG.Workspace.Template.nuspec", "<package><metadata>"
                         "<id>FS.GG.Workspace.Template</id><version>0.14.0</version>"
                         "</metadata></package>")
        for owner in OWNER_FILES:
            template_id = f"fs-gg-{owner}"
            archive.writestr(f"content/templates/{template_id}/.template.config/template.json",
                             json.dumps({"shortName": template_id}))
        if duplicate_game:
            archive.writestr("content/templates/game-legacy/.template.config/template.json",
                             json.dumps({"shortName": "fs-gg-fable-game"}))
    return package_baseline(path)


with tempfile.TemporaryDirectory(prefix="fsc05-provider-archive-") as folder:
    work = Path(folder)
    providers = work / "providers"
    shutil.copytree(ROOT / "providers", providers)
    registry = work / "registry.yml"
    registry.write_text("contracts:\n  - id: fs-gg-ui-template\n"
                        f"    minimum-fsgg-sdd:\n      version: \"{PIN}\"\n", encoding="utf-8")
    subprocess.run(["dotnet", "build", str(PROJECT), "-c", "Release", "--nologo"],
                   check=True, capture_output=True, text=True)
    commands = [
        ["dotnet", "run", "--no-build", "-c", "Release", "--project", str(PROJECT),
         "--", "grade", "--providers", str(providers), "--registry", str(registry)],
        ["python3", str(CHECKER), "--providers", str(providers), "--registry", str(registry)],
    ]
    for command in commands:
        result = subprocess.run(command, capture_output=True, text=True)
        if result.returncode != 0:
            raise AssertionError(f"floor gate did not reproduce green: {result.stderr[-900:]!r}")
    print("PASS red-before boundary: both floor grades are green on mixed package pins")

    archive = work / "FS.GG.Workspace.Template.0.14.0.nupkg"
    baseline = package(archive)
    status, reasons = assess(archive, baseline, providers)
    if status != "NO_VERDICT" or sum("source pin" in reason for reason in reasons) != 3:
        raise AssertionError(f"mixed live pins produced false source match: {status}, {reasons}")
    print("PASS selected-version mismatch: three owner pins remain at 0.13.0")

    for owner in ("console", "fable-bindings", "web"):
        path = providers / OWNER_FILES[owner]
        text = path.read_text(encoding="utf-8")
        revised, count = re.subn(r"(?m)^    source: FS\.GG\.Workspace\.Template::0\.13\.0$",
                                 "    source: FS.GG.Workspace.Template::0.14.0", text)
        assert count == 1
        path.write_text(revised, encoding="utf-8")
    status, reasons = assess(archive, baseline, providers)
    if status != "PIN_ROSTER_MATCH_ONLY" or reasons:
        raise AssertionError(f"matching synthetic pin/roster was refused: {status}, {reasons}")
    print("PASS synthetic pin/roster match: source-only label, no installed claim")

    malformed = providers / OWNER_FILES["console"]
    clean = malformed.read_text(encoding="utf-8")
    malformed.write_text(clean.replace("source: FS.GG.Workspace.Template::0.14.0",
                                       "source: FS.GG.Workspace.Template::0.14.0 foreign: yes"),
                         encoding="utf-8")
    status, reasons = assess(archive, baseline, providers)
    if status != "NO_VERDICT" or "console provider identity/source is ambiguous" not in reasons:
        raise AssertionError(f"foreign source tail was admitted: {status}, {reasons}")
    malformed.write_text(clean, encoding="utf-8")
    print("PASS foreign descriptor source tail: NO_VERDICT")

    altered = {"sourceCandidates": [{"version": VERSION,
                                      "nativeArchiveSha256": "0" * 64}]}
    status, reasons = assess(archive, altered, providers)
    if status != "NO_VERDICT" or reasons != ["selected archive SHA mismatch"]:
        raise AssertionError(f"wrong SHA was admitted: {status}, {reasons}")
    print("PASS wrong selected archive SHA: NO_VERDICT")

    colliding = work / "colliding.nupkg"
    colliding_baseline = package(colliding, duplicate_game=True)
    status, reasons = assess(colliding, colliding_baseline, providers)
    if status != "NO_VERDICT" or not any("fable-game template shortName" in reason for reason in reasons):
        raise AssertionError(f"ambiguous shortName was admitted: {status}, {reasons}")
    print("PASS duplicate template shortName: NO_VERDICT")

    unsafe = work / "unsafe.nupkg"
    with ZipFile(archive) as original, ZipFile(unsafe, "w", ZIP_DEFLATED) as changed:
        for member in original.infolist():
            changed.writestr(member, original.read(member))
        changed.writestr("content/templates/../escape.txt", "foreign")
    unsafe_baseline = package_baseline(unsafe)
    status, reasons = assess(unsafe, unsafe_baseline, providers)
    if status != "NO_VERDICT" or reasons != ["archive member path or type is unsafe"]:
        raise AssertionError(f"parent member was admitted: {status}, {reasons}")
    print("PASS unsafe archive path: NO_VERDICT")

    linked = work / "linked.nupkg"
    with ZipFile(archive) as original, ZipFile(linked, "w", ZIP_DEFLATED) as changed:
        for member in original.infolist():
            changed.writestr(member, original.read(member))
        symlink = ZipInfo("content/templates/link")
        symlink.create_system = 3
        symlink.external_attr = 0o120777 << 16
        changed.writestr(symlink, "outside")
    status, reasons = assess(linked, package_baseline(linked), providers)
    if status != "NO_VERDICT" or reasons != ["archive member path or type is unsafe"]:
        raise AssertionError(f"symlink member was admitted: {status}, {reasons}")
    print("PASS symlink archive member: NO_VERDICT")

    repeated_identity = work / "repeated-identity.nupkg"
    with ZipFile(archive) as original, ZipFile(repeated_identity, "w", ZIP_DEFLATED) as changed:
        for member in original.infolist():
            body = original.read(member)
            if member.filename.endswith(".nuspec"):
                body = body.replace(b"</metadata>", b"<version>0.14.0</version></metadata>")
            changed.writestr(member, body)
    status, reasons = assess(repeated_identity, package_baseline(repeated_identity), providers)
    if status != "NO_VERDICT" or reasons != ["package identity/version differs from selected candidate"]:
        raise AssertionError(f"repeated nuspec version was admitted: {status}, {reasons}")
    print("PASS repeated package version: NO_VERDICT")

    try:
        strict_json(b'{"sourceCandidates":[],"sourceCandidates":[]}')
    except ValueError:
        print("PASS duplicate baseline JSON key: refused")
    else:
        raise AssertionError("duplicate baseline JSON key was accepted")
