"""Inspect a packed Fable binding archive: package identity, compiled binding present, no source or
bundled npm payload, no Fable.Package.SDK consumer dependency, and the binding tags.

    inspect-binding-package.py <nupkg> <package id> <version> <dll name> [--self-test]

--self-test also mutates copies of the archive into the two original defect shapes (a library
source payload, a Fable.Package.SDK dependency) and requires the inspector to reject both.
"""
import io, pathlib, re, sys, xml.etree.ElementTree as ET, zipfile

def inspect(package, package_id, version, dll):
    with zipfile.ZipFile(package) as archive:
        entries = archive.namelist()
        assert len(entries) == len(set(entries)), 'duplicate package entry'
        assert f'lib/netstandard2.1/{dll}' in entries, 'compiled binding absent'
        assert not any(n.lower().startswith('fable/') or n.lower().endswith(('.fs', '.fsi', '.fsx')) for n in entries), 'library source payload'
        assert not any('node_modules/' in n.lower() or n.lower().endswith(('.js', '.mjs', '.cjs', '.ts')) for n in entries), 'bundled native npm implementation'
        specs = [n for n in entries if n.lower().endswith('.nuspec')]
        assert len(specs) == 1, 'one package specification'
        root = ET.fromstring(archive.read(specs[0]))
        metadata = next(e for e in root if e.tag.rsplit('}', 1)[-1] == 'metadata')
        field = lambda name: next(e.text for e in metadata if e.tag.rsplit('}', 1)[-1] == name)
        assert field('id') == package_id, 'package identity'
        assert field('version') == version, 'package version'
        deps = {e.get('id', '').lower() for e in metadata.iter() if e.tag.rsplit('}', 1)[-1] == 'dependency'}
        assert 'fable.package.sdk' not in deps, 'SDK consumer dependency'
        tags = set(re.split(r'[;\s]+', (field('tags') or '').lower()))
        assert {'fable', 'fable-binding', 'fable-javascript'} <= tags and 'fable-library' not in tags, 'binding tags'

path, package_id, version, dll = sys.argv[1:5]
inspect(path, package_id, version, dll)
if '--self-test' in sys.argv:
    with zipfile.ZipFile(path) as archive:
        contents = {n: archive.read(n) for n in archive.namelist()}
    for defect in ['library-source', 'sdk-dependency']:
        mutated = dict(contents)
        if defect == 'library-source':
            mutated['fable/Bindings.fs'] = b'// synthetic library payload'
        else:
            name = next(n for n in mutated if n.lower().endswith('.nuspec'))
            root = ET.fromstring(mutated[name])
            metadata = next(e for e in root if e.tag.rsplit('}', 1)[-1] == 'metadata')
            ns = metadata.tag.rsplit('}', 1)[0] + '}' if '}' in metadata.tag else ''
            dependencies = next((e for e in metadata if e.tag.rsplit('}', 1)[-1] == 'dependencies'), None)
            if dependencies is None:
                dependencies = ET.SubElement(metadata, ns + 'dependencies')
            ET.SubElement(dependencies, ns + 'dependency', {'id': 'Fable.Package.SDK', 'version': '1.4.1'})
            mutated[name] = ET.tostring(root)
        stream = io.BytesIO()
        with zipfile.ZipFile(stream, 'w') as archive:
            for name, body in mutated.items():
                archive.writestr(name, body)
        stream.seek(0)
        try:
            inspect(stream, package_id, version, dll)
        except AssertionError:
            continue
        raise AssertionError('package inspector accepted ' + defect)
print('binding package inspected')
