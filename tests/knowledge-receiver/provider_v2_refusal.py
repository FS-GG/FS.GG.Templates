"""Actual older installed producer must reject v2 receiver descriptors before effects."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess

from receiver import ROOT, inventory, snapshot


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--command-json', required=True)
    parser.add_argument('--public-archive', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    out = args.output.resolve()
    if out.exists():
        raise SystemExit('Refuse existing evidence directory')
    out.mkdir(parents=True)
    command = json.loads(args.command_json)
    os.environ.update(DOTNET_PROCESSOR_COUNT='1', DOTNET_CLI_HOME=str(out / 'dotnet-home'), DOTNET_CLI_TELEMETRY_OPTOUT='1')
    receipt = {'schema': 'fsgg.knowledge-provider-v2-legacy-refusal/1', 'publishedPositiveAcceptance': False,
               'actualPublicProducerVersion': '2.0.3', 'publicArchiveSha256': hashlib.sha256(args.public_archive.read_bytes()).hexdigest(),
               'command': command, 'rows': []}
    for row in inventory():
        descriptor = (ROOT / row['descriptor']).read_bytes()
        assert b'contractVersion: "2.0.0"' in descriptor
        for lifecycle in ('none', 'sdd', 'typed-sdd', 'spec-kit'):
            root = out / (row['provider'] + '-' + lifecycle)
            (root / '.fsgg').mkdir(parents=True)
            (root / '.fsgg/providers.yml').write_bytes(descriptor)
            (root / 'authored.txt').write_text('Existing caller-owned bytes\n')
            before = snapshot(root)
            result = subprocess.run(command + ['scaffold', '--root', str(root), '--provider', row['provider'], '--param', 'lifecycle=' + lifecycle, '--param', 'productName=KnowledgeReceiver', '--no-update', '--json'], capture_output=True, text=True, timeout=60)
            report = json.loads(result.stdout)
            assert result.returncode != 0 and report['outcome'] != 'succeeded', report
            assert any('contract' in str(d).lower() and 'unsupported' in str(d).lower() for d in report['diagnostics']), report
            assert snapshot(root) == before, 'Old client wrote workspace before rejecting v2'
            assert not (root / '.fsgg/knowledge').exists()
            receipt['rows'].append({'provider': row['provider'], 'lifecycle': lifecycle, 'descriptorSha256': hashlib.sha256(descriptor).hexdigest(), 'exit': result.returncode, 'diagnostics': report['diagnostics'], 'allOriginalBytesPreserved': True, 'addedPaths': []})
    assert not (out / 'dotnet-home/.templateengine').exists(), 'Old client invoked template installation'
    (out / 'receipt.json').write_text(json.dumps(receipt, indent=2) + '\n')
    print('PASS 24 actual public 2.0.3 v2-descriptor refusals before workspace/template effects')


if __name__ == '__main__':
    main()
