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


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--archive", type=Path, required=True)
    parser.add_argument("--version", required=True)
    parser.add_argument("--revision", required=True)
    parser.add_argument("--archive-sha256", required=True)
    parser.add_argument("--descriptor-sha256", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    acquire(args.archive, args.version, args.revision, args.archive_sha256, args.descriptor_sha256, args.output)


if __name__ == "__main__":
    main()
