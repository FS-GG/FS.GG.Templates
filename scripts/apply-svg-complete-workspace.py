#!/usr/bin/env python3
"""Inventory and transactionally adopt the complete generated SVG workspace."""

from __future__ import annotations

import difflib
import hashlib
import json
import os
from pathlib import Path
from pathlib import PurePosixPath
import re
import shutil
import stat
import sys
import tempfile

IGNORED_PARTS = {
    ".git", ".nuget", "artifacts", "bin", "dist", "node_modules", "obj", "output",
    "playwright-report", "test-results", "vendor",
}


def fail(message: str, code: int = 2) -> None:
    print(f"complete workspace adoption: {message}", file=sys.stderr)
    raise SystemExit(code)


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def checked_relative(value: str, label: str) -> str:
    path = PurePosixPath(value)
    if path.is_absolute() or not path.parts or any(part in {"", ".", ".."} for part in path.parts):
        fail(f"{label} is not a safe relative path: {value}")
    return path.as_posix()


def reject_symlink_chain(root: Path, path: Path, label: str) -> None:
    root = root.absolute()
    path = path.absolute()
    try:
        relative = path.relative_to(root)
    except ValueError:
        fail(f"{label} escapes root: {path}")
    current = root
    if current.is_symlink():
        fail(f"{label} root is a symlink: {current}")
    for part in relative.parts:
        current = current / part
        if current.is_symlink():
            fail(f"{label} path crosses a symlink: {current}")


def file_mode(path: Path) -> int:
    return stat.S_IMODE(path.stat(follow_symlinks=False).st_mode)


def load_json(path: Path) -> dict:
    try:
        return json.loads(path.read_text())
    except (OSError, json.JSONDecodeError) as error:
        fail(f"cannot read {path}: {error}")


def write_json_durable(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(prefix=path.name + ".fsgg-journal-", dir=path.parent)
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w") as stream:
            json.dump(value, stream, indent=2)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
        directory = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    finally:
        if temporary.exists():
            temporary.unlink()


def identity(root: Path) -> tuple[str, str, Path]:
    if root.is_symlink() or not root.is_dir():
        fail(f"workspace root is missing, not a directory, or a symlink: {root}")
    solutions = sorted(root.glob("*.slnx"))
    if len(solutions) != 1:
        fail(f"expected one root solution in {root}, found {len(solutions)}")
    room = root / "Domain" / "Room.fs"
    reject_symlink_chain(root, room, "identity")
    try:
        text = room.read_text()
    except OSError as error:
        fail(f"cannot read product namespace from {room}: {error}")
    match = re.search(r"^(?:module|namespace) ([A-Za-z_][A-Za-z0-9_.]*?)\.Domain(?:\s|$)", text, re.M)
    if not match:
        fail(f"product namespace is unreadable in {room}")
    return solutions[0].stem, match.group(1), solutions[0]


def canonical_variants(data: bytes, product: str, namespace: str) -> set[str]:
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        return {digest(data)}
    # Template replacement can affect F#, project files, scripts, and display text.
    # Reverse longest identities first so the baseline hash is independent of the
    # receiver's chosen name without normalizing unrelated authored text.
    variants = set()
    if namespace == product:
        # A common generated name is both the product and root namespace. The
        # original template distinguishes those tokens, so accept either exact
        # inverse globally; path-specific public hashes decide which is valid.
        for replacement in ("FableGameWorkspace", "FableGameWorkspaceNamespace"):
            value = text.replace(product, replacement).replace(product.lower(), "fablegameworkspace")
            variants.add(digest(value.encode("utf-8")))
    else:
        value = text
        for actual, template in sorted(
            [(namespace, "FableGameWorkspaceNamespace"), (product, "FableGameWorkspace"),
             (product.lower(), "fablegameworkspace")], key=lambda item: len(item[0]), reverse=True
        ):
            if actual:
                value = value.replace(actual, template)
        variants.add(digest(value.encode("utf-8")))
    return variants


def actual_path(root: Path, logical: str, solution: Path) -> Path:
    return solution if logical == "FableGameWorkspace.slnx" else root / logical


def candidate_path(root: Path, logical: str, solution: Path) -> Path:
    direct = actual_path(root, logical, solution)
    if direct.exists():
        return direct
    for mirror_prefix in (".claude/skills/",):
        if logical.startswith(mirror_prefix):
            return root / ".agents" / "skills" / logical.removeprefix(mirror_prefix)
    return direct


def package_product_manifest(root: Path, current: bytes | None) -> bytes:
    """Merge package-owned declarations without discarding another producer's rows."""
    manifest_path = root / ".agents" / "skills" / "skill-manifest.json"
    reject_symlink_chain(root, manifest_path, "candidate skill manifest")
    manifest = load_json(manifest_path)
    rows = manifest.get("skills")
    if manifest.get("schemaVersion") != 1 or not isinstance(rows, list):
        fail("candidate skill manifest is invalid")
    provenance_path = root / ".fsgg" / "scaffold-provenance.json"
    owned_paths = None
    if provenance_path.exists():
        reject_symlink_chain(root, provenance_path, "candidate scaffold provenance")
        provenance = load_json(provenance_path)
        produced = provenance.get("producedPaths")
        if not isinstance(produced, list):
            fail("candidate scaffold provenance has no produced paths")
        owned_paths = {
            checked_relative(row.get("path", ""), "candidate provenance path")
            for row in produced
            if isinstance(row, dict) and row.get("owner") == "generatedProduct"
            and isinstance(row.get("path"), str) and row["path"].startswith(".agents/skills/")
            and row["path"].endswith("/SKILL.md")
        }
        if not owned_paths:
            fail("candidate scaffold provenance has no generated product skills")
    package_rows = []
    materialized = set()
    package_ids = set()
    for row in rows:
        supplied_by = row.get("supplied-by", "") if isinstance(row, dict) else ""
        if (not isinstance(row, dict) or row.get("scope") != "product"
                or not isinstance(supplied_by, str)
                or not supplied_by.startswith("template/product-skills/fable-")):
            continue
        logical = checked_relative(row.get("resolvablePath", ""), "candidate skill path")
        if not logical.startswith(".agents/skills/") or not logical.endswith("/SKILL.md"):
            fail(f"candidate product skill path is unsupported: {logical}")
        body = root / logical
        reject_symlink_chain(root, body, "candidate product skill")
        skill_id = row.get("id")
        if not isinstance(skill_id, str) or skill_id in package_ids:
            fail(f"candidate product skill manifest repeats or omits id: {skill_id}")
        package_ids.add(skill_id)
        package_rows.append(row)
        if body.exists():
            if not body.is_file() or digest(body.read_bytes()) != row.get("sha256"):
                fail(f"candidate product skill body does not match its manifest: {logical}")
            materialized.add(logical)
    if not package_rows or not materialized:
        fail("candidate has no package-owned product skill declarations or bodies")
    if owned_paths is not None and materialized != owned_paths:
        missing = sorted(owned_paths - materialized)
        fail(f"candidate generated product skills are absent from the manifest: {missing}")

    preserved = []
    if current is not None:
        try:
            existing = json.loads(current)
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            fail(f"workspace skill manifest is invalid: {error}")
        existing_rows = existing.get("skills")
        if existing.get("schemaVersion") != 1 or not isinstance(existing_rows, list):
            fail("workspace skill manifest is invalid")
        for row in existing_rows:
            if not isinstance(row, dict) or not isinstance(row.get("id"), str):
                fail("workspace skill manifest contains an invalid row")
            if row["id"] not in package_ids and row["id"] != "fable-remoting":
                preserved.append(row)
    combined = preserved + package_rows
    if len({row["id"] for row in combined}) != len(combined):
        fail("merged product skill manifest contains duplicate ids")
    combined.sort(key=lambda row: row["id"])
    return (json.dumps({"schemaVersion": 1, "skills": combined}, indent=2) + "\n").encode()


def skill_row_digest(row: dict) -> str:
    return digest(json.dumps(row, sort_keys=True, separators=(",", ":")).encode())


def admitted_workspace_skill_manifest(candidate: Path, current: bytes, adoption_manifest: dict) -> bool:
    """Authenticate only the package-owned rows; preserve other producer rows exactly."""
    try:
        value = json.loads(current)
    except (UnicodeDecodeError, json.JSONDecodeError):
        return False
    rows = value.get("skills")
    if value.get("schemaVersion") != 1 or not isinstance(rows, list):
        return False
    admitted = adoption_manifest.get("baselineSkillManifestRowDigests", {})
    if not isinstance(admitted, dict):
        return False
    candidate_value = json.loads(package_product_manifest(candidate, None))
    candidate_rows = {row["id"]: skill_row_digest(row) for row in candidate_value["skills"]}
    seen = set()
    for row in rows:
        if not isinstance(row, dict) or not isinstance(row.get("id"), str) or row["id"] in seen:
            return False
        seen.add(row["id"])
        package_owned = row["id"] == "fable-remoting" or row["id"] in candidate_rows
        if package_owned:
            allowed = admitted.get(row["id"], [])
            if not isinstance(allowed, list):
                return False
            row_sha = skill_row_digest(row)
            if row_sha != candidate_rows.get(row["id"]) and row_sha not in allowed:
                return False
    return True


def effective_paths(workspace: Path, managed: list[str], retired: list[str]) -> tuple[list[str], list[str]]:
    """Use neutral skills always and update only mirror roots already configured."""
    enabled_mirrors = set()
    for root in (".claude/skills",):
        path = workspace / root
        if path.is_symlink():
            fail(f"configured skill mirror is a symlink: {root}")
        if path.exists():
            if not path.is_dir():
                fail(f"configured skill mirror is not a directory: {root}")
            enabled_mirrors.add(root + "/")

    def admitted(logical: str) -> bool:
        for prefix in (".claude/skills/",):
            if logical.startswith(prefix):
                return prefix in enabled_mirrors
        return True

    return [value for value in managed if admitted(value)], [value for value in retired if admitted(value)]


def relevant_files(root: Path) -> list[Path]:
    values = []
    for path in root.rglob("*"):
        if path.is_symlink():
            values.append(path)
        elif path.is_file() and not any(part in IGNORED_PARTS for part in path.relative_to(root).parts):
            values.append(path)
    return sorted(values)


def tree_observation(root: Path) -> tuple[str, list[dict]]:
    rows = []
    for path in relevant_files(root):
        rel = path.relative_to(root).as_posix()
        if path.is_symlink():
            rows.append({"path": rel, "kind": "symlink", "mode": file_mode(path),
                         "sha256": digest(os.readlink(path).encode())})
        else:
            rows.append({"path": rel, "kind": "file", "mode": file_mode(path),
                         "sha256": digest(path.read_bytes())})
    encoded = "".join(
        f"{row['kind']}\t{row['mode']:o}\t{row['sha256']}\t{row['path']}\n" for row in rows
    ).encode()
    return digest(encoded), rows


def candidate_bytes(source: Path, logical: str, source_solution: Path,
                    source_product: str, source_namespace: str,
                    destination_product: str, destination_namespace: str,
                    destination: Path | None = None) -> bytes:
    path = candidate_path(source, logical, source_solution)
    if path.is_symlink() or not path.is_file():
        fail(f"candidate managed file is missing or not regular: {logical}")
    if logical in {".agents/skills/skill-manifest.json", ".claude/skills/skill-manifest.json"}:
        current = destination.read_bytes() if destination is not None and destination.is_file() else None
        data = package_product_manifest(source, current)
    else:
        data = path.read_bytes()
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        return data
    replacements = sorted(
        [(source_namespace, destination_namespace), (source_product, destination_product),
         (source_product.lower(), destination_product.lower())],
        key=lambda item: len(item[0]), reverse=True)
    for old, new in replacements:
        if old:
            text = text.replace(old, new)
    return text.encode("utf-8")


def manifest_data(path: Path) -> tuple[dict, list[str], list[str], dict[str, set[str]]]:
    manifest = load_json(path)
    if manifest.get("schema") != "fsgg.svg-complete-adoption-manifest/v1":
        fail("unsupported baseline manifest schema")
    managed = manifest.get("managedPaths")
    if not isinstance(managed, list) or not managed or managed != sorted(set(managed)):
        fail("baseline manifest managed paths must be a nonempty sorted unique list")
    managed = [checked_relative(value, "managed path") for value in managed]
    retired = manifest.get("retiredPaths", [])
    if not isinstance(retired, list) or retired != sorted(set(retired)):
        fail("baseline manifest retired paths must be a sorted unique list")
    retired = [checked_relative(value, "retired path") for value in retired]
    if set(managed) & set(retired):
        fail("baseline manifest active and retired paths overlap")
    allowed: dict[str, set[str]] = {logical: set() for logical in managed + retired}
    baselines = manifest.get("baselineDigests")
    if not isinstance(baselines, dict):
        fail("baseline manifest has no public baseline digests")
    for values in baselines.values():
        if not isinstance(values, dict):
            fail("baseline digest set is invalid")
        for logical, value in values.items():
            logical = checked_relative(logical, "baseline path")
            if logical not in allowed or not isinstance(value, str) or not re.fullmatch(r"[0-9a-f]{64}", value):
                fail(f"baseline digest is invalid for {logical}")
            allowed[logical].add(value)
    row_digests = manifest.get("baselineSkillManifestRowDigests")
    if not isinstance(row_digests, dict) or not row_digests:
        fail("baseline manifest has no package skill row digests")
    for skill_id, values in row_digests.items():
        if (not isinstance(skill_id, str) or not skill_id.startswith("fable-")
                or not isinstance(values, list) or not values
                or any(not isinstance(value, str) or not re.fullmatch(r"[0-9a-f]{64}", value)
                       for value in values)):
            fail(f"baseline skill row digests are invalid for {skill_id}")
    candidates = manifest.get("sourceCandidates")
    if not isinstance(candidates, list) or not candidates:
        fail("baseline manifest has no selected candidate custody")
    for candidate in candidates:
        if (not isinstance(candidate, dict) or candidate.get("version") != "0.14.0"
                or not isinstance(candidate.get("sourceHead"), str)
                or not re.fullmatch(r"[0-9a-f]{40}", candidate["sourceHead"])
                or not isinstance(candidate.get("nativeArchiveSha256"), str)
                or not re.fullmatch(r"[0-9a-f]{64}", candidate["nativeArchiveSha256"])):
            fail("selected candidate custody is invalid")
    return manifest, managed, retired, allowed


def classify(candidate: Path, workspace: Path, manifest_path: Path) -> dict:
    manifest, managed, retired, allowed = manifest_data(manifest_path)
    managed, retired = effective_paths(workspace, managed, retired)
    source_product, source_namespace, source_solution = identity(candidate)
    destination_product, destination_namespace, destination_solution = identity(workspace)
    changes, conflicts, unchanged = [], [], []
    candidate_hash_rows = []
    managed_actual = set()
    diff_parts = []
    for logical in managed:
        destination = actual_path(workspace, logical, destination_solution)
        source_path = candidate_path(candidate, logical, source_solution)
        reject_symlink_chain(candidate, source_path, "candidate managed")
        reject_symlink_chain(workspace, destination, "workspace managed")
        managed_actual.add(destination.relative_to(workspace).as_posix())
        staged = candidate_bytes(candidate, logical, source_solution, source_product, source_namespace,
                                 destination_product, destination_namespace, destination)
        candidate_mode = file_mode(source_path)
        candidate_hash_rows.append(f"{candidate_mode:o}\t{digest(staged)}\t{logical}\n")
        if destination.is_symlink():
            conflicts.append({"path": logical, "reason": "managed destination is a symlink"})
            continue
        if not destination.exists():
            changes.append({"path": logical, "state": "add", "candidateSha256": digest(staged),
                            "candidateMode": candidate_mode})
            try:
                after = staged.decode("utf-8").splitlines(keepends=True)
                diff_parts.extend(difflib.unified_diff([], after, fromfile="/dev/null", tofile=f"b/{logical}"))
            except UnicodeDecodeError:
                diff_parts.append(f"Binary file added: {logical}\n")
            continue
        if not destination.is_file():
            conflicts.append({"path": logical, "reason": "managed destination is not a regular file"})
            continue
        current = destination.read_bytes()
        current_mode = file_mode(destination)
        current_canonical = canonical_variants(current, destination_product, destination_namespace)
        candidate_canonical = canonical_variants(staged, destination_product, destination_namespace)
        manifest_logical = logical in {".agents/skills/skill-manifest.json",
                                       ".claude/skills/skill-manifest.json"}
        admitted_manifest = (manifest_logical
                             and admitted_workspace_skill_manifest(candidate, current, manifest))
        if (not admitted_manifest and current_canonical.isdisjoint(candidate_canonical)
                and current_canonical.isdisjoint(allowed[logical])):
            conflicts.append({"path": logical, "reason": "edited or unsupported managed content",
                              "currentCanonicalSha256": sorted(current_canonical)})
            continue
        if current == staged and current_mode == candidate_mode:
            unchanged.append(logical)
            continue
        changes.append({"path": logical, "state": "replace", "currentSha256": digest(current),
                        "currentMode": current_mode, "candidateSha256": digest(staged),
                        "candidateMode": candidate_mode})
        if current_mode != candidate_mode:
            diff_parts.append(f"old mode {current_mode:06o}\nnew mode {candidate_mode:06o}\n")
        try:
            before = current.decode("utf-8").splitlines(keepends=True)
            after = staged.decode("utf-8").splitlines(keepends=True)
            diff_parts.extend(difflib.unified_diff(before, after, fromfile=f"a/{logical}", tofile=f"b/{logical}"))
        except UnicodeDecodeError:
            diff_parts.append(f"Binary files differ: {logical}\n")
    for logical in retired:
        destination = actual_path(workspace, logical, destination_solution)
        reject_symlink_chain(workspace, destination, "workspace retired")
        managed_actual.add(destination.relative_to(workspace).as_posix())
        candidate_hash_rows.append(f"retire\t{logical}\n")
        if destination.is_symlink():
            conflicts.append({"path": logical, "reason": "retired destination is a symlink"})
        elif not destination.exists():
            unchanged.append(logical)
        elif not destination.is_file():
            conflicts.append({"path": logical, "reason": "retired destination is not a regular file"})
        else:
            current = destination.read_bytes()
            current_canonical = canonical_variants(current, destination_product, destination_namespace)
            if current_canonical.isdisjoint(allowed[logical]):
                conflicts.append({"path": logical, "reason": "edited retired product skill",
                                  "currentCanonicalSha256": sorted(current_canonical)})
            else:
                current_mode = file_mode(destination)
                changes.append({"path": logical, "state": "delete", "currentSha256": digest(current),
                                "currentMode": current_mode})
                try:
                    before = current.decode("utf-8").splitlines(keepends=True)
                    diff_parts.extend(difflib.unified_diff(before, [], fromfile=f"a/{logical}", tofile="/dev/null"))
                except UnicodeDecodeError:
                    diff_parts.append(f"Binary file retired: {logical}\n")
    preserved = []
    for path in relevant_files(workspace):
        rel = path.relative_to(workspace).as_posix()
        if rel not in managed_actual:
            preserved.append(rel)
    tree_sha, tree_rows = tree_observation(workspace)
    return {
        "schema": "fsgg.svg-complete-adoption-inventory/v1",
        "ready": not conflicts,
        "candidate": str(candidate.resolve()),
        "workspace": str(workspace.resolve()),
        "manifest": str(manifest_path.resolve()),
        "manifestSha256": digest(manifest_path.read_bytes()),
        "candidateManagedSha256": digest("".join(candidate_hash_rows).encode()),
        "workspaceTreeSha256": tree_sha,
        "workspaceFiles": tree_rows,
        "sourceIdentity": {"product": source_product, "namespace": source_namespace},
        "destinationIdentity": {"product": destination_product, "namespace": destination_namespace},
        "changes": changes,
        "unchangedManaged": unchanged,
        "conflicts": conflicts,
        "preserved": preserved,
        "diff": "".join(diff_parts),
        "publicBaselineArchives": manifest.get("sourceArchives", []),
        "selectedCandidateBaselines": manifest.get("sourceCandidates", []),
    }


def inventory(args: list[str]) -> None:
    if len(args) != 5:
        fail("usage: complete-inventory <candidate> <workspace> <baseline-manifest> <inventory.json> <review.diff>")
    candidate, workspace, manifest_path, output, review = map(Path, args)
    observation = classify(candidate, workspace, manifest_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    review.parent.mkdir(parents=True, exist_ok=True)
    review.write_text(observation.pop("diff"))
    observation["reviewDiff"] = str(review.resolve())
    observation["reviewDiffSha256"] = digest(review.read_bytes())
    output.write_text(json.dumps(observation, indent=2) + "\n")
    print(f"complete workspace adoption: inventory ready={str(observation['ready']).lower()} changes={len(observation['changes'])} conflicts={len(observation['conflicts'])} preserved={len(observation['preserved'])}")
    if not observation["ready"]:
        raise SystemExit(3)


def restore(workspace: Path, backup: Path, portal: bool = False) -> None:
    if workspace.is_symlink() or not workspace.is_dir():
        fail(f"rollback workspace is missing, not a directory, or a symlink: {workspace}")
    if backup.is_symlink() or not backup.is_dir():
        fail(f"rollback backup is missing, not a directory, or a symlink: {backup}")
    reject_symlink_chain(backup.parent, backup, "rollback backup")
    journal_path = backup / "journal.json"
    reject_symlink_chain(backup, journal_path, "rollback journal")
    journal = load_json(journal_path)
    if portal and not isinstance(journal, dict):
        fail("Portal recovery journal is not an object")
    expected_schema = "fsgg.portal.adoption-journal/1" if portal else "fsgg.svg-complete-adoption-journal/v1"
    if journal.get("schema") != expected_schema:
        fail("unsupported rollback journal")
    if str(workspace.resolve()) != journal.get("workspace"):
        fail("rollback workspace does not match journal")
    status = journal.get("status")
    if status not in {"prepared", "applying", "applied", "rolling-back", "rolled-back"}:
        fail("rollback journal status is invalid")
    rows = journal.get("paths")
    if not isinstance(rows, list) or not rows:
        fail("rollback journal has no managed paths")
    if portal:
        portal_journal(workspace, journal)
    seen = set()
    plan = []
    # Validate every object, destination and current post-state before the first
    # mutation. A corrupt late object or newer managed edit cannot cause a partial
    # rollback or be silently overwritten.
    for row in rows:
        logical = checked_relative(row.get("logical", ""), "journal logical path")
        destination_rel = checked_relative(row.get("destination", ""), "journal destination path")
        if logical in seen:
            fail(f"rollback journal repeats managed path: {logical}")
        seen.add(logical)
        destination = workspace / destination_rel
        reject_symlink_chain(workspace, destination, "rollback destination")
        source = backup / "files" / logical
        if row.get("state") == "present":
            reject_symlink_chain(backup, source, "rollback object")
            if not source.is_file() or digest(source.read_bytes()) != row.get("sha256") or file_mode(source) != row.get("mode"):
                fail(f"rollback object missing or changed: {logical}")
        elif row.get("state") != "absent":
            fail(f"invalid rollback state: {logical}")
        if destination.exists() and not destination.is_file():
            fail(f"rollback destination is not a regular file: {logical}")
        current = None if not destination.exists() else (digest(destination.read_bytes()), file_mode(destination))
        before = None if row.get("state") == "absent" else (row.get("sha256"), row.get("mode"))
        post_state = row.get("postState", "present")
        if post_state not in {"present", "absent"}:
            fail(f"invalid rollback post-state: {logical}")
        after = None if post_state == "absent" else (row.get("postSha256"), row.get("postMode"))
        allowed_current = ({before, after} if status in {"prepared", "applying", "rolling-back"}
                           else ({before} if status == "rolled-back" else {after}))
        if current not in allowed_current:
            fail(f"rollback refused before writes: managed path changed after adoption: {logical}", 3)
        plan.append((row, destination, source))
    if status == "rolled-back":
        print("complete workspace adoption: rollback already byte-identical")
        return
    journal["status"] = "rolling-back"
    write_json_durable(journal_path, journal)
    restored = 0
    for row, destination, source in reversed(plan):
        if row["state"] == "present":
            destination.parent.mkdir(parents=True, exist_ok=True)
            descriptor, temporary_name = tempfile.mkstemp(prefix=destination.name + ".fsgg-rollback-", dir=destination.parent)
            os.close(descriptor)
            temporary = Path(temporary_name)
            try:
                shutil.copy2(source, temporary)
                os.replace(temporary, destination)
            finally:
                if temporary.exists(): temporary.unlink()
        elif destination.exists():
            destination.unlink()
        restored += 1
        rollback_env = "FSGG_PORTAL_RECOVER_FAIL_AFTER" if portal else "FSGG_SVG_COMPLETE_ROLLBACK_FAIL_AFTER"
        if os.environ.get(rollback_env) == str(restored):
            raise RuntimeError(f"injected rollback interruption after {restored} managed files")
    if portal:
        for relative in reversed(journal["createdDirectories"]):
            directory = workspace / relative
            reject_symlink_chain(workspace, directory, "Portal recovery directory")
            if directory.is_dir() and not any(directory.iterdir()):
                directory.rmdir()
    journal["status"] = "rolled-back"
    write_json_durable(journal_path, journal)
    print("complete workspace adoption: byte-addressed rollback completed")


def commit_staged_paths(workspace: Path, backup: Path, paths: list[dict], metadata: dict,
                        schema: str = "fsgg.svg-complete-adoption-journal/v1",
                        failure_env: str = "FSGG_SVG_COMPLETE_FAIL_AFTER", strict: bool = False) -> None:
    """Shared durable write loop; Portal additionally checks all staged before states."""
    journal = {"schema": schema, "status": "prepared", "workspace": str(workspace.resolve()),
               **metadata, "paths": paths}
    journal_path = backup / "journal.json"
    write_json_durable(journal_path, journal)
    if strict:
        for row in paths:
            portal_before_state(workspace, row)
            portal_staged_state(backup, row)
    applied = 0
    journal["status"] = "applying"
    write_json_durable(journal_path, journal)
    for row in paths:
        logical = row["logical"]
        destination = workspace / row["destination"]
        if strict:
            portal_before_state(workspace, row)
            portal_staged_state(backup, row)
        if row["postState"] == "absent":
            if destination.exists():
                destination.unlink()
        else:
            destination.parent.mkdir(parents=True, exist_ok=True)
            descriptor, temporary_name = tempfile.mkstemp(prefix=destination.name + ".fsgg-adoption-", dir=destination.parent)
            os.close(descriptor)
            temporary = Path(temporary_name)
            try:
                shutil.copy2(backup / "staged" / logical, temporary)
                if strict:
                    portal_before_state(workspace, row)
                    if digest(temporary.read_bytes()) != row["postSha256"] or file_mode(temporary) != row["postMode"]:
                        fail("Portal temporary staged object differs before write", 3)
                os.replace(temporary, destination)
            finally:
                if temporary.exists(): temporary.unlink()
        applied += 1
        if os.environ.get(failure_env) == str(applied):
            raise RuntimeError(f"injected interruption after {applied} managed files")
    journal["status"] = "applied"
    write_json_durable(journal_path, journal)


def apply(args: list[str]) -> None:
    if len(args) != 5:
        fail("usage: complete-apply <candidate> <workspace> <baseline-manifest> <inventory.json> <backup>")
    candidate, workspace, manifest_path, inventory_path, backup = map(Path, args)
    if backup.is_absolute() is False:
        backup = backup.absolute()
    reject_symlink_chain(backup.parent, backup, "backup")
    if backup.exists() or backup.is_symlink():
        fail(f"backup target already exists: {backup}")
    accepted = load_json(inventory_path)
    current = classify(candidate, workspace, manifest_path)
    current.pop("diff")
    for key in ("ready", "candidate", "workspace", "manifest", "manifestSha256",
                "candidateManagedSha256", "workspaceTreeSha256", "changes", "conflicts"):
        if accepted.get(key) != current.get(key):
            fail(f"inventory is stale or mismatched at {key}", 3)
    review_path = Path(accepted.get("reviewDiff", ""))
    if not review_path.is_file() or digest(review_path.read_bytes()) != accepted.get("reviewDiffSha256"):
        fail("review diff is missing or changed", 3)
    if not current["ready"]:
        fail("inventory contains managed collisions", 3)

    _, managed, retired, _ = manifest_data(manifest_path)
    managed, retired = effective_paths(workspace, managed, retired)
    source_product, source_namespace, source_solution = identity(candidate)
    destination_product, destination_namespace, destination_solution = identity(workspace)
    backup.mkdir(parents=True)
    (backup / "files").mkdir()
    (backup / "staged").mkdir()
    paths = []
    try:
        for logical in managed:
            destination = actual_path(workspace, logical, destination_solution)
            destination_rel = destination.relative_to(workspace).as_posix()
            staged = backup / "staged" / logical
            staged.parent.mkdir(parents=True, exist_ok=True)
            staged.write_bytes(candidate_bytes(candidate, logical, source_solution, source_product,
                                                source_namespace, destination_product, destination_namespace,
                                                destination))
            source_mode = file_mode(candidate_path(candidate, logical, source_solution))
            staged.chmod(source_mode)
            if destination.exists():
                saved = backup / "files" / logical
                saved.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(destination, saved)
                paths.append({"logical": logical, "destination": destination_rel,
                              "state": "present", "sha256": digest(saved.read_bytes()), "mode": file_mode(saved),
                              "postState": "present", "postSha256": digest(staged.read_bytes()), "postMode": source_mode})
            else:
                paths.append({"logical": logical, "destination": destination_rel, "state": "absent",
                              "postState": "present", "postSha256": digest(staged.read_bytes()), "postMode": source_mode})
        for logical in retired:
            destination = actual_path(workspace, logical, destination_solution)
            destination_rel = destination.relative_to(workspace).as_posix()
            if destination.exists():
                saved = backup / "files" / logical
                saved.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(destination, saved)
                paths.append({"logical": logical, "destination": destination_rel,
                              "state": "present", "sha256": digest(saved.read_bytes()), "mode": file_mode(saved),
                              "postState": "absent"})
            else:
                paths.append({"logical": logical, "destination": destination_rel,
                              "state": "absent", "postState": "absent"})
        commit_staged_paths(workspace, backup, paths,
                            {"inventorySha256": digest(inventory_path.read_bytes()),
                             "manifestSha256": digest(manifest_path.read_bytes())})
    except BaseException as error:
        if (backup / "journal.json").is_file():
            restore(workspace, backup)
            fail(f"apply failed and rollback completed: {error}")
        shutil.rmtree(backup)
        fail(f"apply preparation failed before workspace writes: {error}")
    print(f"complete workspace adoption: applied {len(paths)} managed files; preserved {len(current['preserved'])} inventoried files; rollback={backup}")


# Portal schemas are separate from the historical SVG manifest/skill classifier.
PORTAL_SCHEMA = "fsgg.portal.example-source/1"
PORTAL_PATHS = tuple("PortalExample/" + name for name in sorted({
    "Consumer.fsproj", "PortalScene.fs", "Presentation.fs", "Program.fs", "README.md",
    "packages.lock.json", "source-provenance.json", "verify-package-boundary.py", "manage.py",
}))
PORTAL_CANONICAL = {
    "Consumer.fsproj": "0c9929c2fddab032cb3f0f55ced0df30552a0f9eb9604184e8d0e10940678e70",
    "PortalScene.fs": "24c91caaa54c1a09ba342355395b8c9796054aa31619aa2d4a68b425ff5aaf7e",
    "Presentation.fs": "22b29b4670e23d133bdd4cc56b03a09a252b4ebec10f187065a6d4d1e2bd687f",
    "Program.fs": "dda86d3ea3b4349f98512a5ef6173202abc6268565fe1ba283d7071a0442998f",
    "verify-package-boundary.py": "4ed89d48e403b9e5ab496a52497e4fa926e6259e487061bddebab2fb03e713c8",
    "packages.lock.json": "7769c72f28bca3fc4b40e6ce710852c8d5e26098c5e6d5c35cefbe9f7c11f66b",
}
PORTAL_README_SHA = "402d784e0561cb3f4f226667a03bc86cb594f8c0d3a5c54c4c38b2b99aedd7ac"
PORTAL_PUBLIC_BASELINE_SHA = "0d9395b028f14b2c06afe1f1de019610217774f0cb8b6a9618f2aed7d51790fe"
PORTAL_PUBLIC_BASELINE_SOURCE = "d9fe65ea8a456f59d663f20c647a38a195e13c2c"


def portal_regular(root: Path, logical: str) -> Path:
    path = root / logical
    reject_symlink_chain(Path("/"), path.absolute(), "Portal input")
    if not path.is_file():
        fail(f"Portal input missing or not regular: {logical}")
    return path


def portal_external(path: Path, *roots: Path) -> None:
    reject_symlink_chain(Path("/"), path.absolute(), "Portal external path")
    for root in roots:
        if path.absolute().is_relative_to(root.absolute()):
            fail(f"Portal inventory, review, candidate and backup must be outside receiver: {path}")


def portal_payload(candidate: Path) -> tuple[dict, dict[str, tuple[bytes, int]]]:
    identity(candidate)
    folder = candidate / "PortalExample"
    reject_symlink_chain(Path("/"), folder.absolute(), "Portal candidate")
    actual = {p.relative_to(candidate).as_posix() for p in folder.iterdir()} if folder.is_dir() else set()
    if actual != set(PORTAL_PATHS):
        fail("Portal candidate has missing or foreign files")
    payload = {logical: (portal_regular(candidate, logical).read_bytes(),
                         file_mode(candidate / logical)) for logical in PORTAL_PATHS}
    manifest = load_json(candidate / "PortalExample/source-provenance.json")
    if (not isinstance(manifest, dict) or manifest.get("schema") != PORTAL_SCHEMA or manifest.get("templateId") != "fs-gg-fable-game"
            or manifest.get("managedPaths") != [p.removeprefix("PortalExample/") for p in PORTAL_PATHS]
            or manifest.get("gameSource") != {"repository": "https://github.com/FS-GG/FS.GG.Game",
                "revision": "49c7f5a74f2470f68e626b68293d5207c2068a93",
                "tree": "c2aa7259568ddb54f5397ff978ca3baa6d942255"}):
        fail("Portal candidate provenance is unsupported")
    if (manifest.get("feature") != "GAME-PORTAL-01" or manifest.get("item") != "GAME-PORTAL-01.P3"
            or manifest.get("selection") != {"parameter": "portalExample", "default": False,
                "backend": "independent-managed-dotnet10", "browserPhysics": False,
                "productionServerIntegration": False}):
        fail("Portal candidate scope provenance differs")
    for name, expected in PORTAL_CANONICAL.items():
        if digest(payload["PortalExample/" + name][0]) != expected:
            fail(f"Portal canonical source or lock differs: {name}")
    own = Path(__file__).resolve().read_bytes()
    if payload["PortalExample/manage.py"][0] != own:
        fail("Portal management helper differs from executing qualified producer")
    if digest(payload["PortalExample/README.md"][0]) != PORTAL_README_SHA:
        fail("Portal README differs from selected producer")
    expected_template = [{"path": "README.md", "sha256": PORTAL_README_SHA},
                         {"path": "manage.py", "producerPath": "scripts/apply-svg-complete-workspace.py",
                          "sha256": digest(own)}]
    if manifest.get("templateFiles") != expected_template:
        fail("Portal template helper/README provenance differs")
    producers = {"Consumer.fsproj": "tests/release/Box2D.PackageConsumer/PresentationConsumer.fsproj",
        "PortalScene.fs": "examples/Box2D.Portals/Scene.fs", "Presentation.fs": "examples/Box2D.Portals/Presentation.fs",
        "Program.fs": "examples/Box2D.Portals/Program.fs", "verify-package-boundary.py": "tests/release/Box2D.PackageConsumer/verify-package-boundary.py"}
    expected_rows = [{"destination": name, "producerPath": path, "sha256": PORTAL_CANONICAL[name]} for name, path in producers.items()]
    if manifest.get("canonicalFiles") != expected_rows or manifest.get("lock", {}).get("sha256") != PORTAL_CANONICAL["packages.lock.json"]:
        fail("Portal canonical file provenance is forged or unsupported")
    expected_closure = {"FS.GG.Game.Core": "0.17.0", "FS.GG.Game.Physics.Box2D": "0.17.0",
        "FS.GG.Game.Render": "0.17.0", "FS.GG.UI.Scene": "0.31.0", "FS.GG.UI.KeyboardInput": "0.31.0",
        "Box2D.NET": "3.1.654", "FSharp.Core": "10.1.302"}
    if manifest.get("packageClosure") != expected_closure:
        fail("Portal declared seven-package closure differs")
    return manifest, payload


def portal_baseline(archive: Path, workspace: Path) -> dict:
    """Authenticate the actual public archive and unchanged ordinary project defaults."""
    from zipfile import ZipFile
    import xml.etree.ElementTree as ET
    portal_regular(archive.parent, archive.name)
    if digest(archive.read_bytes()) != PORTAL_PUBLIC_BASELINE_SHA:
        fail("Portal initial adoption requires authentic public Templates 0.18.1 archive")
    product, namespace, _ = identity(workspace)
    with ZipFile(archive) as package:
        names = package.namelist()
        if len(names) != len(set(names)) or any("portalexample" in p.lower() for p in names):
            fail("Portal public baseline archive is contrary or ambiguous")
        nuspec = [p for p in names if p.endswith(".nuspec")]
        if len(nuspec) != 1:
            fail("Portal public baseline nuspec is missing or ambiguous")
        root = ET.fromstring(package.read(nuspec[0]))
        fields = {e.tag.split("}")[-1]: e.text for e in root.iter()
                  if e.tag.split("}")[-1] in {"id", "version"}}
        repositories = [e.attrib for e in root.iter() if e.tag.split("}")[-1] == "repository"]
        if fields != {"id": "FS.GG.Workspace.Template", "version": "0.18.1"} or len(repositories) != 1 or repositories[0].get("commit") != PORTAL_PUBLIC_BASELINE_SOURCE:
            fail("Portal public baseline package identity differs")
        prefix = "content/templates/fs-gg-fable-game/"
        config = json.loads(package.read(prefix + ".template.config/template.json"))
        if "portalExample" in config.get("symbols", {}):
            fail("Portal public baseline already declares Portal")
        # Authored gameplay files remain free to change; the independent ordinary
        # project graph, SDK/cache controls and locks must match this supported baseline.
        core = ["global.json", "Directory.Build.props", "Domain/Domain.fsproj",
                "Server/Server.fsproj", "Client/Client.fsproj"]
        core += [p[len(prefix):] for p in names if p.startswith(prefix)
                 and p.endswith("/packages.lock.json")
                 and p[len(prefix):].split("/")[0] in {"Domain", "Server", "Client"}]
        for logical in core:
            current = portal_regular(workspace, logical).read_bytes()
            if digest(package.read(prefix + logical)) not in canonical_variants(current, product, namespace):
                fail(f"Portal receiver ordinary baseline differs: {logical}")
    return {"package": "FS.GG.Workspace.Template", "version": "0.18.1",
            "archiveSha256": PORTAL_PUBLIC_BASELINE_SHA, "sourceCommit": PORTAL_PUBLIC_BASELINE_SOURCE}


def portal_classify(candidate: Path, workspace: Path, archive: Path, remove: bool = False) -> dict:
    for root in (candidate, workspace):
        reject_symlink_chain(Path("/"), root.absolute(), "Portal workspace")
    portal_external(candidate, workspace)
    portal_external(workspace, candidate)
    manifest, payload = portal_payload(candidate)
    baseline = portal_baseline(archive, workspace)
    _, namespace, solution = identity(workspace)
    folder = workspace / "PortalExample"
    reject_symlink_chain(workspace, folder, "Portal destination")
    if folder.exists() and not folder.is_dir():
        fail("Portal destination folder is not a directory")
    provenance_path = folder / "source-provenance.json"
    owned = provenance_path.exists() and portal_regular(workspace, "PortalExample/source-provenance.json").read_bytes() == payload["PortalExample/source-provenance.json"][0]
    changes, conflicts, unchanged, diff = [], [], [], []
    for logical, (raw, mode) in payload.items():
        destination = workspace / logical
        reject_symlink_chain(workspace, destination, "Portal destination")
        if destination.exists():
            if not destination.is_file():
                conflicts.append({"path": logical, "reason": "managed destination not regular"}); continue
            current, current_mode = destination.read_bytes(), file_mode(destination)
            if not owned or current != raw or current_mode != mode:
                conflicts.append({"path": logical, "reason": "unowned, edited or unsupported managed file"}); continue
            if remove:
                changes.append({"path": logical, "state": "delete", "currentSha256": digest(current), "currentMode": current_mode})
                diff.extend(difflib.unified_diff(current.decode().splitlines(True), [], fromfile="a/" + logical, tofile="/dev/null"))
            else:
                unchanged.append(logical)
        elif owned or remove:
            conflicts.append({"path": logical, "reason": "owned payload incomplete or missing"})
        else:
            changes.append({"path": logical, "state": "add", "candidateSha256": digest(raw), "candidateMode": mode})
            diff.extend(difflib.unified_diff([], raw.decode().splitlines(True), fromfile="/dev/null", tofile="b/" + logical))
    tree_sha, rows = tree_observation(workspace)
    st = workspace.stat()
    return {"schema": "fsgg.portal.adoption-inventory/1", "operation": "remove" if remove else "apply",
            "ready": not conflicts, "candidate": str(candidate.resolve()), "workspace": str(workspace.resolve()),
            "receiverIdentity": {"product": solution.stem, "namespace": namespace, "device": st.st_dev, "inode": st.st_ino},
            "publicBaseline": baseline, "candidateManifestSha256": digest(payload["PortalExample/source-provenance.json"][0]),
            "candidateManagedSha256": digest("".join(f"{mode:o}\t{digest(raw)}\t{logical}\n" for logical, (raw, mode) in payload.items()).encode()),
            "workspaceTreeSha256": tree_sha, "workspaceFiles": rows, "changes": changes,
            "conflicts": conflicts, "unchangedManaged": unchanged,
            "preserved": [r["path"] for r in rows if r["path"] not in PORTAL_PATHS], "diff": "".join(diff)}


def portal_inventory(args: list[str]) -> None:
    remove = bool(args and args[-1] == "--remove")
    if remove: args = args[:-1]
    if len(args) != 5:
        fail("usage: portal-inventory <candidate> <workspace> <public-0.18.1.nupkg> <inventory.json> <review.diff> [--remove]")
    candidate, workspace, archive, output, review = map(Path, args)
    for path in (output, review): portal_external(path, candidate, workspace)
    if output.exists() or review.exists(): fail("Portal inventory/review output already exists")
    observation = portal_classify(candidate, workspace, archive, remove)
    review.parent.mkdir(parents=True, exist_ok=True); review.write_text(observation.pop("diff"))
    observation.update(reviewDiff=str(review.absolute()), reviewDiffSha256=digest(review.read_bytes()))
    write_json_durable(output, observation)
    print(f"Portal inventory ready={observation['ready']} changes={len(observation['changes'])}")
    if not observation["ready"]: raise SystemExit(3)


def portal_before_state(workspace: Path, row: dict) -> None:
    destination = workspace / row["destination"]
    reject_symlink_chain(workspace, destination, "Portal transaction destination")
    if destination.exists() and not destination.is_file(): fail("Portal late destination type conflict", 3)
    actual = (digest(destination.read_bytes()), file_mode(destination)) if destination.exists() else None
    expected = (row["sha256"], row["mode"]) if row["state"] == "present" else None
    if actual != expected: fail(f"Portal late managed conflict before write: {row['logical']}", 3)


def portal_staged_state(backup: Path, row: dict) -> None:
    if row["postState"] == "present":
        path = portal_regular(backup, "staged/" + row["logical"])
        if digest(path.read_bytes()) != row["postSha256"] or file_mode(path) != row["postMode"]:
            fail(f"Portal staged object differs before write: {row['logical']}", 3)


def portal_journal(workspace: Path, journal: dict) -> None:
    paths = journal.get("paths", [])
    if (not isinstance(paths, list) or any(not isinstance(r, dict) for r in paths) or len(paths) != len(PORTAL_PATHS)
            or [r.get("logical") for r in paths] != list(PORTAL_PATHS)
            or any(r.get("destination") != r.get("logical") for r in paths)
            or journal.get("operation") not in {"apply", "remove"}
            or journal.get("createdDirectories") not in [[], ["PortalExample"]]):
        fail("Portal recovery journal scope is invalid")
    product, namespace, _ = identity(workspace); st = workspace.stat()
    if journal.get("receiverIdentity") != {"product": product, "namespace": namespace, "device": st.st_dev, "inode": st.st_ino}:
        fail("Portal recovery journal receiver identity differs")
    for row in paths:
        for key in ("sha256", "postSha256"):
            if key in row and not re.fullmatch(r"[0-9a-f]{64}", str(row[key])):
                fail("Portal recovery journal hash is invalid")
        for key in ("mode", "postMode"):
            if key in row and (type(row[key]) is not int or not 0 <= row[key] <= 0o7777):
                fail("Portal recovery journal mode is invalid")


def portal_apply(args: list[str], remove: bool = False) -> None:
    if len(args) != 5:
        fail("usage: portal-apply/remove <candidate> <workspace> <public-0.18.1.nupkg> <inventory.json> <backup>")
    candidate, workspace, archive, inventory_path, backup = map(Path, args)
    for path in (inventory_path, backup): portal_external(path, candidate, workspace)
    if backup.exists(): fail("Portal backup already exists")
    accepted = load_json(inventory_path)
    if not isinstance(accepted, dict): fail("Portal accepted inventory is not an object")
    current = portal_classify(candidate, workspace, archive, remove); current.pop("diff")
    for key, value in current.items():
        if accepted.get(key) != value: fail(f"Portal inventory stale or mismatched at {key}", 3)
    review = Path(accepted.get("reviewDiff", "")); portal_external(review, candidate, workspace)
    if not review.is_file() or digest(review.read_bytes()) != accepted.get("reviewDiffSha256"):
        fail("Portal review diff missing or changed", 3)
    if not current["ready"]: fail("Portal inventory contains conflicts", 3)
    if not current["changes"]:
        print("Portal current payload already byte-and-mode-identical; no writes or backup"); return
    _, payload = portal_payload(candidate)
    backup.mkdir(mode=0o700, parents=True); (backup / "files").mkdir(mode=0o700); (backup / "staged").mkdir(mode=0o700)
    paths = []
    try:
        for logical, (raw, mode) in payload.items():
            destination = workspace / logical
            row = {"logical": logical, "destination": logical,
                   "state": "present" if destination.exists() else "absent",
                   "postState": "absent" if remove else "present"}
            if destination.exists():
                saved = backup / "files" / logical; saved.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(destination, saved); row.update(sha256=digest(saved.read_bytes()), mode=file_mode(saved))
            if not remove:
                staged = backup / "staged" / logical; staged.parent.mkdir(parents=True, exist_ok=True)
                staged.write_bytes(raw); staged.chmod(mode); row.update(postSha256=digest(raw), postMode=mode)
            paths.append(row)
        metadata = {"operation": current["operation"], "receiverIdentity": current["receiverIdentity"], "publicBaseline": current["publicBaseline"],
                    "inventorySha256": digest(inventory_path.read_bytes()), "candidateManifestSha256": current["candidateManifestSha256"],
                    "createdDirectories": [] if (workspace / "PortalExample").exists() else ["PortalExample"]}
        commit_staged_paths(workspace, backup, paths, metadata,
                            schema="fsgg.portal.adoption-journal/1", failure_env="FSGG_PORTAL_FAIL_AFTER", strict=True)
    except BaseException as error:
        if (backup / "journal.json").is_file():
            try:
                restore(workspace, backup, portal=True)
            except BaseException as recovery_error:
                fail(f"Portal apply failed; recovery refused or interrupted, journal retained, cleanup unknown: {error}; {recovery_error}", 3)
            fail(f"Portal apply failed and verified rollback completed: {error}")
        shutil.rmtree(backup)
        fail(f"Portal preparation failed before receiver writes: {error}")
    print(f"Portal {current['operation']} committed; managed={len(paths)} preserved={len(current['preserved'])}; journal={backup}")


def main() -> None:
    if len(sys.argv) < 2:
        fail("command required")
    command, args = sys.argv[1], sys.argv[2:]
    if command == "portal-inventory":
        portal_inventory(args)
    elif command in {"portal-apply", "portal-remove"}:
        portal_apply(args, remove=command == "portal-remove")
    elif command == "portal-recover":
        if len(args) != 2:
            fail("usage: portal-recover <workspace> <backup>")
        restore(Path(args[0]), Path(args[1]), portal=True)
    elif command == "complete-inventory":
        inventory(args)
    elif command == "complete-apply":
        apply(args)
    elif command in {"complete-rollback", "complete-recover"}:
        if len(args) != 2:
            fail(f"usage: {command} <workspace> <backup>")
        restore(Path(args[0]), Path(args[1]))
    else:
        fail(f"unsupported complete-workspace command: {command}")


if __name__ == "__main__":
    main()
