#!/usr/bin/env python3
"""Pure actual I/O/held-caller controls; typed policy runs in ProviderTool tests."""
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
HERE = Path(__file__).parent
SPEC = importlib.util.spec_from_file_location('current_d5_observations', HERE/'d5-current-public.py')
D5 = importlib.util.module_from_spec(SPEC); SPEC.loader.exec_module(D5)

class ObservationsTests(unittest.TestCase):
    def test_actual_runtime_caller_is_held_before_every_effect(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder); pins=root/'pins.json';pins.write_text(json.dumps(D5.PINS));out=root/'output';bins=root/'bin';bins.mkdir();sentinel=root/'launched'
            for name in ('dotnet','curl','git','go','sudo','unshare','npm'):
                p=bins/name;p.write_text('#!/bin/sh\necho launched >>"$SENTINEL"\nexit 91\n');p.chmod(0o700)
            env={**os.environ,'PATH':str(bins)+os.pathsep+os.environ['PATH'],'SENTINEL':str(sentinel)}
            for flag in ('--rehearsal','--full'):
                r=subprocess.run(['bash',str(HERE/'verify-svg-release-d5-current-public.sh'),str(pins),str(out),flag],env=env,capture_output=True,text=True)
                self.assertEqual(r.returncode,3,r.stderr);self.assertIn('admission None',r.stderr);self.assertFalse(out.exists());self.assertFalse(sentinel.exists())
            r=subprocess.run(['bash',str(HERE/'verify-svg-release-d5-current-public.sh'),str(pins),str(out),'--preflight-only'],env=env,capture_output=True,text=True)
            self.assertEqual(r.returncode,0,r.stderr);self.assertIn('typed qualification NOT RUN',r.stdout);self.assertFalse(sentinel.exists())

    def test_actual_snapshot_caller_observes_canonical_mutation_deletion_and_refused_work(self):
        with tempfile.TemporaryDirectory() as folder:
            parent=Path(folder);root=parent/'receiver';canonical=root/'work/d5-default/specification.md';canonical.parent.mkdir(parents=True);canonical.write_text('owned')
            (root/'models').mkdir();(root/'models/rules.md').write_text('model');(root/'Directory.Build.props').write_text('config');(root/'AGENTS.md').write_text('owner')
            def snapshot(name):
                p=parent/(name+'.json');subprocess.run(['python3',str(HERE/'d5-current-public.py'),'snapshot',str(root),str(p)],check=True,capture_output=True);return json.loads(p.read_text())
            before=snapshot('before');canonical.write_text('corrupt');self.assertNotEqual(snapshot('mutated'),before)
            canonical.unlink();self.assertNotEqual(snapshot('deleted'),before)
            canonical.write_text('owned');refused=root/'work/d5-refused/specification.md';refused.parent.mkdir();refused.write_text('partial');self.assertNotEqual(snapshot('refused'),before)
            self.assertIn('work/d5-refused/specification.md',snapshot('present'))

    def test_argument_observation_rejects_malformed_or_missing_plan(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'args.json';command=['python3',str(HERE/'d5-current-public.py'),'arguments',str(path)]
            self.assertNotEqual(subprocess.run(command,capture_output=True).returncode,0)
            for bad in ('{}','[]','not-json','["valid",null]'):
                path.write_text(bad);r=subprocess.run(command,capture_output=True);self.assertNotEqual(r.returncode,0);self.assertEqual(r.stdout,b'')
            path.write_text('["typed-sdd","author","--root","/receiver"]');r=subprocess.run(command,capture_output=True,check=True);self.assertEqual(r.stdout,b'typed-sdd\0author\0--root\0/receiver\0')

    def test_duplicate_input_and_snapshot_inside_receiver_are_refused(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);p=root/'pins.json';p.write_text('{"schema":"one","schema":"two"}')
            with self.assertRaises(ValueError):D5.read_json(p)
            r=subprocess.run(['python3',str(HERE/'d5-current-public.py'),'snapshot',str(root),str(root/'snapshot.json')],capture_output=True)
            self.assertNotEqual(r.returncode,0);self.assertFalse((root/'snapshot.json').exists())

if __name__=='__main__':unittest.main()
