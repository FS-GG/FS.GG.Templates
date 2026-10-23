#!/usr/bin/env python3
"""Inert tests of the maintained observer's actual current-reference functions.

No GI import, Node, browser, SDK, network, live unit or AT operation is selected.
The embedded companion's new JS handler controls are source-prepared separately.
"""
import copy
import importlib.util
import io
import json
from pathlib import Path
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
            O.write(directory / "journey.json", journey)
            activation = O.route_fixture()
            O.route_fixture_evidence(directory, activation)
            cleanup = {"disposition": "observed-empty", "unknown": [], "remaining": []}
            O.write(directory / "process-result.json", {"exit": 0, "firstCause": None, "cleanup": cleanup})
            names = ["orca.log", "orca-debug.log", "process-result.json", "source-qualification.json", "activation-provenance.json",
                     "owned-bus-route.json", "owned-bus-runtime.json", "session.conf", "accessibility.conf", "session-contract-state.json",
                     "session-budget.json", "journey.json", "current-public-at.json", "current-composition-plan.json", *O.FINISH_FILES, *O.BROWSER_FILES]
            receipt = {"schema": O.SCHEMA, "result": "passed", "templates": packet["templates"], "caller": preflight["caller"],
                       "producer": preflight["producer"], **journey, "currentPublicAt": identity, "keyboard": "xdotool-X11",
                       "speechBoundary": "Orca SPEECH OUTPUT", "physicalAudioHardware": "not-observed", "cleanup": cleanup,
                       "sourceQualificationSha256": O.digest(directory / "source-qualification.json"),
                       "localSaveStorage": "synthetic-in-memory", "durableSaveAcceptance": False, "providerMatrixAcceptance": False,
                       "nativeImeAcceptance": False, "whole4817Acceptance": False,
                       "evidenceSha256": {name: O.digest(directory / name) for name in names}}
            self.assertTrue(O.validate(receipt, packet, preflight, directory))
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


if __name__ == "__main__":
    unittest.main()
