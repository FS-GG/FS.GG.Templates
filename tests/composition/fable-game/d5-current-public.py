#!/usr/bin/env python3
"""Bounded current-D5 input/hash observations only. ProviderTool owns acceptance."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import sys
from zipfile import ZipFile

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


def require(ok, message):
    if not ok: raise ValueError(message)


def unique(pairs):
    result = {}
    for key, value in pairs:
        require(key not in result, "duplicate JSON property: " + key)
        result[key] = value
    return result


def read_json(path, limit=65536):
    path = Path(path)
    require(path.is_file() and not path.is_symlink() and path.stat().st_size <= limit, "bounded regular JSON required")
    return json.loads(path.read_bytes().decode("utf-8"), object_pairs_hook=unique)


def owner_snapshot(root):
    root = Path(root)
    require(root.is_dir() and not root.is_symlink(), "regular receiver root required")
    result = {}
    # Explicit build/package/VCS caches only; canonical work, models, config,
    # owner files and authority artifacts are all observed, including new files.
    excluded = {".git", ".nuget", "node_modules", "bin", "obj"}
    for current, directories, files in os.walk(root, followlinks=False):
        directories[:] = sorted(name for name in directories if name not in excluded)
        for name in directories + files:
            path = Path(current) / name
            require(not path.is_symlink(), "receiver symlink refused")
        for name in sorted(files):
            path = Path(current) / name
            require(path.is_file(), "nonregular receiver file refused")
            result[str(path.relative_to(root))] = hashlib.sha256(path.read_bytes()).hexdigest()
    return result


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
    parser.add_argument("command", choices=("pins", "observe", "model", "snapshot", "arguments"))
    parser.add_argument("args", nargs="*")
    a = parser.parse_args()
    counts = {"pins": 0, "observe": 1, "model": 2, "snapshot": 2, "arguments": 1}
    require(len(a.args) == counts[a.command], "incorrect observation argument count")
    if a.command == "pins": print(json.dumps(PINS, indent=2))
    elif a.command == "observe": read_json(a.args[0])
    elif a.command == "model": extract_model(*a.args)
    elif a.command == "snapshot":
        root, output = map(Path, a.args)
        require(not output.resolve().is_relative_to(root.resolve()), "snapshot must stay outside observed receiver")
        with output.open("x") as stream: json.dump(owner_snapshot(root), stream, sort_keys=True)
    elif a.command == "arguments":
        args = read_json(a.args[0])
        require(isinstance(args, list) and 0 < len(args) <= 128 and all(isinstance(v, str) and "\0" not in v for v in args), "bounded argument array required")
        for value in args: sys.stdout.buffer.write(value.encode("utf-8") + b"\0")


if __name__ == "__main__":
    try: main()
    except (ValueError, KeyError, OSError, IndexError) as error:
        print("current D5 observation: " + str(error), file=sys.stderr); raise SystemExit(2)
