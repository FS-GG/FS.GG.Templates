#!/usr/bin/env python3
"""Offline package/preflight controls; fake dotnet stops before any generated workload."""
from pathlib import Path
import hashlib
import importlib.util
import json
import os
import shutil
import subprocess
import tempfile
import unittest
from unittest.mock import patch
from zipfile import ZipFile

ROOT = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('package_input', ROOT/'external-reference-template-package.py')
module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
SHA = '9b73395658d4683a067d150ca9441b04e802c4af'


def package(path, version='0.18.3', identity=module.PACKAGE_ID, repository='https://github.com/FS-GG/FS.GG.Templates', extra=None):
    nuspec=f'<package><metadata><id>{identity}</id><version>{version}</version><repository url="{repository}" commit="{SHA}"/><packageTypes><packageType name="Template"/></packageTypes></metadata></package>'
    with ZipFile(path, 'w') as archive:
        archive.writestr('template.nuspec', nuspec)
        archive.writestr('content/templates/fs-gg-fable-game/.template.config/template.json', json.dumps({'identity':'FS.GG.Workspace.Template.FableGame','groupIdentity':'FS.GG.Workspace.Template.FableGame','shortName':'fs-gg-fable-game'}))
        if extra: archive.writestr(extra, 'unexpected')
    return hashlib.sha256(path.read_bytes()).hexdigest()


class PackageControls(unittest.TestCase):
    def test_closed_identity_and_truthful_scope(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'input.nupkg'; sha=package(path); result=module.inspect_package(path,sha)
            self.assertEqual(result['producerRevision'], SHA)
            self.assertEqual(result['version'],'0.18.3')
            self.assertEqual(result['feedQualification'],'not-established')
            self.assertIs(result['installedAcceptance'],False)

    def test_bad_identity_and_archive_blocked(self):
        for values in [{'version':'0.18.2'}, {'identity':'FS.GG.Other'}, {'repository':'https://wrong.example/repo'},
                       {'extra':'../escaped'}, {'extra':'/absolute'}, {'extra':'content//alias'}]:
            with self.subTest(values=values), tempfile.TemporaryDirectory() as tmp:
                path=Path(tmp)/'input.nupkg'; sha=package(path,**values)
                with self.assertRaises(ValueError): module.inspect_package(path,sha)

    def test_hash_and_link_blocked(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'input.nupkg'; sha=package(path)
            for bad in ['0'*64,sha.upper(),'']:
                with self.subTest(bad=bad),self.assertRaises(ValueError):module.inspect_package(path,bad)
            link=Path(tmp)/'link.nupkg';link.symlink_to(path)
            with self.assertRaises(ValueError):module.inspect_package(link,sha)

    def test_generated_closure_without_producer_source(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);(root/'A').mkdir();(root/'B').mkdir();(root/'B/B.fsproj').write_text('<Project/>')
            project=root/'A/A.fsproj'; project.write_text('<Project><ItemGroup><ProjectReference Include="../B/B.fsproj"/><Compile Include="Main.fs"/></ItemGroup></Project>')
            (root/'A/Main.fs').write_text('module Main')
            result=module.validate_generated(root)
            self.assertIs(result['producerSourceReferenced'],False)
            for bad in ['../../producer.fs','$(ProducerRoot)/source.fs']:
                project.write_text(f'<Project><ItemGroup><Compile Include="{bad}"/></ItemGroup></Project>')
                with self.subTest(bad=bad),self.assertRaises(ValueError):module.validate_generated(root)
            project.write_text('<Project><ItemGroup><ProjectReference Include="../../producer.fsproj"/></ItemGroup></Project>')
            with self.assertRaises(ValueError):module.validate_generated(root)
            project.write_text('<Project/>')
            for name in ['Directory.Build.props', 'Generated.targets']:
                imported = root / name
                imported.write_text('<Project><Import Project="../producer/Shared.targets"/></Project>')
                with self.subTest(build_input=name), self.assertRaises(ValueError):module.validate_generated(root)
                imported.unlink()
            namespace='http://schemas.microsoft.com/developer/msbuild/2003'
            for element in ['<Import Project="../../producer/Shared.targets"/>',
                            '<ItemGroup><ProjectReference Include="../../producer.fsproj"/></ItemGroup>',
                            '<ItemGroup><Compile Include="../../producer.fs"/></ItemGroup>']:
                project.write_text(f'<Project xmlns="{namespace}">{element}</Project>')
                with self.subTest(namespace_element=element),self.assertRaises(ValueError):module.validate_generated(root)
            project.write_text(f'<Project xmlns="{namespace}"><ItemGroup><ProjectReference Include="../B/B.fsproj"/></ItemGroup></Project>')
            self.assertFalse(module.validate_generated(root)['producerSourceReferenced'])
            project.write_text('<Project xmlns="urn:unsupported-build"><Import Project="../../producer.targets"/></Project>')
            with self.assertRaises(ValueError):module.validate_generated(root)

    def test_rendering_hash_correspondence_and_refusals(self):
        with tempfile.TemporaryDirectory() as tmp:
            feed=Path(tmp)
            files={name:('fixture '+name).encode() for name in module.RENDERING_FABLE_ENTRIES}
            pins={}
            for identity in module.RENDERING_ARCHIVES:
                archive=feed/(identity+'.0.32.2.nupkg')
                with ZipFile(archive,'w') as z:
                    if identity.endswith('SvgBrowser'):
                        for name,raw in files.items():z.writestr(name,raw)
                    else:z.writestr('fixture.txt','not original native bytes')
                pins[identity]=hashlib.sha256(archive.read_bytes()).hexdigest()
            entries={name:hashlib.sha256(raw).hexdigest()for name,raw in files.items()}
            with patch.object(module,'RENDERING_ARCHIVES',pins),patch.object(module,'RENDERING_FABLE_ENTRIES',entries):
                sizes=[];real_open=Path.open
                class BoundedReader:
                    def __init__(self,stream):self.stream=stream
                    def __enter__(self):self.stream.__enter__();return self
                    def __exit__(self,*args):return self.stream.__exit__(*args)
                    def read(self,size=-1):sizes.append(size);return self.stream.read(size)
                with patch.object(Path,'open',lambda path,*args,**kwargs:BoundedReader(real_open(path,*args,**kwargs))):
                    value=module.verify_rendering_feed(feed,'0.32.2',SHA)
                self.assertEqual(sizes,[64*1024**2+1]*3)
                self.assertIs(value['installedAcceptance'],False)
                self.assertEqual(value['feedQualification'],'not-established')
                self.assertIsNone(value['producerTree'])
                for version,source in [('0.32.1',SHA),('0.32.2','0'*40)]:
                    with self.subTest(version=version,source=source),self.assertRaises(ValueError):
                        module.verify_rendering_feed(feed,version,source)
                with patch.object(module,'RENDERING_FABLE_ENTRIES',{**entries,next(iter(entries)):'0'*64}):
                    with self.assertRaises(ValueError):module.verify_rendering_feed(feed,'0.32.2',SHA)
                path=feed/'FS.GG.UI.KeyboardInput.0.32.2.nupkg';path.write_bytes(path.read_bytes()+b'changed')
                with self.assertRaises(ValueError):module.verify_rendering_feed(feed,'0.32.2',SHA)

    def test_existing_runner_external_branch_has_no_producer_source(self):
        with tempfile.TemporaryDirectory() as tmp:
            base=Path(tmp);controller=base/'controller/tests/composition/fable-game';controller.mkdir(parents=True)
            for name in ['verify-external-reference-candidate.sh','external-reference-template-package.py']:
                shutil.copyfile(ROOT/name,controller/name)
            producer=base/'absent-rendering'
            feed=base/'feed';feed.mkdir();files=['SvgExternalSessionHost.fs','SvgExternalSessionHost.fsi','SvgInputHost.fs','SvgInputHost.fsi']
            for identity in ['FS.GG.UI.Scene','FS.GG.UI.KeyboardInput','FS.GG.UI.Scene.SvgBrowser']:
                with ZipFile(feed/(identity+'.0.32.2.nupkg'),'w') as archive:
                    if identity.endswith('SvgBrowser'):
                        for name in files:archive.writestr('fable/'+name,name)
                        archive.writestr('fable-compatibility/compatibility-profile.v1.json','{}')
                    else:archive.writestr('fixture.txt','not native evidence')
            # The actual shell route uses a private inert feed-pin seam, never production pins.
            fixture_archives={identity:hashlib.sha256((feed/(identity+'.0.32.2.nupkg')).read_bytes()).hexdigest()
                              for identity in module.RENDERING_ARCHIVES}
            fixture_entries={'fable/'+name:hashlib.sha256(name.encode()).hexdigest() for name in files}
            fixture_entries['fable-compatibility/compatibility-profile.v1.json']=hashlib.sha256(b'{}').hexdigest()
            copied=controller/'external-reference-template-package.py'
            copied.write_text(copied.read_text().replace(repr(module.RENDERING_ARCHIVES),repr(fixture_archives))
                              .replace(repr(module.RENDERING_FABLE_ENTRIES),repr(fixture_entries)))
            archive=base/'external.nupkg';sha=package(archive);tools=base/'tools';tools.mkdir();calls=base/'dotnet-calls.jsonl'
            (tools/'git').write_text('#!/usr/bin/env python3\nraise SystemExit("producer source read forbidden in external package fixture")\n')
            (tools/'dotnet').write_text('#!/usr/bin/env python3\nimport sys,os,json\nwith open(os.environ["CALLS"],"a")as f:f.write(json.dumps({"args":sys.argv[1:],"home":os.environ["DOTNET_CLI_HOME"],"cache":os.environ["NUGET_PACKAGES"]})+"\\n")\nassert sys.argv[1:3] in [["new","install"],["new","fs-gg-fable-game"]]\nsys.exit(0 if sys.argv[2]=="install" else 9)\n')
            for path in tools.iterdir():path.chmod(0o700)
            env={**os.environ,'PATH':str(tools)+os.pathsep+os.environ['PATH'],'CALLS':str(calls)}
            out=base/'qualification';argv=['bash',str(controller/'verify-external-reference-candidate.sh'),str(producer),str(feed),'0.32.2',str(out),SHA,'candidate',str(archive),sha]
            result=subprocess.run(argv,env=env,capture_output=True,text=True,timeout=10)
            self.assertEqual(result.returncode,9,result.stderr)
            rows=[json.loads(line)for line in calls.read_text().splitlines()];self.assertEqual(len(rows),2)
            self.assertIn('--debug:custom-hive',rows[0]['args']);self.assertIn(str(out/'template-hive'),rows[0]['args'])
            self.assertIn('--package',rows[1]['args']);self.assertEqual(rows[0]['home'],str(out/'home'));self.assertEqual(rows[0]['cache'],str(out/'packages'))
            self.assertFalse((base/'controller/FS.GG.Templates.csproj').exists());self.assertFalse((base/'controller/templates').exists())
            self.assertFalse(producer.exists())
            bad_out=base/'bad'
            bad=['bash',str(controller/'verify-external-reference-candidate.sh'),str(producer),str(feed),'0.32.2',str(bad_out),SHA,'candidate',str(archive),'0'*64]
            result=subprocess.run(bad,env=env,capture_output=True,text=True,timeout=10)
            self.assertNotEqual(result.returncode,0);self.assertEqual(len(calls.read_text().splitlines()),2)


if __name__=='__main__':unittest.main()
