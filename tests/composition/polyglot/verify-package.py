import json
from pathlib import Path
import sys
sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent))
from source_contract import validate_archive
if __name__ == "__main__":
    if len(sys.argv) != 3:
        raise SystemExit("usage: verify-package.py <source-root> <one-archive>")
    print(json.dumps(validate_archive(Path(sys.argv[1]), Path(sys.argv[2])), indent=2))
