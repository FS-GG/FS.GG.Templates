"""Mechanical package-only/public restore join; never executes SDK/package code."""
import json
from pathlib import Path
import sys


def require(value, detail):
    if not value:
        raise ValueError(detail)


def check(stage):
    root = Path(stage).resolve(strict=True)
    source = root / 'source'
    for relative in ('obj/project.assets.json', 'packages.lock.json'):
        path = source / relative
        require(path.is_file() and not path.is_symlink() and path.stat().st_size <= 16*1048576,
                'missing/oversize/linked cold resolution: ' + relative)
    assets = json.loads((source / 'obj/project.assets.json').read_bytes())
    lock = json.loads((source / 'packages.lock.json').read_bytes())
    require(lock['version'] == 1, 'unsupported NuGet lock format')
    restore = assets['project']['restore']
    require(set(restore['sources']) == {'https://api.nuget.org/v3/index.json'}, 'non-public package source')
    require({folder.rstrip('/') for folder in assets['packageFolders']} == {str(root / 'packages')}, 'foreign package folder')
    require(not restore.get('fallbackFolders'), 'fallback package folders refused')
    direct = {'FS.GG.Contracts': '7.6.0', 'FS.GG.SDD.Artifacts': '2.4.0',
              'FS.GG.SDD.Commands': '2.4.0', 'FSharp.Core': '10.1.401'}
    require(len(lock['dependencies']) == 1, 'unexpected framework lock')
    dependencies = next(iter(lock['dependencies'].values()))
    require({name: row['resolved'] for name, row in dependencies.items() if row['type'] == 'Direct'} == direct,
            'direct public dependency identity differs')
    libraries = assets['libraries']
    require(libraries and len(libraries) <= 256, 'empty/oversize package closure')
    require(all(row['type'] == 'package' for row in libraries.values()), 'project/non-package dependency refused')
    for identity, row in libraries.items():
        name, version = identity.rsplit('/', 1)
        matches = [entry for key, entry in dependencies.items() if key.lower() == name.lower()]
        require(len(matches) == 1 and matches[0]['resolved'] == version and matches[0]['contentHash'] == row['sha512'],
                'asset/lock identity mismatch: ' + identity)
        relative = Path(row['path'])
        require(not relative.is_absolute() and '..' not in relative.parts, 'escaping package path')
        package = root / 'packages' / relative
        require(package.is_dir() and not package.is_symlink(), 'missing/linked package directory')
    print('cold public package-only assets/lock joined; no native/product qualification')


if __name__ == '__main__':
    check(sys.argv[1])
