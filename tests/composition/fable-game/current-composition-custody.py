#!/usr/bin/env python3
"""Offline producer-custody readback for the typed current-composition plan (#4818).

Joins one retained, authenticated read of the original Rendering producer artifact to the typed
plan: the custody manifest must equal the typed SHA-256, name the typed version and source commit,
and be accepted by the producer's own unchanged `scripts/release-custody.py verify` against the
artifact's 19 archives and the release plan bound by the manifest. Each typed package must then equal
its custody archive entry-for-entry, except the feed-added NuGet signature, by the producer's own
`compare`. The typed plan pins the signed public bytes and the custody records the pre-signing
archives, so equality is at payload level by design; this module never equates the two hashes.

No network call is made. The acquisition itself is a separate, once-only, credentialed read whose
retained result (receipt.json, rendering-packet.zip, release-custody.json) is the input here.
"""
import hashlib
import json
import subprocess
import zipfile
from pathlib import Path

SCHEMA = 'fsgg.rendering.release-custody/v1'
PLAN_DIRECTORY = 'eng/release'


def require(ok, message):
    if not ok:
        raise ValueError(message)


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def read_receipt(evidence):
    receipt = json.loads((Path(evidence) / 'receipt.json').read_text())
    require(receipt.get('attempts') == 1 and receipt.get('exit') == 0 and receipt.get('disposition') == 'matched',
            'acquisition receipt is not a single matched read')
    return receipt


def extract_packet(archive_path, destination, custody_bytes):
    """Extract the closed 19-archive-plus-manifest population into a flat directory."""
    destination = Path(destination)
    destination.mkdir(parents=True)
    with zipfile.ZipFile(archive_path) as archive:
        require(archive.testzip() is None, 'producer artifact archive integrity failed')
        infos = archive.infolist()
        names = [info.filename for info in infos]
        require(len(names) == 20 and len(set(names)) == 20, 'producer artifact census differs')
        for info in infos:
            name = info.filename
            mode = (info.external_attr >> 16) & 0o170000
            require(name == Path(name).name and name not in ('', '.', '..') and mode in (0, 0o100000) and not info.is_dir(),
                    'producer artifact member name or type refused: ' + name)
        require(sum(name == 'release-custody.json' for name in names) == 1
                and sum(name.endswith('.nupkg') for name in names) == 19, 'producer artifact population differs')
        require(archive.read('release-custody.json') == custody_bytes, 'custody member differs from the retained manifest')
        for info in infos:
            require(info.file_size <= 64 * 1048576, 'producer artifact member exceeds its bound')
            (destination / info.filename).write_bytes(archive.read(info.filename))
    return destination


def release_plan(repository, commit, plan_digest, work):
    """Materialize the producer's scripts and the release plan whose digest the manifest binds."""
    run = lambda *args: subprocess.run(['git', '-C', str(repository), *args], capture_output=True, check=True)
    require(run('cat-file', '-t', commit).stdout.strip() == b'commit', 'producer source commit is not present')
    work = Path(work)
    work.mkdir(parents=True)
    archive = subprocess.run(['git', '-C', str(repository), 'archive', commit, 'scripts', PLAN_DIRECTORY], capture_output=True, check=True)
    subprocess.run(['tar', '-x', '-C', str(work)], input=archive.stdout, check=True)
    plans = [path for path in sorted((work / PLAN_DIRECTORY).glob('*.json')) if sha256(path.read_bytes()) == plan_digest]
    require(len(plans) == 1, 'the release plan bound by the manifest is not uniquely present at the producer commit')
    script = work / 'scripts/release-custody.py'
    require(script.is_file(), 'producer custody script absent at the producer commit')
    return script, plans[0]


def binder(script, *args):
    result = subprocess.run(['python3', '-I', '-B', str(script), *args], capture_output=True, text=True, timeout=300)
    require(result.returncode == 0, 'producer custody binder refused: ' + (result.stderr or result.stdout)[-1000:])
    return result.stdout.strip()


def verify_producer_custody(evidence, plan, feed, repository, work):
    """Return the facts that justify actualProducerCustodyReadback=true, or raise ValueError."""
    evidence, feed, work = Path(evidence), Path(feed), Path(work)
    receipt = read_receipt(evidence)
    archive_path, custody_path = evidence / 'rendering-packet.zip', evidence / 'release-custody.json'
    archive_bytes = archive_path.read_bytes()
    require(len(archive_bytes) == receipt['bytes'] and sha256(archive_bytes) == receipt['zipSha256'],
            'retained producer artifact differs from its receipt')
    custody = custody_path.read_bytes()
    typed = plan['rendering']
    require(sha256(custody) == typed['custodySha256'] == receipt['custodySha256'], 'custody manifest differs from the typed SHA-256')
    manifest = json.loads(custody)
    require(manifest.get('schema') == SCHEMA and manifest['version'] == typed['version']
            and manifest['source']['commit'] == typed['sourceCommit'], 'custody names a different version or source')
    packet = extract_packet(archive_path, work / 'packet', custody)
    script, release = release_plan(repository, typed['sourceCommit'], manifest['releasePlanSha256'], work / 'producer-source')
    verified = binder(script, 'verify', '--plan', str(release), '--archives', str(packet), '--manifest', str(packet / 'release-custody.json'),
                      '--source-sha', typed['sourceCommit'])
    compared = []
    for package in typed['packages']:
        name = '%s.%s.nupkg' % (package['id'], typed['version'])
        published = feed / name
        require(published.is_file() and sha256(published.read_bytes()) == package['sha256'], 'published archive differs from the typed SHA-256: ' + package['id'])
        row = [r for r in manifest['archives'] if r['file'] == name]
        require(len(row) == 1 and row[0]['sha256'] != package['sha256'], 'custody row absent or unexpectedly byte-identical to the signed archive: ' + package['id'])
        compared.append(binder(script, 'compare', '--local', str(packet / name), '--remote', str(published)))
    return {
        'acquisitionAttempts': receipt['attempts'], 'artifactBytes': receipt['bytes'], 'artifactSha256': receipt['zipSha256'],
        'custodyBytes': len(custody), 'custodySha256': sha256(custody), 'version': manifest['version'],
        'sourceCommit': manifest['source']['commit'], 'releasePlanSha256': manifest['releasePlanSha256'],
        'archivesVerified': len(manifest['archives']), 'binder': verified, 'payloadJoin': compared,
        'equality': 'payload-entry level; the typed signed archives and the custody pre-signing archives differ only by the feed signature',
    }
