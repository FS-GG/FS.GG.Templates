#!/usr/bin/env python3
"""Create policy-bound OCI import archives by changing only the index image name."""
import argparse, copy, hashlib, json, os, shutil, subprocess, tarfile, tempfile
from pathlib import Path, PurePosixPath

HERE = Path(__file__).resolve().parent
POLICY_PATH = HERE / "policy.json"
POLICY = json.loads(POLICY_PATH.read_text())
MAX_JSON = 1024 * 1024
HEX = set("0123456789abcdef")
REF_ANNOTATION = "org.opencontainers.image.ref.name"
OCI_MANIFEST = "application/vnd.oci.image.manifest.v1+json"
OCI_CONFIG = "application/vnd.oci.image.config.v1+json"
OCI_LAYER = "application/vnd.oci.image.layer.v1.tar+gzip"

class Refusal(RuntimeError): pass

def require(value, reason):
    if not value: raise Refusal(reason)

def canonical(value): return (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode()

def sha_file(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""): digest.update(block)
    return digest.hexdigest()

def safe_name(name):
    parsed = PurePosixPath(name)
    return bool(name) and not parsed.is_absolute() and ".." not in parsed.parts and "" not in parsed.parts and str(parsed) == name.rstrip("/")

def read_json(data, label):
    require(len(data) <= MAX_JSON, label + "-too-large")
    try: return json.loads(data)
    except Exception as error: raise Refusal(label + "-invalid-json") from error

def exact_source(root, revision):
    def git(*arguments):
        result = subprocess.run(["git", "-C", str(root), *arguments], stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
        require(result.returncode == 0, "source-git-refused")
        return result.stdout
    require(len(revision) == 40 and set(revision) <= HEX, "source-revision-refused")
    require(git("rev-parse", "HEAD").decode().strip() == revision, "source-revision-mismatch")
    require(git("status", "--porcelain") == b"", "source-working-tree-not-clean")
    tree = git("rev-parse", revision + "^{tree}").decode().strip()
    require(len(tree) == 40 and set(tree) <= HEX, "source-tree-refused")
    committed = git("show", revision + ":eng/language-route-bindings/policy.json")
    require(hashlib.sha256(committed).hexdigest() == sha_file(POLICY_PATH), "committed-policy-mismatch")
    return tree

def archive_members(archive, kind):
    members = {}
    for member in archive.getmembers():
        require(safe_name(member.name), kind + "-member-path-refused")
        require(member.isfile() or member.isdir(), kind + "-member-type-refused")
        require(member.name not in members, kind + "-duplicate-member")
        members[member.name] = member
    return members

def member_bytes(archive, members, name, label, maximum=None):
    member = members.get(name)
    require(member is not None and member.isfile(), label + "-missing")
    if maximum is not None: require(member.size <= maximum, label + "-too-large")
    stream = archive.extractfile(member); require(stream is not None, label + "-unreadable")
    data = stream.read((maximum + 1) if maximum is not None else -1)
    if maximum is not None: require(len(data) <= maximum, label + "-too-large")
    require(len(data) == member.size, label + "-size-mismatch")
    return data

def descriptor(archive, members, value, label, media_type):
    require(isinstance(value, dict) and value.get("mediaType") == media_type, label + "-media-type-refused")
    digest = value.get("digest", "")
    require(isinstance(digest, str) and digest.startswith("sha256:") and len(digest) == 71 and set(digest[7:]) <= HEX, label + "-digest-refused")
    size = value.get("size")
    require(isinstance(size, int) and not isinstance(size, bool) and size >= 0, label + "-size-refused")
    name = "blobs/sha256/" + digest[7:]
    member = members.get(name)
    require(member is not None and member.isfile() and member.size == size, label + "-blob-size-mismatch")
    stream = archive.extractfile(member); require(stream is not None, label + "-blob-unreadable")
    actual = hashlib.sha256(); count = 0
    for block in iter(lambda: stream.read(1024 * 1024), b""):
        count += len(block); actual.update(block)
    require(count == size and actual.hexdigest() == digest[7:], label + "-blob-digest-mismatch")
    return name, digest

def member_bytes_equal(left, left_member, right, right_member, label):
    require(left_member.isfile() and right_member.isfile() and left_member.size == right_member.size, label + "-size-mismatch")
    left_stream=left.extractfile(left_member); right_stream=right.extractfile(right_member)
    require(left_stream is not None and right_stream is not None, label + "-unreadable")
    while True:
        left_block=left_stream.read(1024 * 1024); right_block=right_stream.read(1024 * 1024)
        require(left_block == right_block, label + "-changed")
        if not left_block: return

def archive_identity(path, kind, expected, annotation):
    require(path.is_file() and not path.is_symlink(), kind + "-archive-refused")
    require(sha_file(path) == expected["archiveSha256"], kind + "-archive-sha-mismatch")
    with tarfile.open(path, "r:") as archive:
        members = archive_members(archive, kind)
        layout_bytes = member_bytes(archive, members, "oci-layout", kind + "-layout", MAX_JSON)
        require(read_json(layout_bytes, kind + "-layout") == {"imageLayoutVersion":"1.0.0"}, kind + "-layout-refused")
        index_bytes = member_bytes(archive, members, "index.json", kind + "-index", MAX_JSON)
        require(hashlib.sha256(index_bytes).hexdigest() == expected["indexSha256"], kind + "-index-sha-mismatch")
        index = read_json(index_bytes, kind + "-index")
        manifests = index.get("manifests", [])
        require(index.get("schemaVersion") == 2 and isinstance(manifests, list) and len(manifests) == 1, kind + "-index-refused")
        manifest_desc = manifests[0]
        require(manifest_desc.get("annotations", {}).get(REF_ANNOTATION) == annotation, kind + "-index-annotation-refused")
        manifest_name, manifest_digest = descriptor(archive, members, manifest_desc, kind + "-manifest", OCI_MANIFEST)
        require(manifest_digest == expected["manifestDigest"], kind + "-manifest-policy-mismatch")
        manifest_bytes = member_bytes(archive, members, manifest_name, kind + "-manifest-json", MAX_JSON)
        manifest = read_json(manifest_bytes, kind + "-manifest-json")
        require(manifest.get("schemaVersion") == 2, kind + "-manifest-schema-refused")
        config_name, config_digest = descriptor(archive, members, manifest.get("config"), kind + "-config", OCI_CONFIG)
        require(config_digest == expected["configDigest"], kind + "-config-policy-mismatch")
        config = read_json(member_bytes(archive, members, config_name, kind + "-config-json", MAX_JSON), kind + "-config-json")
        settings = config.get("config", {})
        require(config.get("architecture") == "amd64" and config.get("os") == "linux", kind + "-platform-refused")
        require(settings.get("User") == "32768:32768" and settings.get("Entrypoint") in (None, []) and settings.get("Cmd") in (None, []), kind + "-config-refused")
        layers = manifest.get("layers")
        require(isinstance(layers, list) and layers, kind + "-layers-refused")
        layer_names, layer_digests = [], []
        for position, layer in enumerate(layers):
            name, digest = descriptor(archive, members, layer, f"{kind}-layer-{position}", OCI_LAYER)
            layer_names.append(name); layer_digests.append(digest)
        expected_names = {"blobs", "blobs/sha256", "oci-layout", "index.json", manifest_name, config_name, *layer_names}
        require(set(members) == expected_names, kind + "-member-inventory-refused")
        inventory = []
        for name in sorted(members):
            member = members[name]
            entry = {"name":name,"type":"file" if member.isfile() else "directory","size":member.size}
            if member.isfile():
                if name == "index.json": entry["sha256"] = hashlib.sha256(index_bytes).hexdigest()
                elif name == "oci-layout": entry["sha256"] = hashlib.sha256(layout_bytes).hexdigest()
                else: entry["sha256"] = name.rsplit("/", 1)[1]
            inventory.append(entry)
        inventory_digest = hashlib.sha256(canonical(inventory)).hexdigest()
        require(inventory_digest == expected["memberInventorySha256"], kind + "-member-inventory-sha-mismatch")
        return {"archiveSha256":expected["archiveSha256"],"indexSha256":expected["indexSha256"],"annotation":annotation,"manifestDigest":manifest_digest,"configDigest":config_digest,"layerDigests":layer_digests,"memberInventorySha256":inventory_digest,"memberCount":len(members)}

def changed_index(original, old_name, new_name, kind):
    old = json.dumps(old_name, ensure_ascii=False).encode()
    new = json.dumps(new_name, ensure_ascii=False).encode()
    require(original.count(old) == 1, kind + "-index-annotation-bytes-refused")
    derived = original.replace(old, new)
    before = read_json(original, kind + "-original-index")
    after = read_json(derived, kind + "-derived-index")
    before["manifests"][0]["annotations"][REF_ANNOTATION] = new_name
    require(before == after, kind + "-index-change-not-isolated")
    return derived

def derive_archive(original_path, output_path, kind, policy):
    original = archive_identity(original_path, kind, policy["original"], policy["originalAnnotation"])
    original_stat = original_path.stat()
    with tarfile.open(original_path, "r:") as source, tarfile.open(output_path, "x", format=tarfile.PAX_FORMAT) as target:
        members = archive_members(source, kind)
        original_index = member_bytes(source, members, "index.json", kind + "-index", MAX_JSON)
        replacement = changed_index(original_index, policy["originalAnnotation"], policy["importName"], kind)
        for member in source.getmembers():
            copied = copy.copy(member)
            if member.name == "index.json":
                copied.size = len(replacement)
                import io
                target.addfile(copied, io.BytesIO(replacement))
            elif member.isfile():
                stream = source.extractfile(member); require(stream is not None, kind + "-member-unreadable")
                target.addfile(copied, stream)
            else:
                target.addfile(copied)
    os.chmod(output_path, 0o600)
    require(original_path.stat().st_size == original_stat.st_size and original_path.stat().st_mtime_ns == original_stat.st_mtime_ns, kind + "-original-mutated")
    derived = archive_identity(output_path, kind, policy["derived"], policy["importName"])
    require(original["manifestDigest"] == derived["manifestDigest"] and original["configDigest"] == derived["configDigest"] and original["layerDigests"] == derived["layerDigests"], kind + "-blob-identity-changed")
    with tarfile.open(original_path, "r:") as left, tarfile.open(output_path, "r:") as right:
        left_members, right_members = archive_members(left, kind), archive_members(right, kind)
        for name in sorted(set(left_members) - {"index.json"}):
            if left_members[name].isfile():
                member_bytes_equal(left,left_members[name],right,right_members[name],kind+"-member-bytes")
    return original, derived

def prepare(args):
    source = Path(args.source_root).resolve(); revision = args.source_revision
    tree = exact_source(source, revision)
    output = Path(args.output).resolve(); require(not output.exists(), "output-already-exists")
    output.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=".language-route-import-", dir=output.parent)); os.chmod(staging, 0o700)
    try:
        images = {}
        for kind, supplied in (("rust", args.rust_archive), ("go", args.go_archive)):
            policy = POLICY["qualifiedImages"][kind]["retainedImport"]
            original_path = Path(supplied).resolve()
            derived_path = staging / f"{kind}-derived.oci.tar"
            original, derived = derive_archive(original_path, derived_path, kind, policy)
            images[kind] = {"original":original,"derived":{**derived,"candidate":derived_path.name,"reference":policy["importReference"]},"contentEquality":{"unchangedMembers":"oci-layout, manifest, config and every layer","changedMembers":["index.json"],"allReferencedBlobBytesEqual":True}}
        receipt = {"schema":"fsgg.language-route-derived-oci-import/1","acceptedNativeImport":False,"acceptedNativeExecution":False,"source":{"revision":revision,"tree":tree,"policySha256":sha_file(POLICY_PATH)},"images":images}
        receipt_path = staging / "derived-import.json"; receipt_path.write_bytes(canonical(receipt)); os.chmod(receipt_path, 0o600)
        staging.rename(output)
        final = output / receipt_path.name
        print(canonical({"receipt":str(final),"receiptSha256":sha_file(final),"nativeImportAccepted":False,"nativeExecutionAccepted":False}).decode(), end="")
    except Exception:
        shutil.rmtree(staging)
        raise

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--rust-archive",required=True); parser.add_argument("--go-archive",required=True)
    parser.add_argument("--source-root",required=True); parser.add_argument("--source-revision",required=True); parser.add_argument("--output",required=True)
    try: prepare(parser.parse_args()); return 0
    except (Refusal,OSError,tarfile.TarError) as error:
        print(json.dumps({"accepted":False,"reason":str(error)},sort_keys=True)); return 2
if __name__ == "__main__": raise SystemExit(main())
