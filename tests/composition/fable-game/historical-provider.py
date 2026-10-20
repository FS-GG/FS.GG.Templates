#!/usr/bin/env python3
"""Bind a released provider descriptor to its exact template archive and source."""
import argparse
import hashlib
from pathlib import Path
import re
import urllib.request
import xml.etree.ElementTree as ET
from zipfile import ZipFile


def sha(data):
    return hashlib.sha256(data).hexdigest()


def acquire(archive, version, revision, archive_sha, descriptor_sha, output, download=None):
    if not re.fullmatch(r"[0-9a-f]{40}", revision):
        raise ValueError("Historical descriptor requires an immutable source revision")
    if any(not re.fullmatch(r"[0-9a-f]{64}", value) for value in (archive_sha, descriptor_sha)):
        raise ValueError("Historical descriptor requires exact archive and descriptor hashes")
    if output.exists():
        raise ValueError("Historical descriptor refuses an existing output")
    if sha(archive.read_bytes()) != archive_sha:
        raise ValueError("Historical template archive hash mismatch")
    with ZipFile(archive) as package:
        nuspecs = [name for name in package.namelist() if name.endswith(".nuspec")]
        if len(nuspecs) != 1:
            raise ValueError("Historical template archive requires exactly one nuspec")
        metadata = ET.fromstring(package.read(nuspecs[0])).find("{*}metadata")
        if metadata is None or metadata.findtext("{*}id") != "FS.GG.Workspace.Template" or metadata.findtext("{*}version") != version:
            raise ValueError("Historical template package identity mismatch")
        repository = metadata.find("{*}repository")
        if repository is None or repository.get("commit") != revision:
            raise ValueError("Historical template repository source mismatch")
    url = f"https://raw.githubusercontent.com/FS-GG/FS.GG.Templates/{revision}/providers/fable-game.providers.yml"
    if download is None:
        with urllib.request.urlopen(url, timeout=60) as response:
            descriptor = response.read()
    else:
        descriptor = download(url)
    if sha(descriptor) != descriptor_sha:
        raise ValueError("Historical provider descriptor hash mismatch")
    with output.open("xb") as stream:
        stream.write(descriptor)



# Exact source/receipt role. This does not select a weaker contract for current
# source, a current public receiver, or a different rendering package cohort.
HISTORICAL_AUTHORING = {
    "templateVersion": "0.13.0",
    "templateSource": "6acdfc5f5da41156db0aeaffcd54885b3b9e66be",
    "templateArchiveSha256": "ab72f74a76d59ad4be6f11f367bbdf1b27f8bdedae7a2e3afecbe0e4b3fac10c",
    "descriptorSha256": "e3f3aa1c77af9f9e559c376ffe1ad8131e205c0d68d81b4556f617b796636309",
    "renderingVersion": "0.31.0",
    "receiverRenderingVersion": "0.31.0",
    "renderingReferenceSha256": "98ba3cf0a2a1db103ca7ac1711017062bf2c3697d59a0880e376c3629c5953b6",
    "observerSha256": "3c2849f82203f136f73decfae230e2ab9aa06949c7d410307bf910e054298637",
}


def authoring_contract(subject):
    if subject != HISTORICAL_AUTHORING:
        raise ValueError("Historical authoring contract requires the exact immutable0.13/0.31 receipt")
    return "svg-authoring-observe-v013.mjs"


def bounded_source(path, maximum):
    if not path.is_file() or path.is_symlink() or path.stat().st_size > maximum:
        raise ValueError("Historical observer binding requires bounded regular inputs")
    with path.open("rb") as stream:
        raw = stream.read(maximum + 1)
    if len(raw) > maximum:
        raise ValueError("Historical observer binding input grew beyond its bound")
    return raw


def bind_authoring_observer(archive, version, revision, archive_sha, descriptor_sha,
                            descriptor, rendering_version, reference, receiver, output):
    # Hash the actual artifacts, not caller declarations. The owning public
    # route also validates every released Rendering Fable member against this
    # frozen reference before it executes the receiver.
    observer = Path(__file__).with_name("svg-authoring-observe-v013.mjs")
    observer_bytes = bounded_source(observer, 64 * 1024)
    project = ET.fromstring(bounded_source(receiver / "SvgFoundation/Studio/Studio.fsproj", 64 * 1024))
    defaults = [node.text for node in project.iter() if node.tag == "FsGgSvgAuthoringVersion"]
    if len(defaults) != 1:
        raise ValueError("Historical Studio rendering default must be unambiguous")
    subject = {
        "templateVersion": version, "templateSource": revision,
        "templateArchiveSha256": sha(bounded_source(archive, 32 * 1024 * 1024)),
        "descriptorSha256": sha(bounded_source(descriptor, 64 * 1024)),
        "renderingVersion": rendering_version, "receiverRenderingVersion": defaults[0],
        "renderingReferenceSha256": sha(bounded_source(reference, 2 * 1024 * 1024)),
        "observerSha256": sha(observer_bytes),
    }
    if archive_sha != subject["templateArchiveSha256"] or descriptor_sha != subject["descriptorSha256"]:
        raise ValueError("Historical authoring declared hashes differ from actual inputs")
    selected = authoring_contract(subject)
    if selected != observer.name or output.exists() or output.is_symlink():
        raise ValueError("Historical authoring requires a new exact observer destination")
    with output.open("xb") as stream:
        stream.write(observer_bytes)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--archive", type=Path, required=True)
    parser.add_argument("--version", required=True)
    parser.add_argument("--revision", required=True)
    parser.add_argument("--archive-sha256", required=True)
    parser.add_argument("--descriptor-sha256", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--bind-authoring-observer", action="store_true")
    parser.add_argument("--descriptor", type=Path)
    parser.add_argument("--rendering-version")
    parser.add_argument("--rendering-reference", type=Path)
    parser.add_argument("--receiver", type=Path)
    args = parser.parse_args()
    binding = (args.descriptor, args.rendering_version, args.rendering_reference, args.receiver)
    if args.bind_authoring_observer:
        if not all(binding):
            parser.error("Historical observer binding requires descriptor, rendering version/reference and receiver")
        bind_authoring_observer(args.archive, args.version, args.revision, args.archive_sha256,
                                args.descriptor_sha256, *binding, args.output)
    else:
        if any(binding):
            parser.error("Observer inputs require explicit --bind-authoring-observer")
        acquire(args.archive, args.version, args.revision, args.archive_sha256, args.descriptor_sha256, args.output)


if __name__ == "__main__":
    main()
