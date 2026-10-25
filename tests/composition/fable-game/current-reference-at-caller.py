#!/usr/bin/env python3
"""Current-public branch of the authenticated reusable caller; native activation stays held.

This prepares actual typed/source/public archive inputs. It never converts a local
summary or supplies a caller identity: the existing authenticated workflow owns
the original producer acquisition and preflight. Historical modes do not use it.
"""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


observer = load('current_at_observer', HERE / 'external-reference-orca.py')
local = load('current_at_source_helpers', HERE / 'current-composition-local.py')
public = load('current_at_public', HERE / 'external-reference-public.py')
require = observer.require


def guard(environment):
    observer.current_public_at_admission(environment)


def join_preflight(preflight, plan, controller, plan_sha, observer_sha, mechanical_sha, package, readback):
    """Bind new facts to the original authenticated preflight without promoting its phase."""
    require(preflight['schema'] == 'fsgg.external-reference-native-preflight/1' and
            preflight['disposition'] == 'preflight-passed' and preflight['qualification'] == 'not-run',
            'original authenticated preflight required')
    require(preflight['templates'] == controller and preflight['renderingInputSource'] == 'current-public-composition',
            'current caller/controller selection differs')
    caller = preflight['caller']
    require(caller['repository'] == 'FS-GG/FS.GG.Rendering' and caller['attempt'] == '1' and
            re.fullmatch('[0-9a-f]{40}', caller['revision']) and int(caller['run']) > 0, 'actual Rendering caller identity differs')
    require(preflight['requestedPhase'] in ['preflight', 'full'], 'original requested phase differs')
    require(preflight['producer']['revision'] == plan['rendering']['sourceCommit'] and
            preflight['producer']['custodySha256'] == plan['rendering']['custodySha256'], 'original producer differs')
    local.observations.validate_public_readback(plan, readback)
    require(all(row['payloadMatched'] is True and row['source'] == plan['rendering']['sourceCommit']
                for row in readback['records']), 'actual public custody payload comparison required')
    require(package['producerRevision'] == plan['template']['sourceCommit'] and
            package['archiveSha256'] == plan['template']['sha256'] and
            package['version'] == plan['template']['version'], 'published template identity differs')
    return {**preflight, 'atJourney': observer.LOCAL_SAVE_JOURNEY,
            'currentCompositionPlanSha256': plan_sha, 'observerSourceSha256': observer_sha,
            'mechanicalObserverSha256': mechanical_sha, 'templatePackageInput': package,
            'actualProducerCustodyReadback': True, 'actualAT': False,
            'providerMatrixAcceptance': False, 'nativeImeAcceptance': False, 'whole4817Acceptance': False}


def prepare(root, owner):
    preflight_path = root / 'external-reference-preflight.json'
    preflight = json.loads(preflight_path.read_text())
    # Both the workflow and this entry guard full mode before source or acquisition.
    if preflight['requestedPhase'] == 'full':
        guard(os.environ)
    controller = {key: subprocess.check_output(['git', '-C', str(ROOT), 'rev-parse', ref], text=True).strip()
                  for key, ref in [('revision', 'HEAD'), ('tree', 'HEAD^{tree}')]}
    require(preflight['templates'] == controller, 'checked-out authenticated controller differs')
    raw = subprocess.check_output(['dotnet', str(owner), 'current-composition-plan'])
    require(0 < len(raw) <= 32768, 'typed current plan exceeds bound')
    plan = json.loads(raw)
    # The actual typed owner validates this plan against its source-artifact digest.
    require(plan['rendering']['sourceCommit'] == public.SOURCE and plan['rendering']['version'] == public.VERSION and
            plan['rendering']['custodySha256'] == public.CUSTODY_SHA256 and
            {p['id']: p['sha256'] for p in plan['rendering']['packages']} == public.PUBLIC_SHA256,
            'typed plan/public producer route differs')
    plan_path = root / 'current-composition-plan.json'
    with plan_path.open('xb') as stream:
        stream.write(raw)
    template = plan['template']
    archive = root / 'current-public-template.nupkg'
    identity = template['id'].lower()
    local.fetch('https://api.nuget.org/v3-flatcontainer/%s/%s/%s.%s.nupkg' %
                (identity, template['version'], identity, template['version']), template['sha256'], 8388608, archive)
    subprocess.run(['dotnet', str(owner), 'published-tool-check', '--archive', str(archive), '--sha256', template['sha256'],
                    '--package-id', template['id'], '--version', template['version'], '--source-revision', template['sourceCommit']], check=True)
    # Reuse the actual original custody verifier result and its exact manifest,
    # then compare every selected public payload against that original manifest.
    custody = root / 'rendering-packet/release-custody.json'
    public.acquire(custody, root / 'current-public-feed')
    shutil.copyfile(custody, root / 'current-public-feed/release-custody.json')
    readback = json.loads((root / 'current-public-feed/public-readback.json').read_text())
    package = {'producerRevision': template['sourceCommit'], 'version': template['version'],
               'archiveSha256': template['sha256'], 'installedAcceptance': False,
               'feedQualification': 'actual download not established by supplied archive identity'}
    joined = join_preflight(preflight, plan, controller, observer.digest(plan_path), observer.digest(HERE / 'external-reference-orca.py'),
                            observer.digest(HERE / 'current-composition-observations.py'), package, readback)
    preflight_path.write_text(json.dumps(joined, indent=2) + '\n')


def source(root, owner):
    guard(os.environ)
    preflight = json.loads((root / 'external-reference-preflight.json').read_text())
    require(preflight['requestedPhase'] == 'full' and preflight['actualProducerCustodyReadback'] is True,
            'authenticated full input prerequisite absent')
    config = root / 'current-public-nuget.config'
    config.write_text('<configuration><packageSources><clear/><add key="public" value="https://api.nuget.org/v3/index.json"/></packageSources></configuration>\n')
    tools = local.pinned_tools()
    subprocess.run(['dotnet', 'tool', 'install', 'fable', '--version', tools['fable'], '--tool-path', str(root / 'current-fable'),
                    '--configfile', str(config)], check=True)
    cores = [p for p in (root / 'current-fable').rglob('*.dll') if local.sha256(p) == local.fable_sha()]
    require(len(cores) == 1, 'independent Fable core differs')
    members = root / 'current-fable-members.json'
    members.write_text(json.dumps(local.member_manifest(cores[0].parent)))
    env = dict(os.environ, FSGG_REFERENCE_PROVIDER_TOOL_DLL=str(owner), FSGG_COMPOSITION_FABLE_MEMBERS=str(members),
               FSGG_COMPOSITION_FABLE_SHA=local.fable_sha())
    plan = json.loads((root / 'current-composition-plan.json').read_text())
    subprocess.run(['bash', str(HERE / 'verify-external-reference-candidate.sh'), str(ROOT / '.tmp/rendering-source'),
                    str(root / 'current-public-feed'), plan['rendering']['version'], str(root / 'external-reference'),
                    plan['rendering']['sourceCommit'], 'current-public-composition', str(root / 'current-public-template.nupkg'),
                    plan['template']['sha256'], 'current-at-full'], env=env, check=True)
    packet = json.loads((root / 'external-reference/qualification.json').read_text())
    # Reuse the actual observer's typed original input reader before native setup.
    observer.current_public_inputs(root / 'external-reference', packet, preflight, preflight['templates'])
    require(not observer.prerequisites(packet, preflight, lambda _: True,
                observer.current_public_inputs(root / 'external-reference', packet, preflight, preflight['templates'])),
            'current full source inputs differ')


if __name__ == '__main__':
    if sys.argv[1:] == ['guard']:
        guard(os.environ)
    elif len(sys.argv) == 4 and sys.argv[1] in ['prepare', 'source']:
        (prepare if sys.argv[1] == 'prepare' else source)(Path(sys.argv[2]), Path(sys.argv[3]))
    else:
        raise SystemExit('usage: current-reference-at-caller.py guard | prepare|source ROOT TYPED_OWNER')
