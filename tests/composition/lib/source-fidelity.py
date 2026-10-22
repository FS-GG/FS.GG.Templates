#!/usr/bin/env python3
"""Byte-fidelity helper for the template source-fidelity gate (FS.GG.Templates#729).

The .NET template engine runs a built-in, extension-keyed conditional processor over every file it
copies. For `*.c`/`*.h` that is C-style `#if`/`#elif`/`#else`/`#endif` processing, so a C source that
uses ordinary preprocessor blocks is silently rewritten on the way to a product. The packaged
`SvgFoundation/Examples/Wasm/guest/policy.c` lost its `POLICY_TRAP` / `POLICY_LOOP` /
`POLICY_MALFORMED` blocks that way (1308 -> 1130 bytes) in `bundle=complete` scaffolds.

Subcommands (all offline, standard library only):

  compare  --packaged DIR --scaffold DIR [--require REL ...]
      Compares every file the archive ships under DIR with the file the engine delivered at the same
      path in the scaffold. A file is graded byte-for-byte unless it is *legitimately* rewritten by
      the engine: its path or content carries the template source-name token (case-insensitive
      `FableGameWorkspace`), or it is simply not delivered (excluded by a modifier). Prints one
      `compared=… tokenized=… absent=…` summary line, then one line per mismatch. Exit 0 when there
      are no mismatches and every --require path was compared; 1 otherwise.

  seed     --in NUPKG --out NUPKG
      Copies an archive and injects a `.c` and a `.h` probe that carry every preprocessor directive
      the engine's C-style conditional recognises, into each packaged template that ships
      `SvgFoundation/`. The probe files make the gate cover the header half of the C family without
      adding a header to the product source tree.

  strip    --in NUPKG --out NUPKG
      Copies an archive and removes the `**/*.c` and `**/*.h` entries from `specialCustomOperations`
      in every packaged template.json. That is exactly the configuration this gate exists to
      prevent, so the result is the causal control: the gate must go red on it.
"""
import argparse
import json
import os
import sys
import zipfile

TOKEN = b"fablegameworkspace"  # compared against lower-cased content/paths
TEMPLATE_PREFIXES = (
    "content/templates/fs-gg-fable-game/",
    "content/templates/fs-gg-fable-game-legacy/",
)
SEED_DIR = "SvgFoundation/"
SEED_C = "SvgFoundation/fsgg729-seed.c"
SEED_H = "SvgFoundation/fsgg729-seed.h"

C_FAMILY = (".c", ".h", ".cc", ".cpp", ".cxx", ".hh", ".hpp", ".hxx", ".inl")

SEED_SOURCE = """\
/* FS.GG.Templates#729 byte-fidelity probe. This file exists only inside the gate's derived archive. */
#ifndef FSGG729_SEED_GUARD
#define FSGG729_SEED_GUARD

#if defined(FSGG729_ALPHA)
int fsgg729_alpha(void);
#elif defined(FSGG729_BETA)
int fsgg729_beta(void);
#else
int fsgg729_default(void);
#endif

#ifdef FSGG729_GAMMA
int fsgg729_gamma(void);
#endif

#ifndef FSGG729_DELTA
#define FSGG729_DELTA 1
#endif

#if 0
this block must survive verbatim
#endif

#endif /* FSGG729_SEED_GUARD */
"""


def walk(root):
    for base, dirs, files in os.walk(root):
        dirs.sort()
        for name in sorted(files):
            path = os.path.join(base, name)
            yield os.path.relpath(path, root).replace(os.sep, "/"), path


def read(path):
    with open(path, "rb") as handle:
        return handle.read()


def compare(args):
    compared = tokenized = absent = 0
    mismatches = []
    seen = set()
    c_family = []
    for rel, packaged_path in walk(args.packaged):
        if rel.startswith(".template.config/") or rel == ".template.config":
            continue
        scaffold_path = os.path.join(args.scaffold, rel)
        if not os.path.isfile(scaffold_path):
            absent += 1
            continue
        packaged = read(packaged_path)
        if TOKEN in packaged.lower() or TOKEN in rel.lower().encode():
            tokenized += 1
            if rel.lower().endswith(C_FAMILY):
                # The gate's contract is that C sources are byte-exact; one that carries the
                # source-name token is rewritten by design and so is outside what it can grade.
                mismatches.append(f"TOKENIZED-C {rel}: a C-family source carries the template source-name token")
            continue
        compared += 1
        seen.add(rel)
        if rel.lower().endswith(C_FAMILY):
            c_family.append(rel)
        delivered = read(scaffold_path)
        if delivered != packaged:
            mismatches.append(
                f"MISMATCH {rel}: packaged {len(packaged)} bytes, scaffold {len(delivered)} bytes"
            )
    # Files whose path carries the source-name token are renamed by the engine, so the scaffold path
    # differs and the loop above counted them absent; that is the expected rewrite, not a gap.
    missing_subjects = [rel for rel in (args.require or []) if rel not in seen]
    print(f"compared={compared} tokenized={tokenized} absent={absent} c_family={','.join(c_family)}")
    for line in mismatches:
        print(line)
    for rel in missing_subjects:
        print(f"NO-SUBJECT {rel}: not compared (absent from the archive, the scaffold, or token-bearing)")
    return 1 if mismatches or missing_subjects else 0


def rewrite(source, target, edit):
    with zipfile.ZipFile(source) as src, zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as dst:
        names = set()
        for info in src.infolist():
            data = src.read(info.filename)
            data = edit(info.filename, data)
            names.add(info.filename)
            dst.writestr(info.filename, data)
        return names


def seed(args):
    with zipfile.ZipFile(args.input) as src:
        roots = [
            prefix
            for prefix in TEMPLATE_PREFIXES
            if any(n.startswith(prefix + SEED_DIR) for n in src.namelist())
        ]
    if not roots:
        print("seed: the archive ships SvgFoundation/ under no known fable-game template", file=sys.stderr)
        return 1
    rewrite(args.input, args.output, lambda name, data: data)
    with zipfile.ZipFile(args.output, "a", zipfile.ZIP_DEFLATED) as dst:
        for prefix in roots:
            for rel in (SEED_C, SEED_H):
                dst.writestr(prefix + rel, SEED_SOURCE)
    print("seeded " + " ".join(roots))
    return 0


def strip_c_family(name, data):
    if not name.startswith(TEMPLATE_PREFIXES) or not name.endswith(".template.config/template.json"):
        return data
    document = json.loads(data.decode("utf-8"))
    operations = document.get("specialCustomOperations", {})
    for pattern in ("**/*.c", "**/*.h"):
        operations.pop(pattern, None)
    return (json.dumps(document, indent=2) + "\n").encode("utf-8")


def strip(args):
    names = rewrite(args.input, args.output, strip_c_family)
    stripped = [n for n in names if n.endswith(".template.config/template.json") and n.startswith(TEMPLATE_PREFIXES)]
    if len(stripped) != 2:
        print(f"strip: expected 2 fable-game template.json entries, found {stripped}", file=sys.stderr)
        return 1
    print("stripped " + " ".join(sorted(stripped)))
    return 0


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)
    cmp_parser = sub.add_parser("compare")
    cmp_parser.add_argument("--packaged", required=True)
    cmp_parser.add_argument("--scaffold", required=True)
    cmp_parser.add_argument("--require", action="append")
    cmp_parser.set_defaults(func=compare)
    for name, func in (("seed", seed), ("strip", strip)):
        derived = sub.add_parser(name)
        derived.add_argument("--in", dest="input", required=True)
        derived.add_argument("--out", dest="output", required=True)
        derived.set_defaults(func=func)
    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
