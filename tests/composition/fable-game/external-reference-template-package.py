#!/usr/bin/env python3
"""Inspect an immutable external Templates input; never pack, install or fetch."""
from pathlib import Path, PurePosixPath
import hashlib
import io
import importlib.util
import json
import re
import stat
import sys
from xml.etree import ElementTree as ET
from zipfile import ZipFile

PACKAGE_ID = 'FS.GG.Workspace.Template'
PACKAGE_VERSION = '0.18.3'


def inspect_package(path, expected_sha):
    path = Path(path)
    if not re.fullmatch('[0-9a-f]{64}', expected_sha) or path.suffix != '.nupkg' or path.is_symlink():
        raise ValueError('exact nupkg and SHA256 required')
    info = path.lstat()
    if not stat.S_ISREG(info.st_mode) or not 0 < info.st_size <= 64 * 1024**2:
        raise ValueError('regular bounded template archive required')
    with path.open('rb') as stream:
        raw = stream.read(64 * 1024**2 + 1)
    if len(raw) != info.st_size or hashlib.sha256(raw).hexdigest() != expected_sha:
        raise ValueError('external template archive identity differs')
    entries = {}; expanded = 0; seen = set()
    with ZipFile(io.BytesIO(raw)) as archive:
        infos = archive.infolist()
        if len(infos) > 20000:
            raise ValueError('template archive member bound exceeded')
        for member in infos:
            name = member.filename
            if (not name or name.startswith('/') or '\\' in name or ':' in name or '\0' in name
                    or '..' in PurePosixPath(name).parts or PurePosixPath(name).as_posix() != name.rstrip('/')
                    or name in seen or (member.external_attr >> 16) & 0o170000 == 0o120000
                    or member.file_size > 16 * 1024**2):
                raise ValueError('unsafe or duplicate template archive member')
            seen.add(name)
            expanded += member.file_size
            if expanded > 256 * 1024**2:
                raise ValueError('template archive expansion bound exceeded')
            if not member.is_dir():
                entries[name] = archive.read(member)
        nuspecs = [name for name in entries if name.endswith('.nuspec')]
        if len(nuspecs) != 1 or len(entries[nuspecs[0]]) > 1024**2 or b'<!DOCTYPE' in entries[nuspecs[0]].upper():
            raise ValueError('one bounded template nuspec required')
        document = ET.fromstring(entries[nuspecs[0]])
        namespace = document.tag.split('}')[0] + '}' if '}' in document.tag else ''
        metadata = document.findall(namespace + 'metadata')
        if len(metadata) != 1:
            raise ValueError('one template metadata record required')
        metadata = metadata[0]
        def field(name):
            values = metadata.findall(namespace + name)
            if len(values) != 1 or not values[0].text:
                raise ValueError('exact template metadata field required: ' + name)
            return values[0].text.strip()
        repositories = metadata.findall(namespace + 'repository')
        types = metadata.findall(namespace + 'packageTypes/' + namespace + 'packageType')
        if (field('id') != PACKAGE_ID or field('version') != PACKAGE_VERSION or len(repositories) != 1
                or repositories[0].attrib.get('url') != 'https://github.com/FS-GG/FS.GG.Templates'
                or not re.fullmatch('[0-9a-f]{40}', repositories[0].attrib.get('commit', ''))
                or len(types) != 1 or types[0].attrib.get('name') != 'Template'):
            raise ValueError('external template package id/version/repository/type differs')
        template = 'content/templates/fs-gg-fable-game/.template.config/template.json'
        if template not in entries:
            raise ValueError('external template package has no Fable workspace identity')
        definition = json.loads(entries[template])
        if (definition.get('identity') != 'FS.GG.Workspace.Template.FableGame' or
                definition.get('groupIdentity') != 'FS.GG.Workspace.Template.FableGame' or
                definition.get('shortName') != 'fs-gg-fable-game'):
            raise ValueError('external template package Fable workspace identity differs')
        payload = {name: hashlib.sha256(value).hexdigest() for name, value in sorted(entries.items())
                   if name != '.signature.p7s'}
    return {'schema': 'fsgg.external-reference-template-package-input/1', 'packageId': PACKAGE_ID,
            'version': PACKAGE_VERSION, 'archiveSha256': expected_sha, 'archiveBytes': len(raw),
            'producerRevision': repositories[0].attrib['commit'], 'payloadEntries': len(payload),
            'payloadSha256': hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(',', ':')).encode()).hexdigest(),
            'feedQualification': 'not-established', 'installedAcceptance': False}


RENDERING_SOURCE = "9b73395658d4683a067d150ca9441b04e802c4af"
RENDERING_ARCHIVES = {'FS.GG.UI.Scene': 'a501ff261f2961b527c6148cb2fa981f443e2ddc90ca48407721237df8ba90e1', 'FS.GG.UI.KeyboardInput': '081ca34bf3648c75c5fcc3624117828cea02e44877747f1a7ef1888d0ff950c4', 'FS.GG.UI.Scene.SvgBrowser': 'd02686aee0a4121a4f1effc75dbb21d6873397b809767103c92267b7a0b7ed5d'}
RENDERING_FABLE_ENTRIES = {'fable/SvgExternalSessionHost.fs': '1729ac0b88a4fc9c90376d2c21369d466739d5d2da21667859fa0ce3767aa469', 'fable/SvgExternalSessionHost.fsi': '2eb5f7ef35aef9a1de84519784793d86aecdb55b210cb2572c701df016971d6b', 'fable/SvgInputHost.fs': 'c55f5e9dfbb1d07b40fbe6ce8abc4e5d711533cd38b76c49f454122fe871c3e6', 'fable/SvgInputHost.fsi': '2fc97531a6a0d3a186fb69fe9a212aad3c98d78633dca9cceedd0b8159d636b8', 'fable-compatibility/compatibility-profile.v1.json': '162e384e18be25b93d29f242181d4ceb103f8049497dc792926f499d8d3e7f66'}

def verify_rendering_feed(feed, version, source):
    """Close external candidate mode to the original archives, not metadata claims."""
    feed = Path(feed)
    if version != '0.32.2' or source != RENDERING_SOURCE:
        raise ValueError('external package requires exact retained Rendering candidate')
    rows = []
    browser_raw = None
    for identity, expected_sha in RENDERING_ARCHIVES.items():
        path = feed / (identity + '.' + version + '.nupkg')
        if path.is_symlink() or not path.is_file() or path.stat().st_size > 64 * 1024**2:
            raise ValueError('retained Rendering archive absent or unbounded')
        with path.open('rb') as stream:
            raw = stream.read(64 * 1024**2 + 1)
        if len(raw) > 64 * 1024**2 or hashlib.sha256(raw).hexdigest() != expected_sha:
            raise ValueError('Rendering archive differs from exact original candidate')
        rows.append({'name': path.name, 'sha256': expected_sha})
        if identity == 'FS.GG.UI.Scene.SvgBrowser':
            browser_raw = raw
    with ZipFile(io.BytesIO(browser_raw)) as archive:
        for name, expected_sha in RENDERING_FABLE_ENTRIES.items():
            if hashlib.sha256(archive.read(name)).hexdigest() != expected_sha:
                raise ValueError('original packaged Fable entry differs')
    return {'schema': 'fsgg.external-reference-retained-rendering-package-input/1',
            'producerRevision': source, 'producerTree': None, 'version': version, 'archives': rows,
            'fableEntryHashes': RENDERING_FABLE_ENTRIES,
            'identitySource': 'exact-original-archive-and-Fable-entry-hashes',
            'originalOuterArtifact': 11725317255,
            'originalOuterSha256': '7b0532caf431cfa41acaf35555016cf126bc495c5a6e13fe7db6b8fbe7478cca',
            'custodyManifestSha256': '85bb1dcdf0378d05ca536d5878b88dedc301ff1524d39d98966e23888aae0120',
            'feedQualification': 'not-established', 'installedAcceptance': False}


def validate_generated(workspace):
    workspace = Path(workspace).resolve()
    spec = importlib.util.spec_from_file_location('maintained_public_references', Path(__file__).with_name('external-reference-public.py'))
    references = importlib.util.module_from_spec(spec); spec.loader.exec_module(references)
    projects = sorted([*workspace.rglob('*.fsproj'), *workspace.rglob('*.csproj'), *workspace.rglob('*.vbproj')])
    build_inputs = sorted([*projects, *workspace.rglob('*.props'), *workspace.rglob('*.targets')])
    if not projects or len(build_inputs) > 1000:
        raise ValueError('bounded generated project closure required')
    for project in build_inputs:
        if project.is_symlink() or not project.resolve().is_relative_to(workspace) or project.stat().st_size > 1024**2:
            raise ValueError('generated project escaped workspace')
        tree = ET.parse(project)
        # MSBuild's standard XML namespace has the same literal reference rules.
        for node in tree.iter():
            if node.tag.startswith('{'):
                namespace, local = node.tag[1:].split('}', 1)
                if namespace != 'http://schemas.microsoft.com/developer/msbuild/2003':
                    raise ValueError('unsupported generated build XML namespace')
                node.tag = local
        relative = project.relative_to(workspace).as_posix()
        if relative in references.LOCAL_PROJECT_REFERENCES:
            references.validate_project_references(tree, relative, workspace)
        else:
            for node in tree.findall('.//ProjectReference'):
                value = node.attrib.get('Include', '')
                if set(node.attrib) != {'Include'} or list(node) or not value or any(v in value for v in ['$', '*', '?']):
                    raise ValueError('unresolved generated project reference')
                target = project.parent / value.replace('\\', '/')
                if target.is_symlink() or not target.resolve().is_relative_to(workspace) or not target.is_file():
                    raise ValueError('generated project reference outside installed workspace')
        # Producer source must not be imported or compiled through a second path either.
        for node in tree.iter():
            if node.tag not in ['Compile', 'Import']:
                continue
            value = node.attrib.get('Include' if node.tag == 'Compile' else 'Project', '')
            if not value:
                continue
            if '$(' in value or '*' in value or '?' in value:
                raise ValueError('unresolved generated source/import path')
            target = (project.parent / value.replace('\\', '/')).resolve()
            if not target.is_relative_to(workspace):
                raise ValueError('generated source/import outside installed workspace')
    return {'schema': 'fsgg.external-reference-generated-package-workspace/1', 'projects': len(projects),
            'buildInputs': len(build_inputs), 'scope': 'literal project/source/import references in generated projects, props and targets',
            'producerSourceReferenced': False, 'installedAcceptance': False}


if __name__ == '__main__':
    if len(sys.argv) == 5 and sys.argv[1] == 'inspect':
        result = inspect_package(Path(sys.argv[2]), sys.argv[3]); output = Path(sys.argv[4])
    elif len(sys.argv) == 6 and sys.argv[1] == 'rendering':
        result = verify_rendering_feed(Path(sys.argv[2]), sys.argv[3], sys.argv[4]); output = Path(sys.argv[5])
    elif len(sys.argv) == 4 and sys.argv[1] == 'generated':
        result = validate_generated(Path(sys.argv[2])); output = Path(sys.argv[3])
    else:
        raise SystemExit('usage: external-reference-template-package.py inspect NUPKG SHA FRESH_JSON | generated WORKSPACE FRESH_JSON')
    with output.open('x', encoding='utf8') as stream:
        json.dump(result, stream, indent=2); stream.write('\n')
