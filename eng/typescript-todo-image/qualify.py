#!/usr/bin/env python3
"""Build and strictly qualify the pinned TypeScript todo browser image."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
from pathlib import PurePosixPath
import re
import shutil
import subprocess
import sys
import tarfile
import urllib.request
import uuid


ROOT = Path(__file__).resolve().parents[2]
IMAGE_DIR = ROOT / "eng" / "typescript-todo-image"
FIXTURE = ROOT / "examples" / "language-routes" / "typescript-todo"
INPUTS_SHA256 = "995914cf786fb2021e2034171935b88cced44a05fe542662f8d91e9daa2fa8e9"
RECIPE_SHA256 = "d622348d58f7584d4214a921611bbd8ca976cd349098dc4978dedcf97b0b1553"
ENTRYPOINT_SHA256 = "2943571089ce68a15085dc037fb60eac69eff8e8cc1ce81a1a1be84015f35e11"
IMAGE_NAME = "localhost/fsgg-typescript-todo:node-24.8.0-playwright-1.63.0"
BASE_REFERENCE = "mcr.microsoft.com/playwright@sha256:bc6ab0d6d44ff4826e4cb8c1e6d801e185bfc42bb0753f8e2a30efc70db054c7"
MAX_OUTPUT = 1024 * 1024
MAX_CANDIDATE = 2 * 1024 * 1024 * 1024
SHA256 = re.compile(r"[0-9a-f]{64}")


def canonical(value: object) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def clean_host_environment() -> dict[str, str]:
    environment = {"HOME": "/tmp", "PATH": "/usr/local/bin:/usr/bin:/bin", "LANG": "C.UTF-8", "LC_ALL": "C.UTF-8"}
    if os.environ.get("XDG_RUNTIME_DIR"):
        environment["XDG_RUNTIME_DIR"] = os.environ["XDG_RUNTIME_DIR"]
    return environment


def run(argv: list[str], *, cwd: Path | None = None, check: bool = True, timeout: int = 180) -> subprocess.CompletedProcess[bytes]:
    try:
        result = subprocess.run(argv, cwd=cwd, capture_output=True, timeout=timeout, env=clean_host_environment())
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


def load_inputs() -> dict:
    inputs_path = IMAGE_DIR / "inputs.json"
    if sha256_file(inputs_path) != INPUTS_SHA256:
        raise RuntimeError("image inputs do not match the reviewed digest")
    if sha256_file(IMAGE_DIR / "Containerfile") != RECIPE_SHA256:
        raise RuntimeError("image recipe does not match the reviewed digest")
    if sha256_file(IMAGE_DIR / "qualify-readonly.sh") != ENTRYPOINT_SHA256:
        raise RuntimeError("fixed qualification entry point does not match the reviewed digest")
    inputs = json.loads(inputs_path.read_text())
    if inputs.get("schema") != "fsgg.typescript-todo-image-inputs/1":
        raise RuntimeError("unsupported image input schema")
    if inputs.get("architecture") != "amd64" or inputs.get("os") != "linux":
        raise RuntimeError("image input platform must be linux/amd64")
    if inputs.get("base", {}).get("reference") != BASE_REFERENCE:
        raise RuntimeError("base image reference does not match the reviewed manifest")
    if inputs.get("node", {}).get("version") != "24.8.0" or inputs.get("typescript") != "5.9.2" or inputs.get("playwright") != "1.63.0":
        raise RuntimeError("toolchain versions do not match the selected route")
    browsers = {item.get("name"): item for item in inputs.get("browserAssets", [])}
    if browsers.get("chromium", {}).get("revision") != "1243" or browsers.get("chromium-headless-shell", {}).get("browserVersion") != "153.0.8010.12":
        raise RuntimeError("Playwright browser asset identity is incomplete")
    if not SHA256.fullmatch(browsers.get("chromium-headless-shell", {}).get("licenseSha256", "")):
        raise RuntimeError("Chromium headless shell licence identity is incomplete")
    for item in [inputs["node"], *inputs["npmPackages"], *inputs["browserAssets"]]:
        if not SHA256.fullmatch(item.get("sha256", "")) or not item.get("url", "").startswith("https://"):
            raise RuntimeError("every external input requires an HTTPS source and full SHA-256")
    return inputs


def prefix(args: argparse.Namespace) -> list[str]:
    return [str(Path(args.podman).resolve()), "--storage-driver=vfs", "--root", str(Path(args.root).resolve()), "--runroot", str(Path(args.runroot).resolve())]


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


def immutable_sha(value: object, label: str, *, prefixed: bool = True) -> str:
    if not isinstance(value, str):
        raise RuntimeError(f"{label} is not a string")
    bare = value.removeprefix("sha256:")
    if not SHA256.fullmatch(bare):
        raise RuntimeError(f"{label} is not a full lowercase SHA-256")
    return f"sha256:{bare}" if prefixed else bare


def preflight(args: argparse.Namespace, state: Path, expected: str) -> Path:
    revision, tree = exact_source(expected)
    load_inputs()
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
        "schema": "fsgg.typescript-todo-image-preflight/1", "sourceRevision": revision, "sourceTree": tree,
        "inputsSha256": INPUTS_SHA256, "recipeSha256": RECIPE_SHA256, "entrypointSha256": ENTRYPOINT_SHA256,
        "baseReference": BASE_REFERENCE, "platform": "linux/amd64", "rootless": True, "containerUser": "32768:32768",
        "buildNetwork": "none", "executionNetwork": "container-loopback-only", "sourceMount": "read-only",
        "podmanVersion": run(podman + ["version", "--format", "{{.Client.Version}}"]).stdout.decode().strip(),
    }
    path = state / "preflight.json"
    path.write_bytes(canonical(receipt)); os.chmod(path, 0o600)
    return path


def prepare_context(state: Path, inputs: dict) -> Path:
    cache = state / "inputs"
    npm_cache = cache / "npm"
    context = state / "context"
    cache.mkdir(parents=True, exist_ok=True, mode=0o700)
    npm_cache.mkdir(parents=True, exist_ok=True, mode=0o700)
    context.mkdir(parents=True, exist_ok=True, mode=0o700)
    node = inputs["node"]
    download(node["url"], cache / node["archive"], node["sha256"])
    for package in inputs["npmPackages"]:
        download(package["url"], npm_cache / package["archive"], package["sha256"])
    shutil.copyfile(IMAGE_DIR / "Containerfile", context / "Containerfile")
    shutil.copyfile(IMAGE_DIR / "qualify-readonly.sh", context / "qualify-readonly.sh")
    shutil.copyfile(FIXTURE / "package.json", context / "package.json")
    shutil.copyfile(FIXTURE / "package-lock.json", context / "package-lock.json")
    shutil.copytree(cache, context / "inputs", dirs_exist_ok=True)
    return context


def inspect_image(podman: list[str], reference: str) -> dict:
    values = json.loads(run(podman + ["image", "inspect", reference]).stdout)
    if not isinstance(values, list) or len(values) != 1:
        raise RuntimeError("image inspection did not return exactly one image")
    image = values[0]
    config = image.get("Config", {})
    if image.get("Os") != "linux" or image.get("Architecture") != "amd64":
        raise RuntimeError("image platform mismatch")
    if config.get("User") not in ("32768", "32768:32768"):
        raise RuntimeError("image is not fixed to the non-root user")
    if config.get("Entrypoint") not in (None, []) or config.get("Cmd") not in (None, []):
        raise RuntimeError("image supplies an executable hook")
    if config.get("Volumes") not in (None, {}):
        raise RuntimeError("image supplies a writable volume hook")
    image["Id"] = immutable_sha(image.get("Id"), "image ID")
    image["Digest"] = immutable_sha(image.get("Digest"), "image digest")
    return image


def operation_create_argv(podman: list[str], reference: str, output: Path, container: str) -> list[str]:
    return podman + [
        "create", "--name", container,
        "--label=fsgg.typescript-todo.qualification=true",
        "--pull=never", "--read-only", "--network=none", "--cap-drop=all",
        "--security-opt=no-new-privileges", "--user=32768:32768", "--unsetenv-all",
        f"--volume={ROOT}:/source:ro", f"--volume={output}:/output:rw",
        "--tmpfs=/tmp:rw,noexec,nosuid,nodev,size=128m", "--tmpfs=/dev/shm:rw,nosuid,nodev,size=512m",
        "--workdir=/source/examples/language-routes/typescript-todo",
        "--entrypoint=/usr/local/bin/fsgg-typescript-todo-qualify", reference,
    ]


def qualify_operation(args: argparse.Namespace, state: Path, reference: str, image: dict) -> Path:
    podman = prefix(args)
    output = state / "run" / "output"
    output.mkdir(parents=True, exist_ok=True, mode=0o755)
    run(podman + ["unshare", "chown", "32768:32768", str(output)])
    container = f"fsgg-typescript-todo-{uuid.uuid4().hex[:16]}"
    journal = output.parent / "journal.jsonl"
    try:
        created = run(operation_create_argv(podman, reference, output, container))
        started = run(podman + ["start", "--attach", container], check=False, timeout=300)
        inspected = json.loads(run(podman + ["container", "inspect", container]).stdout)[0]
        actual_id = immutable_sha(inspected["Image"], "operation image ID")
        record = {
            "event": "operation", "name": "compiled-browser-journey", "containerId": created.stdout.decode().strip(),
            "imageId": actual_id, "containerUser": inspected["Config"]["User"], "exitCode": inspected["State"]["ExitCode"],
            "stdoutSha256": hashlib.sha256(started.stdout).hexdigest(), "stderrSha256": hashlib.sha256(started.stderr).hexdigest(),
        }
        with journal.open("ab") as stream:
            stream.write(canonical(record)); stream.flush(); os.fsync(stream.fileno())
        if actual_id != image["Id"] or record["containerUser"] not in ("32768", "32768:32768"):
            raise RuntimeError("operation container identity mismatch")
        if started.returncode != 0 or record["exitCode"] != 0:
            raise RuntimeError("compiled browser journey failed")
        result = json.loads((output / "result.json").read_text())
        expected_journey = {name: "passed" for name in ("add", "edit", "complete", "filter", "delete", "reload", "malformedRetainedState")}
        expected_outputs = {"dist": "/output/dist", "reports": "/output/reports", "cache": "/output/cache", "retainedBrowserState": "/output/tmp"}
        browser = result.get("chromium", {})
        if (
            result.get("schema") != "fsgg.typescript-todo-image-operation/1"
            or result.get("node") != "24.8.0" or result.get("typescript") != "5.9.2" or result.get("playwright") != "1.63.0"
            or result.get("sourceMount") != "read-only" or result.get("network") != "container-loopback-only"
            or result.get("outputs") != expected_outputs or result.get("journey") != expected_journey
            or browser.get("version") != "153.0.8010.12" or browser.get("revision") != "1243"
            or not SHA256.fullmatch(browser.get("executableSha256", ""))
            or browser.get("licenseSha256") != "b92247f7a44c14627ef5cbbe0aa6dcca4e4422b7c05e6f2c660054061a5e3da7"
        ):
            raise RuntimeError("operation result does not prove the required browser journey")
    finally:
        run(podman + ["container", "rm", "--force", container], check=False)
    return journal


def oci_archive_members(archive: tarfile.TarFile) -> dict[str, tarfile.TarInfo]:
    members: dict[str, tarfile.TarInfo] = {}
    for member in archive.getmembers():
        normalized = str(PurePosixPath(member.name))
        if (
            not member.name or member.name.startswith("/") or "\\" in member.name
            or normalized != member.name.rstrip("/") or ".." in PurePosixPath(member.name).parts
            or not (member.isfile() or member.isdir())
        ):
            raise RuntimeError(f"OCI archive member path or type is unsafe: {member.name!r}")
        if normalized in members:
            raise RuntimeError(f"OCI archive has ambiguous duplicate member: {normalized}")
        members[normalized] = member
    return members


def oci_descriptor_blob(archive: tarfile.TarFile, members: dict[str, tarfile.TarInfo], descriptor: object, label: str, *, retain: bool = False) -> tuple[str, bytes | None]:
    if not isinstance(descriptor, dict):
        raise RuntimeError(f"{label} descriptor is not an object")
    if not isinstance(descriptor.get("mediaType"), str) or not descriptor["mediaType"]:
        raise RuntimeError(f"{label} descriptor media type is invalid")
    digest = immutable_sha(descriptor.get("digest"), f"{label} digest")
    size = descriptor.get("size")
    if not isinstance(size, int) or isinstance(size, bool) or size < 0:
        raise RuntimeError(f"{label} descriptor size is invalid")
    member_path = f"blobs/sha256/{digest[7:]}"
    member = members.get(member_path)
    if member is None:
        raise RuntimeError(f"OCI archive lacks {label} blob")
    if not member.isfile() or member.size != size:
        raise RuntimeError(f"{label} blob size does not match its descriptor")
    stream = archive.extractfile(member)
    if stream is None:
        raise RuntimeError(f"OCI archive cannot read {label} blob")
    content = bytearray() if retain else None
    actual_size = 0
    actual_digest = hashlib.sha256()
    for chunk in iter(lambda: stream.read(1024 * 1024), b""):
        actual_size += len(chunk); actual_digest.update(chunk)
        if content is not None:
            if actual_size > MAX_OUTPUT:
                raise RuntimeError(f"{label} blob exceeds the retained metadata bound")
            content.extend(chunk)
    if actual_size != size or actual_digest.hexdigest() != digest[7:]:
        raise RuntimeError(f"{label} blob content does not match its descriptor")
    return digest, bytes(content) if content is not None else None


def oci_archive_identity(path: Path) -> dict[str, object]:
    with tarfile.open(path, "r") as archive:
        members = oci_archive_members(archive)
        layout_member = members.get("oci-layout")
        if layout_member is None or not layout_member.isfile() or layout_member.size > MAX_OUTPUT:
            raise RuntimeError("OCI archive lacks bounded oci-layout metadata")
        layout_stream = archive.extractfile(layout_member)
        if layout_stream is None or json.load(layout_stream) != {"imageLayoutVersion": "1.0.0"}:
            raise RuntimeError("OCI archive layout version is not 1.0.0")
        index_info = members.get("index.json")
        if index_info is None or not index_info.isfile() or index_info.size > MAX_OUTPUT:
            raise RuntimeError("OCI archive lacks index.json")
        index_member = archive.extractfile(index_info)
        if index_member is None:
            raise RuntimeError("OCI archive cannot read index.json")
        index = json.load(index_member)
        if index.get("schemaVersion") != 2:
            raise RuntimeError("OCI index schema version is not 2")
        manifests = index.get("manifests", [])
        if len(manifests) != 1:
            raise RuntimeError("OCI archive must contain exactly one manifest")
        manifest_descriptor = manifests[0]
        index_platform = manifest_descriptor.get("platform")
        if index_platform is not None and (
            not isinstance(index_platform, dict)
            or index_platform.get("architecture") != "amd64"
            or index_platform.get("os") != "linux"
        ):
            raise RuntimeError("OCI index manifest platform conflicts with linux/amd64")
        manifest_digest, manifest_bytes = oci_descriptor_blob(archive, members, manifest_descriptor, "manifest", retain=True)
        assert manifest_bytes is not None
        manifest = json.loads(manifest_bytes)
        if manifest.get("schemaVersion") != 2:
            raise RuntimeError("OCI manifest schema version is not 2")
        config_digest, config_bytes = oci_descriptor_blob(archive, members, manifest.get("config"), "config", retain=True)
        assert config_bytes is not None
        config = json.loads(config_bytes)
        if config.get("architecture") != "amd64" or config.get("os") != "linux":
            raise RuntimeError("OCI config platform is not linux/amd64")
        layers = manifest.get("layers")
        if not isinstance(layers, list) or not layers:
            raise RuntimeError("OCI manifest has no layers")
        layer_digests = []
        for position, descriptor in enumerate(layers):
            digest, _ = oci_descriptor_blob(archive, members, descriptor, f"layer {position}")
            layer_digests.append(digest)
        referenced_blobs = {f"blobs/sha256/{digest[7:]}" for digest in [manifest_digest, config_digest, *layer_digests]}
        archived_blobs = {name for name, member in members.items() if member.isfile() and name.startswith("blobs/")}
        if archived_blobs != referenced_blobs:
            raise RuntimeError("OCI archive blob inventory does not exactly match its descriptors")
    return {"manifestDigest": manifest_digest, "configDigest": config_digest, "layerDigests": layer_digests}


def require_archive_image_binding(oci: dict[str, object], image: dict) -> None:
    if oci["manifestDigest"] != image["Digest"]:
        raise RuntimeError("exported OCI manifest digest does not match the qualified image digest")
    if oci["configDigest"] != image["Id"]:
        raise RuntimeError("exported OCI config digest does not match the qualified image ID")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=("check", "preflight", "qualify"))
    parser.add_argument("--expected-source-revision")
    parser.add_argument("--state-dir")
    parser.add_argument("--podman", default="/usr/bin/podman")
    parser.add_argument("--root")
    parser.add_argument("--runroot")
    args = parser.parse_args()
    inputs = load_inputs()
    if args.mode == "check":
        print(canonical({"inputsSha256": INPUTS_SHA256, "recipeSha256": RECIPE_SHA256, "entrypointSha256": ENTRYPOINT_SHA256}).decode(), end="")
        return 0
    if not all((args.expected_source_revision, args.state_dir, args.root, args.runroot)):
        parser.error("preflight and qualify require source revision, state, root, and runroot")
    state = Path(args.state_dir).resolve()
    state.mkdir(parents=True, exist_ok=True, mode=0o700)
    preflight_path = preflight(args, state, args.expected_source_revision)
    if args.mode == "preflight":
        print(canonical({"preflight": str(preflight_path), "sha256": sha256_file(preflight_path)}).decode(), end="")
        return 0
    revision, tree = exact_source(args.expected_source_revision)
    context = prepare_context(state, inputs)
    podman = prefix(args)
    run(podman + ["build", "--pull=never", "--network=none", "--timestamp=0", "--platform=linux/amd64", "--format=oci", "--tag", IMAGE_NAME, "--file", str(context / "Containerfile"), str(context)], timeout=1200)
    image = inspect_image(podman, IMAGE_NAME)
    reference = f"{IMAGE_NAME}@{image['Digest']}"
    journal = qualify_operation(args, state, reference, image)
    candidate = state / "typescript-todo-candidate.oci.tar"
    run(podman + ["save", "--format=oci-archive", "--output", str(candidate), reference], timeout=900)
    if candidate.stat().st_size > MAX_CANDIDATE:
        raise RuntimeError(f"candidate exceeds {MAX_CANDIDATE} bytes")
    oci = oci_archive_identity(candidate)
    require_archive_image_binding(oci, image)
    result = {
        "schema": "fsgg.typescript-todo-image-qualification/1", "sourceRevision": revision, "sourceTree": tree,
        "inputsSha256": INPUTS_SHA256, "recipeSha256": RECIPE_SHA256, "entrypointSha256": ENTRYPOINT_SHA256,
        "reference": reference, "imageId": image["Id"], **oci, "candidate": str(candidate),
        "candidateSha256": sha256_file(candidate), "journal": str(journal), "journalSha256": sha256_file(journal),
        "operationResult": str(state / "run" / "output" / "result.json"),
        "operationResultSha256": sha256_file(state / "run" / "output" / "result.json"),
    }
    manifests = state / "manifests"; manifests.mkdir(parents=True, exist_ok=True, mode=0o700)
    manifest = manifests / "qualification.json"
    manifest.write_bytes(canonical(result)); os.chmod(manifest, 0o600)
    print(canonical({"manifest": str(manifest), "manifestSha256": sha256_file(manifest)}).decode(), end="")
    return 0


if __name__ == "__main__":
    sys.exit(main())
