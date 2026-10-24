"""Mechanical source/archive closure checks; public typed SDD owns catalog semantics."""
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import xml.etree.ElementTree as ET
import zipfile

PROVIDERS = ("typescript", "javascript", "rust", "go")

def require(condition, detail):
    if not condition:
        raise ValueError(detail)

def validate_source(root):
    root = Path(root)
    rows = json.loads((root / "template/skill-manifest/skill-manifest.json").read_text())["skills"]
    require(len(rows) == len({row["id"] for row in rows}), "duplicate skill row")
    authored = {path.parent.name: path for path in (root / "template/product-skills").glob("*/SKILL.md")}
    require(set(authored) == {row["id"] for row in rows}, "authored/manifest skill set differs")
    project = ET.parse(root / "FS.GG.Templates.csproj").getroot()
    packed = {node.attrib["Include"]: node.attrib.get("PackagePath", "").split(";")
              for node in project.iter("None") if node.attrib.get("Pack") == "true" and node.attrib.get("Include", "").startswith("template/product-skills/")}
    for row in rows:
        name = row["id"]
        source = "template/product-skills/" + name + "/SKILL.md"
        require(row["scope"] == "product" and row["supplied-by"] == "template/product-skills/" + name + "/", "skill ownership differs: " + name)
        require(hashlib.sha256(authored[name].read_bytes().decode("utf-8-sig").encode("utf-8")).hexdigest() == row["sha256"], "skill body digest differs: " + name)
        match = re.fullmatch(r"template in \[(.*?)\]", row["materializes-when"])
        require(match is not None, "unsupported skill selection")
        expected = {"content/templates/fs-gg-" + value.strip() + "/.agents/skills/" + name + "/" for value in match[1].split(",")}
        require(set(packed.get(source, [])) == expected, "skill package destinations differ: " + name)
    security_source = (root / 'template/polyglot-common/security.sh').read_text()
    require(security_source.count('scripts/security-result.py --single "$FSGG_POLYGLOT_PROVIDER" security-audit.json') == 2,
            'actual security paths must enforce strict raw findings before handoff')
    node_source = (root / 'template/polyglot-common/node-build.sh').read_text()
    for name, text in (('node-build.sh', node_source), ('security.sh', security_source)):
        # Observed with npm 11.19.0: one /dev/null file loaded as both user and global config is refused.
        require('--globalconfig=/dev/null' not in text and '--userconfig=/dev/null' not in text,
                'npm user/global configuration must be distinct files: ' + name)
    for provider in PROVIDERS:
        directory = root / "templates" / ("fs-gg-" + provider + "-cli")
        config = json.loads((directory / ".template.config/template.json").read_text())
        require(config["shortName"] == "fs-gg-" + provider + "-cli", "provider identity differs")
        for key in ("rawName", "packageIdentity", "codeIdentifier"):
            require(config["symbols"][key]["isRequired"] is True, "required identity missing: " + provider + ":" + key)
        operations_source = (directory / 'scripts/operations.sh').read_text()
        require('. "$work/scripts/security.sh"' in operations_source
                and operations_source.index('. "$work/scripts/security.sh"') < operations_source.index('case "$operation" in')
                and operations_source.index('case "$operation" in') < operations_source.index("printf '{"),
                'product security binding must precede real handoff')
        require(not (directory / ".fsgg").exists(), "provider writes reserved SDD tree")
        require(not any(path.is_symlink() for path in directory.rglob("*")), "linked product source")
        require(all(path.is_dir() or path.is_file() for path in directory.rglob("*")), "non-regular product source")
        require("artifacts" in " ".join(config["sources"][0]["exclude"]), "artifact exclusion missing")
        if provider in ("typescript", "javascript"):
            package = json.loads((directory / "package.json").read_text())
            lock = json.loads((directory / "package-lock.json").read_text())
            require(lock["packages"][""]["devDependencies"] == package["devDependencies"], "Node dependency lock differs")
            require(lock["packages"]["node_modules/typescript"]["integrity"].startswith("sha512-"), "Node compiler integrity missing")
            config = json.loads((directory / "tsconfig.json").read_text())["compilerOptions"]
            require(config["strict"] is True, "strict checker required")
            if provider == "typescript":
                require((directory / "src/main.ts").is_file() and not (directory / "src/main.js").exists(), "TypeScript source contract collapsed")
            else:
                require((directory / "src/main.js").is_file() and config["checkJs"] is True and config["noEmit"] is True, "JavaScript ESM/checkJs contract collapsed")
                require(package["type"] == "module", "JavaScript ESM missing")
        elif provider == "rust":
            require((directory / "Cargo.lock").is_file(), "Cargo lock missing")
            require("forbid(unsafe_code)" in (directory / "src/main.rs").read_text(), "Rust safety floor missing")
        else:
            require((directory / "go.mod").read_text().startswith("module example.org/polyglot/product\n"), "explicit Go module missing")
            require(not (directory / "go.sum").exists(), "stdlib-only source has unexplained dependency checksum")
    return rows

def expected_archive_members(root):
    """Mechanical projection of actual csproj entries, never a second catalog policy."""
    root = Path(root)
    expected = {}
    prefixes = tuple("content/templates/fs-gg-" + p + "-cli/" for p in PROVIDERS)
    def add(name, data):
        require(name not in expected, "duplicate projected product member: " + name)
        expected[name] = data
    for provider in PROVIDERS:
        relative = "templates/fs-gg-" + provider + "-cli"
        for path in (root / relative).rglob("*"):
            if path.is_file():
                if any(part in ("node_modules", "target", "dist", "artifacts", ".nuget", "bin", "obj") for part in path.relative_to(root / relative).parts):
                    continue
                add("content/" + path.relative_to(root).as_posix(), path.read_bytes())
    project = ET.parse(root / "FS.GG.Templates.csproj").getroot()
    for node in project.iter("None"):
        if node.attrib.get("Pack") != "true":
            continue
        source = node.attrib.get("Include", "")
        for destination in node.attrib.get("PackagePath", "").split(";"):
            if destination.startswith(prefixes):
                require("$(" not in source and "*" not in source, "unsupported product projection")
                path = root / source
                require(path.is_file() and not path.is_symlink(), "missing/linked projected product source")
                name = destination + path.name if destination.endswith("/") else destination
                add(name, path.read_bytes())
    return expected

def validate_archive(root, archive):
    validate_source(root)
    root = Path(root)
    expected = expected_archive_members(root)
    # Raw byte join only. Catalog policy/version/digests remain the public SDK producer's authority.
    expected["content/providers/polyglot.catalog.json"] = (root / "providers/polyglot.catalog.json").read_bytes()
    with zipfile.ZipFile(archive) as package:
        infos = package.infolist()
        require(len(infos) == len({info.filename for info in infos}), "duplicate package member")
        require(len(infos) <= 16384 and sum(info.file_size for info in infos) <= 64 * 1048576, "package inventory bound exceeded")
        for info in infos:
            name = PurePosixPath(info.filename)
            require(not name.is_absolute() and ".." not in name.parts and "\\" not in info.filename, "unsafe package member")
        actual = {info.filename for info in infos if any(info.filename.startswith("content/templates/fs-gg-" + p + "-cli/") for p in PROVIDERS)}
        require(actual == set(expected) - {"content/providers/polyglot.catalog.json"}, "four-provider package inventory differs")
        for name, data in expected.items():
            require(package.read(name) == data, "package/source bytes differ: " + name)
    return {"archiveSha256": hashlib.sha256(Path(archive).read_bytes()).hexdigest(), "providerCount": 4,
            "state": "source-and-package-closure-only; no product/catalog runtime qualification"}
