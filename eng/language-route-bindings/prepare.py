#!/usr/bin/env python3
import argparse, hashlib, json, os, tarfile, tempfile, zipfile
from pathlib import Path, PurePosixPath

HERE = Path(__file__).resolve().parent
POLICY = json.loads((HERE / "policy.json").read_text())
MAX_JSON = 1024 * 1024
HEX = set("0123456789abcdef")

class Refusal(RuntimeError): pass

def sha(path):
    h=hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda:f.read(1024*1024), b""): h.update(block)
    return h.hexdigest()

def canonical(value): return (json.dumps(value,sort_keys=True,separators=(",",":"))+"\n").encode()
def require(ok,msg):
    if not ok: raise Refusal(msg)
def safe_name(name):
    p=PurePosixPath(name)
    return name and not p.is_absolute() and ".." not in p.parts and "" not in p.parts

def read_json_bytes(data, label):
    require(len(data)<=MAX_JSON, label+"-too-large")
    try: return json.loads(data)
    except Exception as e: raise Refusal(label+"-invalid-json") from e

def verify_oci(path, kind):
    require(path.is_file(), kind+"-candidate-missing")
    with tarfile.open(path,"r:*") as tf:
        members={}
        for m in tf:
            require(safe_name(m.name), kind+"-candidate-path-refused")
            require(m.isfile() or m.isdir(), kind+"-candidate-member-type-refused")
            require(m.name not in members, kind+"-candidate-duplicate-member")
            members[m.name]=m
        def content(name):
            require(name in members and members[name].isfile(), kind+"-candidate-member-missing")
            f=tf.extractfile(members[name]); require(f is not None, kind+"-candidate-member-unreadable")
            return f.read(MAX_JSON+1)
        layout=read_json_bytes(content("oci-layout"), kind+"-oci-layout")
        require(layout=={"imageLayoutVersion":"1.0.0"}, kind+"-oci-layout-refused")
        index=read_json_bytes(content("index.json"), kind+"-oci-index")
        require(index.get("schemaVersion")==2 and len(index.get("manifests",[]))==1, kind+"-oci-index-refused")
        descriptor=index["manifests"][0]
        manifest_name="blobs/sha256/"+descriptor.get("digest","").removeprefix("sha256:")
        manifest_bytes=content(manifest_name)
        require(hashlib.sha256(manifest_bytes).hexdigest()==descriptor["digest"].removeprefix("sha256:"), kind+"-manifest-digest-mismatch")
        manifest=read_json_bytes(manifest_bytes,kind+"-manifest")
        config_desc=manifest.get("config",{})
        config_name="blobs/sha256/"+config_desc.get("digest","").removeprefix("sha256:")
        config_bytes=content(config_name)
        require(hashlib.sha256(config_bytes).hexdigest()==config_desc["digest"].removeprefix("sha256:"), kind+"-config-digest-mismatch")
        config=read_json_bytes(config_bytes,kind+"-config")
        cfg=config.get("config",{})
        require(cfg.get("User")=="32768:32768",kind+"-user-refused")
        require(cfg.get("Entrypoint") in (None,[]) and cfg.get("Cmd") in (None,[]),kind+"-default-command-refused")
        require(config.get("architecture")=="amd64" and config.get("os")=="linux",kind+"-platform-refused")
        for desc in manifest.get("layers",[]):
            digest=desc.get("digest","").removeprefix("sha256:")
            require(len(digest)==64 and set(digest)<=HEX,kind+"-layer-digest-refused")
            name="blobs/sha256/"+digest
            require(name in members and members[name].isfile(),kind+"-layer-missing")
            h=hashlib.sha256(); f=tf.extractfile(members[name]); require(f is not None,kind+"-layer-unreadable")
            for block in iter(lambda:f.read(1024*1024),b""): h.update(block)
            require(h.hexdigest()==digest,kind+"-layer-digest-mismatch")
        return "sha256:"+descriptor["digest"].removeprefix("sha256:"), "sha256:"+config_desc["digest"].removeprefix("sha256:")

def prepare(args):
    source=Path(args.source_root).resolve(); artifact=Path(args.artifact_zip).resolve(); assembly=Path(args.executor_assembly).resolve(); dependency=Path(args.executor_compile_dependency).resolve()
    out=Path(args.output).resolve(); require(not out.exists(),"output-already-exists")
    out.parent.mkdir(parents=True,exist_ok=True)
    staging=Path(tempfile.mkdtemp(prefix=".language-route-binding-",dir=out.parent)); os.chmod(staging,0o700)
    require(sha(artifact)==POLICY["templatesCandidate"]["artifactDigest"].removeprefix("sha256:"),"artifact-digest-mismatch")
    require(sha(assembly)==POLICY["executor"]["assemblySha256"],"executor-assembly-digest-mismatch")
    require(assembly.name==POLICY["executor"]["assembly"],"executor-assembly-name-refused")
    dep=POLICY["executor"]["compileDependency"]
    require(dependency.name==dep["name"] and sha(dependency)==dep["sha256"],"executor-dependency-digest-mismatch")
    with zipfile.ZipFile(artifact) as z:
        names=z.namelist(); require(len(names)==len(set(names)) and all(safe_name(n.rstrip("/")) for n in names if not n.endswith("/")),"artifact-member-refused")
        q=[n for n in names if n.endswith("/qualification.json") or n=="qualification.json"]
        require(len(q)==1,"qualification-manifest-count-refused")
        qualification=read_json_bytes(z.read(q[0]),"qualification")
        require(qualification.get("schema")=="fsgg.language-route-image-qualification/1","qualification-schema-refused")
        tc=POLICY["templatesCandidate"]
        require(qualification.get("sourceRevision")==tc["sourceRevision"] and qualification.get("sourceTree")==tc["sourceTree"],"qualification-source-mismatch")
        require(qualification.get("inputsSha256")==POLICY["imageInputsSha256"],"qualification-inputs-mismatch")
        images=qualification.get("images",{}); bound={}
        for kind in ("rust","go"):
            item=images.get(kind,{}); expected_recipe=POLICY["operations"]["rust-tic-tac-toe-journey" if kind=="rust" else "go-snake-journey"]["recipeSha256"]
            require(qualification.get("recipeSha256",{}).get(kind)==expected_recipe,"qualification-recipe-mismatch")
            candidate_name=Path(item.get("candidate","")).name
            matches=[n for n in names if Path(n).name==candidate_name]
            require(candidate_name==kind+"-candidate.oci.tar" and len(matches)==1,kind+"-candidate-count-refused")
            candidate=staging/(kind+"-candidate.oci.tar")
            with z.open(matches[0]) as src, candidate.open("xb") as dst:
                for block in iter(lambda:src.read(1024*1024),b""): dst.write(block)
            require(sha(candidate)==item.get("candidateSha256"),kind+"-candidate-sha-mismatch")
            manifest_digest,config_digest=verify_oci(candidate,kind)
            os.chmod(candidate,0o600)
            image_id=item.get("id","")
            require(image_id.startswith("sha256:") and len(image_id)==71,kind+"-image-id-refused")
            require(image_id==config_digest,kind+"-qualified-image-config-mismatch")
            bound[kind]={"archiveSha256":item["candidateSha256"],"configDigest":config_digest,"imageId":image_id,"manifestDigest":manifest_digest,"reference":item.get("reference")}
    wrappers={}
    for opid,op in POLICY["operations"].items():
        wrapper=source/op["arguments"][0]
        require(wrapper.is_file() and not wrapper.is_symlink(),opid+"-wrapper-missing")
        wrappers[opid]=sha(wrapper)
        require(wrappers[opid]==op["wrapperSha256"],opid+"-wrapper-digest-mismatch")
    result={"schema":"fsgg.language-route-portable-binding/1","acceptedNativeExecution":False,"artifact":POLICY["templatesCandidate"],"executor":POLICY["executor"],"images":bound,"operations":POLICY["operations"],"wrapperSha256":wrappers}
    target=staging/"binding.json"; target.write_bytes(canonical(result)); os.chmod(target,0o600)
    staging.rename(out); target=out/"binding.json"
    print(canonical({"binding":str(target),"bindingSha256":sha(target),"nativeExecutionAccepted":False}).decode(),end="")

def main():
    p=argparse.ArgumentParser(); p.add_argument("--artifact-zip",required=True); p.add_argument("--executor-assembly",required=True); p.add_argument("--executor-compile-dependency",required=True); p.add_argument("--source-root",required=True); p.add_argument("--output",required=True)
    try: prepare(p.parse_args()); return 0
    except (Refusal,OSError,zipfile.BadZipFile,tarfile.TarError) as e: print(json.dumps({"accepted":False,"reason":str(e)},sort_keys=True)); return 2
if __name__=="__main__": raise SystemExit(main())
