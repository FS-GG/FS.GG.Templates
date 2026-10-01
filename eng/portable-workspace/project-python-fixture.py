#!/usr/bin/env python3
"""Project the exact canonical Coordination Python fixture into template staging."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import stat
import subprocess
import tempfile
from pathlib import Path

SCHEMA = "fsgg.templates.python-fixture-source/1"
REPOSITORY = "FS-GG/FS.GG.Coordination"
RECEIPT_SCHEMA = "fsgg.templates.python-fixture-projection/1"
SHA1 = re.compile(r"[0-9a-f]{40}\Z")
SHA256 = re.compile(r"[0-9a-f]{64}\Z")
FILES = {
    "tests/portable-workspace/image/fixture/python/app.py": "python/app.py",
    "tests/portable-workspace/image/fixture/python/build.py": "python/build.py",
    "tests/portable-workspace/image/fixture/python/test.py": "python/test.py",
}
MAX_FILE_BYTES = 1024 * 1024
GIT = "/usr/bin/git"


class ProjectionError(Exception):
    pass


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def canonical(value: object) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode()


def require_keys(value: dict, expected: set[str], subject: str) -> None:
    if set(value) != expected:
        raise ProjectionError(f"{subject}-fields-refused")


def load_manifest(path: Path) -> tuple[dict, bytes]:
    raw = path.read_bytes()
    try:
        value = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ProjectionError("fixture-source-json-refused") from error
    if not isinstance(value, dict):
        raise ProjectionError("fixture-source-object-refused")
    require_keys(value, {"schema", "repository", "revision", "tree", "files"}, "fixture-source")
    if value["schema"] != SCHEMA or value["repository"] != REPOSITORY:
        raise ProjectionError("fixture-source-authority-refused")
    if not isinstance(value["revision"], str) or not SHA1.fullmatch(value["revision"]):
        raise ProjectionError("fixture-source-revision-pending-or-invalid")
    if not isinstance(value["tree"], str) or not SHA1.fullmatch(value["tree"]):
        raise ProjectionError("fixture-source-tree-pending-or-invalid")
    files = value["files"]
    if not isinstance(files, list) or len(files) != len(FILES):
        raise ProjectionError("fixture-source-file-set-refused")
    selected: dict[str, dict] = {}
    for item in files:
        if not isinstance(item, dict):
            raise ProjectionError("fixture-source-file-refused")
        require_keys(item, {"source", "target", "sha256"}, "fixture-source-file")
        source, target, expected_hash = item["source"], item["target"], item["sha256"]
        if source not in FILES or FILES[source] != target or source in selected:
            raise ProjectionError("fixture-source-path-refused")
        if not isinstance(expected_hash, str) or not SHA256.fullmatch(expected_hash):
            raise ProjectionError("fixture-source-hash-pending-or-invalid")
        selected[source] = item
    if set(selected) != set(FILES):
        raise ProjectionError("fixture-source-file-set-refused")
    value["files"] = [selected[source] for source in FILES]
    return value, raw


def git(coordination_root: Path, *arguments: str) -> bytes:
    result = subprocess.run(
        [GIT, "-C", str(coordination_root), *arguments],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if result.returncode != 0:
        raise ProjectionError("fixture-source-git-refused")
    return result.stdout


def read_projection(manifest: dict, coordination_root: Path) -> dict[str, bytes]:
    revision = manifest["revision"]
    actual_revision = git(coordination_root, "rev-parse", "--verify", revision + "^{commit}").decode().strip()
    if actual_revision != revision:
        raise ProjectionError("fixture-source-revision-refused")
    actual_tree = git(coordination_root, "rev-parse", revision + "^{tree}").decode().strip()
    if actual_tree != manifest["tree"]:
        raise ProjectionError("fixture-source-tree-refused")
    projected: dict[str, bytes] = {}
    for item in manifest["files"]:
        data = git(coordination_root, "show", f"{revision}:{item['source']}")
        if len(data) > MAX_FILE_BYTES or digest(data) != item["sha256"]:
            raise ProjectionError("fixture-source-bytes-refused")
        projected[item["target"]] = data
    return projected


def regular_file_bytes(root: Path, relative: str) -> bytes:
    path = root / relative
    current = root
    for part in Path(relative).parts[:-1]:
        current /= part
        info = current.lstat()
        if not stat.S_ISDIR(info.st_mode) or stat.S_ISLNK(info.st_mode):
            raise ProjectionError("projection-output-path-refused")
    info = path.lstat()
    if not stat.S_ISREG(info.st_mode) or stat.S_ISLNK(info.st_mode):
        raise ProjectionError("projection-output-path-refused")
    return path.read_bytes()


def expected_receipt(manifest: dict, manifest_raw: bytes, projected: dict[str, bytes]) -> bytes:
    script = Path(__file__).resolve().read_bytes()
    return canonical(
        {
            "schema": RECEIPT_SCHEMA,
            "repository": manifest["repository"],
            "revision": manifest["revision"],
            "tree": manifest["tree"],
            "manifestSha256": digest(manifest_raw),
            "projectorSha256": digest(script),
            "files": [
                {
                    "source": item["source"],
                    "target": item["target"],
                    "sha256": item["sha256"],
                    "size": len(projected[item["target"]]),
                }
                for item in manifest["files"]
            ],
        }
    )


def verify_existing(output: Path, expected: dict[str, bytes]) -> None:
    info = output.lstat()
    if not stat.S_ISDIR(info.st_mode) or stat.S_ISLNK(info.st_mode):
        raise ProjectionError("projection-output-root-refused")
    actual_paths: set[str] = set()
    for current, directories, files in os.walk(output, followlinks=False):
        current_path = Path(current)
        for name in directories + files:
            path = current_path / name
            if stat.S_ISLNK(path.lstat().st_mode):
                raise ProjectionError("projection-output-link-refused")
        for name in files:
            actual_paths.add((current_path / name).relative_to(output).as_posix())
    if actual_paths != set(expected):
        raise ProjectionError("projection-output-file-set-refused")
    for relative, data in expected.items():
        if regular_file_bytes(output, relative) != data:
            raise ProjectionError("projection-output-bytes-refused")


def write_new(output: Path, expected: dict[str, bytes]) -> None:
    parent = output.parent
    parent.mkdir(parents=True, exist_ok=True)
    parent_info = parent.lstat()
    if not stat.S_ISDIR(parent_info.st_mode) or stat.S_ISLNK(parent_info.st_mode):
        raise ProjectionError("projection-output-parent-refused")
    temporary = Path(tempfile.mkdtemp(prefix=f".{output.name}.projection-", dir=parent))
    try:
        for relative, data in expected.items():
            path = temporary / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0), 0o644)
            with os.fdopen(descriptor, "wb") as stream:
                stream.write(data)
                stream.flush()
                os.fsync(stream.fileno())
        try:
            temporary.rename(output)
        except FileExistsError:
            verify_existing(output, expected)
    finally:
        if temporary.exists():
            shutil.rmtree(temporary)


def project(manifest_path: Path, coordination_root: Path, output: Path) -> None:
    root_info = coordination_root.lstat()
    if not stat.S_ISDIR(root_info.st_mode) or stat.S_ISLNK(root_info.st_mode):
        raise ProjectionError("coordination-root-refused")
    manifest, manifest_raw = load_manifest(manifest_path)
    projected = read_projection(manifest, coordination_root)
    expected = dict(projected)
    expected["python-fixture-source.json"] = expected_receipt(manifest, manifest_raw, projected)
    if output.exists() or output.is_symlink():
        verify_existing(output, expected)
    else:
        write_new(output, expected)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--coordination-root", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument(
        "--manifest",
        type=Path,
        default=Path(__file__).with_name("python-fixture-source.json"),
    )
    arguments = parser.parse_args()
    try:
        project(arguments.manifest.absolute(), arguments.coordination_root.absolute(), arguments.output.absolute())
    except (OSError, ProjectionError, ValueError) as error:
        print(json.dumps({"accepted": False, "reason": str(error)}, sort_keys=True, separators=(",", ":")))
        return 2
    print(json.dumps({"accepted": True, "output": str(arguments.output.absolute())}, sort_keys=True, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
