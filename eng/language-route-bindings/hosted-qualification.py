#!/usr/bin/env python3
"""Preflight and validate the exact hosted Rust/Go P2 binding qualification."""
import argparse, hashlib, json, os, re, shutil, subprocess, sys
from datetime import datetime
from pathlib import Path

SCHEMA="fsgg.language-route.hosted-qualification/1"
HEAD_RE=re.compile(r"^[0-9a-f]{40}$")
SHA_RE=re.compile(r"^[0-9a-f]{64}$")
CONTAINER_RE=re.compile(r"^[0-9a-f]{64}$")
ARTIFACT={"id":11112465308,"run":36744671457,"sha":"d3ede2552d45357e505de41f34603adb458a815a20fc43dedae13f1650a56027"}
EXECUTOR_SHA="6395cdf3feb6ee114685920d9ba8b48b624df01bb1d38b922b12da0bffa89daf"
AKKA_SHA="1ef266d80a923b25db758987a15e4db99acaa05863a236871bac4dbd6315c5b7"

class Refusal(Exception): pass
def require(value,reason):
    if not value: raise Refusal(reason)
def run(argv,env=None):
    result=subprocess.run(argv,stdout=subprocess.PIPE,stderr=subprocess.PIPE,check=False,env=env)
    require(result.returncode==0,"command-refused:"+Path(argv[0]).name+":"+result.stderr.decode(errors="replace")[:512])
    return result.stdout.decode().strip()
def read(path): return json.loads(Path(path).read_bytes())
def sha(path):
    digest=hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda:stream.read(1024*1024),b""): digest.update(block)
    return digest.hexdigest()
def canonical(value): return (json.dumps(value,sort_keys=True,separators=(",",":"))+"\n").encode()
def write_new(path,value):
    target=Path(path); target.parent.mkdir(parents=True,exist_ok=True)
    with target.open("xb") as stream: stream.write(canonical(value)); stream.flush(); os.fsync(stream.fileno())
    os.chmod(target,0o600)

def policy(root): return read(Path(root)/"eng/language-route-bindings/policy.json")

def source_preflight(args):
    root=Path(args.source_root).resolve(); expected=args.expected_head
    require(HEAD_RE.fullmatch(expected),"expected-head-refused")
    require(run([args.git,"-C",str(root),"rev-parse","HEAD"])==expected,"exact-head-refused")
    require(run([args.git,"-C",str(root),"rev-parse","refs/remotes/origin/main"])==expected,"protected-main-head-refused")
    require(run([args.git,"-C",str(root),"status","--porcelain","--untracked-files=all"])=="","source-not-clean")
    require(not any(root.rglob("*.pyc")) and not any(root.rglob("__pycache__")),"python-bytecode-refused")
    p=policy(root); candidate=p["templatesCandidate"]; executor=p["executor"]
    require(candidate["artifactId"]==ARTIFACT["id"] and candidate["qualificationRunId"]==ARTIFACT["run"],"artifact-policy-refused")
    require(candidate["artifactDigest"]=="sha256:"+ARTIFACT["sha"],"artifact-digest-policy-refused")
    require(executor["sourceRevision"]=="c069263c3e9e8780b1596eee82d2f6c017daa8df" and executor["assemblySha256"]==EXECUTOR_SHA,"executor-policy-refused")
    require(executor["compileDependency"]=={"name":"Akka.dll","sha256":AKKA_SHA,"version":"1.5.71"},"akka-policy-refused")
    for op in p["operations"].values():
        wrapper=root/op["workingDirectory"]/op["arguments"][0]
        require(wrapper.is_file() and sha(wrapper)==op["wrapperSha256"],"wrapper-hash-refused")
    store=Path(args.store_root).resolve(); runroot=Path(args.runroot).resolve()
    require(not store.exists() and not runroot.exists(),"preflight-store-not-fresh")
    try:
        info=run([args.podman,"--storage-driver=vfs","--root",str(store),"--runroot",str(runroot),"info","--format","{{.Host.Security.Rootless}}|{{.Store.GraphDriverName}}"])
    finally:
        shutil.rmtree(store,ignore_errors=True); shutil.rmtree(runroot,ignore_errors=True)
    require(not store.exists() and not runroot.exists(),"preflight-namespace-cleanup-unproved")
    require(info=="true|vfs","rootless-vfs-preflight-refused")
    return {"schema":"fsgg.language-route.hosted-preflight/1","expectedHead":expected,"rootless":True,"storageDriver":"vfs","artifact":ARTIFACT,"executorSha256":EXECUTOR_SHA,"akkaSha256":AKKA_SHA}

def metadata(args):
    value=read(args.input); workflow=value.get("workflow_run") or {}
    require(value.get("id")==ARTIFACT["id"] and workflow.get("id")==ARTIFACT["run"],"artifact-metadata-identity-refused")
    require(value.get("expired") is False,"artifact-expired-refused")
    digest=value.get("digest")
    require(digest in (None,"sha256:"+ARTIFACT["sha"]),"artifact-metadata-digest-refused")
    return {"schema":"fsgg.language-route.artifact-metadata/1","id":ARTIFACT["id"],"runId":ARTIFACT["run"],"expired":False,"expectedZipSha256":ARTIFACT["sha"]}

def cleanup(args):
    state=Path(args.state).resolve(); owned=[]
    require(state.is_dir() and str(state).startswith(str(Path(args.allowed_root).resolve())+os.sep),"cleanup-root-refused")
    for kind in ("preflight","rust","go"):
        store=state/(kind+"-store"); runroot=state/(kind+"-runroot")
        if store.exists() or runroot.exists():
            ids=run([args.podman,"--storage-driver=vfs","--root",str(store),"--runroot",str(runroot),"container","ps","--all","--quiet"]).splitlines()
            for container in ids: run([args.podman,"--storage-driver=vfs","--root",str(store),"--runroot",str(runroot),"container","rm","--force",container])
            require(run([args.podman,"--storage-driver=vfs","--root",str(store),"--runroot",str(runroot),"container","ps","--all","--quiet"])=="","container-cleanup-unproved")
        shutil.rmtree(store,ignore_errors=True); shutil.rmtree(runroot,ignore_errors=True)
        require(not store.exists() and not runroot.exists(),"namespace-cleanup-unproved")
        owned.append(kind)
    return {"schema":"fsgg.language-route.hosted-cleanup/1","containersAbsent":True,"namespacesRemoved":owned}

def validate(args):
    state=Path(args.state); p=policy(args.source_root); head=args.expected_head
    require(sha(state/"qualified-artifact.zip")==ARTIFACT["sha"],"downloaded-artifact-bytes-refused")
    require(sha(args.executor)==EXECUTOR_SHA and sha(args.akka)==AKKA_SHA,"built-executor-bytes-refused")
    tree=run([args.git,"-C",args.source_root,"rev-parse",head+"^{tree}"])
    loads={}; executions={}
    def valid_sha(value): return isinstance(value,str) and SHA_RE.fullmatch(value) is not None
    def command(path):
        value=read(path)
        require(value.get("schema")=="fsgg.workspace.command/1","command-schema-refused")
        require(value.get("sourceRevision")==head,"command-source-refused")
        return value,sha(path)
    def receipt(record,kind,mode,command_value,command_sha,image,operation,verification_required):
        require(record.get("schema")=="fsgg.language-route.hosted-execution/1","execution-schema-refused")
        require(record.get("kind")==kind and record.get("mode")==mode,"execution-route-refused")
        require(record.get("commandId")==command_value.get("commandId") and record.get("commandSha256")==command_sha,"execution-command-refused")
        require(record.get("sourceRevision")==head and record.get("sourceTree")==tree,"execution-source-refused")
        require(record.get("qualifiedImage")==image,"execution-image-refused")
        require(record.get("verificationIdentity")==operation["verificationIdentity"] and record.get("verificationSha256")==operation["verificationSha256"],"execution-verification-policy-refused")
        require(valid_sha(record.get("snapshotSha256")) and valid_sha(record.get("runtimeIdentity")) and valid_sha(record.get("outputSha256")),"execution-hash-refused")
        require(CONTAINER_RE.fullmatch(record.get("containerIdentity") or "") is not None,"execution-container-identity-refused")
        if verification_required:
            require(record.get("verificationOutputSha256")==operation["verificationSha256"],"execution-verification-output-refused")
    signature_fields=("commandId","commandSha256","executionStarted","cleanupCompleted","cancellationRequested","terminationObserved","qualifiedImage","sourceRevision","sourceTree","snapshotSha256","runtimeIdentity","containerIdentity","verificationIdentity","verificationSha256","verificationOutputSha256","outputSha256","errorCode")
    def signature(record): return {field:record.get(field) for field in signature_fields}
    for kind in ("rust","go"):
        trusted=p["qualifiedImages"][kind]["retainedImport"]
        operation=p["operations"]["rust-tic-tac-toe-journey" if kind=="rust" else "go-snake-journey"]
        loaded=read(state/(kind+"-load.json"))
        require(loaded.get("schema")=="fsgg.language-route-derived-oci-load/1" and loaded.get("storeFresh") is True,"fresh-load-refused")
        require(loaded.get("reference")==trusted["importReference"] and loaded.get("manifestDigest")==trusted["derived"]["manifestDigest"] and loaded.get("configDigest")==trusted["derived"]["configDigest"],"loaded-image-identity-refused")
        command_value,command_sha=command(state/"commands"/(kind+".json"))
        records={name:read(state/"executions"/(kind+"-"+name+".json")) for name in ("first","duplicate","recovered")}
        receipt(records["first"],kind,"execute",command_value,command_sha,trusted["importReference"],operation,True)
        receipt(records["duplicate"],kind,"execute",command_value,command_sha,trusted["importReference"],operation,True)
        receipt(records["recovered"],kind,"recover",command_value,command_sha,trusted["importReference"],operation,True)
        require(records["first"].get("disposition")=="completed" and records["first"].get("executionStarted") is True,"journey-not-executed")
        require(records["first"].get("terminationObserved") is True and records["first"].get("cleanupCompleted") is True and records["first"].get("cancellationRequested") is False and records["first"].get("errorCode") is None,"journey-not-cleanly-completed")
        require(records["duplicate"].get("disposition")=="duplicate" and records["recovered"].get("disposition")=="duplicate","settled-reconstruction-refused")
        require(signature(records["first"])==signature(records["duplicate"])==signature(records["recovered"]),"settled-receipt-mismatch")
        loads[kind]={"receiptSha256":sha(state/(kind+"-load.json")),"reference":loaded["reference"],"manifestDigest":loaded["manifestDigest"],"configDigest":loaded["configDigest"]}
        executions[kind]={"commandSha256":command_sha,"first":records["first"],"duplicate":records["duplicate"],"recovered":records["recovered"]}
    cancel_command,cancel_sha=command(state/"commands/cancellation.json")
    cancel=read(state/"executions/cancellation-first.json"); cancel_recovery=read(state/"executions/cancellation-recovered.json")
    cancel_operation=p["operations"]["rust-tic-tac-toe-journey"]
    cancel_image=p["qualifiedImages"]["rust"]["retainedImport"]["importReference"]
    receipt(cancel,"rust","execute",cancel_command,cancel_sha,cancel_image,cancel_operation,False)
    receipt(cancel_recovery,"rust","recover",cancel_command,cancel_sha,cancel_image,cancel_operation,False)
    observation=cancel.get("runningCancellationObservation") or {}
    try:
        observed_at=datetime.fromisoformat(observation.get("observedAt","")); requested_at=datetime.fromisoformat(observation.get("requestedAt",""))
        ordered=observed_at <= requested_at
    except (TypeError,ValueError): ordered=False
    running_observed=(observation.get("schema")=="fsgg.language-route.running-cancellation/1" and observation.get("commandSha256")==cancel_sha and observation.get("state")=="running" and observation.get("observationOrdinal")==1 and observation.get("requestOrdinal")==2 and ordered and observation.get("containerIdentity")==cancel.get("containerIdentity") and observation.get("containerName")=="fsgg-portable-"+(observation.get("bindingDigest") or "")[:24] and valid_sha(observation.get("bindingDigest")))
    cancellation_proven=(running_observed and cancel.get("cancellationCleanupRecovery") is True and cancel.get("disposition")=="completed" and cancel.get("executionStarted") is True and cancel.get("cancellationRequested") is True and cancel.get("terminationObserved") is True and cancel.get("cleanupCompleted") is True and cancel.get("errorCode")=="execution-cancelled" and cancel_recovery.get("disposition")=="duplicate" and signature(cancel)==signature(cancel_recovery))
    refusals={}
    for probe in ("wrong-toolchain","wrong-reference","changed-source"):
        expected={"wrong-toolchain":"portable-executor-toolchain-refused","wrong-reference":"portable-executor-image-binding-refused","changed-source":"portable-executor-source-binding-refused"}[probe]
        value=read(state/"refusals"/(probe+".json")); require(value.get("schema")=="fsgg.language-route.hosted-execution/1" and value.get("kind")=="rust" and value.get("mode")=="execute" and value.get("disposition")=="refused" and value.get("refusalProbe")==probe and value.get("commandSha256")==sha(state/"commands/rust.json") and value.get("reason")==expected,"refusal-probe-failed:"+probe); refusals[probe]=value["reason"]
    clean=read(state/"cleanup.json"); require(clean.get("containersAbsent") is True and clean.get("namespacesRemoved")==["preflight","rust","go"],"cleanup-evidence-refused")
    result={"schema":SCHEMA,"source":{"revision":head,"tree":tree},"artifact":{"id":ARTIFACT["id"],"runId":ARTIFACT["run"],"zipSha256":ARTIFACT["sha"]},"executor":{"sourceRevision":p["executor"]["sourceRevision"],"assemblySha256":EXECUTOR_SHA,"akkaSha256":AKKA_SHA},"loads":loads,"executions":executions,"cancellation":{"status":"proven" if cancellation_proven else "unknown","commandSha256":cancel_sha,"first":cancel,"recovered":cancel_recovery},"refusals":refusals,"cleanup":clean,"accepted":cancellation_proven}
    write_new(args.output,result)
    require(cancellation_proven,"cancellation-or-termination-unknown")
    return {"accepted":True,"evidence":str(Path(args.output).resolve()),"evidenceSha256":sha(args.output)}

def main():
    parser=argparse.ArgumentParser(); sub=parser.add_subparsers(dest="command",required=True)
    p=sub.add_parser("preflight"); p.add_argument("--source-root",required=True);p.add_argument("--expected-head",required=True);p.add_argument("--store-root",required=True);p.add_argument("--runroot",required=True);p.add_argument("--podman",default="/usr/bin/podman");p.add_argument("--git",default="/usr/bin/git");p.set_defaults(call=source_preflight)
    p=sub.add_parser("metadata");p.add_argument("--input",required=True);p.set_defaults(call=metadata)
    p=sub.add_parser("cleanup");p.add_argument("--state",required=True);p.add_argument("--allowed-root",required=True);p.add_argument("--podman",default="/usr/bin/podman");p.set_defaults(call=cleanup)
    p=sub.add_parser("validate");p.add_argument("--state",required=True);p.add_argument("--source-root",required=True);p.add_argument("--expected-head",required=True);p.add_argument("--executor",required=True);p.add_argument("--akka",required=True);p.add_argument("--output",required=True);p.add_argument("--git",default="/usr/bin/git");p.set_defaults(call=validate)
    try:
        args=parser.parse_args(); print(canonical(args.call(args)).decode(),end=""); return 0
    except (Refusal,OSError,ValueError,json.JSONDecodeError) as error:
        print(canonical({"accepted":False,"reason":str(error)}).decode(),end=""); return 2
if __name__=="__main__": raise SystemExit(main())
