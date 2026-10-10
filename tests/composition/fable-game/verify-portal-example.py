#!/usr/bin/env python3
"""Check real source/archive/generated Portal payloads; static controls are not generation proof."""
import argparse
import copy
import hashlib
import json
from pathlib import Path
import re
import shutil
import stat
import sys
import tarfile
import tempfile
import xml.etree.ElementTree as ET
from zipfile import ZipFile

PREFIX = 'templates/fs-gg-fable-game/'
GAME_REVISION = '49c7f5a74f2470f68e626b68293d5207c2068a93'
GAME_TREE = 'c2aa7259568ddb54f5397ff978ca3baa6d942255'
LOCK_SHA256 = '7769c72f28bca3fc4b40e6ce710852c8d5e26098c5e6d5c35cefbe9f7c11f66b'
CLOSURE = {'FS.GG.Game.Core':'0.17.0','FS.GG.Game.Physics.Box2D':'0.17.0','FS.GG.Game.Render':'0.17.0','FS.GG.UI.Scene':'0.31.0','FS.GG.UI.KeyboardInput':'0.31.0','Box2D.NET':'3.1.654','FSharp.Core':'10.1.302'}
CANONICAL = {'Consumer.fsproj':'tests/release/Box2D.PackageConsumer/PresentationConsumer.fsproj','PortalScene.fs':'examples/Box2D.Portals/Scene.fs','Presentation.fs':'examples/Box2D.Portals/Presentation.fs','Program.fs':'examples/Box2D.Portals/Program.fs','verify-package-boundary.py':'tests/release/Box2D.PackageConsumer/verify-package-boundary.py'}
PAYLOAD = set(CANONICAL) | {'packages.lock.json','source-provenance.json','README.md','manage.py'}
ORDINARY = ['FableGameWorkspace.slnx','Server/Server.fsproj','Domain/Domain.fsproj','Client/Client.fsproj','SvgFoundation/SvgFoundation.fsproj']


def fail(message):
    raise ValueError(message)


def digest(content):
    return hashlib.sha256(content).hexdigest()


def read_file(path):
    if path.is_symlink() or not path.is_file():
        fail(f'missing or linked input: {path}')
    return path.read_bytes()


def canonical_reader(args):
    if args.canonical_game:
        return lambda name: read_file(args.canonical_game/name)
    if not args.canonical_game_archive or not args.canonical_game_archive_sha256:
        fail('independent canonical Game directory or pinned archive is required')
    archive = args.canonical_game_archive
    if digest(read_file(archive)) != args.canonical_game_archive_sha256:
        fail('canonical Game archive digest changed')
    with tarfile.open(archive) as package:
        if package.pax_headers.get('comment') != GAME_REVISION:
            fail('canonical Game archive is not the exact accepted producer revision')
        members = package.getmembers()
        if len({row.name for row in members}) != len(members):
            fail('duplicate canonical archive paths')
        result = {}
        for path in CANONICAL.values():
            member = package.getmember(path)
            if not member.isfile():
                fail('canonical producer path is not a regular file')
            result[path] = package.extractfile(member).read()
    return result.__getitem__


def verify_payload(read, names, canonical):
    if set(names) != PAYLOAD:
        fail('Portal payload has missing or foreign files')
    provenance = json.loads(read('source-provenance.json'))
    if provenance['schema'] != 'fsgg.portal.example-source/1' or provenance['templateId'] != 'fs-gg-fable-game':
        fail('Portal provenance identity differs')
    if provenance['gameSource'] != {'repository':'https://github.com/FS-GG/FS.GG.Game','revision':GAME_REVISION,'tree':GAME_TREE}:
        fail('canonical producer identity differs')
    rows = provenance['canonicalFiles']
    if len(rows) != len(CANONICAL) or {row['destination']:row['producerPath'] for row in rows} != CANONICAL:
        fail('canonical source roster differs')
    for row in rows:
        content = read(row['destination'])
        if digest(content) != row['sha256'] or content != canonical(row['producerPath']):
            fail('copied source differs from independent canonical producer: '+row['destination'])
    if provenance['managedPaths'] != sorted(PAYLOAD) or provenance['packageClosure'] != CLOSURE:
        fail('managed paths or package closure differs')
    if digest(read('packages.lock.json')) != provenance['lock']['sha256'] or provenance['lock']['sha256'] != LOCK_SHA256:
        fail('genuine Portal lock digest differs')
    lock = json.loads(read('packages.lock.json'))['dependencies']['net10.0']
    if {name:row['resolved'] for name,row in lock.items()} != CLOSURE:
        fail('committed lock is not the exact seven-package closure')
    direct = {name for name,row in lock.items() if row['type']=='Direct'}
    if direct != {'FS.GG.Game.Physics.Box2D','FS.GG.Game.Render','FSharp.Core'}:
        fail('Portal direct dependency roster differs')
    helper = read_file(Path(__file__).resolve().parents[3]/'scripts/apply-svg-complete-workspace.py')
    if read('manage.py') != helper:
        fail('projected management helper differs from sole producer')
    if provenance['templateFiles'] != [{'path':'README.md','sha256':digest(read('README.md'))}, {'path':'manage.py','producerPath':'scripts/apply-svg-complete-workspace.py','sha256':digest(helper)}]:
        fail('template-authored README/helper provenance differs')


def source_files(root):
    return ['scripts/apply-svg-complete-workspace.py','FS.GG.Templates.csproj',PREFIX+'.template.config/template.json','pack/fs-gg-fable-game-legacy/.template.config/template.json','providers/fable-game.providers.yml',*[PREFIX+'PortalExample/'+name for name in PAYLOAD if name != 'manage.py'],*[PREFIX+name for name in ORDINARY]]


def verify_source(root, canonical):
    current = json.loads(read_file(root/(PREFIX+'.template.config/template.json')))
    legacy = json.loads(read_file(root/'pack/fs-gg-fable-game-legacy/.template.config/template.json'))
    option = current['symbols'].get('portalExample',{})
    if option.get('type')!='parameter' or option.get('datatype')!='bool' or option.get('defaultValue')!='false':
        fail('current Portal selection must be boolean and default false')
    modifiers = current['sources'][0]['modifiers']
    if sum(row.get('condition')=='(portalExample != true)' and row.get('exclude')==['PortalExample/**'] for row in modifiers)!=1:
        fail('Portal false/omitted exclusion differs')
    if 'portalExample' in legacy['symbols'] or 'PortalExample/**' not in legacy['sources'][0]['exclude']:
        fail('legacy must not advertise or deliver Portal')
    provider = read_file(root/'providers/fable-game.providers.yml').decode()
    if len(re.findall(r'      - key: portalExample\n        required: false\n',provider))!=1:
        fail('provider optional Portal parameter missing or duplicated')
    for name in ORDINARY:
        if b'PortalExample' in read_file(root/(PREFIX+name)):
            fail('ordinary project/solution references Portal: '+name)
    folder = root/(PREFIX+'PortalExample')
    names = [p.relative_to(folder).as_posix() for p in folder.rglob('*') if p.is_file() or p.is_symlink()]
    project = ET.fromstring(read_file(root/'FS.GG.Templates.csproj'))
    projections = [row for row in project.iter('None') if row.attrib.get('Include')=='scripts/apply-svg-complete-workspace.py' and row.attrib.get('Pack')=='true']
    expected = 'content/templates/fs-gg-fable-game/PortalExample/manage.py;content/templates/fs-gg-fable-game-legacy/PortalExample/manage.py'
    if len(projections)!=1 or projections[0].attrib.get('PackagePath')!=expected or (folder/'manage.py').exists():
        fail('management helper must have one canonical package projection, not a copied source')
    helper = read_file(root/'scripts/apply-svg-complete-workspace.py')
    for symbol in current['symbols'].values():
        token = symbol.get('replaces')
        if token and token.encode() in helper:
            fail('projected management helper contains a template replacement token')
    names.append('manage.py')
    verify_payload(lambda name:read_file(root/'scripts/apply-svg-complete-workspace.py') if name=='manage.py' else read_file(folder/name),names,canonical)


def verify_archive(path, canonical, archive_sha, templates_source):
    if not archive_sha or digest(read_file(path)) != archive_sha or not templates_source or not re.fullmatch('[0-9a-f]{40}',templates_source):
        fail('candidate archive requires exact digest and Templates source revision')
    with ZipFile(path) as package:
        names = package.namelist()
        nuspecs = [name for name in names if name.endswith('.nuspec')]
        if len(nuspecs)!=1:
            fail('candidate must contain exactly one nuspec')
        metadata = ET.fromstring(package.read(nuspecs[0]))
        repository = [row for row in metadata.iter() if row.tag.split('}')[-1]=='repository']
        if len(repository)!=1 or repository[0].attrib.get('commit')!=templates_source:
            fail('candidate nuspec does not bind exact Templates source')
        if len(set(names))!=len(names):
            fail('duplicate candidate archive paths')
        for row in package.infolist():
            if stat.S_ISLNK(row.external_attr>>16):
                fail('linked candidate archive input')
        for prefix in ['content/templates/fs-gg-fable-game/','content/templates/fs-gg-fable-game-legacy/']:
            payload = [name[len(prefix+'PortalExample/'):] for name in names if name.startswith(prefix+'PortalExample/') and not name.endswith('/')]
            verify_payload(lambda name:package.read(prefix+'PortalExample/'+name),payload,canonical)
        current = json.loads(package.read('content/templates/fs-gg-fable-game/.template.config/template.json'))
        legacy = json.loads(package.read('content/templates/fs-gg-fable-game-legacy/.template.config/template.json'))
        if current['symbols']['portalExample']['defaultValue']!='false' or 'portalExample' in legacy['symbols'] or 'PortalExample/**' not in legacy['sources'][0]['exclude']:
            fail('candidate selector/exclusion differs')


def inventory(root):
    result = {}
    for path in root.rglob('*'):
        if path.is_symlink():
            fail('linked generated input')
        if path.is_file() and not path.relative_to(root).as_posix().startswith('PortalExample/'):
            result[path.relative_to(root).as_posix()] = digest(path.read_bytes())
    return result


def verify_generated(root, enabled, canonical, peer, provider_json):
    folder = root/'PortalExample'
    if enabled:
        verify_payload(lambda name:read_file(folder/name),[p.relative_to(folder).as_posix() for p in folder.rglob('*') if p.is_file() or p.is_symlink()],canonical)
    elif folder.exists() or folder.is_symlink():
        fail('default/false/legacy generated Portal unexpectedly')
    if peer and inventory(root)!=inventory(peer):
        fail('ordinary generated paths changed outside Portal allowlist')
    if provider_json:
        report = json.loads(read_file(provider_json))
        provenance = json.loads(read_file(root/'.fsgg/scaffold-provenance.json'))
        version = tuple(int(x) for x in report['toolVersion'].split('-')[0].split('.')[:3])
        params = {row['key']:row['value'] for row in provenance['effectiveParameters']}
        if report['outcome']!='succeeded' or version<(2,1,0) or report['scaffold']['providerName']!='fable-game' or not report['scaffold']['providerInvoked']:
            fail('actual provider-v2 invocation/version missing')
        if provenance['templateRef']!='fs-gg-fable-game' or provenance['providerName']!='fable-game' or params.get('portalExample')!='true':
            fail('actual provider provenance did not forward Portal')
        if params.get('productName')!='Portal-Provider' or params.get('rootNamespace')!='PortalProvider':
            fail('distinct provider product/namespace parameters differ')
        if not read_file(root/'Server/Program.fs').decode().startswith('namespace PortalProvider.Server'):
            fail('provider namespace substitution differs')


def static_controls(root, canonical):
    results=[]
    def mutate(name,action):
        with tempfile.TemporaryDirectory(prefix='portal-source-control-') as directory:
            target=Path(directory)
            for relative in source_files(root):
                dest=target/relative;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(root/relative,dest)
            action(target)
            try:verify_source(target,canonical)
            except (ValueError,KeyError,FileNotFoundError):results.append({'name':name,'refused':True})
            else:fail('wrong-source control unexpectedly passed: '+name)
    def edit_json(target,relative,change):
        path=target/relative;value=json.loads(path.read_text());change(value);path.write_text(json.dumps(value))
    config=PREFIX+'.template.config/template.json';legacy='pack/fs-gg-fable-game-legacy/.template.config/template.json';payload=PREFIX+'PortalExample/'
    mutate('default-on',lambda t:edit_json(t,config,lambda d:d['symbols']['portalExample'].update(defaultValue='true')))
    mutate('missing-false-exclusion',lambda t:edit_json(t,config,lambda d:d['sources'][0].update(modifiers=[r for r in d['sources'][0]['modifiers'] if 'portalExample' not in r.get('condition','')])) )
    mutate('legacy-delivers-portal',lambda t:edit_json(t,legacy,lambda d:d['sources'][0]['exclude'].remove('PortalExample/**')))
    mutate('legacy-advertises-portal',lambda t:edit_json(t,legacy,lambda d:d['symbols'].update(portalExample={'type':'parameter','datatype':'bool'})))
    mutate('provider-missing-parameter',lambda t:(t/'providers/fable-game.providers.yml').write_text((t/'providers/fable-game.providers.yml').read_text().replace('      - key: portalExample\n        required: false\n','')))
    mutate('edited-canonical-program',lambda t:(t/(payload+'Program.fs')).write_text('foreign source'))
    def forged(t):
        path=t/(payload+'Program.fs');path.write_text('foreign source')
        edit_json(t,payload+'source-provenance.json',lambda d:[r.update(sha256=digest(path.read_bytes())) for r in d['canonicalFiles'] if r['destination']=='Program.fs'])
    mutate('forged-provenance-with-foreign-source',forged)
    mutate('foreign-payload',lambda t:(t/(payload+'foreign.fs')).write_text('foreign'))
    def linked(t):
        path=t/(payload+'Program.fs');path.unlink();path.symlink_to(root/(payload+'Program.fs'))
    mutate('linked-source',linked)
    mutate('edited-lock',lambda t:edit_json(t,payload+'packages.lock.json',lambda d:d['dependencies']['net10.0']['FS.GG.Game.Render'].update(resolved='0.16.0')))
    mutate('missing-helper-projection',lambda t:(t/'FS.GG.Templates.csproj').write_text((t/'FS.GG.Templates.csproj').read_text().replace('Include="scripts/apply-svg-complete-workspace.py"','Include="foreign.py"')))
    mutate('foreign-management-producer',lambda t:(t/'scripts/apply-svg-complete-workspace.py').write_text('foreign helper producer'))
    def replaceable_helper(t):
        helper=t/'scripts/apply-svg-complete-workspace.py';helper.write_bytes(helper.read_bytes()+b'\n# FableGameWorkspaceNamespace\n')
        edit_json(t,payload+'source-provenance.json',lambda d:[r.update(sha256=digest(helper.read_bytes())) for r in d['templateFiles'] if r['path']=='manage.py'])
    mutate('replaceable-management-producer',replaceable_helper)
    mutate('copied-management-source',lambda t:(t/(payload+'manage.py')).write_text('second authored copy'))
    mutate('ordinary-project-reference',lambda t:(t/(PREFIX+'Server/Server.fsproj')).write_text('PortalExample'))
    return {'kind':'synthetic-source-controls','positiveSourcePassed':True,'negativeControls':results,'actualGeneration':False,'actualRestoreBuildRuntime':False}


def main():
    if sys.flags.optimize:
        fail('Python optimization is not permitted for qualification controls')
    parser=argparse.ArgumentParser()
    parser.add_argument('--source',type=Path);parser.add_argument('--archive',type=Path);parser.add_argument('--archive-sha256');parser.add_argument('--templates-source');parser.add_argument('--generated',type=Path)
    parser.add_argument('--expected',choices=['true','false']);parser.add_argument('--peer',type=Path);parser.add_argument('--provider-json',type=Path)
    parser.add_argument('--canonical-game',type=Path);parser.add_argument('--canonical-game-archive',type=Path);parser.add_argument('--canonical-game-archive-sha256')
    parser.add_argument('--self-test',action='store_true');args=parser.parse_args();canonical=canonical_reader(args)
    if args.source:verify_source(args.source,canonical)
    if args.archive:verify_archive(args.archive,canonical,args.archive_sha256,args.templates_source)
    if args.generated:
        if args.expected is None:fail('--generated requires --expected')
        verify_generated(args.generated,args.expected=='true',canonical,args.peer,args.provider_json)
    if not any([args.source,args.archive,args.generated]):fail('select source/archive/generated evidence')
    if args.self_test:
        if not args.source:fail('--self-test requires real source')
        print(json.dumps(static_controls(args.source,canonical),indent=2))
    else:print('PASS scoped Portal payload/selection checks; generation/runtime only if separately supplied genuine inputs')


if __name__=='__main__':
    try:main()
    except (ValueError,KeyError,FileNotFoundError) as error:
        print('portal-example: '+str(error),file=sys.stderr);raise SystemExit(1)
