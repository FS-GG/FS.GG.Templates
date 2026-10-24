"""Inert raw scanner format fixtures; no scanner, native or product invocation."""
import importlib.util
import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[3]
spec = importlib.util.spec_from_file_location('security_results', ROOT / 'scripts/polyglot/check-security-results.py')
checker = importlib.util.module_from_spec(spec)
spec.loader.exec_module(checker)


class SecurityResults(unittest.TestCase):
    def node(self, total=0):
        return json.dumps({'auditReportVersion': 2, 'vulnerabilities': {},
                           'metadata': {'vulnerabilities': {'total': total}}}).encode()
    def go(self, finding=None, version='v1.9.0'):
        config = {'config': {'protocol_version': 'v1.0.0', 'scanner_name': 'govulncheck',
                  'scanner_version': version, 'go_version': 'go1.27.1', 'scan_mode': 'source', 'db': 'file:///synthetic-db'}}
        return (json.dumps(config) + ('\n' + json.dumps({'finding': finding}) if finding is not None else '')).encode()
    def test_node_zero_findings(self):
        checker.parse('typescript-cli', self.node())
    def test_node_any_severity_refuses(self):
        with self.assertRaises(ValueError):
            checker.parse('javascript-cli', self.node(1))
    def test_missing_node_result_refuses(self):
        with self.assertRaises((ValueError, KeyError)):
            checker.parse('javascript-cli', b'{}')
    def test_rust_zero_findings(self):
        checker.parse('rust-cli', b'{"vulnerabilities":{"found":false,"count":0,"list":[]},"warnings":{}}')
    def test_rust_warning_refuses(self):
        with self.assertRaises(ValueError):
            checker.parse('rust-cli', b'{"vulnerabilities":{"found":false,"count":0,"list":[]},"warnings":{"yanked":[{}]}}')
    def test_go_zero_findings(self):
        checker.parse('go-cli', self.go(), 'file:///synthetic-db')
    def test_go_module_only_finding_refuses(self):
        with self.assertRaisesRegex(ValueError, 'finding'):
            checker.parse('go-cli', self.go({'osv': 'GO-SYNTHETIC', 'trace': [{'module': 'synthetic', 'version': 'v1.0.0'}]}), 'file:///synthetic-db')
    def test_go_wrong_database_refuses(self):
        with self.assertRaisesRegex(ValueError, 'database'):
            checker.parse('go-cli', self.go(), 'file:///other-db')
    def test_go_wrong_scanner_refuses(self):
        with self.assertRaises(ValueError):
            checker.parse('go-cli', self.go(version='v1.8.0'), 'file:///synthetic-db')
    def test_partial_stream_refuses(self):
        with self.assertRaises(ValueError):
            checker.parse('go-cli', self.go() + b'\n{"finding":', 'file:///synthetic-db')


if __name__ == '__main__':
    unittest.main()
