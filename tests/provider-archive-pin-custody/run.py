#!/usr/bin/env python3
"""Disposable proof that floor-green does not establish selected archive provider parity."""

from hashlib import sha256
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
from zipfile import ZIP_DEFLATED, ZipFile
from zipfile import ZipInfo
from unittest.mock import patch

import check
from check import DESCRIPTOR_FILES, OWNER_FILES, assess, strict_json

ROOT = Path(__file__).resolve().parents[2]
PROJECT = ROOT / "src/FS.GG.Templates.ProviderTool/FS.GG.Templates.ProviderTool.fsproj"
CHECKER = ROOT / "scripts/check-provider-floors.py"
OBSERVER = Path(__file__).with_name("check.py")
PIN = "1.4.0-preview.1"
VERSION = "0.14.0"
SOURCE_HEAD = "a" * 40


def package_baseline(path: Path) -> dict:
    return {"sourceCandidates": [{"version": VERSION,
                                   "sourceHead": SOURCE_HEAD,
                                   "nativeArchiveSha256": sha256(path.read_bytes()).hexdigest()}]}


def package(path: Path, duplicate_game: bool = False, *,
            commit: str | None = SOURCE_HEAD, duplicate_repository: bool = False) -> dict:
    repository = (f'<repository type="git" url="https://github.com/FS-GG/FS.GG.Templates" '
                  f'commit="{commit}" />') if commit is not None else ""
    if duplicate_repository:
        repository += repository
    with ZipFile(path, "w", ZIP_DEFLATED) as archive:
        archive.writestr("FS.GG.Workspace.Template.nuspec", "<package><metadata>"
                         "<id>FS.GG.Workspace.Template</id><version>0.14.0</version>"
                         f"{repository}</metadata></package>")
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
    for filename, expected in check.REVIEWED_DESCRIPTOR_SHA256.items():
        actual = sha256((ROOT / "providers" / filename).read_bytes()).hexdigest()
        if actual != expected:
            raise AssertionError(f"reviewed source digest drifted: {filename}")
    print("PASS reviewed descriptor digests match checked-in source bytes")
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

    wrong_commit = work / "wrong-source-commit.nupkg"
    wrong_baseline = package(wrong_commit, commit="b" * 40)
    status, reasons = assess(wrong_commit, wrong_baseline, providers)
    if status != "NO_VERDICT" or reasons != ["package source commit differs from selected candidate"]:
        raise AssertionError(f"wrong package source commit was admitted: {status}, {reasons}")
    print("PASS wrong package source commit: NO_VERDICT")

    missing_repository = work / "missing-repository.nupkg"
    missing_baseline = package(missing_repository, commit=None)
    status, reasons = assess(missing_repository, missing_baseline, providers)
    if status != "NO_VERDICT" or reasons != ["package repository metadata is missing or ambiguous"]:
        raise AssertionError(f"missing repository commit was admitted: {status}, {reasons}")
    print("PASS missing package repository: NO_VERDICT")

    repeated_repository = work / "repeated-repository.nupkg"
    repeated_baseline = package(repeated_repository, duplicate_repository=True)
    status, reasons = assess(repeated_repository, repeated_baseline, providers)
    if status != "NO_VERDICT" or reasons != ["package repository metadata is missing or ambiguous"]:
        raise AssertionError(f"repeated repository commit was admitted: {status}, {reasons}")
    print("PASS repeated package repository: NO_VERDICT")

    missing_head = {"sourceCandidates": [{"version": VERSION,
                                          "nativeArchiveSha256": baseline["sourceCandidates"][0]["nativeArchiveSha256"]}]}
    status, reasons = assess(archive, missing_head, providers)
    if status != "NO_VERDICT" or reasons != ["selected source head is invalid"]:
        raise AssertionError(f"missing selected source head was admitted: {status}, {reasons}")
    print("PASS missing selected source head: NO_VERDICT")

    fixture_digests = {name: sha256((providers / name).read_bytes()).hexdigest()
                       for name in DESCRIPTOR_FILES}
    console_changed = providers / OWNER_FILES["console"]
    console_original = console_changed.read_text(encoding="utf-8")
    console_mutation = console_original.replace("default: sdd", "default: foreign")
    assert console_mutation != console_original
    console_changed.write_text(console_mutation, encoding="utf-8")
    status, reasons = assess(archive, baseline, providers)
    if status != "PIN_ROSTER_MATCH_ONLY" or reasons:
        raise AssertionError(f"parameter-only source mutation did not reproduce old narrow match: {status}, {reasons}")
    print("PASS red-before boundary: parameter-only owner mutation retained narrow pin match")
    status, reasons = assess(archive, baseline, providers, expected_descriptors=fixture_digests)
    if status != "NO_VERDICT" or reasons != ["console.providers.yml bytes differ from reviewed source snapshot"]:
        raise AssertionError(f"parameter-only owner mutation was admitted by snapshot: {status}, {reasons}")
    console_changed.write_text(console_original, encoding="utf-8")
    status, reasons = assess(archive, baseline, providers, expected_descriptors=fixture_digests)
    if status != "PIN_ROSTER_MATCH_ONLY" or reasons:
        raise AssertionError(f"unchanged fixture snapshot was refused: {status}, {reasons}")
    print("PASS exact owner source snapshot: mutated refused, unchanged accepted")

    status, reasons = assess(archive, baseline, providers,
                             expected_descriptors={OWNER_FILES["console"]: fixture_digests[OWNER_FILES["console"]]})
    if status != "NO_VERDICT" or reasons != ["reviewed descriptor snapshot is incomplete"]:
        raise AssertionError(f"partial owner digest map was admitted: {status}, {reasons}")
    print("PASS partial owner digest map: NO_VERDICT")

    forged_baseline = work / "forged-baseline.json"
    forged_baseline.write_text(json.dumps(baseline), encoding="utf-8")
    observed = subprocess.run(["python3", str(OBSERVER), "--archive", str(archive),
                               "--baseline", str(forged_baseline), "--providers", str(providers)],
                              check=True, capture_output=True, text=True)
    forged_verdict = json.loads(observed.stdout)
    if forged_verdict["status"] != "NO_VERDICT" or forged_verdict["reasons"] != ["baseline bytes differ from reviewed source"]:
        raise AssertionError(f"caller-forged baseline admitted by CLI: {forged_verdict}")
    print("PASS caller-forged baseline: CLI NO_VERDICT")

    reviewed = subprocess.run(["python3", str(OBSERVER), "--archive", str(archive),
                               "--baseline", str(ROOT / "scripts/svg-complete-workspace-baselines.json"),
                               "--providers", str(providers)],
                              check=True, capture_output=True, text=True)
    reviewed_verdict = json.loads(reviewed.stdout)
    if reviewed_verdict["status"] != "NO_VERDICT" or reviewed_verdict["reasons"] != ["selected archive SHA mismatch"]:
        raise AssertionError(f"reviewed baseline was not accepted for assessment: {reviewed_verdict}")
    print("PASS reviewed baseline: synthetic archive SHA mismatch, no verdict")

    console_path = providers / OWNER_FILES["console"]
    bindings_path = providers / OWNER_FILES["fable-bindings"]
    clean_console = console_path.read_text(encoding="utf-8")
    clean_bindings = bindings_path.read_text(encoding="utf-8")
    bindings_path.write_text(clean_bindings.replace("source: FS.GG.Workspace.Template::0.14.0",
                                                   "source: FS.GG.Workspace.Template::0.13.0"),
                             encoding="utf-8")
    original_open = os.open
    swapped = [False]

    def swap_between_reads(name, flags, *args, **kwargs):
        if name == OWNER_FILES["fable-bindings"] and not swapped[0]:
            swapped[0] = True
            console_path.write_text(clean_console.replace("source: FS.GG.Workspace.Template::0.14.0",
                                                          "source: FS.GG.Workspace.Template::0.13.0"),
                                    encoding="utf-8")
            bindings_path.write_text(clean_bindings, encoding="utf-8")
        return original_open(name, flags, *args, **kwargs)

    with patch.object(check.os, "open", side_effect=swap_between_reads):
        status, reasons = assess(archive, baseline, providers)
    if not swapped[0] or status != "NO_VERDICT" or "provider descriptor changed during observation" not in reasons:
        raise AssertionError(f"cross-file source swap was admitted: {status}, {reasons}")
    console_path.write_text(clean_console, encoding="utf-8")
    bindings_path.write_text(clean_bindings, encoding="utf-8")
    print("PASS cross-file source swap: NO_VERDICT")

    displaced = work / "displaced-console.providers.yml"
    replaced = [False]

    def replace_between_reads(name, flags, *args, **kwargs):
        if name == OWNER_FILES["fable-bindings"] and not replaced[0]:
            replaced[0] = True
            console_path.rename(displaced)
            console_path.write_text(clean_console.replace("source: FS.GG.Workspace.Template::0.14.0",
                                                          "source: FS.GG.Workspace.Template::0.13.0"),
                                    encoding="utf-8")
        return original_open(name, flags, *args, **kwargs)

    with patch.object(check.os, "open", side_effect=replace_between_reads):
        status, reasons = assess(archive, baseline, providers)
    if not replaced[0] or status != "NO_VERDICT" or "provider descriptor changed during observation" not in reasons:
        raise AssertionError(f"renamed owner path was admitted: {status}, {reasons}")
    console_path.unlink()
    displaced.rename(console_path)
    print("PASS replaced owner path: NO_VERDICT")

    extra = providers / "governance.providers.yml"
    extra.write_text("schemaVersion: 1\nproviders:\n  - name: governance\n"
                     "    contractVersion: \"1.1.0\"\n    templateId: fs-gg-governance\n"
                     "    source: FS.GG.Workspace.Template::0.14.0\n"
                     "    minimumFsggSdd:\n      version: \"1.4.0-preview.1\"\n",
                     encoding="utf-8")
    status, reasons = assess(archive, baseline, providers)
    if status != "NO_VERDICT" or "provider descriptor inventory differs from observed owner set" not in reasons:
        raise AssertionError(f"new package owner was silently ignored: {status}, {reasons}")
    extra.unlink()
    print("PASS added package owner: NO_VERDICT pending owner review")

    original_console = providers / OWNER_FILES["console"]
    outside = work / "outside-console.providers.yml"
    original_console.rename(outside)
    os.symlink(outside, original_console)
    status, reasons = assess(archive, baseline, providers)
    if status != "NO_VERDICT" or not any("symlink" in reason for reason in reasons):
        raise AssertionError(f"linked owner descriptor was admitted: {status}, {reasons}")
    original_console.unlink()
    outside.rename(original_console)
    print("PASS linked owner descriptor: NO_VERDICT")

    rendering = providers / "rendering.providers.yml"
    rendering_text = rendering.read_text(encoding="utf-8")
    altered_rendering, replacements = re.subn(
        r"(?m)^    source: FS\.GG\.UI\.Template::0\.31\.0(?=\s|$)",
        "    source: FS.GG.Workspace.Template::0.14.0", rendering_text)
    assert replacements == 1
    rendering.write_text(altered_rendering, encoding="utf-8")
    status, reasons = assess(archive, baseline, providers)
    if status != "NO_VERDICT" or "non-owner provider source is ambiguous or selects the observed package" not in reasons:
        raise AssertionError(f"unreviewed package owner was admitted: {status}, {reasons}")
    rendering.write_text(rendering_text, encoding="utf-8")
    print("PASS changed non-owner package source: NO_VERDICT")

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

    altered = {"sourceCandidates": [{"version": VERSION, "sourceHead": SOURCE_HEAD,
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
