#!/usr/bin/env python3
"""Actual cleanup keeps child status and report bytes when a generated lifecycle fails."""
import json
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[3]
class DiagnosticsTests(unittest.TestCase):
    def test_success_and_failure_reports_survive_cleanup_with_original_status(self):
        for status in (0, 23):
            with tempfile.TemporaryDirectory() as temporary:
                root=Path(temporary);work=root/'work';reports=work/'product/reports';reports.mkdir(parents=True)
                source=json.dumps({'outcome':'blocked' if status else 'succeeded','diagnostics':[{'severity':'error','id':'actual.refusal'}] if status else []})+'\n'
                (reports/'sdd-evidence.json').write_text(source)
                (reports/'unrelated-secret.txt').write_text('excluded')
                dest=root/'retained'
                script='. "$1/tests/composition/lib/lifecycle-diagnostics.sh"; export FSGG_COMPOSITION_DIAGNOSTICS="$3"; trap \'cleanup_lifecycle_product "$2" "$?"\' EXIT; exit "$4"'
                r=subprocess.run(['bash','-c',script,'fixture',str(ROOT),str(work),str(dest),str(status)],capture_output=True,text=True)
                self.assertEqual(status,r.returncode,r.stderr);self.assertFalse(work.exists())
                self.assertEqual(source,(dest/'product-lifecycle/sdd-evidence.json').read_text())
                self.assertEqual(status,json.loads((dest/'product-lifecycle/child-status.json').read_text())['exitCode'])
                self.assertFalse((dest/'product-lifecycle/unrelated-secret.txt').exists())
                if status:self.assertIn('actual.refusal',r.stderr)
    def test_unsafe_report_refuses_retention_and_preserves_failure(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary);work=root/'work';reports=work/'product/reports';reports.mkdir(parents=True)
            outside=root/'outside';outside.write_text('outside');(reports/'sdd-evidence.json').symlink_to(outside)
            script='. "$1/tests/composition/lib/lifecycle-diagnostics.sh"; export FSGG_COMPOSITION_DIAGNOSTICS="$3"; trap \'cleanup_lifecycle_product "$2" "$?"\' EXIT; exit 0'
            r=subprocess.run(['bash','-c',script,'fixture',str(ROOT),str(work),str(root/'retained')],capture_output=True,text=True)
            self.assertNotEqual(0,r.returncode);self.assertEqual('outside',outside.read_text())
    def test_fifo_report_refuses_before_any_read_and_preserves_child_status(self):
        import os
        for status in (0,23):
            with tempfile.TemporaryDirectory() as temporary:
                root=Path(temporary);work=root/'work';reports=work/'product/reports';reports.mkdir(parents=True)
                os.mkfifo(reports/'sdd-evidence.json')
                script=' . "$1/tests/composition/lib/lifecycle-diagnostics.sh"; export FSGG_COMPOSITION_DIAGNOSTICS="$3"; trap \'cleanup_lifecycle_product "$2" "$?"\' EXIT; exit "$4"'
                r=subprocess.run(['bash','-c',script,'fixture',str(ROOT),str(work),str(root/'retained'),str(status)],capture_output=True,text=True,timeout=5)
                self.assertEqual(status if status else 1,r.returncode);self.assertIn('unsafe/oversized',r.stderr)
                self.assertFalse(work.exists());self.assertFalse((root/'retained/product-lifecycle/sdd-evidence.json').exists())
    def test_installed_source_resolver_uses_observed_apphost_version(self):
        import os
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary);tool=root/'tools';tool.mkdir();apphost=tool/'fsgg-sdd'
            apphost.write_text('#!/bin/sh\nprintf "2.1.0\\n"\n');apphost.chmod(0o755)
            assembly=tool/'.store/fs.gg.sdd.cli/2.1.0/fs.gg.sdd.cli/2.1.0/tools/net10.0/any/FS.GG.SDD.Commands.dll'
            assembly.parent.mkdir(parents=True);assembly.write_text('fixture');(assembly.parent/'FS.GG.SDD.Cli.dll').write_text('fixture')
            script='. "$1/tests/composition/lib/sdd-owner-skills.sh"; sdd_commands_assembly'
            env=dict(os.environ,PATH=str(tool)+os.pathsep+os.environ['PATH'])
            def run(): return subprocess.run(['bash','-c',script,'fixture',str(ROOT)],env=env,capture_output=True,text=True)
            r=run();self.assertEqual(0,r.returncode,r.stderr);self.assertEqual(str(assembly),r.stdout.strip())
            assembly.unlink();self.assertNotEqual(0,run().returncode)
            apphost.write_text('#!/bin/sh\nprintf "unknown\\n"\n');self.assertNotEqual(0,run().returncode)
if __name__=='__main__':unittest.main()
