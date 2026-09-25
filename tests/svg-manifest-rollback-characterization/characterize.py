#!/usr/bin/env python3
"""Disposable merged-manifest and rollback controls for selected FSC-05 intents."""

import importlib.util
import json
from pathlib import Path
import stat
import sys
import tempfile
import zipfile

REPO = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("adopter", REPO / "scripts/apply-svg-complete-workspace.py")
adopter = importlib.util.module_from_spec(spec)
spec.loader.exec_module(adopter)

MANIFESTS = [".agents/skills/skill-manifest.json", ".claude/skills/skill-manifest.json"]
RETIRED = [".agents/skills/fable-remoting/SKILL.md", ".claude/skills/fable-remoting/SKILL.md"]
PREFIX = "content/templates/fs-gg-fable-game/"


def write(path, data, mode=0o644):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    path.chmod(mode)


def encoded(value):
    return (json.dumps(value, indent=2) + "\n").encode()


def refusal(operation, code):
    try:
        operation()
    except SystemExit as error:
        assert error.code == code, error.code
    else:
        raise AssertionError("unsafe manifest or rollback state was admitted")


def snapshot(paths):
    return {logical: None if not path.exists() else (path.read_bytes(), stat.S_IMODE(path.stat().st_mode))
            for logical, path in paths.items()}


def run(output):
    selected = adopter.load_json(REPO / "scripts/svg-complete-workspace-baselines.json")
    assert [p for p in selected["managedPaths"] if p in MANIFESTS] == MANIFESTS
    assert [p for p in selected["retiredPaths"] if p in RETIRED] == RETIRED
    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary)
        candidate, workspace = root / "candidate", root / "workspace"
        candidate.mkdir()
        workspace.mkdir()
        write(candidate / "FableGameWorkspace.slnx", b"<Solution/>\n")
        write(candidate / "Domain/Room.fs", b"namespace FableGameWorkspaceNamespace.Domain\n")
        write(workspace / "Receiver.slnx", b"<Solution/>\n")
        write(workspace / "Domain/Room.fs", b"namespace Receiver.Domain\n")
        write(workspace / "authored.txt", b"keep authored bytes\n")

        package_rows = []
        produced_paths = []
        for skill_id, body in [("fable-example", b"# example\n"), ("fable-second", b"# second\n")]:
            logical = f".agents/skills/{skill_id}/SKILL.md"
            write(candidate / logical, body)
            package_rows.append({"id": skill_id, "scope": "product",
                                 "supplied-by": f"template/product-skills/{skill_id}",
                                 "resolvablePath": logical, "sha256": adopter.digest(body)})
            produced_paths.append({"path": logical, "owner": "generatedProduct"})
        write(candidate / ".fsgg/scaffold-provenance.json", encoded({"producedPaths": produced_paths}))
        write(candidate / MANIFESTS[0], encoded({"schemaVersion": 1, "skills": package_rows}))

        foreign = {"id": "other-producer", "scope": "workspace", "owner": "authored", "extra": [1, 2]}
        legacy = dict(package_rows[0], sha256="a" * 64)
        remoting = {"id": "fable-remoting", "scope": "product", "sha256": "b" * 64}
        current = encoded({"schemaVersion": 1, "skills": [foreign, legacy, remoting]})
        for index, logical in enumerate(MANIFESTS):
            write(workspace / logical, current, 0o600 if index == 0 else 0o640)
        for index, logical in enumerate(RETIRED):
            write(workspace / logical, b"retired body\n", 0o755 if index == 0 else 0o640)

        baseline = {
            "schema": "fsgg.svg-complete-adoption-manifest/v1",
            "managedPaths": MANIFESTS,
            "retiredPaths": RETIRED,
            "baselineDigests": {"legacy": {logical: adopter.digest(b"retired body\n") for logical in RETIRED}},
            "baselineSkillManifestRowDigests": {
                "fable-example": [adopter.skill_row_digest(legacy)],
                "fable-remoting": [adopter.skill_row_digest(remoting)]},
            "sourceCandidates": [{"version": "0.14.0", "sourceHead": "a" * 40,
                                  "nativeArchiveSha256": "b" * 64}],
        }
        baseline_path = root / "synthetic-baseline.json"
        baseline_path.write_bytes(encoded(baseline))

        # A duplicate top-level or nested key has two interpretations. It must
        # not be admitted as owned content or silently folded into the merge.
        duplicate_top = (b'{"schemaVersion":1,"skills":[{"id":"fable-example","sha256":"forged"}],'
                         b'"skills":' + json.dumps([foreign, legacy, remoting]).encode() + b'}')
        duplicate_nested = (b'{"schemaVersion":1,"skills":[{"id":"forged","id":"other-producer"},'
                            + json.dumps(legacy).encode() + b',' + json.dumps(remoting).encode() + b']}')
        for duplicate in (duplicate_top, duplicate_nested):
            assert not adopter.admitted_workspace_skill_manifest(candidate, duplicate, baseline)
            refusal(lambda: adopter.package_product_manifest(candidate, duplicate), 2)
        neutral_manifest = workspace / MANIFESTS[0]
        neutral_mode = stat.S_IMODE(neutral_manifest.stat().st_mode)
        neutral_manifest.write_bytes(duplicate_top)
        refusal(lambda: adopter.classify(candidate, workspace, baseline_path), 2)
        neutral_manifest.write_bytes(current)
        neutral_manifest.chmod(neutral_mode)

        archive_path = output.with_name("synthetic-selected.nupkg")
        with zipfile.ZipFile(archive_path, "w") as archive:
            for source in sorted(path for path in candidate.rglob("*") if path.is_file()):
                logical = source.relative_to(candidate).as_posix()
                entry = zipfile.ZipInfo(PREFIX + logical)
                entry.external_attr = (stat.S_IFREG | stat.S_IMODE(source.stat().st_mode)) << 16
                archive.writestr(entry, source.read_bytes())

        inventory_path, review_path, backup = root / "inventory.json", root / "review.diff", root / "backup"
        adopter.inventory([str(candidate), str(workspace), str(baseline_path),
                           str(inventory_path), str(review_path)])
        inventory = adopter.load_json(inventory_path)
        assert inventory["ready"] and not inventory["conflicts"]
        assert [(row["path"], row["state"]) for row in inventory["changes"]] == [
            (MANIFESTS[0], "replace"), (MANIFESTS[1], "replace"),
            (RETIRED[0], "delete"), (RETIRED[1], "delete")]
        touched = {logical: workspace / logical for logical in MANIFESTS + RETIRED}
        before = snapshot(touched)
        adopter.apply([str(candidate), str(workspace), str(baseline_path),
                       str(inventory_path), str(backup)])
        journal = adopter.load_json(backup / "journal.json")
        assert journal["status"] == "applied"
        assert [(row["logical"], row["postState"]) for row in journal["paths"]] == [
            (MANIFESTS[0], "present"), (MANIFESTS[1], "present"),
            (RETIRED[0], "absent"), (RETIRED[1], "absent")]
        after = snapshot(touched)
        for logical in MANIFESTS:
            rows = json.loads((workspace / logical).read_bytes())["skills"]
            assert {row["id"] for row in rows} == {"other-producer", "fable-example", "fable-second"}
            assert next(row for row in rows if row["id"] == "other-producer") == foreign
            assert next(row for row in rows if row["id"] == "fable-example") == package_rows[0]
        assert all(after[logical] is None for logical in RETIRED)
        assert (workspace / "authored.txt").read_bytes() == b"keep authored bytes\n"

        # Corrupt the last saved object: validation must refuse before any
        # earlier destination is restored or journal status is changed.
        late_object = backup / "files" / RETIRED[-1]
        saved_object = late_object.read_bytes()
        late_object.write_bytes(b"corrupt")
        refusal(lambda: adopter.restore(workspace, backup), 2)
        assert snapshot(touched) == after
        assert adopter.load_json(backup / "journal.json")["status"] == "applied"
        late_object.write_bytes(saved_object)
        late_object.chmod(before[RETIRED[-1]][1])

        # A new edit at the last post-state is likewise refused before any
        # earlier rollback mutation. Removing it permits exact rollback.
        write(workspace / RETIRED[-1], b"new author edit\n")
        edited = snapshot(touched)
        refusal(lambda: adopter.restore(workspace, backup), 3)
        assert snapshot(touched) == edited
        assert adopter.load_json(backup / "journal.json")["status"] == "applied"
        (workspace / RETIRED[-1]).unlink()

        # The merged manifest itself is a journaled managed output. Refuse a
        # later edit to it before touching any earlier path.
        merged_path = workspace / MANIFESTS[-1]
        merged_bytes, merged_mode = after[MANIFESTS[-1]]
        merged_path.write_bytes(b"new author edit\n")
        edited_manifest = snapshot(touched)
        refusal(lambda: adopter.restore(workspace, backup), 3)
        assert snapshot(touched) == edited_manifest
        assert adopter.load_json(backup / "journal.json")["status"] == "applied"
        merged_path.write_bytes(merged_bytes)
        merged_path.chmod(merged_mode)
        adopter.restore(workspace, backup)
        assert snapshot(touched) == before
        assert (workspace / "authored.txt").read_bytes() == b"keep authored bytes\n"

        output.write_text(json.dumps({
            "archivePath": str(archive_path), "archiveSha256": adopter.digest(archive_path.read_bytes()),
            "managed": MANIFESTS, "retired": RETIRED,
            "journalPaths": [row["logical"] for row in journal["paths"]],
            "journalStates": [row["postState"] for row in journal["paths"]],
            "rawManifestSha256": adopter.digest((candidate / MANIFESTS[0]).read_bytes()),
        }))


if __name__ == "__main__":
    run(Path(sys.argv[1]))
    print("merged-manifest and rollback characterization: passed")
