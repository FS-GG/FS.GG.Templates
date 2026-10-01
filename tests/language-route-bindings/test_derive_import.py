import copy, hashlib, importlib.util, io, json, tarfile, tempfile, unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
def load(name,path):
    spec=importlib.util.spec_from_file_location(name,path);module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module
DERIVE=load("derived_import_test",ROOT/"eng/language-route-bindings/derive-import.py")
LOADER=load("derived_loader_test",ROOT/"eng/language-route-bindings/load-derived.py")

def canonical(value): return (json.dumps(value,sort_keys=True,separators=(",", ":"))+"\n").encode()

def make_archive(path,annotation,*,user="32768:32768",extra=False,manifest_count=1,duplicate=False,corrupt_layer=False):
    layer=b"closed-layer"; layer_digest=hashlib.sha256(layer).hexdigest()
    config=canonical({"architecture":"amd64","config":{"Cmd":[],"Entrypoint":[],"User":user},"os":"linux"}); config_digest=hashlib.sha256(config).hexdigest()
    manifest=canonical({"config":{"digest":"sha256:"+config_digest,"mediaType":DERIVE.OCI_CONFIG,"size":len(config)},"layers":[{"digest":"sha256:"+layer_digest,"mediaType":DERIVE.OCI_LAYER,"size":len(layer)}],"schemaVersion":2}); manifest_digest=hashlib.sha256(manifest).hexdigest()
    descriptor={"annotations":{DERIVE.REF_ANNOTATION:annotation},"digest":"sha256:"+manifest_digest,"mediaType":DERIVE.OCI_MANIFEST,"size":len(manifest)}
    index=canonical({"manifests":[descriptor for _ in range(manifest_count)],"schemaVersion":2})
    stored_layer=b"closed-layez" if corrupt_layer else layer
    entries=[("blobs",None),("blobs/sha256",None),("blobs/sha256/"+layer_digest,stored_layer),("blobs/sha256/"+manifest_digest,manifest),("blobs/sha256/"+config_digest,config),("index.json",index),("oci-layout",canonical({"imageLayoutVersion":"1.0.0"}))]
    if extra: entries.append(("unexpected",b"extra"))
    if duplicate: entries.append(("blobs",None))
    with tarfile.open(path,"w",format=tarfile.PAX_FORMAT) as archive:
        for name,data in entries:
            info=tarfile.TarInfo(name);info.mtime=0;info.uid=0;info.gid=0;info.mode=0o700 if data is None else 0o600
            if data is None: info.type=tarfile.DIRTYPE;info.size=0;archive.addfile(info)
            else: info.size=len(data);archive.addfile(info,io.BytesIO(data))
    return manifest_digest,config_digest

def facts(path):
    with tarfile.open(path,"r:") as archive:
        members={member.name:member for member in archive.getmembers()}
        def content(name): return archive.extractfile(members[name]).read()
        index_bytes=content("index.json"); index=json.loads(index_bytes); manifest_digest=index["manifests"][0]["digest"]
        manifest=json.loads(content("blobs/sha256/"+manifest_digest[7:])); config_digest=manifest["config"]["digest"]
        inventory=[]
        for name in sorted(members):
            member=members[name];entry={"name":name,"type":"file" if member.isfile() else "directory","size":member.size}
            if member.isfile(): entry["sha256"]=hashlib.sha256(content(name)).hexdigest() if name in ("index.json","oci-layout","unexpected") else name.rsplit("/",1)[1]
            inventory.append(entry)
    return {"archiveSha256":DERIVE.sha_file(path),"indexSha256":hashlib.sha256(index_bytes).hexdigest(),"memberInventorySha256":hashlib.sha256(canonical(inventory)).hexdigest(),"manifestDigest":manifest_digest,"configDigest":config_digest}

class DerivedImportTests(unittest.TestCase):
    def setUp(self): self.temporary=tempfile.TemporaryDirectory();self.root=Path(self.temporary.name)
    def tearDown(self): self.temporary.cleanup()
    def policy(self,original,expected,old_name,new_name):
        return {"originalAnnotation":old_name,"importName":new_name,"importReference":new_name+"@"+facts(original)["manifestDigest"],"original":facts(original),"derived":facts(expected)}
    def test_derives_only_stable_index_name_and_preserves_blob_bytes(self):
        old="localhost/fsgg-language-route@sha256:"+"a"*64;new="localhost/fsgg-language-route-rust:retained-20260930"
        original=self.root/"original.tar";expected=self.root/"expected.tar";actual=self.root/"actual.tar"
        make_archive(original,old);make_archive(expected,new)
        before=DERIVE.sha_file(original); left,right=DERIVE.derive_archive(original,actual,"rust",self.policy(original,expected,old,new))
        self.assertEqual(DERIVE.sha_file(original),before);self.assertEqual(DERIVE.sha_file(actual),facts(expected)["archiveSha256"])
        self.assertEqual(left["manifestDigest"],right["manifestDigest"]);self.assertEqual(left["configDigest"],right["configDigest"]);self.assertEqual(left["layerDigests"],right["layerDigests"])
    def test_refuses_wrong_digest_annotation_member_config_and_ambiguous_index(self):
        old="localhost/fsgg-language-route@sha256:"+"b"*64;new="localhost/fsgg-language-route-go:retained-20260930"
        good=self.root/"good.tar";expected=self.root/"expected.tar";make_archive(good,old);make_archive(expected,new);policy=self.policy(good,expected,old,new)
        wrong=copy.deepcopy(policy);wrong["original"]["archiveSha256"]="0"*64
        with self.assertRaisesRegex(DERIVE.Refusal,"archive-sha-mismatch"): DERIVE.archive_identity(good,"go",wrong["original"],old)
        wrong_index=copy.deepcopy(policy["original"]);wrong_index["indexSha256"]="0"*64
        with self.assertRaisesRegex(DERIVE.Refusal,"index-sha-mismatch"): DERIVE.archive_identity(good,"go",wrong_index,old)
        with self.assertRaisesRegex(DERIVE.Refusal,"index-annotation-refused"): DERIVE.archive_identity(good,"go",policy["original"],"changed")
        extra=self.root/"extra.tar";make_archive(extra,old,extra=True);extra_expected=facts(extra);extra_expected["memberInventorySha256"]=policy["original"]["memberInventorySha256"]
        with self.assertRaisesRegex(DERIVE.Refusal,"member-inventory-refused"): DERIVE.archive_identity(extra,"go",extra_expected,old)
        bad_config=self.root/"config.tar";make_archive(bad_config,old,user="0:0")
        with self.assertRaisesRegex(DERIVE.Refusal,"config-refused"): DERIVE.archive_identity(bad_config,"go",facts(bad_config),old)
        bad_layer=self.root/"layer.tar";make_archive(bad_layer,old,corrupt_layer=True)
        with self.assertRaisesRegex(DERIVE.Refusal,"layer-0-blob-digest-mismatch"): DERIVE.archive_identity(bad_layer,"go",facts(bad_layer),old)
        ambiguous=self.root/"ambiguous.tar";make_archive(ambiguous,old,manifest_count=2)
        with self.assertRaisesRegex(DERIVE.Refusal,"index-refused"): DERIVE.archive_identity(ambiguous,"go",facts(ambiguous),old)
        duplicate=self.root/"duplicate.tar";make_archive(duplicate,old,duplicate=True)
        duplicate_expected=facts(duplicate)
        with self.assertRaisesRegex(DERIVE.Refusal,"duplicate-member"): DERIVE.archive_identity(duplicate,"go",duplicate_expected,old)
    def test_loader_is_fixed_to_fresh_vfs_store_and_policy_archive(self):
        argv=LOADER.load_argv(Path("/usr/bin/podman"),Path("/private/store"),Path("/private/runroot"),Path("/private/rust.oci.tar"))
        self.assertEqual(argv,["/usr/bin/podman","--storage-driver=vfs","--root","/private/store","--runroot","/private/runroot","load","--input","/private/rust.oci.tar"])
        self.assertNotIn("sh",argv);self.assertNotIn("run",argv)

if __name__=="__main__": unittest.main()
