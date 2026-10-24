#!/usr/bin/env python3
"""Held retained-upgrade build/Fable/browser original (FS-GG/.github#4816, cases H-K).

One fixed operation for the four promised public cohorts 0.10.0, 0.11.0, 0.12.0 and 0.13.0
(typed-sdd) -> published Workspace.Template 0.19.3 Complete reference. For every cohort it
repeats the already accepted generation join, owner-sentinel preservation, five transaction
controls and locked restore, then runs the adopted tree's own shipped `build.sh` through the
managed executor: locked solution build and product tests, the Fable/Vite production build,
cross-runtime and model checks, and the Chromium browser suite. Tool identities (Node, npm,
Quint 0.32.0, pinned Chromium headless shell) are hash-pinned; the stock Playwright download
is never used. It reuses the shared retained reader contract 'adopted-build'. Dispatch is held
until Root's conditional selection on #4816 is bound here and the workflow carries its
admission gates; this file grants no operation.
"""
import hashlib
import importlib.util
import json
import os
import re
import stat
import sys
import time
import zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
ADMISSION = 'https://github.com/FS-GG/.github/issues/4816#issuecomment-6389185539'
VERSIONS = ('0.10.0', '0.11.0', '0.12.0', '0.13.0')
QUINT = {'url': 'https://github.com/quint-co/quint/releases/download/v0.32.0/quint-linux-amd64',
         'sha256': '939b64095b706017f2f202c6f99c860c40be7c31bddc2b98557316e50f42cd7f', 'maximum': 134217728}
CHROMIUM = {'asset': 'chromium-headless1243', 'selector': 'chrome-headless-shell-linux64/chrome-headless-shell'}
# Cumulative original phases; the sum (6860 s) stays inside the 7200 s unit.
PHASES = (('setup', 900), ('target', 60)) + tuple(
    (version + '-' + phase, seconds) for version in VERSIONS
    for phase, seconds in (('generate', 60), ('transaction', 100), ('restore', 300), ('build', 940))) + (
    ('collection', 120), ('cleanup', 90), ('overhead', 90))
UNIT_BUILD = {'TasksMax': '1024', 'RuntimeMaxUSec': '2h'}
# build.sh runs dotnet build/test/publish/fable/vite/playwright; no daemon may outlive its managed group
# (MSBuild node reuse and the compiler servers otherwise linger ~15 minutes and break require-empty retirement).
BUILD_DAEMON_OFF = {'MSBUILDDISABLENODEREUSE': '1', 'DOTNET_CLI_USE_MSBUILD_SERVER': '0', 'UseSharedCompilation': 'false',
                    'DOTNET_CLI_TELEMETRY_OPTOUT': '1', 'DOTNET_NOLOGO': '1'}
SENTINELS_EARLIER = {'authored/save.json': '{"save":"owner"}\n', 'authored/replay.json': '{"replay":"owner"}\n',
                     'authored/config.json': '{"config":"owner"}\n', 'authored/extension.fs': 'module OwnerExtension\n',
                     '.agents/skills/local-owner/SKILL.md': '# Owner skill\n', '.fsgg/local-owner.json': '{"owner":"retained"}\n'}
SENTINELS_RETAINED_13 = {'authored/save.json': '{"save":"owner"}\n', 'authored/replay.json': '{"replay":"owner"}\n',
                         'authored/extension.fs': 'module OwnerExtension\n', 'authored/config.json': '{"config":"owner"}\n',
                         '.agents/skills/local-owner/SKILL.md': '# Owner skill\n'}


def load_reader():
    spec = importlib.util.spec_from_file_location('retained_reference_rehearsal', HERE/'retained-reference-rehearsal.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def deadline(m, start, phase, now):
    names = [name for name, _ in PHASES]
    m.require(phase in names and 0 <= start <= now, 'adopted-build phase/clock differs')
    index = names.index(phase)
    cap = start + sum(seconds for _, seconds in PHASES[:index+1])
    until = min(now + PHASES[index][1], cap)
    m.require(until > now, 'adopted-build original phase expired')
    return until


def product_name(version):
    return 'Reference4816Retained' if version == '0.13.0' else 'Earlier4816V' + version.replace('.', '')


def extract_chromium(m, caller, archive, destination, budget):
    """Safe extraction of the hash-pinned headless shell; population and logical size are checked."""
    layout = caller['BROWSER_LAYOUTS'][CHROMIUM['asset']]
    destination.mkdir(mode=0o700)
    total = 0
    with zipfile.ZipFile(archive) as package:
        entries = package.infolist()
        m.require(len(entries) == layout['members'], 'browser archive population differs')
        for entry in entries:
            m.require(time.monotonic() < budget, 'browser extraction deadline expired')
            parts = Path(entry.filename).parts
            m.require(entry.filename and not Path(entry.filename).is_absolute() and '..' not in parts, 'browser archive path refused')
            mode = (entry.external_attr >> 16) & 0o170000
            m.require(mode in (0, stat.S_IFREG, stat.S_IFDIR), 'browser archive special member refused')
            target = destination/entry.filename
            if entry.is_dir():
                target.mkdir(parents=True, exist_ok=True)
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            data = package.read(entry)
            m.require(len(data) == entry.file_size, 'browser member size differs')
            target.write_bytes(data)
            target.chmod((entry.external_attr >> 16) & 0o755 or 0o644)
            total += len(data)
    m.require(total == layout['logicalBytes'], 'browser archive logical size differs')
    executable = destination/CHROMIUM['selector']
    m.require(executable.is_file() and os.access(executable, os.X_OK), 'browser executable missing')
    return executable


def parse_build_output(m, text):
    """Closed readback of build.sh output; no count is trusted without its line."""
    unit = [(int(a), int(b)) for a, b in re.findall(r'Failed:\s+(\d+), Passed:\s+(\d+), Skipped:\s+\d+', text)]
    m.require(unit and all(failed == 0 for failed, _ in unit), 'product test failure or absent totals')
    browser = re.findall(r'^\s*(\d+) passed \(', text, re.M)
    skipped = re.findall(r'^\s*(\d+) skipped\s*$', text, re.M)
    m.require(len(browser) == 1 and int(browser[0]) > 0, 'browser pass count missing')
    m.require(not re.search(r'^\s*\d+ (failed|flaky|did not run|interrupted)', text, re.M), 'browser failure line present')
    m.require('release prepared:' in text, 'release preparation line missing')
    return {'productTestPassed': [passed for _, passed in unit], 'browserPassed': int(browser[0]),
            'browserSkipped': int(skipped[0]) if skipped else 0}


def run_adopted_build(environ):
    m = load_reader()
    contract = m.caller_contract('adopted-build', ADMISSION)
    source = m.validate_admission(environ, ADMISSION, contract)
    workspace = Path(environ['GITHUB_WORKSPACE'])
    m.require(workspace == m.WORKSPACE, 'adopted-build checkout differs')
    root = Path(environ['RUNNER_TEMP'])/('retained-adopted-build-'+environ['RUN_ID']+'-1')
    m.normalized_roots(root, workspace)
    m.no_global_before_create(root)
    initial = m.operational_start(environ, contract)
    start = m.original_clock(environ, initial['boot'], contract)['startedMonotonic']
    receipts, identities, inputs, homes, registrations, acquisitions, provenance = [], {}, {}, {}, {}, [], {}
    summary = {'schema': 'fsgg.retained-adopted-build/1', 'source': source, 'disposition': 'failed',
               'executionDisposition': 'started', 'firstCause': None, 'additionalFailures': [], 'phases': {}, 'cohorts': {},
               'scope': 'fixed genuine 0.10/0.11/0.12/0.13 -> published 0.19.3 materialization, transactions, locked restores and the adopted tree\'s own build.sh (solution build/tests, Fable/Vite, Chromium)',
               'inputDownloads': acquisitions, 'publicInputs': provenance, 'executableIdentities': identities, 'templateRegistrations': registrations}
    primary = None
    try:
        caller = m.load_file('adopted_actual_caller', HERE/'wasm-installed-c.py').actual_caller()
        env = caller['fresh_environment'](root, environ)
        env.update(UNIT_NAME=environ['UNIT_NAME'], PRIVATE_ROOT=str(root), GIT_CONFIG_NOSYSTEM='1')
        m.write(root/'source-seals.json', {name: m.sha(workspace/name) for name in (
            *m.SOURCE_FILES, 'tests/composition/fable-game/d5-managed-runtime.py', 'tests/composition/fable-game/retained-adopted-build.py')})
        setup = deadline(m, start, 'setup', time.monotonic())
        owner = caller['load_owner'](root, setup)
        caller['probe_containment'](owner, root)

        def executor(until):
            return caller['managed_executor'](owner, root, until, identities, 'installed', receipts)
        run = executor(setup)
        m.unit_properties(caller, run, env, identities, initial, {**m.UNIT, **UNIT_BUILD})
        m.acquisition_capacity(owner, root, initial)
        m.earlier_sandbox_prerequisite(caller, run, identities, root, summary)
        tools = root/'tools'; tools.mkdir()
        downloads = root/'downloads'; downloads.mkdir()
        get = caller['acquirer'](root, downloads, caller['download'], setup, acquisitions)

        def sdk_get(name, url, expected, maximum, algorithm='sha256'):
            m.verify_sdk_selection(name, url, expected, maximum, algorithm)
            path = get(name, url, expected, maximum, algorithm)
            if name == 'dotnet-releases.json':
                m.sdk_metadata(path.read_bytes())
            return path
        dotnet = str(caller['provision_sdk'](sdk_get, tools, setup))
        env.update(DOTNET_ROOT=str(tools/'dotnet'), DOTNET_HOST_PATH=dotnet, PATH=str(tools/'dotnet')+':/usr/bin:/bin')
        caller['bind_identity'](identities, dotnet, 'verified-archive-member')
        m.native_closure(caller, run, root, tools, env, identities)
        m.require(run([dotnet, '--version'], root, env).strip() == '10.0.401', 'adopted-build SDK differs')
        summary['sdkInfo'] = run([dotnet, '--info'], root, env)
        m.require('Microsoft.NETCore.App 10.0.12 [' in run([dotnet, '--list-runtimes'], root, env), 'adopted-build runtime absent')
        members = [tools/'dotnet/dotnet', tools/'dotnet/host/fxr/10.0.12/libhostfxr.so'] + [
            tools/'dotnet/shared/Microsoft.NETCore.App/10.0.12'/name for name in ('libhostpolicy.so', 'libcoreclr.so')]
        m.write(root/'sdk-member-identities.json', {str(path.relative_to(root)): m.sha(path) for path in members})
        # Pinned build tools: Node/npm from the reviewed hosted caller, Quint 0.32.0, Chromium headless shell.
        node_root, bin_root = caller['provision_node_npm'](get, tools, setup)
        (bin_root/'npx').write_text('#!/bin/sh\nexec "'+str(node_root/'bin/node')+'" "'+str(tools/'npm/package/bin/npx-cli.js')+'" "$@"\n')
        (bin_root/'npx').chmod(0o700)
        _, shell_sha = caller['host_image']('/bin/sh')
        node = caller['bind_identity'](identities, os.path.realpath(node_root/'bin/node'), 'verified-archive-member')
        for wrapper in ('npm', 'npx'):
            caller['bind_identity'](identities, str(bin_root/wrapper), 'caller-authored', images=[shell_sha, node['sha256']])
        quint = get('quint', QUINT['url'], QUINT['sha256'], QUINT['maximum']); quint.chmod(0o700)
        caller['bind_identity'](identities, str(quint), 'verified-download', expected=QUINT['sha256'])
        spec = caller['BROWSER_ARCHIVES'][CHROMIUM['asset']]
        archive = get('chrome-headless-shell.zip', spec['url'], spec['sha256'], spec['bytes'])
        chromium = extract_chromium(m, caller, archive, tools/'chromium', setup)
        caller['bind_identity'](identities, str(chromium), 'verified-archive-member')
        bash, _ = caller['host_image']('/usr/bin/bash')
        caller['bind_identity'](identities, bash, 'host-observed')
        build_path = ':'.join([str(bin_root), str(node_root/'bin'), str(tools/'dotnet'), '/usr/bin', '/bin'])
        versions = {'node': run([str(node_root/'bin/node'), '--version'], root, env).strip(),
                    'npm': run([str(bin_root/'npm'), '--version'], root, env, inputs=[]).strip(),
                    'quint': run([str(quint), '--version'], root, env).strip(),
                    'chromium': run([str(chromium), '--version'], root, env).strip()}
        m.require(versions['quint'] == '0.32.0', 'Quint must be exactly 0.32.0')
        m.write(root/'build-identities.json', {'versions': versions, 'chromiumArchiveSha256': spec['sha256'],
                                               'quintSha256': QUINT['sha256'], 'nodeSha256': node['sha256'],
                                               'chromiumExecutableSha256': m.sha(chromium)})
        # Public inputs for all cohorts, joined before the first generation.
        rows = m.earlier_inputs(workspace)
        inputs['target'] = get(m.FILENAMES['target'], *m.INPUTS['target'])
        with m.zip_inputs(caller, inputs['target'], setup) as package:
            m.package_identity(package, 'FS.GG.Workspace.Template', '0.19.3'); m.baseline_template(package)
        for version in ('0.10.0', '0.11.0', '0.12.0'):
            inputs[version] = get('fs.gg.workspace.template.'+version+'.nupkg', *rows[version])
            with m.zip_inputs(caller, inputs[version], setup) as package:
                provenance[version] = m.earlier_metadata(package, version)
        inputs['0.13.0'] = get(m.FILENAMES['baseline'], *m.INPUTS['baseline'])
        inputs['sdd'] = get(m.FILENAMES['sdd'], *m.INPUTS['sdd'])
        inputs['provider'] = get(m.FILENAMES['provider'], *m.INPUTS['provider'])
        with m.zip_inputs(caller, inputs['0.13.0'], setup) as package:
            m.package_identity(package, 'FS.GG.Workspace.Template', '0.13.0'); m.baseline_template(package)
        with m.zip_inputs(caller, inputs['sdd'], setup) as package:
            m.package_identity(package, 'FS.GG.SDD.Cli', '2.0.2'); entry, sdd_members = m.sdd_payload(package)
        config = caller['closed_nuget_config'](root)
        run([dotnet, 'tool', 'install', 'FS.GG.SDD.Cli', '--version', '2.0.2', '--tool-path', str(tools/'sdd'), '--configfile', str(config), '--add-source', str(downloads), '--no-cache'], root, env)
        sdd_entry, closure = m.installed_sdd(tools/'sdd', entry, sdd_members)
        m.write(root/'sdd-member-identities.json', closure)
        m.require(run([dotnet, str(sdd_entry), '--version'], root, env, inputs=[sdd_entry]).strip() == '2.0.2', 'adopted-build SDD version differs')
        m.write(root/'earlier-input-provenance.json', provenance); m.write(root/'input-downloads.json', acquisitions)
        m.write(root/'executable-identities.json', identities)
        for version in ('target', *VERSIONS):
            home = root/('template-home-'+version)
            m.require(not home.exists(), 'adopted-build template home occupied'); home.mkdir(mode=0o700)
            homes[version] = {**env, 'DOTNET_CLI_HOME': str(home)}
        summary['phases']['setup'] = 'passed'
        # Target candidate, once.
        target_until = deadline(m, start, 'target', time.monotonic()); run = executor(target_until)
        for argv, cwd in m.earlier_steps(root, dotnet, inputs):
            m.no_global_before_create(root); run(argv, cwd, homes['target'])
        registrations['target'] = m.template_registration(Path(homes['target']['DOTNET_CLI_HOME']), root, '0.19.3', m.INPUTS['target'][1])
        with m.zip_inputs(caller, inputs['target'], target_until) as package:
            summary['targetGeneration'] = m.generation_join(caller, package, root/'candidate', 'Reference4816EarlierCurrent', 'Reference4816EarlierCurrent')
        python, _ = caller['host_image'](sys.executable)
        caller['bind_identity'](identities, python, 'host-observed')
        helper = workspace/'tests/composition/fable-game/verify-current-reference-adoption.py'
        helper_inputs = [workspace/name for name in m.SOURCE_FILES if name.endswith(('.py', '.json'))]
        for version in VERSIONS:
            product = product_name(version); receiver = root/'receivers'/version; transaction = root/'transactions'/version
            case = {'disposition': 'started'}; summary['cohorts'][version] = case
            generate_until = deadline(m, start, version+'-generate', time.monotonic()); run = executor(generate_until)
            if version == '0.13.0':
                (receiver/'.fsgg').mkdir(parents=True)
                provider, count = re.subn(r'source:\s*FS\.GG\.Workspace\.Template::0\.13\.0', 'source: '+str(inputs[version]), inputs['provider'].read_text())
                m.require(count == 1, 'historical provider source replacement ambiguous')
                (receiver/'.fsgg/providers.yml').write_text(provider)
                m.no_global_before_create(receiver)
                run([dotnet, str(sdd_entry), 'scaffold', '--root', str(receiver), '--provider', 'fable-game', '--no-update', '--json',
                     '--param', 'productName='+product, '--param', 'rootNamespace='+product, '--param', 'lifecycle=typed-sdd',
                     '--param', 'svgFoundation=true'], root, homes[version], inputs=[sdd_entry])
                case['generationFlags'] = ['typed-sdd', 'svgFoundation=true']
            else:
                case['generationFlags'] = ['--lifecycle', 'none'] + ([] if version == '0.10.0' else ['--svgFoundation', 'true'])
                for argv, cwd in m.earlier_steps(root, dotnet, inputs, version):
                    m.no_global_before_create(root); run(argv, cwd, homes[version])
            registrations[version] = m.template_registration(Path(homes[version]['DOTNET_CLI_HOME']), root, version,
                                                             m.INPUTS['baseline'][1] if version == '0.13.0' else rows[version][1])
            m.write(root/'template-registrations.json', registrations)
            with m.zip_inputs(caller, inputs[version], generate_until) as package:
                case['generationJoin'] = m.generation_join(caller, package, receiver, product, product)
            original_tools = json.loads((receiver/'.config/dotnet-tools.json').read_text())
            if version == '0.13.0':
                lifecycle = json.loads((receiver/'.fsgg/scaffold-provenance.json').read_text())
                m.require(any(row.get('key') == 'lifecycle' and row.get('value') == 'typed-sdd' for row in lifecycle.get('effectiveParameters', [])), 'real typed-SDD provenance absent')
                for name, expected in [('fable', '5.13.0'), ('fs.gg.sdd.cli', '2.0.2'), ('fs.gg.coord.cli', '0.90.0')]:
                    m.require(original_tools['tools'][name]['version'] == expected, 'historical co-tenant identity differs')
            else:
                m.require(original_tools['tools']['fable'] == {'version': '5.13.0', 'commands': ['fable']}, 'earlier compiler row differs')
            for relative, content in (SENTINELS_RETAINED_13 if version == '0.13.0' else SENTINELS_EARLIER).items():
                path = receiver/relative
                m.require(not path.exists(), 'adopted-build owner sentinel collision')
                path.parent.mkdir(parents=True, exist_ok=True); path.write_text(content); path.chmod(0o600)
            run = executor(deadline(m, start, version+'-transaction', time.monotonic()))
            run([python, '-I', '-B', str(helper), '--candidate', str(root/'candidate'), '--receiver', str(receiver), '--baseline-version', version,
                 '--baseline-archive', str(inputs[version]), '--target-archive', str(inputs['target']), '--output', str(transaction)], root, env, inputs=helper_inputs)
            adopted = transaction/'adopted'
            m.require(json.loads((adopted/'global.json').read_text())['sdk'] == {'version': '10.0.401', 'rollForward': 'disable'}, 'adopted SDK differs')
            changed = json.loads((adopted/'.config/dotnet-tools.json').read_text())
            m.require(changed['tools']['fable'] == {'version': '5.18.0', 'commands': ['fable']}, 'adopted compiler differs')
            m.require(all(changed['tools'].get(key) == value for key, value in original_tools['tools'].items() if key != 'fable'), 'adopted co-tenant changed')
            case['transactions'] = json.loads((transaction/'transaction-controls.json').read_text())['controls']
            before = m.lock_hashes(adopted); m.require('Domain/packages.lock.json' in before, 'adopted declared lock census absent')
            m.write(root/('locks-'+version+'-before.json'), before)
            run = executor(deadline(m, start, version+'-restore', time.monotonic())); restore_failure = None
            try:
                run([dotnet, 'restore', product+'.slnx', '--locked-mode', '--configfile', str(config), '-m:1', '-nodeReuse:false',
                     '-p:UseSharedCompilation=false', '-p:BuildInParallel=false'], adopted, homes[version])
            except BaseException as error:
                restore_failure = error; raise
            finally:
                try:
                    after = m.lock_hashes(adopted); m.write(root/('locks-'+version+'-after.json'), after)
                except BaseException as error:
                    if restore_failure is None:
                        raise
                    restore_failure.add_note(('adopted lock readback: '+str(error))[:8192])
            m.require(before == after, 'adopted locked restore changed reviewed locks')
            case['lockedRestore'] = 'passed'
            # Cases H-K: the adopted tree's own shipped build, run once per cohort in its own managed group.
            build_until = deadline(m, start, version+'-build', time.monotonic()); run = executor(build_until)
            build_env = {**homes[version], 'PATH': build_path, 'QUINT_BIN': str(quint), 'PLAYWRIGHT_EXECUTABLE_PATH': str(chromium),
                         'npm_config_cache': str(root/'npm-cache'), 'LANG': 'C.UTF-8', **BUILD_DAEMON_OFF}
            build_env.pop('PLAYWRIGHT_BROWSERS_PATH', None)
            output = run([bash, 'build.sh'], adopted, build_env)
            case['build'] = parse_build_output(m, output)
            case['build'].update(exit=0, toolVersions=versions, chromiumExecutableSha256=m.sha(chromium))
            m.write(root/('build-'+version+'.json'), case['build'])
            case['disposition'] = 'materialized-adopted-locked-restore-build-browser-passed'
            summary['phases'][version] = 'passed'
        summary.update(disposition='passed', executionDisposition='passed')
    except BaseException as error:
        primary = error
        summary.update(disposition='failed', executionDisposition='failed', firstCause=(type(error).__name__+': '+str(error))[:8192])
        raise
    finally:
        finish(m, root, summary, receipts, primary, start, contract)
    return summary


def finish(m, root, summary, receipts, primary, start, contract):
    deciding = primary

    def protect(label, operation):
        nonlocal deciding
        try:
            return operation()
        except BaseException as error:
            message = (label+': '+type(error).__name__+': '+str(error))[:8192]
            summary.update(disposition='failed', executionDisposition='failed')
            if deciding is None:
                deciding = error; summary['firstCause'] = message
            else:
                summary['additionalFailures'].append(message); deciding.add_note(message)
            print(message, file=sys.stderr)
    protect('adopted receipt index', lambda: m.write(root/'managed-receipts.json', receipts))

    def reporting():
        summary['seconds'] = time.monotonic()-start; m.write(root/'rehearsal.json', summary)
        through_collection = sum(seconds for name, seconds in PHASES[:[n for n, _ in PHASES].index('collection')+1])
        result = m.collect(root, min(time.monotonic()+120, start+through_collection), contract)
        m.require(not result['failures'], 'adopted-build evidence collection incomplete')
    protect('adopted collection', reporting)
    protect('adopted terminal reporting Unknown', lambda: m.collection_terminal(root, summary, contract))
    if primary is None and deciding is not None:
        raise deciding


def main(args):
    m = load_reader()
    m.require(args in ([], ['--check-admission'], ['--outer-preflight'], ['--record-client-exit'], ['--post-unit']), 'closed adopted-build mode required')
    contract = m.caller_contract('adopted-build', ADMISSION)
    m.validate_admission(os.environ, ADMISSION, contract)
    if args == ['--check-admission']:
        return 0
    if args == ['--outer-preflight']:
        m.outer_preflight(os.environ, contract); return 0
    if args == ['--record-client-exit']:
        m.record_client_exit(os.environ, contract); return 0
    if args == ['--post-unit']:
        m.post_unit(os.environ, contract); return 0
    result = run_adopted_build(os.environ)
    print(json.dumps({'disposition': result['disposition'], 'scope': result['scope']}))
    return 0 if result['disposition'] == 'passed' else 1


if __name__ == '__main__':
    try:
        raise SystemExit(main(sys.argv[1:]))
    except (ValueError, KeyError, OSError, TypeError) as error:
        print(str(error), file=sys.stderr)
        raise SystemExit(3)
