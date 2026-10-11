#!/usr/bin/env python3
"""Bounded static controls execute the workflow's actual input/metadata/ZIP assertions."""
import ast
import copy
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile
from unittest.mock import patch
from zipfile import ZipFile

root=Path(__file__).resolve().parents[3]
text=(root/'.github/workflows/fable-external-reference-source.yml').read_text()
blocks=re.findall(r"          python3 - <<'(PY(?:INPUT)?)'\n(.*?)\n          \1",text,re.S)
codes=[ '\n'.join(line[10:] for line in code.splitlines()) for _,code in blocks ]
for code in codes:
    ast.parse(code)
assert len(codes)==5, len(codes)
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
    assert 'if: ${{ !inputs.preflight-only }}' in section, step
assert "'qualification':'not-run'" in codes[3] and "'disposition':'preflight-passed'" in codes[3]
assert "packet['disposition']=='passed'" in codes[4]
assert "['chromium','firefox','webkit']" in codes[4]

# Read the actual closed GitHub expressions; producer rows are immutable workflow
# choices, not overridable caller inputs. Keep the published public row intact.
PRODUCER_ROWS = {
    'public': {
        'PRODUCER_SOURCE':'6c9f766fdd91483c2de6f061e75589e94852a265',
        'PRODUCER_RUN':'37419955679','PRODUCER_ARTIFACT':'11392773621',
        'PRODUCER_ARCHIVE_SHA256':'486182db3efd8442c007f66322a7bfb27caf0cb8e3c87bc2521e66dd90a7adee',
        'PRODUCER_CUSTODY_SHA256':'ecd0c5d742fd8d19d5659991e413e92971c1d2cb9aea913faa2bb249f53f577d',
        'PRODUCER_ARCHIVE_SIZE_BYTES':'14912688',
    },
    'candidate': {
        'PRODUCER_SOURCE':'0f7deec93297bcda67f0e3a1dbd23dcff66a09d5',
        'PRODUCER_RUN':'38102910865','PRODUCER_ARTIFACT':'11688966848',
        'PRODUCER_ARCHIVE_SHA256':'7a1592443d6723a76543e7569856154bcf0205d58ddb90347165301750676fef',
        'PRODUCER_CUSTODY_SHA256':'fe657ad839ed1740c29f85dc7d2244694722d70007512d6fdb22f86927b3a492',
        'PRODUCER_ARCHIVE_SIZE_BYTES':'14993249',
    },
}
selector_cases=[]
def selected_producer(candidate, mode):
    assert mode in PRODUCER_ROWS, 'closed candidate/public route required'
    result={}
    for key in PRODUCER_ROWS['public']:
        values=re.findall(r"^      "+key+r": \$\{\{ inputs\.rendering-input-source == 'public' && '([^']+)' \|\| '([^']+)' \}\}$",candidate,re.M)
        assert len(values)==1, 'closed producer expression absent/duplicated: '+key
        public,source_candidate=values[0]
        assert public==PRODUCER_ROWS['public'][key] and source_candidate==PRODUCER_ROWS['candidate'][key], 'producer row identity differs: '+key
        result[key]=public if mode=='public' else source_candidate
    return {**result,'RENDERING_INPUT_SOURCE':mode}
for mode in ['candidate','public']:
    assert selected_producer(text,mode)=={**PRODUCER_ROWS[mode],'RENDERING_INPUT_SOURCE':mode}
    selector_cases.append('selector-good-'+mode)
for mode in ['unknown','PUBLIC','public\n']:
    try: selected_producer(text,mode)
    except AssertionError: pass
    else: raise AssertionError('unknown producer mode accepted')
    selector_cases.append('selector-bad-mode-'+repr(mode))
for key in PRODUCER_ROWS['public']:
    for mode in ['candidate','public']:
        changed=text.replace(PRODUCER_ROWS[mode][key], 'altered-'+PRODUCER_ROWS[mode][key])
        try: selected_producer(changed,mode)
        except AssertionError: pass
        else: raise AssertionError('altered producer binding accepted: '+key)
        selector_cases.append('selector-altered-'+mode+'-'+key)
checks=0
assertion_cases=[]
def execute(code,env,should_pass):
    global checks
    previous=os.environ.copy()
    os.environ.update(env)
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
with tempfile.TemporaryDirectory() as directory:
    path=Path(directory); env['RUNNER_TEMP']=directory
    for mode in ['candidate','public']:
        env.update(selected_producer(text,mode))
        run={'id':int(env['PRODUCER_RUN']),'head_sha':env['PRODUCER_SOURCE'],'conclusion':'success','path':'.github/workflows/release.yml'}
        artifact={'id':int(env['PRODUCER_ARTIFACT']),'expired':False,'size_in_bytes':int(env['PRODUCER_ARCHIVE_SIZE_BYTES']),'digest':'sha256:'+env['PRODUCER_ARCHIVE_SHA256'],'workflow_run':{'id':run['id'],'head_sha':run['head_sha']},'name':'rendering-source-candidate-'+run['head_sha']+'-0.32.1'}
        def metadata(r,a,success):
            (path/'rendering-run.json').write_text(json.dumps(r)); (path/'rendering-artifact.json').write_text(json.dumps(a)); execute(codes[1],env,success)
        metadata(run,artifact,True)
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
                        'name':'rendering-source-candidate-'+mixed_run['head_sha']+'-0.32.1'}
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
        assert receipt['producer']=={name:env[key] for name,key in [('revision','PRODUCER_SOURCE'),('run','PRODUCER_RUN'),('artifact','PRODUCER_ARTIFACT'),('archiveSha256','PRODUCER_ARCHIVE_SHA256'),('custodySha256','PRODUCER_CUSTODY_SHA256')]}
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
    env={**os.environ,'PATH':directory+os.pathsep+os.environ['PATH'],'NPM_FIXTURE_STATE':str(state)}
    assert subprocess.run(['bash','-euo','pipefail','-c',provision],env=env,check=False).returncode==0
    state.write_text('11.19.1')
    assert subprocess.run(['bash','-euo','pipefail','-c',provision.replace('npm install --global npm@12.1.0','true')],env=env,check=False).returncode!=0
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
    previous=os.environ.copy();os.environ['RUNNER_TEMP']=directory
    try:
        for count in [186,185,187,0]:
            log.write_text('build diagnostics\n'+'PASS assertion\n'*count+' PASS indented\nPASS\twrong delimiter\n')
            try: exec(compile(provider_code,'actual-provider-count','exec'),{})
            except AssertionError: assert count!=186
            else: assert count==186
        log.unlink()
        try: exec(compile(provider_code,'actual-provider-count','exec'),{})
        except FileNotFoundError: pass
        else: raise AssertionError('missing Provider evidence accepted')
        binary=path/'dotnet';binary.write_text('#!/usr/bin/env bash\nexit 7\n');binary.chmod(0o700)
        env={**os.environ,'PATH':directory+os.pathsep+os.environ['PATH']}
        result=subprocess.run(['bash','-euo','pipefail','-c',provider_prefix],env=env,text=True,capture_output=True)
        assert result.returncode==7 and 'ProviderComposition: verified' not in result.stdout, 'failed Provider command must stop before count'
    finally: os.environ.clear();os.environ.update(previous)
print('PASS actual stdlib Provider count186;185/187/empty/missing evidence refused; native command exit7 preserved')

# Execute the actual final receipt binder, including its report reads and writeback.
# A good receipt must describe all eight cases in each of the three families.
for mode in ['candidate','public']:
    with tempfile.TemporaryDirectory() as directory:
        path=Path(directory); evidence=path/'external-reference'; evidence.mkdir()
        templates={'revision':'a'*40,'tree':'b'*40}
        (path/'external-reference-preflight.json').write_text(json.dumps({'templates':templates}))
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
                'passedPerFamily':8,'skipped':0,'browserReportSha256':reports}
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
                assert bound=={**candidate,'nativePreflight':{'templates':templates}}
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
        print(f'PASS actual final receipt binder: valid8 per family; {len(negatives)+1} negative receipts refused without writeback')

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
