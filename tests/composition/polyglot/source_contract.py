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
        require(hashlib.sha256(authored[name].read_text(encoding="utf-8-sig").encode()).hexdigest() == row["sha256"], "skill body digest differs: " + name)
        match = re.fullmatch(r"template in \[(.*?)\]", row["materializes-when"])
        require(match is not None, "unsupported skill selection")
        expected = {"content/templates/fs-gg-" + value.strip() + "/.agents/skills/" + name + "/" for value in match[1].split(",")}
        require(set(packed.get(source, [])) == expected, "skill package destinations differ: " + name)
    for provider in PROVIDERS:
        directory = root / "templates" / ("fs-gg-" + provider + "-cli")
        config = json.loads((directory / ".template.config/template.json").read_text())
        require(config["shortName"] == "fs-gg-" + provider + "-cli", "provider identity differs")
        for key in ("rawName", "packageIdentity", "codeIdentifier"):
            require(config["symbols"][key]["isRequired"] is True, "required identity missing: " + provider + ":" + key)
        require(not (directory / ".fsgg").exists(), "provider writes reserved SDD tree")
        require(not any(path.is_symlink() for path in directory.rglob("*")), "linked product source")
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

def validate_archive(root, archive):
    rows = validate_source(root)
    root = Path(root)
    expected = {}
    for provider in PROVIDERS:
        relative = "templates/fs-gg-" + provider + "-cli"
        for path in (root / relative).rglob("*"):
            if path.is_file():
                if any(part in ("node_modules", "target", "dist", "artifacts", ".nuget", "bin", "obj") for part in path.relative_to(root / relative).parts):
                    continue
                expected["content/" + str(path.relative_to(root))] = path.read_bytes()
    for row in rows:
        for provider in PROVIDERS:
            if provider + "-cli" in row["materializes-when"].removeprefix("template in [").removesuffix("]").split(", "):
                expected["content/templates/fs-gg-" + provider + "-cli/.agents/skills/" + row["id"] + "/SKILL.md"] = (root / row["supplied-by"] / "SKILL.md").read_bytes()
    for provider in PROVIDERS:
        expected["content/templates/fs-gg-" + provider + "-cli/.agents/skills/skill-manifest.json"] = (root / "template/skill-manifest/skill-manifest.json").read_bytes()
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
