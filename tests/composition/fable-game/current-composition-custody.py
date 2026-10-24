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
import io
import json
import os
import re
import subprocess
import zipfile
from pathlib import Path

SCHEMA = 'fsgg.rendering.release-custody/v1'
PLAN_DIRECTORY = 'eng/release'


def child_env():
    """Local git/tar/python children need no credential, global git configuration or home directory."""
    return {'PATH': os.environ.get('PATH', ''), 'LANG': 'C.UTF-8', 'GIT_CONFIG_NOSYSTEM': '1', 'GIT_CONFIG_GLOBAL': os.devnull}


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


def extract_packet(archive_bytes, destination, custody_bytes):
    """Extract the closed 19-archive-plus-manifest population into a flat directory."""
    destination = Path(destination)
    destination.mkdir(parents=True)
    with zipfile.ZipFile(io.BytesIO(archive_bytes)) as archive:
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
    """Read the producer's script and the release plan whose digest the manifest binds, as exact blobs at the commit."""
    require(re.fullmatch(r'[0-9a-f]{40}', commit) is not None, 'producer source commit is not a full SHA')
    git = lambda *args: subprocess.run(['git', '-C', str(repository), *args], capture_output=True, check=True, env=child_env()).stdout
    require(git('cat-file', '-t', commit).strip() == b'commit', 'producer source commit is not present')
    work = Path(work)
    (work / 'scripts').mkdir(parents=True)
    (work / PLAN_DIRECTORY).mkdir(parents=True)
    (work / 'scripts/release-custody.py').write_bytes(git('show', commit + ':scripts/release-custody.py'))
    plans = []
    for name in git('ls-tree', '--name-only', commit, PLAN_DIRECTORY + '/').decode().split():
        if name.endswith('.json'):
            blob = git('show', commit + ':' + name)
            if sha256(blob) == plan_digest:
                plans.append(work / name)
                plans[-1].write_bytes(blob)
    require(len(plans) == 1, 'the release plan bound by the manifest is not uniquely present at the producer commit')
    return work / 'scripts/release-custody.py', plans[0]


def binder(script, *args):
    result = subprocess.run(['python3', '-I', '-B', str(script), *args], capture_output=True, text=True, timeout=300, env=child_env())
    require(result.returncode == 0, 'producer custody binder refused: ' + (result.stderr or result.stdout)[-1000:])
    return result.stdout.strip()


def published_urls(evidence, template='https://api.nuget.org/v3-flatcontainer/{id}/{version}/{file}'):
    """(file, url) for every archive named by the retained custody manifest; the caller does the unauthenticated read."""
    manifest = json.loads((Path(evidence) / 'release-custody.json').read_text())
    return [(row['file'], template.format(id=row['id'].lower(), version=row['version'], file=row['file'].lower())) for row in manifest['archives']]


def verify_producer_custody(evidence, plan, feed, repository, work, published_all=None):
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
    packet = extract_packet(archive_bytes, work / 'packet', custody)
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
        outcome = binder(script, 'compare', '--local', str(packet / name), '--remote', str(published))
        require('payload entries exact' in outcome and 'feed signature=present (excluded)' in outcome,
                'published archive is not the custody archive plus the feed signature: ' + package['id'])
        compared.append(outcome)
    published = None
    if published_all is not None:
        # Every custody archive against the signed bytes served publicly (the read needs no credential).
        published_all = Path(published_all)
        require(sorted(p.name for p in published_all.iterdir()) == sorted(r['file'] for r in manifest['archives']),
                'published population differs from the custody archives')
        published = []
        for row in sorted(manifest['archives'], key=lambda r: r['id']):
            data = (published_all / row['file']).read_bytes()
            typed_row = [p for p in typed['packages'] if '%s.%s.nupkg' % (p['id'], typed['version']) == row['file']]
            require(not typed_row or typed_row[0]['sha256'] == sha256(data), 'published archive differs from the typed SHA-256: ' + row['id'])
            require(sha256(data) != row['sha256'], 'custody row unexpectedly byte-identical to the signed archive: ' + row['id'])
            outcome = binder(script, 'compare', '--local', str(packet / row['file']), '--remote', str(published_all / row['file']))
            require('payload entries exact' in outcome and 'feed signature=present (excluded)' in outcome,
                    'published archive is not the custody archive plus the feed signature: ' + row['id'])
            with zipfile.ZipFile(io.BytesIO(data)) as archive:
                signatures = [n for n in archive.namelist() if n.endswith('.signature.p7s')]
            require(len(signatures) == 1, 'published archive does not carry exactly one feed signature: ' + row['id'])
            custody_size = (packet / row['file']).stat().st_size
            published.append({'id': row['id'], 'custodyBytes': custody_size, 'publishedBytes': len(data), 'signatureOverheadBytes': len(data) - custody_size,
                              'publishedSha256': sha256(data), 'compare': 'payload-exact'})
    return {
        'publishedPayload': published,
        'acquisitionAttempts': receipt['attempts'], 'artifactBytes': receipt['bytes'], 'artifactSha256': receipt['zipSha256'],
        'custodyBytes': len(custody), 'custodySha256': sha256(custody), 'version': manifest['version'],
        'sourceCommit': manifest['source']['commit'], 'releasePlanSha256': manifest['releasePlanSha256'],
        'archivesVerified': len(manifest['archives']), 'binder': verified, 'payloadJoin': compared,
        'equality': 'payload-entry level: every entry of the custody archive is identical in the published archive, which adds only the feed signature entry',
    }
