"""Mechanical source projection or actual source-package CI qualification; never a release claim."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import time
import xml.etree.ElementTree as ET
import zipfile

from receiver import ROOT


def invoke(args, success=True):
    result = subprocess.run(args, capture_output=True, text=True, timeout=90)
    if (result.returncode == 0) != success:
        raise AssertionError(f"Unexpected outcome: {args}: {result.stdout} {result.stderr}")
    return result


def main():
    parser = argparse.ArgumentParser()
    archives = parser.add_mutually_exclusive_group(required=True)
    archives.add_argument("--baseline-archive", type=Path)
    archives.add_argument("--packed-archive", type=Path)
    parser.add_argument("--candidate-command-json", required=True)
    parser.add_argument("--public203-command-json", required=True)
    parser.add_argument("--real-receiver", type=Path, required=True)
    parser.add_argument("--external-receiver", type=Path, action="append", default=[])
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    out = args.output.resolve()
    if out.exists():
        raise SystemExit("Refuse existing qualification directory")
    out.mkdir(parents=True)
    os.environ.update(DOTNET_PROCESSOR_COUNT="1", DOTNET_CLI_HOME=str(out / "dotnet-home"),
                      DOTNET_CLI_TELEMETRY_OPTOUT="1", DOTNET_NOLOGO="1")
    packed = args.packed_archive is not None
    archive_path = args.packed_archive if packed else args.baseline_archive
    staged = out / ("actual-source-package" if packed else "source-projection")
    with zipfile.ZipFile(archive_path) as archive:
        archive.extractall(staged)
    # Read actual package destinations, not a second hand-authored projection list.
    projected = []
    project = ET.parse(ROOT / "FS.GG.Templates.csproj")
    for item in project.findall(".//None"):
        source = item.attrib.get("Include", "")
        if source.startswith("template/project-knowledge/") and "/.template.config/" not in source:
            for destination in item.attrib["PackagePath"].split(";"):
                target = staged / destination / Path(source).name
                if not packed:
                    target.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copyfile(ROOT / source, target)
                assert target.read_bytes() == (ROOT / source).read_bytes()
                projected.append(str(target.relative_to(staged)))
    assert len(projected) == 14, "CI projection omitted an owned family or legacy member"
    configs = [ROOT / f"templates/fs-gg-{x}/.template.config/template.json" for x in ("console", "web", "fable-bindings", "python", "fable-game")]
    configs.append(ROOT / "pack/fs-gg-fable-game-legacy/.template.config/template.json")
    for config in configs:
        family = config.parents[1].name
        target = staged / "content/templates" / family / ".template.config/template.json"
        if not packed:
            shutil.copyfile(config, target)
        assert target.read_bytes() == config.read_bytes()
    overlay_config = ROOT / "template/project-knowledge/.template.config/template.json"
    target = staged / "content/templates/fs-gg-project-knowledge/.template.config/template.json"
    if not packed:
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(overlay_config, target)
    assert target.read_bytes() == overlay_config.read_bytes()
    workflow = (ROOT / "template/project-knowledge/.github/workflows/project-knowledge.yml").read_text()
    # This literal linear workflow has no dependency graph or YAML expressions.
    # Check its actual trigger, permission and call ordering without installing a parser.
    assert re.search(r"^on:\n  pull_request:\n  push:", workflow, re.MULTILINE)
    assert "pull_request_target" not in workflow
    assert re.search(r"^permissions:\n  contents: read\n", workflow, re.MULTILINE)
    assert re.search(r"^jobs:\n  project-knowledge:\n", workflow, re.MULTILINE)
    assert "persist-credentials: false" in workflow and "timeout-minutes: 5" in workflow
    assert workflow.index(" --preflight") < workflow.index("dotnet tool restore") < workflow.rindex("run: python3 scripts/check-project-knowledge.py")
    assert "--command-json" not in workflow, "Ordinary CI must not substitute a candidate CLI"
    invoke(["dotnet", "new", "install", str(staged / "content/templates")])
    families = [(x, {}) for x in ("console", "web", "fable-bindings", "python")]
    families += [("fable-game", {"bundle": "player"}), ("fable-game-legacy", {"svgFoundation": "false"})]
    receipt = {"schema": "fsgg.knowledge-product-ci-source-projection/1", "artifactKind": "actual-source-packed-archive" if packed else "explicit-source-projection-fixture",
               "packedArchiveQualified": packed, "published": False,
               "archiveSha256": hashlib.sha256(archive_path.read_bytes()).hexdigest(),
               "centralAssetCensus": projected,
               "projectSha256": hashlib.sha256((ROOT / "FS.GG.Templates.csproj").read_bytes()).hexdigest(),
               "assetSha256": {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in (ROOT / "template/project-knowledge").rglob("*") if p.is_file() and "__pycache__" not in p.parts},
               "emission": [], "entry": []}
    for family, params in families:
        for lane in ("none", "sdd", "typed-sdd", "spec-kit", "omitted"):
            root = out / "generated" / (family + "-" + lane)
            template = "fs-gg-fable-game" if family == "fable-game-legacy" else "fs-gg-" + family
            command = ["dotnet", "new", template, "-o", str(root), "--productName", "KnowledgeCi"]
            if lane != "omitted":
                command += ["--lifecycle", lane]
            for key, value in params.items():
                command += ["--" + key, value]
            invoke(command)
            effective = "typed-sdd" if family == "fable-game" and lane == "omitted" else "sdd" if lane == "omitted" else lane
            emitted = effective == "typed-sdd"
            for path in (".github/workflows/project-knowledge.yml", "scripts/check-project-knowledge.py"):
                assert (root / path).is_file() == emitted, f"Wrong typed-only emission: {family}/{lane}/{path}"
                if emitted:
                    assert (root / path).read_bytes() == (ROOT / "template/project-knowledge" / path).read_bytes()
            assert not (root / ".fsgg/knowledge").exists(), "CI projection must not impersonate SDD initialization"
            receipt["emission"].append({"family": family, "selection": lane, "effectiveLifecycle": effective, "emitted": emitted})
    receipt["overlay"] = []
    from receiver import snapshot
    for lane in ("none", "sdd", "typed-sdd", "spec-kit", "omitted"):
        root = out / "overlay" / lane
        root.mkdir(parents=True)
        (root / "product.txt").write_text("authored external Rendering product bytes\n")
        before = snapshot(root)
        command = ["dotnet", "new", "fs-gg-project-knowledge", "-o", str(root)]
        if lane != "omitted":
            command += ["--lifecycle", lane]
        invoke(command)
        emitted = lane == "typed-sdd"
        assert all(snapshot(root).get(path) == digest for path, digest in before.items())
        for path in (".github/workflows/project-knowledge.yml", "scripts/check-project-knowledge.py"):
            assert (root / path).is_file() == emitted
            if emitted:
                assert (root / path).read_bytes() == (ROOT / "template/project-knowledge" / path).read_bytes()
        receipt["overlay"].append({"selection": lane, "emitted": emitted, "originalProductBytesPreserved": True})
    conflict = out / "overlay/owner-conflict"
    (conflict / ".github/workflows").mkdir(parents=True)
    (conflict / ".github/workflows/project-knowledge.yml").write_text("authored owner workflow\n")
    (conflict / "product.txt").write_text("authored Rendering bytes\n")
    before = snapshot(conflict)
    refused = invoke(["dotnet", "new", "fs-gg-project-knowledge", "-o", str(conflict), "--lifecycle", "typed-sdd"], success=False)
    assert snapshot(conflict) == before, "Overlay conflict must preserve all owner bytes and add no files"
    receipt["overlay"].append({"case": "authored-workflow-no-force-refusal", "exit": refused.returncode, "allOwnerBytesPreserved": True})
    for index, original in enumerate(args.external_receiver):
        root = out / "external-overlay" / str(index)
        shutil.copytree(original, root, ignore=shutil.ignore_patterns(".git"))
        before = snapshot(root)
        invoke(["dotnet", "new", "fs-gg-project-knowledge", "-o", str(root), "--lifecycle", "typed-sdd"])
        after = snapshot(root)
        assert all(after.get(path) == digest for path, digest in before.items())
        added = set(after) - set(before)
        assert added == {".github/workflows/project-knowledge.yml", "scripts/check-project-knowledge.py"}
        for path in added:
            assert (root / path).read_bytes() == (ROOT / "template/project-knowledge" / path).read_bytes()
        (root / ".github/workflows/project-knowledge.yml").write_text("authored external workflow\n")
        authored = snapshot(root)
        refused = invoke(["dotnet", "new", "fs-gg-project-knowledge", "-o", str(root), "--lifecycle", "typed-sdd"], success=False)
        assert snapshot(root) == authored
        receipt["overlay"].append({"case": "actual-external-product-" + original.name, "originalFileCount": len(before), "addedPaths": sorted(added), "allOriginalOwnerBytesPreserved": True, "authoredConflictExit": refused.returncode})
    real = out / "actual-product-entry"
    shutil.copytree(args.real_receiver, real, ignore=shutil.ignore_patterns(".git"))
    script = out / "generated/console-typed-sdd/scripts/check-project-knowledge.py"
    prefix = [sys.executable, str(script), "--root", str(real)]
    manifest = real / ".config/dotnet-tools.json"
    original_manifest = manifest.read_bytes()
    manifest_value = json.loads(original_manifest)
    manifest_value["tools"]["fs.gg.sdd.cli"]["version"] = "2.1.0"
    manifest.write_text(json.dumps(manifest_value))
    receipt["qualificationManifestOverride"] = {"pinnedVersion": "2.1.0", "published": False, "purpose": "Explicit stable candidate floor; source prefix supplied separately"}
    invoke(prefix + ["--preflight"])
    for version in ("2.0.3", "2.1.0-preview.1"):
        manifest_value["tools"]["fs.gg.sdd.cli"]["version"] = version
        manifest.write_text(json.dumps(manifest_value))
        refused = invoke(prefix + ["--preflight"], success=False)
        assert "stable knowledge-capable version >= 2.1.0" in refused.stderr
        receipt["entry"].append({"case": "incapable-or-prerelease-manifest-" + version, "exit": refused.returncode})
    manifest_value["tools"]["fs.gg.sdd.cli"]["version"] = "2.1.0"
    manifest.write_text(json.dumps(manifest_value))
    started = time.monotonic()
    good = invoke(prefix + ["--command-json", args.candidate_command_json])
    receipt["entry"].append({"case": "actual-generated-product-valid", "result": json.loads(good.stdout), "elapsedMilliseconds": round((time.monotonic() - started) * 1000)})
    schema = real / ".fsgg/knowledge/schema.json"
    original = schema.read_bytes()
    total = sum(p.stat().st_size for p in (real / ".fsgg/knowledge").rglob("*") if p.is_file())
    schema.write_bytes(original + b" " * (10485760 - total))
    at_limit = invoke(prefix + ["--command-json", args.candidate_command_json])
    assert json.loads(at_limit.stdout)["bytes"] == 10485760
    receipt["entry"].append({"case": "disk-bypass-exact-limit", "result": json.loads(at_limit.stdout)})
    schema.write_bytes(schema.read_bytes() + b" ")
    over = invoke(prefix + ["--command-json", args.candidate_command_json], success=False)
    assert "byte budget exceeded" in over.stderr.lower()
    receipt["entry"].append({"case": "disk-bypass-over-limit", "exit": over.returncode})
    schema.write_bytes(original)
    unavailable = invoke(prefix + ["--command-json", args.public203_command_json], success=False)
    assert "unknownCommand" in unavailable.stderr
    receipt["entry"].append({"case": "actual-public-2.0.3-incapable", "exit": unavailable.returncode})
    guide = real / ".fsgg/knowledge-guide.md"
    guide.rename(guide.with_suffix(".saved"))
    missing = invoke(prefix + ["--preflight"], success=False)
    assert "Missing .fsgg/knowledge-guide.md" in missing.stderr
    receipt["entry"].append({"case": "missing-capture-guide", "exit": missing.returncode})
    guide.with_suffix(".saved").rename(guide)
    schema.rename(schema.with_suffix(".saved"))
    missing = invoke(prefix + ["--preflight"], success=False)
    assert "Missing .fsgg/knowledge/schema.json" in missing.stderr
    receipt["entry"].append({"case": "missing-canonical-schema", "exit": missing.returncode})
    schema.with_suffix(".saved").rename(schema)
    manifest = real / ".config/dotnet-tools.json"
    saved_manifest = manifest.read_bytes()
    manifest.write_text('{"version":1,"isRoot":true,"tools":{}}')
    missing = invoke(prefix + ["--preflight"], success=False)
    assert "must pin FS.GG.SDD.Cli" in missing.stderr
    receipt["entry"].append({"case": "missing-local-tool-pin", "exit": missing.returncode})
    manifest.write_bytes(original_manifest)
    (out / "receipt.json").write_text(json.dumps(receipt, indent=2) + "\n")
    print("PASS 30 family emission cells, five overlay lifecycle cells, no-force owner conflict and nine actual CI entry controls")


if __name__ == "__main__":
    main()
