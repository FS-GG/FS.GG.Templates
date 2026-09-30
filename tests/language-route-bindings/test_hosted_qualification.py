import importlib.util,json,tempfile,unittest
from pathlib import Path
from types import SimpleNamespace

ROOT=Path(__file__).resolve().parents[2]
SPEC=importlib.util.spec_from_file_location("hosted_qualification",ROOT/"eng/language-route-bindings/hosted-qualification.py")
HOSTED=importlib.util.module_from_spec(SPEC); SPEC.loader.exec_module(HOSTED)

class HostedQualificationTests(unittest.TestCase):
 def test_metadata_binds_live_exact_public_artifact_and_run(self):
  with tempfile.TemporaryDirectory() as folder:
   path=Path(folder)/"artifact.json"
   path.write_text(json.dumps({"id":11112465308,"expired":False,"digest":"sha256:"+HOSTED.ARTIFACT["sha"],"workflow_run":{"id":36744671457}}))
   result=HOSTED.metadata(SimpleNamespace(input=str(path)))
   self.assertEqual(result["expectedZipSha256"],HOSTED.ARTIFACT["sha"])
   for change,reason in (({"expired":True},"artifact-expired-refused"),({"id":1},"artifact-metadata-identity-refused"),({"digest":"sha256:"+"0"*64},"artifact-metadata-digest-refused")):
    value=json.loads(path.read_text());value.update(change);path.write_text(json.dumps(value))
    with self.assertRaisesRegex(HOSTED.Refusal,reason): HOSTED.metadata(SimpleNamespace(input=str(path)))
    path.write_text(json.dumps({"id":11112465308,"expired":False,"digest":"sha256:"+HOSTED.ARTIFACT["sha"],"workflow_run":{"id":36744671457}}))
 def test_cleanup_refuses_unowned_namespace(self):
  with tempfile.TemporaryDirectory() as allowed,tempfile.TemporaryDirectory() as outside:
   with self.assertRaisesRegex(HOSTED.Refusal,"cleanup-root-refused"):
    HOSTED.cleanup(SimpleNamespace(state=outside,allowed_root=allowed,podman="/usr/bin/podman"))

if __name__=="__main__": unittest.main()
