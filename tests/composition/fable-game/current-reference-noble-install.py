#!/usr/bin/env python3
"""Hosted snapshot provisioning for the current-public full route (FS-GG/.github#4817).

Installs the 32 exact roots of fixtures/noble-source-prefix-request.json from the signed Ubuntu snapshot
20261024T000000Z, using a private keyring-pinned `Signed-By` source and `--no-install-recommends`, then reads
installed versions, .deb hashes and file hashes back against the supplied facility manifest and refuses on any
difference.

  --simulate   private apt state, no privilege, no install: proves the transaction against the runner's real dpkg
               status (refuses on any removal). Runs without admission.
  --install    holds on CURRENT_PUBLIC_AT_ADMISSION (None in source), then installs and reads back.

This is provisioning, not an AT result: no service, browser, IME or journey starts here.
"""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile

HERE = Path(__file__).resolve().parent
ROOTS = HERE / 'fixtures/noble-source-prefix-request.json'
COMMITTED = HERE / 'native-input-facility/noble-20261024.manifest.json'
KEYRING = Path('/usr/share/keyrings/ubuntu-archive-keyring.gpg')
SUITES = 'noble noble-updates noble-security'
TIMEOUT = 900


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


A = load('noble_install_acquisition', HERE / 'current-reference-noble-acquisition.py')
N = load('noble_install_native', HERE / 'current-reference-native-input.py')


class Refused(RuntimeError):
    pass


def need(value, message):
    if not value:
        raise Refused('snapshot provisioning: ' + message)


def roots():
    """The exact name=version roots; the request file is the only source."""
    value = json.loads(ROOTS.read_text())
    need(set(value) == {'schema', 'packages'}, 'closed root request required')
    N.validate_packages(value['packages'])
    rows = [(row['name'], row['version']) for row in value['packages']]
    need(len(rows) == 32, 'the 32 reviewed roots are required')
    return rows


def check_manifest_against_roots(manifest, root_rows):
    """A manifest package that is also a root must carry the root's exact version; the rest (a dependency such as
    ibus-data) are pinned by the manifest alone and checked at readback."""
    versions = dict(root_rows)
    matched = 0
    for row in manifest['packages']:
        name = row['name'].removesuffix(':amd64')
        if name in versions:
            need(versions[name] == row['version'], 'manifest version differs from root: ' + name)
            matched += 1
    need(matched >= len(manifest['packages']) - 1 and matched > 0, 'manifest packages must be the reviewed roots plus at most one dependency')
    return matched


def sources_text(keyring):
    return ('Types: deb\nURIs: %s\nSuites: %s\nComponents: main universe\nArchitectures: amd64\nSigned-By: %s\n'
            % (A.BASE, SUITES, keyring))


def prepare_private(private, keyring_source=KEYRING):
    """Private apt tree with the pinned keyring. The host's sources, preferences and lists are not consulted."""
    private = Path(private)
    need(private.is_dir() and not private.is_symlink(), 'private directory required')
    raw = Path(keyring_source).read_bytes()
    need(len(raw) <= 1024**2 and hashlib.sha256(raw).hexdigest() == A.KEYRING_SHA256, 'trusted Ubuntu archive keyring differs')
    keyring = private / 'ubuntu-archive-keyring.gpg'
    keyring.write_bytes(raw)
    for name in ['sources.d', 'lists', 'cache', 'archives', 'preferences.d']:
        (private / name).mkdir(exist_ok=True)
    (private / 'sources.d/snapshot.sources').write_text(sources_text(keyring))
    (private / 'empty.list').write_text('')
    (private / 'preferences').write_text('')
    return keyring


def apt_options(private):
    p = Path(private)
    return ['-o', 'Dir::Etc::sourcelist=%s' % (p / 'empty.list'), '-o', 'Dir::Etc::sourceparts=%s' % (p / 'sources.d'),
            '-o', 'Dir::Etc::preferences=%s' % (p / 'preferences'), '-o', 'Dir::Etc::preferencesparts=%s' % (p / 'preferences.d'),
            '-o', 'Dir::State::lists=%s' % (p / 'lists'), '-o', 'Dir::Cache=%s' % (p / 'cache'),
            '-o', 'Dir::Cache::archives=%s' % (p / 'archives'), '-o', 'Acquire::Languages=none',
            '-o', 'Acquire::Check-Valid-Until=false', '-o', 'APT::Install-Recommends=false',
            '-o', 'APT::Sandbox::User=root']


def install_argv(private, root_rows, simulate, allow_downgrades=False):
    """The one install transaction: exact roots, no recommends. apt offers --allow-downgrades only globally, so it is
    added solely when the unflagged simulation proved a downgrade is required, and the flagged simulation is then
    classified so that only root packages (pinned to their reviewed versions) may be downgraded."""
    return (['apt-get'] + apt_options(private) + (['--simulate'] if simulate else ['--yes']) +
            ['install', '--no-install-recommends'] + (['--allow-downgrades'] if allow_downgrades else []) +
            ['%s=%s' % row for row in root_rows])


CLEAN_ENV = {'PATH': '/usr/sbin:/usr/bin:/sbin:/bin', 'LANG': 'C.UTF-8', 'DEBIAN_FRONTEND': 'noninteractive'}


def run(argv, privileged=False, capture=True, cwd=None):
    argv = (['sudo', '-n', 'env', *['%s=%s' % kv for kv in CLEAN_ENV.items()]] + argv) if privileged else argv
    result = subprocess.run(argv, env=CLEAN_ENV, capture_output=capture, text=True, timeout=TIMEOUT, cwd=cwd)
    need(result.returncode == 0, 'command failed (%s): %s' % (result.returncode, ' '.join(argv[:6])) +
         ('\n' + (result.stderr or '')[-2000:] if capture else ''))
    return result.stdout if capture else ''


def version_less(new, old):
    return subprocess.run(['dpkg', '--compare-versions', new, 'lt', old]).returncode == 0


def classify_simulation(output, root_names):
    """Classify the simulated transaction on the actual image. Any removal refuses; a downgrade of a package that is
    not one of the reviewed roots refuses; downgrades of roots (to their pinned versions) are returned for the receipt."""
    inst = re.findall(r'^Inst (\S+)(?: \[([^\]]+)\])? \(([^ ]+) ', output, re.M)
    removed = re.findall(r'^Remv (\S+)', output, re.M)
    need(not removed, 'simulated transaction removes packages: ' + ', '.join(sorted(removed)[:8]))
    need(re.search(r'^\d+ upgraded, \d+ newly installed, \d+ to remove', output, re.M), 'simulation summary absent')
    downgrades = sorted(name for name, old, new in inst if old and version_less(new, old))
    stray = [name for name in downgrades if name.split(':')[0] not in root_names]
    need(not stray, 'simulated transaction downgrades non-root packages: ' + ', '.join(stray[:8]))
    return {'install': len(inst), 'rootDowngrades': downgrades, 'removals': 0}


def plan(private, root_rows):
    """Simulate the transaction on the actual image with downgrades permitted so that any are visible, classify it, and
    return (allow_downgrades, classification). The privileged install carries --allow-downgrades only when the
    classified simulation contains downgrades, and then only of root packages; otherwise it is run without the flag,
    so apt itself refuses any downgrade that was not simulated. apt cannot scope the flag to named packages."""
    names = {name for name, _ in root_rows}
    planned = classify_simulation(run(install_argv(private, root_rows, True, True)), names)
    return bool(planned['rootDowngrades']), planned


def readback(manifest, root_rows, query, download_hash, verify_files):
    """Refuse on any installed-version, .deb-hash or installed-file difference from the reviewed manifest."""
    for name, version in root_rows:
        need(query(name) == version, 'installed root version differs: %s' % name)
    for row in manifest['packages']:
        need(query(row['name']) == row['version'], 'installed package version differs: %s' % row['name'])
        need(download_hash(row['name'], row['version']) == row['debSha256'], 'package archive hash differs: %s' % row['name'])
    verify_files(manifest)
    return {'roots': len(root_rows), 'packages': len(manifest['packages']),
            'files': len(manifest['objects']) + len(manifest['dataFiles'])}


def installed_version(name):
    return run(['dpkg-query', '-W', '-f=${Version}', name]).strip()


def archive_hash_factory(private):
    def download_hash(name, version):
        target = Path(tempfile.mkdtemp(prefix='download-', dir=private))
        run(['apt-get'] + apt_options(private) + ['download', '%s=%s' % (name, version)], cwd=target)
        files = list(target.glob('*.deb'))
        need(len(files) == 1, 'one downloaded archive required: ' + name)
        return hashlib.sha256(files[0].read_bytes()).hexdigest()
    return download_hash


def manifest_value():
    raw = os.environ.get('FSGG_CURRENT_NATIVE_INPUT_FACILITY', '')
    return N.read_manifest(raw if raw else COMMITTED.read_text())


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--simulate', action='store_true')
    mode.add_argument('--install', action='store_true')
    parser.add_argument('--private', type=Path, required=True, help='fresh private working directory (0700)')
    parser.add_argument('--receipt', type=Path, help='write the closed result record here')
    args = parser.parse_args(argv)
    root_rows = roots()
    if args.install:
        # The admission guard is the existing one; the source constant stays None.
        caller = load('noble_install_caller', HERE / 'current-reference-at-caller.py')
        caller.guard(os.environ)
        raw = os.environ.get('FSGG_CURRENT_NATIVE_INPUT_FACILITY', '')
        need(raw, 'facility manifest input required for installation')
        manifest = N.read_manifest(raw)
    else:
        manifest = manifest_value()
    check_manifest_against_roots(manifest, root_rows)
    args.private.mkdir(mode=0o700, exist_ok=True)
    prepare_private(args.private)
    run(['apt-get'] + apt_options(args.private) + ['update'])
    allow, planned = plan(args.private, root_rows)
    if args.simulate:
        result = {'mode': 'simulate', 'allowDowngrades': allow, **planned}
    else:
        # The same classified transaction is the privileged one; nothing broader runs.
        run(install_argv(args.private, root_rows, False, allow), privileged=True)
        result = {'mode': 'install', 'allowDowngrades': allow, **planned,
                  **readback(manifest, root_rows, installed_version, archive_hash_factory(args.private), N.verify_files)}
    result.update(schema='fsgg.current-reference-noble-snapshot-provisioning/1', snapshot=A.BASE,
                  manifestSha256=N.sha(N.canonical(manifest)), helperSha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                  signedBy='pinned keyring sha256 ' + A.KEYRING_SHA256, installRecommends=False)
    if args.receipt:
        args.receipt.write_text(json.dumps(result, indent=2, sort_keys=True) + '\n')
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == '__main__':
    try:
        sys.exit(main())
    except Refused as error:
        print(error, file=sys.stderr)
        sys.exit(1)
