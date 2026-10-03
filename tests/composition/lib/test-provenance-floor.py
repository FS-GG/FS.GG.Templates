#!/usr/bin/env python3
"""Pure causal checks for the real floor assertion and first-loop shell integration."""
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[3]
spec = importlib.util.spec_from_file_location("provenance_floor", Path(__file__).with_name("provenance-floor.py"))
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class FloorTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.work = Path(self.temp.name)
        self.descriptor = self.work / "providers.yml"
        self.descriptor.write_bytes((ROOT / "providers/console.providers.yml").read_bytes())
        self.provenance = self.work / "provenance.json"
        self.provenance.write_text(json.dumps({"requiredMinimumCliVersion": "2.1.0"}))

    def check(self):
        return module.check(self.descriptor, self.provenance, "console", ROOT)

    def test_current_floor_joins_the_selected_descriptor(self):
        self.assertEqual("2.1.0", self.check())

    def test_old_and_ahead_provenance_both_refuse(self):
        for value in ("1.4.0-preview.1", "2.2.0", None, 2.1):
            self.provenance.write_text(json.dumps({"requiredMinimumCliVersion": value}))
            with self.assertRaisesRegex(ValueError, "provenance requiredMinimumCliVersion"):
                self.check()

    def test_historical_descriptor_keeps_its_actual_floor(self):
        text = self.descriptor.read_text().replace('contractVersion: "2.0.0"', 'contractVersion: "1.1.0"').replace('version: "2.1.0"', 'version: "1.4.0-preview.1"')
        self.descriptor.write_text(text)
        self.provenance.write_text('{"requiredMinimumCliVersion":"1.4.0-preview.1"}')
        self.assertEqual("1.4.0-preview.1", self.check())

    def test_missing_ambiguous_and_wrong_provider_descriptor_refuse(self):
        text = self.descriptor.read_text()
        for changed in (text.replace('      version: "2.1.0"\n', ''),
                        text.replace('      version: "2.1.0"', '      version: "2.1.0"\n      version: "2.1.0"'),
                        text.replace('  - name: console', '  - name: web')):
            self.descriptor.write_text(changed)
            with self.assertRaises(Exception):
                self.check()

    def test_duplicate_provenance_key_refuses(self):
        self.provenance.write_text('{"requiredMinimumCliVersion":"2.1.0","requiredMinimumCliVersion":"2.1.0"}')
        with self.assertRaisesRegex(ValueError, "duplicate provenance key"):
            self.check()

    def test_real_shell_loop_passes_current_floor_and_keeps_reports_before_next_scaffold(self):
        # Stop at the second scaffold: the first floor assertion must pass, but no typed authoring,
        # compiler, product build or lifecycle completion is allowed in this pure integration check.
        for provider in ("console", "fable-bindings", "fable-game", "web"):
            work = self.work / provider
            work.mkdir()
            stub = work / "fsgg-sdd"
            stub.write_text('''#!/usr/bin/env python3
import json, os, pathlib, sys
calls=pathlib.Path(os.environ["CALLS"])
count=int(calls.read_text())+1 if calls.exists() else 1
calls.write_text(str(count))
if count != 1:
 print(json.dumps({"diagnostics":[{"id":"fixture.secondScaffold","message":"intentional pure stop"}]}));sys.exit(37)
args=sys.argv[1:]; root=pathlib.Path(args[args.index("--root")+1]); provider=args[args.index("--provider")+1]
p={"requiredMinimumCliVersion":os.environ.get("PROVENANCE_FLOOR","2.1.0"),"effectiveParameters":[{"key":"lifecycle","value":"none"}]}
(root/".fsgg/scaffold-provenance.json").write_text(json.dumps(p))
print(json.dumps({"outcome":"succeeded","scaffold":{"providerName":provider,"providerInvoked":True}}))
''')
            stub.chmod(0o755)
            env = dict(os.environ, PATH=str(work)+os.pathsep+os.environ["PATH"], CALLS=str(work/"calls"),
                       FSGG_COMPOSITION_DIAGNOSTICS=str(work/"kept"))
            script = '''set -euo pipefail
LANE_REPO_ROOT="$1"
. "$1/tests/composition/lib/lane-package.sh"
. "$1/tests/composition/lib/lifecycle-matrix.sh"
assert_provider_lifecycle_matrix "$2" "$3/archive.nupkg" "$3/matrix"
'''
            result = subprocess.run(["bash", "-c", script, "fixture", str(ROOT), provider, str(work)], env=env, text=True, capture_output=True)
            self.assertNotEqual(0, result.returncode)
            self.assertEqual("2", (work/"calls").read_text(), result.stderr)
            self.assertIn("fixture.secondScaffold", result.stderr)
            self.assertEqual("2.1.0", json.loads((work/"kept/none.provenance.json").read_text())["requiredMinimumCliVersion"])
            self.assertEqual((work/"matrix/none/.fsgg/providers.yml").read_bytes(), (work/"kept/none.providers.yml").read_bytes())
            (work/"calls").unlink()
            env["PROVENANCE_FLOOR"] = "1.4.0-preview.1"
            result = subprocess.run(["bash", "-c", script, "fixture", str(ROOT), provider, str(work)], env=env, text=True, capture_output=True)
            self.assertNotEqual(0, result.returncode)
            self.assertEqual("1", (work/"calls").read_text())
            self.assertIn("descriptor minimumFsggSdd.version='2.1.0'", result.stderr)
            self.assertIn('"requiredMinimumCliVersion": "1.4.0-preview.1"', result.stderr)

    def test_parent_log_pipeline_preserves_child_failure_and_stderr(self):
        text = (ROOT/"tests/composition/run.sh").read_text()
        begin = text.index('  if bash "$lane_script"')
        end = text.index('\ndone', begin)
        actual = text[begin:end]
        child = self.work / "lane.sh"
        child.write_text("echo actual-child-error >&2; exit 23\n")
        script = '''set -uo pipefail
lane=fixture; lane_script="$1"; WORKDIR="$2"
ok() { echo SHOULD-NOT-PASS; }
bad() { echo EXPECTED-FAILED-GATE; }
'''+actual
        result = subprocess.run(["bash", "-c", script, "fixture", str(child), str(self.work)], text=True, capture_output=True)
        self.assertIn("EXPECTED-FAILED-GATE", result.stdout)
        self.assertNotIn("SHOULD-NOT-PASS", result.stdout)
        self.assertEqual("actual-child-error\n", (self.work/"fixture-lifecycle.log").read_text())


if __name__ == "__main__":
    unittest.main()
