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
    # PurePosixPath normalizes "." and repeated separators before exposing
    # parts. Refuse their raw spellings so two manifest rows cannot name one
    # physical managed target under different strings.
    if (not isinstance(value, str) or not value or "\x00" in value or "\\" in value
            or re.match(r"^[A-Za-z]:", value)
            or any(part in {"", ".", ".."} for part in value.split("/"))):
        fail(f"{label} is not a safe relative path: {value}")
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


def unique_json_pairs(pairs: list[tuple[str, object]]) -> dict:
    value = {}
    for key, item in pairs:
        if key in value:
            raise ValueError(f"duplicate JSON key: {key}")
        value[key] = item
    return value


def load_json(path: Path) -> dict:
    try:
        return json.loads(path.read_text(), object_pairs_hook=unique_json_pairs)
    except (OSError, json.JSONDecodeError, ValueError) as error:
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


def restore(workspace: Path, backup: Path) -> None:
    if workspace.is_symlink() or not workspace.is_dir():
        fail(f"rollback workspace is missing, not a directory, or a symlink: {workspace}")
    if backup.is_symlink() or not backup.is_dir():
        fail(f"rollback backup is missing, not a directory, or a symlink: {backup}")
    reject_symlink_chain(backup.parent, backup, "rollback backup")
    journal_path = backup / "journal.json"
    reject_symlink_chain(backup, journal_path, "rollback journal")
    journal = load_json(journal_path)
    if journal.get("schema") != "fsgg.svg-complete-adoption-journal/v1":
        fail("unsupported rollback journal")
    if str(workspace.resolve()) != journal.get("workspace"):
        fail("rollback workspace does not match journal")
    status = journal.get("status")
    if status not in {"prepared", "applying", "applied", "rolling-back", "rolled-back"}:
        fail("rollback journal status is invalid")
    rows = journal.get("paths")
    if not isinstance(rows, list) or not rows:
        fail("rollback journal has no managed paths")
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
        if os.environ.get("FSGG_SVG_COMPLETE_ROLLBACK_FAIL_AFTER") == str(restored):
            raise RuntimeError(f"injected rollback interruption after {restored} managed files")
    journal["status"] = "rolled-back"
    write_json_durable(journal_path, journal)
    print("complete workspace adoption: byte-addressed rollback completed")


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
        journal = {"schema": "fsgg.svg-complete-adoption-journal/v1", "status": "prepared",
                   "workspace": str(workspace.resolve()), "inventorySha256": digest(inventory_path.read_bytes()),
                   "manifestSha256": digest(manifest_path.read_bytes()), "paths": paths}
        journal_path = backup / "journal.json"
        write_json_durable(journal_path, journal)
        applied = 0
        journal["status"] = "applying"
        write_json_durable(journal_path, journal)
        for row in paths:
            logical = row["logical"]
            destination = workspace / row["destination"]
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
                    os.replace(temporary, destination)
                finally:
                    if temporary.exists(): temporary.unlink()
            applied += 1
            if os.environ.get("FSGG_SVG_COMPLETE_FAIL_AFTER") == str(applied):
                raise RuntimeError(f"injected interruption after {applied} managed files")
        journal["status"] = "applied"
        write_json_durable(journal_path, journal)
    except BaseException as error:
        if (backup / "journal.json").is_file():
            restore(workspace, backup)
            fail(f"apply failed and rollback completed: {error}")
        shutil.rmtree(backup)
        fail(f"apply preparation failed before workspace writes: {error}")
    print(f"complete workspace adoption: applied {len(paths)} managed files; preserved {len(current['preserved'])} inventoried files; rollback={backup}")


def main() -> None:
    if len(sys.argv) < 2:
        fail("command required")
    command, args = sys.argv[1], sys.argv[2:]
    if command == "complete-inventory":
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
