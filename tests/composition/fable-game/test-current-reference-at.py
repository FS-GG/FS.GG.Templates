#!/usr/bin/env python3
"""Inert tests of the maintained observer's actual current-reference functions.

No GI import, Node, browser, SDK, network, live unit or AT operation is selected.
The embedded companion's new JS handler controls are source-prepared separately.
"""
import copy
import ast
import importlib.util
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

SPEC = importlib.util.spec_from_file_location("current_at_observer", Path(__file__).with_name("external-reference-orca.py"))
O = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(O)


def inputs():
    controller = {"revision": "a" * 40, "tree": "b" * 40}
    template = {"sourceCommit": "c" * 40, "version": "fixture-template", "sha256": "d" * 64}
    package = {"producerRevision": template["sourceCommit"], "version": template["version"], "archiveSha256": template["sha256"]}
    plan = {"template": template, "rendering": {"sourceCommit": "e" * 40, "custodySha256": "f" * 64},
            "browsers": {"families": ["chromium", "firefox", "webkit"], "workers": 1, "retries": 0,
                         "cases": [{"file": "fixture.spec.ts", "suite": [], "title": "fixture"}]}}
    packet = {"currentCompositionPlan": plan, "templates": {"revision": template["sourceCommit"], "tree": None},
              "templatesInputSource": "exact-current-public-archive", "templatePackageInput": package,
              "actualProducerCustodyReadback": True, "disposition": "passed", "qualificationMode": "current-public-composition",
              "producer": {"revision": "e" * 40, "custodyManifestSha256": "f" * 64},
              "browserFamilies": plan["browsers"]["families"], "passedPerFamily": 1, "skipped": 0}
    preflight = {"atJourney": O.LOCAL_SAVE_JOURNEY, "renderingInputSource": "current-public-composition",
                 "templates": controller, "currentCompositionPlanSha256": "1" * 64,
                 "observerSourceSha256": "2" * 64, "mechanicalObserverSha256": "4" * 64, "templatePackageInput": copy.deepcopy(package),
                 "actualProducerCustodyReadback": True, "producer": {"revision": "e" * 40, "custodySha256": "f" * 64},
                 "disposition": "preflight-passed", "requestedPhase": "full",
                 "caller": {"repository": "FS-GG/FS.GG.Rendering", "revision": "3" * 40, "run": "1", "attempt": "1"}}
    spec = importlib.util.spec_from_file_location('native_fixture_controls', Path(__file__).with_name('test-current-reference-native-input.py'))
    controls = importlib.util.module_from_spec(spec); spec.loader.exec_module(controls)
    preflight['nativeInputFacility'] = controls.fixture()
    preflight['nativeInputHelperSha256'] = O.digest(Path(__file__).with_name('current-reference-native-input.py'))
    return packet, preflight, controller


class LocalFixture:
    """Independent tiny model of the published in-memory controls, not an AT client."""
    def __init__(self, directory, mutant=None):
        self.log = directory / "speech.log"
        self.log.write_bytes(b"")
        self.accepted = 0
        self.saved = None
        self.replay = None
        self.result = "ready"
        self.sequence = 0
        self.disposed = False
        self.actions = []
        self.observations = {}
        self.mutant = mutant

    def snapshot(self):
        self.sequence += 1
        if self.disposed:
            local = {"rootCount": 0, "statusCount": 0, "directButtons": []}
        else:
            local = {"rootCount": 1, "statusCount": 1, "statusLive": "polite", "localAgent": "-7:23:-41:89", "agentFullCell": "0:0:0:0",
                     "localAccepted": str(self.accepted), "localSaved": str(self.saved is not None).lower(),
                     "localReplayCount": "none" if self.replay is None else str(self.replay),
                     "status": f"Synthetic local save/replay: {self.result}; accepted inspections {self.accepted}. Agent -7, 23, -41, 89."}
            if self.mutant == "coordinate" and self.accepted:
                local["localAgent"] = "-7:23:-41:88"
        return {"sequence": self.sequence, "localReference": local}

    def press(self, name):
        self.actions.append({"name": name, "key": "Return", "atspiFocused": True, "directReferenceControl": True,
                             "controlRoot": "fourd-reference", "eventSequence": len(self.actions) + 1})
        if name == "Synthetic inspect full cell":
            self.accepted += 1
            self.result = "inspection accepted"
        elif name == "Save synthetic local snapshot":
            self.saved = self.accepted
            self.result = "snapshot saved in memory"
        elif name == "Replay synthetic local recording":
            self.replay = self.accepted
            self.result = "replay preview completed"
            if self.mutant == "replay-mutates":
                self.accepted += 1
        elif name == "Restore synthetic local snapshot":
            if self.mutant != "restore-keeps-current":
                self.accepted = self.saved
            self.replay = None
            self.result = "snapshot restored; new recording epoch"
        elif name == "Dispose FourD reference":
            self.disposed = self.mutant != "still-present"
        else:
            raise AssertionError("unselected fixture control")
        if not self.disposed and self.mutant != "stale-speech":
            with self.log.open("ab") as stream:
                stream.write(("SPEECH OUTPUT: " + self.snapshot()["localReference"]["status"] + "\n").encode())

    def wait(self, predicate):
        value = self.snapshot()
        O.require(predicate(value), "fixture condition unavailable")
        return value

    def speech(self, phase, start, expected):
        spoken, end = O.speech_range(self.log, start)
        O.require(expected in spoken, "fixture genuine phase speech absent")
        return {"speechStart": start, "speechEnd": end}

    def run(self):
        O.observe_local_save(self.press, self.snapshot, self.wait, self.speech,
                             lambda: self.log.stat().st_size, lambda: self.mutant != "at-retained", self.observations)
        return O.validate_local_save(self.observations, self.actions,
                                     lambda start, end: O.speech_range(self.log, start, end)[0])


class CurrentAtTests(unittest.TestCase):
    def caller(self):
        spec = importlib.util.spec_from_file_location('current_at_caller', Path(__file__).with_name('current-reference-at-caller.py'))
        module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
        return module

    def test_full_caller_source_entry_is_held_before_any_tools_or_inputs(self):
        caller = self.caller()
        with patch.object(caller.subprocess, 'run', side_effect=AssertionError('tool reached')), \
             patch.object(Path, 'read_text', side_effect=AssertionError('input reached')):
            with self.assertRaisesRegex(RuntimeError, 'held'):
                caller.source(Path('/absent'), Path('/absent'))

    def test_current_source_preflight_does_not_promote_phase_or_invent_at(self):
        caller = self.caller()
        packet, preflight, controller = inputs()
        preflight.update(schema='fsgg.external-reference-native-preflight/1', qualification='not-run', requestedPhase='preflight')
        plan = packet['currentCompositionPlan']
        plan['rendering']['packages'] = [{'id': 'Fixture.UI', 'sha256': '9' * 64}]
        readback = {'custodySha256': plan['rendering']['custodySha256'], 'records': [
            {'id': 'Fixture.UI', 'rawSha256': '9' * 64, 'state': 'matched', 'payloadMatched': True, 'source': 'e' * 40}]}
        joined = caller.join_preflight(preflight, plan, controller, '1' * 64, '2' * 64, '4' * 64,
                                        packet['templatePackageInput'], readback)
        self.assertEqual(joined['requestedPhase'], 'preflight')
        self.assertEqual(joined['caller'], preflight['caller'])
        self.assertEqual(joined['qualification'], 'not-run')
        self.assertTrue(joined['actualProducerCustodyReadback'])
        for key in ['actualAT', 'providerMatrixAcceptance', 'nativeImeAcceptance', 'whole4817Acceptance']:
            self.assertIs(joined[key], False)
        for field, value in [('caller', {}), ('disposition', 'passed'), ('qualification', 'passed'),
                             ('templates', {}), ('renderingInputSource', 'public')]:
            with self.subTest(field=field), self.assertRaises((RuntimeError, KeyError)):
                caller.join_preflight({**preflight, field: value}, plan, controller, '1' * 64, '2' * 64, '4' * 64,
                                      packet['templatePackageInput'], readback)
        for changed in [{**readback, 'custodySha256': '0' * 64},
                        {**readback, 'records': [{**readback['records'][0], 'payloadMatched': False}]}]:
            with self.assertRaises((RuntimeError, ValueError)):
                caller.join_preflight(preflight, plan, controller, '1' * 64, '2' * 64, '4' * 64,
                                      packet['templatePackageInput'], changed)

    def test_actual_current_workflow_guard_precedes_acquisition_and_native_setup(self):
        workflow = (O.ROOT / '.github/workflows/fable-external-reference-source.yml').read_text()
        guard = workflow.index('      - name: Refuse held current AT before acquisition or setup')
        for effect in ['      - name: Verify native producer run', '      - uses: actions/setup-dotnet',
                       '      - name: Provision external reference assistive technology']:
            self.assertLess(guard, workflow.index(effect))
        section = workflow[guard:workflow.index('\n      - ', guard + 1)]
        self.assertIn("!inputs.preflight-only && inputs.rendering-input-source == 'current-public-composition'", section)
        self.assertIn('current-reference-at-caller.py guard', section)
        self.assertIn('current-reference-at-caller.py source', workflow)
        self.assertIn('journey=current-public-local-save', workflow)
        shell = (Path(__file__).with_name('verify-external-reference-candidate.sh')).read_text()
        self.assertLess(shell.index('current-reference-at-caller.py" guard'), shell.index('mkdir -p'))
        self.assertIn('"$current_stage" == current-at-full', shell)
        self.assertIn('if [[ "$current_stage" == current-source-stage ]]; then exit 0; fi', shell)
        self.assertIn("packet['actualProducerCustodyReadback']=True", shell)

    def test_wrapper_has_closed_current_journey_argument(self):
        wrapper = (Path(__file__).with_name('observe-external-reference-orca.sh')).read_text()
        self.assertIn('current-public-local-save) args=(--current-public-local-save)', wrapper)
        self.assertIn('*) echo "unknown AT journey"', wrapper)
        self.assertIn('"$script_dir/external-reference-orca.py" "${args[@]}"', wrapper)

    def test_actual_prepare_uses_original_preflight_and_public_custody_ports(self):
        caller = self.caller()
        packet, preflight, controller = inputs()
        preflight.update(schema='fsgg.external-reference-native-preflight/1', qualification='not-run', requestedPhase='preflight')
        plan = packet['currentCompositionPlan']
        plan['template']['id'] = 'FS.GG.Workspace.Template'
        plan['rendering'].update(sourceCommit=caller.public.SOURCE, custodySha256=caller.public.CUSTODY_SHA256,
                                  version=caller.public.VERSION, packages=[{'id': k, 'sha256': v} for k, v in caller.public.PUBLIC_SHA256.items()])
        preflight['producer'].update(revision=caller.public.SOURCE, custodySha256=caller.public.CUSTODY_SHA256)
        raw = (json.dumps(plan) + '\n').encode()
        calls = []
        def output(argv, **kwargs):
            calls.append(list(map(str, argv)))
            if argv[0] == 'git': return controller['tree' if argv[-1] == 'HEAD^{tree}' else 'revision']
            self.assertEqual(argv[-1], 'current-composition-plan')
            return raw
        def fetch(url, expected, maximum, destination):
            calls.append(['public-template', url]); destination.write_bytes(b'archive fixture')
        def acquire(original, destination):
            self.assertEqual(original.read_bytes(), b'original verified custody')
            calls.append(['public-payload-compare']); destination.mkdir()
            (destination / 'public-readback.json').write_text(json.dumps({'custodySha256': caller.public.CUSTODY_SHA256,
                'records': [{'id': k, 'rawSha256': v, 'state': 'matched', 'payloadMatched': True, 'source': caller.public.SOURCE}
                            for k, v in caller.public.PUBLIC_SHA256.items()]}))
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'rendering-packet').mkdir()
            (root / 'rendering-packet/release-custody.json').write_bytes(b'original verified custody')
            O.write(root / 'external-reference-preflight.json', preflight)
            with patch.object(caller.subprocess, 'check_output', side_effect=output), \
                 patch.object(caller.subprocess, 'run') as run, patch.object(caller.local, 'fetch', side_effect=fetch), \
                 patch.object(caller.public, 'acquire', side_effect=acquire):
                caller.prepare(root, Path('/typed-owner.dll'))
            self.assertEqual((root / 'current-composition-plan.json').read_bytes(), raw)
            joined = json.loads((root / 'external-reference-preflight.json').read_text())
            self.assertEqual(joined['caller'], preflight['caller'])
            self.assertEqual(joined['requestedPhase'], 'preflight')
            self.assertFalse(joined['actualAT'])
            self.assertEqual(joined['currentCompositionPlanSha256'], O.digest(root / 'current-composition-plan.json'))
            self.assertEqual(run.call_count, 1)  # actual typed package identity port, no second producer fetch or verifier
            self.assertIn('published-tool-check', run.call_args.args[0])
            self.assertEqual(calls[-1], ['public-payload-compare'])
            self.assertFalse((root / 'external-reference').exists())

    def test_actual_full_prepare_cannot_bypass_gate_with_supplied_receipt(self):
        caller = self.caller()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            O.write(root / 'external-reference-preflight.json', {'requestedPhase': 'full'})
            with patch.object(caller.subprocess, 'check_output', side_effect=AssertionError('tool reached')):
                with self.assertRaisesRegex(RuntimeError, 'held'):
                    caller.prepare(root, Path('/typed-owner.dll'))
            self.assertFalse((root / 'current-composition-plan.json').exists())

    def test_actual_full_shell_and_wrapper_refuse_before_receiver_or_native_effects(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = str(Path(tmp) / 'never-created')
            env = {'PATH': os.environ['PATH'], 'LANG': 'C.UTF-8', 'PYTHONDONTWRITEBYTECODE': '1',
                   'FSGG_CURRENT_COMPOSITION_LOCAL_VERIFICATION': 'adr-0096-local-development-verification',
                   'FSGG_CURRENT_PUBLIC_AT_ADMISSION': 'cannot-lift-none'}
            commands = [
                ['bash', str(Path(__file__).with_name('verify-external-reference-candidate.sh')), '/absent', '/absent',
                 '0.32.3', target, '4ec6eafbbbf02264db9b0db4780c590abe0bf9cd', 'current-public-composition',
                 '/absent.nupkg', 'a' * 64, 'current-at-full'],
                ['bash', str(Path(__file__).with_name('observe-external-reference-orca.sh')), target,
                 '/absent.json', 'current-public-local-save'],
            ]
            for argv in commands:
                result = subprocess.run(argv, env=env, text=True, capture_output=True, timeout=5)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn('current public AT held', result.stderr)
                self.assertFalse(Path(target).exists())

    def test_imports_do_not_load_gi(self):
        self.assertNotIn("gi", sys.modules)
        self.assertNotIn("gi.repository.Atspi", sys.modules)

    def test_actual_main_is_held_before_files_signals_or_qualify(self):
        with patch.object(sys, "argv", ["observer", "--current-public-local-save", "/missing", "/missing"]), \
             patch.object(O, "qualify", side_effect=AssertionError("qualify reached")), \
             patch.object(O, "capture_termination", side_effect=AssertionError("signals reached")):
            with self.assertRaisesRegex(RuntimeError, "held"):
                O.main()

    def test_direct_entry_is_also_held(self):
        with patch.object(O.subprocess, "check_output", side_effect=AssertionError("native reached")):
            with self.assertRaisesRegex(RuntimeError, "held"):
                O.qualify(Path("/missing"), Path("/missing"), [], current_public=True)

    def test_environment_cannot_activate_none(self):
        with self.assertRaisesRegex(RuntimeError, "held"):
            O.current_public_at_admission({"FSGG_CURRENT_PUBLIC_AT_ADMISSION": "anything"})

    def test_controller_and_published_producer_are_separately_joined(self):
        packet, preflight, controller = inputs()
        identity = O.current_public_identity(packet, preflight, controller, "1" * 64, "2" * 64, "4" * 64)
        self.assertNotEqual(controller["revision"], packet["templates"]["revision"])
        self.assertEqual(identity["controller"], controller)
        self.assertFalse(O.prerequisites(packet, preflight, lambda _: True, identity))
        self.assertTrue(O.prerequisites(packet, preflight, lambda _: True))

    def test_wrong_or_missing_authenticated_join_refuses(self):
        for target, field, bad in [("preflight", "templates", {"revision": "0" * 40, "tree": "b" * 40}),
                                    ("preflight", "observerSourceSha256", "0" * 64),
                                    ("preflight", "mechanicalObserverSha256", "0" * 64),
                                    ("preflight", "currentCompositionPlanSha256", "0" * 64),
                                    ("preflight", "templatePackageInput", {}),
                                    ("preflight", "actualProducerCustodyReadback", False),
                                    ("packet", "actualProducerCustodyReadback", False),
                                    ("packet", "templates", {"revision": "0" * 40, "tree": None}),
                                    ("packet", "producer", {"revision": "0" * 40, "custodyManifestSha256": "f" * 64})]:
            with self.subTest(field=field, target=target):
                packet, preflight, controller = inputs()
                (packet if target == "packet" else preflight)[field] = bad
                with self.assertRaises((RuntimeError, KeyError)):
                    O.current_public_identity(packet, preflight, controller, "1" * 64, "2" * 64, "4" * 64)

    def test_browser_population_and_typed_identity_are_not_legacy_count(self):
        packet, preflight, _ = inputs()
        self.assertTrue(O.browser_prerequisite(packet, preflight))
        packet["passedPerFamily"] = 8
        self.assertFalse(O.browser_prerequisite(packet, preflight))

    def test_actual_current_input_reader_joins_original_reports(self):
        packet, preflight, controller = inputs()
        with tempfile.TemporaryDirectory() as temp:
            out = Path(temp)
            O.write(out / "current-composition-plan.json", packet["currentCompositionPlan"])
            preflight["currentCompositionPlanSha256"] = O.digest(out / "current-composition-plan.json")
            preflight["observerSourceSha256"] = O.digest(Path(O.__file__))
            preflight["mechanicalObserverSha256"] = O.digest(Path(__file__).with_name("current-composition-observations.py"))
            packet["browserReportSha256"] = {}
            for family in packet["browserFamilies"]:
                report = {"stats": {"expected": 1, "unexpected": 0, "skipped": 0, "flaky": 0}, "suites": [{"specs": [
                    {"file": "fixture.spec.ts", "title": "fixture", "ok": True, "tests": [
                        {"projectName": family, "status": "expected", "results": [{"status": "passed", "retry": 0}]}]}]}]}
                path = out / (family + "-browser.json")
                O.write(path, report); packet["browserReportSha256"][family] = O.digest(path)
            self.assertEqual(O.current_public_inputs(out, packet, preflight, controller)["controller"], controller)
            path = out / "chromium-browser.json"; value = json.loads(path.read_text())
            value["suites"][0]["specs"][0]["title"] = "unselected case"
            O.write(path, value)
            with self.assertRaisesRegex(RuntimeError, "report changed"):
                O.current_public_inputs(out, packet, preflight, controller)
            packet["browserReportSha256"]["chromium"] = O.digest(path)
            with self.assertRaisesRegex(ValueError, "identity differs"):
                O.current_public_inputs(out, packet, preflight, controller)

    def test_assembled_current_receipt_preserves_original_common_binder(self):
        self.assembled_current_receipt()

    def test_original_journey_boolean_projection_mutants_refuse(self):
        self.assembled_current_receipt(True)

    def test_original_journey_float_projection_mutants_refuse(self):
        self.assembled_current_receipt(1.0)

    def assembled_current_receipt(self, numeric_mutant=None):
        packet, preflight, controller = inputs()
        with tempfile.TemporaryDirectory() as temp:
            directory = Path(temp)
            fixture = LocalFixture(directory); fixture.run()
            fixture.log.rename(directory / "orca-debug.log")
            O.write(directory / "current-composition-plan.json", packet["currentCompositionPlan"])
            preflight["currentCompositionPlanSha256"] = O.digest(directory / "current-composition-plan.json")
            preflight["observerSourceSha256"] = O.digest(Path(O.__file__))
            preflight["mechanicalObserverSha256"] = O.digest(Path(__file__).with_name("current-composition-observations.py"))
            identity = O.current_public_identity(packet, preflight, controller, preflight["currentCompositionPlanSha256"],
                                                  preflight["observerSourceSha256"], preflight["mechanicalObserverSha256"])
            O.write(directory / "current-public-at.json", identity)
            O.write(directory / "source-qualification.json", packet)
            journey = {"process": {"name": "orca", "pid": 62}, "browser": {"family": "chromium", "pid": 2, "launcherPid": 2, "companionPid": 60},
                       "actions": fixture.actions, "observations": fixture.observations, "journey": O.LOCAL_SAVE_JOURNEY, "firstCause": None}
            native = O.native_input_helper()
            spec = importlib.util.spec_from_file_location('native_report_fixture', Path(__file__).with_name('test-current-reference-native-input.py'))
            controls = importlib.util.module_from_spec(spec);spec.loader.exec_module(controls)
            journey['observations']['nativeInput'] = controls.report_fixture(identity['nativeInputFacilitySha256'])
            (directory / 'native-input-facility.json').write_bytes(native.canonical(preflight['nativeInputFacility']))
            O.write(directory / "journey.json", journey)
            activation = O.route_fixture()
            births={role:dict(pid=n,start=n,ppid=42,sid=42,pgid=42) for n,role in enumerate(['bus','config','dconf','pinyin','simple'],100)}
            O.write(directory/'native-input-runtime.json',dict(manifestSha256=identity['nativeInputFacilitySha256'],firstCause=None,births=births,
                clientMapping={'roles':{k:preflight['nativeInputFacility']['objects'][k] for k in ['gtk3','ibusGtk3']}}))
            journey['observations']['nativeInput']['runtimeSha256'] = O.digest(directory/'native-input-runtime.json')
            O.write(directory/'journey.json',journey)
            O.route_fixture_evidence(directory, activation, native_facility_sha=identity['nativeInputFacilitySha256'])
            leaders=json.loads((directory/'resource-leaders.json').read_text())
            leaders += [dict(resource='native-ime-'+role,**birth) for role,birth in births.items()]
            O.write(directory/'resource-leaders.json',leaders)
            cleanup = {"disposition": "observed-empty", "unknown": [], "remaining": []}
            O.write(directory / "process-result.json", {"exit": 0, "firstCause": None, "cleanup": cleanup})
            names = ["orca.log", "orca-debug.log", "process-result.json", "source-qualification.json", "activation-provenance.json",
                     "owned-bus-route.json", "owned-bus-runtime.json", "session.conf", "accessibility.conf", "session-contract-state.json",
                     "session-budget.json", "journey.json", "current-public-at.json", "current-composition-plan.json", "native-input-runtime.json", "native-input-facility.json", *O.FINISH_FILES, *O.BROWSER_FILES]
            receipt = {"schema": O.SCHEMA, "result": "passed", "templates": packet["templates"], "caller": preflight["caller"],
                       "producer": preflight["producer"], **journey, "currentPublicAt": identity, "keyboard": "xdotool-X11",
                       "speechBoundary": "Orca SPEECH OUTPUT", "physicalAudioHardware": "not-observed", "cleanup": cleanup,
                       "sourceQualificationSha256": O.digest(directory / "source-qualification.json"),
                       "localSaveStorage": "synthetic-in-memory", "durableSaveAcceptance": False, "providerMatrixAcceptance": False,
                       "nativeImeAcceptance": False, "whole4817Acceptance": False,
                       "evidenceSha256": {name: O.digest(directory / name) for name in names}}
            self.assertTrue(O.validate(receipt, packet, preflight, directory))
            if numeric_mutant is not None:
                originals = {path.name: path.read_bytes() for path in directory.iterdir() if path.is_file()}
                for field in ["rootCount", "eventSequence", "transportOutcome"]:
                    altered = copy.deepcopy(receipt)
                    if field == "rootCount":
                        self.assertIs(type(receipt["observations"]["initial"][field]), int)
                        altered["observations"]["initial"][field] = numeric_mutant
                    elif field == "eventSequence":
                        self.assertIs(type(receipt["actions"][0][field]), int)
                        altered["actions"][0][field] = numeric_mutant
                    else:
                        altered["browser"][field] = {"reported": 0 if type(numeric_mutant) is bool else 0.0,
                                                      "stage": "not-observed"}
                    with self.subTest(field=field), self.assertRaisesRegex(RuntimeError, "original journey projection|derived transport projection"):
                        O.validate(altered, packet, preflight, directory)
                self.assertEqual(originals, {path.name: path.read_bytes() for path in directory.iterdir() if path.is_file()})
                return
            derived = copy.deepcopy(receipt)
            derived["browser"]["transportOutcome"] = {"reported": False, "stage": "not-observed"}
            self.assertTrue(O.validate(derived, packet, preflight, directory))
            derived["browser"]["transportOutcome"] = {"reported": True, "stage": "invented"}
            with self.assertRaisesRegex(RuntimeError, "transport outcome"):
                O.validate(derived, packet, preflight, directory)
            originals = {path.name: path.read_bytes() for path in directory.iterdir() if path.is_file()}
            altered = copy.deepcopy(receipt)
            for action in altered["actions"]:
                action["eventSequence"] += 100
            for observation in altered["observations"].values():
                if 'sampleSequence' in observation:
                    observation["sampleSequence"] += 100
            with self.assertRaisesRegex(RuntimeError, "original journey projection"):
                O.validate(altered, packet, preflight, directory)
            for field, value in [("actions", []), ("observations", {}),
                                 ("journey", "other"), ("firstCause", "unreported original failure"),
                                 ("process", {**receipt["process"], "extra": True}),
                                 ("browser", {**receipt["browser"], "extra": True})]:
                altered = copy.deepcopy(receipt); altered[field] = value
                with self.subTest(projection=field), self.assertRaises(RuntimeError):
                    O.validate(altered, packet, preflight, directory)
            self.assertEqual(originals, {path.name: path.read_bytes() for path in directory.iterdir() if path.is_file()})
            O.write(directory / "process-result.json", {"exit": 1, "firstCause": "original refusal", "cleanup": cleanup})
            receipt["evidenceSha256"]["process-result.json"] = O.digest(directory / "process-result.json")
            with self.assertRaisesRegex(RuntimeError, "original AT exit"):
                O.validate(receipt, packet, preflight, directory)

    def test_actual_local_sequence_and_original_speech_windows(self):
        with tempfile.TemporaryDirectory() as temp:
            fixture = LocalFixture(Path(temp))
            self.assertTrue(fixture.run())
            self.assertEqual(fixture.accepted, 1)
            self.assertEqual(fixture.replay, 1)
            self.assertEqual(len(fixture.actions), 7)

    def test_actual_finite_workflow_registration_and_missing_routes_refuse(self):
        source = Path(__file__).with_name("verify-external-reference-workflow.py").read_text()
        tree = ast.parse(source)
        function = next(node for node in tree.body if isinstance(node, ast.FunctionDef)
                        and node.name == "validate_current_at_registration")
        namespace = {}
        exec(compile(ast.Module(body=[function], type_ignores=[]), "actual-workflow-registration", "exec"), namespace)
        validate = namespace["validate_current_at_registration"]
        workflow = (O.ROOT / ".github/workflows/fable-external-reference-source.yml").read_text()
        self.assertTrue(validate(workflow))
        command = "PYTHONDONTWRITEBYTECODE=1 timeout --kill-after=5s 120s prlimit --cpu=120 --fsize=16777216 python3 -I -B tests/composition/fable-game/test-current-reference-at.py"
        mutants = [workflow.replace("      - 'tests/composition/fable-game/test-current-reference-at.py'\n", ""),
                   workflow.replace(command, "true", 1),
                   workflow[::-1].replace(command[::-1], "true"[::-1], 1)[::-1],
                   workflow.replace("120s prlimit", "1200s prlimit")]
        for mutant in mutants:
            with self.assertRaises(AssertionError):
                validate(mutant)

    def test_actual_sequence_refuses_causal_bad_states(self):
        for mutant in ["coordinate", "replay-mutates", "restore-keeps-current", "still-present", "at-retained", "stale-speech"]:
            with self.subTest(mutant=mutant), tempfile.TemporaryDirectory() as temp:
                with self.assertRaises(RuntimeError):
                    LocalFixture(Path(temp), mutant).run()

    def test_binder_refuses_replay_counter_focus_order_and_disposal_mutants(self):
        with tempfile.TemporaryDirectory() as temp:
            fixture = LocalFixture(Path(temp)); fixture.run()
            def bind(obs, actions):
                return O.validate_local_save(obs, actions, lambda a, b: O.speech_range(fixture.log, a, b)[0])
            for phase, field, bad in [("save", "speechStart", 0), ("replay2", "localAccepted", "3"),
                                       ("restore", "sampleSequence", 0), ("afterDisposal", "atControlsAbsent", False),
                                       ("disposed", "rootCount", 1)]:
                obs = copy.deepcopy(fixture.observations); obs[phase][field] = bad
                with self.subTest(field=field), self.assertRaises(RuntimeError):
                    bind(obs, fixture.actions)
            for field, bad in [("atspiFocused", False), ("controlRoot", "external-authority-reference"), ("name", "wrong")]:
                actions = copy.deepcopy(fixture.actions); actions[0][field] = bad
                with self.subTest(field=field), self.assertRaises(RuntimeError):
                    bind(fixture.observations, actions)

    def test_actual_local_navigation_and_late_focus_refusal(self):
        for late in [False, True]:
            with self.subTest(late=late):
                tick = [0.0]; keys = []; actions = []; name = "Synthetic inspect full cell"
                def dom():
                    return {"documentHasFocus": True, "active": {"text": name, "id": "", "parentId": "fourd-reference"},
                            "localReference": {"directButtons": [name]}, "keys": copy.deepcopy(keys)}
                def focused(_):
                    if late: tick[0] += 3
                    return True
                def key(value):
                    self.assertEqual(value, "Return")
                    keys.append({"sequence": len(keys)+1, "key": "Enter", "text": name, "parentId": "fourd-reference", "id": ""})
                action = lambda: O.activate_reference_control(name, dom, focused, actions, clock=lambda: tick[0],
                    pause=lambda _: None, key=key, root_id="fourd-reference", reference_key="localReference")
                if late:
                    with self.assertRaisesRegex(RuntimeError, "after deadline"): action()
                    self.assertEqual(keys, [])
                else:
                    action(); self.assertEqual(actions[0]["controlRoot"], "fourd-reference")

    def test_primary_failure_survives_reporting_failure(self):
        first = ValueError("original observation refused")
        attempted = []
        def fail(): raise first
        def report(cause):
            attempted.append(cause)
            raise OSError("original storage refused")
        with patch.object(sys, "stderr", io.StringIO()), self.assertRaises(ValueError) as caught:
            O.record_local_observation(fail, report)
        self.assertIs(caught.exception, first)
        self.assertEqual(attempted, ["ValueError: original observation refused"])
        self.assertIn("OSError", first.__notes__[0])

    def test_first_reporting_failure_is_not_success(self):
        with self.assertRaisesRegex(OSError, "storage"):
            O.record_local_observation(lambda: None, lambda _: (_ for _ in ()).throw(OSError("storage")))

    def test_original_external_navigation_and_recovery_controls(self):
        names = O.reference_navigation_self_test()
        self.assertIn("actual-observer-recovery-sequence-original-generation", names)
        self.assertIn("old-generation-reconciliation-remains-refused", names)


class PaletteAnnouncementControls(unittest.TestCase):
    """Execute the real observer functions without importing GI or running AT."""
    def observer(self, directory, spoken):
        source = Path(__file__).with_name("svg-input-orca.py").read_text()
        tree = ast.parse(source)
        selected = {"speech_log_offset", "wait_for_speech", "open_command_palette"}
        module = ast.Module(body=[node for node in tree.body
                                  if isinstance(node, ast.FunctionDef) and node.name in selected], type_ignores=[])
        log = directory / "palette.orca-debug.log"
        log.write_text("SPEECH OUTPUT: Command palette dialog\n")
        calls = []
        class Clock:
            now = 0
            def time(self):
                return self.now
            def sleep(self, seconds):
                self.now += seconds
        def key(value):
            calls.append(("key", value))
            with log.open("a") as stream:
                stream.write(spoken)
        namespace = {"os": os, "time": Clock(), "output": str(directory / "palette"),
                     "key": key, "find": lambda *a, **k: calls.append(("find", a, k)),
                     "wait_for_focus": lambda *a, **k: calls.append(("focus", a, k))}
        exec(compile(module, "svg-input-orca.py selected functions", "exec"), namespace)
        return namespace, calls, log

    def test_palette_uses_fresh_speech_and_actual_initial_dialog_focus(self):
        with tempfile.TemporaryDirectory() as directory:
            namespace, calls, log = self.observer(Path(directory), "SPEECH OUTPUT: Command palette dialog\n")
            start = log.stat().st_size
            receipt = namespace["open_command_palette"]()
            self.assertEqual(receipt, {"name": "Command palette", "role": "dialog",
                                       "initialFocus": "dialog", "speechAfter": start})
            self.assertEqual(calls, [("key", "Return"),
                                    ("find", ("dialog",), {"name": "Command palette"}),
                                    ("focus", ("Command palette",), {"role": "dialog", "dom_role": "dialog"})])

    def test_palette_refuses_stale_missing_role_and_debug_only_speech(self):
        for spoken in ["", "SPEECH OUTPUT: Command palette\n", "DEBUG: Command palette dialog\n"]:
            with self.subTest(spoken=spoken), tempfile.TemporaryDirectory() as directory:
                namespace, _, _ = self.observer(Path(directory), spoken)
                with self.assertRaisesRegex(RuntimeError, "expected speech output"):
                    namespace["open_command_palette"]()

    def test_actual_dialog_focus_requires_fresh_named_dom_and_atspi_agreement(self):
        from types import SimpleNamespace
        source = ast.parse(Path(__file__).with_name("svg-input-orca.py").read_text())
        function = next(node for node in source.body if isinstance(node, ast.FunctionDef)
                        and node.name == "wait_for_focus")
        for mutant in [None, "wrong-dom-role", "wrong-at-role", "stale-dom", "document-blurred"]:
            with self.subTest(mutant=mutant), tempfile.TemporaryDirectory() as directory:
                namespace, _, _ = self.observer(Path(directory), "")
                value = {"schema": "fsgg.orca-browser-dom/v1", "browserFamily": "chromium",
                         "sampleSequence": 1, "sampledAt": "fixture", "sampledAtUnixMs": 0,
                         "observation": {"documentHasFocus": mutant != "document-blurred",
                                         "activeElement": {"role": "button" if mutant == "wrong-dom-role" else "dialog",
                                                           "ariaLabel": "Command palette"}}}
                if mutant == "stale-dom":
                    value["sampledAtUnixMs"] = -3000
                Path(namespace["output"] + ".browser-dom.json").write_text(json.dumps(value))
                node = SimpleNamespace(get_state_set=lambda: SimpleNamespace(contains=lambda _: True),
                                       get_name=lambda: "Command palette",
                                       get_role_name=lambda: "push button" if mutant == "wrong-at-role" else "dialog")
                namespace.update(json=json, walk=lambda _: [node], focused=lambda: None,
                                 Atspi=SimpleNamespace(get_desktop=lambda _: None,
                                                       StateType=SimpleNamespace(FOCUSED=1)))
                exec(compile(ast.Module(body=[function], type_ignores=[]), "actual focus observer", "exec"), namespace)
                with patch.dict(os.environ, {"SVG_ORCA_BROWSER_FAMILY": "chromium"}):
                    if mutant is None:
                        self.assertIs(namespace["wait_for_focus"]("Command palette", role="dialog", dom_role="dialog"), node)
                    else:
                        with self.assertRaisesRegex(RuntimeError, "focus was not restored"):
                            namespace["wait_for_focus"]("Command palette", role="dialog", dom_role="dialog", timeout=.2)

    def test_palette_focus_failure_cannot_be_replaced_by_matching_speech(self):
        with tempfile.TemporaryDirectory() as directory:
            namespace, _, _ = self.observer(Path(directory), "SPEECH OUTPUT: Command palette dialog\n")
            def wrong_focus(*args, **kwargs):
                raise RuntimeError("wrong actual focus")
            namespace["wait_for_focus"] = wrong_focus
            with self.assertRaisesRegex(RuntimeError, "wrong actual focus"):
                namespace["open_command_palette"]()


if __name__ == "__main__":
    unittest.main()
