#!/usr/bin/env python3
"""Explicit SignalR dependency maintenance after immutable historical scaffolding."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import stat
import sys
import xml.etree.ElementTree as ET
from zipfile import ZipFile

BASELINES = {
    '0.10.0': ('69cbed30447e6bd4d221e0ce78060c8245d2744fc3993b4c27368aeeb48d11c8', '30d3c55255a95eae43b794de5170c2be7f8dba40c22bdd0b9e94673db62692ed'),
    '0.13.0': ('ab72f74a76d59ad4be6f11f367bbdf1b27f8bdedae7a2e3afecbe0e4b3fac10c', '2704b23dfd50ab3f14a071389b1062395a787216ce6ae791141126c267bc4d0f'),
    '0.11.0': ('41fa91ba1674a4c1140c4054d4e76cff00cd514462dcdb3d9b3e3cdfa22ba4d9', '169a9e87a5c680ea9de7e1b47ac69bf30af8072af024d46a96187469e02c3667'),
}
MANIFEST_SHA = 'c4f9790fdcddb607362a9a9a3c86c2135f2b49e58e0b766ea61897175017c982'
MANIFEST_SHAS = {'0.13.0': 'a83102b36379d00e162d94d5578644c2704608ae5abca7b2ea99655bc1aee36d'}
MANIFEST = 'Server.Tests/Server.Tests.fsproj'
LOCK = 'Server.Tests/packages.lock.json'
PACKAGE = 'Microsoft.AspNetCore.SignalR.Client'
OLD = b'<PackageReference Include="Microsoft.AspNetCore.SignalR.Client" Version="10.0.0" />'
NEW = OLD.replace(b'10.0.0', b'10.0.13')
PUBLIC_CONFIG = '<configuration><packageSources><clear/><add key="public" value="https://api.nuget.org/v3/index.json"/></packageSources></configuration>\n'
SCHEMA = 'fsgg.receiver-dependency-maintenance/2'
LEGACY_VERSION = '0.19.0'
LEGACY_ARCHIVE = '187c995806bb2f22db67c8a9a67c251f46f339bf6350b8051035935d308b497f'
LEGACY_MANIFEST = 'dc20f88542eb2195df32009326b0649fd00c8e62fffa8d676d9fe56033b3bd14'
LEGACY_LOCK = 'a7e11044ee37bc544a6135646d94e2b7f97984153d83db07b5d7f2a9b0bab406'
LEGACY_MEMBER = 'content/templates/fs-gg-fable-game-legacy/'
LEGACY_CONFIG = 'dd8feae9693b7b7dae3bda1b3cf7ea61c9b6cc5a568e8efeed5021c56d086e34'
WIZARD_ARCHIVE = '9c5337aeccc731c68242d176f471b8f4f5e85124642f6543f9c6092f55dadb30'
WIZARD_DESCRIPTOR = 'aada25f0300421ebc10efc79414ce5c697e6a4e31d28b9c45d69c5c01d559660'


def wizard_guard(receiver, archive, registry, wizard_archive, output):
    """Authenticate the separately admitted legacy selector before any adoption."""
    require(receiver.is_absolute() and receiver.is_dir() and not receiver.is_symlink(), 'absolute real Wizard receiver required')
    require(not output.exists() and not output.is_symlink() and not output.is_relative_to(receiver), 'fresh external Wizard evidence required')
    observed = {'schema': 'fsgg.wizard-legacy-compatibility/1', 'phase': 'refused', 'receiver': str(receiver)}
    try:
        require(receiver.name == 'wizard', 'Wizard receiver role required')
        observed.update(archiveSha256=sha(archive), wizardArchiveSha256=sha(wizard_archive), registrySha256=sha(registry))
        observed.update(originalManifestSha256=sha(receiver / MANIFEST), originalLockSha256=sha(receiver / LOCK),
                        descriptorSha256=sha(receiver / '.fsgg/providers.yml'), provenanceSha256=sha(receiver / '.fsgg/scaffold-provenance.json'))
        require(observed['archiveSha256'] == LEGACY_ARCHIVE and observed['wizardArchiveSha256'] == WIZARD_ARCHIVE, 'exact public Wizard/template archive required')
        with ZipFile(wizard_archive) as package:
            metadata = ET.fromstring(package.read('FS.GG.NewSddWorkspace.nuspec')).find('{*}metadata')
            require(metadata.findtext('{*}version') == '0.11.1' and metadata.find('{*}repository').get('commit') == 'f0f6d13313c90ae38bff42416e90b6b36bc7161d', 'Wizard source mismatch')
        records = json.loads(registry.read_text(encoding='utf-8-sig'))['Packages']
        require(len(records) == 1, 'sole template registry entry required')
        entry = records[0]
        require(entry['Details']['PackageId'] == 'FS.GG.Workspace.Template' and entry['Details']['Version'] == LEGACY_VERSION
                and sha(Path(entry['MountPointUri'])) == LEGACY_ARCHIVE, 'actual installed template registry mismatch')
        with ZipFile(archive) as package:
            metadata = ET.fromstring(package.read('FS.GG.Workspace.Template.nuspec')).find('{*}metadata')
            require(metadata.findtext('{*}version') == LEGACY_VERSION and metadata.find('{*}repository').get('commit') == '8952e1c5753b0abc972154c7596ddc8da772b271', 'template source mismatch')
            raw = package.read(LEGACY_MEMBER + '.template.config/template.json')
            config = json.loads(raw)
            require(hashlib.sha256(raw).hexdigest() == LEGACY_CONFIG and config['identity'] == 'FS.GG.Workspace.Template.FableGame.LegacySvgFoundation'
                    and config['symbols']['svgFoundation']['isRequired'] and 'bundle' not in config['symbols'], 'legacy member/config mismatch')
            primary = json.loads(package.read('content/templates/fs-gg-fable-game/.template.config/template.json'))
            require('svgFoundation' not in primary['symbols'], 'template member selection ambiguous')
            for name, digest in ((MANIFEST, LEGACY_MANIFEST), (LOCK, LEGACY_LOCK)):
                require(sha(receiver / name) == digest and package.read(LEGACY_MEMBER + name) == (receiver / name).read_bytes(), 'original legacy manifest/lock mismatch')
        descriptor = receiver / '.fsgg/providers.yml'
        require(sha(descriptor) == WIZARD_DESCRIPTOR, 'requested historical descriptor mismatch')
        provenance = receiver / '.fsgg/scaffold-provenance.json'
        data = json.loads(provenance.read_text())
        require(data['generator']['version'] == '1.7.0' and data['outcome'] == 'providerSucceeded'
                and data['effectiveParameters'] == [{'key': 'lifecycle', 'value': 'none'}, {'key': 'productName', 'value': 'WizardReceiver'}, {'key': 'rootNamespace', 'value': 'WizardReceiver'}, {'key': 'svgFoundation', 'value': 'false'}], 'effective legacy parameters mismatch')
        require(not (receiver / 'SvgFoundation').exists() and json.loads((receiver / '.fsgg/workspace-initialization.json').read_text())['status'] == 'pending', 'initial legacy lifecycle mismatch')
        observed.update(phase='exact-original-before-adoption', descriptorVersion='0.11.0', scaffoldTemplateVersion=LEGACY_VERSION,
                        templateSource='8952e1c5753b0abc972154c7596ddc8da772b271', member=LEGACY_MEMBER, legacyConfigSha256=LEGACY_CONFIG,
                        wizardVersion='0.11.1', sddVersion='1.7.0', templatePinning=False, selection='legacy-default-update-observed-exact',
                        effectiveParameters=data['effectiveParameters'], providerArgvObservation='not-emitted-by-successful-SDD-1.7',
                        originalManifestSha256=sha(receiver / MANIFEST), originalLockSha256=sha(receiver / LOCK), descriptorSha256=sha(descriptor), provenanceSha256=sha(provenance))
        return observed
    except Exception as error:
        observed['firstCause'] = str(error)
        raise
    finally:
        with output.open('x') as stream:
            json.dump(observed, stream, indent=2); stream.write('\n')


def baseline(receiver, archive, version, evidence):
    if version != LEGACY_VERSION:
        guard_archive(archive, version)
        require(evidence is None, 'historical receiver cannot use Wizard compatibility evidence')
        return MANIFEST_SHAS.get(version, MANIFEST_SHA), BASELINES[version][1], OLD, 'content/templates/fs-gg-fable-game/', 'historical'
    require(receiver.name == 'wizard' and evidence is not None, 'distinct Wizard legacy role/evidence required')
    require(sha(archive) == LEGACY_ARCHIVE, 'immutable legacy archive mismatch')
    record = json.loads(evidence.read_text())
    require(record['phase'] == 'exact-original-before-adoption' and record['receiver'] == str(receiver)
            and record['archiveSha256'] == LEGACY_ARCHIVE and record['member'] == LEGACY_MEMBER
            and record['legacyConfigSha256'] == LEGACY_CONFIG and record['templatePinning'] is False, 'stale Wizard compatibility evidence')
    return LEGACY_MANIFEST, LEGACY_LOCK, OLD.replace(b'10.0.0', b'10.0.12'), LEGACY_MEMBER, 'wizard-legacy-compatibility'


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


def prepare(receiver, archive, version, config, state, evidence=None):
    require(receiver.is_absolute() and receiver.is_dir() and not receiver.is_symlink(), 'absolute real receiver required')
    require(not state.exists() and not state.is_symlink() and not state.is_relative_to(receiver), 'fresh external state required')
    manifest_sha, lock_sha, old, member, cohort = baseline(receiver, archive, version, evidence)
    require(config.is_file() and not config.is_symlink() and config.read_text() == PUBLIC_CONFIG, 'closed public-only configuration required')
    manifest = receiver / MANIFEST
    lock = receiver / LOCK
    require(sha(manifest) == manifest_sha, 'original historical manifest mismatch')
    require(sha(lock) == lock_sha, 'original historical lock mismatch')
    raw = manifest.read_bytes()
    references = [node for node in ET.fromstring(raw).iter('PackageReference') if node.get('Include') == PACKAGE]
    require(len(references) == 1 and references[0].get('Version') == ('10.0.12' if version == LEGACY_VERSION else '10.0.0') and raw.count(old) == 1, 'exact original SignalR reference required')
    before = snapshot(receiver)
    expected = raw.replace(old, NEW)
    record = {'schema': SCHEMA, 'phase': 'prepared-not-restored', 'receiver': str(receiver), 'archive': str(archive), 'historicalTemplateVersion': version,
              'archiveSha256': sha(archive), 'publicConfig': str(config), 'publicConfigSha256': sha(config), 'sourceBefore': before,
              'originalManifestSha256': sha(manifest), 'originalLockSha256': sha(lock), 'expectedManifestSha256': hashlib.sha256(expected).hexdigest(),
              'originalDependencies': json.loads(lock.read_text())['dependencies']}
    record.update(scaffoldTemplateVersion=version, cohort=cohort, archiveMember=member, wizardEvidenceSha256=sha(evidence) if evidence else None)
    if version == LEGACY_VERSION:
        del record['historicalTemplateVersion']
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


def finish(receiver, archive, version, config, state, restore_log, output, evidence=None):
    require(not output.exists() and not output.is_symlink() and not output.is_relative_to(receiver), 'fresh external receipt required')
    _, _, _, member, cohort = baseline(receiver, archive, version, evidence)
    saved = json.loads(state.read_text())
    require(saved['schema'] == SCHEMA and saved['phase'] == 'prepared-not-restored' and saved['receiver'] == str(receiver)
            and saved['archive'] == str(archive) and saved['scaffoldTemplateVersion'] == version and saved['archiveSha256'] == sha(archive)
            and saved['cohort'] == cohort and saved['archiveMember'] == member and saved['wizardEvidenceSha256'] == (sha(evidence) if evidence else None), 'stale maintenance state')
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
            entries = [row for row in package.infolist() if row.filename == member + name]
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
    record.update(scaffoldTemplateVersion=version, cohort=cohort, archiveMember=member, wizardEvidenceSha256=saved['wizardEvidenceSha256'])
    if version == LEGACY_VERSION:
        del record['historicalTemplateVersion']
    with output.open('x') as stream:
        json.dump(record, stream, indent=2)
        stream.write('\n')
    return record


def main():
    if len(sys.argv) > 1 and sys.argv[1] == 'wizard-guard':
        parser = argparse.ArgumentParser()
        for name in ('receiver', 'archive', 'registry', 'wizard-archive', 'output'):
            parser.add_argument('--' + name, type=Path, required=True)
        args = parser.parse_args(sys.argv[2:])
        wizard_guard(args.receiver, args.archive, args.registry, args.wizard_archive, args.output)
        return
    parser = argparse.ArgumentParser()
    parser.add_argument('action', choices=['prepare', 'finish'])
    for name in ('receiver', 'archive', 'config', 'state'):
        parser.add_argument('--' + name, type=Path, required=True)
    parser.add_argument('--version', required=True)
    parser.add_argument('--restore-log', type=Path)
    parser.add_argument('--output', type=Path)
    parser.add_argument('--wizard-evidence', type=Path)
    args = parser.parse_args()
    if args.action == 'prepare':
        prepare(args.receiver, args.archive, args.version, args.config, args.state, args.wizard_evidence)
    else:
        require(args.restore_log is not None and args.output is not None, 'finish needs original successful restore log and fresh output')
        finish(args.receiver, args.archive, args.version, args.config, args.state, args.restore_log, args.output, args.wizard_evidence)


if __name__ == '__main__':
    main()
