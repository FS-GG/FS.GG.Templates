import hashlib, importlib.util, io, json, os, subprocess, tarfile, tempfile, unittest, zipfile
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
spec=importlib.util.spec_from_file_location("binding_prepare",ROOT/"eng/language-route-bindings/prepare.py")
mod=importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
REAL_GIT_SOURCE_IDENTITY=mod.git_source_identity

def canon(x): return (json.dumps(x,sort_keys=True,separators=(",",":"))+"\n").encode()
def oci(path,kind):
    layer=b"fixture-layer-"+kind.encode(); ld=hashlib.sha256(layer).hexdigest()
    config=canon({"architecture":"amd64","config":{"Cmd":[],"Entrypoint":[],"User":"32768:32768"},"os":"linux","rootfs":{"diff_ids":["sha256:"+ld],"type":"layers"}}); cd=hashlib.sha256(config).hexdigest()
    manifest=canon({"config":{"digest":"sha256:"+cd,"mediaType":"application/vnd.oci.image.config.v1+json","size":len(config)},"layers":[{"digest":"sha256:"+ld,"mediaType":"application/vnd.oci.image.layer.v1.tar","size":len(layer)}],"schemaVersion":2}); md=hashlib.sha256(manifest).hexdigest()
    index=canon({"manifests":[{"digest":"sha256:"+md,"mediaType":"application/vnd.oci.image.manifest.v1+json","size":len(manifest)}],"schemaVersion":2})
    with tarfile.open(path,"w") as tf:
        for name,data in [("oci-layout",canon({"imageLayoutVersion":"1.0.0"})),("index.json",index),("blobs/sha256/"+md,manifest),("blobs/sha256/"+cd,config),("blobs/sha256/"+ld,layer)]:
            info=tarfile.TarInfo(name);info.size=len(data);info.mode=0o600;tf.addfile(info,io.BytesIO(data))
    return hashlib.sha256(path.read_bytes()).hexdigest(),md,cd

class BindingTests(unittest.TestCase):
    def setUp(self):
        self.t=tempfile.TemporaryDirectory(); self.root=Path(self.t.name); self.assembly=self.root/mod.POLICY["executor"]["assembly"];self.assembly.write_bytes(b"exact-executor")
        mod.POLICY["executor"]["assemblySha256"]=hashlib.sha256(self.assembly.read_bytes()).hexdigest(); self.dependency=self.root/"Akka.dll"; self.dependency.write_bytes(b"akka")
        mod.POLICY["executor"]["compileDependency"]["sha256"]=hashlib.sha256(self.dependency.read_bytes()).hexdigest()
        images={}
        candidates={}
        for kind in ("rust","go"):
            p=self.root/(kind+"-candidate.oci.tar"); digest,manifest_digest,config_digest=oci(p,kind); candidates[kind]=p
            mod.POLICY["qualifiedImages"][kind]["archiveSha256"]=digest
            mod.POLICY["qualifiedImages"][kind]["retainedOciManifestDigest"]="sha256:"+manifest_digest
            mod.POLICY["qualifiedImages"][kind]["configDigest"]="sha256:"+config_digest
            retained=mod.POLICY["qualifiedImages"][kind]["retainedImport"]
            retained["original"]["archiveSha256"]=digest
            retained["original"]["manifestDigest"]="sha256:"+manifest_digest
            retained["original"]["configDigest"]="sha256:"+config_digest
            retained["derived"]["manifestDigest"]="sha256:"+manifest_digest
            retained["derived"]["configDigest"]="sha256:"+config_digest
            retained["importReference"]=retained["importName"]+"@sha256:"+manifest_digest
            images[kind]={"candidate":"/private/"+p.name,"candidateSha256":digest,"id":"sha256:"+config_digest,"journal":"/private/journal","journalSha256":"2"*64,"reference":"localhost/fsgg-language-route:"+kind}
        q={"schema":"fsgg.language-route-image-qualification/1","sourceRevision":mod.POLICY["templatesCandidate"]["sourceRevision"],"sourceTree":mod.POLICY["templatesCandidate"]["sourceTree"],"inputsSha256":mod.POLICY["imageInputsSha256"],"recipeSha256":{"rust":mod.POLICY["operations"]["rust-tic-tac-toe-journey"]["recipeSha256"],"go":mod.POLICY["operations"]["go-snake-journey"]["recipeSha256"]},"images":images}
        self.artifact=self.root/"artifact.zip"
        with zipfile.ZipFile(self.artifact,"w",zipfile.ZIP_STORED) as z:
            z.writestr("manifests/qualification.json",canon(q))
            for kind,p in candidates.items(): z.write(p,p.name)
        mod.POLICY["templatesCandidate"]["artifactDigest"]="sha256:"+hashlib.sha256(self.artifact.read_bytes()).hexdigest()
        def committed(*args):
            path=args[-1]
            if path.endswith('policy.json'):return (ROOT/'eng/language-route-bindings/policy.json').read_bytes()
            operation='rust-tic-tac-toe-journey' if 'rust' in path else 'go-snake-journey'
            return (ROOT/mod.POLICY['operations'][operation]['workingDirectory']/"portable-verify.sh").read_bytes()
        mod.git_source_identity=lambda source,revision:("3"*40,committed)
    def tearDown(self): self.t.cleanup()
    def args(self):
        return type("Args",(),{"source_root":str(ROOT),"source_revision":"4"*40,"artifact_zip":str(self.artifact),"executor_assembly":str(self.assembly),"executor_compile_dependency":str(self.dependency),"output":str(self.root/"out")})()
    def test_prepares_closed_binding_without_native_claim(self):
        mod.prepare(self.args()); result=json.loads((self.root/"out/binding.json").read_text())
        self.assertFalse(result["acceptedNativeExecution"]); self.assertEqual(set(result["images"]),{"rust","go"})
        self.assertEqual(result["images"]["rust"]["importReference"],mod.POLICY["qualifiedImages"]["rust"]["retainedImport"]["importReference"])
        self.assertEqual(result["operations"]["go-snake-journey"]["executable"],"/bin/sh")
    def test_refuses_changed_artifact(self):
        with self.artifact.open("ab") as f:f.write(b"changed")
        with self.assertRaisesRegex(mod.Refusal,"artifact-digest-mismatch"): mod.prepare(self.args())
    def test_refuses_changed_executor(self):
        self.assembly.write_bytes(b"changed")
        with self.assertRaisesRegex(mod.Refusal,"executor-assembly-digest-mismatch"): mod.prepare(self.args())
    def test_refuses_candidate_not_in_trusted_image_mapping(self):
        mod.POLICY["qualifiedImages"]["rust"]["archiveSha256"]="0"*64
        with self.assertRaisesRegex(mod.Refusal,"rust-archive-policy-mismatch"): mod.prepare(self.args())
    def test_refuses_unsafe_artifact_member(self):
        with zipfile.ZipFile(self.artifact,"a") as z:z.writestr("../escape",b"x")
        mod.POLICY["templatesCandidate"]["artifactDigest"]="sha256:"+hashlib.sha256(self.artifact.read_bytes()).hexdigest()
        with self.assertRaisesRegex(mod.Refusal,"artifact-member-refused"): mod.prepare(self.args())
    def test_git_source_identity_refuses_changed_worktree(self):
        repo=self.root/"source";repo.mkdir();subprocess.run(["git","init","-q",str(repo)],check=True)
        (repo/"wrapper.sh").write_text("one\n")
        subprocess.run(["git","-C",str(repo),"add","wrapper.sh"],check=True)
        subprocess.run(["git","-C",str(repo),"-c","user.name=test","-c","user.email=test@example.invalid","commit","-qm","one"],check=True)
        revision=subprocess.check_output(["git","-C",str(repo),"rev-parse","HEAD"],text=True).strip()
        (repo/"wrapper.sh").write_text("two\n")
        with self.assertRaisesRegex(mod.Refusal,"source-working-tree-not-clean"):REAL_GIT_SOURCE_IDENTITY(repo,revision)

if __name__=="__main__": unittest.main()
