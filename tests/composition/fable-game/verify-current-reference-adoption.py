#!/usr/bin/env python3
"""One preserving transaction cohort on supplied materialized public receivers.

This harness launches no compiler, package manager, browser or network client.
Its receipt establishes transaction controls only; the caller owns genuine
scaffolding, exact dependency readback, builds and adopted browser qualification.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
from pathlib import Path
import shutil
import zipfile
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[3]
SPEC = importlib.util.spec_from_file_location("complete_adopter", ROOT / "scripts/apply-svg-complete-workspace.py")
adopter = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(adopter)
MANIFEST = ROOT / "scripts/svg-current-reference-adoption.json"


def require(condition, message):
    if not condition:
        raise ValueError(message)


def public_archive(path: Path, expected_sha: str, version: str) -> dict:
    require(path.is_file() and not path.is_symlink(), "public archive must be a regular file")
    require(adopter.digest(path.read_bytes()) == expected_sha, "public archive hash mismatch")
    with zipfile.ZipFile(path) as archive:
        members = [name for name in archive.namelist() if name.endswith('.nuspec')]
        require(len(members) == 1, "exactly one nuspec required")
        metadata = ET.fromstring(archive.read(members[0]))
        values = {element.tag.rsplit('}', 1)[-1]: element.text for element in metadata.iter()}
        require(values.get('id') == 'FS.GG.Workspace.Template' and values.get('version') == version,
                "public archive package identity mismatch")
    return {"version": version, "sha256": expected_sha}


def exercise(candidate: Path, receiver: Path, output: Path, manifest: Path = MANIFEST) -> dict:
    """Exercise copied receivers, leaving one adopted tree for later build gates."""
    candidate, receiver, output = [path.absolute() for path in (candidate, receiver, output)]
    require(not output.exists() and not output.is_symlink(), "evidence output must be new")
    require(not candidate.is_relative_to(output) and not receiver.is_relative_to(output)
            and not output.is_relative_to(candidate) and not output.is_relative_to(receiver),
            "output and receiver/candidate must be disjoint")
    require(candidate.is_dir() and receiver.is_dir() and not candidate.is_symlink()
            and not receiver.is_symlink(), "materialized receiver roots required")
    # Validate candidate bytes and full reference population before copying or writing.
    require(adopter.classify(candidate, receiver, manifest)["ready"], "input receiver has managed conflicts")
    output.mkdir(parents=True, mode=0o700)
    controls = []

    def copy(name):
        path = output / name
        shutil.copytree(receiver, path, symlinks=True)
        return path

    def observe(path):
        return adopter.tree_observation(path)[0]

    def inventory(workspace, name):
        inv, review = output / (name + '.json'), output / (name + '.diff')
        adopter.inventory(list(map(str, [candidate, workspace, manifest, inv, review])))
        return inv

    def apply(workspace, name):
        inv = inventory(workspace, name)
        backup = output / (name + '-backup')
        adopter.apply(list(map(str, [candidate, workspace, manifest, inv, backup])))
        return backup

    def refused(call, code):
        try:
            call()
        except SystemExit as error:
            require(error.code == code, 'unexpected refusal code')
        else:
            raise ValueError('negative control unexpectedly succeeded')

    adopted = copy('adopted')
    original = adopter.classify(candidate, adopted, manifest)
    preserved = {row['path']: row for row in original['workspaceFiles'] if row['path'] in original['preserved']}
    apply(adopted, 'apply')
    final = adopter.classify(candidate, adopted, manifest)
    require(final['ready'] and not final['changes'], 'adopted product does not match full target')
    after = {row['path']: row for row in final['workspaceFiles']}
    require(all(after.get(path) == row for path, row in preserved.items()), 'preserved bytes/modes changed')
    controls.append('adopted-full-reference-and-preserved-files')

    for name, logical in [('managed-conflict', 'Domain/Room.fs'),
                          ('new-reference-conflict', 'SvgFoundation/Examples/Wasm/WasmPolicyExample.fs')]:
        workspace = copy(name)
        path = workspace / logical
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(path.read_bytes() + b'\n// owner edit\n' if path.exists() else b'owner extension\n')
        before = observe(workspace)
        refused(lambda: inventory(workspace, name), 3)
        require(observe(workspace) == before, 'conflict changed receiver')
        controls.append(name + '-refused-before-write')

    workspace = copy('interrupted')
    before = observe(workspace)
    old = os.environ.get('FSGG_SVG_COMPLETE_FAIL_AFTER')
    try:
        os.environ['FSGG_SVG_COMPLETE_FAIL_AFTER'] = '37'
        refused(lambda: apply(workspace, 'interrupted'), 2)
    finally:
        if old is None:
            os.environ.pop('FSGG_SVG_COMPLETE_FAIL_AFTER', None)
        else:
            os.environ['FSGG_SVG_COMPLETE_FAIL_AFTER'] = old
    require(observe(workspace) == before, 'interrupted apply did not restore bytes and modes')
    controls.append('interrupted-apply-restored')

    workspace = copy('rollback')
    before = observe(workspace)
    backup = apply(workspace, 'rollback')
    old = os.environ.get('FSGG_SVG_COMPLETE_ROLLBACK_FAIL_AFTER')
    try:
        os.environ['FSGG_SVG_COMPLETE_ROLLBACK_FAIL_AFTER'] = '37'
        try:
            adopter.restore(workspace, backup)
        except RuntimeError:
            require(json.loads((backup / 'journal.json').read_text())['status'] == 'rolling-back',
                    'interrupted rollback phase missing')
        else:
            raise ValueError('rollback interruption not reached')
    finally:
        if old is None:
            os.environ.pop('FSGG_SVG_COMPLETE_ROLLBACK_FAIL_AFTER', None)
        else:
            os.environ['FSGG_SVG_COMPLETE_ROLLBACK_FAIL_AFTER'] = old
    adopter.restore(workspace, backup)
    require(observe(workspace) == before, 'rollback recovery changed bytes or modes')
    adopter.restore(workspace, backup)
    controls.append('explicit-interrupted-rollback-recovered-and-idempotent')

    receipt = {'schema': 'fsgg.current-reference-adoption-controls/v1',
               'scope': 'copied-receiver transaction controls; no scaffold/build/browser acceptance',
               'currentPublishedReference': final['currentPublishedReference'],
               'manifestSha256': adopter.digest(manifest.read_bytes()),
               'candidateManagedSha256': final['candidateManagedSha256'],
               'adopted': str(adopted), 'controls': controls,
               'requiredNext': ['genuine-generation-readback', 'locked-build', 'fable-build', 'adopted-browser-conformance']}
    (output / 'transaction-controls.json').write_text(json.dumps(receipt, indent=2) + '\n')
    return receipt


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--candidate', type=Path, required=True)
    parser.add_argument('--receiver', type=Path, required=True)
    parser.add_argument('--baseline-version', choices=['0.10.0', '0.11.0', '0.12.0', '0.13.0'], required=True)
    parser.add_argument('--baseline-archive', type=Path, required=True)
    parser.add_argument('--target-archive', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    manifest, _, _, _ = adopter.manifest_data(MANIFEST)
    baseline_sha = next(row['sha256'] for row in manifest['sourceArchives'] if row['version'] == args.baseline_version)
    baseline = public_archive(args.baseline_archive, baseline_sha, args.baseline_version)
    target = public_archive(args.target_archive, adopter.CURRENT_REFERENCE['publicArchiveSha256'], '0.19.3')
    receipt = exercise(args.candidate, args.receiver, args.output)
    receipt['suppliedPublicArchives'] = {'baseline': baseline, 'target': target}
    receipt['generationProvenance'] = 'caller must bind these archives to the actual materialized inputs'
    (args.output / 'transaction-controls.json').write_text(json.dumps(receipt, indent=2) + '\n')


if __name__ == '__main__':
    main()
