#!/usr/bin/env python3
"""Local ordinary-verification runner for the typed current-composition DOM cases (ADR-0096).

Runs the typed owner's plan on a clean checkout, in one fresh private root, with a closed
environment: build the typed owner, fetch the exact public template and Rendering archives by
their typed SHA-256, generate and build the receiver through the existing source stage, then run
every selected browser family with no retry, skip or flake. It needs no Root runtime admission,
original clock or managed-group owner. Every file it creates is under its root (the optional
container runtime keeps its image store under the real home), and it passes no ambient credential
to any child process. It refuses to start on a hosted runner.

The product under test is the exact published template and Rendering archives, fetched by typed
SHA-256; the checkout supplies the harness, the typed plan and the stage script. It is development
verification only: it does not accept hosted runtime, installed, published, producer-custody,
durable-save, assistive-technology or whole-#4818 scope.
"""
import argparse
import hashlib
import importlib.util
import json
import os
import re
import shutil
import signal
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

sys.dont_write_bytecode = True

HERE = Path(__file__).resolve().parent
WORKSPACE = HERE.parents[2]
FAMILIES = ('chromium', 'firefox', 'webkit')
SCHEMA = 'fsgg.current-composition-local/1'


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


observations = load('composition_observations', HERE / 'current-composition-observations.py')
custody = load('composition_custody', HERE / 'current-composition-custody.py')
require = observations.require


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def git(*args):
    return subprocess.check_output(['git', '-C', str(WORKSPACE), *args], text=True).strip()


def pinned_tools():
    """The shared hosted workflow's declared tool versions; the local run must use the same ones."""
    text = (WORKSPACE / '.github/workflows/fable-reference-public.yml').read_text()
    match = re.search(r'^\s*TOOLS = (\{.*\})$', text, re.M)
    require(match is not None, 'declared tool versions absent')
    return json.loads(match.group(1))


def fable_sha():
    match = re.search(r'^\s*FABLE_SHA = "([0-9a-f]{64})"$', (WORKSPACE / '.github/workflows/fable-reference-public.yml').read_text(), re.M)
    require(match is not None, 'declared Fable core identity absent')
    return match.group(1)


def member_manifest(directory):
    rows = {}
    for path in sorted(Path(directory).rglob('*')):
        if path.is_file():
            require(not path.is_symlink() and len(rows) < 20000, 'member closure refused')
            rows[str(path.relative_to(directory))] = {'bytes': path.stat().st_size, 'sha256': sha256(path)}
    require(rows, 'empty member closure')
    return rows


def closed_environment(root, base):
    home = root / 'home'
    env = {
        'PATH': base['PATH'], 'LANG': 'C.UTF-8', 'HOME': str(home), 'TMPDIR': str(root / 'tmp'),
        'DOTNET_CLI_HOME': str(home / 'dotnet'), 'NUGET_PACKAGES': str(root / 'nuget'),
        'NUGET_HTTP_CACHE_PATH': str(root / 'nuget-http'), 'npm_config_cache': str(root / 'npm-cache'),
        'DOTNET_NOLOGO': '1', 'DOTNET_CLI_TELEMETRY_OPTOUT': '1', 'DOTNET_PROCESSOR_COUNT': str(base['cpus']),
        'MSBUILDDISABLENODEREUSE': '1', 'DOTNET_CLI_USE_MSBUILD_SERVER': '0', 'PYTHONDONTWRITEBYTECODE': '1',
        'PLAYWRIGHT_BROWSERS_PATH': str(root / 'browsers'), 'GIT_CONFIG_NOSYSTEM': '1',
        'FSGG_CURRENT_COMPOSITION_LOCAL_VERIFICATION': observations.LOCAL_VERIFICATION,
    }
    if 'DOTNET_ROOT' in base['environ']:
        env['DOTNET_ROOT'] = base['environ']['DOTNET_ROOT']
    if base.get('platform'):
        env['PLAYWRIGHT_HOST_PLATFORM_OVERRIDE'] = base['platform']
    return env


def run(argv, cwd, env, log, timeout):
    """Run one process group to completion; keep its combined output as an ordinary log."""
    started = time.monotonic()
    with open(log, 'wb') as stream:
        proc = subprocess.Popen([str(a) for a in argv], cwd=str(cwd), env=env, stdout=stream,
                                stderr=subprocess.STDOUT, start_new_session=True)
        try:
            proc.wait(timeout=timeout)
        except subprocess.TimeoutExpired as error:
            os.killpg(proc.pid, signal.SIGKILL)  # dotnet, node and browser descendants share the group
            proc.wait()
            raise RuntimeError('timed out after %ds: %s (log %s)' % (timeout, argv[0], log)) from error
    if proc.returncode != 0:
        tail = Path(log).read_bytes()[-2000:].decode('utf-8', 'replace')
        raise RuntimeError('exit %d: %s\n--- %s tail ---\n%s' % (proc.returncode, ' '.join(map(str, argv))[:300], log, tail))
    return round(time.monotonic() - started, 1)


CONTAINER_ENTRY = '''#!/bin/sh
# Browser phase only, inside the host-libraries container. Everything it executes is bind-mounted.
export PATH=/opt/node/bin:/opt/dotnet:$PATH DOTNET_ROOT=/opt/dotnet DOTNET_SYSTEM_GLOBALIZATION_INVARIANT=1
export DOTNET_CLI_TELEMETRY_OPTOUT=1 DOTNET_NOLOGO=1 HOME=/tmp/home TMPDIR=/tmp PLAYWRIGHT_BROWSERS_PATH=/browsers
mkdir -p "$HOME"
cd /receiver/Browser.Tests
exec node node_modules/@playwright/test/cli.js "$@"
'''


def container_prefix(image, root, cpus, family_env, memory_gib=8):
    """podman argv that runs the receiver's Playwright CLI with no network and only bind-mounted tools."""
    dotnet = Path(shutil.which('dotnet')).resolve().parent
    node = Path(shutil.which('node')).resolve().parent.parent
    entry = root / 'container-entry.sh'
    entry.write_text(CONTAINER_ENTRY)
    entry.chmod(0o700)
    cpuset = ','.join(str(cpu) for cpu in sorted(os.sched_getaffinity(0)))
    argv = ['podman', 'run', '--rm', '--network=none', '--cpuset-cpus=' + cpuset, '--memory=%dg' % memory_gib,
            '-v', '%s:/opt/dotnet:ro' % dotnet, '-v', '%s:/opt/node:ro' % node,
            '-v', '%s:/receiver' % (root / 'product/complete'), '-v', '%s:/browsers' % (root / 'browsers'),
            '-v', '%s:/entry.sh:ro' % entry]
    for name in ('FsGgExternalReferenceCandidate', 'FsGgWasmPolicyExample', 'PLAYWRIGHT_BROWSER_FAMILY'):
        argv += ['-e', '%s=%s' % (name, family_env[name])]
    return argv + [image, '/entry.sh']


def pack_source_template(root, env, coordination_source):
    """Pack Workspace.Template from the exact checked-out commit, in a copy under the private root.

    The pack target needs the Coordination Python fixture at the revision the source names, as a git checkout; it is
    taken from a local clone (`--coordination-source`), never fetched. Nothing is written inside the checkout.
    """
    head = git('rev-parse', 'HEAD')
    source = root / 'source'
    source.mkdir(mode=0o700)
    archive = subprocess.run(['git', '-C', str(WORKSPACE), 'archive', head], capture_output=True, check=True)
    subprocess.run(['tar', '-x', '-C', str(source)], input=archive.stdout, check=True)
    fixture = json.loads((source / 'eng/portable-workspace/python-fixture-source.json').read_text())
    revision = fixture['revision']
    require(re.fullmatch(r'[0-9a-f]{40}', revision) is not None, 'python fixture revision malformed')
    coordination = root / 'coordination'
    subprocess.run(['git', 'clone', '-q', '--shared', '--no-checkout', str(coordination_source), str(coordination)], check=True, env={'PATH': env['PATH']})
    subprocess.run(['git', '-C', str(coordination), 'checkout', '-q', '--detach', revision], check=True, env={'PATH': env['PATH']})
    feed = root / 'template-feed'
    feed.mkdir(mode=0o700)
    pack_env = {**env, 'FSGG_PYTHON_COORDINATION_ROOT': str(coordination)}
    seconds = run(['dotnet', 'pack', source / 'FS.GG.Templates.csproj', '-c', 'Release', '-o', feed, '-m:1', '-p:UseSharedCompilation=false'],
                  source, pack_env, root / 'template-pack.log', 900)
    packages = sorted(feed.glob('*.nupkg'))
    require(len(packages) == 1 and packages[0].name.startswith('FS.GG.Workspace.Template.'), 'exactly one Workspace.Template package expected')
    data = packages[0].read_bytes()
    return {'package': packages[0], 'packageSha256': hashlib.sha256(data).hexdigest(), 'packageBytes': len(data),
            'sourceCommit': head, 'sourceTree': git('rev-parse', 'HEAD^{tree}'), 'pythonFixtureRevision': revision, 'seconds': seconds}


def protected_main(head):
    """True when the checkout is already on the local copy of the protected default branch."""
    result = subprocess.run(['git', '-C', str(WORKSPACE), 'merge-base', '--is-ancestor', head, 'refs/remotes/origin/main'], capture_output=True)
    return result.returncode == 0


def fetch(url, expected, maximum, destination):
    with urllib.request.urlopen(url, timeout=120) as response:
        data = response.read(maximum + 1)
    require(len(data) <= maximum, 'download exceeds its bound: ' + url)
    require(hashlib.sha256(data).hexdigest() == expected, 'download differs from the typed SHA-256: ' + url)
    destination.write_bytes(data)


def fetch_unpinned(url, maximum, destination):
    """Unauthenticated public read whose bytes are verified by the producer's payload compare, not by a pinned hash."""
    require(url.startswith('https://api.nuget.org/v3-flatcontainer/'), 'only the public NuGet flat container is read')
    with urllib.request.urlopen(url, timeout=300) as response:
        data = response.read(maximum + 1)
    require(0 < len(data) <= maximum, 'download exceeds its bound: ' + url)
    destination.write_bytes(data)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    parser.add_argument('--root', required=True, help='fresh private output root (must not exist)')
    parser.add_argument('--families', default=','.join(FAMILIES))
    parser.add_argument('--cpus', type=int, default=2)
    parser.add_argument('--memory-gib', type=int, default=8, help='container memory cap (the proposed hosted envelope is 8)')
    parser.add_argument('--host-platform', default='', help='Playwright host platform override, for example ubuntu24.04-x64')
    parser.add_argument('--container', default='', help='podman image carrying Playwright host libraries '
                        '(see current-composition-local-image.sh); runs the browser phase inside it with '
                        'Node, .NET, the receiver and the browsers bind-mounted. Needed on hosts lacking the libraries.')
    parser.add_argument('--custody-evidence', default='', help='retained read-only acquisition of the original producer artifact '
                        '(receipt.json, rendering-packet.zip, release-custody.json); with --rendering-source it sets '
                        'actualProducerCustodyReadback from an offline join to the typed plan')
    parser.add_argument('--published-all', action='store_true', help='with --custody-evidence: also read every custody archive from the public feed '
                        '(unauthenticated) and compare each payload with the producer compare')
    parser.add_argument('--rendering-source', default='', help='local FS.GG.Rendering git checkout containing the typed producer commit')
    parser.add_argument('--source-built', action='store_true', help='pack Workspace.Template from the checked-out source commit into a private '
                        'feed and run the typed cases against it; the verdict is labelled source-built, never published')
    parser.add_argument('--coordination-source', default='', help='local FS.GG.Coordination clone holding the revision named by '
                        'eng/portable-workspace/python-fixture-source.json (required with --source-built)')
    parser.add_argument('--allow-dirty', action='store_true', help='record, rather than refuse, uncommitted source')
    args = parser.parse_args(argv)

    require(bool(args.custody_evidence) == bool(args.rendering_source), '--custody-evidence and --rendering-source go together')
    require(bool(args.source_built) == bool(args.coordination_source), '--source-built and --coordination-source go together')
    require(not args.published_all or args.custody_evidence, '--published-all needs --custody-evidence')
    families = args.families.split(',')
    require(families and all(f in FAMILIES for f in families) and len(set(families)) == len(families), 'closed browser families required')
    require(1 <= args.cpus <= 3, 'at most 3 CPUs')
    available = sorted(os.sched_getaffinity(0))
    require(len(available) >= args.cpus, 'fewer CPUs than requested')

    root = Path(args.root).resolve()
    require(not root.exists(), 'output root must be fresh')
    require(not root.is_relative_to(WORKSPACE), 'output root must be outside the checkout')
    require(not os.environ.get('GITHUB_ACTIONS'), 'a hosted runner needs its own admission; this runner is for local verification')
    dirty = git('status', '--porcelain', '--untracked-files=no')
    require(args.allow_dirty or not dirty, 'a clean checkout is required so results bind to the exact tree')

    os.sched_setaffinity(0, set(available[:args.cpus]))  # inherited by every child, including the container runtime
    tools = pinned_tools()
    for name in ('home', 'tmp', 'inputs/feed'):
        (root / name).mkdir(parents=True, mode=0o700)
    env = closed_environment(root, {'PATH': os.environ['PATH'], 'environ': os.environ, 'cpus': args.cpus, 'platform': args.host_platform})
    observations.check_admission(env)  # the closed child environment carries no credential
    summary = {
        'schema': SCHEMA, 'disposition': 'failed', 'scope': 'adr-0096-local-development-verification',
        'head': git('rev-parse', 'HEAD'), 'tree': git('rev-parse', 'HEAD^{tree}'), 'dirty': bool(dirty),
        'cpus': args.cpus, 'browserHost': args.container or 'host', 'families': {}, 'seconds': {},
        'hostedRuntimeAdmission': False, 'installedAcceptance': False, 'actualProducerCustodyReadback': False,
        'durableSaveAcceptance': False, 'actualAT': False, 'whole4818Acceptance': False,
        'origin': 'source-built' if args.source_built else 'published', 'publishedAcceptance': False,
    }
    summary_path = root / 'local-summary.json'
    try:
        node = subprocess.check_output(['node', '--version'], env=env, text=True).strip()
        npm = subprocess.check_output(['npm', '--version'], env=env, text=True).strip()
        dotnet = subprocess.check_output(['dotnet', '--version'], env=env, text=True, cwd=str(WORKSPACE)).strip()
        require(node == 'v' + tools['node'] and npm == tools['npm'] and dotnet == tools['sdk'],
                'declared tool versions differ: node %s npm %s sdk %s' % (node, npm, dotnet))
        summary['tools'] = {'node': node, 'npm': npm, 'sdk': dotnet}

        project = WORKSPACE / 'src/FS.GG.Templates.ProviderTool/FS.GG.Templates.ProviderTool.fsproj'
        artifacts = root / 'validator-artifacts'
        summary['seconds']['typedOwnerBuild'] = run(
            ['dotnet', 'build', project, '-c', 'Release', '--artifacts-path', artifacts, '-m:1', '--disable-build-servers'],
            WORKSPACE, env, root / 'typed-owner-build.log', 900)
        core = artifacts / 'bin/FS.GG.Templates.ProviderTool/release/FS.GG.Templates.ProviderTool.dll'
        require(core.is_file(), 'typed owner output absent')
        plan_text = subprocess.check_output(['dotnet', core, 'source-built-composition-plan' if args.source_built else 'current-composition-plan'], env=env, text=True, cwd=str(root))
        require(len(plan_text.encode()) <= 32768, 'typed plan exceeded its bound')
        plan = json.loads(plan_text)
        (root / 'current-composition-plan.json').write_text(plan_text)
        summary['typedOwnerSha256'] = sha256(core)
        summary['fableCoreSha256'] = fable_sha()
        summary['planSha256'] = hashlib.sha256(plan_text.encode()).hexdigest()

        if args.source_built:
            built = pack_source_template(root, env, args.coordination_source)
            template, template_sha = built['package'], built['packageSha256']
            summary['sourceBuilt'] = {key: value for key, value in built.items() if key not in ('package', 'seconds')}
            summary['sourceBuilt']['package'] = built['package'].name
            summary['sourceBuilt']['protectedMain'] = protected_main(built['sourceCommit'])
            summary['seconds']['templatePack'] = built['seconds']
        else:
            row = plan['template']
            identity = row['id'].lower()
            template = root / 'inputs' / (row['id'] + '.' + row['version'] + '.nupkg')
            fetch('https://api.nuget.org/v3-flatcontainer/%s/%s/%s.%s.nupkg' % (identity, row['version'], identity, row['version']),
                  row['sha256'], 8388608, template)
            template_sha = row['sha256']
        version = plan['rendering']['version']
        for package in plan['rendering']['packages']:
            name = package['id'] + '.' + version + '.nupkg'
            fetch('https://api.nuget.org/v3-flatcontainer/%s/%s/%s' % (package['id'].lower(), version, name.lower()),
                  package['sha256'], 33554432, root / 'inputs/feed' / name)

        # Independent Fable install: the stage joins the receiver's restored tool to this member closure.
        config = root / 'nuget.config'
        config.write_text('<configuration><packageSources><clear/><add key="public" value="https://api.nuget.org/v3/index.json"/></packageSources></configuration>\n')
        summary['seconds']['fableInstall'] = run(
            ['dotnet', 'tool', 'install', 'fable', '--version', tools['fable'], '--tool-path', root / 'tools/fable', '--configfile', config],
            root, env, root / 'fable-install.log', 600)
        cores = [path for path in (root / 'tools/fable').rglob('*.dll') if sha256(path) == fable_sha()]
        require(len(cores) == 1, 'Fable core hash differs')
        (root / 'fable-member-identities.json').write_text(json.dumps(member_manifest(cores[0].parent)))
        if args.custody_evidence:
            # Before the expensive stage: the retained producer read must justify the flag first. Offline except the
            # optional unauthenticated public-feed reads of --published-all.
            published_all = None
            if args.published_all:
                published_all = root / 'inputs/published-all'
                published_all.mkdir()
                for file, url in custody.published_urls(args.custody_evidence):
                    fetch_unpinned(url, 64 * 1048576, published_all / file)
            summary['producerCustody'] = custody.verify_producer_custody(
                args.custody_evidence, plan, root / 'inputs/feed', args.rendering_source, root / 'custody', published_all)
        stage_env = {**env, 'FSGG_REFERENCE_PROVIDER_TOOL_DLL': str(core),
                     'FSGG_COMPOSITION_FABLE_MEMBERS': str(root / 'fable-member-identities.json'),
                     'FSGG_COMPOSITION_FABLE_SHA': fable_sha()}
        if args.source_built:
            stage_args = ['bash', WORKSPACE / 'tests/composition/fable-game/verify-source-built-composition.sh', root / 'inputs/feed', root / 'product',
                          root / 'current-composition-plan.json', template, template_sha]
        else:
            stage_args = ['bash', WORKSPACE / 'tests/composition/fable-game/verify-external-reference-candidate.sh',
                          root / 'absent-rendering-source', root / 'inputs/feed', version, root / 'product',
                          plan['rendering']['sourceCommit'], 'current-public-composition', template, template_sha, 'current-source-stage']
        summary['seconds']['sourceStage'] = run(stage_args, WORKSPACE, stage_env, root / 'source-stage.log', 2400)
        stage = json.loads((root / 'product/current-source-stage.json').read_text())
        require(stage['disposition'] == 'source-passed' and stage['browserExecuted'] is False, 'source stage incomplete')

        tests = root / 'product/complete/Browser.Tests'
        playwright = tests / 'node_modules/playwright/cli.js'
        require(playwright.is_file(), 'Playwright is not installed in the receiver')
        # Downloads only; a container supplies the host libraries this machine lacks.
        install_env = {**env, 'PLAYWRIGHT_SKIP_VALIDATE_HOST_REQUIREMENTS': '1'} if args.container else env
        summary['playwrightVersion'] = json.loads((tests / 'node_modules/playwright/package.json').read_text())['version']
        if args.container:
            summary['containerImageId'] = subprocess.check_output(
                ['podman', 'image', 'inspect', args.container, '--format', '{{.Id}}'], text=True).strip()
        summary['seconds']['browserInstall'] = run(['node', playwright, 'install', *families], tests, install_env, root / 'browser-install.log', 1800)
        runner = tests / 'node_modules/@playwright/test/cli.js'
        config = 'current-composition.generated.config.ts'
        for family in families:
            family_env = {**env, **observations.browser_environment(plan), 'PLAYWRIGHT_BROWSER_FAMILY': family}
            if args.container:
                launch = container_prefix(args.container, root, args.cpus, family_env, args.memory_gib)
                # podman keeps its image store under the real home; nothing else of the host environment passes.
                launch_env = {key: os.environ[key] for key in ('PATH', 'HOME', 'XDG_RUNTIME_DIR') if key in os.environ}
                launch_cwd = root
            else:
                launch, launch_env, launch_cwd = ['node', runner], family_env, tests
            listing = subprocess.run([*launch, 'test', '--config', config, '--list', '--reporter=json'], cwd=str(launch_cwd),
                                     env=launch_env, capture_output=True, text=True, timeout=300)
            (root / (family + '-list.json')).write_text(listing.stdout)
            require(listing.returncode == 0, family + ' listing failed: ' + listing.stderr[-2000:])
            observations.validate_listing(json.loads(listing.stdout), plan, family)
            report_path = tests / 'test-results/browser.json'
            if report_path.exists():
                report_path.unlink()
            summary['seconds'][family] = run([*launch, 'test', '--config', config, '--workers=%d' % plan['browsers']['workers'],
                                              '--retries=%d' % plan['browsers']['retries']],
                                             launch_cwd, launch_env, root / (family + '-browser.log'), 1800)
            shutil.copyfile(report_path, root / (family + '-report.json'))
            report = json.loads((root / (family + '-report.json')).read_text())
            observations.validate_report(report, plan, family)
            stats = report['stats']
            summary['families'][family] = {'passed': stats['expected'], 'retries': plan['browsers']['retries'], 'skipped': stats['skipped'],
                                           'reportSha256': sha256(root / (family + '-report.json'))}
        summary['runtimeCases'] = sum(entry['passed'] for entry in summary['families'].values())
        summary['actualProducerCustodyReadback'] = 'producerCustody' in summary  # only when the whole run succeeded
        summary['disposition'] = 'dom-observed-source-built-reference-only' if args.source_built else 'dom-observed-local-reference-only'
    except BaseException as error:
        summary['firstCause'] = (type(error).__name__ + ': ' + str(error))[:8192]
        raise
    finally:
        summary_path.write_text(json.dumps(summary, indent=2) + '\n')
        print('summary:', summary_path, summary['disposition'], summary.get('runtimeCases', 0), 'cases')
    return 0


if __name__ == '__main__':
    sys.exit(main())
