import hashlib,json,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
class SourceContract(unittest.TestCase):
 def test_closed_operations_and_go_offline_environment(self):
  p=json.loads((ROOT/'eng/language-route-bindings/policy.json').read_text())
  self.assertEqual(set(p['operations']),{'rust-tic-tac-toe-journey','go-snake-journey'})
  go=(ROOT/'examples/language-routes/go-snake/portable-verify.sh').read_text()
  for value in ('TMPDIR=/output/tmp','GOTOOLCHAIN=local','GOWORK=off','GOPROXY=off','GOSUMDB=off'): self.assertIn(value,go)
  self.assertEqual(p['operations']['go-snake-journey']['workingDirectory'],'examples/language-routes/go-snake')
  self.assertEqual(p['operations']['rust-tic-tac-toe-journey']['workingDirectory'],'examples/language-routes/rust-tic-tac-toe')
  self.assertEqual(p['operations']['go-snake-journey']['arguments'],['portable-verify.sh'])
 def test_verification_bytes_are_exact(self):
  p=json.loads((ROOT/'eng/language-route-bindings/policy.json').read_text())
  values={'rust-tic-tac-toe-journey':b'{"journey":"rust-tic-tac-toe","schema":"fsgg.language-route.rust-tic-tac-toe/1","toolchain":"1.98.1"}\n','go-snake-journey':b'{"journey":"go-snake","schema":"fsgg.language-route.go-snake/1","toolchain":"1.27.1"}\n'}
  for name,data in values.items(): self.assertEqual(hashlib.sha256(data).hexdigest(),p['operations'][name]['verificationSha256'])
 def test_executor_binding_uses_production_api(self):
  text=(ROOT/'eng/language-route-bindings/execute.fsx').read_text()
  for symbol in ('PortableWorkspacePodmanRunner','PortableWorkspaceExecutor.Executor','ExecuteAsync','RecoverAsync','inspectRunning','cancellation.Cancel()'): self.assertIn(symbol,text)
  self.assertNotIn('Process.Start',text)
  self.assertNotIn('UtcNow.AddSeconds',text)
  self.assertIn('portableNowFrom DateTimeOffset.UtcNow',text)
  self.assertIn('binding-source-tree-mismatch',text)
  support=(ROOT/'eng/language-route-bindings/BindingSupport.fsx').read_text()
  self.assertIn('binding-qualified-image-mismatch',support)
  self.assertIn('qualifiedImageReference trustedImage image',text)
  self.assertIn('retained.GetProperty("importReference")',support)
  self.assertNotIn('"localhost/fsgg-language-route@" + manifestDigest',text)
  self.assertIn('parseCommand commandBytes',text)
  for probe in ('wrong-toolchain','wrong-reference','changed-source'): self.assertIn(probe,text)
  for field in ('executionStarted','cleanupCompleted','cancellationRequested','terminationObserved','commandSha256'): self.assertIn(field,text)
 def test_qualified_image_mapping_distinguishes_build_and_retained_oci_identities(self):
  p=json.loads((ROOT/'eng/language-route-bindings/policy.json').read_text())
  for kind in ('rust','go'):
   image=p['qualifiedImages'][kind]
   self.assertRegex(image['archiveSha256'],r'^[0-9a-f]{64}$')
   self.assertRegex(image['configDigest'],r'^sha256:[0-9a-f]{64}$')
   self.assertRegex(image['retainedOciManifestDigest'],r'^sha256:[0-9a-f]{64}$')
   self.assertRegex(image['qualifiedBuildDigest'],r'^sha256:[0-9a-f]{64}$')
   self.assertNotEqual(image['retainedOciManifestDigest'],image['qualifiedBuildDigest'])
   self.assertEqual(image['qualifiedReference'],'localhost/fsgg-language-route@'+image['qualifiedBuildDigest'])
   retained=image['retainedImport']
   self.assertNotIn('@',retained['importName'])
   self.assertEqual(retained['importReference'],retained['importName']+'@'+image['retainedOciManifestDigest'])
   self.assertEqual(retained['original']['archiveSha256'],image['archiveSha256'])
   self.assertEqual(retained['original']['manifestDigest'],image['retainedOciManifestDigest'])
   self.assertEqual(retained['derived']['manifestDigest'],image['retainedOciManifestDigest'])
   self.assertEqual(retained['derived']['configDigest'],image['configDigest'])
   for stage in ('original','derived'):
    for field in ('archiveSha256','indexSha256','memberInventorySha256'):
     self.assertRegex(retained[stage][field],r'^[0-9a-f]{64}$')
 def test_derived_loader_has_no_arbitrary_command_surface(self):
  derive=(ROOT/'eng/language-route-bindings/derive-import.py').read_text()
  loader=(ROOT/'eng/language-route-bindings/load-derived.py').read_text()
  self.assertIn('changedMembers":["index.json"]',derive)
  self.assertIn('"load","--input"',loader)
  self.assertIn('"image","inspect",policy["importReference"]',loader)
  self.assertNotIn('shell=True',derive+loader)
 def test_hosted_workflow_is_exact_main_serial_and_receipt_driven(self):
  workflow=(ROOT/'.github/workflows/rust-go-hosted-bind-qualification.yml').read_text()
  validator=(ROOT/'eng/language-route-bindings/hosted-qualification.py').read_text()
  self.assertIn("inputs.expected_head == github.sha",workflow)
  self.assertEqual(workflow.count('runs-on:'),1)
  self.assertIn('refs/remotes/origin/main',validator)
  self.assertLess(workflow.index('hosted-qualification.py preflight'),workflow.index('qualified-artifact.zip'))
  self.assertLess(workflow.index('qualified-artifact.zip'),workflow.index('dotnet build'))
  self.assertIn('execution-command-refused',validator)
  self.assertIn('settled-reconstruction-refused',validator)
  self.assertIn('settled-receipt-mismatch',validator)
  self.assertIn('runningCancellationObservation',validator)
  self.assertIn('cancellation-or-termination-unknown',validator)
  self.assertIn('"accepted":cancellation_proven',validator)
if __name__=='__main__':unittest.main()
