#!/usr/bin/env python3
"""Disposable config-only false green and local template-payload comparison controls."""

from hashlib import sha256
import json
from pathlib import Path
import stat
import subprocess
import tempfile
import warnings
from zipfile import ZipFile, ZipInfo

from check import PROJECT, Refusal, compare, github_no_verdict, snapshot

HEAD_A = "a" * 40
HEAD_B = "b" * 40
CONFIG = "content/templates/fs-gg-fable-game/.template.config/template.json"
ASSET = "content/templates/fs-gg-fable-game/build.sh"


def package(path: Path, *, head: str, asset: bytes, extra: bool = False,
            signed: bool = False, duplicate: bool = False, executable: bool = False,
            oversized_nuspec: bool = False) -> str:
    nuspec = ("<package><metadata><id>FS.GG.Workspace.Template</id><version>0.14.0</version>"
              f'<repository commit="{head}" /></metadata></package>').encode()
    if oversized_nuspec:
        nuspec += b"x" * (1024 * 1024)
    rows = [("FS.GG.Workspace.Template.nuspec", nuspec, 0o644),
            (CONFIG, b'{"shortName":"fs-gg-fable-game"}', 0o755 if executable else 0o644),
            (ASSET, asset, 0o644)]
    if extra:
        rows.append(("content/templates/fs-gg-fable-game/new-asset.txt", b"new", 0o644))
    if duplicate:
        rows.append((ASSET, b"duplicate", 0o644))
    if signed:
        rows.append((".signature.p7s", b"synthetic signature member", 0o644))
    with ZipFile(path, "w") as archive, warnings.catch_warnings():
        warnings.simplefilter("ignore", UserWarning)
        for name, body, permissions in rows:
            info = ZipInfo(name)
            info.create_system = 3
            info.external_attr = (stat.S_IFREG | permissions) << 16
            archive.writestr(info, body)
    return sha256(path.read_bytes()).hexdigest()


def refused(action, phrase: str) -> None:
    try:
        action()
    except Refusal as error:
        if phrase not in str(error):
            raise AssertionError(f"wrong refusal: {error}") from error
    else:
        raise AssertionError(f"expected refusal containing {phrase!r}")


def typed(raw: str) -> dict:
    completed = subprocess.run(["dotnet", "run", "--project", str(PROJECT), "-c", "Release",
                                "--no-launch-profile", "--"], input=raw, capture_output=True,
                               text=True, check=True)
    return json.loads(completed.stdout)


with tempfile.TemporaryDirectory(prefix="fsc05-provider-local-payload-") as folder:
    work = Path(folder)
    no_config = {"templates": {ASSET: (sha256(b"body").hexdigest(), stat.S_IFREG | 0o644)},
                 "configs": {}}
    no_config_verdict = compare(no_config, no_config)
    if no_config_verdict["status"] != "NO_VERDICT":
        raise AssertionError(f"matching payload without template config was admitted: {no_config_verdict}")
    print("PASS missing template config in both inputs: NO_VERDICT")

    member_config = {"name": CONFIG, "sha256": sha256(b"config").hexdigest(),
                     "mode": stat.S_IFREG | 0o644}
    member_asset = {"name": ASSET, "sha256": sha256(b"asset").hexdigest(),
                    "mode": stat.S_IFREG | 0o644}
    valid = {"left": [member_config, member_asset], "right": [member_config, member_asset]}
    if typed(json.dumps(valid))["status"] != "TEMPLATE_PAYLOAD_MATCH_ONLY":
        raise AssertionError("typed comparator refused a complete matching template")
    print("PASS typed complete template: narrow match")

    for label, unsafe_name in (
            ("trailing-dot directory", "content/templates/fs-gg-fable-game/assets./build.sh"),
            ("trailing-space file", ASSET + " ")):
        unsafe_asset = dict(member_asset, name=unsafe_name)
        unsafe_snapshot = {"left": [member_config, unsafe_asset],
                           "right": [member_config, unsafe_asset]}
        unsafe_result = typed(json.dumps(unsafe_snapshot))
        if unsafe_result["status"] != "NO_VERDICT" or "trailing dot or space" not in unsafe_result["reason"]:
            raise AssertionError(f"{label} yielded a typed payload match: {unsafe_result}")
        print(f"PASS {label}: NO_VERDICT")

    internal_space_asset = dict(member_asset, name="content/templates/fs-gg-fable-game/build script.sh")
    internal_space = {"left": [member_config, internal_space_asset],
                      "right": [member_config, internal_space_asset]}
    if typed(json.dumps(internal_space))["status"] != "TEMPLATE_PAYLOAD_MATCH_ONLY":
        raise AssertionError("ordinary internal-space asset was refused")
    print("PASS internal-space asset: narrow match")

    for label, unsafe_name in (
            ("control-character asset", ASSET.replace("build.sh", "build\n.sh")),
            ("reserved-punctuation asset", ASSET.replace("build.sh", "build?.sh"))):
        unsafe_asset = dict(member_asset, name=unsafe_name)
        unsafe_snapshot = {"left": [member_config, unsafe_asset],
                           "right": [member_config, unsafe_asset]}
        unsafe_result = typed(json.dumps(unsafe_snapshot))
        if unsafe_result["status"] != "NO_VERDICT" or "reserved path character" not in unsafe_result["reason"]:
            raise AssertionError(f"{label} yielded a typed payload match: {unsafe_result}")
        print(f"PASS {label}: NO_VERDICT")

    plus_asset = dict(member_asset, name=ASSET.replace("build.sh", "build+script.sh"))
    plus_snapshot = {"left": [member_config, plus_asset], "right": [member_config, plus_asset]}
    if typed(json.dumps(plus_snapshot))["status"] != "TEMPLATE_PAYLOAD_MATCH_ONLY":
        raise AssertionError("ordinary plus-sign asset was refused")
    print("PASS plus-sign asset: narrow match")

    for label, unsafe_name in (
            ("reserved device with extension", ASSET.replace("build.sh", "NUL.txt")),
            ("reserved superscript device", ASSET.replace("build.sh", "com\u00b9.bin"))):
        unsafe_asset = dict(member_asset, name=unsafe_name)
        unsafe_snapshot = {"left": [member_config, unsafe_asset],
                           "right": [member_config, unsafe_asset]}
        unsafe_result = typed(json.dumps(unsafe_snapshot))
        if unsafe_result["status"] != "NO_VERDICT" or "reserved device name" not in unsafe_result["reason"]:
            raise AssertionError(f"{label} yielded a typed payload match: {unsafe_result}")
        print(f"PASS {label}: NO_VERDICT")

    ordinary_numbered_asset = dict(member_asset, name=ASSET.replace("build.sh", "COM10.txt"))
    ordinary_numbered = {"left": [member_config, ordinary_numbered_asset],
                         "right": [member_config, ordinary_numbered_asset]}
    if typed(json.dumps(ordinary_numbered))["status"] != "TEMPLATE_PAYLOAD_MATCH_ONLY":
        raise AssertionError("ordinary numbered asset was refused")
    print("PASS ordinary numbered asset: narrow match")

    for label, segment in (
            ("256-byte ASCII segment", "a" * 256),
            ("256-byte NFC segment", "\u00e9" * 128)):
        long_asset = dict(member_asset, name="content/templates/fs-gg-fable-game/" + segment)
        long_snapshot = {"left": [member_config, long_asset], "right": [member_config, long_asset]}
        long_result = typed(json.dumps(long_snapshot, ensure_ascii=False))
        if long_result["status"] != "NO_VERDICT" or "segment exceeds byte bound" not in long_result["reason"]:
            raise AssertionError(f"{label} yielded a typed payload match: {long_result}")
        print(f"PASS {label}: NO_VERDICT")

    max_asset = dict(member_asset, name="content/templates/fs-gg-fable-game/" + "a" * 255)
    max_snapshot = {"left": [member_config, max_asset], "right": [member_config, max_asset]}
    if typed(json.dumps(max_snapshot))["status"] != "TEMPLATE_PAYLOAD_MATCH_ONLY":
        raise AssertionError("255-byte path segment was refused")
    print("PASS 255-byte path segment: narrow match")

    newline_digest_asset = dict(member_asset, sha256=member_asset["sha256"] + "\n")
    newline_digest = {"left": [member_config, newline_digest_asset],
                      "right": [member_config, newline_digest_asset]}
    newline_digest_result = typed(json.dumps(newline_digest))
    if newline_digest_result["status"] != "NO_VERDICT" or "sha256 is invalid" not in newline_digest_result["reason"]:
        raise AssertionError(f"newline-terminated digest yielded a payload match: {newline_digest_result}")
    print("PASS newline-terminated typed digest: NO_VERDICT")

    nested_config = dict(member_config, name="content/templates/fs-gg-fable-game/scaffold/.template.config/template.json")
    nested = {"left": [member_config, member_asset, nested_config],
              "right": [member_config, member_asset, nested_config]}
    nested_result = typed(json.dumps(nested))
    if nested_result["status"] != "NO_VERDICT" or "non-root template config" not in nested_result["reason"]:
        raise AssertionError(f"nested config yielded a typed payload match: {nested_result}")
    print("PASS nested template config: NO_VERDICT")

    nested_asset = dict(member_asset, name="content/templates/fs-gg-fable-game/scaffold/template.json")
    nested_asset_snapshot = {"left": [member_config, member_asset, nested_asset],
                             "right": [member_config, member_asset, nested_asset]}
    if typed(json.dumps(nested_asset_snapshot))["status"] != "TEMPLATE_PAYLOAD_MATCH_ONLY":
        raise AssertionError("ordinary nested template asset was refused")
    print("PASS ordinary nested template asset: narrow match")

    config_child = dict(member_asset, name=CONFIG + "/child")
    config_collision = {"left": [member_config, member_asset, config_child],
                        "right": [member_config, member_asset, config_child]}
    config_collision_result = typed(json.dumps(config_collision))
    if config_collision_result["status"] != "NO_VERDICT" or "file ancestor" not in config_collision_result["reason"]:
        raise AssertionError(f"config file and child yielded a payload match: {config_collision_result}")
    print("PASS config file and child path collision: NO_VERDICT")

    case_child = dict(member_asset, name=ASSET.replace("build.sh", "BUILD.SH/child"))
    case_collision = {"left": [member_config, member_asset, case_child],
                      "right": [member_config, member_asset, case_child]}
    case_collision_result = typed(json.dumps(case_collision))
    if case_collision_result["status"] != "NO_VERDICT" or "file ancestor" not in case_collision_result["reason"]:
        raise AssertionError(f"case-aliased file and child yielded a payload match: {case_collision_result}")
    print("PASS case-aliased file and child path collision: NO_VERDICT")

    decomposed_root = "fs-gg-cafe\u0301"
    decomposed_config = dict(member_config, name=f"content/templates/{decomposed_root}/.template.config/template.json")
    decomposed_asset = dict(member_asset, name=f"content/templates/{decomposed_root}/build.sh")
    decomposed = {"left": [decomposed_config, decomposed_asset],
                  "right": [decomposed_config, decomposed_asset]}
    decomposed_result = typed(json.dumps(decomposed, ensure_ascii=False))
    if decomposed_result["status"] != "NO_VERDICT" or "noncanonical Unicode path" not in decomposed_result["reason"]:
        raise AssertionError(f"decomposed typed path was admitted: {decomposed_result}")
    print("PASS decomposed typed path: NO_VERDICT")

    composed_root = "fs-gg-caf\u00e9"
    composed_config = dict(member_config, name=f"content/templates/{composed_root}/.template.config/template.json")
    composed_asset = dict(member_asset, name=f"content/templates/{composed_root}/build.sh")
    composed = {"left": [composed_config, composed_asset], "right": [composed_config, composed_asset]}
    if typed(json.dumps(composed, ensure_ascii=False))["status"] != "TEMPLATE_PAYLOAD_MATCH_ONLY":
        raise AssertionError("canonical composed typed path was refused")
    print("PASS composed typed path: narrow match")

    duplicate_root = typed('{"left":[],"left":[],"right":[]}')
    if duplicate_root["status"] != "NO_VERDICT" or "repeats left" not in duplicate_root["reason"]:
        raise AssertionError(f"duplicate comparison key was admitted: {duplicate_root}")
    print("PASS duplicate comparison key: NO_VERDICT")

    duplicate_member = dict(valid, left=[member_config, member_asset, member_asset])
    duplicate_result = typed(json.dumps(duplicate_member))
    if duplicate_result["status"] != "NO_VERDICT" or "repeats or aliases" not in duplicate_result["reason"]:
        raise AssertionError(f"duplicate member was admitted: {duplicate_result}")
    print("PASS duplicate typed member: NO_VERDICT")

    alias_asset = dict(member_asset, name=ASSET.replace("build.sh", "BUILD.sh"))
    alias_result = typed(json.dumps(dict(valid, left=[member_config, member_asset, alias_asset])))
    if alias_result["status"] != "NO_VERDICT" or "repeats or aliases" not in alias_result["reason"]:
        raise AssertionError(f"case-aliased member was admitted: {alias_result}")
    print("PASS case-aliased typed member: NO_VERDICT")

    foreign_member = dict(member_config, foreign=True)
    foreign_result = typed(json.dumps(dict(valid, left=[foreign_member, member_asset])))
    if foreign_result["status"] != "NO_VERDICT" or "unsupported field" not in foreign_result["reason"]:
        raise AssertionError(f"foreign member field was admitted: {foreign_result}")
    print("PASS foreign typed member field: NO_VERDICT")

    selected_path = work / "selected.nupkg"
    release_path = work / "release.nupkg"
    nuget_path = work / "nuget.nupkg"
    selected_sha = package(selected_path, head=HEAD_A, asset=b"old")
    release_sha = package(release_path, head=HEAD_B, asset=b"new", extra=True)
    nuget_sha = package(nuget_path, head=HEAD_B, asset=b"new", extra=True, signed=True)

    selected = snapshot(selected_path, selected_sha, HEAD_A)
    release = snapshot(release_path, release_sha, HEAD_B)
    nuget = snapshot(nuget_path, nuget_sha, HEAD_B, signed=True)
    if selected["configs"] != release["configs"]:
        raise AssertionError("config-only comparison did not reproduce the false parity signal")
    print("PASS red-before boundary: identical template configs hide asset drift")

    drift = compare(selected, release)
    if drift != {"status": "NO_VERDICT", "configOnlyMatch": True,
                 "missing": 0, "extra": 1, "bodyDrift": 1, "modeDrift": 0}:
        raise AssertionError(f"asset drift was not reported exactly: {drift}")
    print("PASS full template payload: changed and extra assets are NO_VERDICT")

    signed_match = compare(release, nuget)
    if signed_match["status"] != "TEMPLATE_PAYLOAD_MATCH_ONLY" or any(
            signed_match[key] for key in ("missing", "extra", "bodyDrift", "modeDrift")):
        raise AssertionError(f"signed local file template payload differed: {signed_match}")
    print("PASS signed local file: template payload match only")

    refused(lambda: snapshot(selected_path, "0" * 64, HEAD_A), "SHA differs")
    refused(lambda: snapshot(selected_path, selected_sha, HEAD_B), "source commit differs")
    print("PASS local archive SHA and source commit are both bound")

    duplicate_path = work / "duplicate.nupkg"
    duplicate_sha = package(duplicate_path, head=HEAD_A, asset=b"old", duplicate=True)
    refused(lambda: snapshot(duplicate_path, duplicate_sha, HEAD_A), "duplicate or case alias")
    print("PASS duplicate template member: refused")

    mode_path = work / "mode.nupkg"
    mode_sha = package(mode_path, head=HEAD_A, asset=b"old", executable=True)
    refused(lambda: snapshot(mode_path, mode_sha, HEAD_A), "Unix mode differs")
    print("PASS mode-only template change: refused")

    oversized_path = work / "oversized-nuspec.nupkg"
    oversized_sha = package(oversized_path, head=HEAD_A, asset=b"old", oversized_nuspec=True)
    refused(lambda: snapshot(oversized_path, oversized_sha, HEAD_A), "identity exceeds observation bound")
    print("PASS oversized package identity: refused before XML parse")

    for status in (403, 200, None):
        if github_no_verdict(status)["status"] != "NO_VERDICT":
            raise AssertionError("status-only GitHub report supplied archive evidence")
    print("PASS GitHub status-only reports: NO_VERDICT without bytes")
