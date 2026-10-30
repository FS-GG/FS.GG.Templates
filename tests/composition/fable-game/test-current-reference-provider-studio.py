#!/usr/bin/env python3
"""Inert controls for the provider/Studio journey producer.

No gi import, Orca, browser, SDK, network or AT operation. A tiny independent model of the Studio and of
Orca's debug log stands in for the live primitives; its speech lines are the verbatim lines of a real
Orca 46.1 run (fixtures/provider-studio-orca-speech.json), so the expected phrases are calibrated on real
output rather than invented. Native execution stays behind CURRENT_PUBLIC_AT_ADMISSION.

Every refusal below goes through `kill(name, action)`: a named mutant of the model, the recorded journey, the
receiver, the receipt or the run. Names are unique, so the final count is the number of distinct mutants killed.
"""
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import subprocess
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
KILLED = {}
REFUSALS = (ValueError, RuntimeError, KeyError, FileNotFoundError, json.JSONDecodeError, subprocess.TimeoutExpired)


class Clock:
    def __init__(self):
        self.now = 0.0

    def monotonic(self):
        return self.now

    def sleep(self, seconds):
        self.now += seconds


class Model:
    """Independent model of the Studio, its keyboard focus and Orca's debug log. Not an AT client."""

    def __init__(self, directory, mutant=None, served=None):
        self.log = Path(directory) / 'orca-debug.log'
        self.log.write_bytes(b'09:38:14.000000 - DEBUG filler before any action\n' * 3)
        self.mutant, self.served = mutant, served
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
                    'focus': [], 'keys': [dict(k) for k in self.keys], 'keysTotal': self.total}}

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
                if self.mutant != 'palette-never-opens':
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
        if name == 'Close workspace overlay' and self.mutant != 'close-noop':
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


def receiver_fixture(root, studio_fsproj=None):
    """A tiny synthetic template archive plus the receiver the template would generate from it.

    `studio_fsproj` substitutes the real published Studio.fsproj in BOTH archive and receiver, so the bundle stays
    self-consistent and only the package checks can see a difference."""
    root = Path(tempfile.mkdtemp(dir=root))
    plan = plan_fixture()
    archive = root / 'template.nupkg'
    receiver = root / 'receiver'
    entries = {}
    for relative in M.BUNDLE_FILES:
        text = 'namespace FableGameWorkspaceNamespace // %s\n' % relative if relative.endswith('Program.fs') else 'bytes of %s\n' % relative
        if relative.endswith('Studio.fsproj'):
            text = studio_fsproj if studio_fsproj is not None else (HERE / 'fixtures/studio-0.20.1.fsproj').read_text()
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


class Journey:
    """A genuine (or mutated-model) run plus everything a validator needs."""

    def __init__(self, case, mutant=None, served='match', wait_tree=True):
        self.plan, self.archive, self.receiver = receiver_fixture(case.dir)
        self.before = M.custody(self.receiver, self.plan, self.archive, DESCRIPTOR)
        work = Path(tempfile.mkdtemp(dir=case.dir))
        clock = Clock()
        self.model = Model(work, mutant, self.before['studio']['distIndexSha256'] if served == 'match' else sha(b'other'))
        self.steps = M.run_steps(self.model, self.before, sleep=clock.sleep, clock=clock.monotonic, wait_tree=wait_tree)
        self.steps.append({'id': 'provider-custody-after', 'kind': 'provider', 'bound': sha(M.canonical(self.before).encode()), 'reaped': True})
        self.final = self.model.dom()

    def read(self, start, end):
        return self.model.speech_between(start, end)

    def validate(self, steps=None, after=None, final=None, before=None):
        return M.validate_journey(self.steps if steps is None else steps, self.before if before is None else before,
                                  self.before if after is None else after, self.read, self.final if final is None else final)

    def mutated(self):
        return copy.deepcopy(self.steps), copy.deepcopy(self.final)

    def step(self, steps, step_id):
        return next(r for r in steps if r['id'] == step_id)

    def primed(self, upto):
        """The validation state a step sees: every earlier genuine step validated in order."""
        state = M.new_state()
        by_id = {r['id']: r for r in self.steps}
        for step in M.STUDIO_STEPS:
            if step['id'] == upto:
                return step, state
            M.validate_studio_step(step, by_id[step['id']], state, self.read)
        raise KeyError(upto)


class Case(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='provider-studio-')
        self.addCleanup(self.tmp.cleanup)
        self.dir = Path(self.tmp.name)

    def kill(self, name, action, expect=None):
        """Assert that one named mutant is refused; the name must be unique across the whole suite."""
        self.assertNotIn(name, KILLED, 'duplicate mutant name: ' + name)
        with self.assertRaises(REFUSALS, msg=name) as caught:
            action()
        if expect is not None:
            self.assertRegex(str(caught.exception), expect, name)
        KILLED[name] = str(caught.exception)[:90]

    def step_mutant(self, journey, name, step_id, change, expect, final=None):
        """Mutate one recorded step and validate it in the exact state its predecessors leave."""
        step, state = journey.primed(step_id)
        record = copy.deepcopy(next(r for r in journey.steps if r['id'] == step_id))
        change(record)
        self.kill(name, lambda: M.validate_studio_step(step, record, state, journey.read), expect)


FOCUS_STEPS = ['tab-to-rectangle', 'tab-to-command-palette', 'open-command-palette', 'escape-restores-scene-focus']
SPEECH_STEPS = [s['id'] for s in M.STUDIO_STEPS if s.get('speech')]


class RealSpeechCalibration(Case):
    def test_every_expected_phrase_is_in_the_verbatim_real_orca_lines(self):
        checked = 0
        for step in M.STUDIO_STEPS:
            for phrase in step.get('speech', []):
                text = '\n'.join(row['text'].split('SPEECH OUTPUT:', 1)[1] for row in REAL[step['id']])
                self.assertIn(phrase, text, step['id'])
                checked += 1
        self.assertEqual(checked, 13)
        self.assertEqual(len(SPEECH_STEPS), 10)


class GenuineJourney(Case):
    def test_genuine_journey_validates_with_every_step_and_ordered_disjoint_windows(self):
        journey = Journey(self)
        self.assertEqual([r['id'] for r in journey.steps], M.STEP_IDS)
        self.assertEqual(len(journey.steps), 19)
        self.assertTrue(journey.validate())
        windows = [(r['speech']['start'], r['speech']['end']) for r in journey.steps if 'speech' in r]
        self.assertEqual(len(windows), 10)
        self.assertTrue(all(a[1] <= b[0] for a, b in zip(windows, windows[1:])))

    def test_tab_steps_record_one_row_per_hop(self):
        journey = Journey(self)
        self.assertEqual([h['target'] for h in journey.step(journey.steps, 'tab-to-command-palette')['hops']],
                         ['Replay timeline', 'Replay complete arena recording', 'Command palette'])
        self.assertEqual([h['target'] for h in journey.step(journey.steps, 'tab-to-rectangle')['hops']], ['Rectangle'])


class StepPopulation(Case):
    def test_missing_extra_reordered_and_unbound_steps(self):
        journey = Journey(self)
        for name in M.PROVIDER_BEFORE + M.PROVIDER_AFTER:
            self.kill('missing provider step ' + name, lambda name=name: journey.validate([r for r in journey.steps if r['id'] != name]),
                      'population or order')
        for step in M.STUDIO_STEPS:
            self.kill('missing studio step ' + step['id'], lambda step=step: journey.validate([r for r in journey.steps if r['id'] != step['id']]),
                      'population or order')
        swapped = list(journey.steps)
        swapped[5], swapped[6] = swapped[6], swapped[5]
        self.kill('reordered steps', lambda: journey.validate(swapped), 'population or order')
        self.kill('duplicated step', lambda: journey.validate(journey.steps + [journey.steps[0]]), 'population or order')
        self.kill('rotated steps', lambda: journey.validate(journey.steps[1:] + [journey.steps[0]]), 'population or order')
        for name in M.PROVIDER_BEFORE + M.PROVIDER_AFTER:
            def tamper(name=name):
                steps, _ = journey.mutated()
                journey.step(steps, name)['bound'] = '0' * 64
                journey.validate(steps)
            self.kill('provider step unbound from custody ' + name, tamper, 'custody|unbound')

    def test_served_bytes_drift_and_unreaped_server(self):
        self.kill('served bytes differ from dist', lambda: Journey(self, served='other').validate(), 'served Studio bytes')
        journey = Journey(self)
        drifted = copy.deepcopy(journey.before)
        drifted['studio']['lockSha256'] = '1' * 64
        self.kill('custody drift during journey', lambda: journey.validate(after=drifted), 'custody changed')
        steps, _ = journey.mutated()
        journey.step(steps, 'provider-custody-after')['reaped'] = False
        self.kill('after-step not reaped', lambda: journey.validate(steps), 'unbound')


class SpeechCausality(Case):
    def test_runner_refuses_acausal_or_absent_speech(self):
        for step_id in SPEECH_STEPS:
            self.kill('speech only before the action ' + step_id, lambda step_id=step_id: Journey(self, ('early', step_id)))
            self.kill('silent action ' + step_id, lambda step_id=step_id: Journey(self, ('silent', step_id)))

    def test_recorded_windows(self):
        journey = Journey(self)
        base = journey.step(journey.steps, 'create-rectangle')['speech']
        for field, value in [('start', base['end'] - 1), ('end', base['start'] + 1), ('offsetBefore', base['start'] - 1)]:
            def tamper(field=field, value=value):
                steps, _ = journey.mutated()
                journey.step(steps, 'create-rectangle')['speech'][field] = value
                journey.validate(steps)
            self.kill('recorded window %s moved' % field, tamper, 'fresh window|speech absent')

        def overlap_with_generic_phrase():
            # B reuses A's window start: 'Command palette' is spoken in both, so only the ordering rule can refuse it.
            steps, _ = journey.mutated()
            a = journey.step(steps, 'tab-to-command-palette')['speech']
            b = journey.step(steps, 'open-command-palette')['speech']
            b['start'] = b['offsetBefore'] = a['start']
            journey.validate(steps)
        self.kill('genuine overlapping window reusing a generic phrase', overlap_with_generic_phrase, 'fresh window')

        def phrase_missing_in_ordered_window():
            steps, _ = journey.mutated()
            previous = journey.step(steps, 'tab-to-rectangle')['speech']
            row = journey.step(steps, 'create-rectangle')['speech']
            row['start'] = row['offsetBefore'] = previous['end']
            row['end'] = previous['end'] + 1
            journey.validate(steps)
        self.kill('ordered window without the phrase', phrase_missing_in_ordered_window, 'speech absent')

        def silent_step_with_window():
            steps, _ = journey.mutated()
            journey.step(steps, 'escape-restores-scene-focus')['speech'] = {'expect': [], 'offsetBefore': 0, 'start': 0, 'end': 1}
            journey.validate(steps)
        self.kill('silent step carries a window', silent_step_with_window, 'silent step')


class KeyEvidence(Case):
    def test_runner_and_model_mutants(self):
        self.kill('keys never delivered', lambda: Journey(self, 'keys-lost'))
        self.kill('no key events counted', lambda: Journey(self, 'no-key-events').validate(), 'Tab hops differ|counter delta')
        self.kill('every key untrusted', lambda: Journey(self, 'untrusted-key').validate(), 'trusted key events')

    def consistent(self, journey, step_id, change_event):
        """Change one event in the record AND the retained sample, so only the step's own rule can see it."""
        steps, final = journey.mutated()
        record = journey.step(steps, step_id)
        for event in record['keyEvents']:
            change_event(event)
            for row in final['observation']['keys']:
                if row['n'] == event['n']:
                    change_event(row)
        return steps, final

    def test_isolated_key_rules(self):
        journey = Journey(self)
        steps, final = self.consistent(journey, 'tab-to-rectangle', lambda e: e.update(trusted=False))
        self.kill('Tab step with untrusted keys', lambda: journey.validate(steps, final=final), 'Tab navigation lacks trusted')
        steps, final = self.consistent(journey, 'create-rectangle', lambda e: e.update(trusted=False))
        self.kill('Enter step with untrusted key', lambda: journey.validate(steps, final=final), 'expected trusted key events')
        steps, final = self.consistent(journey, 'create-rectangle', lambda e: e.update(key='Return'))
        self.kill('domKeys equality (xdotool name instead of event.key)', lambda: journey.validate(steps, final=final), 'expected trusted key events')
        steps, final = self.consistent(journey, 'escape-restores-scene-focus', lambda e: e.update(key='Enter'))
        self.kill('Escape step reported as Enter', lambda: journey.validate(steps, final=final), 'expected trusted key events')
        steps, final = self.consistent(journey, 'tab-to-rectangle', lambda e: e.update(key='ArrowDown'))
        self.kill('Tab step with a non-Tab key', lambda: journey.validate(steps, final=final), 'Tab navigation lacks trusted')

    def test_self_asserted_evidence_is_crosschecked_against_the_retained_sample(self):
        journey = Journey(self)
        steps, final = journey.mutated()
        final['observation']['keys'] = [k for k in final['observation']['keys'] if k['n'] != 2]
        self.kill('recorded event absent from retained sample', lambda: journey.validate(steps, final=final), 'not in the retained')
        steps, final = journey.mutated()
        for row in final['observation']['keys']:
            if row['n'] == 3:
                row['trusted'] = False
        self.kill('record claims trusted, retained sample says untrusted', lambda: journey.validate(steps, final=final), 'not in the retained')
        steps, final = journey.mutated()
        for row in final['observation']['keys']:
            if row['n'] == 3:
                row['key'] = 'x'
        self.kill('record key name differs from retained sample', lambda: journey.validate(steps, final=final), 'not in the retained')
        steps, final = journey.mutated()
        final['observation']['keysTotal'] += 1
        self.kill('unexplained key after the journey', lambda: journey.validate(steps, final=final), 'key counter')
        steps, final = journey.mutated()
        final['sampleSequence'] = 0
        self.kill('retained sample older than the journey', lambda: journey.validate(steps, final=final), 'key counter')
        steps, final = journey.mutated()
        final['schema'] = 'other'
        self.kill('retained sample malformed', lambda: journey.validate(steps, final=final), 'malformed')

    def test_step_level_key_and_counter_rules(self):
        journey = Journey(self)
        extra = lambda r: (r['keyEvents'].append({'n': r['domAfter']['keysTotal'] + 1, 'key': 'x', 'trusted': True}),
                           r['domAfter'].update(keysTotal=r['domAfter']['keysTotal'] + 1))
        self.step_mutant(journey, 'keyless AT-SPI action with a key event', 'edit-scene-properties', extra, 'keyless')
        self.step_mutant(journey, 'keyless Orca modifier chord with a key event', 'enter-focus-mode', extra, 'keyless')
        self.step_mutant(journey, 'keyless tree step with a key event', 'studio-heading', extra, 'one sample')
        self.step_mutant(journey, 'extra key in the Enter step', 'create-rectangle', extra, 'expected trusted key events|counter delta')
        self.step_mutant(journey, 'counter delta lower than events', 'tab-to-rectangle',
                         lambda r: r['domBefore'].update(keysTotal=r['domBefore']['keysTotal'] - 1), 'counter|delta')
        self.step_mutant(journey, 'key counter moved between steps', 'create-rectangle',
                         lambda r: (r['domBefore'].update(keysTotal=r['domBefore']['keysTotal'] + 1)), 'counter')
        self.step_mutant(journey, 'key counter moved backwards', 'create-rectangle',
                         lambda r: r['domAfter'].update(keysTotal=r['domBefore']['keysTotal'] - 1), 'counter')

    def test_tab_hops(self):
        journey = Journey(self)
        self.step_mutant(journey, 'hop row removed', 'tab-to-command-palette', lambda r: r['hops'].pop(0), 'Tab hops differ')
        self.step_mutant(journey, 'hop target wrong', 'tab-to-command-palette', lambda r: r['hops'][0].update(target='Other'), 'Tab hops differ')
        self.step_mutant(journey, 'hop presses disagree with events', 'tab-to-command-palette', lambda r: r['hops'][1].update(presses=r['hops'][1]['presses'] + 1), 'Tab hops differ')
        self.step_mutant(journey, 'hop DOM element wrong', 'tab-to-command-palette',
                         lambda r: r['hops'][0].update(domActive={'id': None, 'role': None, 'ariaLabel': 'Other', 'text': 'Other'}), 'not on its control')
        self.step_mutant(journey, 'hop AT-SPI node wrong', 'tab-to-command-palette', lambda r: r['hops'][2].update(atspi=[{'name': 'Other', 'role': 'push button'}]), 'not on its control')
        self.step_mutant(journey, 'hop AT-SPI node absent', 'tab-to-rectangle', lambda r: r['hops'][0].update(atspi=[]), 'not on its control')


class SampleFreshness(Case):
    def test_stale_and_regressing_samples(self):
        self.kill('browser samples never advance', lambda: Journey(self, 'stale-dom'))
        journey = Journey(self)
        self.step_mutant(journey, 'post-action sample not newer', 'open-command-palette',
                         lambda r: r['domAfter'].update(sampleSequence=r['domBefore']['sampleSequence']), 'not after the action')
        self.step_mutant(journey, 'post-action timestamp earlier', 'open-command-palette',
                         lambda r: r['domAfter'].update(sampledAtUnixMs=r['domBefore']['sampledAtUnixMs'] - 1), 'not after the action')
        self.step_mutant(journey, 'pre-action sample precedes the previous step', 'edit-scene-properties',
                         lambda r: r['domBefore'].update(sampleSequence=1), 'precedes the previous step')
        self.step_mutant(journey, 'pre-action timestamp precedes the previous step', 'edit-scene-properties',
                         lambda r: r['domBefore'].update(sampledAtUnixMs=1), 'precedes the previous step')
        self.step_mutant(journey, 'tree step with two different samples', 'studio-heading',
                         lambda r: r['domAfter'].update(sampleSequence=r['domAfter']['sampleSequence'] + 1), 'one sample')


class FocusEvidence(Case):
    def test_runner_mutants(self):
        self.kill('focus not restored by Escape', lambda: Journey(self, 'focus-not-restored'))
        self.kill('document unfocused', lambda: Journey(self, 'document-unfocused'))
        self.kill('AT-SPI action refused', lambda: Journey(self, 'action-refused'))

    def test_recorded_focus(self):
        journey = Journey(self)
        for step_id in FOCUS_STEPS:
            self.step_mutant(journey, 'focus unchanged ' + step_id, step_id,
                             lambda r: r['domBefore'].update(active=dict(r['domAfter']['active'])), 'did not change')
            self.step_mutant(journey, 'wrong DOM element ' + step_id, step_id,
                             lambda r: r['domAfter'].update(active={'id': 'x', 'role': 'button', 'ariaLabel': 'Other', 'text': 'Other'}), 'focus not on')
            self.step_mutant(journey, 'AT-SPI node absent ' + step_id, step_id, lambda r: r['focus'].update(atspi=[]), 'focus not on')
            self.step_mutant(journey, 'AT-SPI node wrong name ' + step_id, step_id,
                             lambda r: r['focus'].update(atspi=[{'name': 'Other', 'role': r['focus']['expect']['role']}]), 'focus not on')
            self.step_mutant(journey, 'AT-SPI node wrong role ' + step_id, step_id,
                             lambda r: r['focus'].update(atspi=[{'name': r['focus']['expect']['name'], 'role': 'label'}]), 'focus not on')
        self.step_mutant(journey, 'document lost focus', 'open-command-palette', lambda r: r['domAfter'].update(documentHasFocus=False), 'focus not on')
        self.step_mutant(journey, 'expected focus rewritten', 'open-command-palette',
                         lambda r: r['focus'].update(expect=dict(r['focus']['expect'], name='Other')), 'focus not on')


class TreeEvidence(Case):
    def test_observed_tree_state_is_required(self):
        journey = Journey(self)
        for step_id in ['studio-heading', 'open-command-palette', 'input-help-shortcut', 'open-rebind', 'create-rectangle']:
            self.step_mutant(journey, 'required object not showing after ' + step_id, step_id,
                             lambda r: r['tree'].update(presentAfter=[False] * len(r['tree']['presentAfter'])), 'observed tree state')
        for step_id in ['escape-restores-scene-focus', 'close-input-help', 'close-rebind']:
            self.step_mutant(journey, 'removed object still showing after ' + step_id, step_id,
                             lambda r: r['tree'].update(absentAfter=[False]), 'observed tree state')
            self.step_mutant(journey, 'observation list truncated ' + step_id, step_id, lambda r: r['tree'].update(absentAfter=[]), 'observed tree state')
        self.step_mutant(journey, 'tree expectation edited', 'open-command-palette', lambda r: r['tree'].update(present=[]), 'tree expectation')

    def test_close_that_does_nothing_is_refused(self):
        self.kill('Close is a no-op (runner waits on the tree)', lambda: Journey(self, 'close-noop'))
        # The runner's own tree wait removed: the recorded observation alone must refuse the journey.
        for step_id in ['close-input-help', 'close-rebind']:
            journey = Journey(self, 'close-noop', wait_tree=False)
            self.assertFalse(journey.step(journey.steps, step_id)['tree']['absentAfter'][0])
        self.kill('Close is a no-op (runner tree wait removed)', lambda: Journey(self, 'close-noop', wait_tree=False).validate(), 'observed tree state')

    def test_a_removal_needs_a_prior_observed_presence(self):
        journey = Journey(self)
        for step_id in ['escape-restores-scene-focus', 'close-input-help', 'close-rebind']:
            step = next(s for s in M.STUDIO_STEPS if s['id'] == step_id)
            record = next(r for r in journey.steps if r['id'] == step_id)
            self.kill('removal never observed present ' + step_id, lambda step=step, record=record: M.validate_studio_step(step, copy.deepcopy(record), M.new_state(), journey.read),
                      'never observed|precedes|counter')
        # An earlier step that did not observe the dialog (runner hard-coding the "was present" claim) leaves it unobserved.
        steps, _ = journey.mutated()
        for name in ('open-command-palette',):
            journey.step(steps, name)['tree']['present'] = []
        self.kill('open step no longer observes the dialog', lambda: journey.validate(steps), 'tree expectation')

    def test_escape_without_an_open_dialog_is_refused_by_the_runner(self):
        def run_escape_alone():
            model = Model(Path(tempfile.mkdtemp(dir=self.dir)), 'palette-never-opens')
            clock = Clock()
            step = next(s for s in M.STUDIO_STEPS if s['id'] == 'escape-restores-scene-focus')
            M.run_studio_step(step, model, clock.sleep, clock.monotonic)
        self.kill('Escape with no dialog open', run_escape_alone, 'without prior presence')
        self.kill('palette never opens', lambda: Journey(self, 'palette-never-opens'))


class CustodyControls(Case):
    def test_genuine_custody_binds_every_provider_fact(self):
        plan, archive, receiver = receiver_fixture(self.dir)
        custody = M.custody(receiver, plan, archive, DESCRIPTOR)
        self.assertEqual(custody['provider']['descriptorSha256'], plan['template']['descriptorSha256'])
        self.assertEqual((len(custody['bundle']['files']), len(custody['studio']['packages']), custody['studio']['distFiles']), (9, 3, 2))
        self.assertEqual(M.canonical(custody), M.canonical(M.custody(receiver, plan, archive, DESCRIPTOR)))

    def refuses(self, name, mutate, descriptor=DESCRIPTOR, studio_fsproj=None, expect=None):
        plan, archive, receiver = receiver_fixture(self.dir, studio_fsproj)
        mutate(plan, archive, receiver)
        self.kill(name, lambda: M.custody(receiver, plan, archive, descriptor), expect)

    def test_provider_mutants(self):
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
            self.refuses('custody: ' + name, mutate)

    def test_descriptor_mutants(self):
        plan, archive, receiver = receiver_fixture(self.dir)
        for name, raw in {'wrong bytes': DESCRIPTOR + b'#', 'no bundle parameter': DESCRIPTOR.replace(b'      - key: bundle\n', b''),
                          'no lifecycle parameter': DESCRIPTOR.replace(b'      - key: lifecycle\n', b''),
                          'other template': DESCRIPTOR.replace(b'fs-gg-fable-game', b'fs-gg-web')}.items():
            other = copy.deepcopy(plan)
            other['template']['descriptorSha256'] = sha(raw) if name != 'wrong bytes' else plan['template']['descriptorSha256']
            self.kill('descriptor: ' + name, lambda other=other, raw=raw: M.custody(receiver, other, archive, raw))
        self.kill('descriptor fetch needs an immutable revision', lambda: M.fetch_descriptor('main', lambda url: b''))
        self.assertTrue(M.fetch_descriptor('a' * 40, lambda url: url.encode()).startswith(b'https://raw.githubusercontent.com/FS-GG/FS.GG.Templates/' + b'a' * 40))

    def test_real_published_studio_defaults(self):
        # The real published 0.20.0 Studio.fsproj (default 0.32.3) on both sides keeps the bundle self-consistent,
        # so the typed-version check is the only thing that can refuse it.
        real_0200 = (HERE / 'fixtures/studio-0.20.0.fsproj').read_text()
        self.refuses('real 0.20.0 bundle with its 0.32.3 Studio default', lambda p, a, r: None, studio_fsproj=real_0200,
                     expect='authoring default differs')
        plan, archive, receiver = receiver_fixture(self.dir, (HERE / 'fixtures/studio-0.20.1.fsproj').read_text())
        self.assertEqual(M.custody(receiver, plan, archive, DESCRIPTOR)['studio']['authoringDefault'], '0.32.4')

    def edit(self, path, change):
        value = json.loads(path.read_text())
        change(value)
        path.write_text(json.dumps(value))

    def test_studio_package_mutants(self):
        lock, assets = 'SvgFoundation/Studio/packages.lock.json', 'SvgFoundation/Studio/obj/project.assets.json'
        mutants = {
            'lock resolved version': lambda p, a, r: self.edit(r / lock, lambda v: v['dependencies']['net10.0']['FS.GG.UI.Scene'].update(resolved='0.32.3')),
            'lock content hash': lambda p, a, r: self.edit(r / lock, lambda v: v['dependencies']['net10.0']['FS.GG.UI.KeyboardInput'].update(contentHash='x')),
            'project-backed package': lambda p, a, r: self.edit(r / assets, lambda v: v['libraries']['FS.GG.UI.Scene/0.32.4'].update(type='project')),
            'foreign package folder': lambda p, a, r: self.edit(r / assets, lambda v: v.update(packageFolders={'/tmp/elsewhere': {}})),
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
            self.refuses('studio: ' + name, mutate)

    def test_dist_change_changes_custody(self):
        plan, archive, receiver = receiver_fixture(self.dir)
        before = M.custody(receiver, plan, archive, DESCRIPTOR)
        (receiver / 'SvgFoundation/Studio/dist/assets/app.js').write_text('changed();')
        after = M.custody(receiver, plan, archive, DESCRIPTOR)
        self.assertNotEqual(before['studio']['distManifestSha256'], after['studio']['distManifestSha256'])
        self.assertEqual(before['studio']['distIndexSha256'], after['studio']['distIndexSha256'])


def copy_tree(source, destination):
    import shutil
    shutil.copytree(source, destination, symlinks=True)


class FakeServer:
    code = -15
    wait_error = None

    def __init__(self, *args, **kwargs):
        pass

    def send_signal(self, signal):
        pass

    def wait(self, timeout=None):
        if FakeServer.wait_error:
            raise FakeServer.wait_error
        return FakeServer.code

    def poll(self):
        return None


class RunFixture(Case):
    def fixture(self):
        plan, archive, receiver = receiver_fixture(self.dir)
        root = Path(tempfile.mkdtemp(dir=self.dir)) / 'run'
        (root / 'external-reference/orca').mkdir(parents=True)
        moved = root / 'external-reference/complete'
        copy_tree(receiver, moved)
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
        served = sha((moved / 'SvgFoundation/Studio/dist/index.html').read_bytes())

        def session(out, flight, before, tamper=None):
            clock = Clock()
            model = Model(out, None, served)
            steps = M.run_steps(model, before, sleep=clock.sleep, clock=clock.monotonic)
            if tamper:
                steps = tamper(steps)
            (out / 'journey.json').write_text(json.dumps({'process': {'name': 'orca', 'pid': 41}, 'browser': {'family': 'chromium', 'pid': 42},
                                                           'orcaVersion': '46.1', 'steps': steps}))
            (out / 'browser-dom.json').write_text(json.dumps(model.dom()))
        return root, preflight, session

    def go(self, root, session, guard=lambda env: None, code=-15, error=None):
        real, FakeServer.code, FakeServer.wait_error = subprocess.Popen, code, error
        subprocess.Popen = FakeServer
        try:
            return M.run(root, {}, session, lambda url: DESCRIPTOR, guard=guard, ready=lambda server: None)
        finally:
            subprocess.Popen = real
            FakeServer.code, FakeServer.wait_error = -15, None


class RunLevel(RunFixture):
    def test_held_run_refuses_before_any_effect_and_the_gate_stays_none(self):
        self.assertIsNone(O.CURRENT_PUBLIC_AT_ADMISSION)
        root, preflight, session = self.fixture()
        for environment in [{}, {'FSGG_CURRENT_PUBLIC_AT_ADMISSION': 'anything'}, {'FSGG_CURRENT_PUBLIC_AT_ADMISSION': 'inert-control-only'}]:
            self.kill('held run with environment %r' % (environment,), lambda environment=environment: M.run(root, environment, session, lambda url: DESCRIPTOR),
                      'current public AT held')
            self.assertFalse((root / 'provider-studio').exists())
        self.assertNotIn('CURRENT_PUBLIC_AT_ADMISSION =', (HERE / 'current-reference-provider-studio.py').read_text())
        self.assertEqual(len(re.findall(r'^CURRENT_PUBLIC_AT_ADMISSION = None$', (HERE / 'external-reference-orca.py').read_text(), re.M)), 1)

    def test_genuine_run_derives_acceptance_from_validation_and_revalidates(self):
        root, preflight, session = self.fixture()
        receipt = self.go(root, session)
        self.assertEqual((receipt['providerMatrixAcceptance'], receipt['studioAtAcceptance']), (True, True))
        self.assertEqual((receipt['nativeImeAcceptance'], receipt['durableSaveAcceptance'], receipt['whole4817Acceptance']), (False, False, False))
        stored = json.loads((root / 'provider-studio/receipt.json').read_text())
        local_path = root / 'external-reference/orca/observation.json'
        local = json.loads(local_path.read_text())
        local['_sha256'] = M.sha256_file(local_path)
        plan = json.loads((root / 'current-composition-plan.json').read_text())
        self.assertTrue(M.validate_receipt(stored, plan, preflight, root / 'provider-studio', local))
        self.assertEqual(len(stored['steps']), 19)

    def test_run_never_writes_a_receipt_or_acceptance_for_a_bad_session(self):
        def tampered(name, change, **kwargs):
            root, preflight, session = self.fixture()
            self.kill(name, lambda: self.go(root, lambda out, f, b: session(out, f, b, tamper=change), **kwargs))
            self.assertFalse((root / 'provider-studio/receipt.json').exists(), name)
        tampered('run: step deleted', lambda steps: [r for r in steps if r['id'] != 'close-rebind'])
        tampered('run: speech window rewritten', lambda steps: [dict(r, speech=dict(r['speech'], start=0, offsetBefore=0)) if r['id'] == 'create-rectangle' else r for r in steps])
        tampered('run: provider step unbound', lambda steps: [dict(r, bound='0' * 64) if r['id'] == 'provider-descriptor' else r for r in steps])
        tampered('run: removal observed still showing', lambda steps: [
            dict(r, tree=dict(r['tree'], absentAfter=[False])) if r['id'] == 'close-input-help' else r for r in steps])
        tampered('run: server not reaped (exit 0)', lambda steps: steps, code=0)
        tampered('run: server wait times out', lambda steps: steps, error=subprocess.TimeoutExpired('server', 15))

    def test_acceptance_is_derived_not_asserted(self):
        root, preflight, session = self.fixture()
        real, M.validate_receipt = M.validate_receipt, lambda *a, **k: False
        try:
            receipt = self.go(root, session)
        finally:
            M.validate_receipt = real
        self.assertEqual((receipt['providerMatrixAcceptance'], receipt['studioAtAcceptance']), (False, False))
        KILLED['run: a failed validation result never yields acceptance'] = 'flags False'

    def test_missing_local_save_observation_stops_the_run_before_effects(self):
        root, preflight, session = self.fixture()
        (root / 'external-reference/orca/observation.json').unlink()
        self.kill('run: local-save observation missing', lambda: self.go(root, session))
        self.assertFalse((root / 'provider-studio').exists())

    def test_server_readiness_poll(self):
        class Dead:
            def poll(self):
                return 1

        class Silent:
            def poll(self):
                return None
        clock = Clock()
        self.kill('server exited before the session', lambda: M.wait_server_ready(Dead(), 'http://127.0.0.1:9/', 1, clock.sleep, clock.monotonic), 'exited')
        self.kill('server never answers', lambda: M.wait_server_ready(Silent(), 'http://127.0.0.1:9/', 1, clock.sleep, clock.monotonic), 'did not answer')


class ReceiptLevel(RunFixture):
    def mutate_receipt(self, change):
        root, preflight, session = self.fixture()
        self.go(root, session)
        out = root / 'provider-studio'
        receipt = json.loads((out / 'receipt.json').read_text())
        local_path = root / 'external-reference/orca/observation.json'
        local = json.loads(local_path.read_text())
        local['_sha256'] = M.sha256_file(local_path)
        plan = json.loads((root / 'current-composition-plan.json').read_text())
        change(receipt, local, preflight, plan, out)
        return lambda: M.validate_receipt(receipt, plan, preflight, out, local)

    @staticmethod
    def unreaped(receipt, local, preflight, plan, out):
        (out / 'server.json').write_text(json.dumps({'signal': 'SIGTERM', 'exit': 0, 'reaped': True}))
        receipt['evidenceSha256']['server.json'] = M.sha256_file(out / 'server.json')

    @staticmethod
    def dom_unparseable(receipt, local, preflight, plan, out):
        (out / 'browser-dom.json').write_text('{')
        receipt['evidenceSha256']['browser-dom.json'] = M.sha256_file(out / 'browser-dom.json')

    @staticmethod
    def dom_event_removed(receipt, local, preflight, plan, out):
        value = json.loads((out / 'browser-dom.json').read_text())
        value['observation']['keys'] = value['observation']['keys'][1:]
        (out / 'browser-dom.json').write_text(json.dumps(value))
        receipt['evidenceSha256']['browser-dom.json'] = M.sha256_file(out / 'browser-dom.json')

    def test_receipt_mutants(self):
        cases = {
            'matrix cell unobserved': lambda r, l, f, p, o: r['matrix'].update(observed=[]),
            'provider matrix false on a stored receipt': lambda r, l, f, p, o: r.update(providerMatrixAcceptance=False),
            'studio acceptance false on a stored receipt': lambda r, l, f, p, o: r.update(studioAtAcceptance=False),
            'ime overclaim': lambda r, l, f, p, o: r.update(nativeImeAcceptance=True),
            'durable overclaim': lambda r, l, f, p, o: r.update(durableSaveAcceptance=True),
            'whole overclaim': lambda r, l, f, p, o: r.update(whole4817Acceptance=True),
            'audio claim': lambda r, l, f, p, o: r.update(physicalAudioHardware='observed'),
            'orca version': lambda r, l, f, p, o: r.update(orcaVersion='45.0'),
            'foreign templates': lambda r, l, f, p, o: r.update(templates={'revision': 'e' * 40, 'tree': None}),
            'foreign caller': lambda r, l, f, p, o: r['caller'].update(run='9'),
            'local save failed': lambda r, l, f, p, o: l.update(result='failed'),
            'local save other controller': lambda r, l, f, p, o: l['currentPublicAt'].update(controller={'revision': 'f' * 40, 'tree': None}),
            'local join digest': lambda r, l, f, p, o: r['localSaveJoin'].update(observationSha256='0' * 64),
            'evidence hash': lambda r, l, f, p, o: r['evidenceSha256'].update({'custody-before.json': '0' * 64}),
            'evidence unbound': lambda r, l, f, p, o: r['evidenceSha256'].pop('server.json'),
            'steps differ from original': lambda r, l, f, p, o: r['steps'].pop(),
            'server not reaped': self.unreaped,
            'browser sample unparseable': self.dom_unparseable,
            'retained browser sample lost a recorded key': self.dom_event_removed,
            'plan selection differs': lambda r, l, f, p, o: p['selection'].update(bundle='studio'),
        }
        for name, change in cases.items():
            self.kill('receipt: ' + name, self.mutate_receipt(change))


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
            self.assertNotEqual(bad, text, name)
            self.kill('workflow: ' + name, lambda bad=bad: M.workflow_guard(bad))
        self.assertLess(text.index('      - name: Observe actual external reference Orca journey'), text.index('      - name: Observe provider/Studio Orca journey'))

    def test_shell_allow_list(self):
        shell = HERE / 'observe-svg-input-orca.sh'
        self.assertEqual(subprocess.run(['bash', '-n', str(shell)]).returncode, 0)
        text = shell.read_text()
        head = text.split('export NO_AT_BRIDGE=0', 1)[0]
        head = head.replace('exec dbus-run-session -- env SVG_ORCA_INNER=1 xvfb-run -a bash "$0" "$address" "$output"', 'true')
        probe = self.dir / 'probe.sh'
        probe.write_text(head + '\ntrue\n')

        def run(variable, value):
            result = subprocess.run(['bash', str(probe), 'addr', 'out'], env={'PATH': '/usr/bin:/bin', variable: value, 'SVG_ORCA_INNER': '1'},
                                    capture_output=True, text=True)
            if result.returncode != 0:
                raise ValueError('shell refused (%s)' % result.returncode)
        for variable, value in [('SVG_ORCA_JOURNEY', 'other.py'), ('SVG_ORCA_JOURNEY', '../x.py'), ('SVG_ORCA_BROWSER_SCRIPT', 'other.cjs')]:
            self.kill('shell: %s=%s' % (variable, value), lambda variable=variable, value=value: run(variable, value), 'refused \\(2\\)')
        run('SVG_ORCA_JOURNEY', 'provider-studio-orca.py')
        run('SVG_ORCA_BROWSER_SCRIPT', 'provider-studio-browser.cjs')
        self.assertIn('${SVG_ORCA_JOURNEY:-svg-input-orca.py}', text)
        self.assertIn('${SVG_ORCA_BROWSER_SCRIPT:-orca-playwright-browser.cjs}', text)
        import ast
        ast.parse((HERE / 'provider-studio-orca.py').read_text())
        companion = (HERE / 'provider-studio-browser.cjs').read_text()
        self.assertIn('trusted: event.isTrusted === true', companion)
        self.assertIn('keysTotal', companion)


class ZZMutantCount(unittest.TestCase):
    EXPECTED = None

    def test_names_are_distinct_and_counted(self):
        print('\ndistinct mutants killed: %d' % len(KILLED))
        self.assertEqual(len(KILLED), 216)


if __name__ == '__main__':
    unittest.main(verbosity=1)
