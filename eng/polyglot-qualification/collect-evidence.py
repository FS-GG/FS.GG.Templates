"""Compose the qualification evidence record (fsgg.polyglot-qualification-evidence/v1) for ONE attempt.

Every field is read from the original artifacts of the attempt or observed in the carrier at collection
time; nothing is typed in. The record binds the archive bytes, the carrier, the independent inputs and the
per-product Governance Verify outcomes. It is evidence for an independent reviewer and for root acceptance,
not an admission: `acceptance` stays null until a recorded root decision names this archive digest.

usage: collect-evidence.py <carrier-root> <attempt-name> <archive.nupkg> <output.json>
"""
import hashlib, json, subprocess, sys, zipfile
from pathlib import Path

root, attempt, archive, output = Path(sys.argv[1]), sys.argv[2], Path(sys.argv[3]), Path(sys.argv[4])
work = root / "work"
run = work / attempt
sha = lambda data: hashlib.sha256(data).hexdigest()
fsha = lambda path: sha(Path(path).read_bytes())

def carrier(*argv):
    command = ["podman", "--root", str(root / "containers"), "--runroot", str(root / "runroot"), "--storage-driver", "vfs",
               "run", "--rm", "-v", str(work) + ":/w:ro", "--rootfs", str(root / "rootfs/arch"), *argv]
    return subprocess.run(command, capture_output=True, text=True, check=True).stdout.strip()

archive_bytes = archive.read_bytes()
with zipfile.ZipFile(archive) as package:
    entries = sorted((info.filename, sha(package.read(info))) for info in package.infolist() if not info.is_dir())
    nuspec = next(package.read(name).decode() for name, _ in entries if name.endswith(".nuspec"))
commit = nuspec.split('commit="')[1].split('"')[0]
entry_manifest = "".join("%s  %s\n" % (digest, name) for name, digest in entries)
stripped = "".join("%s  %s\n" % (digest, name) for name, digest in entries if not name.endswith(".nuspec"))

pacman = lambda *names: {name: carrier("pacman", "-Q", name).split()[1] for name in names}
sources = dict(line.split("=") for line in (work / "advisory-sources.env").read_text().split())
products = []
for provider in ("typescript-cli", "javascript-cli", "rust-cli", "go-cli"):
    private = run / provider
    acceptance = json.loads((private / "catalog-acceptance" / "acceptance.json").read_text())
    verify = json.loads((private / "verify.json").read_text())
    gates = sorted(verify.get("passing", []) + verify.get("blockers", []), key=lambda g: g["id"]["gate"])
    products.append({
        "provider": provider,
        "catalogCases": [{"name": c["name"], "passed": c["passed"]} for c in acceptance["cases"]],
        "catalogAcceptancePassed": acceptance["passed"] and acceptance["casesPassed"],
        "catalogAcceptanceSha256": fsha(private / "catalog-acceptance" / "acceptance.json"),
        "provenanceSha256": fsha(private / "catalog-acceptance" / "positive-target" / ".fsgg" / "scaffold-provenance.json"),
        "governanceVerdict": verify["verdict"],
        "governanceProfile": sorted({g["enforcement"]["profile"] for g in gates})[0],
        "gates": [{"capability": g["id"]["gate"], "disposition": g["execution"]["disposition"],
                   "exitCode": g["execution"]["exitCode"], "passed": g["execution"]["passed"]} for g in gates],
        "verifyJsonSha256": fsha(private / "verify.json"),
        "securityReportsSha256": {str(p.relative_to(private / "catalog-acceptance" / "positive-target")): fsha(p)
                                  for p in sorted((private / "catalog-acceptance" / "positive-target").glob("artifacts/*-work/security-audit.json"))},
    })
record = {
    "schema": "fsgg.polyglot-qualification-evidence/v1",
    "archive": {"file": archive.name, "sha256": sha(archive_bytes), "bytes": len(archive_bytes), "sourceCommit": commit,
                "entries": len(entries), "entryManifestSha256": sha(entry_manifest.encode()),
                "entryManifestWithoutNuspecSha256": sha(stripped.encode()),
                "note": "zip entry timestamps differ between packs; entry content digests are the reproducible identity"},
    "carrier": {
        "kind": "rootless podman --rootfs on the fdev host", "kernel": carrier("uname", "-r"),
        "glibc": carrier("sh", "-c", "ldd --version | head -1"), "image": [l for l in (Path(__file__).parent / "pins.env").read_text().splitlines() if l.startswith(("ARCH_IMAGE=", "ARCH_SNAPSHOT="))],
        "packages": pacman("glibc", "gcc", "python", "cargo-audit", "govulncheck", "rustup", "git"),
        "toolVersions": {"dotnet": carrier("/opt/dotnet/dotnet", "--list-runtimes").splitlines(), "dotnetSdk": carrier("/opt/dotnet/dotnet", "--list-sdks"),
                         "node": carrier("/opt/node/bin/node", "--version"), "npm": carrier("/opt/node/bin/node", "-p", "require('/opt/node/lib/node_modules/npm/package.json').version"),
                         "go": carrier("sh", "-c", "/opt/go-*/go/bin/go version"), "rustc": carrier("sh", "-c", "/opt/q1/rustup/toolchains/*/bin/rustc --version"),
                         "gcc": carrier("sh", "-c", "/usr/bin/gcc --version | head -1"), "cargo-audit": carrier("/usr/bin/cargo-audit", "--version"),
                         "govulncheck": carrier("/usr/bin/govulncheck", "-version", "-db", "file:///opt/q1/advisory/go-db").splitlines()[0]},
        "binarySha256": {name: carrier("sha256sum", path).split()[0] for name, path in
                         (("python", "/usr/bin/python3.14"), ("cargo-audit", "/usr/bin/cargo-audit"), ("govulncheck", "/usr/bin/govulncheck"), ("gcc", "/usr/bin/x86_64-pc-linux-gnu-gcc"))},
        "cpuLimit": "taskset -c 0-3 (4 CPUs)",
    },
    "inputs": {
        "catalogPolicySha256": fsha(work / "policy.json"),
        "governanceWorkspaceCatalogSha256": {p.name: fsha(p) for p in sorted((work / "gov-catalog").glob("*.yml"))},
        "catalogSha256": fsha(work / "stage" / "catalog-first.json"),
        "sddCli": {"package": "FS.GG.SDD.Cli", "nupkgSha256": fsha(next((root / "dl").glob("fs.gg.sdd.cli.*.nupkg")))},
        "governanceCli": {"package": "FS.GG.Governance.Cli", "nupkgSha256": fsha(next((root / "dl").glob("fs.gg.governance.cli.*.nupkg")))},
        "sddDriverSourceCommit": subprocess.run(["git", "-C", str(root / "sdd-src"), "rev-parse", "HEAD"], capture_output=True, text=True, check=True).stdout.strip(),
        "advisory": {"rustsec": {"commit": sources["RUST_ADVISORY_COMMIT"], "epoch": int(sources["RUST_ADVISORY_EPOCH"]), "manifestSha256": carrier("sha256sum", "/opt/q1/advisory/rust.manifest").split()[0]},
                     "goVulnDb": {"commit": sources["GO_ADVISORY_COMMIT"], "epoch": int(sources["GO_ADVISORY_EPOCH"]), "manifestSha256": carrier("sha256sum", "/opt/q1/advisory/go.manifest").split()[0]}},
        "consumerScriptSha256": fsha(Path(__file__).resolve().parents[2] / "scripts/polyglot/qualify-once-packed.sh"),
    },
    "products": products,
    "verdict": "pass" if all(p["catalogAcceptancePassed"] and p["governanceVerdict"] == "pass" and len(p["gates"]) == 8
                              and all(g["passed"] for g in p["gates"]) for p in products) else "fail",
    "acceptance": None,
}
with output.open("x") as stream:
    json.dump(record, stream, indent=2)
    stream.write("\n")
print(record["verdict"])
