"""Real receiver probe for a frozen candidate CLI; no build, publish, or background commit."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess

from receiver import call, inventory, snapshot


def git(root, *args):
    return subprocess.run(["git", "-C", str(root), *args], check=True, capture_output=True, text=True).stdout.strip()


def commit(root, message):
    git(root, "add", ".")
    git(root, "-c", "user.name=Receiver", "-c", "user.email=receiver@example.invalid", "commit", "-qm", message)
    return git(root, "rev-parse", "HEAD")


def probe(command: list[str], root: Path, scratch: Path):
    scratch.mkdir(parents=True, exist_ok=True)
    seed = call(command, "knowledge", "get", "--root", str(root), "--id", "project-knowledge")
    assert seed["Record"]["Author"] == "fsgg-sdd"
    assert seed["Record"]["State"] == "accepted"
    preserved = snapshot(root)
    guide = root / ".fsgg/knowledge-guide.md"
    guide.write_text(guide.read_text() + "\nProject-owned capture guidance.\n")
    expected_guide = guide.read_bytes()
    with (root / ".gitignore").open("a") as stream:
        stream.write("\n# Authored later broad ignore control\n.fsgg/**\n")
    authored_ignore = (root / ".gitignore").read_bytes()
    call(command, "knowledge", "initialize", "--root", str(root))
    assert guide.read_bytes() == expected_guide, "initialization clobbered authored guidance"
    assert (root / ".gitignore").read_bytes().startswith(authored_ignore), "initialization discarded authored ignore rules"
    initialized = snapshot(root)
    call(command, "knowledge", "initialize", "--root", str(root))
    assert snapshot(root) == initialized, "unchanged reinitialization was not idempotent"
    git(root, "init", "-q")
    initial_commit = commit(root, "Initial generated receiver with project knowledge")
    tracked = set(git(root, "ls-files").splitlines())
    canonical = [p for p in snapshot(root) if p.startswith(".fsgg/knowledge/")]
    assert canonical and all(p in tracked for p in canonical), "initial commit hid canonical files"
    assert ".fsgg/knowledge-guide.md" in tracked, "initial commit hid capture guidance/evidence locator"
    fixture = json.loads((Path(__file__).parent / "findings.json").read_text())
    versions = {}
    for finding in fixture["findings"]:
        evidence = finding["evidence"]
        record = dict(seed["Record"])
        record.update(Id=finding["id"], Kind=finding["kind"],
                      Title=finding["id"], Summary=finding["finding"], Author="synthetic-receiver", State=finding["state"],
                      Scope="receiver-fixture", Applicability="Synthetic receiver only", Limits="Does not establish production findings",
                      Created="2026-10-03", Updated="2026-10-03", AsOf="2026-10-03",
                      Evidence=[dict(Locator=evidence["path"], Repository="FS-GG/FS.GG.Templates",
                                     Revision=evidence.get("revision", ""), Path=evidence["path"], Digest="",
                                     Run=evidence.get("run", ""))],
                      Relations=[] if finding["id"] == "architecture-decision" else [{"Kind": "related", "Target": "architecture-decision"}])
        path = scratch / (record["Id"] + ".json")
        path.write_text(json.dumps(record))
        result = call(command, "knowledge", "capture", "--root", str(root), "--record", str(path))
        assert result["version"]["Record"] == record, "capture lost finding attribution/evidence"
        versions[record["Id"]] = result["version"]
    findings_commit = commit(root, "Capture concise receiver findings")
    old = versions["architecture-decision"]
    updated = dict(old["Record"])
    updated["Summary"] += " Applicability is limited to a fresh receiver."
    path = scratch / "updated.json"
    path.write_text(json.dumps(updated))
    call(command, "knowledge", "capture", "--root", str(root), "--record", str(path), "--expected", old["Revision"])
    changed_commit = commit(root, "Clarify decision applicability")
    before_refusal = snapshot(root)
    # A retry of the same bytes is intentionally idempotent; a divergent stale writer must refuse.
    path.write_text(json.dumps(dict(updated, Summary=updated["Summary"] + " Divergent stale writer.")))
    call(command, "knowledge", "capture", "--root", str(root), "--record", str(path), "--expected", old["Revision"], expect_success=False)
    assert snapshot(root) == before_refusal, "stale concurrent update changed receiver"
    history = call(command, "knowledge", "history", "--root", str(root), "--id", "architecture-decision")
    assert len(history) == 2
    past = call(command, "knowledge", "get-version", "--root", str(root), "--id", "architecture-decision", "--commit", findings_commit)
    assert past["Record"] == old["Record"], "Git history lost previous finding"
    results = call(command, "knowledge", "search", "--root", str(root), "--scope", "receiver-fixture")
    assert len(results) == 4
    for excluded in fixture["excludedInputs"]:
        invalid = dict(old["Record"], Id=excluded["id"], Kind=excluded["kind"], Summary=excluded["finding"])
        invalid_path = scratch / (excluded["id"] + ".json")
        invalid_path.write_text(json.dumps(invalid))
        before_refusal = snapshot(root)
        call(command, "knowledge", "capture", "--root", str(root), "--record", str(invalid_path), expect_success=False)
        assert snapshot(root) == before_refusal, "excluded input mutated receiver"
    # Canonical source/product/lifecycle bytes must survive capture and no-clobber initialization.
    after = snapshot(root)
    for relative, digest in preserved.items():
        if relative in {".gitignore", ".fsgg/knowledge-guide.md"}:
            continue
        assert after.get(relative) == digest, f"producer changed existing product/lifecycle file {relative}"
    archive = scratch / "knowledge.json"
    ids = ",".join(versions)
    call(command, "knowledge", "export", "--root", str(root), "--ids", ids, "--archive", str(archive))
    assert json.loads(archive.read_text())["HistoryIncluded"] is False
    restored = scratch / "restored"
    call(command, "knowledge", "restore", "--root", str(restored), "--archive", str(archive))
    assert call(command, "knowledge", "search", "--root", str(restored), "--scope", "receiver-fixture") == results
    restored_version = call(command, "knowledge", "get", "--root", str(restored), "--id", "architecture-decision")
    edited_restore = dict(restored_version["Record"], Summary="Project-owned clarification must survive a restore attempt.")
    restore_input = scratch / "restore-authored.json"
    restore_input.write_text(json.dumps(edited_restore))
    call(command, "knowledge", "capture", "--root", str(restored), "--record", str(restore_input), "--expected", restored_version["Revision"])
    before_restore = snapshot(restored)
    call(command, "knowledge", "restore", "--root", str(restored), "--archive", str(archive), expect_success=False)
    assert snapshot(restored) == before_restore, "restore overwrote authored finding"
    private_store = scratch / "synthetic-private"
    private_input = scratch / "synthetic-private.json"
    private_input.write_text(json.dumps(dict(old["Record"], Id="synthetic-private", Summary="Synthetic private fixture, never production content.")))
    shared_before = snapshot(root)
    call(command, "knowledge", "capture", "--store", str(private_store), "--record", str(private_input))
    assert snapshot(root) == shared_before, "explicit private store changed shared receiver"
    assert not call(command, "knowledge", "search", "--root", str(root), "--id", "synthetic-private")
    assert "synthetic-private" not in archive.read_text(), "shared export leaked private fixture"
    clone = scratch / "clone"
    subprocess.run(["git", "clone", "-q", str(root), str(clone)], check=True, capture_output=True)
    assert not (clone / ".fsgg/cache").exists()
    assert call(command, "knowledge", "search", "--root", str(clone), "--scope", "receiver-fixture") == results
    assert len(call(command, "knowledge", "history", "--root", str(clone), "--id", "architecture-decision")) == 2
    size = call(command, "knowledge", "check", "--root", str(root))
    assert size["Limit"] == 10485760 and 0 < size["Bytes"] <= size["Limit"]
    return dict(initialCommit=initial_commit, findingsCommit=findings_commit, updatedCommit=changed_commit,
                findings=4, historyVersions=2, canonicalFilesTracked=len(canonical), size=size,
                restoreAuthoredNoClobber=True, explicitPrivateStoreExcludedFromShared=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--command-json", required=True, help="Frozen candidate CLI argv JSON")
    parser.add_argument("--receiver", type=Path, required=True, help="An actually generated receiver, already initialized")
    parser.add_argument("--scratch", type=Path, required=True)
    args = parser.parse_args()
    inventory()
    print(json.dumps(probe(json.loads(args.command_json), args.receiver, args.scratch), indent=2))


if __name__ == "__main__":
    main()
