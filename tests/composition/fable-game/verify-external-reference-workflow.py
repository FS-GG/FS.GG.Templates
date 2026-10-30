#!/usr/bin/env python3
"""Bounded static controls execute the workflow's actual input/metadata/ZIP assertions."""
import ast
import copy
import hashlib
import json
import os
from pathlib import Path
import re
import runpy
import subprocess
import tempfile
from unittest.mock import patch
from zipfile import ZipFile

INERT_ENV={'PATH':'/usr/bin:/bin','LANG':'C.UTF-8','LC_ALL':'C.UTF-8','PYTHONDONTWRITEBYTECODE':'1','PYTHONNOUSERSITE':'1'}
root=Path(__file__).resolve().parents[3]
text=(root/'.github/workflows/fable-external-reference-source.yml').read_text()

def validate_current_at_registration(workflow):
    command = 'PYTHONDONTWRITEBYTECODE=1 timeout --kill-after=5s 120s prlimit --cpu=120 --fsize=16777216 python3 -I -B tests/composition/fable-game/test-current-reference-at.py'
    assert "      - 'tests/composition/fable-game/test-current-reference-at.py'" in workflow, 'AT pure test path is not watched'
    static, candidate = workflow.split('\n  candidate:\n', 1)
    assert static.count(command) == 1, 'AT pure controls missing from PR static job'
    start = candidate.index('      - name: Verify existing external reference static controls')
    stop = candidate.index('\n      - ', start + 1)
    section = candidate[start:stop]
    assert section.count(command) == 1 and 'if:' not in section, 'AT pure controls missing from reusable preflight'
    assert stop <= candidate.index('      - name: Verify native producer run'), 'AT pure controls occur after acquisition'
    native_command = 'PYTHONDONTWRITEBYTECODE=1 timeout --kill-after=5s 120s prlimit --as=2147483648 --cpu=120 python3 -I -B tests/composition/fable-game/test-current-reference-native-input.py'
    for path in ['current-reference-native-input.py', 'test-current-reference-native-input.py']:
        assert "      - 'tests/composition/fable-game/" + path + "'" in workflow, 'native input source path not watched'
    assert static.count(native_command) == 1 and section.count(native_command) == 1, 'native input pure controls absent before acquisition'
    assert '      native-input-facility:' in workflow and 'FSGG_CURRENT_NATIVE_INPUT_FACILITY: ${{ inputs.native-input-facility }}' in workflow, 'facility input binding absent'
    acquisition_command = native_command.replace('test-current-reference-native-input.py', 'test-current-reference-noble-acquisition.py')
    assert static.count(acquisition_command) == 1 and section.count(acquisition_command) == 1, 'acquisition pure controls absent'
    for path in ['current-reference-noble-acquisition.py', 'test-current-reference-noble-acquisition.py', 'current-reference-noble-metadata-fixture.json']:
        assert "      - 'tests/composition/fable-game/" + path + "'" in workflow, 'acquisition source path not watched'
    marker = '      - name: Acquire declared current Noble inputs without installation'
    start = candidate.index(marker)
    stop = candidate.index('\n      - ', start + 1)
    acquisition = candidate[start:stop]
    assert "if: ${{ !inputs.preflight-only && inputs.rendering-input-source == 'current-public-composition' }}" in acquisition, 'acquisition current/full branch differs'
    assert 'timeout --kill-after=5s 240s prlimit --as=2147483648 --cpu=120' in acquisition, 'acquisition source bounds differ'
    assert 'current-reference-noble-acquisition.py "$RUNNER_TEMP/current-noble-acquisition"' in acquisition, 'acquisition output differs'
    assert candidate.index('Refuse held current AT before acquisition or setup') < start, 'held guard occurs after acquisition'
    assert '${{ runner.temp }}/current-noble-acquisition/acquisition.json' in workflow, 'closed acquisition receipt missing'
    transaction_command = native_command.replace('test-current-reference-native-input.py', 'test-current-reference-noble-transaction.py')
    assert static.count(transaction_command) == 1 and section.count(transaction_command) == 1, 'transaction pure controls absent'
    for path in ['current-reference-noble-transaction.py', 'test-current-reference-noble-transaction.py', 'fixtures/noble-c068-status.xz', 'fixtures/noble-source-prefix-request.json', 'fixtures/apt-config-init-order.json']:
        assert "      - 'tests/composition/fable-game/" + path + "'" in workflow, 'transaction source path not watched'
    tools = static.index('Check actual Noble solver tools and c068 fixture before work')
    acquisition = static.index('Acquire signed metadata for the offline source solver')
    solver = static.index('Exercise actual isolated no-install APT source prefix')
    assert tools < acquisition < solver, 'real solver preflight/order differs'
    assert '--check-context' in static and '--metadata-only "$RUNNER_TEMP/noble-source-metadata"' in static
    assert '--inputs "$RUNNER_TEMP/noble-source-metadata"' in static and '--out "$RUNNER_TEMP/noble-source-transaction"' in static
    assert '--request tests/composition/fable-game/fixtures/noble-source-prefix-request.json' in static
    assert 'env -i PATH=/usr/sbin:/usr/bin:/sbin:/bin' in static and 'timeout --kill-after=5s 120s prlimit --as=1073741824 --cpu=105' in static
    assert 'noble-source-transaction' not in candidate, 'real source solver leaked into reference runtime/preflight'
    assert '${{ runner.temp }}/noble-source-transaction/**' in static, 'original solver partial evidence missing'
    return True

validate_current_at_registration(text)
def assertion_codes(workflow):
    result=[]
    for name,count in [('Reject invalid caller or Templates identity before checkout',1),('Verify native producer run and authenticated archive before compilation',2),('Record authenticated preflight identity',1),('Bind successful full result to requested Templates source',1)]:
        marker='      - name: '+name+'\n'
        assert workflow.count(marker)==1, 'missing/ambiguous actual assertion step: '+name
        start=workflow.index(marker)+len(marker)
        end=workflow.find('\n      - ',start)
        section=workflow[start:end if end!=-1 else len(workflow)]
        blocks=re.findall(r"          python3 - <<'(PY(?:INPUT)?)'\n(.*?)\n          \1",section,re.S)
        assert len(blocks)==count, 'actual assertion body count differs: '+name
        result.extend('\n'.join(line[10:] for line in code.splitlines()) for _,code in blocks)
    for code in result:ast.parse(code)
    return result

codes=assertion_codes(text)
# A preceding preparation body must never become the authorization reader under test.
assert assertion_codes(text.replace('      - name: Reject invalid caller',"      - name: Inert extra preparation\n        run: |\n          python3 - <<'PY'\n          raise AssertionError('not an authorization reader')\n          PY\n      - name: Reject invalid caller",1))==codes
assert 'create-github-app-token' not in text and 'secrets.' not in text
assert 'workflow_dispatch:' not in text and 'workflow_call:' in text
assert 'GH_TOKEN: ${{ github.token }}' in text
assert 'repository: FS-GG/FS.GG.Templates\n          ref: ${{ inputs.templates-source }}' in text
assert 'contents: read\n  actions: read' in text
assert not re.search(r'(contents|actions|packages|id-token): write|continue-on-error',text)
assert text.index('Reject invalid caller') < text.index('repository: FS-GG/FS.GG.Templates')
assert text.index('release-custody.py verify') < text.index('actions/setup-dotnet')
for step in ['actions/setup-dotnet@v6','actions/setup-node@v6','Install pinned npm','Verify loaded toolchain','Qualify exact generated','Bind successful full']:
    position=text.index(step)
    section=text[position:text.find('\n      - ',position) if '\n      - ' in text[position:] else len(text)]
    expected = "if: ${{ !inputs.preflight-only || inputs.rendering-input-source == 'current-public-composition' }}" if step == 'actions/setup-dotnet@v6' else 'if: ${{ !inputs.preflight-only }}'
    if step in ['Qualify exact generated','Bind successful full']:expected="if: ${{ !inputs.preflight-only && inputs.rendering-input-source != 'palette-heading' }}"
    assert expected in section, step
assert "'qualification':'not-run'" in codes[3] and "'disposition':'preflight-passed'" in codes[3]
assert "packet['disposition']=='passed'" in codes[4]
assert "['chromium','firefox','webkit']" in codes[4]

# Read the actual closed GitHub expressions; producer rows are immutable workflow
# choices, not overridable caller inputs. The public row is the currently published default
# (Rendering 0.32.4, published original 4ede bytes); it is never caller-overridable.
PRODUCER_ROWS = {
    'public': {
        'PRODUCER_SOURCE':'4ede04be66cedffc8551cd14045bab714aa358a7',
        'PRODUCER_RUN':'40737624380','PRODUCER_ARTIFACT':'12838338215',
        'PRODUCER_ARCHIVE_SHA256':'baaa17b807bd52c9297dafbfd9161ec84fec4842317bb1f5df4e3d40d837c8bf',
        'PRODUCER_CUSTODY_SHA256':'89ea6424cae4d06969f0a60394679e9892bd2b873fb46ebd281aa10616809720',
        'PRODUCER_ARCHIVE_SIZE_BYTES':'15375023',
        'PRODUCER_VERSION':'0.32.4','PRODUCER_PLAN':'eng/release/palette-heading-0.32.4.json',
    },
    'candidate': {
        'PRODUCER_SOURCE':'9b73395658d4683a067d150ca9441b04e802c4af',
        'PRODUCER_RUN':'38200411661','PRODUCER_ARTIFACT':'11725317255',
        'PRODUCER_ARCHIVE_SHA256':'7b0532caf431cfa41acaf35555016cf126bc495c5a6e13fe7db6b8fbe7478cca',
        'PRODUCER_CUSTODY_SHA256':'85bb1dcdf0378d05ca536d5878b88dedc301ff1524d39d98966e23888aae0120',
        'PRODUCER_ARCHIVE_SIZE_BYTES':'15007722',
        'PRODUCER_VERSION':'0.32.2','PRODUCER_PLAN':'eng/release/external-authority-recovery-0.32.2.json',
    },
}
PRODUCER_ROWS['font-disposal']={
    'PRODUCER_SOURCE':'4ec6eafbbbf02264db9b0db4780c590abe0bf9cd',
    'PRODUCER_RUN':'39509314882','PRODUCER_ARTIFACT':'12305198394',
    'PRODUCER_ARCHIVE_SHA256':'84647332c124e511545787c8c3f8634d4f5177068521acfc86c93430ac73ef63',
    'PRODUCER_CUSTODY_SHA256':'7dbd4329546932c4c1d12767550b7b78aae85e32c81b354935b2c615b3e298c9',
    'PRODUCER_ARCHIVE_SIZE_BYTES':'15073469','PRODUCER_VERSION':'0.32.3',
    'PRODUCER_PLAN':'eng/release/font-disposal-0.32.3.json',
}
PRODUCER_ROWS['current-public-composition']=dict(PRODUCER_ROWS['public'])
selector_cases=[]
def selected_producer(candidate, mode):
    assert mode in PRODUCER_ROWS, 'closed candidate/public route required'
    result={}
    for key in PRODUCER_ROWS['public']:
        values=re.findall(r"^      "+key+r": \$\{\{ inputs\.rendering-input-source == 'current-public-composition' && '([^']+)' \|\| inputs\.rendering-input-source == 'font-disposal' && '([^']+)' \|\| inputs\.rendering-input-source == 'public' && '([^']+)' \|\| '([^']+)' \}\}$",candidate,re.M)
        assert len(values)==1, 'closed producer expression absent/duplicated: '+key
        current,font,public,source_candidate=values[0]
        assert current==PRODUCER_ROWS['current-public-composition'][key], 'current producer row differs: '+key
        assert font==PRODUCER_ROWS['font-disposal'][key], 'font producer row identity differs: '+key
        assert public==PRODUCER_ROWS['public'][key] and source_candidate==PRODUCER_ROWS['candidate'][key], 'producer row identity differs: '+key
        result[key]={'public':public,'candidate':source_candidate,'font-disposal':font,'current-public-composition':current}[mode]
    return {**result,'RENDERING_INPUT_SOURCE':mode}
for mode in ['candidate','public','font-disposal','current-public-composition']:
    assert selected_producer(text,mode)=={**PRODUCER_ROWS[mode],'RENDERING_INPUT_SOURCE':mode}
    selector_cases.append('selector-good-'+mode)
for mode in ['unknown','PUBLIC','public\n']:
    try: selected_producer(text,mode)
    except AssertionError: pass
    else: raise AssertionError('unknown producer mode accepted')
    selector_cases.append('selector-bad-mode-'+repr(mode))
for key in PRODUCER_ROWS['public']:
    for mode in ['candidate','public','font-disposal','current-public-composition']:
        changed=text.replace(PRODUCER_ROWS[mode][key], 'altered-'+PRODUCER_ROWS[mode][key])
        try: selected_producer(changed,mode)
        except AssertionError: pass
        else: raise AssertionError('altered producer binding accepted: '+key)
        selector_cases.append('selector-altered-'+mode+'-'+key)
# Stale 0.32.3 producer tuple (#4817): the current-public-composition slot must never fall back to the
# retained 0.32.3 font-disposal tuple, whole or in part, while the published default stays 0.32.4.
def stale_current_slot(candidate, key):
    pattern=re.compile(r"(^      "+key+r": \$\{\{ inputs\.rendering-input-source == 'current-public-composition' && ')([^']+)(')",re.M)
    assert len(pattern.findall(candidate))==1, 'single current-public slot required: '+key
    return pattern.sub(lambda match: match.group(1)+PRODUCER_ROWS['font-disposal'][key]+match.group(3),candidate)
assert selected_producer(text,'current-public-composition')['PRODUCER_VERSION']=='0.32.4'
selector_cases.append('selector-current-public-0.32.4-passes')
for key in PRODUCER_ROWS['public']:
    stale=stale_current_slot(text,key)
    assert stale!=text, 'stale fixture must change the workflow: '+key
    try: selected_producer(stale,'current-public-composition')
    except AssertionError as refusal: assert 'current producer row differs: '+key in str(refusal), 'stale refusal names the wrong binding'
    else: raise AssertionError('stale 0.32.3 current-public producer accepted: '+key)
    selector_cases.append('selector-stale-0.32.3-current-public-composition-'+key)
whole=text
for key in PRODUCER_ROWS['public']: whole=stale_current_slot(whole,key)
try: selected_producer(whole,'current-public-composition')
except AssertionError: selector_cases.append('selector-stale-0.32.3-current-public-composition-whole-tuple')
else: raise AssertionError('whole stale 0.32.3 tuple accepted')
print('PASS current-public producer tuple: 0.32.4 accepted; %d stale 0.32.3 single-field and whole-tuple mutants refused by name'%sum('stale-0.32.3' in name for name in selector_cases))
checks=0
assertion_cases=[]
def execute(code,env,should_pass):
    global checks
    previous=os.environ.copy()
    os.environ.clear(); os.environ.update(INERT_ENV); os.environ.update(env)
    try:
        try:
            exec(compile(code,'workflow-assertions','exec'),{})
        except (AssertionError,KeyError):
            assert not should_pass, 'valid fixture refused'
        else:
            assert should_pass, 'bad fixture accepted'
        checks+=1
        assertion_cases.append("actual-workflow-assertion-"+str(checks))
    finally:
        os.environ.clear(); os.environ.update(previous)

source=PRODUCER_ROWS['candidate']['PRODUCER_SOURCE']
env={'CALLER_REPOSITORY':'FS-GG/FS.GG.Rendering','TEMPLATES_SOURCE':'a'*40,**selected_producer(text,'candidate')}
execute(codes[0],env,True)
execute(codes[0],{**env,'RENDERING_INPUT_SOURCE':'public'},True)
for mode in ['unknown','public\n','PUBLIC']:
    execute(codes[0],{**env,'RENDERING_INPUT_SOURCE':mode},False)
for key,value in [('CALLER_REPOSITORY','FS-GG/FS.GG.Templates'),('CALLER_REPOSITORY','other/repository'),('TEMPLATES_SOURCE','main'),('TEMPLATES_SOURCE','a'*39),('TEMPLATES_SOURCE','A'*40),('TEMPLATES_SOURCE','a'*40+'\n')]:
    execute(codes[0],{**env,key:value},False)
# New operands are caller-provided inert fixtures here, never production defaults.
with tempfile.TemporaryDirectory() as directory:
    selected={'producerSha':'4ede04be66cedffc8551cd14045bab714aa358a7','producerRun':11,'producerAttempt':1,'producerArtifact':12,'outerSha256':'b'*64,'outerSizeBytes':1234,'custodySha256':'c'*64}
    palette={**env,'RENDERING_INPUT_SOURCE':'palette-heading','RENDERING_SUCCESSOR_INPUT':json.dumps(selected),'GITHUB_ENV':str(Path(directory)/'environment')}
    execute(codes[0],palette,True)
    exported=dict(line.split('=',1) for line in Path(palette['GITHUB_ENV']).read_text().splitlines())
    assert exported['PRODUCER_SOURCE']==selected['producerSha'] and exported['PRODUCER_VERSION']=='0.32.4'
    for key,value in [('producerSha',source),('producerRun',True),('producerAttempt',0),('producerAttempt',2),('outerSha256','missing'),('outerSizeBytes',67108865)]:
        bad={**selected,key:value};execute(codes[0],{**palette,'RENDERING_SUCCESSOR_INPUT':json.dumps(bad)},False)
    execute(codes[0],{**palette,'CALLER_REPOSITORY':'FS-GG/FS.GG.Templates'},False)
    execute(codes[0],{**palette,'RENDERING_SUCCESSOR_INPUT':'{}'},False)
    execute(codes[0],{**palette,'RENDERING_SUCCESSOR_INPUT':'{\"producerRun\":99,'+json.dumps(selected)[1:]},False)
    path=Path(directory)
    r={'id':11,'head_sha':selected['producerSha'],'run_attempt':1,'conclusion':'success','path':'.github/workflows/release.yml'}
    a={'id':12,'expired':False,'size_in_bytes':1234,'digest':'sha256:'+'b'*64,'workflow_run':{'id':11,'head_sha':r['head_sha']},'name':'rendering-source-candidate-'+r['head_sha']+'-0.32.4'}
    required=['Static release source and plan guard','Package consumption (release-only)','Generated product (template instantiation, release-only)','Qualify complete successor archive custody without publication']
    steps=['Pack the complete source candidate and verify custody','ApiCompat against the selected published baseline','Qualify all three browser families against original candidate archives without repacking']
    jobs={'total_count':4,'jobs':[{'name':name,'conclusion':'success','run_id':11,'run_attempt':1,'head_sha':r['head_sha'],'steps':[{'name':step,'conclusion':'success'} for step in steps]} for name in required]}
    writers=['Protected publication preflight (no mutation) [org-publication-writer]','Publish FS.GG.UI.* to org GitHub Packages (release-only) [org-publication-writer]']
    jobs['jobs'].extend({'name':name,'conclusion':'skipped','run_id':11,'run_attempt':1,'head_sha':r['head_sha'],'steps':[]} for name in writers);jobs['total_count']=6
    metadata_env={**palette,**exported,'RUNNER_TEMP':directory}
    class Digest:
        def hexdigest(self):return '4bcbb1c756a799ab634e14d1fc9191ac51a8cd5d3537aec75eeab1c1d545deaa'
    def palette_metadata(run,artifact,job_rows,success,attempt='1'):
        (path/'rendering-run.json').write_text(json.dumps(run));(path/'rendering-artifact.json').write_text(json.dumps(artifact));(path/'rendering-jobs.json').write_text(json.dumps(job_rows))
        with patch.object(Path,'read_bytes',return_value=b'plan-byte-fixture'),patch('hashlib.sha256',return_value=Digest()):execute(codes[1],{**metadata_env,'PRODUCER_ATTEMPT':attempt},success)
    palette_metadata(r,a,jobs,True)
    palette_metadata({**r,'run_attempt':2},a,jobs,False)
    later=json.loads(json.dumps(jobs))
    for job in later['jobs']:job['run_attempt']=2
    palette_metadata({**r,'run_attempt':2},a,later,False,attempt='2')
    palette_metadata(r,{**a,'workflow_run':{'id':99,'head_sha':r['head_sha']}},jobs,False)
    palette_metadata(r,a,{**jobs,'total_count':7},False)
    for index in range(4):
        bad=json.loads(json.dumps(jobs));bad['jobs'][index]['conclusion']='cancelled';palette_metadata(r,a,bad,False)
    for index in range(3):
        bad=json.loads(json.dumps(jobs));bad['jobs'][3]['steps'][index]['conclusion']='failure';palette_metadata(r,a,bad,False)
    bad=json.loads(json.dumps(jobs));bad['jobs'][0]['head_sha']='a'*40;palette_metadata(r,a,bad,False)
    for index in [4,5]:
        bad=json.loads(json.dumps(jobs));bad['jobs'][index]['conclusion']='success';palette_metadata(r,a,bad,False)
print('PASS actual palette caller coordinates and mandatory producer/package/ApiCompat/three-browser refusal controls')

with tempfile.TemporaryDirectory() as directory:
    path=Path(directory); env['RUNNER_TEMP']=directory
    for mode in ['candidate','public','font-disposal','current-public-composition']:
        env.update(selected_producer(text,mode))
        run={'id':int(env['PRODUCER_RUN']),'head_sha':env['PRODUCER_SOURCE'],'conclusion':'success','path':'.github/workflows/release.yml','run_attempt':1}
        artifact={'id':int(env['PRODUCER_ARTIFACT']),'expired':False,'size_in_bytes':int(env['PRODUCER_ARCHIVE_SIZE_BYTES']),'digest':'sha256:'+env['PRODUCER_ARCHIVE_SHA256'],'workflow_run':{'id':run['id'],'head_sha':run['head_sha']},'name':'rendering-source-candidate-'+run['head_sha']+'-'+env['PRODUCER_VERSION']}
        # Per-mode plan identity: the font-disposal plan and the palette-heading plan have different bytes.
        PLAN_IDENTITY={'font-disposal':(3490,'89369de0c0944c66a52c6ed914cef78d6bb7670866baedf85cd8a198c5c46239'),'current-public-composition':(3514,'4bcbb1c756a799ab634e14d1fc9191ac51a8cd5d3537aec75eeab1c1d545deaa')}
        def metadata(r,a,success,plan_good=True,plan_identity=None):
            (path/'rendering-run.json').write_text(json.dumps(r)); (path/'rendering-artifact.json').write_text(json.dumps(a))
            # Closed plan-byte seam: metadata fixtures do not acquire a producer checkout.
            size,digest=plan_identity or PLAN_IDENTITY.get(mode,(3490,'89369de0c0944c66a52c6ed914cef78d6bb7670866baedf85cd8a198c5c46239'))
            class PlanDigest:
                def hexdigest(self): return digest if plan_good else '0'*64
            with patch.object(Path,'read_bytes',return_value=b'x'*size), patch.object(hashlib,'sha256',side_effect=lambda raw: PlanDigest()):
                execute(codes[1],env,success)

        metadata(run,artifact,True)
        if mode in PLAN_IDENTITY:
            metadata({**run,'run_attempt':2},artifact,False)
            metadata(run,artifact,False,plan_good=False)
            # Causal control: the other plan's size and digest must be refused for this mode.
            wrong=PLAN_IDENTITY['font-disposal' if mode=='current-public-composition' else 'current-public-composition']
            metadata(run,artifact,False,plan_identity=wrong)
        for key,value in [('id',0),('head_sha','b'*40),('conclusion','failure'),('path','.github/workflows/other.yml')]:
            metadata({**run,key:value},artifact,False)
        for key,value in [('id',0),('expired',True),('size_in_bytes',1),('digest','sha256:'+'0'*64),('name','other'),('workflow_run',{'id':0,'head_sha':run['head_sha']}),('workflow_run',{'id':run['id'],'head_sha':'b'*40})]:
            metadata(run,{**artifact,key:value},False)
        # A complete producer tuple from the other mode must fail the selected route.
        other='public' if mode=='candidate' else 'candidate'
        other_row=PRODUCER_ROWS[other]
        mixed_run={**run,'id':int(other_row['PRODUCER_RUN']),'head_sha':other_row['PRODUCER_SOURCE']}
        mixed_artifact={**artifact,'id':int(other_row['PRODUCER_ARTIFACT']),'size_in_bytes':int(other_row['PRODUCER_ARCHIVE_SIZE_BYTES']),
                        'digest':'sha256:'+other_row['PRODUCER_ARCHIVE_SHA256'],
                        'workflow_run':{'id':mixed_run['id'],'head_sha':mixed_run['head_sha']},
                        'name':'rendering-source-candidate-'+mixed_run['head_sha']+'-'+other_row['PRODUCER_VERSION']}
        metadata(mixed_run,mixed_artifact,False)
        receipt_env={**env,'CALLER_SOURCE':'e'*40,'CALLER_RUN':'123','CALLER_ATTEMPT':'1','PREFLIGHT_ONLY':'true'}
        calls=[]
        def git_tree(argv,text):
            calls.append(argv)
            assert text is True
            if argv==['git','rev-parse','HEAD^{tree}']: return 'b'*40+'\n'
            if argv==['git','-C','.tmp/rendering-source','rev-parse','HEAD^{tree}']: return 'c'*40+'\n'
            raise AssertionError('unselected preflight subprocess')
        with patch.object(subprocess,'check_output',side_effect=git_tree):
            execute(codes[3],receipt_env,True)
        receipt=json.loads((path/'external-reference-preflight.json').read_text())
        assert len(calls)==2 and receipt['templates']=={'revision':'a'*40,'tree':'b'*40}
        producer_expected={name:env[key] for name,key in [('revision','PRODUCER_SOURCE'),('run','PRODUCER_RUN'),('artifact','PRODUCER_ARTIFACT'),('archiveSha256','PRODUCER_ARCHIVE_SHA256'),('custodySha256','PRODUCER_CUSTODY_SHA256')]}
        if mode=='font-disposal':
            producer_expected.update(attempt='1',version=env['PRODUCER_VERSION'],plan=env['PRODUCER_PLAN'],rawPlanSha256='89369de0c0944c66a52c6ed914cef78d6bb7670866baedf85cd8a198c5c46239')
        assert receipt['producer']==producer_expected
        assert receipt['producerTree']=='c'*40 and receipt['artifactSizeBytes']==int(env['PRODUCER_ARCHIVE_SIZE_BYTES'])
        assert receipt['renderingInputSource']==mode and receipt['requestedPhase']=='preflight'
        assert receipt['qualification']=='not-run' and receipt['publication'] is False and receipt['installedAcceptance'] is False
    env.update(selected_producer(text,'candidate'))
    (path/'rendering-packet').mkdir()
    custody=b'fixture custody'; env['PRODUCER_CUSTODY_SHA256']=hashlib.sha256(custody).hexdigest()
    def zip_case(count,duplicate=False,tamper=False):
        with ZipFile(path/'rendering-packet.zip','w') as archive:
            for n in range(count): archive.writestr(f'{n}/package{n if not duplicate else 0}.nupkg',b'fixture')
            archive.writestr('release-custody.json',custody if not tamper else b'changed')
    zip_case(19); execute(codes[2],env,True)
    for count,duplicate,tamper in [(18,False,False),(20,False,False),(19,True,False),(19,False,True)]:
        zip_case(count,duplicate,tamper); execute(codes[2],env,False)
    env['RENDERING_INPUT_SOURCE']='palette-heading'
    zip_case(19);execute(codes[2],env,True)
    with ZipFile(path/'rendering-packet.zip','a') as archive:archive.writestr('unexpected.txt',b'not original custody')
    execute(codes[2],env,False)
    with ZipFile(path/'rendering-packet.zip','w') as archive:
        for n in range(19):archive.writestr(('../escape.nupkg' if n==0 else f'package{n}.nupkg'),b'fixture')
        archive.writestr('release-custody.json',custody)
    execute(codes[2],env,False)
# Match the actual upload allowlist against emitted companions and the retained failing path.
# A broad output-tree glob selected the colon-bearing NuGet HTTP cache in40740615402.
def palette_upload_controls(workflow):
    import glob
    marker='      - name: Upload source qualification evidence\n'
    assert workflow.count(marker)==1
    section=workflow.split(marker,1)[1]
    paths=section.split('          path: |\n',1)[1].splitlines()
    patterns=[line.strip().replace('${{ runner.temp }}/','') for line in paths if line.startswith('            ${{ runner.temp }}/')]
    required=['palette-candidate/qualification.json','palette-candidate/candidate-input.json','palette-candidate/orca-input.json','palette-candidate/consumer-before.json','palette-candidate/consumer-after.json','palette-candidate/server.log','palette-candidate/orca-version.log','palette-candidate/orca-input.json.orca-debug.log','palette-candidate/orca-input.json.orca.log','palette-candidate/orca-input.json.speechd-preflight.json','palette-candidate/orca-input.json.browser-dom.json','palette-candidate/orca-input.json.speechd-logs/espeak-ng.log','palette-candidate/orca-input.json.speechd-logs/speech-dispatcher.log','palette-candidate/receiver/SvgFoundation/Studio/packages.lock.json','palette-candidate/receiver/SvgFoundation/Studio/obj/project.assets.json','palette-template-feed/FS.GG.Workspace.Template.fixture.nupkg','palette-template-feed/python-fixture-projection.json','palette-template-feed/python-fixture-preflight/qualification.json','external-reference-preflight.json','rendering-packet.zip','rendering-packet/release-custody.json','rendering-run.json','rendering-artifact.json','rendering-jobs.json']
    excluded=['palette-candidate/http/670c1461c29885f9aa22c281d8b7da90845b38e4$ps:_api.nuget.org_v3_index.json/list_fable.browser.blob.dat','palette-candidate/packages/unrelated.nupkg','palette-candidate/receiver/node_modules/unrelated.json']
    with tempfile.TemporaryDirectory() as directory:
        base=Path(directory)
        for name in required+excluded:
            file=base/name;file.parent.mkdir(parents=True,exist_ok=True);file.write_bytes(b'inert emitted evidence')
        selected={str(Path(name).relative_to(base)) for pattern in patterns for name in glob.glob(str(base/pattern),recursive=True) if Path(name).is_file()}
        assert set(required)<=selected, 'required qualification companion omitted'
        assert not set(excluded)&selected, 'cache or generated tree selected for evidence upload'
        assert not any(re.search(r'["<>|*?:\r\n]',name) for name in selected), 'upload-invalid retained path selected'
    return True

assert palette_upload_controls(text)
try:palette_upload_controls(text.replace('${{ runner.temp }}/palette-candidate/*.json','${{ runner.temp }}/palette-candidate/**',1))
except AssertionError:pass
else:raise AssertionError('original broad upload regression accepted')
print('PASS actual upload allowlist:24 required companions selected; original colon-bearing cache and generated trees refused')
print(f'PASS: {checks} actual workflow assertion fixtures; source/permission/order/phase controls')

# Execute the actual provision shell against a finite npm command fixture. No packages install.
def npm_provision(candidate):
    match=re.search(r"      - name: Install pinned npm for locked toolchain\n(.*?)(?=\n      - )",candidate,re.S)
    assert match and 'if: ${{ !inputs.preflight-only }}' in match[1]
    assert 'npm install --global npm@12.1.0' in match[1]
    assert candidate.index('Install pinned npm') < candidate.index('Verify loaded toolchain')
    shell=match[1].split('        run: |\n',1)[1]
    return '\n'.join(line[10:] for line in shell.splitlines())
provision=npm_provision(text)
for bad in [text.replace('npm install --global npm@12.1.0','npm install --global npm@latest'),text.replace('npm install --global npm@12.1.0','true'),text.replace('      - name: Install pinned npm for locked toolchain\n        if: ${{ !inputs.preflight-only }}','      - name: Install pinned npm for locked toolchain')]:
    try: npm_provision(bad)
    except AssertionError: pass
    else: raise AssertionError('unpinned or missing npm provision accepted')
with tempfile.TemporaryDirectory() as directory:
    path=Path(directory); state=path/'npm-version'; state.write_text('11.19.1')
    binary=path/'npm'
    binary.write_text("#!/usr/bin/env python3\nimport os,sys\nfrom pathlib import Path\np=Path(os.environ['NPM_FIXTURE_STATE'])\nif sys.argv[1:]==['install','--global','npm@12.1.0']: p.write_text('12.1.0')\nelif sys.argv[1:]==['--version']: print(p.read_text())\nelse: sys.exit(2)\n")
    binary.chmod(0o700)
    env={**INERT_ENV,'PATH':directory+os.pathsep+INERT_ENV['PATH'],'NPM_FIXTURE_STATE':str(state)}
    assert subprocess.run(['bash','-euo','pipefail','-c',provision],env=env,check=False,timeout=5).returncode==0
    state.write_text('11.19.1')
    assert subprocess.run(['bash','-euo','pipefail','-c',provision.replace('npm install --global npm@12.1.0','true')],env=env,check=False,timeout=5).returncode!=0
print('PASS pinned npm provision: actual shell upgrades bundled11.19.1 fixture to12.1.0; missing/floating provision refused')

# The actual native Provider command must exit successfully before its exact-count assertion.
provider_match=re.search(r"          python3 - <<'PYPROVIDER'\n(.*?)\n          PYPROVIDER",text,re.S)
assert provider_match and not re.search(r'\brg\s',text)
provider_code='\n'.join(line[10:] for line in provider_match[1].splitlines())
ast.parse(provider_code)
qualify_match=re.search(r'      - name: Qualify exact generated candidate and existing publication validator\n.*?        run: \|\n(.*?)(?=\n      - )',text,re.S)
assert qualify_match
qualification='\n'.join(line[10:] for line in qualify_match[1].splitlines())
provider_prefix=qualification.split('bash tests/composition/fable-game/verify-external-reference-candidate.sh',1)[0]
assert provider_prefix.startswith('set -euo pipefail\n') and provider_prefix.index('dotnet run') < provider_prefix.index('PYPROVIDER')
with tempfile.TemporaryDirectory() as directory:
    path=Path(directory);log=path/'provider-composition.log'
    previous=os.environ.copy();os.environ.clear();os.environ.update(INERT_ENV);os.environ['RUNNER_TEMP']=directory
    try:
        for count in [249,248,250,247,246,243,242,244,241,240,239,229,228,230,209,208,210,203,192,0]:
            log.write_text('build diagnostics\n'+'PASS assertion\n'*count+' PASS indented\nPASS\twrong delimiter\n')
            try: exec(compile(provider_code,'actual-provider-count','exec'),{})
            except AssertionError: assert count!=249
            else: assert count==249
        log.unlink()
        try: exec(compile(provider_code,'actual-provider-count','exec'),{})
        except FileNotFoundError: pass
        else: raise AssertionError('missing Provider evidence accepted')
        binary=path/'dotnet';binary.write_text('#!/usr/bin/env bash\nexit 7\n');binary.chmod(0o700)
        env={**INERT_ENV,'PATH':directory+os.pathsep+INERT_ENV['PATH'],'RUNNER_TEMP':directory}
        result=subprocess.run(['bash','-euo','pipefail','-c',provider_prefix],env=env,text=True,capture_output=True,timeout=5)
        assert result.returncode==7 and 'ProviderComposition: verified' not in result.stdout, 'failed Provider command must stop before count'
    finally: os.environ.clear();os.environ.update(previous)
print('PASS actual stdlib Provider count249;248/250/247/246/243;242/244/241/240/239/229/228/230/209/208/210/203/192/empty/missing evidence refused; native command exit7 preserved')

# Execute the actual final receipt binder, including its report reads and writeback.
# A good receipt must describe all eight cases in each of the three families.
for mode in ['candidate','public','font-disposal']:
    with tempfile.TemporaryDirectory() as directory:
        path=Path(directory); evidence=path/'external-reference'; evidence.mkdir()
        templates={'revision':'a'*40,'tree':'b'*40}
        (path/'external-reference-preflight.json').write_text(json.dumps({'templates':templates,'renderingInputSource':mode}))
        families=['chromium','firefox','webkit']
        reports={}
        for family in families:
            report=evidence/f'{family}-browser.json'
            report.write_text(json.dumps({'stats':{'expected':8,'unexpected':0,'skipped':0,'flaky':0}}))
            reports[family]=hashlib.sha256(report.read_bytes()).hexdigest()
        custody_digest=PRODUCER_ROWS[mode]['PRODUCER_CUSTODY_SHA256']
        packet={'disposition':'passed','templates':templates,
                'producer':{'revision':PRODUCER_ROWS[mode]['PRODUCER_SOURCE'],'custodyManifestSha256':custody_digest},
                'renderingInputSource':'nuget.org' if mode=='public' else 'candidate','templatesInputSource':'source-built-candidate',
                'renderingPublicInputsQualified':mode=='public','browserFamilies':families,
                'passedPerFamily':15 if mode=='font-disposal' else 8,'skipped':0,'browserReportSha256':reports}
        if mode=='font-disposal':
            packet.update(qualificationMode=mode,studioFontCases=runpy.run_path(str(root/'tests/composition/fable-game/external-reference-orca.py'))['FONT_CASE_TITLES'])
            packet['producer']['candidateVersion']='0.32.3'
        binder_env={'RUNNER_TEMP':directory,'TEMPLATES_SOURCE':templates['revision'],
                    'PRODUCER_SOURCE':PRODUCER_ROWS[mode]['PRODUCER_SOURCE'],'PRODUCER_CUSTODY_SHA256':custody_digest,
                    'RENDERING_INPUT_SOURCE':mode}
        def bind(candidate,success):
            receipt=evidence/'qualification.json'
            receipt.write_text(json.dumps(candidate))
            before=receipt.read_bytes()
            execute(codes[4],binder_env,success)
            if success:
                bound=json.loads(receipt.read_text())
                assert bound=={**candidate,'nativePreflight':{'templates':templates,'renderingInputSource':mode}}
            else:
                assert receipt.read_bytes()==before, 'refused receipt must not be rewritten'
        bind(packet,True)
        negatives=[]
        def altered(path,value):
            candidate=copy.deepcopy(packet); target=candidate
            for key in path[:-1]: target=target[key]
            target[path[-1]]=value; negatives.append(candidate)
        altered(['passedPerFamily'],4)
        altered(['templates','revision'],'c'*40)
        altered(['templates','tree'],'c'*40)
        altered(['producer','revision'],'c'*40)
        altered(['producer','custodyManifestSha256'],'0'*64)
        altered(['browserReportSha256','chromium'],'0'*64)
        altered(['browserFamilies'],['firefox','chromium','webkit'])
        altered(['browserFamilies'],['chromium','firefox'])
        altered(['skipped'],1)
        altered(['disposition'],'failed')
        altered(['renderingInputSource'],'candidate' if mode=='public' else 'nuget.org')
        altered(['renderingPublicInputsQualified'],mode!='public')
        altered(['templatesInputSource'],'published')
        for candidate in negatives: bind(candidate,False)
        missing=copy.deepcopy(packet); del missing['browserReportSha256']; bind(missing,False)
        bind(packet,True)
        print(f'PASS actual final receipt binder: valid{packet["passedPerFamily"]} per family; {len(negatives)+1} negative receipts refused without writeback')

# Reusable calls bypass the pull-request-only static job, so run these controls
# from the exact checked-out consumer before archive acquisition or compilation.
control=text.index('      - name: Verify existing external reference static controls')
checkout=text.index('repository: FS-GG/FS.GG.Templates\n          ref: ${{ inputs.templates-source }}')
assert checkout < control < text.index('      - name: Verify native producer run')
section=text[control:text.index('\n      - ',control+1)]
assert 'python3 tests/composition/fable-game/verify-external-reference-workflow.py' in section
assert 'python3 tests/composition/fable-game/test-external-reference-public.py' in section
assert 'if:' not in section, 'static controls must also run for reusable preflight calls'
print('PASS reusable static controls run after exact checkout and before expensive qualification')

# Names/count are consumed only after the complete module returns.
qualified_assertion_names=selector_cases+assertion_cases
assert len(qualified_assertion_names)==len(set(qualified_assertion_names))

# A finite union binds the actual maintained test titles and successful report rows.
receiver=runpy.run_path(str(root/'tests/composition/fable-game/external-reference-orca.py'))
titles=receiver['FONT_CASE_TITLES']
spec=(root/'templates/fs-gg-fable-game/Browser.Tests/two-client.spec.ts').read_text()
expanded=spec.replace('Studio ${cancellation} prevents a late genuine font load from mounting or leaking',
    'Studio timeout prevents a late genuine font load from mounting or leaking\nStudio replacement prevents a late genuine font load from mounting or leaking')
assert len(titles)==7 and all(expanded.count(title)==1 for title in titles)
assert 'for (const cancellation of ["timeout", "replacement"] as const)' in spec
assert "timeout-minutes: ${{ inputs.rendering-input-source == 'palette-heading' && 30 || inputs.rendering-input-source == 'font-disposal' && 60 || 35 }}" in text
assert text.index('Require fresh exact SDK root') < text.index('actions/setup-dotnet') < text.index('test "$(dotnet --version)" = 10.0.401')
sdk=text.split('      - name: Require fresh exact SDK root',1)[1].split('      - uses:',1)[0]
assert "!inputs.preflight-only && (inputs.rendering-input-source == 'font-disposal' || inputs.rendering-input-source == 'palette-heading')" in sdk
assert '! -e "$expected" && ! -L "$expected"' in sdk and '>> "$GITHUB_ENV"' in sdk
selector=receiver['browser_selector']
assert selector('candidate')==selector('public')=='external authority reference|FourD reference'
# Playwright grep is applied to project/file/full title, not a bare-title anchor.
for title in titles:
    assert re.search(selector('font-disposal'),'[chromium] two-client.spec.ts '+title)
    assert not re.search(selector('candidate'),title)
for mode in ('unknown','FONT-DISPOSAL','font-disposal\n'):
    try: selector(mode)
    except RuntimeError: pass
    else: raise AssertionError('unknown selection accepted')
# Genuine source-derived identities and actual JSON reporter topology: four
# direct historical specs, four describe-nested specs, seven direct font specs.
references=receiver['REFERENCE_CASES']
for filename,ancestry,title in references:
    authored=(root/'templates/fs-gg-fable-game/Browser.Tests'/filename).read_text()
    assert authored.count('test("'+title+'"')==1
    for group in ancestry: assert authored.count('test.describe("'+group+'"')==1
    assert re.search(selector('font-disposal'),'[chromium] '+filename+' '+ ' '.join(ancestry+(title,)))
def json_spec(filename,title):
    return {'file':filename,'title':title,'ok':True,'tests':[{'status':'expected'}]}
direct=[json_spec(filename,title) for filename,ancestry,title in references if not ancestry]
nested=[json_spec(filename,title) for filename,ancestry,title in references if ancestry]
report={'stats':{'expected':15,'unexpected':0,'skipped':0,'flaky':0},'suites':[
    {'title':'two-client.spec.ts','file':'two-client.spec.ts','specs':direct+[json_spec('two-client.spec.ts',title) for title in titles]},
    {'title':'external-command-outcomes.spec.ts','file':'external-command-outcomes.spec.ts','specs':[],
     'suites':[{'title':'external authority reference command outcomes','specs':nested}]},
]}
# Causal RED: the original209a1ad leaf-only predicate rejects this genuine-shaped
# successful15-case report: only four historical leaves contain its grep text.
all_leaves=report['suites'][0]['specs']+report['suites'][1]['suites'][0]['specs']
assert len(all_leaves)==15
assert sum(bool(re.search('external authority reference|FourD reference',v['title'])) for v in all_leaves)==4
validate_report=receiver['validate_browser_report']
assert validate_report(report,'font-disposal')
report_bad=[]
for key in ('unexpected','skipped','flaky'):
    bad=copy.deepcopy(report);bad['stats'][key]=1;report_bad.append(bad)
for title in ('unrelated Studio case',titles[0]):
    bad=copy.deepcopy(report);bad['suites'][0]['specs'][-1]['title']=title;report_bad.append(bad)
# Preserve15successfulstats while independently changing each actual identity,
# describe ancestry, file, multiplicity, result or population.
for field,value in [('file','foreign.spec.ts'),('title','foreign leaf')]:
    bad=copy.deepcopy(report);bad['suites'][1]['suites'][0]['specs'][0][field]=value;report_bad.append(bad)
bad=copy.deepcopy(report);bad['suites'][1]['suites'][0]['title']='foreign describe';report_bad.append(bad)
bad=copy.deepcopy(report);bad['suites'][1]['suites'][0]['specs'].pop();report_bad.append(bad)
bad=copy.deepcopy(report);bad['suites'][1]['suites'][0]['specs'][1]=copy.deepcopy(bad['suites'][1]['suites'][0]['specs'][0]);report_bad.append(bad)
for status in ('skipped','unexpected'):
    bad=copy.deepcopy(report);bad['suites'][1]['suites'][0]['specs'][0]['tests'][0]['status']=status;report_bad.append(bad)
bad=copy.deepcopy(report);bad['suites'][0]['specs'][-1]['ok']=False;report_bad.append(bad)
for bad in report_bad:
    try: validate_report(bad,'font-disposal')
    except RuntimeError: pass
    else: raise AssertionError('wrong/missing/duplicate/skipped named case accepted')
print('PASS reportshape causal RED originalleafpredicate4not8; GREEN genuine4direct+4nested+7font; '+str(len(report_bad))+' independent identity/population/outcome refusals')
for mode in ('candidate','public'):
    assert validate_report({'stats':{'expected':8,'unexpected':0,'skipped':0,'flaky':0}},mode)
    try: validate_report(report,mode)
    except RuntimeError: pass
    else: raise AssertionError('new population selected historical contract')
font_packet={'qualificationMode':'font-disposal','producer':{'revision':PRODUCER_ROWS['font-disposal']['PRODUCER_SOURCE'],'candidateVersion':'0.32.3'},'studioFontCases':titles,'passedPerFamily':15,'skipped':0,'browserFamilies':['chromium','firefox','webkit']}
assert receiver['browser_prerequisite'](font_packet,{'renderingInputSource':'font-disposal'})
for field,value in [('qualificationMode','candidate'),('passedPerFamily',8),('studioFontCases',titles[:-1]),('producer',{'revision':PRODUCER_ROWS['candidate']['PRODUCER_SOURCE'],'candidateVersion':'0.32.3'})]:
    bad=copy.deepcopy(font_packet);bad[field]=value
    assert not receiver['browser_prerequisite'](bad,{'renderingInputSource':'font-disposal'})
for mode in ('candidate','public'):
    assert not receiver['browser_prerequisite'](font_packet,{'renderingInputSource':mode})
script=(root/'tests/composition/fable-game/verify-external-reference-candidate.sh').read_text()
assert script.index('if [[ "$input_mode" == font-disposal ]]; then') < script.index('mkdir -p "$out"')
assert script.index('>"$out/studio-restore.log"') < script.index('>"$out/studio-build.log"') < script.index('npx playwright install')
assert 'FSGG_SVG_AUTHORING_VERSION="$version" FSGG_SVG_CANDIDATE_FEED="$out/feed"' in script
assert "cached.read_bytes()" in script and "assets['libraries'][name+'/'+version]['type']=='package'" in script
print('PASS finite0323 source/plan/SDK/Studio guards;7 genuine font titles+8 historical cases across3 families; wrong/missing/duplicate/skipped/mixed receipts refused; no native execution')

# The maintained shell guard itself refuses mixed current/historical tuples before
# mkdir, Git, package/tool work or output creation; only Bash is spawned here.
mode_guard=next(line for line in script.splitlines() if line.startswith('[[ "$input_mode" == candidate'))
font_guard=script.split('if [[ "$input_mode" == font-disposal ]]; then',1)[1].split('\nfi',1)[0]
actual_guard='set -euo pipefail\n'+mode_guard+'\nif [[ "$input_mode" == font-disposal ]]; then'+font_guard+'\nfi\nprintf GUARD_ACCEPTED'
guard_env={**INERT_ENV,'input_mode':'font-disposal','version':'0.32.3','expected_source':PRODUCER_ROWS['font-disposal']['PRODUCER_SOURCE'],'templates_package':''}
for changes,good in [({},True),({'version':'0.32.2'},False),({'expected_source':'6c9f766fdd91483c2de6f061e75589e94852a265'},False),({'templates_package':'foreign.nupkg'},False),({'FsGgSvgAuthoringVersion':'0.32.1'},False),({'input_mode':'unknown'},False)]:
    result=subprocess.run(['/bin/bash','-c',actual_guard],env={**guard_env,**changes},capture_output=True,text=True,timeout=5)
    assert (result.returncode==0)==good and ('GUARD_ACCEPTED' in result.stdout)==good, 'actual pre-effect guard disposition differs'
print('PASS actual closed-mode pre-effect shell guard: correct0323 accepted; historical/source/package/override/unknown controls refused without product effects')
