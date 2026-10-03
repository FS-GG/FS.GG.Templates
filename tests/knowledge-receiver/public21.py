"""Qualify a fresh public SDD tool against explicitly source-only Templates bytes."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys

from candidate import probe
from receiver import ROOT, call, inventory, snapshot


def run(argv, cwd=None, success=True):
    result = subprocess.run(argv, cwd=cwd, capture_output=True, text=True, timeout=120)
    if (result.returncode == 0) != success:
        raise AssertionError(f"Unexpected outcome: {argv}: {result.stdout}\n{result.stderr}")
    return result


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def ordinary_ci_limits(root):
    """Exercise the ordinary pinned-tool checker without a CLI override."""
    checker = root / "scripts/check-project-knowledge.py"
    argv = [sys.executable, str(checker)]
    schema = root / ".fsgg/knowledge/schema.json"
    original = schema.read_bytes()
    total = sum(p.stat().st_size for p in (root / ".fsgg/knowledge").rglob("*") if p.is_file())
    try:
        schema.write_bytes(original + b" " * (10485760 - total))
        exact = json.loads(run(argv, root).stdout)
        assert exact["bytes"] == 10485760 and exact["sourceCandidateOverride"] is False
        schema.write_bytes(schema.read_bytes() + b" ")
        refused = run(argv, root, success=False)
        assert "byte budget exceeded" in refused.stderr.lower()
        return dict(exactLimit=exact, oneByteOverExit=refused.returncode)
    finally:
        schema.write_bytes(original)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--sdd", type=Path, required=True)
    parser.add_argument("--workspace-archive", type=Path, required=True)
    parser.add_argument("--rendering-archive", type=Path, required=True)
    parser.add_argument("--freshness-receipt", type=Path, required=True)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    out = args.output.resolve()
    out.mkdir(parents=True, exist_ok=False)
    command = [str(args.sdd.resolve())]
    assert run(command + ["--version"]).stdout.strip() == "2.1.0"
    fresh = json.loads(args.freshness_receipt.read_text())
    cli = next(row for row in fresh["packages"] if row["package"] == "fs.gg.sdd.cli")
    installed = next(args.sdd.parent.rglob("FS.GG.SDD.Cli.dll"))
    for name, expected in cli["literalPayloads"].items():
        if name.startswith("tools/net10.0/any/") and name.endswith(".dll"):
            assert digest(installed.parent / name.removeprefix("tools/net10.0/any/")) == expected, name
    assert digest(installed.parent / "FSharp.Core.dll") == fresh["core"]["assets"]["lib/netstandard2.1/FSharp.Core.dll"]
    rows = {row["provider"]: row for row in inventory()}
    cases = [(name, "default", {}) for name in ("console", "web", "fable-bindings", "python")]
    cases += [("fable-game", "player", {"bundle": "player"}),
              ("fable-game", "complete", {"bundle": "complete"}),
              ("fable-game", "legacy", {"svgFoundation": "false"}),
              ("rendering", "app", {"profile": "app"}), ("rendering", "game", {"profile": "game"})]
    receipt = dict(schema="fsgg.templates.public21-source-receiver/1", publishedProducer=True,
                   publishedTemplates=False, protectedActivation=False,
                   templatesSource=run(["git", "rev-parse", "HEAD"], ROOT).stdout.strip(),
                   freshnessReceiptSha256=digest(args.freshness_receipt),
                   producerSource=cli["sourceRevision"], installedCliSha256=digest(installed),
                   runtimeCoreSha256=digest(installed.parent / "FSharp.Core.dll"),
                   archives={"workspace": digest(args.workspace_archive), "rendering": digest(args.rendering_archive)}, rows=[])
    for selection in ("typed-sdd", "omitted"):
        for family, variant, params in cases:
            case = f"{family}-{variant}-{selection}"
            root = out / "receivers" / case
            (root / ".fsgg").mkdir(parents=True)
            os.environ["DOTNET_CLI_HOME"] = str(out / "homes" / case)
            archive = args.rendering_archive if family == "rendering" else args.workspace_archive
            descriptor = ROOT / rows[family]["descriptor"]
            text = re.sub(r"(?m)^(    source:)\s*\S+", lambda m: m[1] + " " + str(archive.resolve()), descriptor.read_text())
            (root / ".fsgg/providers.yml").write_text(text)
            argv = ["scaffold", "--root", str(root), "--provider", family, "--no-update", "--json"]
            for key, value in dict(productName="PublicKnowledgeReceiver", **params).items():
                argv += ["--param", f"{key}={value}"]
            if selection != "omitted":
                argv += ["--param", "lifecycle=typed-sdd"]
            report = call(command, *argv)
            assert report["outcome"] == "succeeded", report
            effective = {x["key"]: x["value"] for x in report["scaffold"]["effectiveParameters"]}
            expected = rows[family]["default"] if selection == "omitted" else selection
            assert effective["lifecycle"] == expected
            row = dict(family=family, variant=variant, selection=selection, effectiveLifecycle=expected,
                       descriptorPath=rows[family]["descriptor"], descriptorSha256=digest(descriptor),
                       descriptorSource=rows[family]["source"], scaffold=report)
            receipt["rows"].append(row)
            if expected == "typed-sdd":
                if family == "rendering":
                    before = snapshot(root)
                    run(["dotnet", "new", "install", str(args.workspace_archive.resolve())])
                    run(["dotnet", "new", "fs-gg-project-knowledge", "-o", str(root), "--lifecycle", "typed-sdd"])
                    after = snapshot(root)
                    assert all(after.get(p) == h for p, h in before.items())
                    assert set(after) - set(before) == {".github/workflows/project-knowledge.yml", "scripts/check-project-knowledge.py"}
                    row["externalOriginalBytesPreserved"] = True
                row["probe"] = probe(command, root, out / "probes" / case)
                checker = root / "scripts/check-project-knowledge.py"
                assert checker.read_bytes() == (ROOT / "template/project-knowledge/scripts/check-project-knowledge.py").read_bytes()
                run([sys.executable, str(checker), "--preflight"], root)
                run(["dotnet", "tool", "restore", "--configfile", str(args.config.resolve()), "--no-cache"], root)
                checked = json.loads(run([sys.executable, str(checker)], root).stdout)
                assert checked["sourceCandidateOverride"] is False and checked["pinnedVersion"] == "2.1.0"
                row["ordinaryLocalToolCi"] = checked
            else:
                assert not (root / ".fsgg/knowledge").exists()
                assert not (root / ".github/workflows/project-knowledge.yml").exists()
            row["outcome"] = "passed"
            (out / "receipt.json").write_text(json.dumps(receipt, indent=2) + "\n")
            print(case, "passed", flush=True)
    receipt["ordinaryLocalToolBudget"] = ordinary_ci_limits(out / "receivers/console-default-typed-sdd")
    (out / "receipt.json").write_text(json.dumps(receipt, indent=2) + "\n")


if __name__ == "__main__":
    main()
