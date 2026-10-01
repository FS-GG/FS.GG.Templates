#!/usr/bin/env python3
"""Load one policy-bound derived archive into a fresh scoped Podman store."""
import argparse, json, os, subprocess
from pathlib import Path
import importlib.util

HERE=Path(__file__).resolve().parent
SPEC=importlib.util.spec_from_file_location("derived_import",HERE/"derive-import.py")
DERIVE=importlib.util.module_from_spec(SPEC); SPEC.loader.exec_module(DERIVE)
POLICY=DERIVE.POLICY
Refusal=DERIVE.Refusal

def require(value, reason):
    if not value: raise Refusal(reason)

def load_argv(podman, store, runroot, archive):
    return [str(podman),"--storage-driver=vfs","--root",str(store),"--runroot",str(runroot),"load","--input",str(archive)]

def podman_argv(podman, store, runroot, *arguments):
    return [str(podman),"--storage-driver=vfs","--root",str(store),"--runroot",str(runroot),*arguments]

def canonical_config_digest(value):
    require(isinstance(value,str),"loaded-config-identity-invalid")
    if len(value)==64 and set(value)<=DERIVE.HEX: value="sha256:"+value
    require(len(value)==71 and value.startswith("sha256:") and set(value[7:])<=DERIVE.HEX,"loaded-config-identity-invalid")
    return value

def run(argv, maximum=1024*1024):
    result=subprocess.run(argv,stdout=subprocess.PIPE,stderr=subprocess.PIPE,check=False,env={"HOME":"/tmp","PATH":"/usr/local/bin:/usr/bin:/bin","LANG":"C.UTF-8"})
    require(len(result.stdout)+len(result.stderr)<=maximum,"podman-output-limit-refused")
    require(result.returncode==0,"podman-command-refused")
    return result.stdout

def load(args):
    source=Path(args.source_root).resolve(); tree=DERIVE.exact_source(source,args.source_revision)
    kind=args.kind; require(kind in ("rust","go"),"kind-refused")
    archive=Path(args.archive).resolve(); receipt_path=Path(args.receipt).resolve(); output=Path(args.output).resolve()
    store=Path(args.store_root).resolve(); runroot=Path(args.runroot).resolve(); podman=Path(args.podman).resolve()
    require(podman.is_file() and os.access(podman,os.X_OK),"podman-refused")
    require(not store.exists() and not runroot.exists(),"podman-store-not-fresh")
    require(not output.exists(),"output-already-exists")
    receipt=DERIVE.read_json(receipt_path.read_bytes(),"derived-import-receipt")
    require(receipt.get("schema")=="fsgg.language-route-derived-oci-import/1" and not receipt.get("acceptedNativeImport") and not receipt.get("acceptedNativeExecution"),"derived-import-receipt-refused")
    source_receipt=receipt.get("source",{})
    require(source_receipt.get("revision")==args.source_revision and source_receipt.get("tree")==tree and source_receipt.get("policySha256")==DERIVE.sha_file(DERIVE.POLICY_PATH),"derived-import-source-refused")
    policy=POLICY["qualifiedImages"][kind]["retainedImport"]
    identity=DERIVE.archive_identity(archive,kind,policy["derived"],policy["importName"])
    recorded=receipt.get("images",{}).get(kind,{}).get("derived",{})
    for field in ("archiveSha256","indexSha256","annotation","manifestDigest","configDigest","layerDigests","memberInventorySha256","memberCount"):
        require(recorded.get(field)==identity[field],kind+"-derived-receipt-mismatch")
    require(recorded.get("reference")==policy["importReference"],kind+"-derived-reference-mismatch")
    run(load_argv(podman,store,runroot,archive))
    inspected=json.loads(run(podman_argv(podman,store,runroot,"image","inspect",policy["importReference"])))
    require(isinstance(inspected,list) and len(inspected)==1,"loaded-image-count-refused")
    image=inspected[0]
    config_digest=canonical_config_digest(image.get("Id"))
    require(config_digest==policy["derived"]["configDigest"],"loaded-config-identity-mismatch")
    require(image.get("Digest")==policy["derived"]["manifestDigest"],"loaded-manifest-identity-mismatch")
    result={"schema":"fsgg.language-route-derived-oci-load/1","acceptedNativeExecution":False,"kind":kind,"source":{"revision":args.source_revision,"tree":tree},"archiveSha256":identity["archiveSha256"],"reference":policy["importReference"],"manifestDigest":image["Digest"],"configDigest":config_digest,"inspectedConfigId":image["Id"],"storeFresh":True}
    output.parent.mkdir(parents=True,exist_ok=True)
    with output.open("xb") as stream: stream.write(DERIVE.canonical(result)); stream.flush(); os.fsync(stream.fileno())
    os.chmod(output,0o600)
    print(DERIVE.canonical({"loadReceipt":str(output),"loadReceiptSha256":DERIVE.sha_file(output),"nativeExecutionAccepted":False}).decode(),end="")

def main():
    parser=argparse.ArgumentParser(); parser.add_argument("--kind",required=True);parser.add_argument("--archive",required=True);parser.add_argument("--receipt",required=True)
    parser.add_argument("--source-root",required=True);parser.add_argument("--source-revision",required=True);parser.add_argument("--store-root",required=True);parser.add_argument("--runroot",required=True);parser.add_argument("--output",required=True);parser.add_argument("--podman",default="/usr/bin/podman")
    try: load(parser.parse_args()); return 0
    except (Refusal,OSError,json.JSONDecodeError) as error: print(json.dumps({"accepted":False,"reason":str(error)},sort_keys=True)); return 2
if __name__=="__main__": raise SystemExit(main())
