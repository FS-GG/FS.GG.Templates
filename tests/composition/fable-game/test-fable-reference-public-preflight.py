#!/usr/bin/env python3
"""Synthetic input controls; preflight cannot install, build or query a feed."""
from pathlib import Path
import os
import subprocess
import tempfile
import unittest

HERE = Path(__file__).resolve().parent

class PublicReferencePreflightTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name); self.effect = self.root / 'effect'
        stub = self.root / 'dotnet'; stub.write_text('#!/bin/sh\ntouch "' + str(self.effect) + '"\nexit 99\n'); stub.chmod(0o700)
        self.env = {**os.environ, 'DOTNET_HOST_PATH': str(stub), 'QUINT_BIN': str(stub)}

    def args(self, mode='templates'):
        args = ['--mode', mode, '--template-version', '0.18.1', '--sha256', 'a'*64,
                '--descriptor-sha256', 'b'*64, '--source-revision', 'c'*40,
                '--tag-revision', 'c'*40, '--sdd-version', '2.1.0', '--sdd-sha256', 'd'*64,
                '--sdd-source-revision', 'e'*40, '--evidence-dir', str(self.root/'fresh'), '--preflight-only']
        if mode == 'full': args += ['--wizard-version', '0.16.0', '--wizard-sha256', 'f'*64, '--wizard-source-revision', 'a'*40]
        return args

    def run_preflight(self, args, expected):
        result = subprocess.run(['bash', str(HERE/'verify-fable-reference-public.sh'), *args], env=self.env, capture_output=True, text=True)
        self.assertEqual(result.returncode == 0, expected, result.stderr)
        self.assertFalse(self.effect.exists()); self.assertFalse((self.root/'fresh').exists())

    def test_templates_only_is_independent_of_wizard(self): self.run_preflight(self.args(), True)
    def test_full_requires_selected_successor_inputs(self): self.run_preflight(self.args('full'), True)
    def test_historical_version_refused(self): self.run_preflight([a.replace('0.18.1', '0.18.0') for a in self.args()], False)
    def test_old_wizard_refused(self): self.run_preflight([a.replace('0.16.0', '0.15.0') for a in self.args('full')], False)
    def test_templates_mode_refuses_wizard_claim(self): self.run_preflight(self.args()+['--wizard-version', '0.16.0'], False)
    def test_unknown_mode_refused(self): self.run_preflight(self.args('unknown'), False)
    def test_missing_full_wizard_refused(self):
        args = self.args(); args[1] = 'full'; self.run_preflight(args, False)
    def test_different_tag_source_refused(self): self.run_preflight([a.replace('c'*40, 'b'*40) if i and self.args()[i-1]=='--tag-revision' else a for i,a in enumerate(self.args())], False)
    def test_source_newline_refused(self): self.run_preflight([a+'\n' if a=='c'*40 else a for a in self.args()], False)
    def test_duplicate_version_refused(self): self.run_preflight(self.args()+['--template-version', '0.18.1'], False)

if __name__ == '__main__': unittest.main()
