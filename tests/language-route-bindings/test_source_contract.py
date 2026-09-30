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
  for symbol in ('PortableWorkspacePodmanRunner','PortableWorkspaceExecutor.Executor','ExecuteAsync','RecoverAsync','CancelAfter'): self.assertIn(symbol,text)
  self.assertNotIn('Process.Start',text)
  self.assertNotIn('UtcNow.AddSeconds',text)
  self.assertIn('portableNowFrom DateTimeOffset.UtcNow',text)
  self.assertIn('binding-source-tree-mismatch',text)
  support=(ROOT/'eng/language-route-bindings/BindingSupport.fsx').read_text()
  self.assertIn('binding-qualified-image-mismatch',support)
  self.assertIn('qualifiedImageReference trustedImage image',text)
  self.assertIn('trustedImage.GetProperty("qualifiedReference")',support)
  self.assertNotIn('"localhost/fsgg-language-route@" + manifestDigest',text)
  self.assertIn('parseCommand commandBytes',text)
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
if __name__=='__main__':unittest.main()
