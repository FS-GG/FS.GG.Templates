#!/usr/bin/env python3
"""Always-run PR control: installed C's exact NuGet restore commands from clean caches.

FS-GG/.github#4710 run 39858275028 failed its first hosted restore (NU1403) because no PR job
executed the caller's real restore argv; fixture executors never restore. This control runs,
from a fresh private root, the same code the admitted caller runs:

* the caller's own fresh_environment (fresh HOME, DOTNET_CLI_HOME, NUGET_PACKAGES, HTTP cache),
  its closed acquisition and provision_sdk (the fixed official SDK by its published sha512) and
  closed_nuget_config;
* the caller's fable_install_argv, provider_tool_restore_argv and provider_tool_build_argv;
* the checker's own environment, generation and SvgFoundation restore lines for the default
  and Complete receivers, extracted verbatim from verify-fable-reference-public.sh.

It needs no browser, guest, WASI, Node or Rust, no managed group and no admission, and it
writes only below the private root it is given.
"""
import importlib.util
import json
import os
import pathlib
import shutil
import subprocess
import sys
import time

HERE = pathlib.Path(__file__).resolve().parent
WORKSPACE = HERE.parents[2]
CHECKER = HERE / 'verify-fable-reference-public.sh'
STEP_SECONDS = 900

# Checker lines the control runs verbatim: (selector on the stripped line, required count).
CHECKER_LINES = (
    ('mkdir "$evidence"/{', 1),
    ('export DOTNET_', 2),
    ('archive="$evidence/feed/', 1),
    ('"$DOTNET_HOST_PATH" new ', 3),
    ('for receiver in default direct; do', 1),
    ('foundation="$evidence/$receiver/SvgFoundation"', 1),
    ('enabled=false; [[ "$receiver" != direct ]] || enabled=true', 1),
    ('"$DOTNET_HOST_PATH" restore ', 1),
)


def load_caller():
    spec = importlib.util.spec_from_file_location('wasm_installed_c_runner', HERE / 'wasm-installed-c.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.actual_caller()


def checker_lines():
    text = CHECKER.read_text()
    start = text.index('if [[ "$mode" == wasm ]]; then\n  : "${DOTNET_HOST_PATH:?')
    block = text[start:text.index('\n  exit 0\nfi\n', start)].splitlines()
    selected = {}
    for prefix, count in CHECKER_LINES:
        rows = [line.strip() for line in block if line.strip().startswith(prefix)]
        if len(rows) != count:
            raise SystemExit(f'checker line {prefix!r}: expected {count}, found {len(rows)}')
        selected[prefix] = rows
    return selected


def run(argv, cwd, env, log):
    started = time.monotonic()
    with open(log, 'wb') as out:
        result = subprocess.run(argv, cwd=cwd, env=env, stdout=out, stderr=subprocess.STDOUT, timeout=STEP_SECONDS)
    return {'argv': [str(a) for a in argv], 'exit': result.returncode, 'seconds': round(time.monotonic() - started, 1), 'log': str(log)}


def fsharp_core_sources(packages):
    rows = {}
    for metadata in sorted(pathlib.Path(packages).glob('fsharp.core/*/.nupkg.metadata')):
        value = json.loads(metadata.read_text())
        rows[metadata.parent.name] = {'contentHash': value.get('contentHash'), 'source': value.get('source')}
    return rows


def main():
    if len(sys.argv) != 2 or not os.path.isabs(sys.argv[1]):
        raise SystemExit('usage: installed-c-restore-control.py ABSOLUTE_FRESH_ROOT')
    caller = load_caller()
    lines = checker_lines()
    root = pathlib.Path(sys.argv[1])
    env = caller['fresh_environment'](root, os.environ)  # refuses an occupied root
    deadline = time.monotonic() + 3 * STEP_SECONDS
    tools = root / 'tools'; tools.mkdir(mode=0o700)
    downloads = root / 'downloads'; downloads.mkdir(mode=0o700)
    logs = root / 'logs'; logs.mkdir(mode=0o700)
    records = []
    get = caller['acquirer'](root, downloads, caller['download'], deadline, records)
    url, expected, maximum = caller['ENDPOINTS']['template']
    template = get('template', url, expected, maximum)
    dotnet = str(caller['provision_sdk'](get, tools, deadline))
    env.update(DOTNET_ROOT=str(tools / 'dotnet'), DOTNET_HOST_PATH=dotnet)
    config = caller['closed_nuget_config'](root)
    env['FSGG_WASM_NUGET_CONFIG'] = str(config)
    project = WORKSPACE / 'src/FS.GG.Templates.ProviderTool/FS.GG.Templates.ProviderTool.fsproj'
    summary = {'schema': 'fsgg.templates.installed-c-restore-control/1', 'disposition': 'failed', 'root': str(root),
               'sdk': caller['TOOLS']['sdk'], 'templateVersion': caller['TEMPLATE_VERSION'], 'steps': []}
    report = root / 'restore-control.json'
    try:
        steps = (('fable-tool-install', caller['fable_install_argv'](dotnet, tools, config)),
                 ('provider-tool-restore', caller['provider_tool_restore_argv'](dotnet, project, config)),
                 ('provider-tool-build', caller['provider_tool_build_argv'](dotnet, project)))
        for name, argv in steps:
            step = {'name': name, **run(argv, root, env, logs / (name + '.log'))}
            summary['steps'].append(step)
            if step['exit'] != 0:
                raise RuntimeError(name + ' failed with exit ' + str(step['exit']))
        summary['providerToolFSharpCore'] = fsharp_core_sources(env['NUGET_PACKAGES'])
        # The checker's own environment, generation and restore lines, verbatim, for both receivers.
        evidence = root / 'checker'; evidence.mkdir(mode=0o700)
        script = ['set -euo pipefail', 'evidence=' + json.dumps(str(evidence)), 'version=' + json.dumps(caller['TEMPLATE_VERSION'])]
        script += lines['mkdir "$evidence"/{'] + lines['export DOTNET_'] + lines['archive="$evidence/feed/']
        script += ['cp -- "$CONTROL_TEMPLATE_ARCHIVE" "$archive"  # control glue: the caller-verified package bytes']
        script += lines['"$DOTNET_HOST_PATH" new ']
        script += lines['for receiver in default direct; do'] + lines['foundation="$evidence/$receiver/SvgFoundation"']
        script += lines['enabled=false; [[ "$receiver" != direct ]] || enabled=true'] + lines['"$DOTNET_HOST_PATH" restore ']
        script += ['done']
        (root / 'checker-restore.sh').write_text('\n'.join(script) + '\n')
        summary['checkerScript'] = script
        step = {'name': 'checker-generate-and-restore', **run([shutil.which('bash', path='/usr/bin:/bin'), str(root / 'checker-restore.sh')],
                root, {**env, 'CONTROL_TEMPLATE_ARCHIVE': str(template)}, logs / 'checker-generate-and-restore.log')}
        summary['steps'].append(step)
        if step['exit'] != 0:
            raise RuntimeError('checker generation/restore failed with exit ' + str(step['exit']))
        for receiver in ('default', 'direct'):
            log = evidence / (receiver + '-restore.log')
            summary.setdefault('checkerRestoreLogs', {})[receiver] = log.read_text()[-2000:] if log.is_file() else None
            summary.setdefault('receiverFSharpCore', {})[receiver] = fsharp_core_sources(evidence / receiver / '.nuget/packages')
        summary['disposition'] = 'passed'
    except BaseException as error:
        summary['firstCause'] = type(error).__name__ + ': ' + str(error)
        for path in sorted(logs.glob('*.log')) + sorted(evidence.glob('*-restore.log') if (root / 'checker').is_dir() else []):
            print('--- ' + str(path), file=sys.stderr)
            print(path.read_text(errors='replace')[-4000:], file=sys.stderr)
        raise
    finally:
        summary['acquisitions'] = records
        report.write_text(json.dumps(summary, indent=2) + '\n')
        print(json.dumps({k: summary.get(k) for k in ('disposition', 'firstCause', 'providerToolFSharpCore', 'receiverFSharpCore')}, indent=2))
    return 0


if __name__ == '__main__':
    sys.exit(main())
