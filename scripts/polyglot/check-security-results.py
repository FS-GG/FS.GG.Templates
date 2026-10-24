"""Repository consumer of the single authored product finding checker."""
import importlib.util
from pathlib import Path
import sys

source = Path(__file__).resolve().parents[2] / 'template/polyglot-common/security-result.py'
spec = importlib.util.spec_from_file_location('polyglot_security_result', source)
checker = importlib.util.module_from_spec(spec)
spec.loader.exec_module(checker)
parse = checker.parse
single = checker.single

if __name__ == '__main__':
    checker.main(*sys.argv[1:])
