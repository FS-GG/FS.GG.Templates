"""Author the catalog admission policy for the qualification carrier (runs INSIDE the carrier).

The policy binds the exact tool versions the catalog declares to absolute executables and to the literal
output those executables print. Each probe is executed once here; its output must contain the pinned
version, and the text around the version becomes the policy's prefix/suffix. Nothing here widens a
version: a different tool version changes the output and the scaffold refuses it.

usage: make-policy.py <output-file> <go-version>
"""
import hashlib, json, subprocess, sys

output, go_version = sys.argv[1:3]
RUST = "/opt/q1/rustup/toolchains/1.98.1-x86_64-unknown-linux-gnu/bin/"
PROBES = [
    ("python", "/usr/bin/python3.14", ["--version"], "3.14.8"),
    ("node", "/opt/node/bin/node", ["--version"], "24.20.0"),
    ("npm", "/opt/node/bin/node", ["-p", "require('/opt/node/lib/node_modules/npm/package.json').version"], "11.19.0"),
    ("typescript", "/opt/node/bin/node", ["-p", "require('/opt/q1/ts/node_modules/typescript/package.json').version"], "5.9.2"),
    ("rustc", RUST + "rustc", ["--version"], "1.98.1"),
    ("cargo", RUST + "cargo", ["--version"], "1.98.1"),
    ("cargo-audit", "/usr/bin/cargo-audit", ["--version"], "0.22.2"),
    ("go", "/opt/go-%s/go/bin/go" % go_version, ["version"], go_version),
    ("govulncheck", "/usr/bin/govulncheck", ["-version", "-db", "file:///opt/q1/advisory/go-db"], "1.9.0"),
]
# npm and TypeScript are read from their package manifests: running their CLIs writes a Node compile
# cache into the scaffold's private root, which exhausts SDD's 8 MiB cumulative snapshot budget.
probes = []
for identity, executable, arguments, version in PROBES:
    text = subprocess.run([executable] + arguments, capture_output=True, text=True, check=True).stdout
    if text.count(version) != 1:
        raise SystemExit("probe %s does not print exactly one %s: %r" % (identity, version, text))
    prefix, suffix = text.split(version)
    probes.append(dict(id=identity, executable=executable, arguments=arguments, versionPrefix=prefix,
                       versionSuffix=suffix, maximumOutputCharacters=512))
mappings = [{"format": "fsgg.governance-handoff@2.0.0", "id": "fsgg.governance-handoff", "version": "2.0.0"}]
mapping_bytes = ("[" + ",".join('{"format":%s,"id":%s,"version":%s}' % (json.dumps(m["format"]), json.dumps(m["id"]), json.dumps(m["version"])) for m in mappings) + "]").encode()
operations = ["build", "lint", "test", "public-surface", "package", "security", "evidence", "release"]
policy = {
    "schemaVersion": 1, "id": "fs-gg-polyglot-qualification-policy", "version": "1.0.0",
    "evidenceMap": {"id": "fsgg-polyglot-evidence-map", "version": "1.0.0",
                    "digest": "sha256:" + hashlib.sha256(mapping_bytes).hexdigest(), "mappings": mappings},
    "requiredCapabilityIds": [o + ":" + o for o in operations], "semanticOnlyCapabilityIds": [],
    "knownPlatforms": ["linux-x64"], "environments": [{"id": "polyglot-local", "environment": "local"}],
    "supportedEvidenceFormats": [{"id": "fsgg.governance-handoff", "version": "2.0.0"}],
    "maximumPreflightSeconds": 120, "maximumScaffoldSeconds": 240, "toolProbes": probes,
    "archives": [{"templateSource": "FS.GG.Workspace.Template::0.20.1", "packageId": "FS.GG.Workspace.Template", "packageVersion": "0.20.1"}],
}
with open(output, "x") as stream:
    json.dump(policy, stream, indent=2)
    stream.write("\n")
