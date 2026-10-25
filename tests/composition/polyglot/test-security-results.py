"""Inert raw scanner format fixtures; no scanner, native or product invocation."""
import importlib.util
import json
from pathlib import Path
import unittest
import tempfile

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
                  'scanner_version': version, 'go_version': 'go1.27.3', 'scan_mode': 'source', 'scan_level': 'symbol', 'db': 'file:///synthetic-db'}}
        messages = [config,
                    {'SBOM': {'go_version': 'go1.27.3', 'roots': ['example.org/synthetic'],
                              'modules': [{'path': 'example.org/synthetic'}, {'path': 'stdlib', 'version': 'v1.27.3'}]}},
                    {'progress': {'message': 'synthetic fetching observation'}},
                    {'progress': {'message': 'synthetic checking observation'}}]
        if finding is not None:
            messages.append({'finding': finding})
        return ('\n'.join(json.dumps(message) for message in messages)).encode()
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
        checker.parse('go-cli', self.go(), 'file:///synthetic-db', 'example.org/synthetic')
    def test_go_module_only_finding_refuses(self):
        with self.assertRaisesRegex(ValueError, 'finding'):
            checker.parse('go-cli', self.go({'osv': 'GO-SYNTHETIC', 'trace': [{'module': 'synthetic', 'version': 'v1.0.0'}]}), 'file:///synthetic-db', 'example.org/synthetic')
    def test_go_wrong_database_refuses(self):
        with self.assertRaisesRegex(ValueError, 'database'):
            checker.parse('go-cli', self.go(), 'file:///other-db', 'example.org/synthetic')
    def test_go_wrong_scanner_refuses(self):
        with self.assertRaises(ValueError):
            checker.parse('go-cli', self.go(version='v1.8.0'), 'file:///synthetic-db', 'example.org/synthetic')
    def test_partial_stream_refuses(self):
        with self.assertRaises(ValueError):
            checker.parse('go-cli', self.go() + b'\n{"finding":', 'file:///synthetic-db', 'example.org/synthetic')

    def test_duplicate_vulnerability_key_refuses(self):
        with self.assertRaisesRegex(ValueError, 'duplicate'):
            checker.parse('typescript-cli', b'{"auditReportVersion":2,"vulnerabilities":{"bad":{}},"vulnerabilities":{},"metadata":{"vulnerabilities":{"total":0}}}')
    def test_duplicate_nested_count_refuses(self):
        with self.assertRaisesRegex(ValueError, 'duplicate'):
            checker.parse('typescript-cli', b'{"auditReportVersion":2,"vulnerabilities":{},"metadata":{"vulnerabilities":{"total":1,"total":0}}}')
    def test_duplicate_go_configuration_field_refuses(self):
        raw = self.go().replace(b'"scanner_version": "v1.9.0"', b'"scanner_version":"wrong","scanner_version":"v1.9.0"')
        with self.assertRaisesRegex(ValueError, 'duplicate'):
            checker.parse('go-cli', raw, 'file:///synthetic-db', 'example.org/synthetic')
    def test_nonfinite_values_refuse(self):
        for value in (b'NaN', b'Infinity', b'-Infinity', b'1e999'):
            with self.subTest(value=value), self.assertRaisesRegex(ValueError, 'nonfinite'):
                checker.parse('typescript-cli', self.node().replace(b'"total": 0', b'"total": ' + value))
    def test_go_config_only_refuses(self):
        with self.assertRaisesRegex(ValueError, 'SBOM'):
            checker.parse('go-cli', self.go().split(b'\n')[0], 'file:///synthetic-db', 'example.org/synthetic')
    def test_go_source_progress_absent_refuses(self):
        raw = b'\n'.join(self.go().split(b'\n')[:2])
        with self.assertRaisesRegex(ValueError, 'progress'):
            checker.parse('go-cli', raw, 'file:///synthetic-db', 'example.org/synthetic')
    def test_go_wrong_source_root_refuses(self):
        with self.assertRaisesRegex(ValueError, 'roots'):
            checker.parse('go-cli', self.go(), 'file:///synthetic-db', 'example.org/wrong')
    def test_go_duplicate_sbom_refuses(self):
        raw = self.go() + b'\n' + self.go().split(b'\n')[1]
        with self.assertRaisesRegex(ValueError, 'SBOM'):
            checker.parse('go-cli', raw, 'file:///synthetic-db', 'example.org/synthetic')

    def test_actual_single_product_guard_rejects_go_module_finding(self):
        with tempfile.TemporaryDirectory(prefix='synthetic-product-security-') as temporary:
            root = Path(temporary)
            (root / 'go.mod').write_text('module example.org/synthetic\n\ngo 1.27.3\n')
            report = root / 'security-audit.json'
            report.write_bytes(self.go({'osv': 'GO-SYNTHETIC', 'trace': [{'module': 'synthetic'}]}))
            with self.assertRaisesRegex(ValueError, 'finding'):
                checker.single('go-cli', str(report), 'file:///synthetic-db')

    def test_non_json_unicode_stream_separator_refuses(self):
        with self.assertRaises(ValueError):
            checker.parse('go-cli', self.go().replace(b'\n', b'\xc2\xa0', 1), 'file:///synthetic-db', 'example.org/synthetic')


if __name__ == '__main__':
    unittest.main()
