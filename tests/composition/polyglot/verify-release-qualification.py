"""Publication gate for archives that carry the four polyglot providers.

Legacy archives have no new provider payload and retain their existing release gates.

An archive carrying a polyglot provider is publishable only when its PAYLOAD IDENTITY is listed in the
protected acceptance register (readiness/polyglot-qualification-acceptance.json). A register entry exists
only after genuine four-product qualification of that payload was independently reviewed and accepted by
root; adding it is a pull request into protected main, so the register is not editable by the release run.

The npm audit of the two Node products is a dated live-registry observation (an accepted recorded limit), so each
entry records the audit response digest and the UTC time it was observed.

Payload identity = SHA-256 over the sorted `<entry sha256>  <entry name>` lines of every archive entry, with
the nuspec's repository commit blanked. Zip entry timestamps differ between packs and the commit necessarily
differs once the register entry itself lands, so neither can be part of the identity; every payload byte is.
"""
import hashlib
import json
from pathlib import Path
import re
import sys
import zipfile

REGISTER = Path(__file__).resolve().parents[3] / "readiness" / "polyglot-qualification-acceptance.json"
REGISTER_SCHEMA = "fsgg.polyglot-qualification-acceptance/v1"
PROVIDERS = ("typescript", "javascript", "rust", "go")
ENTRY_KEYS = {"payloadIdentitySha256", "package", "evidence", "acceptance", "npmAuditObservation"}


def requires_qualification(archive):
    with zipfile.ZipFile(archive) as package:
        return any(name.startswith("content/templates/fs-gg-" + language + "-cli/")
                   for name in package.namelist() for language in PROVIDERS)


def payload_identity(archive):
    lines = []
    with zipfile.ZipFile(archive) as package:
        names = [info.filename for info in package.infolist() if not info.is_dir()]
        if len(names) != len(set(names)):
            raise ValueError("duplicate archive entries refused")
        roots = [name for name in names if "/" not in name and name.endswith(".nuspec")]
        if len(roots) != 1:
            raise ValueError("exactly one top-level nuspec is required")
        for name in sorted(names):
            data = package.read(name)
            if name == roots[0]:
                data = re.sub(rb'(<repository\b[^>]*\bcommit=")[0-9a-f]{40}(")', rb"\1\2", data)
            lines.append("%s  %s\n" % (hashlib.sha256(data).hexdigest(), name))
    return hashlib.sha256("".join(lines).encode("utf-8")).hexdigest()


def load_register(path=REGISTER):
    document = json.loads(Path(path).read_bytes(), object_pairs_hook=_no_duplicates)
    if set(document) != {"schema", "accepted"} or document["schema"] != REGISTER_SCHEMA or not isinstance(document["accepted"], list):
        raise ValueError("acceptance register shape differs")
    seen = set()
    for entry in document["accepted"]:
        if not isinstance(entry, dict) or set(entry) != ENTRY_KEYS:
            raise ValueError("acceptance register entry shape differs")
        if not re.fullmatch(r"[0-9a-f]{64}", str(entry["payloadIdentitySha256"])):
            raise ValueError("acceptance register payload identity must be 64 lowercase hex characters")
        if not all(isinstance(entry[key], str) and entry[key].startswith("https://github.com/FS-GG/") for key in ("evidence", "acceptance")):
            raise ValueError("acceptance register entries cite their evidence and root acceptance URLs")
        observation = entry["npmAuditObservation"]
        if (not isinstance(observation, dict) or set(observation) != {"responseSha256", "observedUtc"}
                or not re.fullmatch(r"[0-9a-f]{64}", str(observation["responseSha256"]))
                or not re.fullmatch(r"20[0-9]{2}-[01][0-9]-[0-3][0-9]T[0-2][0-9]:[0-5][0-9]:[0-5][0-9]Z", str(observation["observedUtc"]))):
            raise ValueError("acceptance register entries record the dated npm audit response digest and UTC time")
        if entry["payloadIdentitySha256"] in seen:
            raise ValueError("duplicate acceptance register entry")
        seen.add(entry["payloadIdentitySha256"])
    return document["accepted"]


def _no_duplicates(pairs):
    keys = [key for key, _ in pairs]
    if len(keys) != len(set(keys)):
        raise ValueError("duplicate JSON keys refused")
    return dict(pairs)


def main(argv, register=REGISTER):
    if len(argv) != 1:
        raise ValueError("one immutable archive required")
    archive = Path(argv[0])
    if not requires_qualification(archive):
        print("legacy archive: existing release gates remain required")
        return 0
    identity = payload_identity(archive)
    accepted = {entry["payloadIdentitySha256"]: entry for entry in load_register(register)}
    if identity not in accepted:
        raise ValueError("polyglot publication held: payload identity %s has no independently accepted genuine four-product qualification in %s; source/ordinary CI is insufficient"
                         % (identity, register.name))
    entry = accepted[identity]
    print("polyglot payload %s accepted: evidence %s; acceptance %s" % (identity, entry["evidence"], entry["acceptance"]))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main(sys.argv[1:]))
    except (ValueError, OSError, zipfile.BadZipFile, json.JSONDecodeError) as error:
        print(str(error), file=sys.stderr)
        raise SystemExit(3)
