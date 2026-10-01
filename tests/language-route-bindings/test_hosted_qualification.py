import copy,hashlib,importlib.util,json,tempfile,unittest
from pathlib import Path
from types import SimpleNamespace

ROOT=Path(__file__).resolve().parents[2]
SPEC=importlib.util.spec_from_file_location("hosted_qualification",ROOT/"eng/language-route-bindings/hosted-qualification.py")
HOSTED=importlib.util.module_from_spec(SPEC); SPEC.loader.exec_module(HOSTED)
def digest(value): return hashlib.sha256(value).hexdigest()

class HostedQualificationTests(unittest.TestCase):
 def test_metadata_binds_live_exact_public_artifact_and_run(self):
  with tempfile.TemporaryDirectory() as folder:
   path=Path(folder)/"artifact.json"
   baseline={"id":11112465308,"expired":False,"digest":"sha256:"+HOSTED.ARTIFACT["sha"],"workflow_run":{"id":36744671457}}
   path.write_text(json.dumps(baseline));self.assertEqual(HOSTED.metadata(SimpleNamespace(input=str(path)))["expectedZipSha256"],HOSTED.ARTIFACT["sha"])
   for change,reason in (({"expired":True},"artifact-expired-refused"),({"id":1},"artifact-metadata-identity-refused"),({"digest":"sha256:"+"0"*64},"artifact-metadata-digest-refused")):
    value=copy.deepcopy(baseline);value.update(change);path.write_text(json.dumps(value))
    with self.assertRaisesRegex(HOSTED.Refusal,reason): HOSTED.metadata(SimpleNamespace(input=str(path)))

 def test_cleanup_refuses_unowned_namespace(self):
  with tempfile.TemporaryDirectory() as allowed,tempfile.TemporaryDirectory() as outside:
   with self.assertRaisesRegex(HOSTED.Refusal,"cleanup-root-refused"): HOSTED.cleanup(SimpleNamespace(state=outside,allowed_root=allowed,podman="podman"))

 def test_failed_preflight_removes_its_namespaces(self):
  with tempfile.TemporaryDirectory() as folder:
   store=Path(folder)/"preflight-store";runroot=Path(folder)/"preflight-runroot";original=HOSTED.run
   def failing(argv,env=None):
    if "info" in argv: store.mkdir();runroot.mkdir();raise HOSTED.Refusal("podman-failed")
    if "status" in argv: return ""
    if "rev-parse" in argv: return "f"*40
    return ""
   HOSTED.run=failing
   try:
    args=SimpleNamespace(source_root=str(ROOT),expected_head="f"*40,git="git",podman="podman",store_root=str(store),runroot=str(runroot))
    with self.assertRaisesRegex(HOSTED.Refusal,"podman-failed"): HOSTED.source_preflight(args)
    self.assertFalse(store.exists());self.assertFalse(runroot.exists())
   finally: HOSTED.run=original

 def qualification_fixture(self,mutate=None):
  temporary=tempfile.TemporaryDirectory();self.addCleanup(temporary.cleanup)
  state=Path(temporary.name);(state/"commands").mkdir();(state/"executions").mkdir();(state/"refusals").mkdir()
  head="e"*40;tree="d"*40;policy=json.loads((ROOT/"eng/language-route-bindings/policy.json").read_text())
  artifact=b"artifact";executor=b"executor";akka=b"akka"
  (state/"qualified-artifact.zip").write_bytes(artifact);(state/"executor.dll").write_bytes(executor);(state/"Akka.dll").write_bytes(akka)
  old=(HOSTED.ARTIFACT["sha"],HOSTED.EXECUTOR_SHA,HOSTED.AKKA_SHA,HOSTED.run)
  HOSTED.ARTIFACT["sha"]=digest(artifact);HOSTED.EXECUTOR_SHA=digest(executor);HOSTED.AKKA_SHA=digest(akka);HOSTED.run=lambda argv,env=None:tree
  self.addCleanup(lambda:(HOSTED.ARTIFACT.__setitem__("sha",old[0]),setattr(HOSTED,"EXECUTOR_SHA",old[1]),setattr(HOSTED,"AKKA_SHA",old[2]),setattr(HOSTED,"run",old[3])))
  commands={}
  for kind,command_id in (("rust","10000000-0000-0000-0000-000000000001"),("go","20000000-0000-0000-0000-000000000001"),("cancellation","30000000-0000-0000-0000-000000000001")):
   command={"schema":"fsgg.workspace.command/1","commandId":command_id,"sourceRevision":head};path=state/"commands"/(kind+".json")
   path.write_text(json.dumps(command,separators=(",",":")));commands[kind]=(command,digest(path.read_bytes()))
  def receipt(kind,mode,command,image,operation,error=None,cancelled=False):
   return {"schema":"fsgg.language-route.hosted-execution/1","kind":kind,"mode":mode,"commandId":command[0]["commandId"],"commandSha256":command[1],"refusalProbe":None,"disposition":"completed","executionStarted":True,"cleanupCompleted":True,"cancellationRequested":cancelled,"terminationObserved":True,"qualifiedImage":image,"sourceRevision":head,"sourceTree":tree,"snapshotSha256":"1"*64,"runtimeIdentity":"2"*64,"containerIdentity":"3"*64,"verificationIdentity":operation["verificationIdentity"],"verificationSha256":operation["verificationSha256"],"verificationOutputSha256":None if cancelled else operation["verificationSha256"],"outputSha256":"4"*64,"errorCode":error,"runningCancellationObservation":None}
  for kind in ("rust","go"):
   trusted=policy["qualifiedImages"][kind]["retainedImport"];operation=policy["operations"]["rust-tic-tac-toe-journey" if kind=="rust" else "go-snake-journey"]
   load={"schema":"fsgg.language-route-derived-oci-load/1","storeFresh":True,"reference":trusted["importReference"],"manifestDigest":trusted["derived"]["manifestDigest"],"configDigest":trusted["derived"]["configDigest"]}
   (state/(kind+"-load.json")).write_text(json.dumps(load));first=receipt(kind,"execute",commands[kind],trusted["importReference"],operation)
   for name,mode,disposition in (("first","execute","completed"),("duplicate","execute","duplicate"),("recovered","recover","duplicate")):
    value=copy.deepcopy(first);value["mode"]=mode;value["disposition"]=disposition;(state/"executions"/(kind+"-"+name+".json")).write_text(json.dumps(value))
  operation=policy["operations"]["rust-tic-tac-toe-journey"];image=policy["qualifiedImages"]["rust"]["retainedImport"]["importReference"]
  cancel=receipt("rust","execute",commands["cancellation"],image,operation,"execution-cancelled",True);cancel["cancellationCleanupRecovery"]=True
  cancel["runningCancellationObservation"]={"schema":"fsgg.language-route.running-cancellation/1","commandSha256":commands["cancellation"][1],"bindingDigest":"5"*64,"containerName":"fsgg-portable-"+"5"*24,"containerIdentity":"3"*64,"state":"running","observedAt":"2026-10-01T00:00:00+00:00","requestedAt":"2026-10-01T00:00:00.001000+00:00","observationOrdinal":1,"requestOrdinal":2}
  recovered=copy.deepcopy(cancel);recovered["mode"]="recover";recovered["disposition"]="duplicate";recovered["runningCancellationObservation"]=None
  (state/"executions/cancellation-first.json").write_text(json.dumps(cancel));(state/"executions/cancellation-recovered.json").write_text(json.dumps(recovered))
  reasons={"wrong-toolchain":"portable-executor-toolchain-refused","wrong-reference":"portable-executor-image-binding-refused","changed-source":"portable-executor-source-binding-refused"}
  for probe,reason in reasons.items():
   value={"schema":"fsgg.language-route.hosted-execution/1","kind":"rust","mode":"execute","disposition":"refused","refusalProbe":probe,"commandSha256":commands["rust"][1],"reason":reason};(state/"refusals"/(probe+".json")).write_text(json.dumps(value))
  (state/"cleanup.json").write_text(json.dumps({"containersAbsent":True,"namespacesRemoved":["preflight","rust","go"]}))
  if mutate: mutate(state)
  return SimpleNamespace(state=str(state),source_root=str(ROOT),expected_head=head,executor=str(state/"executor.dll"),akka=str(state/"Akka.dll"),output=str(state/"qualification.json"),git="git")

 def test_validate_accepts_exact_joined_receipts(self): self.assertTrue(HOSTED.validate(self.qualification_fixture())["accepted"])

 def test_validate_refuses_unbound_or_inferred_evidence(self):
  cases=(("executions/rust-first.json","schema","wrong","execution-schema-refused"),("executions/rust-first.json","kind","go","execution-route-refused"),("executions/go-recovered.json","mode","execute","execution-route-refused"),("executions/rust-first.json","commandId","00000000-0000-0000-0000-000000000000","execution-command-refused"),("executions/rust-first.json","sourceRevision","0"*40,"execution-source-refused"),("executions/rust-first.json","sourceTree","0"*40,"execution-source-refused"),("executions/rust-first.json","qualifiedImage","wrong","execution-image-refused"),("executions/rust-first.json","verificationIdentity","wrong","execution-verification-policy-refused"),("executions/rust-first.json","verificationSha256","0"*64,"execution-verification-policy-refused"),("executions/rust-first.json","verificationOutputSha256","0"*64,"execution-verification-output-refused"),("executions/rust-first.json","containerIdentity",None,"execution-container-identity-refused"),("executions/cancellation-recovered.json","containerIdentity","6"*64,"cancellation-or-termination-unknown"),("executions/cancellation-first.json","runningCancellationObservation",None,"cancellation-or-termination-unknown"),("refusals/wrong-toolchain.json","reason","something-else","refusal-probe-failed:wrong-toolchain"))
  for path,key,value,reason in cases:
   def mutate(state,path=path,key=key,value=value):
    target=state/path;record=json.loads(target.read_text());record[key]=value;target.write_text(json.dumps(record))
   with self.subTest(path=path,key=key),self.assertRaisesRegex(HOSTED.Refusal,reason): HOSTED.validate(self.qualification_fixture(mutate))

if __name__=="__main__": unittest.main()
