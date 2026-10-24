"""Fail-closed raw finding consumer; source/DB authenticity belongs to native custody."""
import json
from pathlib import Path
import sys


def require(value, message):
    if not value:
        raise ValueError(message)


def parse(provider, raw, expected_go_db=None):
    require(0 < len(raw) <= 8*1048576, 'missing/oversize security output')
    text = raw.decode('utf-8')
    if provider in ('typescript-cli', 'javascript-cli'):
        report = json.loads(text)
        require(report.get('auditReportVersion') == 2, 'unsupported npm audit report')
        require(report.get('vulnerabilities') == {}, 'npm reported vulnerabilities')
        counts = report['metadata']['vulnerabilities']
        require(counts.get('total') == 0 and all(type(value) is int and value == 0 for value in counts.values()),
                'npm vulnerability counts nonzero/malformed')
    elif provider == 'rust-cli':
        report = json.loads(text)
        vulnerabilities = report['vulnerabilities']
        require(vulnerabilities.get('found') is False and type(vulnerabilities.get('count')) is int
                and vulnerabilities['count'] == 0 and vulnerabilities.get('list') == [],
                'RustSec reported vulnerabilities or incomplete report')
        warnings = report.get('warnings')
        require(isinstance(warnings, dict) and all(isinstance(values, list) and not values for values in warnings.values()),
                'RustSec reported warning or incomplete report')
    elif provider == 'go-cli':
        decoder = json.JSONDecoder()
        messages = []
        rest = text.strip()
        while rest:
            value, position = decoder.raw_decode(rest)
            require(isinstance(value, dict) and len(value) == 1 and len(messages) < 65536,
                    'malformed/oversize Go message stream')
            messages.append(value)
            rest = rest[position:].lstrip()
        require(messages and set(messages[0]) == {'config'}, 'missing Go configuration')
        config = messages[0]['config']
        require(config.get('protocol_version') == 'v1.0.0' and config.get('scanner_name') == 'govulncheck'
                and config.get('scanner_version') == 'v1.9.0' and config.get('go_version') == 'go1.27.1'
                and config.get('scan_mode') == 'source', 'unexpected Go scanner/toolchain/protocol')
        require(expected_go_db is not None and config.get('db') == expected_go_db, 'Go database identity differs')
        for index, message in enumerate(messages):
            require(set(message).issubset({'config', 'progress', 'SBOM', 'osv', 'finding'}), 'unknown Go message kind')
            require(index == 0 or 'config' not in message, 'duplicate Go configuration')
            # OSV entries can describe versions not in use; every actual finding
            # blocks, including module/package findings with no called symbol.
            require('finding' not in message, 'Go reported vulnerability finding')
    else:
        raise ValueError('closed four-provider security consumer required')


def main(provider, target, expected_go_db=None):
    target = Path(target)
    for operation in ('security', 'evidence', 'release'):
        path = target / 'artifacts' / (operation + '-work') / 'security-audit.json'
        require(path.is_file() and not path.is_symlink(), 'missing/linked actual raw report')
        with path.open('rb') as stream:
            raw = stream.read(8*1048576 + 1)
        parse(provider, raw, expected_go_db)
    print('all three original raw scanner reports contain zero reported findings; native custody still required')


if __name__ == '__main__':
    main(*sys.argv[1:])
