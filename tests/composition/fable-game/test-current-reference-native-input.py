#!/usr/bin/env python3
"""Pure controls of the real helper/recorder; no IME or browser is launched."""
import ast
import copy
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

HERE = Path(__file__).parent
SPEC = importlib.util.spec_from_file_location('native_input_controls', HERE / 'current-reference-native-input.py')
N = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(N)


def fixture():
    """Explicit synthetic tuple; never a usable facility or native witness."""
    row = lambda path: dict(path='/usr/fixture/' + path, sha256='a'*64, package='fixture')
    return {'schema': N.SCHEMA, 'platform': 'ubuntu-24.04-x11',
            'packages': [dict(name='fixture', version='fixture', debSha256='b'*64,
                              sourceUri='https://fixture.invalid/source', sourceSha256='c'*64)],
            'objects': {role: row(role) for role in N.ROLES},
            'dataFiles': [{**row(kind), 'kind': kind} for kind in ['dictionary', 'xkb', 'schema', 'compose']],
            'keymaps': {'us': 'd'*64, 'de': 'e'*64}}


def v2_fixture():
    value=fixture();value['schema']=N.SCHEMA2;value['softwareContractSha256']='f'*64
    value['packages'].append({**value['packages'][0],'name':'xkb-data'})
    for role in N.V2_ROLES-N.ROLES:value['objects'][role]={'path':'/usr/fixture/'+role,'sha256':'a'*64,'package':'fixture'}
    for row in value['dataFiles']:
        if row['kind']=='schema':row['path']=N.TREE_PATHS['schemas']+'/fixture.gschema.xml'
        if row['kind']=='xkb':row['path']=N.TREE_PATHS['xkb']+'/rules/fixture';row['package']='xkb-data'
    value['dataClosures']={name:{'path':path,'sha256':'c'*64,'entries':2,'bytes':5} for name,path in N.TREE_PATHS.items()}
    value['derivedFiles']={'compiledSchemas':{'path':N.TREE_PATHS['schemas']+'/gschemas.compiled',
        'sha256':'b'*64,'compilerRole':'glibCompileSchemas','inputTreeSha256':'c'*64}}
    return value


def snapshot(value='', events=()):
    return {'documentHasFocus': True, 'nativeInput': {'count': 1, 'focused': True, 'id': 'fourd-reference-note',
        'label': 'Encounter note', 'tag': 'INPUT', 'value': value, 'commandOrder': '', 'agentFullCell': '0:0:0:0',
        'events': list(events)}}


def event(n, kind, data=None, key=None):
    return dict(sequence=n, type=kind, data=data, key=key, trusted=True, id='fourd-reference-note')


def report_fixture(digest='a'*64):
    preedit = [event(1,'compositionstart'),event(2,'compositionupdate','nihao')]
    first = snapshot('你好', [*preedit,event(3,'compositionend','你好'),event(4,'input','你好')])
    second_before = snapshot('你好',[{'sequence':4}])
    second_preedit = snapshot('你好nihao',[event(5,'compositionstart'),event(6,'compositionupdate','nihao')])
    second_after = snapshot('你好',[*second_preedit['nativeInput']['events'],event(7,'compositionend','')])
    keys=[*'nihao','space',*'nihao','Escape','dead_acute','e']
    return {'manifestSha256':digest, 'keys':keys,'keyRequests':[{'key':k,'returnedZero':True} for k in keys],'complete':True,'phases':{
        'commit':{'before':snapshot(),'preedit':snapshot('nihao',preedit),'after':first},
        'cancel':{'before':second_before,'preedit':second_preedit,'after':second_after},
        'deadkey':{'before':snapshot('你好',[{'sequence':7}]),'after':snapshot('你好é',[event(8,'keydown',key='Dead'),event(9,'input','é')])}}}


class NativeInputControls(unittest.TestCase):
    def test_v2_compiled_schema_is_a_derivation_not_a_package_owned_file(self):
        value=v2_fixture();N.manifest(value)
        self.assertNotIn('package',value['derivedFiles']['compiledSchemas'])
        for change in ['owner','compiler','input','path','tree','v1-mix']:
            bad=copy.deepcopy(value)
            if change=='owner':bad['derivedFiles']['compiledSchemas']['package']='fixture'
            elif change=='compiler':del bad['objects']['glibCompileSchemas']
            elif change=='input':bad['derivedFiles']['compiledSchemas']['inputTreeSha256']='d'*64
            elif change=='path':bad['derivedFiles']['compiledSchemas']['path']='/usr/local/ambient/gschemas.compiled'
            elif change=='tree':del bad['dataClosures']['schemas']
            else:bad['schema']=N.SCHEMA
            with self.assertRaises((RuntimeError,KeyError,TypeError)):N.manifest(bad)

    def test_v2_derived_bytes_and_both_complete_trees_are_required(self):
        import types,stat
        value=v2_fixture();body=b'owned source';compiled=b'actual derived bytes'
        for row in [*value['objects'].values(),*value['dataFiles']]:row['sha256']=N.sha(body)
        value['derivedFiles']['compiledSchemas']['sha256']=N.sha(compiled)
        def read(path):
            if path=='/etc/os-release':return b'ID=ubuntu\nVERSION_ID="24.04"\n'
            return compiled if path.endswith('/gschemas.compiled') else body
        inspect=lambda p:types.SimpleNamespace(st_mode=stat.S_IFREG|0o644,st_uid=0,st_size=len(compiled))
        calls=[]
        def tree(path,excluded):
            calls.append((path,excluded));return {'sha256':'c'*64,'entries':2,'bytes':5}
        N.verify_files(value,read,inspect,tree)
        self.assertIn((N.TREE_PATHS['schemas'],('gschemas.compiled',)),calls)
        self.assertEqual(2,len(calls))
        with self.assertRaisesRegex(RuntimeError,'complete input tree changed'):
            N.verify_files(value,read,inspect,lambda p,e:{'sha256':'d'*64,'entries':2,'bytes':5})
        with self.assertRaisesRegex(RuntimeError,'compiled schema changed'):
            N.verify_files(value,lambda p:b'changed' if p.endswith('/gschemas.compiled') else read(p),inspect,tree)

    def test_real_bounded_tree_identity_detects_input_drift_and_escaping_link(self):
        import os
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)/'tree';root.mkdir();leaf=root/'input';leaf.write_bytes(b'first');leaf.chmod(0o644)
            before=N.tree_identity(root,owner_uid=os.getuid());leaf.write_bytes(b'second')
            self.assertNotEqual(before['sha256'],N.tree_identity(root,owner_uid=os.getuid())['sha256'])
            (root/'gschemas.compiled').write_bytes(b'generated')
            excluded=N.tree_identity(root,('gschemas.compiled',),owner_uid=os.getuid())
            self.assertEqual(2,excluded['entries'])
            outside=Path(tmp)/'outside';outside.write_bytes(b'outside');(root/'escape').symlink_to(outside)
            with self.assertRaisesRegex(RuntimeError,'escapes'):
                N.tree_identity(root,owner_uid=os.getuid())

    def test_v2_settings_route_refuses_before_any_owned_service(self):
        with patch.object(N,'verify_files',return_value=True),patch.dict(os.environ,{'XDG_DATA_DIRS':'/ambient'}):
            forbidden=lambda *a:self.fail('service or query reached')
            with self.assertRaisesRegex(RuntimeError,'schema search route'):
                N.start(Path('/absent'),v2_fixture(),forbidden,forbidden,forbidden,forbidden,0,forbidden,forbidden,forbidden)

    def test_missing_and_unknown_manifest_never_become_defaults(self):
        N.manifest(fixture())
        for value in [{}, None, {**fixture(), 'platform': 'arch'}, {**fixture(), 'objects': {}},
                      {**fixture(), 'keymaps': {'de': 'e'*64}}, {**fixture(), 'dataFiles': []}]:
            with self.subTest(value=value):
                with self.assertRaises((RuntimeError, KeyError, TypeError)):
                    N.manifest(value)
        for raw in ['', 'x'*65537, '{}', '{"schema":1,"schema":2}']:
            with self.assertRaises(RuntimeError):
                N.read_manifest(raw)

    def test_each_pin_is_required(self):
        for family in ['objects', 'dataFiles', 'packages']:
            fields = ['sha256', 'package', 'path'] if family != 'packages' else ['version', 'sourceSha256', 'debSha256']
            for field in fields:
                value = fixture()
                row = next(iter(value[family].values())) if family == 'objects' else value[family][0]
                del row[field]
                with self.assertRaises((RuntimeError, KeyError, TypeError)):
                    N.manifest(value)

    def test_failing_file_pin_stops_before_any_service(self):
        with patch.object(N, 'verify_files', side_effect=RuntimeError('original file refusal')):
            forbidden = lambda *a: self.fail('service or command reached')
            with self.assertRaisesRegex(RuntimeError, 'original file refusal'):
                N.start(Path('/absent'), fixture(), forbidden, forbidden, forbidden, forbidden, 0, forbidden, forbidden, forbidden)

    def test_full_caller_refuses_missing_facility_before_acquisition_or_tools(self):
        spec=importlib.util.spec_from_file_location('native_caller_controls',HERE/'current-reference-at-caller.py')
        caller=importlib.util.module_from_spec(spec);spec.loader.exec_module(caller)
        self.assertIsNone(caller.observer.CURRENT_PUBLIC_AT_ADMISSION)
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);(root/'external-reference-preflight.json').write_text('{"requestedPhase":"full"}')
            with patch.object(caller.observer,'CURRENT_PUBLIC_AT_ADMISSION','inert-control-only'), \
                 patch.dict(N.os.environ,FSGG_CURRENT_PUBLIC_AT_ADMISSION='inert-control-only',FSGG_CURRENT_NATIVE_INPUT_FACILITY=''), \
                 patch.object(caller.subprocess,'check_output',side_effect=AssertionError('tool reached')), \
                 patch.object(caller.public,'acquire',side_effect=AssertionError('acquisition reached')):
                with self.assertRaisesRegex(RuntimeError,'facility input missing'):
                    caller.prepare(root,Path('/absent-owner'))
        self.assertIsNone(caller.observer.CURRENT_PUBLIC_AT_ADMISSION)

    def test_actual_client_mapping_requires_loaded_module_and_stable_birth(self):
        value=fixture();birth={'pid':42,'start':7}
        rows='\n'.join('address perms offset device inode '+value['objects'][k]['path'] for k in ['gtk3','ibusGtk3'])
        actual=N.file_mappings(42,value,['gtk3','ibusGtk3'],birth,lambda a,b:a==b,lambda _:birth,read=lambda _:rows)
        self.assertEqual(actual['mapsSha256'],N.sha(rows.encode()))
        for text,process in [(rows.replace('ibusGtk3','wrong'),birth),(rows,{'pid':42,'start':8})]:
            with self.assertRaises(RuntimeError):
                N.file_mappings(42,value,['gtk3','ibusGtk3'],birth,lambda a,b:a==b,lambda _:process,read=lambda _:text)

    def test_real_phase_predicates_and_surrogate_refusals(self):
        before = snapshot()
        preedit = [event(1, 'compositionstart'), event(2, 'compositionupdate', 'nihao')]
        commit = snapshot('你好', [*preedit, event(3, 'compositionend', '你好'), event(4, 'input', '你好')])
        cancel = snapshot('', [*preedit, event(3, 'compositionend', '')])
        dead = snapshot('é', [event(1, 'keydown', key='Dead'), event(2, 'input', 'é')])
        self.assertTrue(N.validate_phase(before, snapshot('nihao', preedit), 'preedit'))
        for phase, good in [('commit', commit), ('cancel', cancel), ('deadkey', dead)]:
            self.assertTrue(N.validate_phase(before, good, phase))
            for mutate in [lambda v: v.update(documentHasFocus=False),
                           lambda v: v['nativeInput'].update(commandOrder='1'),
                           lambda v: v['nativeInput'].update(value='wrong'),
                           lambda v: v['nativeInput'].update(focused=False),
                           lambda v: v['nativeInput']['events'][0].update(trusted=False),
                           lambda v: v['nativeInput']['events'][0].update(id='other')]:
                bad = copy.deepcopy(good); mutate(bad)
                with self.assertRaises(RuntimeError):
                    N.validate_phase(before, bad, phase)
        with self.assertRaises(RuntimeError):
            N.validate_phase(before, snapshot('你好', [event(1, 'input', '你好')]), 'commit')
        with self.assertRaises(RuntimeError):
            N.validate_phase(before, snapshot('é', [event(1, 'input', 'é')]), 'deadkey')

    def test_original_native_report_binds_phase_continuity_and_key_route(self):
        good = report_fixture()
        self.assertTrue(N.validate_report(good))
        for mutate in [lambda v:v['keys'].append('space'),
                       lambda v:v['phases'].pop('cancel'),
                       lambda v:v['phases']['cancel']['before']['nativeInput'].update(value=''),
                       lambda v:v['phases']['deadkey']['before']['nativeInput']['events'][0].update(sequence=0)]:
            bad=copy.deepcopy(good);mutate(bad)
            with self.assertRaises(RuntimeError):
                N.validate_report(bad)

    def test_deadline_does_not_accept_late_return_or_retry_effect(self):
        ticks = iter([0, 2])
        with self.assertRaisesRegex(RuntimeError, 'late'):
            N.wait_until(lambda: True, 1, lambda: None, clock=lambda: next(ticks), pause=lambda _: None)

    def test_actual_keymap_control_binds_existing_dead_key_and_compiled_hash(self):
        tree = ast.parse((HERE / 'current-reference-native-input.py').read_text())
        start = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'start')
        function = next(n for n in start.body if isinstance(n, ast.FunctionDef) and n.name == 'keymap')
        raw = 'key <AE12> { type="FOUR_LEVEL", symbols[Group1]= [ dead_acute, dead_grave ] }; key <AD03> { [ e, E ] };'
        value = fixture(); value['keymaps']['de'] = N.sha(raw.encode())
        commands = []
        scope = dict(live=lambda: None, command=commands.append, query=lambda _:raw, tool=lambda role:'/usr/fixture/'+role,
                     value=value, sha=N.sha, require=N.require, re=N.re, os=N.os)
        exec(compile(ast.Module(body=[function],type_ignores=[]),'<actual-keymap>','exec'),scope)
        with patch.dict(N.os.environ, DISPLAY=':fixture'):
            self.assertEqual(scope['keymap']('de'), N.sha(raw.encode()))
            self.assertEqual(commands, [['/usr/fixture/setxkbmap','-layout','de','-variant','','-option','']])
            scope['query'] = lambda _: raw.replace('dead_acute','acute')
            with self.assertRaisesRegex(RuntimeError,'keymap differs'):
                scope['keymap']('de')
            value['keymaps']['de'] = N.sha(scope['query'](None).encode())
            with self.assertRaisesRegex(RuntimeError,'dead-key'):
                scope['keymap']('de')

    def test_workflow_executes_actual_native_controls_before_acquisition(self):
        source = ast.parse((HERE / 'verify-external-reference-workflow.py').read_text())
        function = next(n for n in source.body if isinstance(n, ast.FunctionDef) and n.name == 'validate_current_at_registration')
        scope = {}
        exec(compile(ast.Module(body=[function], type_ignores=[]), '<actual-registration>', 'exec'), scope)
        root = HERE.resolve().parents[2]
        workflow = (root / '.github/workflows/fable-external-reference-source.yml').read_text()
        validate = scope['validate_current_at_registration']
        self.assertTrue(validate(workflow))
        for token in ["      - 'tests/composition/fable-game/current-reference-native-input.py'",
                      'python3 -I -B tests/composition/fable-game/test-current-reference-native-input.py',
                      'FSGG_CURRENT_NATIVE_INPUT_FACILITY: ${{ inputs.native-input-facility }}']:
            with self.assertRaises(AssertionError):
                validate(workflow.replace(token, '', 1))

    def test_native_journey_stops_on_first_input_failure_without_replay(self):
        calls = []
        runtime = dict(keymap=lambda x: calls.append(('map', x)), select=lambda x: calls.append(('select', x)), evidence={'manifestSha256':'a'*64})
        def key(value):
            calls.append(('key', value))
            raise RuntimeError('original XTest failure')
        with self.assertRaisesRegex(RuntimeError, 'original XTest failure'):
            retained={}
            N.journey(runtime, lambda: snapshot(), self.fail, lambda _: True, lambda: None, key, retained)
        self.assertFalse(retained['complete'])
        self.assertEqual(retained['keyRequests'],[{'key':'n','returnedZero':False}])
        self.assertEqual(calls, [('map','us'), ('select','libpinyin'), ('key','n')])

    def test_actual_journey_uses_native_key_route_and_original_readbacks(self):
        for mutant in [None, 'synthetic', 'cancel-text', 'gameplay', 'keymap']:
            text, composing, dead, keys, events = '', False, False, [], []
            def emit(kind, data=None, key=None):
                e = event(len(events)+1, kind, data, key);e['trusted'] = mutant != 'synthetic';events.append(e)
            def native_key(key):
                nonlocal text, composing, dead
                keys.append(key)
                if key in 'nihao' and len(key) == 1:
                    if not composing:
                        composing=True;emit('compositionstart')
                    emit('compositionupdate','nihao')
                elif key == 'space':
                    composing=False;text+='你好';emit('compositionend','你好');emit('input','你好')
                elif key == 'Escape':
                    composing=False
                    if mutant == 'cancel-text':text+='wrong'
                    emit('compositionend','')
                elif key == 'dead_acute':
                    dead=True;emit('keydown',key='Dead')
                elif key == 'e' and dead:
                    text+='é';emit('input','é')
            def dom():
                value=snapshot(text,copy.deepcopy(events))
                if mutant == 'gameplay' and keys:value['nativeInput']['commandOrder']='1'
                return value
            def wait(predicate):
                value=dom();N.require(predicate(value),'fixture actual readback unavailable');return value
            raw='compiled fixture map'
            runtime=dict(keymap=lambda _:N.sha(raw.encode()),select=lambda _:None,live=lambda:None,verify=lambda:None,
                         query=lambda _:raw+('changed' if mutant=='keymap' else ''),tool=lambda x:x,
                         evidence={'manifestSha256':'a'*64})
            with patch.dict(N.os.environ,DISPLAY=':fixture'):
                if mutant:
                    with self.assertRaises(RuntimeError):
                        N.journey(runtime,dom,wait,lambda _:True,lambda:None,native_key)
                else:
                    report=N.journey(runtime,dom,wait,lambda _:True,lambda:None,native_key)
                    self.assertTrue(N.validate_report(report))
                    self.assertEqual(report['keys'],[*'nihao','space',*'nihao','Escape','dead_acute','e'])
                    self.assertEqual(report['phases']['deadkey']['after']['nativeInput']['value'],'你好é')

    def test_actual_passive_js_recorder_and_snapshot(self):
        source = ast.parse((HERE / 'external-reference-orca.py').read_text())
        browser = next(ast.literal_eval(n.value) for n in source.body if isinstance(n, ast.Assign) and
                       any(isinstance(t, ast.Name) and t.id == 'BROWSER' for t in n.targets))
        script = r'''
const a=require(process.argv[2]),vm=require('node:vm');const handlers={};
global.window={};const root={getAttribute:k=>k==='data-command-order'?'':'0:0:0:0',querySelectorAll:()=>[]};
const note={id:'fourd-reference-note',tagName:'INPUT',value:'',getAttribute:()=> 'Encounter note'};
global.document={activeElement:note,addEventListener:(t,f,c)=>{if(c!==true)throw Error('capture');handlers[t]=f},
 hasFocus:()=>true,querySelectorAll:s=>s==='#fourd-reference-note'?[note]:s==='#fourd-reference'?[root]:[],querySelector:s=>s==='#fourd-reference'?root:null};
vm.runInNewContext('('+a.nativeInputRecorder.toString()+')()',{window,document});
for(const t of ['compositionstart','compositionupdate','compositionend','input'])handlers[t]({type:t,isTrusted:true,target:note,data:'nihao'});
const v=a.nativeInputSnapshot();const sampled=vm.runInNewContext('('+a.referenceDomSnapshot.toString()+')()',{window,document});if(sampled.nativeInput.events.length!==4)throw Error('serialized actual sample lost native capture');if(v.events.length!==4||!v.focused||v.label!=='Encounter note')throw Error('actual capture');
handlers.input({type:'input',isTrusted:false,target:note,data:'fake'});
if(a.nativeInputSnapshot().events.at(-1).trusted!==false)throw Error('synthetic hidden');
note.value='x'.repeat(257);let refused=false;try{a.nativeInputSnapshot()}catch{refused=true}if(!refused)throw Error('unbounded text');
note.value='';window.__nativeInput.overflow=true;refused=false;try{a.nativeInputSnapshot()}catch{refused=true}if(!refused)throw Error('capture truncation');
window.__nativeInput.overflow=false;document.querySelectorAll=()=>[];document.querySelector=()=>null;const removed=a.nativeInputSnapshot();if(removed.count!==0||removed.focused||'value' in removed)throw Error('disposed native target retained');
console.log('PASS actual capture-only handlers; no browser/IME');
'''
        with tempfile.TemporaryDirectory(prefix='native-input-controls-') as tmp:
            module = Path(tmp) / 'companion.cjs'; module.write_text(browser)
            runner = Path(tmp) / 'controls.cjs'; runner.write_text(script)
            subprocess.run(['node', '--max-old-space-size=128', str(runner), str(module)], check=True, timeout=15)


if __name__ == '__main__':
    unittest.main()
