#!/usr/bin/env python3
"""Inert controls for the provider/Studio journey producer.

No gi import, Orca, browser, SDK, network or AT operation. A tiny independent model of the Studio and of
Orca's debug log stands in for the live primitives; its speech lines are the verbatim lines of a real
Orca 46.1 run (fixtures/provider-studio-orca-speech.json), so the expected phrases are calibrated on real
output rather than invented. Native execution stays behind CURRENT_PUBLIC_AT_ADMISSION.
"""
import copy
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import re
import tempfile
import unittest
from zipfile import ZipFile

HERE = Path(__file__).resolve().parent


def load(name, file):
    spec = importlib.util.spec_from_file_location(name, HERE / file)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


M = load('provider_studio', 'current-reference-provider-studio.py')
O = load('provider_studio_observer', 'external-reference-orca.py')
REAL = json.loads((HERE / 'fixtures/provider-studio-orca-speech.json').read_text())['lines']
ORDER = [('Bookmark', 'push button'), ('Undo', 'push button'), ('Rectangle', 'push button'), ('Edit scene properties', 'push button'),
         ('Place two instances', 'push button'), ('Replay timeline', 'region'), ('Replay complete arena recording', 'push button'),
         ('Command palette', 'push button')]
SCENE = {'id': 'generated-authoring-studio--scene', 'role': 'application', 'ariaLabel': 'Generated SVG scene studio'}


class Clock:
    def __init__(self):
        self.now = 0.0

    def monotonic(self):
        return self.now

    def sleep(self, seconds):
        self.now += seconds


class Model:
    """Independent model of the Studio, its keyboard focus and Orca's debug log. Not an AT client."""

    def __init__(self, directory, clock, mutant=None, served=None):
        self.log = Path(directory) / 'orca-debug.log'
        self.log.write_bytes(b'09:38:14.000000 - DEBUG filler before any action\n' * 3)
        self.clock, self.mutant, self.served = clock, mutant, served
        self.sequence, self.total, self.keys = 0, 0, []
        self.index, self.active, self.at = None, {'id': None, 'role': None, 'ariaLabel': None, 'text': ''}, []
        self.dialogs, self.texts = set(), set()
        if mutant and mutant[0] == 'early':
            self.speak(mutant[1])   # the phrase exists only BEFORE the action's offset

    def speak(self, step):
        with self.log.open('ab') as stream:
            for row in REAL[step]:
                stream.write((row['text'] + '\n').encode())
            stream.write(b'09:38:15.000000 - DEBUG filler after speech\n')

    def emit(self, step):
        if self.mutant == ('silent', step) or (self.mutant and self.mutant[0] == 'early' and self.mutant[1] == step):
            with self.log.open('ab') as stream:
                stream.write(b'09:38:15.000000 - DEBUG no speech\n')
        else:
            self.speak(step)

    def focus(self, control):
        name, role = control
        self.active = {'id': None, 'role': None, 'ariaLabel': name, 'text': name}
        self.at = [{'name': name, 'role': role}]

    def speech_offset(self):
        return self.log.stat().st_size

    def speech_between(self, start, end):
        return M.speech_text(self.log, start, end)

    def dom(self):
        if not (self.mutant == 'stale-dom' and self.sequence > 0):
            self.sequence += 1
        return {'schema': 'fsgg.orca-browser-dom/v1', 'browserFamily': 'chromium', 'sampleSequence': self.sequence,
                'sampledAtUnixMs': 1000 + self.sequence, 'observation': {
                    'documentHasFocus': self.mutant != 'document-unfocused', 'activeElement': dict(self.active),
                    'focus': [], 'keys': list(self.keys), 'keysTotal': self.total}}

    def record_key(self, name):
        if self.mutant == 'no-key-events':
            return
        self.total += 1
        self.keys.append({'n': self.total, 'at': 1.0, 'key': name, 'trusted': self.mutant != 'untrusted-key', 'target': None})

    def key(self, *names):
        if self.mutant == 'keys-lost':
            return
        for name in names:
            if name == 'Insert+a':
                self.emit('enter-focus-mode')
                continue
            self.record_key({'Return': 'Enter'}.get(name, name))
            current = ORDER[self.index] if self.index is not None else None
            if name == 'Tab':
                self.index = 0 if self.index is None else (self.index + 1) % len(ORDER)
                self.focus(ORDER[self.index])
                if ORDER[self.index][0] == 'Rectangle':
                    self.emit('tab-to-rectangle')
                if ORDER[self.index][0] == 'Command palette':
                    self.emit('tab-to-command-palette')
            elif name == 'Return' and current and current[0] == 'Rectangle':
                self.texts.add('Rectangle created and selected')
                self.emit('create-rectangle')
            elif name == 'Return' and current and current[0] == 'Command palette':
                self.dialogs.add('Command palette')
                self.active = {'id': None, 'role': 'heading', 'ariaLabel': 'Command palette', 'text': 'Command palette'}
                self.at = [{'name': 'Command palette', 'role': 'heading'}]
                self.emit('open-command-palette')
            elif name == 'Escape' and 'Command palette' in self.dialogs:
                if self.mutant != 'focus-not-restored':
                    self.dialogs.discard('Command palette')
                    self.active = dict(SCENE, text='')
                    self.at = [{'name': 'Generated SVG scene studio', 'role': 'embedded'}]
                self.emit('escape-restores-scene-focus')
            elif name == 'h':
                self.dialogs.add('Possible input help')
                self.emit('input-help-shortcut')

    def activate(self, name, role):
        if self.mutant == 'action-refused':
            raise RuntimeError('AT-SPI action refused: ' + name)
        table = {'Edit scene properties': ('edit-scene-properties', 'properties and grid edited'),
                 'Place two instances': ('place-two-instances-refused', 'Validation error: save the sample asset first'),
                 'Rebind command': ('open-rebind', 'Rebind command. Press a new input. Conflict feedback: no displacement.'),
                 'Arrange mode': ('arrange-mode', 'Mode: Arrange')}
        if name in table:
            self.texts.add(table[name][1])
            self.emit(table[name][0])
        if name == 'Rebind command':
            self.dialogs.add('Rebind command')
        if name == 'Close workspace overlay':
            self.dialogs.discard('Possible input help')
            self.dialogs.discard('Rebind command')
        for position, control in enumerate(ORDER):
            if control[0] == name:
                self.index = position
                self.focus(control)

    def focused(self):
        return list(self.at)

    def present(self, role, name):
        if role == 'heading' and name == 'Generated SVG scene studio':
            return True
        if role is None:
            return any(name in text for text in self.texts)
        return role == 'dialog' and name in self.dialogs

    def served_index_sha256(self):
        return self.served


def sha(data):
    return hashlib.sha256(data).hexdigest()


def plan_fixture():
    packages = [{'id': i, 'sha256': sha(i.encode()), 'lockContentHash': 'hash-' + i} for i in M.STUDIO_PACKAGES]
    return {'template': {'id': M.TEMPLATE_ID, 'version': '0.20.1', 'sha256': None, 'sourceCommit': 'a' * 40, 'descriptorSha256': None},
            'selection': {'route': 'direct', 'bundle': 'complete', 'lifecycle': 'none', 'productName': 'CurrentComposition',
                          'externalReference': True, 'wasmPolicyExample': False},
            'rendering': {'version': '0.32.4', 'sourceCommit': 'b' * 40, 'custodySha256': 'c' * 64, 'packages': packages}}


DESCRIPTOR = b'schemaVersion: 1\nproviders:\n  - name: fable-game\n    templateId: fs-gg-fable-game\n    parameters:\n      - key: productName\n      - key: bundle\n      - key: lifecycle\n'


def receiver_fixture(root, version='0.32.4'):
    """A tiny synthetic template archive plus the receiver the template would generate from it."""
    root = Path(tempfile.mkdtemp(dir=root))
    plan = plan_fixture()
    archive = root / 'template.nupkg'
    receiver = root / 'receiver'
    entries = {}
    for relative in M.BUNDLE_FILES:
        text = 'namespace FableGameWorkspaceNamespace // %s\n' % relative if relative.endswith('Program.fs') else 'bytes of %s\n' % relative
        if relative.endswith('Studio.fsproj'):
            text = '<Project><PropertyGroup><FsGgSvgAuthoringVersion Condition="\'$(FsGgSvgAuthoringVersion)\' == \'\'">%s</FsGgSvgAuthoringVersion></PropertyGroup></Project>\n' % version
        entries[M.PREFIX + relative] = text
        target = receiver / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text.replace('FableGameWorkspaceNamespace', 'CurrentComposition'))
    nuspec = ('<package><metadata><id>%s</id><version>0.20.1</version><repository type="git" commit="%s"/></metadata></package>' %
              (M.TEMPLATE_ID, 'a' * 40))
    with ZipFile(archive, 'w') as package:
        package.writestr('FS.GG.Workspace.Template.nuspec', nuspec)
        for name, text in entries.items():
            package.writestr(name, text)
    plan['template']['sha256'] = sha(archive.read_bytes())
    plan['template']['descriptorSha256'] = sha(DESCRIPTOR)
    studio = receiver / 'SvgFoundation/Studio'
    cache = receiver / '.nuget/packages'
    lock = {'dependencies': {'net10.0': {}}}
    libraries = {}
    for row in plan['rendering']['packages']:
        lock['dependencies']['net10.0'][row['id']] = {'resolved': '0.32.4', 'contentHash': row['lockContentHash']}
        libraries[row['id'] + '/0.32.4'] = {'type': 'package'}
        folder = cache / row['id'].lower() / '0.32.4'
        folder.mkdir(parents=True)
        (folder / (row['id'].lower() + '.0.32.4.nupkg')).write_bytes(row['id'].encode())
        (folder / '.nupkg.metadata').write_text(json.dumps({'contentHash': row['lockContentHash']}))
    (studio / 'packages.lock.json').write_text(json.dumps(lock))
    (studio / 'obj').mkdir()
    (studio / 'obj/project.assets.json').write_text(json.dumps({'libraries': libraries, 'packageFolders': {str(cache): {}}}))
    (studio / 'dist/assets').mkdir(parents=True)
    (studio / 'dist/index.html').write_text('<html>Generated SVG scene studio</html>')
    (studio / 'dist/assets/app.js').write_text('studio();')
    return plan, archive, receiver


class Case(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='provider-studio-')
        self.addCleanup(self.tmp.cleanup)
        self.dir = Path(self.tmp.name)

    def custody(self):
        plan, archive, receiver = receiver_fixture(self.dir)
        return plan, archive, receiver, M.custody(receiver, plan, archive, DESCRIPTOR)

    def journey(self, mutant=None, served='match'):
        plan, archive, receiver, before = self.custody()
        work = self.dir / ('work-' + str(mutant).replace(' ', ''))
        work.mkdir()
        clock = Clock()
        model = Model(work, clock, mutant, before['studio']['distIndexSha256'] if served == 'match' else sha(b'other'))
        steps = M.run_steps(model, before, sleep=clock.sleep, clock=clock.monotonic)
        steps.append({'id': 'provider-custody-after', 'kind': 'provider', 'bound': sha(M.canonical(before).encode()), 'reaped': True})
        return before, steps, model

    def validate(self, before, steps, model, after=None):
        return M.validate_journey(steps, before, before if after is None else after, lambda a, b: model.speech_between(a, b))


class RealSpeechCalibration(Case):
    def test_every_expected_phrase_is_in_the_verbatim_real_orca_lines(self):
        checked = 0
        for step in M.STUDIO_STEPS:
            for phrase in step.get('speech', []):
                text = '\n'.join(row['text'].split('SPEECH OUTPUT:', 1)[1] for row in REAL[step['id']])
                self.assertIn(phrase, text, step['id'])
                checked += 1
        self.assertEqual(checked, 13)
        for step_id, rows in REAL.items():
            self.assertTrue(all('SPEECH OUTPUT:' in row['text'] for row in rows), step_id)


class GenuineJourney(Case):
    def test_genuine_journey_validates_in_order_with_every_step(self):
        before, steps, model = self.journey()
        self.assertEqual([r['id'] for r in steps], M.STEP_IDS)
        self.assertEqual(len(steps), 19)
        self.assertTrue(self.validate(before, steps, model))

    def test_speech_windows_are_fresh_and_ordered(self):
        before, steps, model = self.journey()
        windows = [(r['speech']['start'], r['speech']['end']) for r in steps if 'speech' in r]
        self.assertEqual(len(windows), 10)
        self.assertTrue(all(a[1] <= b[0] for a, b in zip(windows, windows[1:])))
        self.assertTrue(all(r['speech']['offsetBefore'] == r['speech']['start'] for r in steps if 'speech' in r))


class ProviderStepControls(Case):
    def test_a_missing_provider_step_refuses_each_of_the_five(self):
        before, steps, model = self.journey()
        refused = 0
        for name in M.PROVIDER_BEFORE + M.PROVIDER_AFTER:
            mutant = [r for r in steps if r['id'] != name]
            with self.assertRaisesRegex(ValueError, 'step population or order differs'):
                self.validate(before, mutant, model)
            refused += 1
        self.assertEqual(refused, 5)

    def test_a_missing_studio_step_a_reordering_and_a_duplicate_refuse(self):
        before, steps, model = self.journey()
        count = 0
        for step in M.STUDIO_STEPS:
            with self.assertRaises(ValueError):
                self.validate(before, [r for r in steps if r['id'] != step['id']], model)
            count += 1
        swapped = list(steps)
        swapped[5], swapped[6] = swapped[6], swapped[5]
        with self.assertRaises(ValueError):
            self.validate(before, swapped, model)
        with self.assertRaises(ValueError):
            self.validate(before, steps + [steps[0]], model)
        with self.assertRaises(ValueError):
            self.validate(before, steps[1:] + [steps[0]], model)
        self.assertEqual(count, 14)

    def test_provider_steps_must_equal_their_custody(self):
        before, steps, model = self.journey()
        for index, name in enumerate(M.PROVIDER_BEFORE + M.PROVIDER_AFTER):
            mutant = copy.deepcopy(steps)
            row = next(r for r in mutant if r['id'] == name)
            row['bound'] = '0' * 64
            with self.assertRaises(ValueError, msg=name):
                self.validate(before, mutant, model)

    def test_served_bytes_must_equal_the_receiver_dist(self):
        before, steps, model = self.journey(served='other')
        with self.assertRaisesRegex(ValueError, 'served Studio bytes differ'):
            self.validate(before, steps, model)

    def test_custody_drift_or_unreaped_server_refuses(self):
        before, steps, model = self.journey()
        drifted = copy.deepcopy(before)
        drifted['studio']['lockSha256'] = '1' * 64
        with self.assertRaisesRegex(ValueError, 'custody changed'):
            self.validate(before, steps, model, drifted)
        mutant = copy.deepcopy(steps)
        mutant[-1]['reaped'] = False
        with self.assertRaisesRegex(ValueError, 'unbound'):
            self.validate(before, mutant, model)


class CausalControls(Case):
    """The recorded journey and the live runner both refuse acausal speech and focus."""

    def test_speech_present_only_before_the_action_refuses_every_speech_step(self):
        refused = 0
        for step in M.STUDIO_STEPS:
            if not step.get('speech'):
                continue
            with self.assertRaises((ValueError, RuntimeError), msg=step['id']):
                self.journey(('early', step['id']))
            refused += 1
        self.assertEqual(refused, 10)

    def test_silent_action_refuses_every_speech_step(self):
        refused = 0
        for step in M.STUDIO_STEPS:
            if not step.get('speech'):
                continue
            with self.assertRaises(ValueError, msg=step['id']):
                self.journey(('silent', step['id']))
            refused += 1
        self.assertEqual(refused, 10)

    def test_recorded_window_that_ends_before_the_speech_or_starts_late_refuses(self):
        before, steps, model = self.journey()
        row = next(r for r in steps if r['id'] == 'create-rectangle')
        for change in [('start', row['speech']['end'] - 1), ('end', row['speech']['start'] + 1), ('offsetBefore', row['speech']['start'] - 1)]:
            mutant = copy.deepcopy(steps)
            target = next(r for r in mutant if r['id'] == 'create-rectangle')
            target['speech'][change[0]] = change[1]
            with self.assertRaises(ValueError, msg=change[0]):
                self.validate(before, mutant, model)

    def test_overlapping_or_replayed_windows_refuse(self):
        before, steps, model = self.journey()
        mutant = copy.deepcopy(steps)
        a = next(r for r in mutant if r['id'] == 'edit-scene-properties')
        b = next(r for r in mutant if r['id'] == 'create-rectangle')
        a['speech'].update(b['speech'])
        with self.assertRaises(ValueError):
            self.validate(before, mutant, model)

    def test_key_events_must_be_trusted_counted_and_after_the_pre_sample(self):
        with self.assertRaises(ValueError):
            self.journey('keys-lost')
        before, steps, model = self.journey('no-key-events')
        with self.assertRaises(ValueError):
            self.validate(before, steps, model)
        before, steps, model = self.journey('untrusted-key')
        with self.assertRaisesRegex(ValueError, 'trusted key events'):
            self.validate(before, steps, model)
        before, steps, model = self.journey()
        mutant = copy.deepcopy(steps)
        next(r for r in mutant if r['id'] == 'escape-restores-scene-focus')['keys'] = []
        with self.assertRaises(ValueError):
            self.validate(before, mutant, model)
        mutant = copy.deepcopy(steps)
        next(r for r in mutant if r['id'] == 'edit-scene-properties')['keys'] = ['Return']
        with self.assertRaises(ValueError):
            self.validate(before, mutant, model)
        mutant = copy.deepcopy(steps)
        row = next(r for r in mutant if r['id'] == 'tab-to-rectangle')
        row['domBefore']['keysTotal'] -= 1
        with self.assertRaisesRegex(ValueError, 'counter disagrees'):
            self.validate(before, mutant, model)

    def test_a_stale_post_action_browser_sample_refuses(self):
        with self.assertRaises(ValueError):
            self.journey('stale-dom')
        before, steps, model = self.journey()
        mutant = copy.deepcopy(steps)
        row = next(r for r in mutant if r['id'] == 'open-command-palette')
        row['domAfter']['sampleSequence'] = row['domBefore']['sampleSequence']
        with self.assertRaisesRegex(ValueError, 'not after the action'):
            self.validate(before, mutant, model)

    def test_focus_must_move_land_on_the_control_and_be_at_spi_focused(self):
        for mutant in ['focus-not-restored', 'document-unfocused']:
            with self.assertRaises(ValueError, msg=mutant):
                self.journey(mutant)
        before, steps, model = self.journey()
        cases = 0
        for step_id in ['tab-to-rectangle', 'tab-to-command-palette', 'open-command-palette', 'escape-restores-scene-focus']:
            same = copy.deepcopy(steps)
            row = next(r for r in same if r['id'] == step_id)
            row['domBefore']['active'] = dict(row['domAfter']['active'])
            with self.assertRaisesRegex(ValueError, 'focus did not change', msg=step_id):
                self.validate(before, same, model)
            wrong = copy.deepcopy(steps)
            next(r for r in wrong if r['id'] == step_id)['domAfter']['active'] = {'id': 'x', 'role': 'button', 'ariaLabel': 'Other', 'text': 'Other'}
            with self.assertRaisesRegex(ValueError, 'focus not on the expected control', msg=step_id):
                self.validate(before, wrong, model)
            gone = copy.deepcopy(steps)
            next(r for r in gone if r['id'] == step_id)['focus']['atspi'] = []
            with self.assertRaisesRegex(ValueError, 'focus not on the expected control', msg=step_id):
                self.validate(before, gone, model)
            cases += 3
        self.assertEqual(cases, 12)

    def test_removal_must_follow_presence(self):
        before, steps, model = self.journey()
        mutant = copy.deepcopy(steps)
        next(r for r in mutant if r['id'] == 'escape-restores-scene-focus')['tree']['absentWasPresentBefore'] = [False]
        with self.assertRaisesRegex(ValueError, 'not present before'):
            self.validate(before, mutant, model)

    def test_atspi_action_refusal_is_reported_not_swallowed(self):
        with self.assertRaises(RuntimeError):
            self.journey('action-refused')


class CustodyControls(Case):
    def test_genuine_custody_binds_every_provider_fact(self):
        plan, archive, receiver, custody = self.custody()
        self.assertEqual(custody['provider']['descriptorSha256'], plan['template']['descriptorSha256'])
        self.assertEqual(len(custody['bundle']['files']), 9)
        self.assertEqual(len(custody['studio']['packages']), 3)
        self.assertEqual(custody['studio']['distFiles'], 2)
        self.assertEqual(M.canonical(custody), M.canonical(M.custody(receiver, plan, archive, DESCRIPTOR)))

    def refuses(self, mutate, message=None, descriptor=DESCRIPTOR):
        plan, archive, receiver = receiver_fixture(self.dir)
        mutate(plan, archive, receiver)
        with self.assertRaises((ValueError, KeyError, FileNotFoundError, json.JSONDecodeError), msg=message):
            M.custody(receiver, plan, archive, descriptor)

    def test_single_field_provider_mutants_refuse(self):
        mutants = {
            'plan archive digest': lambda p, a, r: p['template'].update(sha256='0' * 64),
            'plan version': lambda p, a, r: p['template'].update(version='0.20.0'),
            'plan source commit': lambda p, a, r: p['template'].update(sourceCommit='f' * 40),
            'plan descriptor digest': lambda p, a, r: p['template'].update(descriptorSha256='0' * 64),
            'other bundle': lambda p, a, r: p['selection'].update(bundle='studio'),
            'other lifecycle': lambda p, a, r: p['selection'].update(lifecycle='typed-sdd'),
            'other route': lambda p, a, r: p['selection'].update(route='provider'),
            'other product name': lambda p, a, r: p['selection'].update(productName='Other'),
        }
        for relative in M.BUNDLE_FILES:
            mutants['bundle file ' + relative] = (lambda rel: lambda p, a, r: (r / rel).write_text('tampered\n'))(relative)
        for relative in M.LIFECYCLE_NONE_ABSENT:
            def add(p, a, r, relative=relative):
                (r / relative).parent.mkdir(exist_ok=True)
                (r / relative).write_text('x')
            mutants['lifecycle file ' + relative] = add
        for name, mutate in mutants.items():
            with self.subTest(name):
                self.refuses(mutate, name)
        self.assertEqual(len(mutants), 20)

    def test_descriptor_mutants_refuse(self):
        plan, archive, receiver = receiver_fixture(self.dir)
        for name, raw in {'wrong bytes': DESCRIPTOR + b'#', 'no bundle parameter': DESCRIPTOR.replace(b'      - key: bundle\n', b''),
                          'no lifecycle parameter': DESCRIPTOR.replace(b'      - key: lifecycle\n', b''),
                          'other template': DESCRIPTOR.replace(b'fs-gg-fable-game', b'fs-gg-web')}.items():
            with self.subTest(name):
                other = copy.deepcopy(plan)
                other['template']['descriptorSha256'] = sha(raw) if name != 'wrong bytes' else plan['template']['descriptorSha256']
                with self.assertRaises(ValueError):
                    M.custody(receiver, other, archive, raw)
        with self.assertRaises(ValueError):
            M.fetch_descriptor('main', lambda url: b'')
        self.assertTrue(M.fetch_descriptor('a' * 40, lambda url: url.encode()).startswith(b'https://raw.githubusercontent.com/FS-GG/FS.GG.Templates/' + b'a' * 40))

    def test_studio_package_mutants_refuse_including_the_real_0_32_3_default(self):
        mutants = {
            'stale 0.32.3 Studio default (published template 0.20.0)': lambda p, a, r: (
                (r / 'SvgFoundation/Studio/Studio.fsproj').write_text((r / 'SvgFoundation/Studio/Studio.fsproj').read_text().replace('0.32.4', '0.32.3'))),
            'lock resolved version': lambda p, a, r: self.edit_json(r / 'SvgFoundation/Studio/packages.lock.json',
                                                                   lambda v: v['dependencies']['net10.0']['FS.GG.UI.Scene'].update(resolved='0.32.3')),
            'lock content hash': lambda p, a, r: self.edit_json(r / 'SvgFoundation/Studio/packages.lock.json',
                                                               lambda v: v['dependencies']['net10.0']['FS.GG.UI.KeyboardInput'].update(contentHash='x')),
            'project-backed package': lambda p, a, r: self.edit_json(r / 'SvgFoundation/Studio/obj/project.assets.json',
                                                                    lambda v: v['libraries']['FS.GG.UI.Scene/0.32.4'].update(type='project')),
            'foreign package folder': lambda p, a, r: self.edit_json(r / 'SvgFoundation/Studio/obj/project.assets.json',
                                                                    lambda v: v.update(packageFolders={'/tmp/elsewhere': {}})),
            'cached archive bytes': lambda p, a, r: (r / '.nuget/packages/fs.gg.ui.scene/0.32.4/fs.gg.ui.scene.0.32.4.nupkg').write_bytes(b'other'),
            'cache metadata hash': lambda p, a, r: (r / '.nuget/packages/fs.gg.ui.scene/0.32.4/.nupkg.metadata').write_text('{"contentHash":"x"}'),
            'plan package digest': lambda p, a, r: p['rendering']['packages'][0].update(sha256='0' * 64),
            'plan package population': lambda p, a, r: p['rendering']['packages'].pop(),
            'plan rendering version': lambda p, a, r: p['rendering'].update(version='0.32.5'),
            'dist absent': lambda p, a, r: __import__('shutil').rmtree(r / 'SvgFoundation/Studio/dist'),
            'dist index absent': lambda p, a, r: (r / 'SvgFoundation/Studio/dist/index.html').unlink(),
            'dist symlink member': lambda p, a, r: (r / 'SvgFoundation/Studio/dist/link.js').symlink_to('/etc/hostname'),
        }
        for name, mutate in mutants.items():
            with self.subTest(name):
                self.refuses(mutate, name)
        self.assertEqual(len(mutants), 13)

    @staticmethod
    def edit_json(path, change):
        value = json.loads(path.read_text())
        change(value)
        path.write_text(json.dumps(value))

    def test_dist_change_changes_custody(self):
        plan, archive, receiver, before = self.custody()
        (receiver / 'SvgFoundation/Studio/dist/assets/app.js').write_text('changed();')
        after = M.custody(receiver, plan, archive, DESCRIPTOR)
        self.assertNotEqual(before['studio']['distManifestSha256'], after['studio']['distManifestSha256'])
        self.assertEqual(before['studio']['distIndexSha256'], after['studio']['distIndexSha256'])


class ReceiptAndRun(Case):
    def run_fixture(self, mutate=None):
        plan, archive, receiver = receiver_fixture(self.dir)
        root = Path(tempfile.mkdtemp(dir=self.dir)) / 'run'
        (root / 'external-reference/orca').mkdir(parents=True)
        shutil_copy_tree(receiver, root / 'external-reference/complete')
        moved = root / 'external-reference/complete'
        assets = moved / 'SvgFoundation/Studio/obj/project.assets.json'
        value = json.loads(assets.read_text())
        value['packageFolders'] = {str(moved / '.nuget/packages'): {}}
        assets.write_text(json.dumps(value))
        (root / 'current-public-template.nupkg').write_bytes(archive.read_bytes())
        (root / 'current-composition-plan.json').write_text(json.dumps(plan))
        preflight = {'requestedPhase': 'full', 'atJourney': O.LOCAL_SAVE_JOURNEY, 'renderingInputSource': 'current-public-composition',
                     'templates': {'revision': 'a' * 40, 'tree': 'b' * 40}, 'caller': {'repository': 'FS-GG/FS.GG.Rendering', 'revision': '3' * 40, 'run': '1', 'attempt': '1'},
                     'producer': {'revision': 'b' * 40, 'custodySha256': 'c' * 64}}
        (root / 'external-reference-preflight.json').write_text(json.dumps(preflight))
        local = {'result': 'passed', 'currentPublicAt': {'controller': preflight['templates'], 'journey': O.LOCAL_SAVE_JOURNEY}}
        (root / 'external-reference/orca/observation.json').write_text(json.dumps(local))
        served = sha((root / 'external-reference/complete/SvgFoundation/Studio/dist/index.html').read_bytes())

        def session(out, flight, before):
            clock = Clock()
            model = Model(out, clock, None, served)
            steps = M.run_steps(model, before, sleep=clock.sleep, clock=clock.monotonic)
            (out / 'journey.json').write_text(json.dumps({'process': {'name': 'orca', 'pid': 41}, 'browser': {'family': 'chromium', 'pid': 42},
                                                           'orcaVersion': '46.1', 'steps': steps}))
            (out / 'browser-dom.json').write_text(json.dumps(model.dom()))

        return root, preflight, session

    def go(self, root, session, guard=lambda env: None):
        # The owned server is a real child here; patch Popen to avoid a listener in the inert controls.
        import subprocess
        real = subprocess.Popen

        class Fake:
            def __init__(self, *a, **k):
                self.code = -15

            def send_signal(self, sig):
                pass

            def wait(self, timeout=None):
                return self.code
        subprocess.Popen = Fake
        try:
            return M.run(root, {}, session, lambda url: DESCRIPTOR, guard=guard)
        finally:
            subprocess.Popen = real

    def test_held_run_refuses_before_any_effect_and_the_gate_stays_none(self):
        self.assertIsNone(O.CURRENT_PUBLIC_AT_ADMISSION)
        root, preflight, session = self.run_fixture()
        for environment in [{}, {'FSGG_CURRENT_PUBLIC_AT_ADMISSION': 'anything'}, {'FSGG_CURRENT_PUBLIC_AT_ADMISSION': 'inert-control-only'}]:
            with self.assertRaisesRegex(RuntimeError, 'current public AT held'):
                M.run(root, environment, session, lambda url: DESCRIPTOR)
            self.assertFalse((root / 'provider-studio').exists())
        text = (HERE / 'current-reference-provider-studio.py').read_text()
        self.assertNotIn('CURRENT_PUBLIC_AT_ADMISSION =', text)
        self.assertEqual(len(re.findall(r'^CURRENT_PUBLIC_AT_ADMISSION = None$', (HERE / 'external-reference-orca.py').read_text(), re.M)), 1)

    def test_genuine_run_writes_a_receipt_that_revalidates_with_provider_matrix_acceptance(self):
        root, preflight, session = self.run_fixture()
        receipt = self.go(root, session)
        self.assertIs(receipt['providerMatrixAcceptance'], True)
        self.assertIs(receipt['whole4817Acceptance'], False)
        self.assertIs(receipt['nativeImeAcceptance'], False)
        stored = json.loads((root / 'provider-studio/receipt.json').read_text())
        local_path = root / 'external-reference/orca/observation.json'
        local = json.loads(local_path.read_text())
        local['_sha256'] = M.sha256_file(local_path)
        plan = json.loads((root / 'current-composition-plan.json').read_text())
        self.assertTrue(M.validate_receipt(stored, plan, preflight, root / 'provider-studio', local))
        self.assertEqual(len(stored['steps']), 19)
        self.assertEqual(stored['matrix']['cells'], stored['matrix']['observed'])

    def mutate_receipt(self, change, expect):
        root, preflight, session = self.run_fixture()
        self.go(root, session)
        out = root / 'provider-studio'
        receipt = json.loads((out / 'receipt.json').read_text())
        local_path = root / 'external-reference/orca/observation.json'
        local = json.loads(local_path.read_text())
        local['_sha256'] = M.sha256_file(local_path)
        plan = json.loads((root / 'current-composition-plan.json').read_text())
        change(receipt, local, preflight, plan, out)
        with self.assertRaisesRegex(ValueError, expect):
            M.validate_receipt(receipt, plan, preflight, out, local)

    @staticmethod
    def unreaped(receipt, local, preflight, plan, out):
        (out / 'server.json').write_text(json.dumps({'signal': 'SIGTERM', 'exit': 0, 'reaped': True}))
        receipt['evidenceSha256']['server.json'] = M.sha256_file(out / 'server.json')

    def test_receipt_level_controls(self):
        cases = {
            'matrix cell unobserved': (lambda r, l, f, p, o: r['matrix'].update(observed=[]), 'matrix cell'),
            'provider matrix false': (lambda r, l, f, p, o: r.update(providerMatrixAcceptance=False), 'acceptance flags'),
            'ime overclaim': (lambda r, l, f, p, o: r.update(nativeImeAcceptance=True), 'acceptance flags'),
            'whole overclaim': (lambda r, l, f, p, o: r.update(whole4817Acceptance=True), 'acceptance flags'),
            'audio claim': (lambda r, l, f, p, o: r.update(physicalAudioHardware='observed'), 'AT boundary'),
            'orca version': (lambda r, l, f, p, o: r.update(orcaVersion='45.0'), 'AT boundary'),
            'foreign templates': (lambda r, l, f, p, o: r.update(templates={'revision': 'e' * 40, 'tree': None}), 'preflight'),
            'foreign caller': (lambda r, l, f, p, o: r['caller'].update(run='9'), 'preflight'),
            'local save failed': (lambda r, l, f, p, o: l.update(result='failed'), 'local-save'),
            'local save other controller': (lambda r, l, f, p, o: l['currentPublicAt'].update(controller={'revision': 'f' * 40, 'tree': None}), 'local-save'),
            'local join digest': (lambda r, l, f, p, o: r['localSaveJoin'].update(observationSha256='0' * 64), 'local-save'),
            'evidence hash': (lambda r, l, f, p, o: r['evidenceSha256'].update({'custody-before.json': '0' * 64}), 'hash mismatch'),
            'evidence unbound': (lambda r, l, f, p, o: r['evidenceSha256'].pop('server.json'), 'unbound'),
            'steps differ from original': (lambda r, l, f, p, o: r['steps'].pop(), 'differ from the original'),
            'server not reaped': (self.unreaped, 'reaped'),
            'plan selection differs': (lambda r, l, f, p, o: p['selection'].update(bundle='studio'), 'typed plan'),
        }
        for name, (change, expect) in cases.items():
            with self.subTest(name):
                self.mutate_receipt(change, expect)
        self.assertEqual(len(cases), 16)

    def test_missing_local_save_observation_stops_the_run_before_effects(self):
        root, preflight, session = self.run_fixture()
        (root / 'external-reference/orca/observation.json').unlink()
        with self.assertRaises(FileNotFoundError):
            self.go(root, session)
        self.assertFalse((root / 'provider-studio').exists())


def shutil_copy_tree(source, destination):
    import shutil
    shutil.copytree(source, destination, symlinks=True)


class WorkflowAndShell(Case):
    workflow_path = HERE.parents[2] / '.github/workflows/fable-external-reference-source.yml'

    def test_workflow_registration_guard_and_mutants(self):
        text = self.workflow_path.read_text()
        self.assertTrue(M.workflow_guard(text))
        mutants = {
            'step removed': text.replace('      - name: Observe provider/Studio Orca journey\n', '      - name: Something else\n'),
            'unconditional': re.sub(r"(      - name: Observe provider/Studio Orca journey\n)        if: .*\n", r'\1', text),
            'wrong branch': text.replace("      - name: Observe provider/Studio Orca journey\n        if: ${{ !inputs.preflight-only && inputs.rendering-input-source == 'current-public-composition' }}",
                                         "      - name: Observe provider/Studio Orca journey\n        if: ${{ !inputs.preflight-only }}"),
            'entry differs': text.replace('current-reference-provider-studio.py run "$RUNNER_TEMP"', 'true'),
            'evidence omitted': text.replace('${{ runner.temp }}/provider-studio/**', '${{ runner.temp }}/other/**'),
            'tests dropped from both paths': text.replace('python3 -I -B tests/composition/fable-game/test-current-reference-provider-studio.py', 'true'),
            'tests dropped once': text.replace('python3 -I -B tests/composition/fable-game/test-current-reference-provider-studio.py', 'true', 1),
            'path unwatched': text.replace("      - 'tests/composition/fable-game/current-reference-provider-studio.py'\n", ''),
        }
        for name, bad in mutants.items():
            with self.subTest(name):
                self.assertNotEqual(bad, text)
                with self.assertRaises(ValueError):
                    M.workflow_guard(bad)
        moved = text.replace('      - name: Observe provider/Studio Orca journey\n', '      - name: Observe provider/Studio Orca journey\n', 1)
        before_local = text.index('      - name: Observe actual external reference Orca journey')
        marker = text.index('      - name: Observe provider/Studio Orca journey')
        self.assertLess(before_local, marker)
        self.assertEqual(len(mutants), 8)

    def test_shell_allow_list_and_static_syntax(self):
        import subprocess
        shell = HERE / 'observe-svg-input-orca.sh'
        self.assertEqual(subprocess.run(['bash', '-n', str(shell)]).returncode, 0)
        text = shell.read_text()
        self.assertIn('svg-input-orca.py|provider-studio-orca.py', text)
        self.assertIn('orca-playwright-browser.cjs|provider-studio-browser.cjs', text)
        head = text.split('export NO_AT_BRIDGE=0', 1)[0]
        head = head.replace('exec dbus-run-session -- env SVG_ORCA_INNER=1 xvfb-run -a bash "$0" "$address" "$output"', 'true')
        probe = self.dir / 'probe.sh'
        probe.write_text(head + '\ntrue\n')
        for variable, value in [('SVG_ORCA_JOURNEY', 'other.py'), ('SVG_ORCA_JOURNEY', '../x.py'), ('SVG_ORCA_BROWSER_SCRIPT', 'other.cjs')]:
            result = subprocess.run(['bash', str(probe), 'addr', 'out'], env={'PATH': '/usr/bin:/bin', variable: value, 'SVG_ORCA_INNER': '1'},
                                    capture_output=True, text=True)
            self.assertEqual(result.returncode, 2, (variable, value, result.stderr))
        ok = subprocess.run(['bash', str(probe), 'addr', 'out'], env={'PATH': '/usr/bin:/bin', 'SVG_ORCA_JOURNEY': 'provider-studio-orca.py',
                            'SVG_ORCA_BROWSER_SCRIPT': 'provider-studio-browser.cjs', 'SVG_ORCA_INNER': '1'}, capture_output=True, text=True)
        self.assertEqual(ok.returncode, 0, ok.stderr)
        self.assertNotIn('hash', ok.stderr)

    def test_driver_and_companion_are_syntactically_valid_and_default_journey_is_unchanged(self):
        import ast
        ast.parse((HERE / 'provider-studio-orca.py').read_text())
        text = (HERE / 'observe-svg-input-orca.sh').read_text()
        self.assertIn('${SVG_ORCA_JOURNEY:-svg-input-orca.py}', text)
        self.assertIn('${SVG_ORCA_BROWSER_SCRIPT:-orca-playwright-browser.cjs}', text)
        companion = (HERE / 'provider-studio-browser.cjs').read_text()
        self.assertIn('trusted: event.isTrusted === true', companion)
        self.assertIn('keysTotal', companion)


if __name__ == '__main__':
    unittest.main(verbosity=1)
