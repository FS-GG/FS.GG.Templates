#!/usr/bin/env python3
"""Explicit SignalR dependency maintenance after immutable historical scaffolding."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import stat
import xml.etree.ElementTree as ET
from zipfile import ZipFile

BASELINES = {
    '0.10.0': ('69cbed30447e6bd4d221e0ce78060c8245d2744fc3993b4c27368aeeb48d11c8', '30d3c55255a95eae43b794de5170c2be7f8dba40c22bdd0b9e94673db62692ed'),
    '0.11.0': ('41fa91ba1674a4c1140c4054d4e76cff00cd514462dcdb3d9b3e3cdfa22ba4d9', '169a9e87a5c680ea9de7e1b47ac69bf30af8072af024d46a96187469e02c3667'),
}
MANIFEST_SHA = 'c4f9790fdcddb607362a9a9a3c86c2135f2b49e58e0b766ea61897175017c982'
MANIFEST = 'Server.Tests/Server.Tests.fsproj'
LOCK = 'Server.Tests/packages.lock.json'
PACKAGE = 'Microsoft.AspNetCore.SignalR.Client'
OLD = b'<PackageReference Include="Microsoft.AspNetCore.SignalR.Client" Version="10.0.0" />'
NEW = OLD.replace(b'10.0.0', b'10.0.13')
PUBLIC_CONFIG = '<configuration><packageSources><clear/><add key="public" value="https://api.nuget.org/v3/index.json"/></packageSources></configuration>\n'
SCHEMA = 'fsgg.historical-receiver-dependency-maintenance/1'


def require(value, message):
    if not value:
        raise ValueError(message)


def sha(path):
    require(path.is_file() and not path.is_symlink() and path.stat().st_size <= 8388608, 'regular bounded file required: ' + str(path))
    return hashlib.sha256(path.read_bytes()).hexdigest()


def snapshot(root):
    rows = {}
    total = 0
    directories = 0
    pending = [root]
    while pending:
        directory = pending.pop()
        directories += 1
        require(directories <= 10000, 'source directory snapshot bound exceeded')
        with os.scandir(directory) as entries:
            for entry in entries:
                if entry.name in ('obj', 'bin', '.nuget'):
                    continue  # Prune declared outputs before traversing package/build caches.
                path = Path(entry.path)
                relative = path.relative_to(root)
                require(not entry.is_symlink(), 'source symlink refused: ' + str(relative))
                if entry.is_dir(follow_symlinks=False):
                    require(len(pending) + directories < 10000, 'source directory snapshot bound exceeded')
                    pending.append(path)
                    continue
                require(entry.is_file(follow_symlinks=False), 'nonregular source refused: ' + str(relative))
                total += entry.stat(follow_symlinks=False).st_size
                require(len(rows) < 10000 and total <= 67108864, 'source snapshot bound exceeded')
                rows[str(relative)] = [sha(path), stat.S_IMODE(entry.stat(follow_symlinks=False).st_mode)]
    return rows


def guard_archive(archive, version):
    require(version in BASELINES and sha(archive) == BASELINES[version][0], 'immutable historical archive mismatch')


def prepare(receiver, archive, version, config, state):
    require(receiver.is_absolute() and receiver.is_dir() and not receiver.is_symlink(), 'absolute real receiver required')
    require(not state.exists() and not state.is_symlink() and not state.is_relative_to(receiver), 'fresh external state required')
    guard_archive(archive, version)
    require(config.is_file() and not config.is_symlink() and config.read_text() == PUBLIC_CONFIG, 'closed public-only configuration required')
    manifest = receiver / MANIFEST
    lock = receiver / LOCK
    require(sha(manifest) == MANIFEST_SHA, 'original historical manifest mismatch')
    require(sha(lock) == BASELINES[version][1], 'original historical lock mismatch')
    raw = manifest.read_bytes()
    references = [node for node in ET.fromstring(raw).iter('PackageReference') if node.get('Include') == PACKAGE]
    require(len(references) == 1 and references[0].get('Version') == '10.0.0' and raw.count(OLD) == 1, 'exact original SignalR reference required')
    before = snapshot(receiver)
    expected = raw.replace(OLD, NEW)
    record = {'schema': SCHEMA, 'phase': 'prepared-not-restored', 'receiver': str(receiver), 'archive': str(archive), 'historicalTemplateVersion': version,
              'archiveSha256': sha(archive), 'publicConfig': str(config), 'publicConfigSha256': sha(config), 'sourceBefore': before,
              'originalManifestSha256': sha(manifest), 'originalLockSha256': sha(lock), 'expectedManifestSha256': hashlib.sha256(expected).hexdigest(),
              'originalDependencies': json.loads(lock.read_text())['dependencies']}
    with state.open('x') as output:
        json.dump(record, output, indent=2)
        output.write('\n')
    manifest.write_bytes(expected)
    return record


def closure(graph, name):
    result = set()
    pending = [name]
    while pending:
        name = pending.pop()
        if name in result:
            continue
        result.add(name)
        pending.extend(graph.get(name, {}).get('dependencies', {}))
    return result


def finish(receiver, archive, version, config, state, restore_log, output):
    require(not output.exists() and not output.is_symlink() and not output.is_relative_to(receiver), 'fresh external receipt required')
    guard_archive(archive, version)
    saved = json.loads(state.read_text())
    require(saved['schema'] == SCHEMA and saved['phase'] == 'prepared-not-restored' and saved['receiver'] == str(receiver)
            and saved['archive'] == str(archive) and saved['historicalTemplateVersion'] == version and saved['archiveSha256'] == sha(archive), 'stale maintenance state')
    require(saved['publicConfig'] == str(config) and saved['publicConfigSha256'] == sha(config) and config.read_text() == PUBLIC_CONFIG, 'public configuration changed')
    after = snapshot(receiver)
    before = saved['sourceBefore']
    require(set(after) == set(before), 'unexpected source population mutation')
    changed = {name for name in before if before[name] != after[name]}
    serializer_restorations = []
    for name in sorted(changed - {MANIFEST, LOCK}):
        require(name.endswith('/packages.lock.json') and before[name][1] == after[name][1], 'mutation outside exact manifest/lock maintenance')
        # NuGet400 omits the final LF when rewriting an unchanged v1 lock.
        # Restore only that observed serializer difference, authenticated against
        # both the immutable archive and the pre-maintenance source hash.
        with ZipFile(archive) as package:
            member = 'content/templates/fs-gg-fable-game/' + name
            entries = [row for row in package.infolist() if row.filename == member]
            require(len(entries) == 1 and entries[0].file_size <= 1048576, 'bounded original unrelated lock required')
            original = package.read(entries[0])
        path = receiver / name
        require(hashlib.sha256(original).hexdigest() == before[name][0] and original.endswith(b'\n')
                and path.read_bytes() == original[:-1], 'unrelated lock differs beyond serializer final LF: ' + name)
        serializer_restorations.append({'path': name, 'observedSha256': after[name][0], 'restoredSha256': before[name][0]})
        path.write_bytes(original)
    after = snapshot(receiver)
    changed = {name for name in before if before[name] != after[name]}
    require(changed == {MANIFEST, LOCK}, 'mutation outside exact manifest/lock maintenance')
    require(after[MANIFEST][0] == saved['expectedManifestSha256'] and after[MANIFEST][1] == before[MANIFEST][1]
            and after[LOCK][1] == before[LOCK][1], 'upgraded manifest or modes differ')
    old = saved['originalDependencies']
    new = json.loads((receiver / LOCK).read_text())['dependencies']
    require(set(old) == set(new), 'framework graph drift')
    for framework, graph in new.items():
        original = old[framework]
        require(graph[PACKAGE]['type'] == 'Direct' and graph[PACKAGE]['resolved'] == '10.0.13' and graph[PACKAGE]['requested'] == '[10.0.13, )', 'patched direct dependency missing')
        require(graph['Microsoft.AspNetCore.SignalR.Common']['resolved'] == '10.0.13', 'vulnerable resolved SignalR.Common remains')
        related = closure(original, PACKAGE) | closure(graph, PACKAGE)
        for name in set(original) | set(graph):
            if name not in related:
                require(original.get(name) == graph.get(name), 'unrelated lock dependency drift: ' + name)
        for name, row in original.items():
            if row['type'] == 'Direct' and name != PACKAGE:
                require(row == graph.get(name), 'unrelated direct dependency drift: ' + name)
    require(sha(restore_log), 'restore log missing')
    record = {'schema': SCHEMA, 'phase': 'audited-public-regeneration-and-locked-restore-passed',
              'historicalTemplateVersion': version, 'archiveSha256': saved['archiveSha256'],
              'originalManifestSha256': saved['originalManifestSha256'], 'originalLockSha256': saved['originalLockSha256'],
              'upgradedManifestSha256': sha(receiver / MANIFEST), 'upgradedLockSha256': sha(receiver / LOCK),
              'directPackage': PACKAGE, 'directVersion': '10.0.13', 'resolvedSignalRCommon': '10.0.13',
              'publicSource': 'https://api.nuget.org/v3/index.json', 'publicConfigSha256': sha(config),
              'restoreLogSha256': sha(restore_log), 'sourcePreservation': 'only-declared-manifest-and-adjacent-lock-changed',
              'serializerRestorations': serializer_restorations,
              'executionBoundary': 'root-build-test-browser-must-run-after-maintenance'}
    with output.open('x') as stream:
        json.dump(record, stream, indent=2)
        stream.write('\n')
    return record


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('action', choices=['prepare', 'finish'])
    for name in ('receiver', 'archive', 'config', 'state'):
        parser.add_argument('--' + name, type=Path, required=True)
    parser.add_argument('--version', required=True)
    parser.add_argument('--restore-log', type=Path)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    if args.action == 'prepare':
        prepare(args.receiver, args.archive, args.version, args.config, args.state)
    else:
        require(args.restore_log is not None and args.output is not None, 'finish needs original successful restore log and fresh output')
        finish(args.receiver, args.archive, args.version, args.config, args.state, args.restore_log, args.output)


if __name__ == '__main__':
    main()
