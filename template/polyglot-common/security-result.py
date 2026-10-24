"""Fail-closed raw finding consumer; source/DB authenticity belongs to native custody."""
import json
import math
from pathlib import Path
import sys


def require(value, message):
    if not value:
        raise ValueError(message)


def object_without_duplicates(pairs):
    result = {}
    for key, value in pairs:
        require(key not in result, 'duplicate raw JSON key: ' + key)
        result[key] = value
    return result


def finite_float(value):
    number = float(value)
    require(math.isfinite(number), 'nonfinite raw JSON value')
    return number


def refuse_constant(value):
    raise ValueError('nonfinite raw JSON value: ' + value)


def decoder():
    return json.JSONDecoder(object_pairs_hook=object_without_duplicates,
                            parse_constant=refuse_constant, parse_float=finite_float)


def parse(provider, raw, expected_go_db=None, expected_go_module=None):
    require(0 < len(raw) <= 8*1048576, 'missing/oversize security output')
    text = raw.decode('utf-8')
    if provider in ('typescript-cli', 'javascript-cli'):
        report = decoder().decode(text)
        require(report.get('auditReportVersion') == 2, 'unsupported npm audit report')
        require(report.get('vulnerabilities') == {}, 'npm reported vulnerabilities')
        counts = report['metadata']['vulnerabilities']
        require(counts.get('total') == 0 and all(type(value) is int and value == 0 for value in counts.values()),
                'npm vulnerability counts nonzero/malformed')
    elif provider == 'rust-cli':
        report = decoder().decode(text)
        vulnerabilities = report['vulnerabilities']
        require(vulnerabilities.get('found') is False and type(vulnerabilities.get('count')) is int
                and vulnerabilities['count'] == 0 and vulnerabilities.get('list') == [],
                'RustSec reported vulnerabilities or incomplete report')
        warnings = report.get('warnings')
        require(isinstance(warnings, dict) and all(isinstance(values, list) and not values for values in warnings.values()),
                'RustSec reported warning or incomplete report')
    elif provider == 'go-cli':
        reader = decoder()
        messages = []
        rest = text.strip()
        while rest:
            value, position = reader.raw_decode(rest)
            require(isinstance(value, dict) and len(value) == 1 and len(messages) < 65536,
                    'malformed/oversize Go message stream')
            messages.append(value)
            rest = rest[position:].lstrip()
        require(messages and set(messages[0]) == {'config'}, 'missing Go configuration')
        config = messages[0]['config']
        require(config.get('protocol_version') == 'v1.0.0' and config.get('scanner_name') == 'govulncheck'
                and config.get('scanner_version') == 'v1.9.0' and config.get('go_version') == 'go1.27.1'
                and config.get('scan_mode') == 'source' and config.get('scan_level') == 'symbol', 'unexpected Go scanner/toolchain/protocol')
        require(expected_go_db is not None and config.get('db') == expected_go_db, 'Go database identity differs')
        # The selected source path always emits SBOM after loading matched source
        # packages. This is coverage evidence, NOT an invented final/end marker.
        sboms = [message['SBOM'] for message in messages if 'SBOM' in message]
        require(len(sboms) == 1 and isinstance(sboms[0], dict), 'missing/duplicate Go source SBOM')
        sbom = sboms[0]
        require(expected_go_module is not None and sbom.get('go_version') == 'go1.27.1'
                and sbom.get('roots') == [expected_go_module], 'Go source roots/toolchain differ')
        modules = sbom.get('modules')
        require(isinstance(modules, list) and len(modules) == 2
                and all(isinstance(module, dict) and isinstance(module.get('path'), str) for module in modules),
                'Go stdlib-only module inventory differs')
        require(len({module['path'] for module in modules}) == 2
                and {module['path']: module.get('version', '') for module in modules}
                == {expected_go_module: '', 'stdlib': 'v1.27.1'}, 'Go module identity differs')
        progress = [message['progress'] for message in messages if 'progress' in message]
        # Selected Source emits fetching/checking progress around DB resolution.
        # Neither progress nor SBOM is a final marker; original zero exit and
        # complete stream/file custody are still indispensable at the native edge.
        require(len(progress) >= 2 and all(isinstance(item, dict) and isinstance(item.get('message'), str)
                and item['message'] for item in progress), 'incomplete Go source scan progress')
        for index, message in enumerate(messages):
            require(set(message).issubset({'config', 'progress', 'SBOM', 'osv', 'finding'}), 'unknown Go message kind')
            require(index == 0 or 'config' not in message, 'duplicate Go configuration')
            # OSV entries can describe versions not in use; every actual finding
            # blocks, including module/package findings with no called symbol.
            require('finding' not in message, 'Go reported vulnerability finding')
    else:
        raise ValueError('closed four-provider security consumer required')


def read_report(path):
    path = Path(path)
    require(path.is_file() and not path.is_symlink(), 'missing/linked actual raw report')
    with path.open('rb') as stream:
        return stream.read(8*1048576 + 1)


def go_module(root):
    path = Path(root) / 'go.mod'
    require(path.is_file() and not path.is_symlink() and path.stat().st_size <= 65536, 'missing/linked/oversize Go module')
    first = path.read_text().splitlines()[0]
    require(first.startswith('module ') and len(first.split()) == 2, 'explicit generated Go module required')
    return first.split()[1]


def single(provider, report, expected_go_db=None):
    # Supported selected interpreter is explicit, not an ambient Python fallback.
    require(sys.version_info[:3] == (3, 14, 8), 'qualified Python3.14.8 required')
    module = go_module(Path(report).parent) if provider == 'go-cli' else None
    parse(provider, read_report(report), expected_go_db, module)


def main(provider, target, expected_go_db=None):
    target = Path(target)
    module = go_module(target) if provider == 'go-cli' else None
    for operation in ('security', 'evidence', 'release'):
        path = target / 'artifacts' / (operation + '-work') / 'security-audit.json'
        parse(provider, read_report(path), expected_go_db, module)
    print('all three original raw scanner reports contain zero reported findings; native custody still required')


if __name__ == '__main__':
    if sys.argv[1] == '--single':
        single(*sys.argv[2:])
    else:
        main(*sys.argv[1:])
