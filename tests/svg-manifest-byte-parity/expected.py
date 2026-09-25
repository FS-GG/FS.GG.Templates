#!/usr/bin/env python3
"""Python output bytes for independent F# merged-manifest comparison."""

import base64
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import zipfile

REPO = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("adopter", REPO / "scripts/apply-svg-complete-workspace.py")
adopter = importlib.util.module_from_spec(spec)
spec.loader.exec_module(adopter)
PREFIX = "content/templates/fs-gg-fable-game/"
MANIFEST = ".agents/skills/skill-manifest.json"


def b64(value):
    return None if value is None else base64.b64encode(value).decode("ascii")


def run(observation_path, output_path):
    observation = json.loads(observation_path.read_text())
    archive_path = Path(observation["archivePath"])
    assert adopter.digest(archive_path.read_bytes()) == observation["archiveSha256"]
    with tempfile.TemporaryDirectory() as temporary:
        candidate = Path(temporary) / "candidate"
        candidate.mkdir()
        bodies = {}
        provenance = None
        manifest = None
        with zipfile.ZipFile(archive_path) as archive:
            for member in archive.infolist():
                assert member.filename.startswith(PREFIX)
                logical = member.filename.removeprefix(PREFIX)
                assert adopter.checked_relative(logical, "synthetic archive path") == logical
                body = archive.read(member)
                target = candidate / logical
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(body)
                if logical.endswith("/SKILL.md"):
                    bodies[logical] = body
                if logical == MANIFEST:
                    manifest = body
                if logical == ".fsgg/scaffold-provenance.json":
                    provenance = body
        assert manifest is not None and provenance is not None and len(bodies) == 2
        source_solution = candidate / "FableGameWorkspace.slnx"
        package_rows = json.loads(manifest)["skills"]
        foreign = {"id": "Ω-other", "scope": "workspace", "note": "Å <>& 😀\nquoted \"x\"",
                   "nested": {"k": [True, None, -123456789012345678901234567890]},
                   "owned-by": "another producer"}
        foreign_bmp = {"id": "\ue000-other", "scope": "workspace", "owner": "bmp producer"}
        foreign_astral = {"id": "𐀀-other", "scope": "workspace", "owner": "astral producer"}
        legacy = dict(package_rows[0], sha256="a" * 64)
        retired = {"id": "fable-remoting", "scope": "product", "sha256": "b" * 64}
        cases = [
            ("no-current", None),
            ("foreign-and-legacy", json.dumps({"schemaVersion": 1, "skills":
                                                [foreign_astral, foreign, foreign_bmp, legacy, retired]},
                                               ensure_ascii=False).encode()),
            ("foreign-identity-text", json.dumps({"schemaVersion": 1, "skills": [
                {"id": "A-other", "scope": "workspace", "text":
                 "FableGameWorkspaceNamespace / FableGameWorkspace / fablegameworkspace"},
                package_rows[1]]}, ensure_ascii=False).encode()),
        ]
        expected = []
        for name, current in cases:
            destination = None
            if current is not None:
                destination = Path(temporary) / f"{name}.json"
                destination.write_bytes(current)
            merged = adopter.candidate_bytes(candidate, MANIFEST, source_solution,
                                             "FableGameWorkspace", "FableGameWorkspaceNamespace",
                                             "Receiver", "Receiver", destination)
            expected.append({"name": name, "currentBase64": b64(current),
                             "provenanceBase64": b64(provenance), "expectedBase64": b64(merged)})
        (candidate / ".fsgg/scaffold-provenance.json").unlink()
        without_provenance = adopter.candidate_bytes(candidate, MANIFEST, source_solution,
                                                     "FableGameWorkspace", "FableGameWorkspaceNamespace",
                                                     "Receiver", "Receiver")
        expected.append({"name": "no-provenance", "currentBase64": None,
                         "provenanceBase64": None, "expectedBase64": b64(without_provenance)})
        output_path.write_text(json.dumps({
            "sourceArchivePath": str(archive_path),
            "sourceArchiveSha256": observation["archiveSha256"],
            "candidateManifestBase64": b64(manifest),
            "candidateBodiesBase64": {name: b64(body) for name, body in bodies.items()},
            "candidateProvenanceBase64": b64(provenance),
            "cases": expected,
        }))


if __name__ == "__main__":
    run(Path(sys.argv[1]), Path(sys.argv[2]))
    print("Python merged-manifest expected bytes: 4 cases")
