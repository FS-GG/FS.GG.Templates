#!/usr/bin/env python3
"""Provider/Studio actual-AT journey for the current-public composition (FS-GG/.github#4817, item 3).

Scope. The typed current-composition plan selects one provider cell: the published
`fs-gg-fable-game` template, route direct, bundle complete, lifecycle none. This module drives the
generated SVG Studio of that exact generated receiver with a real keyboard and Orca, and binds every
observation to the provider facts that produced the receiver:

  provider-descriptor      descriptor bytes at the template source commit equal the plan's descriptor digest
  provider-selection       the receiver's bundle files are the archive's bytes for the plan's bundle and lifecycle
  studio-package-closure   the Studio restored the plan's public Rendering archives (lock, assets, cached bytes)
  studio-served-bytes      the page Orca read is the receiver's built `dist`, byte for byte
  provider-custody-after   the same facts hold again after the journey and the owned server's reaping

Studio steps are keyboard or AT-SPI actions. Each carries its own causal evidence: the Orca byte offset
was taken before the action and the expected speech lies in the window that starts there; trusted DOM key
events are counted only after the action's pre-sample; focus is the AT-SPI FOCUSED node and the DOM active
element, sampled after the action and different from the pre-action element where focus must move.

`providerMatrixAcceptance` is True only in a receipt that validates every step in order. The matrix is the
plan's single selection cell, stated explicitly; no other provider, lifecycle or route is claimed.

The native run stays behind the existing `CURRENT_PUBLIC_AT_ADMISSION` guard. Nothing here changes it.
No physical audio hardware or human listener is involved.
"""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import shutil
import signal
import subprocess
import sys
import time
import urllib.request
from xml.etree import ElementTree as ET
from zipfile import ZipFile

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
SCHEMA = 'fsgg.current-provider-studio-observation/1'
CUSTODY_SCHEMA = 'fsgg.current-provider-studio-custody/1'
JOURNEY = 'current-public-provider-studio'
TEMPLATE_ID = 'FS.GG.Workspace.Template'
PREFIX = 'content/templates/fs-gg-fable-game/'
ADDRESS = 'http://127.0.0.1:8144/'
SPEECH_LIMIT = 32 * 1048576
# Closed list: the bundle=complete files that define the Studio and its examples. Each is the archive entry
# after the template's own product-name transform (Studio/Program.fs carries the namespace token).
BUNDLE_FILES = ['SvgFoundation/Studio/Studio.fsproj', 'SvgFoundation/Studio/Program.fs', 'SvgFoundation/Studio/build.sh',
                'SvgFoundation/Studio/index.html', 'SvgFoundation/Studio/vite.config.js',
                'SvgFoundation/Examples/ExternalAuthority/reference.json', 'SvgFoundation/Examples/FourD/reference.json',
                'SvgFoundation/Examples/Tactical/scene.json', 'SvgFoundation/Examples/Arcade/scene.json']
LIFECYCLE_NONE_ABSENT = ['.fsgg/sdd.yml', '.fsgg/providers.yml', '.fsgg/scaffold-provenance.json']
STUDIO_PACKAGES = ['FS.GG.UI.Scene', 'FS.GG.UI.Scene.SvgBrowser', 'FS.GG.UI.KeyboardInput']

SCENE = {'name': 'Generated SVG scene studio', 'role': 'embedded', 'domId': 'generated-authoring-studio--scene',
         'domRole': 'application'}
# kind provider steps are computed from custody; they bracket the Studio steps (see PROVIDER_*).
PROVIDER_BEFORE = ['provider-descriptor', 'provider-selection', 'studio-package-closure', 'studio-served-bytes']
PROVIDER_AFTER = ['provider-custody-after']
STUDIO_STEPS = [
    {'id': 'studio-heading', 'how': 'tree', 'present': [('heading', 'Generated SVG scene studio')]},
    {'id': 'tab-to-rectangle', 'how': 'tab', 'target': 'Rectangle', 'via': [], 'speech': ['Rectangle'],
     'focus': {'name': 'Rectangle', 'role': 'push button', 'domId': None, 'domRole': None}, 'changes': True},
    {'id': 'create-rectangle', 'how': 'keys', 'keys': ['Return'], 'domKeys': ['Enter'], 'speech': ['Rectangle created and selected'],
     'present': [(None, 'created and selected')]},
    {'id': 'edit-scene-properties', 'how': 'atspi', 'name': 'Edit scene properties', 'role': 'push button',
     'speech': ['Scene properties and grid edited'], 'present': [(None, 'properties and grid edited')]},
    {'id': 'place-two-instances-refused', 'how': 'atspi', 'name': 'Place two instances', 'role': 'push button',
     'speech': ['save the sample asset first'], 'present': [(None, 'save the sample asset first')]},
    {'id': 'tab-to-command-palette', 'how': 'tab', 'target': 'Command palette',
     'via': ['Replay timeline', 'Replay complete arena recording'], 'speech': ['Command palette'],
     'focus': {'name': 'Command palette', 'role': 'push button', 'domId': None, 'domRole': None}, 'changes': True},
    {'id': 'open-command-palette', 'how': 'keys', 'keys': ['Return'], 'domKeys': ['Enter'],
     'speech': ['dialog', 'Command palette', 'heading', 'Command palette opened'],
     'present': [('dialog', 'Command palette')],
     'focus': {'name': 'Command palette', 'role': 'heading', 'domId': None, 'domRole': 'heading'}, 'changes': True},
    {'id': 'escape-restores-scene-focus', 'how': 'keys', 'keys': ['Escape'], 'domKeys': ['Escape'], 'speech': [],
     'absent': [('dialog', 'Command palette')], 'focus': SCENE, 'changes': True},
    {'id': 'enter-focus-mode', 'how': 'modifier', 'keys': ['Insert+a'], 'speech': ['Focus mode'], 'focus': SCENE, 'changes': False},
    {'id': 'input-help-shortcut', 'how': 'keys', 'keys': ['g', 'h'], 'domKeys': ['g', 'h'], 'speech': ['Possible input help opened'],
     'present': [('dialog', 'Possible input help')]},
    {'id': 'close-input-help', 'how': 'atspi', 'name': 'Close workspace overlay', 'role': 'push button',
     'speech': [], 'absent': [('dialog', 'Possible input help')]},
    {'id': 'open-rebind', 'how': 'atspi', 'name': 'Rebind command', 'role': 'push button',
     'speech': ['Rebind capture waiting for raw input'], 'present': [('dialog', 'Rebind command'), (None, 'Conflict feedback')]},
    {'id': 'close-rebind', 'how': 'atspi', 'name': 'Close workspace overlay', 'role': 'push button',
     'speech': [], 'absent': [('dialog', 'Rebind command')]},
    {'id': 'arrange-mode', 'how': 'atspi', 'name': 'Arrange mode', 'role': 'toggle button', 'speech': ['Mode: Arrange'],
     'present': [(None, 'Mode: Arrange')]},
]
STEP_IDS = PROVIDER_BEFORE + [s['id'] for s in STUDIO_STEPS] + PROVIDER_AFTER


def require(condition, message):
    if not condition:
        raise ValueError(message)


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def sha256_bytes(data):
    return hashlib.sha256(data).hexdigest()


def sha256_file(path, limit=64 * 1048576):
    path = Path(path)
    require(path.is_file() and not path.is_symlink() and path.stat().st_size <= limit, 'bounded regular input required: ' + path.name)
    return sha256_bytes(path.read_bytes())


def canonical(value):
    return json.dumps(value, sort_keys=True, allow_nan=False, separators=(',', ':'))


# ---------------------------------------------------------------- provider custody (pure, reads real bytes)

def fetch_descriptor(source, download=None):
    require(re.fullmatch('[0-9a-f]{40}', source) is not None, 'descriptor needs an immutable source revision')
    url = 'https://raw.githubusercontent.com/FS-GG/FS.GG.Templates/%s/providers/fable-game.providers.yml' % source
    if download is not None:
        return download(url)
    with urllib.request.urlopen(url, timeout=60) as response:
        raw = response.read(65537)
    require(len(raw) <= 65536, 'descriptor oversized')
    return raw


def descriptor_facts(raw):
    text = raw.decode('utf-8')
    keys = re.findall(r'^      - key: (\w+)$', text, re.M)
    template = re.findall(r'^    templateId: (\S+)$', text, re.M)
    return {'templateId': template[0] if len(template) == 1 else None, 'parameters': keys}


def dist_manifest(dist):
    dist = Path(dist)
    require(dist.is_dir() and not dist.is_symlink() and (dist / 'index.html').is_file(), 'built Studio dist absent')
    rows = []
    for path in sorted(dist.rglob('*')):
        if path.is_dir():
            continue
        require(not path.is_symlink() and path.is_file() and len(rows) < 2000, 'dist member refused')
        rows.append({'path': path.relative_to(dist).as_posix(), 'sha256': sha256_file(path)})
    return rows


def custody(receiver, plan, archive, descriptor):
    """Read the generated receiver and its template/Rendering inputs. Raises on any provider-fact mismatch."""
    receiver, archive = Path(receiver), Path(archive)
    template, selection, rendering = plan['template'], plan['selection'], plan['rendering']
    require(selection['route'] == 'direct' and selection['bundle'] == 'complete' and selection['lifecycle'] == 'none',
            'only the typed plan direct/complete/none provider cell is covered')
    archive_sha = sha256_file(archive, 32 * 1048576)
    require(archive_sha == template['sha256'], 'template archive differs from the typed plan')
    with ZipFile(archive) as package:
        nuspecs = [n for n in package.namelist() if n.endswith('.nuspec')]
        require(len(nuspecs) == 1, 'template archive needs exactly one nuspec')
        metadata = ET.fromstring(package.read(nuspecs[0])).find('{*}metadata')
        repository = metadata.find('{*}repository')
        require(metadata.findtext('{*}id') == TEMPLATE_ID and metadata.findtext('{*}version') == template['version'] and
                repository is not None and repository.get('commit') == template['sourceCommit'], 'template package identity differs')
        # Provider descriptor, fetched at the immutable template source commit, is the declared parameter surface.
        require(sha256_bytes(descriptor) == template['descriptorSha256'], 'provider descriptor differs from the typed plan')
        facts = descriptor_facts(descriptor)
        require(facts['templateId'] == 'fs-gg-fable-game' and {'bundle', 'lifecycle', 'productName'} <= set(facts['parameters']),
                'provider descriptor does not declare the selected parameters')
        product = selection['productName']
        files = []
        for relative in BUNDLE_FILES:
            expected = package.read(PREFIX + relative).decode('utf-8').replace('FableGameWorkspaceNamespace', product).replace('FableGameWorkspace', product)
            actual = (receiver / relative)
            require(actual.is_file() and not actual.is_symlink() and actual.read_bytes() == expected.encode('utf-8'),
                    'receiver bundle file differs from the selected template bytes: ' + relative)
            files.append({'path': relative, 'sha256': sha256_file(actual)})
    require(all(not (receiver / name).exists() for name in LIFECYCLE_NONE_ABSENT), 'lifecycle none receiver carries lifecycle provenance')
    # Studio package closure.
    studio = receiver / 'SvgFoundation/Studio'
    project = ET.parse(studio / 'Studio.fsproj')
    defaults = [node.text for node in project.iter() if node.tag == 'FsGgSvgAuthoringVersion']
    require(defaults == [rendering['version']], 'Studio authoring default differs from the typed Rendering version: %s' % defaults)
    lock = json.loads((studio / 'packages.lock.json').read_text())
    assets_path = studio / 'obj/project.assets.json'
    assets = json.loads(assets_path.read_text())
    cache = (receiver / '.nuget/packages').resolve()
    require({str(Path(p).resolve()) for p in assets['packageFolders']} == {str(cache)}, 'Studio package folder differs')
    require(sorted(row['id'] for row in rendering['packages']) == sorted(STUDIO_PACKAGES), 'typed Rendering package population differs')
    packages = []
    for row in rendering['packages']:
        identity, version = row['id'], rendering['version']
        for dependencies in lock['dependencies'].values():
            actual = dependencies[identity]
            require(actual['resolved'] == version and actual['contentHash'] == row['lockContentHash'], 'Studio lock identity differs: ' + identity)
        require(assets['libraries'][identity + '/' + version]['type'] == 'package', 'Studio package is not package-backed: ' + identity)
        folder = cache / identity.lower() / version
        cached = folder / (identity.lower() + '.' + version + '.nupkg')
        require(sha256_file(cached) == row['sha256'], 'Studio cached archive differs from the typed public archive: ' + identity)
        require(json.loads((folder / '.nupkg.metadata').read_text())['contentHash'] == row['lockContentHash'], 'Studio cache content hash differs')
        packages.append({'id': identity, 'version': version, 'sha256': row['sha256'], 'lockContentHash': row['lockContentHash']})
    require(all(v['type'] != 'project' for k, v in assets['libraries'].items() if k.startswith('FS.GG.UI.')), 'Studio carries a project-backed UI package')
    manifest = dist_manifest(studio / 'dist')
    return {'schema': CUSTODY_SCHEMA,
            'provider': {'templateId': facts['templateId'], 'version': template['version'], 'source': template['sourceCommit'],
                         'archiveSha256': archive_sha, 'descriptorSha256': template['descriptorSha256'], 'parameters': facts['parameters']},
            'selection': dict(selection),
            'bundle': {'name': selection['bundle'], 'files': files},
            'lifecycle': {'name': selection['lifecycle'], 'absent': LIFECYCLE_NONE_ABSENT},
            'studio': {'authoringDefault': defaults[0], 'lockSha256': sha256_file(studio / 'packages.lock.json'),
                       'assetsSha256': sha256_bytes(assets_path.read_bytes()), 'packages': packages,
                       'distManifestSha256': sha256_bytes(canonical(manifest).encode()),
                       'distIndexSha256': next(r['sha256'] for r in manifest if r['path'] == 'index.html'),
                       'distFiles': len(manifest)}}


# ---------------------------------------------------------------- Orca speech window (original bytes)

def speech_text(path, start, end=None):
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        size = os.fstat(fd).st_size
        require(size <= SPEECH_LIMIT, 'Orca speech evidence over budget')
        end = size if end is None else end
        require(type(start) is int and type(end) is int and 0 <= start <= end <= size, 'Orca speech byte range invalid')
        os.lseek(fd, start, os.SEEK_SET)
        raw = b''
        while len(raw) < end - start:
            chunk = os.read(fd, min(65536, end - start - len(raw)))
            require(chunk, 'Orca speech evidence truncated')
            raw += chunk
    finally:
        os.close(fd)
    return '\n'.join(line.split('SPEECH OUTPUT:', 1)[1] for line in raw.decode(errors='replace').splitlines() if 'SPEECH OUTPUT:' in line)


# ---------------------------------------------------------------- journey runner (primitives are injected)

def active_matches(active, expected):
    label = active.get('ariaLabel') or active.get('text')
    return (label == expected['name'] and (expected['domId'] is None or active.get('id') == expected['domId']) and
            (expected['domRole'] is None or active.get('role') == expected['domRole']))


def run_steps(p, custody_before, sleep=time.sleep, clock=time.monotonic, wait_tree=True):
    """Perform provider steps 1-4 and every Studio step through `p`; return the step records.

    Primitives: speech_offset(), speech_between(start, end), dom(), key(*keys), activate(name, role),
    focused() -> [{name, role}], present(role, name) -> bool, served_index_sha256(). The AT-SPI driver
    (provider-studio-orca.py) supplies the real ones; inert controls supply a model.
    """
    records = []
    for name, check in [('provider-descriptor', custody_before['provider']['descriptorSha256']),
                        ('provider-selection', sha256_bytes(canonical([custody_before['selection'], custody_before['bundle'], custody_before['lifecycle']]).encode())),
                        ('studio-package-closure', sha256_bytes(canonical(custody_before['studio']['packages'] + [custody_before['studio']['lockSha256']]).encode()))]:
        records.append({'id': name, 'kind': 'provider', 'bound': check})
    served = p.served_index_sha256()
    records.append({'id': 'studio-served-bytes', 'kind': 'provider', 'bound': custody_before['studio']['distIndexSha256'], 'served': served})
    for step in STUDIO_STEPS:
        records.append(run_studio_step(step, p, sleep, clock, wait_tree))
    return records


def wait_for(predicate, seconds, sleep, clock, message):
    end = clock() + seconds
    while True:
        value = predicate()
        if value:
            return value
        require(clock() < end, message)
        sleep(.1)


def fresh_after(p, sequence, sleep, clock):
    return wait_for(lambda: (lambda d: d if d['sampleSequence'] > sequence else None)(p.dom()), 10, sleep, clock, 'no browser sample after the action')


def tree_state(step, p):
    """One observation of the AT tree: which required objects are present, which removed ones are absent."""
    present = [p.present(role, name) is True for role, name in step.get('present', [])]
    absent = [p.present(role, name) is not True for role, name in step.get('absent', [])]
    return present, absent


def run_studio_step(step, p, sleep, clock, wait_tree=True):
    """Perform one action and record what was observed. `wait_tree=False` is a control seam only: it removes the
    runner's own tree wait so the validator's independent check of the recorded observation can be exercised."""
    how = step['how']
    record = {'id': step['id'], 'kind': 'studio', 'how': how}
    before = p.dom()
    start = p.speech_offset()
    for role, name in step.get('absent', []):
        require(p.present(role, name) is True, 'removal without prior presence: %s %s' % (role, name))
    if how == 'tree':
        for role, name in step['present']:
            wait_for(lambda role=role, name=name: p.present(role, name), 30, sleep, clock, 'AT-SPI object unavailable: %s %s' % (role, name))
        present, absent = tree_state(step, p)
        record['tree'] = {'present': [list(v) for v in step['present']], 'absent': [], 'presentAfter': present, 'absentAfter': absent}
        record.update(keyEvents=[], domBefore=slim(before), domAfter=slim(before))
        return record
    hop_rows = []
    if how == 'tab':
        # Real Tab presses until each hop, then the target, is the DOM-active and AT-SPI-focused control; one row per hop.
        for hop in step['via'] + [step['target']]:
            for presses in range(1, 121):
                p.key('Tab')
                dom = p.dom()
                active = dom['observation']['activeElement']
                landed = [dict(f) for f in p.focused() if f['name'] == hop][:1]
                if dom['observation']['documentHasFocus'] and active_matches(active, {'name': hop, 'domId': None, 'domRole': None}) and landed:
                    hop_rows.append({'target': hop, 'presses': presses, 'domActive': dict(active), 'atspi': landed})
                    break
            else:
                raise ValueError('keyboard focus did not reach ' + hop)
    elif how in ('keys', 'modifier'):
        p.key(*step['keys'])
    elif how == 'atspi':
        p.activate(step['name'], step['role'])
    else:
        raise ValueError('unknown step kind')
    deadline = clock() + 15
    while True:
        spoken_end = p.speech_offset()
        spoken = p.speech_between(start, spoken_end)
        conditions = [phrase in spoken for phrase in step.get('speech', [])]
        tree_ok = True
        if wait_tree:
            present, absent = tree_state(step, p)
            tree_ok = all(present) and all(absent)
        focus_ok = True
        if step.get('focus'):
            dom = p.dom()
            focus_ok = (dom['sampleSequence'] > before['sampleSequence'] and dom['observation']['documentHasFocus'] is True and
                        active_matches(dom['observation']['activeElement'], step['focus']) and
                        any(f['name'] == step['focus']['name'] and f['role'] == step['focus']['role'] for f in p.focused()))
        if all(conditions) and tree_ok and focus_ok:
            break
        require(clock() < deadline, 'step did not complete causally within its deadline: ' + step['id'])
        sleep(.1)
    after = fresh_after(p, before['sampleSequence'], sleep, clock)
    # The observation recorded for the validator is a separate final read, never the wait condition itself.
    present, absent = tree_state(step, p)
    record['keyEvents'] = [{'n': k['n'], 'key': k['key'], 'trusted': k['trusted']} for k in after['observation']['keys']
                           if k['n'] > before['observation']['keysTotal']]
    record['domBefore'], record['domAfter'] = slim(before), slim(after)
    if hop_rows:
        record['hops'] = hop_rows
    if step.get('speech'):
        record['speech'] = {'expect': list(step['speech']), 'offsetBefore': start, 'start': start, 'end': spoken_end}
    if step.get('focus'):
        record['focus'] = {'expect': dict(step['focus']), 'atspi': [dict(f) for f in p.focused()
                           if f['name'] == step['focus']['name'] and f['role'] == step['focus']['role']][:1]}
    record['tree'] = {'present': [list(v) for v in step.get('present', [])], 'absent': [list(v) for v in step.get('absent', [])],
                      'presentAfter': present, 'absentAfter': absent}
    return record


def slim(sample):
    observation = sample['observation']
    return {'sampleSequence': sample['sampleSequence'], 'sampledAtUnixMs': sample['sampledAtUnixMs'],
            'documentHasFocus': observation['documentHasFocus'], 'active': observation['activeElement'],
            'keysTotal': observation['keysTotal']}


# ---------------------------------------------------------------- validation

def new_state():
    return {'end': 0, 'sequence': 0, 'sampledAt': 0, 'keysTotal': None, 'observed': {}, 'events': []}


def validate_keys(step, record, before, after):
    events = record['keyEvents']
    keys = [e['key'] for e in events]
    require([e['n'] for e in events] == list(range(before['keysTotal'] + 1, after['keysTotal'] + 1)),
            'key events are not exactly the counter delta after the pre-sample: ' + step['id'])
    how = step['how']
    if how == 'tab':
        hops = record.get('hops', [])
        require([h['target'] for h in hops] == step['via'] + [step['target']] and sum(h['presses'] for h in hops) == len(events) and
                all(h['presses'] >= 1 for h in hops), 'Tab hops differ: ' + step['id'])
        for hop in hops:
            require(active_matches(hop['domActive'], {'name': hop['target'], 'domId': None, 'domRole': None}) and
                    [a['name'] for a in hop['atspi']] == [hop['target']], 'Tab hop not on its control: ' + hop['target'])
        require(set(keys) == {'Tab'} and all(e['trusted'] is True for e in events), 'Tab navigation lacks trusted key events: ' + step['id'])
    elif how == 'keys':
        # xdotool names the key; the browser reports event.key (Return -> Enter).
        require(keys == step['domKeys'] and all(e['trusted'] is True for e in events), 'expected trusted key events absent: ' + step['id'])
    else:
        # AT-SPI actions and Orca-modifier chords reach the page as no key event at all.
        require(events == [], 'step is not a keyless route: ' + step['id'])


def validate_studio_step(step, record, state, read_speech):
    require(record['kind'] == 'studio' and record['how'] == step['how'], 'step shape differs: ' + step['id'])
    before, after = record['domBefore'], record['domAfter']
    require(type(before['sampleSequence']) is int and before['sampleSequence'] >= state['sequence'] and
            before['sampledAtUnixMs'] >= state['sampledAt'], 'pre-action sample precedes the previous step: ' + step['id'])
    if state['keysTotal'] is not None:
        require(before['keysTotal'] == state['keysTotal'], 'key counter moved between steps: ' + step['id'])
    if step['how'] == 'tree':
        require(canonical(before) == canonical(after), 'tree step needs one sample: ' + step['id'])
    else:
        require(after['sampleSequence'] > before['sampleSequence'] and after['sampledAtUnixMs'] >= before['sampledAtUnixMs'],
                'post-action browser sample is not after the action: ' + step['id'])
    require(after['keysTotal'] >= before['keysTotal'], 'key counter moved backwards: ' + step['id'])
    validate_keys(step, record, before, after)
    speech = record.get('speech')
    if step.get('speech'):
        # Steps that expect speech carry a window taken before the action; silent steps (removal, restore) rest on tree and focus.
        require(speech is not None and speech['expect'] == step['speech'], 'speech expectation differs: ' + step['id'])
        start, end = speech['start'], speech['end']
        require(type(start) is int and type(end) is int and speech['offsetBefore'] == start and state['end'] <= start < end,
                'speech window is not a fresh window taken before the action: ' + step['id'])
        text = read_speech(start, end)
        require(all(phrase in text for phrase in step['speech']), 'actual Orca speech absent from the post-action window: ' + step['id'])
        state['end'] = end
    else:
        require(speech is None, 'silent step carries a speech window: ' + step['id'])
    if step.get('focus'):
        focus = record['focus']
        wanted = {'name': step['focus']['name'], 'role': step['focus']['role']}
        require(focus['expect'] == step['focus'] and after['documentHasFocus'] is True and
                active_matches(after['active'], step['focus']) and focus['atspi'] == [wanted], 'focus not on the expected control: ' + step['id'])
        if step['changes']:
            require(before['active'] != after['active'], 'focus did not change after the action: ' + step['id'])
    tree = record['tree']
    present, absent = [list(v) for v in step.get('present', [])], [list(v) for v in step.get('absent', [])]
    require(tree['present'] == present and tree['absent'] == absent, 'tree expectation differs: ' + step['id'])
    # The observed post-action tree, not the static step table: required objects are showing, removed ones are gone.
    require(tree['presentAfter'] == [True] * len(present) and tree['absentAfter'] == [True] * len(absent),
            'observed tree state differs after the action: ' + step['id'])
    for role, name in absent:
        # A removal is evidence only if an earlier step observed the object present and nothing since observed it gone.
        require(state['observed'].get((role, name)) is True, 'removed object was never observed present: %s %s (%s)' % (role, name, step['id']))
        state['observed'][(role, name)] = False
    for role, name in present:
        state['observed'][(role, name)] = True
    state.update(sequence=after['sampleSequence'], sampledAt=after['sampledAtUnixMs'], keysTotal=after['keysTotal'])
    state['events'].extend(record['keyEvents'])
    return state


def validate_final_dom(final, state):
    """The retained last browser sample must contain every recorded key event, unchanged, and no others after them."""
    require(final.get('schema') == 'fsgg.orca-browser-dom/v1' and final.get('browserFamily') == 'chromium' and
            type(final.get('sampleSequence')) is int and 'observation' in final, 'retained browser sample malformed')
    observation = final['observation']
    require(final['sampleSequence'] >= state['sequence'] and observation['keysTotal'] == state['keysTotal'],
            'retained browser sample disagrees with the journey key counter')
    retained = {k['n']: k for k in observation['keys']}
    for event in state['events']:
        row = retained.get(event['n'])
        require(row is not None and row['key'] == event['key'] and row['trusted'] == event['trusted'],
                'recorded key event is not in the retained browser sample: %s' % event['n'])


def validate_journey(steps, before, after, read_speech, final_dom):
    """Strict, ordered, complete: a missing, extra, reordered or duplicated step refuses."""
    require([r.get('id') for r in steps] == STEP_IDS, 'provider/Studio step population or order differs')
    by_id = {r['id']: r for r in steps}
    selection_sha = sha256_bytes(canonical([before['selection'], before['bundle'], before['lifecycle']]).encode())
    package_sha = sha256_bytes(canonical(before['studio']['packages'] + [before['studio']['lockSha256']]).encode())
    bound = {'provider-descriptor': before['provider']['descriptorSha256'], 'provider-selection': selection_sha,
             'studio-package-closure': package_sha, 'studio-served-bytes': before['studio']['distIndexSha256']}
    for name, value in bound.items():
        require(by_id[name]['kind'] == 'provider' and by_id[name]['bound'] == value, 'provider step differs from its custody: ' + name)
    require(by_id['studio-served-bytes']['served'] == before['studio']['distIndexSha256'], 'served Studio bytes differ from the receiver dist')
    require(canonical(before) == canonical(after), 'provider custody changed during the journey')
    after_record = by_id['provider-custody-after']
    require(after_record['kind'] == 'provider' and after_record['bound'] == sha256_bytes(canonical(after).encode()) and
            after_record['reaped'] is True, 'provider custody after the journey is unbound')
    state = new_state()
    for step in STUDIO_STEPS:
        validate_studio_step(step, by_id[step['id']], state, read_speech)
    validate_final_dom(final_dom, state)
    return True


def validate_receipt(receipt, plan, preflight, directory, local_save, claim=True):
    """Every provider/Studio check. `claim=False` validates a draft whose acceptance flags are still False;
    the run derives its acceptance from this returning, and `claim=True` revalidates the stored receipt."""
    directory = Path(directory)
    require(receipt['schema'] == SCHEMA and receipt['result'] == 'passed' and receipt['journey'] == JOURNEY, 'provider/Studio result incomplete')
    for name, sha in receipt['evidenceSha256'].items():
        require(Path(name).name == name and sha256_file(directory / name) == sha, 'provider/Studio evidence hash mismatch: ' + name)
    for name in ['custody-before.json', 'custody-after.json', 'journey.json', 'orca-debug.log', 'browser-dom.json', 'server.json']:
        require(name in receipt['evidenceSha256'], 'provider/Studio evidence unbound: ' + name)
    before = json.loads((directory / 'custody-before.json').read_text())
    after = json.loads((directory / 'custody-after.json').read_text())
    steps = json.loads((directory / 'journey.json').read_text())['steps']
    final_dom = json.loads((directory / 'browser-dom.json').read_text())
    require(canonical(steps) == canonical(receipt['steps']), 'receipt steps differ from the original journey')
    validate_journey(steps, before, after, lambda start, end: speech_text(directory / 'orca-debug.log', start, end), final_dom)
    require(before['selection'] == plan['selection'] and before['provider']['version'] == plan['template']['version'] and
            before['provider']['archiveSha256'] == plan['template']['sha256'] and
            before['provider']['descriptorSha256'] == plan['template']['descriptorSha256'], 'custody differs from the typed plan')
    require(receipt['templates'] == preflight['templates'] and receipt['caller'] == preflight['caller'] and
            receipt['producer'] == preflight['producer'], 'provider/Studio identity differs from the authenticated preflight')
    cell = {'route': plan['selection']['route'], 'bundle': plan['selection']['bundle'], 'lifecycle': plan['selection']['lifecycle'], 'studio': True}
    require(receipt['matrix'] == {'cells': [cell], 'observed': [cell]}, 'provider matrix cell unobserved')
    require(local_save['result'] == 'passed' and local_save['currentPublicAt']['controller'] == preflight['templates'] and
            receipt['localSaveJoin'] == {'observationSha256': local_save['_sha256'], 'currentPublicAtSha256': sha256_bytes(canonical(local_save['currentPublicAt']).encode())},
            'local-save observation of the same run is unbound')
    require(receipt['process']['name'] == 'orca' and receipt['process']['pid'] > 0 and receipt['browser']['family'] == 'chromium' and
            receipt['browser']['pid'] > 0 and receipt['keyboard'] == 'xdotool-X11' and
            receipt['speechBoundary'] == 'Orca SPEECH OUTPUT' and receipt['physicalAudioHardware'] == 'not-observed' and
            receipt['orcaVersion'] == '46.1', 'actual AT boundary absent')
    server = json.loads((directory / 'server.json').read_text())
    require(server == {'signal': 'SIGTERM', 'exit': -15, 'reaped': True}, 'owned Studio server was not reaped')
    require(all(receipt[k] is False for k in ['nativeImeAcceptance', 'durableSaveAcceptance', 'whole4817Acceptance']) and
            receipt['providerMatrixAcceptance'] is claim and receipt['studioAtAcceptance'] is claim, 'acceptance flags differ')
    return True


# ---------------------------------------------------------------- workflow registration guard (static)

def workflow_guard(workflow):
    marker = '      - name: Observe provider/Studio Orca journey\n'
    require(workflow.count(marker) == 1, 'provider/Studio step missing or ambiguous')
    section = workflow.split(marker, 1)[1].split('\n      - ', 1)[0]
    require(re.findall(r'^        if: (.+)$', section, re.M) ==
            ["${{ !inputs.preflight-only && inputs.rendering-input-source == 'current-public-composition' }}"], 'provider/Studio branch differs')
    require('current-reference-provider-studio.py run "$RUNNER_TEMP"' in section, 'provider/Studio entry differs')
    require(workflow.index('      - name: Observe actual external reference Orca journey') < workflow.index(marker) <
            workflow.index('      - name: Bind successful full result'), 'provider/Studio ordering drift')
    require('${{ runner.temp }}/provider-studio/**' in workflow, 'provider/Studio original evidence omitted')
    require("      - 'tests/composition/fable-game/current-reference-provider-studio.py'" in workflow and
            "      - 'tests/composition/fable-game/test-current-reference-provider-studio.py'" in workflow, 'provider/Studio paths not watched')
    command = 'python3 -I -B tests/composition/fable-game/test-current-reference-provider-studio.py'
    require(workflow.count(command) == 2, 'provider/Studio pure controls missing from PR/reusable path')
    return True


# ---------------------------------------------------------------- native run (held behind the admission guard)

def wait_server_ready(server, address=ADDRESS, seconds=30, sleep=time.sleep, clock=time.monotonic):
    """Poll the owned Studio server until it answers 200; an early exit or silence refuses before any session starts."""
    end = clock() + seconds
    while True:
        require(server.poll() is None, 'owned Studio server exited before the session')
        try:
            with urllib.request.urlopen(address, timeout=2) as response:
                if response.status == 200:
                    return
        except OSError:
            pass
        require(clock() < end, 'owned Studio server did not answer')
        sleep(.25)


def run(root, environment=None, run_session=None, download=None, guard=None, ready=None):
    """Held run entry. The existing admission guard is the first effect-free statement.

    `guard`, `run_session`, `download` and `ready` exist only for inert controls; the defaults are the maintained
    observer's own guard, the native Orca session, a pinned raw fetch and a poll of the owned server."""
    environment = os.environ if environment is None else environment
    observer = load('provider_studio_observer', HERE / 'external-reference-orca.py')
    (guard or observer.current_public_at_admission)(environment)
    root = Path(root)
    preflight = json.loads((root / 'external-reference-preflight.json').read_text())
    plan = json.loads((root / 'current-composition-plan.json').read_text())
    require(preflight['requestedPhase'] == 'full' and preflight['atJourney'] == observer.LOCAL_SAVE_JOURNEY and
            preflight['renderingInputSource'] == 'current-public-composition', 'authenticated full current-public preflight required')
    local_path = root / 'external-reference/orca/observation.json'
    local = json.loads(local_path.read_text())
    local['_sha256'] = sha256_file(local_path)
    receiver, archive = root / 'external-reference/complete', root / 'current-public-template.nupkg'
    out = root / 'provider-studio'
    out.mkdir(mode=0o700)
    descriptor = fetch_descriptor(plan['template']['sourceCommit'], download)
    (out / 'descriptor.yml').write_bytes(descriptor)
    before = custody(receiver, plan, archive, descriptor)
    (out / 'custody-before.json').write_text(json.dumps(before, indent=2, sort_keys=True) + '\n')
    with (out / 'server.log').open('wb') as server_log:
        server = subprocess.Popen(['/usr/bin/python3', '-m', 'http.server', '8144', '--bind', '127.0.0.1'], cwd=receiver / 'SvgFoundation/Studio/dist',
                                  stdout=server_log, stderr=subprocess.STDOUT, start_new_session=True)
        try:
            (ready or wait_server_ready)(server)
            run_session(out, preflight, before) if run_session else native_session(observer, receiver, out, before)
        finally:
            server.send_signal(signal.SIGTERM)
            code = server.wait(timeout=15)
    (out / 'server.json').write_text(json.dumps({'signal': 'SIGTERM', 'exit': code, 'reaped': code == -15}) + '\n')
    after = custody(receiver, plan, archive, descriptor)
    (out / 'custody-after.json').write_text(json.dumps(after, indent=2, sort_keys=True) + '\n')
    journey = json.loads((out / 'journey.json').read_text())
    journey['steps'].append({'id': 'provider-custody-after', 'kind': 'provider', 'bound': sha256_bytes(canonical(after).encode()), 'reaped': code == -15})
    (out / 'journey.json').write_text(json.dumps(journey, indent=2) + '\n')
    cell = {'route': plan['selection']['route'], 'bundle': plan['selection']['bundle'], 'lifecycle': plan['selection']['lifecycle'], 'studio': True}
    draft = {'schema': SCHEMA, 'result': 'passed', 'journey': JOURNEY, 'templates': preflight['templates'], 'caller': preflight['caller'],
             'producer': preflight['producer'], 'process': journey['process'], 'browser': journey['browser'], 'keyboard': 'xdotool-X11',
             'speechBoundary': 'Orca SPEECH OUTPUT', 'physicalAudioHardware': 'not-observed', 'orcaVersion': journey['orcaVersion'],
             'steps': journey['steps'], 'matrix': {'cells': [cell], 'observed': [cell]},
             'localSaveJoin': {'observationSha256': local['_sha256'], 'currentPublicAtSha256': sha256_bytes(canonical(local['currentPublicAt']).encode())},
             'providerMatrixAcceptance': False, 'studioAtAcceptance': False, 'nativeImeAcceptance': False,
             'durableSaveAcceptance': False, 'whole4817Acceptance': False,
             'evidenceSha256': {n: sha256_file(out / n) for n in ['custody-before.json', 'custody-after.json', 'journey.json', 'orca-debug.log',
                                                                  'browser-dom.json', 'server.json', 'descriptor.yml']}}
    # Acceptance is derived from validation: it is True only because the full validator returned for this draft.
    accepted = validate_receipt(draft, plan, preflight, out, local, claim=False) is True
    receipt = dict(draft, providerMatrixAcceptance=accepted, studioAtAcceptance=accepted)
    validate_receipt(receipt, plan, preflight, out, local, claim=True)
    (out / 'receipt.json').write_text(json.dumps(receipt, indent=2) + '\n')
    return receipt


def native_session(observer, receiver, out, before):
    """One Orca session through the shared svg session shell, selecting only the allow-listed provider journey."""
    browser = observer.resolve_browser(receiver, time.monotonic() + 30)
    version = subprocess.check_output(['orca', '--version'], text=True, timeout=30).strip()
    require(version == '46.1', 'Orca version differs')
    env = dict(os.environ, SVG_ORCA_BROWSER_FAMILY='chromium', SVG_ORCA_JOURNEY='provider-studio-orca.py',
               SVG_ORCA_BROWSER_SCRIPT='provider-studio-browser.cjs', PROVIDER_STUDIO_CUSTODY=str(out / 'custody-before.json'),
               PROVIDER_STUDIO_ADDRESS=ADDRESS, PROVIDER_STUDIO_ORCA_VERSION=version,
               PLAYWRIGHT_MODULE_ROOT=str(receiver / 'Browser.Tests/node_modules'), PLAYWRIGHT_EXECUTABLE_PATH=browser['path'])
    output = out / 'orca'
    subprocess.run(['timeout', '--signal=TERM', '--kill-after=15s', '5m', 'bash', str(HERE / 'observe-svg-input-orca.sh'), ADDRESS, str(output)],
                   env=env, check=True)
    for source, name in [('orca.orca-debug.log', 'orca-debug.log'), ('orca.browser-dom.json', 'browser-dom.json')]:
        shutil.copyfile(out / source, out / name)
    shutil.copyfile(output, out / 'journey.json')


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument('action', choices=['run'])
    parser.add_argument('root')
    args = parser.parse_args(argv)
    run(Path(args.root))
    print('provider/Studio journey: passed; evidence=%s/provider-studio/receipt.json' % args.root)


if __name__ == '__main__':
    main()
