#!/usr/bin/env python3
"""Copy the complete restored public package asset tree for the ordinary Vite build."""
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import shutil
import sys
import zipfile

PACKAGE_SHA256 = "74a11425bfb64c152ffbeab5be2753434e08f55f806e85113cdc25cacbc86fa5"
PREFIX = "contentFiles/any/any/_content/FS.GG.Wasm.Browser/"


def materialize(foundation):
    foundation = Path(foundation).resolve(strict=True)
    assets = json.loads((foundation / "obj/project.assets.json").read_text())
    libraries = assets["libraries"]
    if any(value.get("type") == "project" for value in libraries.values()):
        raise ValueError("WASM example refuses source-project dependencies")
    for package in ("FS.GG.Wasm.Contracts/0.3.0", "FS.GG.Wasm.Browser/0.3.0"):
        if package not in libraries or libraries[package].get("type") != "package":
            raise ValueError("WASM example requires exact public 0.3.0 packages")
    roots = list(assets["packageFolders"])
    if len(roots) != 1:
        raise ValueError("WASM example requires one explicitly evaluated package root")
    package = Path(roots[0]) / libraries["FS.GG.Wasm.Browser/0.3.0"]["path"]
    archive = package / "fs.gg.wasm.browser.0.3.0.nupkg"
    if archive.is_symlink() or hashlib.sha256(archive.read_bytes()).hexdigest() != PACKAGE_SHA256:
        raise ValueError("Restored Browser archive differs from the selected public bytes")
    records = {}
    with zipfile.ZipFile(archive) as value:
        for member in value.infolist():
            if not member.filename.startswith(PREFIX) or member.is_dir():
                continue
            relative = member.filename[len(PREFIX):]
            path = PurePosixPath(relative)
            if path.is_absolute() or ".." in path.parts or relative in records:
                raise ValueError("Unsafe or duplicate package asset")
            payload = value.read(member)
            cached = package / member.filename
            if cached.is_symlink() or cached.read_bytes() != payload:
                raise ValueError("Restored asset differs from its exact package member")
            records[relative] = payload
    if not {"module-worker.mjs", "worker-client.mjs"}.issubset(records):
        raise ValueError("Package Worker entry or transport is missing")
    # Check the production entry graph; copy every asset, including unused library modules.
    imports = re.compile(r"(?m)^[ \t]*(?:import(?:[^\n;]*?\bfrom)?|export[^\n;]*?\bfrom)[ \t]*[\"']([^\"'\n]+)[\"']")
    edges = {}
    for name, payload in records.items():
        if not name.endswith((".js", ".mjs")):
            continue
        dependencies = []
        for specifier in imports.findall(payload.decode("utf-8")):
            if not specifier.startswith("."):
                dependencies.append(specifier)
                continue
            parts = list(PurePosixPath(name).parent.parts)
            for part in PurePosixPath(specifier).parts:
                if part == "..":
                    if not parts:
                        raise ValueError("Package ESM import escapes its asset root")
                    parts.pop()
                elif part != ".":
                    parts.append(part)
            target = "/".join(parts)
            dependencies.append(target)
        edges[name] = dependencies
    pending = ["module-worker.mjs", "worker-client.mjs"]
    reachable = set()
    while pending:
        name = pending.pop()
        if name in reachable:
            continue
        if name not in records:
            raise ValueError("Production package ESM import is external or missing: " + name)
        reachable.add(name)
        pending.extend(edges.get(name, []))
    # Owner static assets remain in Vite's ordinary public directory. Generated
    # package/guest content never enters it, so disabling the option ignores stale output.
    owner = foundation / "public"
    reserved = ("_content/FS.GG.Wasm.Browser", "wasm-policy", "wasm-package-assets.json", ".wasm-generated-files.json")
    if owner.is_symlink() or any((owner / name).exists() or (owner / name).is_symlink() for name in reserved):
        raise ValueError("Owner public assets collide with reserved WASM output")
    static = {}
    if owner.exists():
        for path in owner.rglob("*"):
            if path.is_symlink():
                raise ValueError("Linked owner public asset refused")
            if path.is_file():
                static[path.relative_to(owner).as_posix()] = path.read_bytes()
    guests = foundation / "obj/wasm-policy-guests"
    modules = json.loads((guests / "modules.json").read_text())
    names = {"c-normal.wasm", "c-malformed.wasm", "c-trap.wasm", "c-loop.wasm", "rust-normal.wasm"}
    if guests.is_symlink() or modules.get("sdkSha256") != "8091df6824981c0c37131524ffbcbae9bb8b36f672a20edc2efaddd35664f8c8" or set(modules.get("modules", {})) != names:
        raise ValueError("Guest build manifest differs from selected independent inputs")
    source = foundation / "Examples/Wasm/guest"
    for field, path in (("cSourceSha256", source / "policy.c"), ("rustSourceSha256", source / "rust/src/lib.rs")):
        if modules.get(field) != hashlib.sha256(path.read_bytes()).hexdigest():
            raise ValueError("Guest build manifest does not bind the actual authored source")
    guest_files = {}
    for name in names:
        path = guests / name
        payload = path.read_bytes()
        if path.is_symlink() or hashlib.sha256(payload).hexdigest() != modules["modules"][name]:
            raise ValueError("Guest output differs from its build manifest")
        guest_files["wasm-policy/" + name] = payload
    guest_files["wasm-policy/modules.json"] = (guests / "modules.json").read_bytes()
    output = foundation / "obj/wasm-policy-public"
    if (foundation / "obj").is_symlink() or output.is_symlink():
        raise ValueError("Linked generated output refused")
    marker = output / ".wasm-generated-files.json"
    if output.exists():
        if marker.is_symlink() or not marker.is_file():
            raise ValueError("Unowned generated-output directory refused")
        previous = json.loads(marker.read_text())
        actual = {}
        for path in output.rglob("*"):
            if path.is_symlink():
                raise ValueError("Linked previous generated asset refused")
            if path.is_file() and path != marker:
                actual[path.relative_to(output).as_posix()] = hashlib.sha256(path.read_bytes()).hexdigest()
        if previous.get("format") != "fsgg-wasm-policy-public/1" or previous.get("files") != actual:
            raise ValueError("Previous generated output has foreign or modified files")
        shutil.rmtree(output)
    output.mkdir(parents=True)
    for name, payload in {**static, **guest_files, **{"_content/FS.GG.Wasm.Browser/" + name: payload for name, payload in records.items()}}.items():
        target = output / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(payload)
    manifest = {
        "package": "FS.GG.Wasm.Browser/0.3.0",
        "archiveSha256": PACKAGE_SHA256,
        "files": {name: hashlib.sha256(payload).hexdigest() for name, payload in sorted(records.items())},
        "imports": edges,
        "productionReachable": sorted(reachable),
    }
    (output / "wasm-package-assets.json").write_text(json.dumps(manifest, sort_keys=True))
    marker.write_text(json.dumps({"format": "fsgg-wasm-policy-public/1", "files": {
        path.relative_to(output).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in output.rglob("*") if path.is_file() and path != marker
    }}, sort_keys=True))


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("usage: materialize-assets.py <SvgFoundation directory>")
    materialize(sys.argv[1])
