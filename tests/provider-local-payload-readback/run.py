#!/usr/bin/env python3
"""Disposable config-only false green and local template-payload comparison controls."""

from hashlib import sha256
import json
from pathlib import Path
import stat
import subprocess
import tempfile
import unicodedata
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

    ligature_asset = dict(member_asset, name=ASSET.replace("build.sh", "\ufb01le.sh"))
    ascii_alias_asset = dict(member_asset, name=ASSET.replace("build.sh", "file.sh"))
    if ligature_asset["name"].casefold() != ascii_alias_asset["name"].casefold():
        raise AssertionError("fixture does not reproduce Python's casefold alias")
    compatibility_alias = {"left": [member_config, ligature_asset, ascii_alias_asset],
                           "right": [member_config, ligature_asset, ascii_alias_asset]}
    compatibility_result = typed(json.dumps(compatibility_alias, ensure_ascii=False))
    if compatibility_result["status"] != "NO_VERDICT" or "noncanonical compatibility path" not in compatibility_result["reason"]:
        raise AssertionError(f"compatibility alias yielded a typed payload match: {compatibility_result}")
    print("PASS compatibility-form casefold alias: NO_VERDICT")

    ascii_sharp_alias = dict(member_asset, name=ASSET.replace("build.sh", "Strasse.sh"))
    for glyph in ("\u00df", "\u1e9e"):
        sharp_asset = dict(member_asset, name=ASSET.replace("build.sh", f"Stra{glyph}e.sh"))
        if sharp_asset["name"].casefold() != ascii_sharp_alias["name"].casefold():
            raise AssertionError("sharp-s fixture does not reproduce Python's casefold alias")
        sharp_snapshot = {"left": [member_config, sharp_asset, ascii_sharp_alias],
                          "right": [member_config, sharp_asset, ascii_sharp_alias]}
        sharp_result = typed(json.dumps(sharp_snapshot, ensure_ascii=False))
        if sharp_result["status"] != "NO_VERDICT" or "sharp-s case-fold expansion" not in sharp_result["reason"]:
            raise AssertionError(f"sharp-s alias yielded a typed payload match: {sharp_result}")
        print(f"PASS sharp-s U+{ord(glyph):04X} casefold alias: NO_VERDICT")

    ascii_sharp_snapshot = {"left": [member_config, ascii_sharp_alias],
                            "right": [member_config, ascii_sharp_alias]}
    if typed(json.dumps(ascii_sharp_snapshot))["status"] != "TEMPLATE_PAYLOAD_MATCH_ONLY":
        raise AssertionError("ASCII sharp-s spelling was refused")
    print("PASS ASCII sharp-s spelling: narrow match")

    if unicodedata.unidata_version != "16.0.0":
        raise AssertionError("review typed full-fold expansion table against the Python Unicode version")
    drift_character = "\ua7f1"
    if unicodedata.name(drift_character, None) is not None or not unicodedata.is_normalized("NFKC", drift_character):
        raise AssertionError("U+A7F1 is no longer an unassigned NFKC-stable Python 16.0 fixture")
    drift_asset = dict(member_asset, name=ASSET.replace("build.sh", drift_character + ".sh"))
    drift_snapshot = {"left": [member_config, drift_asset], "right": [member_config, drift_asset]}
    drift_result = typed(json.dumps(drift_snapshot, ensure_ascii=False))
    if drift_result["status"] != "NO_VERDICT" or "Unicode 16.0 normalization drift" not in drift_result["reason"]:
        raise AssertionError(f"normalization version drift lacked a specific refusal: {drift_result}")
    print("PASS Unicode 16.0 normalization drift: explicit NO_VERDICT")

    dotted_asset = dict(member_asset, name=ASSET.replace("build.sh", "\u0130zmir.sh"))
    dotted_alias = dict(member_asset, name=ASSET.replace("build.sh", "i\u0307zmir.sh"))
    if dotted_asset["name"].casefold() != dotted_alias["name"].casefold():
        raise AssertionError("dotted-I fixture does not reproduce Python's casefold alias")
    dotted_snapshot = {"left": [member_config, dotted_asset, dotted_alias],
                       "right": [member_config, dotted_asset, dotted_alias]}
    dotted_result = typed(json.dumps(dotted_snapshot, ensure_ascii=False))
    if dotted_result["status"] != "NO_VERDICT" or "full case-fold expansion" not in dotted_result["reason"]:
        raise AssertionError(f"dotted-I alias yielded a typed payload match: {dotted_result}")
    print("PASS dotted-I full casefold alias: NO_VERDICT")

    greek_asset = dict(member_asset, name=ASSET.replace("build.sh", "\u1f80.sh"))
    greek_snapshot = {"left": [member_config, greek_asset], "right": [member_config, greek_asset]}
    greek_result = typed(json.dumps(greek_snapshot, ensure_ascii=False))
    if greek_result["status"] != "NO_VERDICT" or "full case-fold expansion" not in greek_result["reason"]:
        raise AssertionError(f"Greek full-fold expansion yielded a typed payload match: {greek_result}")
    print("PASS Greek full casefold expansion: NO_VERDICT")

    ascii_dotted_asset = dict(member_asset, name=ASSET.replace("build.sh", "Izmir.sh"))
    ascii_dotted_snapshot = {"left": [member_config, ascii_dotted_asset],
                             "right": [member_config, ascii_dotted_asset]}
    if typed(json.dumps(ascii_dotted_snapshot))["status"] != "TEMPLATE_PAYLOAD_MATCH_ONLY":
        raise AssertionError("ASCII dotted-I spelling was refused")
    print("PASS ASCII dotted-I spelling: narrow match")

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

    external_traversal_path = work / "external-traversal.nupkg"
    package(external_traversal_path, head=HEAD_A, asset=b"old")
    with ZipFile(external_traversal_path, "a") as archive:
        traversal = ZipInfo("../outside.txt")
        traversal.create_system = 3
        traversal.external_attr = (stat.S_IFREG | 0o644) << 16
        archive.writestr(traversal, b"outside")
    traversal_sha = sha256(external_traversal_path.read_bytes()).hexdigest()
    refused(lambda: snapshot(external_traversal_path, traversal_sha, HEAD_A),
            "archive member path is unsafe")
    print("PASS non-template traversal member: NO_VERDICT")

    external_symlink_path = work / "external-symlink.nupkg"
    package(external_symlink_path, head=HEAD_A, asset=b"old")
    with ZipFile(external_symlink_path, "a") as archive:
        symlink = ZipInfo("tools/link")
        symlink.create_system = 3
        symlink.external_attr = (stat.S_IFLNK | 0o777) << 16
        archive.writestr(symlink, b"../outside")
    symlink_sha = sha256(external_symlink_path.read_bytes()).hexdigest()
    refused(lambda: snapshot(external_symlink_path, symlink_sha, HEAD_A),
            "archive member is not a Unix regular file")
    print("PASS non-template symlink member: NO_VERDICT")

    corrupt_external_path = work / "corrupt-external.nupkg"
    package(corrupt_external_path, head=HEAD_A, asset=b"old")
    with ZipFile(corrupt_external_path, "a") as archive:
        external = ZipInfo("README.md")
        external.create_system = 3
        external.external_attr = (stat.S_IFREG | 0o644) << 16
        archive.writestr(external, b"outside-document-body")
    corrupt_external = corrupt_external_path.read_bytes()
    if corrupt_external.count(b"outside-document-body") != 1:
        raise AssertionError("corrupt external fixture did not locate one member body")
    corrupt_external = corrupt_external.replace(b"outside-document-body", b"outside-document-b0dy")
    corrupt_external_path.write_bytes(corrupt_external)
    refused(lambda: snapshot(corrupt_external_path, sha256(corrupt_external).hexdigest(), HEAD_A),
            "cannot be read exactly")
    print("PASS corrupt non-template member body: NO_VERDICT")

    trailing_overlay_path = work / "trailing-overlay.nupkg"
    package(trailing_overlay_path, head=HEAD_A, asset=b"old")
    trailing_overlay = trailing_overlay_path.read_bytes() + b"UNOWNED_TRAILING_BYTES"
    trailing_overlay_path.write_bytes(trailing_overlay)
    refused(lambda: snapshot(trailing_overlay_path, sha256(trailing_overlay).hexdigest(), HEAD_A),
            "archive end record differs from selected contract")
    print("PASS trailing ZIP overlay: NO_VERDICT")

    invalid_utf8_path = work / "invalid-utf8-name.nupkg"
    package(invalid_utf8_path, head=HEAD_A, asset=b"old")
    invalid_utf8 = bytearray(invalid_utf8_path.read_bytes())
    asset_name = ASSET.encode("ascii")
    central_name = invalid_utf8.rfind(asset_name)
    central_header = invalid_utf8.rfind(b"PK\x01\x02", 0, central_name)
    if central_name - central_header != 46:
        raise AssertionError("invalid UTF-8 fixture did not locate the central directory name")
    invalid_utf8[central_header + 8:central_header + 10] = (0x800).to_bytes(2, "little")
    invalid_utf8[central_name] = 0xff
    invalid_utf8_path.write_bytes(invalid_utf8)
    refused(lambda: snapshot(invalid_utf8_path, sha256(invalid_utf8).hexdigest(), HEAD_A),
            "cannot be read exactly")
    print("PASS invalid UTF-8 central directory name: NO_VERDICT")

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
