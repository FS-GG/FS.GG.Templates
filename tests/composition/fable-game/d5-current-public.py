#!/usr/bin/env python3
"""Current D.5 identity, matrix and evidence checks; no acquisition or product launch."""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
from zipfile import ZipFile

SPEC = importlib.util.spec_from_file_location("historical_d5", Path(__file__).with_name("d5-public-pins.py"))
HISTORICAL = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(HISTORICAL)
LIFECYCLES = ("none", "sdd", "typed-sdd", "spec-kit")
BUNDLES = ("player", "studio", "tactical", "arcade", "complete")
PINS = {
    "schema": "fsgg.svg-release-d5.current-public-pins/1",
    "templates": {"version": "0.19.3", "sha256": "9594ec204a26f238a06e016d1cfe1e796a07fda23c16589eceb19366cd4a72a2",
                  "sourceCommit": "7be0bcf5886d39a8161b186beb8cc06e82415f1e",
                  "providerSha256": "6b3d8f2dcbdcd429e4f622cfd6e1515c439097147bb79f5d5c7969d36c3b5006"},
    "sdd": {"version": "2.4.0", "sha256": "1df2e74faebd388f90b813ed9d7497f4247f977718469c9247b37111d791921f",
            "sourceCommit": "c1fee66a34ec8d222586eb708ddff4973ad5594e"},
    "wizard": {"version": "0.22.0", "sha256": "caa91285e5370edc7a8a14a5a46f6cfef236d1db95f1e186357e6591b9ec7bd5",
               "sourceCommit": "6e6fb9b9f7677e26f0c7d58cab1646323e81df58"},
    "overlay": {"version": "0.18.2", "sha256": "496aad0e89496719bc543edc6ffbf829a82307862e630ba4e174e374ac11cc4e",
                "sourceCommit": "20c009bc6728302f9ed06fdf49cb2e8bd19e417d"},
}
IDS = {"templates": "FS.GG.Workspace.Template", "overlay": "FS.GG.Workspace.Template",
       "sdd": "FS.GG.SDD.Cli", "wizard": "FS.GG.NewSddWorkspace"}


def require(ok, message):
    if not ok:
        raise ValueError(message)


def unique(pairs):
    value = {}
    for key, item in pairs:
        require(key not in value, "duplicate JSON property: " + key)
        value[key] = item
    return value


def read_json(path, limit=65536):
    path = Path(path)
    require(path.is_file() and not path.is_symlink() and path.stat().st_size <= limit, "bounded regular JSON required")
    return json.loads(path.read_bytes().decode("utf-8"), object_pairs_hook=unique)


def validate(value):
    require(value == PINS, "exact current Templates/SDD/Wizard/initial-overlay identities required")
    return value


def archive_identity(path, key, pins):
    require(key in IDS, "unknown package role")
    require(hashlib.sha256(Path(path).read_bytes()).hexdigest() == pins[key]["sha256"], "public archive hash mismatch")
    # The maintained historical checker is version-parameterized at this seam.
    HISTORICAL.archive_identity(path, IDS[key], pins[key])
    if key == "templates":
        with ZipFile(path) as package:
            matches = [p for p in package.namelist() if p.endswith("fs-gg-fable-game/.template.config/template.json")]
            require(len(matches) == 1, "modern template selection ambiguous")
            symbols = json.loads(package.read(matches[0]))["symbols"]
            require(tuple(row["choice"] for row in symbols["bundle"]["choices"]) == BUNDLES,
                    "published bundle choices differ from requested matrix")
            require(symbols["bundle"]["defaultValue"] == "player", "raw omitted bundle default differs")


def cases(scope):
    # Both current Wizard lifecycleTokens and the package's template choices declare
    # these four tokens/five bundles, without a cross-selection restriction.
    require(scope in ("rehearsal", "full"), "unknown qualification scope")
    result = [("provider-omitted", "provider", "omitted", "omitted"),
              ("wizard-omitted", "wizard", "omitted", "omitted")]
    if scope == "full":
        result += [(f"{route}-{lane}-{bundle}", route, lane, bundle)
                   for route in ("provider", "wizard") for lane in LIFECYCLES for bundle in BUNDLES]
    return result


def check_tree(root, lifecycle, bundle, raw=False):
    root = Path(root)
    bundle = "player" if bundle == "omitted" else bundle
    require(bundle in BUNDLES, "unsupported bundle")
    foundation = root / "SvgFoundation"
    require((foundation / "SvgFoundation.fsproj").is_file(), "SVG Player project missing")
    require((foundation / "Studio").is_dir() == (bundle != "player"), "Studio bundle contents differ")
    for name, expected in (("Tactical", bundle in ("tactical", "complete")),
                           ("Arcade", bundle in ("arcade", "complete"))):
        require((foundation / "Examples" / name / "scene.json").is_file() == expected, name + " bundle contents differ")
    for relative in ("FourD/reference.json", "ExternalAuthority/reference.json", "SoldierReference/reference.json",
                     "Wasm/WasmPolicyExample.fs", "Wasm/guest/policy.c"):
        require((foundation / "Examples" / relative).is_file() == (bundle == "complete"),
                "Complete-only reference contents differ: " + relative)
    model_files = [p for p in (root / "models").rglob("*") if p.is_file()]
    require(bool(model_files) == (bundle != "player"), "model bundle contents differ")
    if raw:
        return
    expected = "typed-sdd" if lifecycle == "omitted" else lifecycle
    provenance = read_json(root / ".fsgg/scaffold-provenance.json")
    require(provenance["generator"] == {"id": "FS.GG.SDD.Artifacts", "version": "2.4.0"}, "current generator identity differs")
    params = [row["value"] for row in provenance["effectiveParameters"] if row["key"] == "lifecycle"]
    require(params == [expected], "effective lifecycle differs")
    if expected == "typed-sdd":
        require((root / ".fsgg/sdd.yml").is_file(), "typed root lifecycle missing")
        require(len(list(root.rglob(".fsgg/sdd.yml"))) == 1, "multiple root lifecycles")


def owner_snapshot(root):
    root = Path(root)
    selected = [root / name for name in ("AGENTS.md", "CLAUDE.md", ".fsgg", ".agents", ".claude", "readiness/d5-default")]
    result = {}
    for entry in selected:
        require(not entry.is_symlink(), "owner/authority symlink refused")
        paths = [entry] if entry.is_file() else entry.rglob("*") if entry.is_dir() else []
        for path in paths:
            require(not path.is_symlink(), "owner/authority symlink refused")
            if path.is_file():
                result[str(path.relative_to(root))] = hashlib.sha256(path.read_bytes()).hexdigest()
    require("readiness/d5-default/typed-authority.json" in result, "existing authority missing")
    return result


def check_authority(root):
    root = Path(root)
    authority = read_json(root / "readiness/d5-default/typed-authority.json")
    require(authority["backend"] == "quint-specification-v1" and authority["profileIdentity"] == "fsgg-quint-profile/2", "default backend/profile differs")
    require(authority["packageIdentity"] == "FS.GG.SDD.Artifacts/2.4.0", "current authority producer differs")
    require(bool(authority["artifacts"]), "authority artifacts missing")
    for artifact in authority["artifacts"]:
        path = root / artifact["path"]
        require(path.resolve().is_relative_to(root.resolve()) and not path.is_symlink(), "authority artifact escaped root")
        require(hashlib.sha256(path.read_bytes()).hexdigest() == artifact["sha256"], "authority artifact hash differs")


def extract_model(archive, destination):
    destination = Path(destination)
    destination.mkdir(parents=True, exist_ok=False)
    with ZipFile(archive) as package:
        for name in ("arena-rules.md", "arena-rules.bindings.json", "arena-rules.qnt", "correspondence.qnt"):
            suffix = "fs-gg-fable-game/models/svg-arena/" + name
            matches = [p for p in package.namelist() if p.endswith(suffix)]
            require(len(matches) == 1, "public model member missing/ambiguous")
            data = package.read(matches[0])
            require(len(data) <= 1048576, "model member too large")
            (destination / name).write_bytes(data)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("pins", "preflight", "cases", "archive", "tree", "model", "authority", "snapshot", "preserved"))
    parser.add_argument("args", nargs="*")
    a = parser.parse_args()
    arities = {"pins": (0,), "preflight": (1,), "cases": (1,), "archive": (3,), "tree": (3, 4),
               "model": (2,), "authority": (1,), "snapshot": (2,), "preserved": (2,)}
    require(len(a.args) in arities[a.command], "incorrect argument count for " + a.command)
    if a.command == "tree" and len(a.args) == 4:
        require(a.args[3] == "raw", "unknown tree-check mode")
    if a.command == "pins":
        require(not a.args, "pins accepts no arguments")
        print(json.dumps(PINS, indent=2)); return
    if a.command == "cases":
        require(len(a.args) == 1, "cases requires rehearsal/full")
        for row in cases(a.args[0]): print("\t".join(row))
    elif a.command == "preflight":
        require(len(a.args) == 1, "preflight requires exactly one pins file")
        validate(read_json(a.args[0]))
    elif a.command == "archive": archive_identity(a.args[2], a.args[1], validate(read_json(a.args[0])))
    elif a.command == "tree": check_tree(*a.args[:3], raw=a.args[3:] == ["raw"])
    elif a.command == "model": extract_model(*a.args)
    elif a.command == "authority": check_authority(a.args[0])
    elif a.command == "snapshot":
        with Path(a.args[1]).open("x") as stream: json.dump(owner_snapshot(a.args[0]), stream, sort_keys=True)
    elif a.command == "preserved":
        require(owner_snapshot(a.args[0]) == read_json(a.args[1], 4194304), "refusal changed existing authority/owner bytes")
        require(not (Path(a.args[0]) / "readiness/d5-refused/typed-authority.json").exists(), "refused authority was published")


if __name__ == "__main__":
    try: main()
    except (ValueError, KeyError, OSError, IndexError) as error:
        print("current D.5: " + str(error), file=sys.stderr); raise SystemExit(2)
