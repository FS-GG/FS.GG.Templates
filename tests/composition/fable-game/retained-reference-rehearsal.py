#!/usr/bin/env python3
"""Held, fixed 0.13 typed-SDD -> 0.19.3 materialization/adopted-restore rehearsal.

No command forwarding interface. Browser/Fable build and other retained cohorts
remain outside this entry. Historical installed-C/AT admissions stay unchanged.
"""
import sys
sys.dont_write_bytecode = True
import hashlib
import importlib.util
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import time
import xml.etree.ElementTree as ET

HERE = Path(__file__).resolve().parent
WORKSPACE = HERE.parents[2]
ADMISSION = None
WORKFLOW = 'FS-GG/FS.GG.Templates/.github/workflows/retained-reference-rehearsal.yml@refs/heads/main'
SDK_URL = 'https://builds.dotnet.microsoft.com/dotnet/Sdk/10.0.401/dotnet-sdk-10.0.401-linux-x64.tar.gz'
SDK_SHA512 = '51c8b999af9e8dd9998c9edc5944e19a90788862068acd38694e098889054ce8c23d4f0c5cccfa16bf187d044562359e5ee69a9f8ad0bbe913ba90311fbce25b'
INPUTS = {
    'target': ('https://api.nuget.org/v3-flatcontainer/fs.gg.workspace.template/0.19.3/fs.gg.workspace.template.0.19.3.nupkg', '9594ec204a26f238a06e016d1cfe1e796a07fda23c16589eceb19366cd4a72a2', 8*1048576),
    'baseline': ('https://api.nuget.org/v3-flatcontainer/fs.gg.workspace.template/0.13.0/fs.gg.workspace.template.0.13.0.nupkg', 'ab72f74a76d59ad4be6f11f367bbdf1b27f8bdedae7a2e3afecbe0e4b3fac10c', 8*1048576),
    'sdd': ('https://api.nuget.org/v3-flatcontainer/fs.gg.sdd.cli/2.0.2/fs.gg.sdd.cli.2.0.2.nupkg', 'a1e75e0dfcb408dfbff3e2f7e9534607b2fcd90c37c9da911c9295aed28d0fc8', 128*1048576),
    'provider': ('https://raw.githubusercontent.com/FS-GG/FS.GG.Templates/6acdfc5f5da41156db0aeaffcd54885b3b9e66be/providers/fable-game.providers.yml', 'e3f3aa1c77af9f9e559c376ffe1ad8131e205c0d68d81b4556f617b796636309', 1048576),
}
# 30-minute unit, within the workflow's 35-minute horizon including checkout/upload.
BUDGET = {'setup': 720, 'materialize': 300, 'restore': 480, 'collection': 120, 'cleanup': 90, 'overhead': 90}
UNIT = {'TasksMax': '512', 'MemoryMax': str(8*1073741824), 'RuntimeMaxUSec': '30min',
        'Delegate': 'yes', 'NoNewPrivileges': 'yes', 'KillMode': 'control-group'}
SOURCE_FILES = ('tests/composition/fable-game/retained-reference-rehearsal.py',
                '.github/workflows/retained-reference-rehearsal.yml', '.github/workflows/fable-reference-public.yml',
                'tests/composition/fable-game/wasm-installed-c.py', 'tests/composition/fable-game/verify-current-reference-adoption.py',
                'scripts/apply-svg-complete-workspace.py', 'scripts/svg-current-reference-adoption.json',
                'scripts/svg-complete-workspace-baselines.json')
FILENAMES = {'target':'fs.gg.workspace.template.0.19.3.nupkg', 'baseline':'fs.gg.workspace.template.0.13.0.nupkg',
             'sdd':'fs.gg.sdd.cli.2.0.2.nupkg', 'provider':'provider.yml'}
EVIDENCE_CAP = 128*1048576


def require(value, message):
    if not value:
        raise ValueError(message)


def sha(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1048576), b''):
            digest.update(block)
    return digest.hexdigest()


def write(path, value):
    Path(path).write_text(json.dumps(value, indent=2) + '\n')


def load_file(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def validate_admission(env, admission=None):
    # No root creation, local imports, acquisition, unit or process before this gate.
    require(admission is not None, 'retained rehearsal held: no source admission')
    require(re.fullmatch(r'https://github.com/FS-GG/\.github/issues/4816#issuecomment-[0-9]+', admission), 'wrong owning admission')
    require(env.get('ADMISSION') == admission, 'admission input differs')
    require(env.get('EVENT') == 'workflow_dispatch' and env.get('REPOSITORY') == 'FS-GG/FS.GG.Templates', 'same-repository dispatch required')
    require(env.get('REF') == 'refs/heads/main', 'main dispatch required')
    head = env.get('SHA', '')
    require(re.fullmatch(r'[0-9a-f]{40}', head) and all(env.get(key) == head for key in ('ADMITTED_REF', 'CHECKOUT_HEAD', 'WORKFLOW_SHA')), 'source/checkout/workflow commit differs')
    require(env.get('WORKFLOW_REF') == WORKFLOW and env.get('RUN_ATTEMPT') == '1', 'workflow identity or attempt differs')
    require(re.fullmatch(r'[0-9]+', env.get('RUN_ID', '')), 'run identity missing')
    require(env.get('UNIT_NAME') == 'fsgg-mg-templates-retained-' + env['RUN_ID'] + '-1', 'unit identity differs')
    return {key: env[key] for key in ('EVENT', 'REPOSITORY', 'REF', 'SHA', 'ADMITTED_REF', 'CHECKOUT_HEAD', 'WORKFLOW_REF', 'WORKFLOW_SHA', 'RUN_ID', 'RUN_ATTEMPT', 'UNIT_NAME', 'ADMISSION')}


def phase_deadline(start, phase, now):
    require(phase in ('setup', 'materialize', 'restore'), 'closed phase required')
    phases = ('setup', 'materialize', 'restore')
    cap = start + sum(BUDGET[p] for p in phases[:phases.index(phase)+1])
    deadline = min(now + BUDGET[phase], cap)
    require(deadline > now, 'original phase deadline expired')
    return deadline


def no_global_before_create(root):
    # A 400-pinned old global.json must not influence the generating SDK process.
    for path in (root, *root.parents):
        require(not (path / 'global.json').exists() and not (path / 'global.json').is_symlink(), 'global.json exists before generation: ' + str(path))


def normalized_roots(root, workspace):
    for path in (root, workspace):
        require(path.is_absolute() and os.path.normpath(str(path)) == str(path), 'normalized absolute root required')
        current = Path(path.anchor)
        for part in path.parts[1:]:
            current /= part
            require(not current.is_symlink(), 'symlink boundary refused: ' + str(current))
    require(not root.is_relative_to(workspace) and not workspace.is_relative_to(root), 'private root and checkout overlap')


def verify_sdk_selection(name, url, expected, maximum, algorithm):
    if name == 'dotnet.tar.gz':
        require((url, expected, maximum, algorithm) == (SDK_URL, SDK_SHA512, 536870912, 'sha512'), 'official SDK selection differs from source-qualified 401 tuple')
    else:
        require(name == 'dotnet-releases.json' and url == 'https://builds.dotnet.microsoft.com/dotnet/release-metadata/10.0/releases.json'
                and expected is None and maximum == 8388608 and algorithm == 'sha256', 'unexpected SDK acquisition')


def sdk_metadata(data):
    values = json.loads(data)
    require(isinstance(values, dict) and isinstance(values.get('releases'), list), 'SDK release metadata malformed')
    files = set()
    for release in values['releases']:
        require(isinstance(release, dict), 'SDK release record malformed')
        versions = release.get('sdks', [release.get('sdk', {})])
        require(isinstance(versions, list), 'SDK population malformed')
        for sdk in versions:
            require(isinstance(sdk, dict), 'SDK record malformed')
            if sdk.get('version') != '10.0.401': continue
            for file in sdk.get('files', []):
                if file.get('rid') == 'linux-x64' and file.get('name', '').endswith('.tar.gz'):
                    files.add((file.get('url'), file.get('hash')))
    require(files == {(SDK_URL, SDK_SHA512)}, 'SDK metadata selection absent, changed or ambiguous')


def zip_inputs(caller, archive, deadline):
    source = caller['bounded_zip'](archive, 20000, deadline)
    entries = source.infolist()
    require(sum(row.file_size for row in entries) <= 512*1048576 and all(row.file_size <= 128*1048576 for row in entries), 'package expanded bounds exceeded')
    names = [row.filename for row in entries]
    require(len(names) == len(set(names)) and all(not name.startswith('/') and '..' not in PurePosixPath(name).parts and '\\' not in name for name in names), 'unsafe or duplicate package member')
    return source


def package_identity(source, package, version):
    nuspec = [name for name in source.namelist() if name.endswith('.nuspec')]
    require(len(nuspec) == 1, 'exactly one package nuspec required')
    values = {element.tag.rsplit('}', 1)[-1]: element.text for element in ET.fromstring(source.read(nuspec[0])).iter()}
    require(values.get('id') == package and values.get('version') == version, 'package identity differs')


def baseline_template(source):
    names = [name for name in source.namelist() if name.endswith('/fs-gg-fable-game/.template.config/template.json')]
    require(len(names) == 1, 'historical template metadata ambiguous')
    value = json.loads(source.read(names[0]))
    require('sources' in value and 'symbols' in value and 'postActions' not in value, 'historical generation has unqualified post-actions')


def sdd_payload(source):
    settings = [name for name in source.namelist() if name.endswith('/DotnetToolSettings.xml')]
    require(len(settings) == 1, 'SDD tool declaration ambiguous')
    commands = [node for node in ET.fromstring(source.read(settings[0])).iter() if node.tag.rsplit('}', 1)[-1] == 'Command']
    require(len(commands) == 1 and commands[0].get('Name') == 'fsgg-sdd' and commands[0].get('Runner') == 'dotnet', 'SDD command differs')
    entry = str(PurePosixPath(settings[0]).parent / commands[0].get('EntryPoint', ''))
    require(entry.startswith('tools/net10.0/any/') and entry.endswith('.dll') and entry in source.namelist(), 'SDD entrypoint differs')
    runtime = str(PurePosixPath(entry).with_suffix('.runtimeconfig.json'))
    value = json.loads(source.read(runtime))['runtimeOptions']
    framework = value.get('framework')
    require(value.get('tfm') == 'net10.0' and framework == {'name': 'Microsoft.NETCore.App', 'version': '10.0.0'}
            and value.get('rollForward', 'Major') == 'Major', 'SDD runtime policy differs from qualified source')
    members = {name: hashlib.sha256(source.read(name)).hexdigest() for name in source.namelist()
               if name.startswith(('tools/', 'skills/')) and not name.endswith('/')}
    require(entry in members and runtime in members, 'SDD runtime closure missing')
    return entry, members


def installed_sdd(tool_root, entry, members):
    candidates = list(tool_root.rglob(PurePosixPath(entry).name))
    require(len(candidates) == 1, 'installed SDD entrypoint ambiguous')
    actual = candidates[0]
    package_root = actual.parents[len(PurePosixPath(entry).parts)-1]
    require(package_root.is_relative_to(tool_root), 'SDD package escapes private tool store')
    for relative, expected in members.items():
        path = package_root / relative
        normalized_roots(path, WORKSPACE)
        require(path.is_file() and sha(path) == expected, 'installed SDD member differs: ' + relative)
    return actual, {'entrypoint': str(actual), 'members': members, 'packageRoot': str(package_root)}


def generation_join(caller, source, tree, product, namespace):
    # Compare non-skill content shipped by the selected archive with actual generated
    # content, allowing only template identity replacements. Lifecycle skill/provenance
    # joins are separately read from the real SDD-produced tree below.
    prefix = 'content/templates/fs-gg-fable-game/'
    names = [name for name in source.namelist() if name.startswith(prefix) and not name.endswith('/')]
    require(names, 'package template content absent')
    count = 0
    for name in names:
        logical = name[len(prefix):]
        if logical.startswith(('.template.config/', 'PortalExample/', '.agents/', '.github/workflows/project-knowledge.yml', 'scripts/check-project-knowledge.py')) or logical in ('SvgFoundation/PreviewDocument.fs', 'SvgFoundation/PreviewFont.fs'):
            continue
        path = tree / logical.replace('FableGameWorkspace', product)
        # Complete/typed selections retain all remaining package product content.
        require(path.is_file() and not path.is_symlink(), 'generated package member missing: ' + logical)
        expected = source.read(name).replace(b'FableGameWorkspaceNamespace', namespace.encode()).replace(b'FableGameWorkspace', product.encode()).replace(b'fablegameworkspace', product.lower().encode())
        # SDD owns this hybrid manifest; the compiler-row and co-tenants are checked below.
        if logical not in ('.config/dotnet-tools.json', '.gitignore', 'AGENTS.md', 'CLAUDE.md'):
            require(path.read_bytes() == expected, 'generated package member differs: ' + logical)
        count += 1
    require((tree/'global.json').is_file() and (tree/'Domain/Room.fs').is_file(), 'generation control population absent')
    return {'archiveProductFilesChecked': count, 'globalJson': json.loads((tree/'global.json').read_text())}


def lock_hashes(root):
    return {str(path.relative_to(root)): sha(path) for path in sorted(root.rglob('packages.lock.json'))
            if not set(path.relative_to(root).parts) & {'obj', 'bin', '.nuget'}}


def collect(root, deadline):
    evidence = root/'retained-evidence'
    require(not evidence.exists(), 'evidence output occupied')
    evidence.mkdir(mode=0o700)
    names = ('rehearsal.json','source-seals.json','managed-owner.json','managed-owner-probe.json',
             'managed-receipts.json','input-downloads.json','sdk-member-identities.json',
             'sdd-member-identities.json','native-closure.json','executable-identities.json',
             'locks-before.json','locks-after.json','template-registrations.json')
    candidates = [root/name for name in names if (root/name).exists()]
    if (root/'managed').is_dir():
        groups = sorted((root/'managed').iterdir())
        require(len(groups) <= 128, 'managed evidence population exceeded')
        candidates += [group/name for group in groups for name in ('receipt.json','stdout.log','stderr.log') if (group/name).exists()]
    transaction = root/'transaction'
    if transaction.is_dir():
        candidates += [transaction/'transaction-controls.json']
        for name in ('apply','managed-conflict','new-reference-conflict','interrupted','rollback'):
            candidates += [transaction/(name+suffix) for suffix in ('.json','.diff') if (transaction/(name+suffix)).exists()]
            journal = transaction/(name+'-backup')/'journal.json'
            if journal.exists(): candidates.append(journal)
    # No recursion into adopted/.nuget/obj/bin or the copied product trees.
    manifest = {'capBytes': EVIDENCE_CAP, 'files': [], 'failures': []}
    total = 0
    for path in candidates:
        try:
            require(time.monotonic() < deadline, 'original collection deadline expired')
            normalized_roots(path, WORKSPACE)
            require(path.is_file() and not path.is_symlink(), 'nonregular evidence refused')
            size = path.stat().st_size
            require(total + size <= EVIDENCE_CAP-min(262144,EVIDENCE_CAP//8), 'evidence byte cap exceeded')
            target = evidence/path.relative_to(root)
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(path, target)
            manifest['files'].append({'path': str(path.relative_to(root)), 'bytes': size, 'sha256': sha(target)})
            total += size
        except Exception as error:
            manifest['failures'].append({'path': str(path.relative_to(root)), 'error': str(error)})
    manifest['totalBytes'] = total
    write(evidence/'manifest.json', manifest)
    return manifest


def collection_terminal(root, summary):
    evidence = root/'retained-evidence'
    terminal = {key:summary[key] for key in ('disposition','executionDisposition','firstCause','additionalFailures','phases','seconds')}
    path = evidence/'collection-terminal.json'
    write(path, terminal)
    manifest_path = evidence/'manifest.json'
    manifest = json.loads(manifest_path.read_text()) if manifest_path.is_file() else {'capBytes':EVIDENCE_CAP,'files':[],'failures':[{'error':'collection did not finish'}],'totalBytes':0}
    size = path.stat().st_size
    require(manifest['totalBytes']+size <= EVIDENCE_CAP, 'collection terminal exceeds evidence cap')
    manifest['files'].append({'path':'collection-terminal.json','bytes':size,'sha256':sha(path)})
    manifest['totalBytes'] += size
    write(manifest_path, manifest)


def template_registration(home, root, version, expected):
    registry = home/'.templateengine/packages.json'
    normalized_roots(registry, WORKSPACE)
    values = json.loads(registry.read_text(encoding='utf-8-sig'))
    rows = [row for row in values['Packages'] if row['Details'].get('PackageId') == 'FS.GG.Workspace.Template']
    require(len(rows) == 1 and rows[0]['Details'].get('Version') == version, 'selected template registration differs')
    archive = Path(rows[0]['MountPointUri'])
    normalized_roots(archive, WORKSPACE)
    require(archive.is_relative_to(root) and archive.is_file() and sha(archive) == expected, 'registered template archive differs')
    return {'home':str(home),'version':version,'registrySha256':sha(registry),'mountPoint':str(archive),'archiveSha256':expected}


def fixed_product_steps(root, dotnet, sdd_entry, inputs):
    # Values derive only from this owned root and qualified inputs, never a caller command.
    return [
        ('target-install', [dotnet, 'new', 'install', str(inputs['target']), '--force'], root),
        ('target-create', [dotnet, 'new', 'fs-gg-fable-game', '-n', 'Reference4816Current', '-o', str(root/'candidate'), '--bundle', 'complete', '--lifecycle', 'none'], root),
        ('retained-create', [dotnet, str(sdd_entry), 'scaffold', '--root', str(root/'retained'), '--provider', 'fable-game', '--no-update', '--json', '--param', 'productName=Reference4816Retained', '--param', 'rootNamespace=Reference4816Retained', '--param', 'lifecycle=typed-sdd', '--param', 'svgFoundation=true'], root),
    ]


def unit_properties(caller, run, env, identities):
    path, _ = caller['host_image']('/usr/bin/systemctl')
    caller['bind_identity'](identities, path, 'host-observed')
    names = [*UNIT, 'CPUQuotaPerSecUSec']
    text = run([path, 'show', '--no-pager', env['UNIT_NAME']] + [item for name in names for item in ('-p', name)], Path(env['PRIVATE_ROOT']), env)
    values = dict(line.split('=', 1) for line in text.splitlines() if '=' in line)
    require(all(values.get(key) == value for key, value in UNIT.items()), 'unit properties differ')
    quota = re.fullmatch(r'([0-9]+(?:\.[0-9]+)?)(us|ms|s)', values.get('CPUQuotaPerSecUSec', ''))
    require(quota and float(quota[1])*{'us':1,'ms':1000,'s':1000000}[quota[2]] == 2000000, 'CPU quota differs')
    return values


def native_closure(caller, run, root, tools, env, identities):
    # Verified SDK archive supplies these members; native host dependencies are
    # observed on this runner, not promoted to publisher/source correspondence.
    targets = [tools/'dotnet/dotnet', tools/'dotnet/host/fxr/10.0.12/libhostfxr.so']
    targets += [tools/'dotnet/shared/Microsoft.NETCore.App/10.0.12'/name
                for name in ('libhostpolicy.so', 'libcoreclr.so',
                             'libSystem.Globalization.Native.so', 'libSystem.Security.Cryptography.Native.OpenSsl.so')]
    ldd, _ = caller['host_image']('/usr/bin/ldd')
    shebang = Path(ldd).read_text().splitlines()[0]
    require(shebang.startswith('#!') and len(shebang[2:].split()) == 1, 'host ldd interpreter ambiguous')
    interpreter, digest = caller['host_image'](shebang[2:])
    caller['bind_identity'](identities, ldd, 'host-observed', images=[digest])
    result = {'scope':'declared SDK native members and observed ldd dependencies; not every runtime dlopen',
              'sdkArchiveSha512':SDK_SHA512, 'members':{}, 'hostLibraries':{}}
    for target in targets:
        normalized_roots(target, WORKSPACE)
        require(target.is_file(), 'declared SDK native member missing')
        result['members'][str(target.relative_to(root))] = sha(target)
        output = run([ldd, str(target)], root, env)
        paths = []
        for line in output.splitlines():
            line = line.strip()
            if not line or line.startswith('linux-vdso.'):
                continue
            require('not found' not in line, 'SDK native dependency missing')
            match = re.fullmatch(r'(?:[^ ]+ => )?(/[^ ]+) \(0x[0-9a-f]+\)', line)
            require(match, 'unrecognized SDK native dependency output: '+line)
            paths.append(match[1])
        require(paths, 'native dependency census absent')
        for path in paths:
            actual, digest = caller['host_image'](path)
            result['hostLibraries'][actual] = digest
    write(root/'native-closure.json', result)
    return result


def run_rehearsal(environ, start):
    source = validate_admission(environ, ADMISSION)
    root = Path(environ['RUNNER_TEMP'])/('retained-reference-'+environ['RUN_ID']+'-1')
    workspace = Path(environ['GITHUB_WORKSPACE'])
    normalized_roots(root, workspace)
    require(workspace == WORKSPACE, 'executing checkout path differs')
    require(shutil.disk_usage(root.parent).free >= 20*1073741824, 'private staging needs 20GiB available')
    no_global_before_create(root)
    caller = load_file('retained_caller_loader', HERE/'wasm-installed-c.py').actual_caller()
    env = caller['fresh_environment'](root, environ)
    env.update(UNIT_NAME=environ['UNIT_NAME'], PRIVATE_ROOT=str(root), GIT_CONFIG_NOSYSTEM='1')
    summary = {'schema': 'fsgg.templates.retained-reference-rehearsal/1', 'disposition': 'failed', 'source': source,
               'scope': 'one genuine 0.13 typed-SDD to 0.19.3 Complete materialization/adoption/locked-restore; no builds/browser', 'budget': BUDGET,
               'phases': {}, 'firstCause': None, 'additionalFailures': [], 'membersQualified': False, 'executionDisposition': 'started'}
    receipts = []
    try:
        write(root/'source-seals.json', {name: sha(workspace/name) for name in SOURCE_FILES})
        write(root/'rehearsal.json', summary)
        setup = phase_deadline(start, 'setup', time.monotonic())
        owner = caller['load_owner'](root, setup)
        summary['probe'] = caller['probe_containment'](owner, root)
        identities = {}
        run = caller['managed_executor'](owner, root, setup, identities, 'setup', receipts)
        summary['unit'] = unit_properties(caller, run, env, identities)
        tools = root/'tools'; tools.mkdir(mode=0o700)
        downloads = root/'downloads'; downloads.mkdir(mode=0o700)
        acquisitions = []
        get = caller['acquirer'](root, downloads, caller['download'], setup, acquisitions)
        def sdk_get(name, url, expected, maximum, algorithm='sha256'):
            verify_sdk_selection(name, url, expected, maximum, algorithm)
            path = get(name, url, expected, maximum, algorithm)
            if name == 'dotnet-releases.json': sdk_metadata(path.read_bytes())
            return path
        dotnet = str(caller['provision_sdk'](sdk_get, tools, setup))
        env.update(DOTNET_ROOT=str(tools/'dotnet'), DOTNET_HOST_PATH=dotnet, PATH=str(tools/'dotnet')+':/usr/bin:/bin')
        caller['bind_identity'](identities, dotnet, 'verified-archive-member')
        git, _ = caller['host_image']('/usr/bin/git')
        caller['bind_identity'](identities, git, 'host-observed')
        summary['nativeClosure'] = native_closure(caller, run, root, tools, env, identities)
        require(run([dotnet, '--version'], root, env).strip() == '10.0.401', 'actual SDK differs')
        summary['sdkInfo'] = run([dotnet, '--info'], root, env)
        require('Microsoft.NETCore.App 10.0.12 [' in run([dotnet, '--list-runtimes'], root, env), 'actual runtime absent')
        sdk_members = [tools/'dotnet/dotnet', tools/'dotnet/host/fxr/10.0.12/libhostfxr.so']
        sdk_members += [tools/'dotnet/shared/Microsoft.NETCore.App/10.0.12'/name for name in ('libhostpolicy.so','libcoreclr.so')]
        write(root/'sdk-member-identities.json', {str(path.relative_to(root)): sha(path) for path in sdk_members})
        inputs = {name: get(FILENAMES[name], *row) for name, row in INPUTS.items()}
        with zip_inputs(caller, inputs['target'], setup) as package:
            package_identity(package, 'FS.GG.Workspace.Template', '0.19.3')
        with zip_inputs(caller, inputs['baseline'], setup) as package:
            package_identity(package, 'FS.GG.Workspace.Template', '0.13.0'); baseline_template(package)
        with zip_inputs(caller, inputs['sdd'], setup) as package:
            package_identity(package, 'FS.GG.SDD.Cli', '2.0.2'); entry, members = sdd_payload(package)
        config = caller['closed_nuget_config'](root)
        run([dotnet, 'tool', 'install', 'FS.GG.SDD.Cli', '--version', '2.0.2', '--tool-path', str(tools/'sdd'), '--configfile', str(config), '--add-source', str(downloads), '--no-cache'], root, env)
        sdd_entry, closure = installed_sdd(tools/'sdd', entry, members)
        write(root/'sdd-member-identities.json', closure)
        require(run([dotnet, str(sdd_entry), '--version'], root, env, inputs=[sdd_entry]).strip() == '2.0.2', 'actual SDD version differs')
        summary['membersQualified'] = True
        write(root/'executable-identities.json', identities)
        summary['phases']['setupFinished'] = time.monotonic()-start
        write(root/'rehearsal.json', summary)
        materialize = phase_deadline(start, 'materialize', time.monotonic())
        run = caller['managed_executor'](owner, root, materialize, identities, 'installed', receipts)
        (root/'retained/.fsgg').mkdir(parents=True)
        provider = inputs['provider'].read_text()
        provider, count = re.subn(r'source:\s*FS\.GG\.Workspace\.Template::0\.13\.0', 'source: '+str(inputs['baseline']), provider)
        require(count == 1, 'historical provider source replacement ambiguous')
        (root/'retained/.fsgg/providers.yml').write_text(provider)
        homes = {}
        for name in ('target','retained'):
            home = root/(name+'-home'); require(not home.exists(), 'template home occupied'); home.mkdir(mode=0o700)
            homes[name] = {**env,'DOTNET_CLI_HOME':str(home)}
        registrations = {}
        for name, argv, cwd in fixed_product_steps(root, dotnet, sdd_entry, inputs):
            no_global_before_create(root if name != 'retained-create' else root/'retained')
            cohort = 'retained' if name == 'retained-create' else 'target'
            run(argv, cwd, homes[cohort], inputs=([sdd_entry] if name == 'retained-create' else []))
            registrations[name] = template_registration(Path(homes[cohort]['DOTNET_CLI_HOME']),root,
                '0.13.0' if cohort == 'retained' else '0.19.3', INPUTS['baseline' if cohort == 'retained' else 'target'][1])
            write(root/'template-registrations.json', registrations)
            summary['phases'][name] = time.monotonic()-start
            write(root/'rehearsal.json', summary)
        with zip_inputs(caller, inputs['target'], materialize) as package:
            summary['targetGeneration'] = generation_join(caller, package, root/'candidate', 'Reference4816Current', 'Reference4816Current')
        with zip_inputs(caller, inputs['baseline'], materialize) as package:
            summary['retainedGeneration'] = generation_join(caller, package, root/'retained', 'Reference4816Retained', 'Reference4816Retained')
        provenance = json.loads((root/'retained/.fsgg/scaffold-provenance.json').read_text())
        require(any(row.get('key') == 'lifecycle' and row.get('value') == 'typed-sdd' for row in provenance.get('effectiveParameters', [])), 'real typed-SDD provenance absent')
        original_tools = json.loads((root/'retained/.config/dotnet-tools.json').read_text())
        for name, version in [('fable','5.13.0'),('fs.gg.sdd.cli','2.0.2'),('fs.gg.coord.cli','0.90.0')]:
            require(original_tools['tools'][name]['version'] == version, 'historical co-tenant identity differs')
        for relative, content in {'authored/save.json':'{"save":"owner"}\n','authored/replay.json':'{"replay":"owner"}\n','authored/extension.fs':'module OwnerExtension\n','authored/config.json':'{"config":"owner"}\n','.agents/skills/local-owner/SKILL.md':'# Owner skill\n'}.items():
            path = root/'retained'/relative; require(not path.exists(), 'owner sentinel collides'); path.parent.mkdir(parents=True, exist_ok=True); path.write_text(content)
        python, _ = caller['host_image'](sys.executable)
        caller['bind_identity'](identities, python, 'host-observed')
        helper = workspace/'tests/composition/fable-game/verify-current-reference-adoption.py'
        run([python, '-I', '-B', str(helper), '--candidate', str(root/'candidate'), '--receiver', str(root/'retained'), '--baseline-version', '0.13.0', '--baseline-archive', str(inputs['baseline']), '--target-archive', str(inputs['target']), '--output', str(root/'transaction')], root, env, inputs=[workspace/name for name in SOURCE_FILES if name.endswith(('.py','.json'))])
        adopted = root/'transaction/adopted'
        require(json.loads((adopted/'global.json').read_text())['sdk'] == {'version':'10.0.401','rollForward':'disable'}, 'adopted SDK pin differs')
        changed_tools = json.loads((adopted/'.config/dotnet-tools.json').read_text())
        require(changed_tools['tools']['fable'] == {'version':'5.18.0','commands':['fable']}, 'adopted compiler row differs')
        require(all(changed_tools['tools'].get(key) == value for key,value in original_tools['tools'].items() if key != 'fable'), 'co-tenant rows changed')
        summary['phases']['materializeFinished'] = time.monotonic()-start
        write(root/'rehearsal.json', summary)
        restore = phase_deadline(start, 'restore', time.monotonic())
        run = caller['managed_executor'](owner, root, restore, identities, 'installed', receipts)
        before = lock_hashes(adopted); require('Domain/packages.lock.json' in before and before, 'lock census missing known control')
        write(root/'locks-before.json', before)
        restore_failure = None
        try:
            run([dotnet, 'restore', 'Reference4816Retained.slnx', '--locked-mode', '--configfile', str(config), '-m:1', '-nodeReuse:false', '-p:UseSharedCompilation=false', '-p:BuildInParallel=false'], adopted, env)
        except BaseException as error:
            restore_failure = error
            raise
        finally:
            try:
                after = lock_hashes(adopted); write(root/'locks-after.json', after)
            except BaseException as reporting:
                if restore_failure is None: raise
                summary['additionalFailures'].append('restore lock readback: '+str(reporting))
                print(summary['additionalFailures'][-1], file=sys.stderr)
        require(after == before, 'locked restore changed declared lock population or bytes')
        summary['disposition'] = 'passed'
        summary['executionDisposition'] = 'passed'
        summary['phases']['restoreFinished'] = time.monotonic()-start
    except BaseException as error:
        summary['firstCause'] = type(error).__name__+': '+str(error)
        summary['executionDisposition'] = 'failed'
        print('retained rehearsal firstCause: '+summary['firstCause'], file=sys.stderr)
        raise
    finally:
        summary['seconds'] = time.monotonic()-start
        try:
            write(root/'rehearsal.json', summary)
            evidence = collect(root, min(time.monotonic()+BUDGET['collection'], start+sum(BUDGET.values())-BUDGET['overhead']))
            if evidence['failures']:
                raise RuntimeError('evidence collection incomplete: '+str(evidence['failures']))
        except BaseException as error:
            summary['additionalFailures'].append('collection: '+type(error).__name__+': '+str(error))
            summary['disposition'] = 'failed'
            print(summary['additionalFailures'][-1], file=sys.stderr)
            try:
                write(root/'rehearsal.json', summary)
                if (root/'retained-evidence').is_dir(): collection_terminal(root, summary)
            except BaseException as reporting: print('additional summary reporting failure: '+str(reporting), file=sys.stderr)
            if summary['firstCause'] is None:
                raise
    return summary


def main():
    require(sys.argv[1:] in ([], ['--check-admission']), 'usage: retained-reference-rehearsal.py [--check-admission]')
    validate_admission(os.environ, ADMISSION)
    if sys.argv[1:]:
        print('retained rehearsal admission bound')
        return 0
    summary = run_rehearsal(os.environ, time.monotonic())
    print(json.dumps({'disposition':summary['disposition'], 'scope':summary['scope']}))
    return 0 if summary['disposition'] == 'passed' else 1


if __name__ == '__main__':
    sys.exit(main())
