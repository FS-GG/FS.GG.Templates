"""Publication refusal for the new pack while genuine same-archive qualification is held.
Legacy archives have no new provider payload and retain their existing release gates.
"""
from pathlib import Path
import sys
import zipfile

# No native operation, receipt or admission is invented by source CI.
POLYGLOT_QUALIFICATION_ADMISSION = None

def requires_qualification(archive):
    with zipfile.ZipFile(archive) as package:
        return any(name.startswith("content/templates/fs-gg-" + language + "-cli/")
                   for name in package.namelist() for language in ("typescript", "javascript", "rust", "go"))

def main(argv):
    if len(argv) != 1:
        raise ValueError("one immutable archive required")
    if requires_qualification(Path(argv[0])):
        raise ValueError("polyglot publication held: no independently accepted genuine four-product qualification of this SAME archive; source/ordinary CI is insufficient")
    print("legacy archive: existing release gates remain required")
    return 0

if __name__ == "__main__":
    try:
        raise SystemExit(main(sys.argv[1:]))
    except ValueError as error:
        print(str(error), file=sys.stderr)
        raise SystemExit(3)
