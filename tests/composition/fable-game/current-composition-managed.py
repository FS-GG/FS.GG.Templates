#!/usr/bin/env python3
"""Held fixed DOM consumer of existing managed primitives; no local supervisor."""
import sys
sys.dont_write_bytecode=True
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import time

HERE=Path(__file__).resolve().parent
ADMISSION=None
BUDGET={'setup':720,'build':660,'browser':180,'collection':120,'cleanup':30,'overhead':90}
READER_SHA='42acc6b7953fd8044b2f839813ea45487e29322dffccf29dda088f84f6bda940'
D5_SHA='8222c8cf338fcdccf4dc01807b61d358381d5e6e130853fb16a1c387f9813891'
WORKFLOW='FS-GG/FS.GG.Templates/.github/workflows/current-reference-composition.yml@refs/heads/main'


def require(ok,message):
    if not ok:raise ValueError(message)


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path,value):
    raw=json.dumps(value,indent=2)+'\n';require(len(raw.encode())<=1048576,'metadata cap exceeded');Path(path).write_text(raw)


def load(name,path,expected=None):
    require(Path(path).is_file() and not Path(path).is_symlink(),'source dependency missing')
    if expected:require(sha(path)==expected,'source dependency seal differs')
    spec=importlib.util.spec_from_file_location(name,path);module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module


def dependencies():
    return (load('composition_outer',HERE/'retained-reference-rehearsal.py',READER_SHA),
            load('composition_collection',HERE/'d5-managed-runtime.py',D5_SHA))


def deadline(start,phase,now):
    sequence=('setup','build','browser');require(phase in sequence and start<=now,'phase/clock differs')
    end=min(now+BUDGET[phase],start+sum(BUDGET[key] for key in sequence[:sequence.index(phase)+1]))
    require(end>now,'original phase expired');return end


def manifest(directory):
    rows={}
    for path in sorted(Path(directory).rglob('*')):
        if path.is_file():
            require(not path.is_symlink() and len(rows)<20000,'member closure refused')
            rows[str(path.relative_to(directory))]={'bytes':path.stat().st_size,'sha256':sha(path)}
    require(rows,'empty member closure');return rows


def qualified_provider(caller,run,dotnet,root,workspace,config):
    project=workspace/'src/FS.GG.Templates.ProviderTool/FS.GG.Templates.ProviderTool.fsproj';artifacts=root/'validator-artifacts'
    run(caller['provider_tool_restore_argv'](dotnet,project,config)+['--artifacts-path',str(artifacts),'-m:1'],root,inputs=[project])
    run(caller['provider_tool_build_argv'](dotnet,project)+['--artifacts-path',str(artifacts),'--disable-build-servers','-m:1'],root,inputs=[project])
    folder=artifacts/'bin/FS.GG.Templates.ProviderTool/release';core=folder/'FS.GG.Templates.ProviderTool.dll'
    require(core.is_file() and (folder/'FS.GG.Templates.ProviderTool.deps.json').is_file() and (folder/'FS.GG.Templates.ProviderTool.runtimeconfig.json').is_file(),'typed output closure absent')
    write(root/'provider-member-identities.json',manifest(folder))
    value=run([dotnet,str(core),'current-composition-plan'],root,inputs=[core]);require(len(value.encode())<=32768,'typed plan exceeded')
    plan=json.loads(value);write(root/'current-composition-plan.json',plan)
    return core,plan


def source_arguments(bash,root,workspace,plan,template):
    return [bash,str(workspace/'tests/composition/fable-game/verify-external-reference-candidate.sh'),str(root/'absent-rendering-source'),str(root/'public-feed'),plan['rendering']['version'],str(root/'product'),plan['rendering']['sourceCommit'],'current-public-composition',str(template),plan['template']['sha256'],'current-source-stage']


# Closed metadata/log inventory: no packages, SDKs, browser assets or recursive trees.
PRODUCT_EVIDENCE=(
    'NuGet.Config','current-composition-plan.json','template-package-input.json',
    'producer-package-input.json','producer-archives.json','producer-source-entries.json',
    'template-generated-independent.json','current-source-stage.json','feed/public-readback.json',
    'template-typed-identity.log','template-install.log','complete-generate.log','player-generate.log',
    'current-composition-receiver.log','public-locked-restore.log','receiver-restore.log',
    'fable-restore.log','fable-build.log','fable-version.log','npm-client.log','npm-browser.log',
    'vite-build.log','public-codec-build.log','public-studio-build.log','public-tactical-build.log',
    'public-player-restore.log','server-restore.log','server-publish.log',
    'complete/global.json','complete/Directory.Build.props','complete/Directory.Packages.props',
    'complete/NuGet.Config','complete/.config/dotnet-tools.json',
    'complete/SvgFoundation/SvgFoundation.fsproj','complete/SvgFoundation/packages.lock.json',
    'complete/SvgFoundation/obj/project.assets.json',
    'complete/Browser.Tests/current-composition.generated.config.ts',
    'complete/Browser.Tests/package.json','complete/Browser.Tests/package-lock.json',
    'complete/Browser.Tests/playwright.config.ts','complete/Browser.Tests/two-client.spec.ts',
    'complete/Browser.Tests/external-command-outcomes.spec.ts',
    'complete/SvgFoundation/ExternalAuthorityReference.fs','complete/SvgFoundation/PlayerInput.fs',
    'complete/SvgFoundation/Examples/FourD/LocalSaveReplayExample.fs',
    'complete/SvgFoundation/Examples/FourD/LocalSaveReplayExample.TestEntry.fs',
    'complete/SvgFoundation/Examples/FourD/LocalSaveReplayExample.Tests.fs',
    'complete/SvgFoundation/Examples/ExternalAuthority/reference.json',
    'complete/SvgFoundation/Examples/FourD/reference.json',
    'complete/Server/Server.fsproj','complete/Server/packages.lock.json',
    'complete/Server/obj/project.assets.json',
    'player/SvgFoundation/packages.lock.json','player/SvgFoundation/obj/project.assets.json',
    'complete/Client/package.json','complete/Client/package-lock.json')


def evidence_inventory(root):
    names=('attempt.json','source-seals.json','managed-receipts.json','unit.json',
           'provider-member-identities.json','current-composition-plan.json',
           'fable-member-identities.json','node-native-closure.json','browser-native-closure.json',
           'input-downloads.json','executable-identities.json','game-public-observation.json','NuGet.Config',
           'browser-archive-inputs.json','browser-extracted-layouts.json',
           'browser-registration.json','browser-host-validation.json')
    names += tuple(family+'-'+kind+'.json' for family in ('chromium','firefox','webkit') for kind in ('list','report'))
    selected=[name for name in names if (root/name).exists()]
    selected += ['product/'+name for name in PRODUCT_EVIDENCE if (root/'product'/name).exists()]
    require(len(selected)<=128,'closed evidence population exceeded')
    total=0
    for name in selected:
        path=root/name
        require(not any(parent.is_symlink() for parent in (path,*path.parents)) and path.is_file(),'evidence path refused')
        size=path.stat().st_size;require(size<=16777216,'evidence member cap exceeded');total+=size
    require(total<=100663296,'evidence total cap exceeded')
    return sorted(set(selected))


def finish_composition(reader,contract,root,summary,receipts,primary,start):
    deciding=primary
    def protected(label,operation):
        nonlocal deciding
        try:return operation()
        except BaseException as error:
            message=(label+': '+type(error).__name__+': '+str(error))[:8192]
            summary.update(disposition='failed',executionDisposition='failed')
            if deciding is None:
                deciding=error;summary['firstCause']=message
            else:
                summary['additionalFailures'].append(message);deciding.add_note(message)
            print(message,file=sys.stderr)
    protected('managed receipt index',lambda:write(root/'managed-receipts.json',receipts))
    def collect():
        summary['seconds']=time.monotonic()-start
        write(root/'attempt.json',summary)
        write(root/'d5-evidence-inputs.json',evidence_inventory(root))
        result=reader.collect(root,min(time.monotonic()+120,start+1770),contract)
        require(not result['failures'],'composition collection incomplete')
    protected('composition reporting/collection',collect)
    summary['collectionDisposition']='Unknown'
    protected('terminal collection report Unknown',lambda:reader.collection_terminal(root,summary,contract))
    if primary is None and deciding is not None:raise deciding


def retain_raw(source,target):
    require(not source.is_symlink() and source.is_file(),'raw report missing or symlink')
    require(not any(parent.is_symlink() for parent in source.parents),'raw report ancestor refused')
    require(source.stat().st_size<=16777216,'raw report cap exceeded')
    target.write_bytes(source.read_bytes())


def browser_sequence(caller,run,node,root,env,plan,observations):
    tests=root/'product/complete/Browser.Tests';results={}
    for family in plan['browsers']['families']:
        require(family in ('chromium','firefox','webkit'),'browser evidence family differs')
        listed=caller['managed_playwright'](run,node,tests,family,env,list_only=True,config='current-composition.generated.config.ts')
        require(len(listed.encode())<=16777216,'listing cap exceeded')
        (root/(family+'-list.json')).write_text(listed)
        listing=json.loads(listed);observations.validate_listing(listing,plan,family)
        report_path=tests/'test-results/browser.json'
        # Clear only the previous family's fixed report; never attribute stale bytes.
        if report_path.exists():
            require(report_path.is_file() and not report_path.is_symlink(),'previous raw report refused');report_path.unlink()
        primary=None
        try:
            caller['managed_playwright'](run,node,tests,family,env,config='current-composition.generated.config.ts')
        except BaseException as error:
            primary=error;raise
        finally:
            try:
                if report_path.exists():retain_raw(report_path,root/(family+'-report.json'))
            except BaseException as error:
                if primary is None:raise
                primary.add_note(('raw report retention: '+str(error))[:8192])
        report=json.loads((root/(family+'-report.json')).read_text());observations.validate_report(report,plan,family)
        results[family]={'passed':len(plan['browsers']['cases']),'retries':0}
    return results


def run_composition(reader,collection,contract,environ):
    source=reader.validate_admission(environ,ADMISSION,contract);workspace=HERE.parents[2]
    require(Path(environ['GITHUB_WORKSPACE'])==workspace,'checkout differs')
    initial=reader.operational_start(environ,contract);root=Path(environ['RUNNER_TEMP'])/('current-composition-'+environ['RUN_ID']+'-1')
    reader.normalized_roots(root,workspace);reader.no_global_before_create(root)
    caller=reader.load_file('composition_actual_caller',HERE/'wasm-installed-c.py').actual_caller()
    env=caller['fresh_environment'](root,environ);env.update(UNIT_NAME=environ['UNIT_NAME'],PRIVATE_ROOT=str(root),GIT_CONFIG_NOSYSTEM='1')
    start=reader.original_clock(environ,initial['boot'],contract)['startedMonotonic'];receipts=[];identities={};inventory=[]
    summary={'schema':'fsgg.current-composition-managed/1','source':source,'disposition':'failed','executionDisposition':'started','firstCause':None,'additionalFailures':[],'phases':{},'runtimeCases':0,'durableSaveAcceptance':False,'actualAT':False,'whole4818Acceptance':False,'completeCompositionAcceptance':False,'actualProducerCustodyReadback':False}
    source_paths=[HERE/'current-composition-managed.py',HERE/'current-composition-observations.py',HERE/'retained-reference-rehearsal.py',HERE/'d5-managed-runtime.py',HERE/'wasm-installed-c.py',HERE/'verify-external-reference-candidate.sh',workspace/'.github/workflows/fable-reference-public.yml']
    provider=workspace/'src/FS.GG.Templates.ProviderTool'
    source_paths+=list(provider.glob('*.fs'))+[provider/'FS.GG.Templates.ProviderTool.fsproj',provider/'packages.lock.json']
    source_paths += [workspace/name for name in ('global.json','Directory.Build.props','Directory.Packages.props') if (workspace/name).is_file()]
    primary=None
    try:
        write(root/'source-seals.json',{str(path.relative_to(workspace)):sha(path) for path in source_paths})
        setup=deadline(start,'setup',time.monotonic());owner=caller['load_owner'](root,setup);caller['probe_containment'](owner,root)
        def transport(phase,until):
            execute=collection.managed_transport(caller,owner,root,until,identities,{'setup':'setup','build':'generation','browser':'backend'}[phase],receipts)
            return lambda argv,cwd,custom=None,inputs=():execute(argv,cwd,env if custom is None else custom,inputs=inputs)
        run=transport('setup',setup)
        expected={'TasksMax':'512','MemoryMax':str(8*1073741824),'MemorySwapMax':'0','RuntimeMaxUSec':'30min','Delegate':'yes','NoNewPrivileges':'yes','KillMode':'control-group'}
        write(root/'unit.json',reader.unit_properties(caller,run,env,identities,initial,expected));reader.acquisition_capacity(owner,root,initial)
        tools=root/'tools';tools.mkdir();downloads=root/'downloads';downloads.mkdir();acquisitions=[]
        get=caller['acquirer'](root,downloads,caller['download'],setup,acquisitions)
        def sdk_get(name,url,expected,maximum,algorithm='sha256'):
            reader.verify_sdk_selection(name,url,expected,maximum,algorithm);path=get(name,url,expected,maximum,algorithm)
            if name=='dotnet-releases.json':reader.sdk_metadata(path.read_bytes())
            return path
        dotnet=str(caller['provision_sdk'](sdk_get,tools,setup));env.update(DOTNET_ROOT=str(tools/'dotnet'),DOTNET_HOST_PATH=dotnet)
        caller['bind_identity'](identities,dotnet,'verified-archive-member');reader.native_closure(caller,run,root,tools,env,identities)
        require(run([dotnet,'--version'],root).strip()==caller['TOOLS']['sdk'],'SDK version differs')
        node_root,bin_root=caller['provision_node_npm'](get,tools,setup);node=os.path.realpath(node_root/'bin/node')
        env['PATH']=str(bin_root)+':'+str(node_root/'bin')+':'+str(tools/'dotnet')+':/usr/bin:/bin'
        node_identity=caller['bind_identity'](identities,node,'verified-archive-member');_,shell_sha=caller['host_image']('/bin/sh')
        caller['bind_identity'](identities,str(bin_root/'npm'),'caller-authored',images=[shell_sha,node_identity['sha256']])
        ldd,_=caller['host_image']('/usr/bin/ldd');interpreter=Path(ldd).read_text().splitlines()[0]
        require(interpreter.startswith('#!'),'host ldd interpreter unknown');_,image=caller['host_image'](interpreter[2:].strip().split()[0])
        caller['bind_identity'](identities,ldd,'host-observed',images=[image]);node_ldd=run([ldd,node],root)
        require(not any(caller['parse_ldd'](node_ldd,[Path(node)]).values()),'Node host dependencies missing');write(root/'node-native-closure.json',{'ldd':node_ldd,'nodeSha256':sha(node)})
        require(run([node,'--version'],root).strip()=='v'+caller['TOOLS']['node'],'Node version differs')
        require(run([str(bin_root/'npm'),'--version'],root).strip()==caller['TOOLS']['npm'],'npm version differs')
        config=caller['closed_nuget_config'](root);run(caller['fable_install_argv'](dotnet,tools,config),root)
        cores=[path for path in (tools/'fable').rglob('*.dll') if sha(path)==caller['FABLE_SHA']];require(len(cores)==1,'Fable core hash differs')
        write(root/'fable-member-identities.json',manifest(cores[0].parent));env.update(FSGG_COMPOSITION_FABLE_MEMBERS=str(root/'fable-member-identities.json'),FSGG_COMPOSITION_FABLE_SHA=caller['FABLE_SHA']);require(caller['TOOLS']['fable'] in run([dotnet,str(cores[0]),'--version'],root,inputs=[cores[0]]),'Fable version differs')
        core,plan=qualified_provider(caller,run,dotnet,root,workspace,config)
        row=plan['template'];template=get('template','https://api.nuget.org/v3-flatcontainer/'+row['id'].lower()+'/'+row['version']+'/'+row['id'].lower()+'.'+row['version']+'.nupkg',row['sha256'],8388608)
        # Existing stock browser source validation expects this acquirer's template role.
        feed=root/'public-feed';feed.mkdir()
        for row in plan['rendering']['packages']:
            version=plan['rendering']['version'];name=row['id']+'.'+version+'.nupkg'
            path=get(name,'https://api.nuget.org/v3-flatcontainer/'+row['id'].lower()+'/'+version+'/'+name.lower(),row['sha256'],33554432)
            (feed/name).write_bytes(path.read_bytes())
        seed=caller['seed_from_package'](template,root/'npm-seed',setup)
        env.update(FSGG_WASM_NPM_CACHE=str(root/'npm-cache'),npm_config_cache=str(root/'npm-cache'),PLAYWRIGHT_BROWSERS_PATH=str(root/'browsers'))
        for role in ('Client','Browser.Tests'):run([str(bin_root/'npm'),'ci','--ignore-scripts','--no-audit','--no-fund','--cache',env['FSGG_WASM_NPM_CACHE']],seed/role)
        registered,host_validation=caller['register_browsers'](root,downloads,seed,env,run,get,setup)
        # Preserve the maintained selected Chromium library supplement.
        support=caller['chromium_library_scan'](root,env,owner,identities,receipts,registered,setup)
        require(host_validation['state']=='stock-host-validation-passed-runtime-pending' and all(row['disposition']=='support-complete' for row in support.values()),'browser native closure unqualified')
        write(root/'browser-native-closure.json',{'stock':host_validation,'chromium':support})
        write(root/'input-downloads.json',acquisitions);write(root/'executable-identities.json',identities)
        summary['phases']['setup']='passed';build=deadline(start,'build',time.monotonic());run=transport('build',build)
        bash,_=caller['host_image']('/bin/bash');caller['bind_identity'](identities,bash,'host-observed')
        env.update(FSGG_REFERENCE_PROVIDER_TOOL_DLL=str(core),FSGG_CURRENT_COMPOSITION_ADMISSION=ADMISSION)
        run(source_arguments(bash,root,workspace,plan,template),root,inputs=[core,HERE/'verify-external-reference-candidate.sh',HERE/'current-composition-observations.py'])
        require(json.loads((root/'product/current-source-stage.json').read_text())['disposition']=='source-passed','source stage incomplete')
        game=plan['game'];game_archive=root/'product/complete/.nuget/packages'/game['id'].lower()/game['version']/(game['id'].lower()+'.'+game['version']+'.nupkg')
        require(game_archive.is_file(),'selected Game archive absent')
        import xml.etree.ElementTree as ET
        with reader.zip_inputs(caller,game_archive,build) as archive:
            reader.package_identity(archive,game['id'],game['version'])
            nuspecs=[name for name in archive.namelist() if name.endswith('.nuspec')];require(len(nuspecs)==1,'Game metadata census differs')
            repositories=[node for node in ET.fromstring(archive.read(nuspecs[0])).iter() if node.tag.rsplit('}',1)[-1]=='repository']
            require(len(repositories)==1,'Game producer source absent');observed_source=repositories[0].attrib.get('commit')
            require(re.fullmatch(r'[0-9a-f]{40}',observed_source or ''),'Game producer commit malformed')
        write(root/'game-public-observation.json',{'selected':game,'rawArchiveSha256':sha(game_archive),'sourceCommit':observed_source,'basis':'selected signed-lock content identity plus actual raw/NuSpec observation; independent producer receipt still required for acceptance'})
        summary['phases']['build']='passed';browser=deadline(start,'browser',time.monotonic());run=transport('browser',browser)
        observations=load('composition_observations',HERE/'current-composition-observations.py')
        summary['families']=browser_sequence(caller,run,node,root,env,plan,observations)
        summary.update(disposition='dom-observed-producer-custody-reference-only',executionDisposition='dom-cases-complete',runtimeCases=sum(row['passed'] for row in summary['families'].values()))
        summary['phases']['browser']='passed'
    except BaseException as error:
        primary=error;summary.update(disposition='failed',executionDisposition='failed',firstCause=(type(error).__name__+': '+str(error))[:8192]);raise
    finally:
        finish_composition(reader,contract,root,summary,receipts,primary,start)
    return summary


def main(argv=None):
    args=sys.argv[1:] if argv is None else argv
    require(len(args)==1 and args[0] in ('--check-admission','--outer-preflight','--record-client-exit','--post-unit','--run'),'closed composition mode required')
    require(ADMISSION is not None,'HELD: composition admission None; runtime unqualified')
    reader,collection=dependencies();contract=reader.caller_contract('composition',ADMISSION)
    reader.validate_admission(os.environ,ADMISSION,contract)
    if args==['--check-admission']:return
    if args==['--outer-preflight']:reader.outer_preflight(os.environ,contract)
    elif args==['--record-client-exit']:reader.record_client_exit(os.environ,contract)
    elif args==['--post-unit']:reader.post_unit(os.environ,contract)
    else:run_composition(reader,collection,contract,os.environ)


if __name__=='__main__':
    try:main()
    except (ValueError,KeyError,OSError,TypeError) as error:print(str(error),file=sys.stderr);raise SystemExit(3)
