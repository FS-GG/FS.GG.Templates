"""Create real products serially using exact caller-bound archives and a frozen source CLI."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess

from candidate import probe
from receiver import ROOT, call, inventory, snapshot


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--command-json", required=True)
    parser.add_argument("--workspace-013", type=Path, required=True)
    parser.add_argument("--workspace-candidate", type=Path, required=True)
    parser.add_argument("--rendering-031", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--families", help="Comma-separated bounded replay selection")
    parser.add_argument("--routes", help="Comma-separated bounded replay selection")
    args = parser.parse_args()
    command = json.loads(args.command_json)
    out = args.output.resolve()
    out.mkdir(parents=True, exist_ok=True)
    os.environ.update(DOTNET_PROCESSOR_COUNT="1", DOTNET_CLI_HOME=str(out / "dotnet-home"),
                      DOTNET_CLI_TELEMETRY_OPTOUT="1", DOTNET_NOLOGO="1", DOTNET_SKIP_FIRST_TIME_EXPERIENCE="1")
    rows = {row["provider"]: row for row in inventory()}
    cases = [(name, "default-product", {}) for name in ("console", "web", "fable-bindings", "python")]
    cases += [("fable-game", "player", {"bundle": "player"}), ("fable-game", "complete", {"bundle": "complete"}),
              ("fable-game", "legacy", {"svgFoundation": "false"}), ("rendering", "app", {"profile": "app"}),
              ("rendering", "game", {"profile": "game"})]
    archive_map = {name: args.workspace_013.resolve() for name in ("console", "web", "fable-bindings")}
    archive_map.update(python=args.workspace_candidate.resolve(), **{"fable-game": args.workspace_candidate.resolve(), "rendering": args.rendering_031.resolve()})
    receipt = {"schema": "fsgg.knowledge-receiver-candidate-matrix/1", "publishedProducer": False,
               "sourceAcceptance": False, "command": command,
               "archives": [{"path": str(p), "sha256": hashlib.sha256(p.read_bytes()).hexdigest()} for p in set(archive_map.values())], "rows": []}
    for route in ("provider", "direct-plus-generic-initialization"):
        if args.routes and route not in args.routes.split(","):
            continue
        for family, variant, parameters in cases:
            if args.families and family not in args.families.split(","):
                continue
            case = f"{route}-{family}-{variant}"
            root = out / "receivers" / case
            if root.exists():
                raise SystemExit(f"refuse existing receiver: {root}")
            root.mkdir(parents=True)
            os.environ["DOTNET_CLI_HOME"] = str(out / "dotnet-homes" / case)
            archive = archive_map[family]
            row = {"route": route, "family": family, "variant": variant, "descriptorSource": rows[family]["source"],
                   "testedArchive": str(archive), "receiver": str(root), "effectiveSelection": "typed-sdd"}
            receipt["rows"].append(row)
            try:
                params = {"productName": "KnowledgeReceiver", **parameters}
                if route == "provider":
                    (root / ".fsgg").mkdir()
                    text = (ROOT / rows[family]["descriptor"]).read_text()
                    text = re.sub(r"(?m)^(    source:)\s*\S+", lambda m: m[1] + " " + str(archive), text)
                    (root / ".fsgg/providers.yml").write_text(text)
                    scaffold_args = ["scaffold", "--root", str(root), "--provider", family, "--param", "lifecycle=typed-sdd", "--no-update", "--json"]
                    for key, value in params.items():
                        scaffold_args += ["--param", f"{key}={value}"]
                    report = call(command, *scaffold_args)
                    (out / (case + ".scaffold.json")).write_text(json.dumps(report, indent=2))
                    assert report["outcome"] == "succeeded", report["diagnostics"]
                    effective = {x["key"]: x["value"] for x in report["scaffold"]["effectiveParameters"]}
                    assert effective["lifecycle"] == "typed-sdd"
                    row["effectiveParameters"] = effective
                    row["automaticTypedKnowledge"] = True
                else:
                    install = subprocess.run(["dotnet", "new", "install", str(archive), "--force"], capture_output=True, text=True)
                    assert install.returncode == 0, install.stdout + install.stderr
                    direct = ["dotnet", "new", rows[family]["template"], "-o", str(root), "--lifecycle", "typed-sdd"]
                    for key, value in params.items():
                        direct += ["--" + key, value]
                    result = subprocess.run(direct, capture_output=True, text=True)
                    assert result.returncode == 0, result.stdout + result.stderr
                    assert not (root / ".fsgg/knowledge").exists(), "raw template unexpectedly owns knowledge"
                    product_before = snapshot(root)
                    init = subprocess.run(command + ["init", "--root", str(root), "--json"], capture_output=True, text=True)
                    if init.returncode:
                        refused = json.loads(init.stdout)
                        assert refused["outcome"] == "blocked"
                        assert refused["diagnostics"] and all(x["id"] == "unsafeOverwrite" and x["artifact"] == ".gitignore" for x in refused["diagnostics"])
                        after_refusal = snapshot(root)
                        assert all(after_refusal.get(path) == digest for path, digest in product_before.items()), "refused generic init overwrote raw product"
                        row["genericInit"] = "refused product-owned .gitignore; original product bytes preserved"
                        row["genericInitAddedPaths"] = sorted(after_refusal.keys() - product_before.keys())
                    else:
                        assert json.loads(init.stdout)["outcome"] in {"succeeded", "noChange"}
                        row["genericInit"] = "succeeded"
                    assert not (root / ".fsgg/knowledge").exists(), "generic init silently changed knowledge applicability"
                    with (root / ".gitignore").open("a") as stream:
                        stream.write("\n# Authored broad ignore control\n.fsgg/\n")
                    call(command, "knowledge", "initialize", "--root", str(root))
                    after = snapshot(root)
                    for path, digest in product_before.items():
                        if path != ".gitignore":
                            assert after.get(path) == digest, f"init clobbered raw product: {path}"
                    row["automaticTypedKnowledge"] = False
                    row["initializationRecipe"] = ["raw template explicit typed-sdd", row["genericInit"], "explicit standalone knowledge initialize", "normal foreground initial Git add and commit"]
                    row["typedLifecycleActivation"] = "not claimed; generic knowledge initialize does not select lifecycle"
                if family == "fable-game" and variant == "complete":
                    assert (root / "SvgFoundation/Examples/ExternalAuthority/reference.json").is_file()
                if family == "python":
                    assert (root / "python/app.py").is_file(), "candidate package lacks canonical Python projection"
                row["probe"] = probe(command, root, out / "probes" / case)
                row["disposition"] = "passed-candidate-probe"
            except Exception as error:
                row["disposition"] = "failed"
                row["error"] = str(error)
            (out / "receipt.json").write_text(json.dumps(receipt, indent=2) + "\n")
            print(case, row["disposition"], row.get("error", "")[:240], flush=True)
    if any(x["disposition"] != "passed-candidate-probe" for x in receipt["rows"]):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
