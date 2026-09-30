#!/usr/bin/env python3
"""Build and qualify immutable Rust and Go route images with rootless Podman."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import urllib.request
import uuid


ROOT = Path(__file__).resolve().parents[2]
IMAGE_DIR = ROOT / "eng" / "language-route-images"
INPUTS_SHA256 = "33232c80576e6f1e15e3ed7a9df979aba97f1691ce66502931b63b2bf1bda424"
RECIPE_SHA256 = {
    "rust": "26f02aa5ca5b0ba3316603402e314c9b568d1c318c98cedb2d052798fe043c34",
    "go": "a0d59ccedc4f09c9517ecf8d72677f62795a75286e0787e3d0710622a7a57319",
}
IMAGE_NAMES = {
    "rust": "localhost/fsgg-language-route:rust-1.98.1",
    "go": "localhost/fsgg-language-route:go-1.27.1",
}
ROUTES = {
    "rust": ROOT / "examples" / "language-routes" / "rust-tic-tac-toe",
    "go": ROOT / "examples" / "language-routes" / "go-snake",
}
MAX_OUTPUT = 1024 * 1024
MAX_CANDIDATE = 768 * 1024 * 1024
SHA256 = re.compile(r"[0-9a-f]{64}")


def clean_host_environment() -> dict[str, str]:
    environment = {
        "HOME": "/tmp",
        "PATH": "/usr/local/bin:/usr/bin:/bin",
        "LANG": "C.UTF-8",
        "LC_ALL": "C.UTF-8",
    }
    if os.environ.get("XDG_RUNTIME_DIR"):
        environment["XDG_RUNTIME_DIR"] = os.environ["XDG_RUNTIME_DIR"]
    return environment


def canonical(value: object) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode()


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def immutable_image_id(value: object) -> str:
    if not isinstance(value, str):
        raise RuntimeError("image ID is not a string")
    bare = value.removeprefix("sha256:")
    if not SHA256.fullmatch(bare):
        raise RuntimeError("image ID is not a full lowercase SHA-256")
    return f"sha256:{bare}"


def immutable_digest(value: object) -> str:
    if not isinstance(value, str) or not value.startswith("sha256:") or not SHA256.fullmatch(value[7:]):
        raise RuntimeError("image digest is not a full lowercase SHA-256")
    return value


def run(argv: list[str], *, cwd: Path | None = None, check: bool = True, timeout: int = 180) -> subprocess.CompletedProcess[bytes]:
    try:
        result = subprocess.run(
            argv,
            cwd=cwd,
            capture_output=True,
            timeout=timeout,
            env=clean_host_environment(),
        )
    except subprocess.TimeoutExpired as error:
        raise RuntimeError(f"command timed out after {timeout}s: {argv[0]}") from error
    if len(result.stdout) + len(result.stderr) > MAX_OUTPUT:
        raise RuntimeError(f"command output exceeded {MAX_OUTPUT} bytes: {argv[0]}")
    if check and result.returncode != 0:
        raise RuntimeError(
            f"command failed ({result.returncode}): {argv[0]}; "
            f"stdout={result.stdout[-4096:]!r}; stderr={result.stderr[-4096:]!r}"
        )
    return result


def git(*arguments: str) -> str:
    return run(["git", *arguments], cwd=ROOT).stdout.decode().strip()


def exact_source(expected: str) -> tuple[str, str]:
    if git("status", "--porcelain"):
        raise RuntimeError("qualification requires a clean committed worktree")
    revision = git("rev-parse", "HEAD")
    if revision != expected:
        raise RuntimeError(f"source revision mismatch: expected {expected}, got {revision}")
    return revision, git("rev-parse", "HEAD^{tree}")


def prefix(args: argparse.Namespace) -> list[str]:
    return [
        str(Path(args.podman).resolve()),
        "--storage-driver=vfs",
        "--root", str(Path(args.root).resolve()),
        "--runroot", str(Path(args.runroot).resolve()),
    ]


def load_inputs() -> dict:
    inputs = json.loads((IMAGE_DIR / "inputs.json").read_text())
    if inputs.get("schema") != "fsgg.language-route-image-inputs/1":
        raise RuntimeError("unsupported image input schema")
    if sha256_file(IMAGE_DIR / "inputs.json") != INPUTS_SHA256:
        raise RuntimeError("image inputs do not match the reviewed digest")
    for language, expected in RECIPE_SHA256.items():
        if sha256_file(IMAGE_DIR / f"{language}.Containerfile") != expected:
            raise RuntimeError(f"{language} recipe does not match the reviewed digest")
    return inputs


def download(url: str, destination: Path, expected: str) -> None:
    if destination.is_file() and sha256_file(destination) == expected:
        return
    temporary = destination.with_name(f".{destination.name}.{uuid.uuid4().hex}.partial")
    with urllib.request.urlopen(url, timeout=60) as response, temporary.open("xb") as output:
        shutil.copyfileobj(response, output)
        output.flush()
        os.fsync(output.fileno())
    actual = sha256_file(temporary)
    if actual != expected:
        temporary.unlink(missing_ok=True)
        raise RuntimeError(f"archive digest mismatch for {url}: {actual}")
    os.replace(temporary, destination)


def inspect_one(podman: list[str], kind: str, reference: str) -> dict:
    values = json.loads(run(podman + ["image", "inspect", reference]).stdout)
    if not isinstance(values, list) or len(values) != 1:
        raise RuntimeError(f"{kind} image inspection did not return exactly one image")
    image = values[0]
    config = image.get("Config", {})
    if image.get("Os") != "linux" or image.get("Architecture") != "amd64":
        raise RuntimeError(f"{kind} image platform mismatch")
    if config.get("User") not in ("32768", "32768:32768"):
        raise RuntimeError(f"{kind} image is not fixed to the non-root user")
    if config.get("Entrypoint") not in (None, []) or config.get("Cmd") not in (None, []):
        raise RuntimeError(f"{kind} image supplies an executable hook")
    if config.get("Volumes") not in (None, {}):
        raise RuntimeError(f"{kind} image supplies a writable volume hook")
    return image


def preflight(args: argparse.Namespace, state: Path, expected: str) -> Path:
    revision, tree = exact_source(expected)
    inputs = load_inputs()
    podman = prefix(args)
    info = json.loads(run(podman + ["info", "--format=json"]).stdout)
    host = info["host"]
    if host.get("os") != "linux" or host.get("arch") != "amd64" or not host.get("security", {}).get("rootless"):
        raise RuntimeError("qualification requires rootless Podman on linux/amd64")
    mappings = host.get("idMappings", {}).get("uidmap", [])
    if not any(item["container_id"] <= 32768 < item["container_id"] + item["size"] for item in mappings):
        raise RuntimeError("rootless mapping does not cover uid 32768")
    build_help = run(podman + ["build", "--help"]).stdout.decode()
    create_help = run(podman + ["create", "--help"]).stdout.decode()
    for option in ("--network", "--pull", "--platform", "--timestamp", "--format"):
        if option not in build_help:
            raise RuntimeError(f"Podman build lacks required option {option}")
    for option in ("--read-only", "--network", "--cap-drop", "--security-opt", "--user", "--unsetenv-all", "--volume", "--tmpfs"):
        if option not in create_help:
            raise RuntimeError(f"Podman create lacks required option {option}")
    receipt = {
        "schema": "fsgg.language-route-image-preflight/1",
        "sourceRevision": revision,
        "sourceTree": tree,
        "inputsSha256": INPUTS_SHA256,
        "recipeSha256": RECIPE_SHA256,
        "baseReferences": {name: inputs[name]["base"] for name in ("rust", "go")},
        "rootless": True,
        "platform": "linux/amd64",
        "containerUser": "32768:32768",
        "network": "none-during-build-and-execution",
        "sourceMount": "read-only",
        "podmanVersion": run(podman + ["version", "--format", "{{.Client.Version}}"]).stdout.decode().strip(),
    }
    path = state / "preflight.json"
    path.write_bytes(canonical(receipt))
    os.chmod(path, 0o600)
    return path


def build(args: argparse.Namespace, state: Path, inputs: dict, kind: str) -> tuple[str, dict]:
    cache = state / "inputs"
    context = state / "contexts" / kind
    cache.mkdir(parents=True, exist_ok=True, mode=0o700)
    context.mkdir(parents=True, exist_ok=True, mode=0o700)
    shutil.copyfile(IMAGE_DIR / f"{kind}.Containerfile", context / "Containerfile")
    items = inputs["rust"]["components"] if kind == "rust" else [inputs["go"]]
    for item in items:
        archive = cache / item["archive"]
        download(item["url"], archive, item["sha256"])
        shutil.copyfile(archive, context / item["archive"])
    podman = prefix(args)
    run(
        podman + [
            "build", "--pull=never", "--network=none", "--timestamp=0",
            "--platform=linux/amd64", "--format=oci", "--tag", IMAGE_NAMES[kind],
            "--file", str(context / "Containerfile"), str(context),
        ],
        timeout=900,
    )
    image = inspect_one(podman, kind, IMAGE_NAMES[kind])
    try:
        digest = immutable_digest(image.get("Digest"))
        image_id = immutable_image_id(image.get("Id"))
    except RuntimeError as error:
        raise RuntimeError(f"{kind} image lacks immutable digest or ID") from error
    image["Id"] = image_id
    return f"{IMAGE_NAMES[kind]}@{digest}", image


def operation(podman: list[str], reference: str, image_id: str, kind: str, route: Path, output: Path, name: str, executable: str, arguments: list[str], environment: list[str], journal: Path) -> None:
    container = f"fsgg-language-{kind}-{uuid.uuid4().hex[:16]}"
    try:
        created = run(podman + [
            "create", "--name", container,
            "--label=fsgg.language-route.qualification=true",
            f"--label=fsgg.language-route.kind={kind}",
            "--pull=never", "--read-only", "--network=none", "--cap-drop=all",
            "--security-opt=no-new-privileges", "--user=32768:32768", "--unsetenv-all",
            f"--volume={ROOT}:/source:ro", f"--volume={output}:/output:rw",
            "--tmpfs=/tmp:rw,noexec,nosuid,nodev,size=128m",
            f"--workdir=/source/{route.relative_to(ROOT)}", f"--entrypoint={executable}",
            *[f"--env={item}" for item in environment], reference, *arguments,
        ])
        started = run(podman + ["start", "--attach", container], check=False, timeout=300)
        inspected = json.loads(run(podman + ["container", "inspect", container]).stdout)[0]
        try:
            actual_id = immutable_image_id(inspected["Image"])
        except RuntimeError as error:
            raise RuntimeError(f"{kind}/{name} container lacks an immutable image ID") from error
        actual_user = inspected["Config"]["User"]
        record = {
            "event": "operation", "kind": kind, "name": name,
            "containerId": created.stdout.decode().strip(), "imageId": actual_id,
            "containerUser": actual_user, "exitCode": inspected["State"]["ExitCode"],
            "stdoutSha256": sha256_bytes(started.stdout), "stderrSha256": sha256_bytes(started.stderr),
        }
        with journal.open("ab") as stream:
            stream.write(canonical(record)); stream.flush(); os.fsync(stream.fileno())
        if actual_id != image_id or actual_user not in ("32768", "32768:32768"):
            raise RuntimeError(f"{kind}/{name} container identity mismatch")
        if started.returncode != 0 or inspected["State"]["ExitCode"] != 0:
            raise RuntimeError(f"{kind}/{name} failed")
    finally:
        run(podman + ["container", "rm", "--force", container], check=False)


def qualify_image(args: argparse.Namespace, state: Path, kind: str, reference: str, image: dict) -> Path:
    podman = prefix(args)
    output = state / "runs" / kind / "output"
    output.mkdir(parents=True, exist_ok=True, mode=0o755)
    run(podman + ["unshare", "chown", "32768:32768", str(output)])
    journal = output.parent / "journal.jsonl"
    source = ROUTES[kind]
    if kind == "rust":
        environment = ["HOME=/tmp", "PATH=/usr/local/bin:/usr/bin:/bin", "CARGO_HOME=/tmp/cargo", "CARGO_TARGET_DIR=/output/target", "CARGO_NET_OFFLINE=true", "LANG=C.UTF-8"]
        commands = [
            ("test-and-entrypoint", "/usr/local/bin/cargo", ["test", "--locked"]),
            ("clippy", "/usr/local/bin/cargo", ["clippy", "--all-targets", "--locked", "--", "-D", "warnings"]),
            ("format", "/usr/local/bin/cargo", ["fmt", "--check"]),
        ]
    else:
        environment = ["HOME=/tmp", "PATH=/usr/local/go/bin:/usr/bin:/bin", "FSGG_GO_BIN=/usr/local/go/bin/go", "GOTOOLCHAIN=local", "GOWORK=off", "GOPROXY=off", "GOSUMDB=off", "CGO_ENABLED=0", "LANG=C.UTF-8"]
        commands = [("verify-and-entrypoint", "/bin/bash", ["scripts/verify.sh"])]
    for name, executable, arguments in commands:
        operation(podman, reference, image["Id"], kind, source, output, name, executable, arguments, environment, journal)
    return journal


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=("check", "preflight", "qualify"))
    parser.add_argument("--expected-source-revision")
    parser.add_argument("--state-dir")
    parser.add_argument("--podman", default="/usr/bin/podman")
    parser.add_argument("--root")
    parser.add_argument("--runroot")
    args = parser.parse_args()
    load_inputs()
    if args.mode == "check":
        print(json.dumps({"inputsSha256": INPUTS_SHA256, "recipeSha256": RECIPE_SHA256}, sort_keys=True))
        return 0
    if not all((args.expected_source_revision, args.state_dir, args.root, args.runroot)):
        parser.error("preflight and qualify require source revision, state, root, and runroot")
    state = Path(args.state_dir).resolve()
    state.mkdir(parents=True, exist_ok=True, mode=0o700)
    preflight_path = preflight(args, state, args.expected_source_revision)
    if args.mode == "preflight":
        print(canonical({"preflight": str(preflight_path), "sha256": sha256_file(preflight_path)}).decode(), end="")
        return 0
    inputs = load_inputs()
    manifests = state / "manifests"
    manifests.mkdir(parents=True, exist_ok=True, mode=0o700)
    revision, tree = exact_source(args.expected_source_revision)
    result = {
        "schema": "fsgg.language-route-image-qualification/1",
        "sourceRevision": revision,
        "sourceTree": tree,
        "inputsSha256": INPUTS_SHA256,
        "recipeSha256": RECIPE_SHA256,
        "images": {},
    }
    for kind in ("rust", "go"):
        reference, image = build(args, state, inputs, kind)
        journal = qualify_image(args, state, kind, reference, image)
        candidate = state / f"{kind}-candidate.oci.tar"
        run(prefix(args) + ["save", "--format=oci-archive", "--output", str(candidate), reference], timeout=600)
        if candidate.stat().st_size > MAX_CANDIDATE:
            raise RuntimeError(f"{kind} candidate exceeds {MAX_CANDIDATE} bytes")
        result["images"][kind] = {
            "reference": reference, "id": image["Id"], "candidate": str(candidate),
            "candidateSha256": sha256_file(candidate), "journal": str(journal),
            "journalSha256": sha256_file(journal),
        }
    manifest = manifests / "qualification.json"
    manifest.write_bytes(canonical(result)); os.chmod(manifest, 0o600)
    print(canonical({"manifest": str(manifest), "manifestSha256": sha256_file(manifest)}).decode(), end="")
    return 0


if __name__ == "__main__":
    sys.exit(main())
