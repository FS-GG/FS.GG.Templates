#!/usr/bin/env python3
"""Held D5 consumer of the canonical managed owner; this file is not a supervisor.

Transport decisions concern process receipts only. ProviderTool remains the sole
receiver/backend policy owner. Current source holds every runtime CLI mode before effects.
"""
import sys
sys.dont_write_bytecode = True
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path
import re
import stat
import time

HERE = Path(__file__).resolve().parent
# Original6377028965 admission is retired. This successor source binding is not actual runtime selection.
ADMISSION = 'https://github.com/FS-GG/.github/issues/4849#issuecomment-6378268333'
ADMITTED_SCOPE = 'rehearsal' # First operation only; full43 needs a separate source admission.
# Closed D5 naming in the existing retained controller; no globals mutation or
# controller copy. This source selection is not runtime admission.
OUTER_CALLER_CONTRACT = 'd5'
WORKFLOW = 'FS-GG/FS.GG.Templates/.github/workflows/svg-release-d5-current-public.yml@refs/heads/main'
READER = {'baseRevision': '1d832f2214147065bb56e0afd76d600ed01bd27d',
          'path': 'tests/composition/fable-game/retained-reference-rehearsal.py',
          'baseSha256': '4e4fb76333804a3f16c36ef16ae1fd8aac165fae6b5cf8492157f87f18dcfd43',
          'sha256': '39f1e667d967e9a9cdc974d1f6ff30bfb76c299f1c5b483cdb115307ecc8e528'}
OWNER = {'revision': 'ac22206560f3eddfea524ce8f752ff1d0dfeec4e',
         'path': 'eng/managed_group_owner.py', 'bytes': 45315,
         'sha256': 'd846dbe158befb5b824bd94a5bc0bb89b1145f825d5d6fa3a3225fa0451a36c0'}
# The supplied acquisition and canonical build receipts were inspected, not run.
GO = {'url': 'https://go.dev/dl/go1.24.1.linux-amd64.tar.gz',
      'sha256': 'cb2396bae64183cdccf81a9a6df0aea3bce9511fc21469fb89a0c00470088073',
      'maximumBytes': 134217728}
LMT = {'sourceSha256': '88bc47acae2c26919ab96a5cafa80b12fac762092c57840a2baad1afcc7feda3',
       'sha256': '37e0b0365c2641edce40b48605471f61fa12e97c3e2376152f0e849abdc31f10',
       'ldflags': '-buildid=IvXAt1kJ-3iINki1alCT/Ut12KGabgkWIkwVpw-xO/c4zkZMLAubfWHvjZOY8o/8-oR_8tNNndNgfMVoD8F -B 0x03d1703027f57ed4dd2ba90b7cdfc8cdea2815da'}
BUDGET = {'setup': 720, 'generation': 360, 'backend': 480,
          'collection': 120, 'cleanup': 30, 'overhead': 90}
UNIT = {'CPUQuota': '200%', 'MemoryMax': '8G', 'MemorySwapMax': '0',
        'TasksMax': '512', 'RuntimeMaxSec': '1800', 'TimeoutStopSec': '5',
        'Delegate': 'yes', 'NoNewPrivileges': 'yes', 'KillMode': 'control-group'}
SOURCE_KEYS = ('EVENT', 'REPOSITORY', 'REF', 'SHA', 'ADMITTED_REF', 'CHECKOUT_HEAD',
               'WORKFLOW_REF', 'WORKFLOW_SHA', 'RUN_ID', 'RUN_ATTEMPT', 'UNIT_NAME', 'ADMISSION')


def require(value, message):
    if not value:
        raise ValueError(message)


def unique(pairs):
    result = {}
    for key, value in pairs:
        require(key not in result, 'duplicate receipt property')
        result[key] = value
    return result


def read_json(path, maximum=131072):
    path = Path(path)
    require(path.is_file() and not path.is_symlink() and path.stat().st_size <= maximum,
            'bounded regular receipt required')
    return json.loads(path.read_text(), object_pairs_hook=unique)


def sha(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1048576), b''):
            digest.update(block)
    return digest.hexdigest()


def admission_join(env, selected):
    """Pure source-join control through the existing parameterized reader."""
    require(selected is not None, 'HELD: runtime admission None; retirement unqualified')
    reader=load_reader(HERE.parents[2])
    return reader.validate_admission(env,selected,reader.caller_contract('d5',selected))


def runtime_scope(environ):
    require(environ.get('SCOPE') == ADMITTED_SCOPE, 'source admission permits rehearsal only; full matrix remains separately pending')
    return ADMITTED_SCOPE


def phase_deadline(start, phase, now):
    phases = ('setup', 'generation', 'backend')
    require(phase in phases and all(type(v) in (int, float) and math.isfinite(v) for v in (start, now)), 'invalid original phase')
    require(0 <= start <= now, 'original phase clock differs')
    cap = start + sum(BUDGET[p] for p in phases[:phases.index(phase) + 1])
    deadline = min(now + BUDGET[phase], cap)
    require(deadline > now, 'original phase deadline expired')
    return deadline


def load_reader(workspace):
    """Read-only immutable dependency. Its4816 product/controller entry is never called."""
    workspace = Path(workspace).resolve()
    path = workspace / READER['path']
    require(path.is_file() and not path.is_symlink() and sha(path) == READER['sha256'], 'reviewed repaired capacity reader dependency unavailable')
    spec = importlib.util.spec_from_file_location('d5_canonical_capacity_reader', path)
    reader = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(reader)
    return reader


def managed_transport(caller, owner, root, deadline, identities, phase, receipts):
    """Use the existing executor unchanged; no local fork/kill/wait/supervision."""
    require(phase in ('setup', 'generation', 'backend'), 'closed D5 phase required')
    require(getattr(owner, 'OWNER_SHA256', None) == OWNER['sha256'], 'managed owner identity differs')
    # Existing phase tags select receipt names only; D5 retains its original deadline.
    tag = {'setup': 'setup', 'generation': 'custody', 'backend': 'installed'}[phase]
    return caller['managed_executor'](owner, root, deadline, identities, tag, receipts)


def refusal_receipt(owner, receipt, directory, argv, cwd, env):
    """Authenticate a genuine managed command failure, retaining its failed outcome.

    This establishes only the expected positive-nonzero *transport* result. The
    original actual JSON and owner snapshots still require F# backend validation.
    """
    require(receipt.get('schema') == 'fsgg.managed-group-receipt/1'
            and receipt.get('contract') == 'fsgg.managed-group-contract/1', 'wrong process receipt')
    require(receipt.get('owner', {}).get('sha256') == OWNER['sha256']
            and receipt['owner'].get('path') == owner.OWNER_PATH, 'receipt owner differs')
    require(read_json(Path(directory) / 'receipt.json') == receipt, 'original process receipt differs')
    profile = receipt['profile']
    _, digest = owner.validate_profile(profile)
    require(receipt.get('profileSha256') == digest and profile['argv'] == argv
            and profile['cwd'] == str(cwd) and profile['environmentKeys'] == sorted(env), 'command/profile join differs')
    require(profile['executable']['path'] == os.path.realpath(argv[0]), 'receipt executable differs')
    require(str(Path(directory).resolve()) == str(Path(directory))
            and Path(directory).is_relative_to(Path(profile['root']))
            and Path(cwd).is_relative_to(Path(profile['root'])), 'receipt root/directory differs')
    require(re.fullmatch(r'[0-9a-f]{32}',receipt.get('invocationId','')) and isinstance(receipt.get('bootId'),str) and receipt['bootId'], 'original invocation/boot missing')
    leader=receipt.get('leader') or {}
    require(all(type(leader.get(k)) is int and leader[k]>0 for k in ('pid','start','pidfdInode'))
            and leader.get('image')=='admitted' and leader.get('imageSha256') in profile['leaderImages']
            and leader.get('noNewPrivileges')=='1' and leader.get('cmdline')==argv, 'refusal leader birth/image unqualified')
    require(receipt.get('launch', {}).get('attempted') is True and receipt.get('launch', {}).get('launched') is True, 'refusal command was not launched')
    require(profile['retirement']['onLeaderExit'] == 'require-empty', 'wrong retirement policy')
    require(profile['containment'] == 'cgroup2-delegated', 'wrong containment policy')
    exit_value = receipt.get('exit') or {}
    code = exit_value.get('code')
    require(type(code) is int and 0 < code <= 255 and exit_value.get('signal') is None, 'expected positive nonzero exit required')
    require(receipt.get('outcome') == 'failed' and receipt.get('refusal') is None
            and receipt.get('firstCause') == 'RuntimeError: command failed with exit ' + str(code)
            and receipt.get('additionalFailures') == [], 'non-command failure cannot be expected refusal')
    require(receipt.get('cleanup') == 'observed-empty-removed' and receipt.get('custody') == 'contained'
            and receipt.get('escaped') == [] and receipt.get('residualInRoot') == [], 'refusal process retirement unqualified')
    retirement = receipt.get('retirement') or {}
    require(retirement.get('leaderReaped') is True and retirement.get('leafRemoved') is True
            and retirement.get('populatedAfter') is False, 'refusal process not reaped/removed')
    require(isinstance(receipt.get('createdCgroups'),list) and all(row.get('removed') is True for row in receipt['createdCgroups']), 'created process group remains')
    for name in ('stdout', 'stderr'):
        stream = receipt.get('streams', {}).get(name, {})
        path = Path(directory) / (name + '.log')
        require(stream.get('eof') is True and stream.get('capped') is False and stream.get('sinkError') is None, 'refusal stream unqualified')
        require(path.is_file() and not path.is_symlink() and path.stat().st_size <= 16777216
                and path.stat().st_size == stream.get('bytes') and sha(path) == stream.get('sha256'), 'original refusal stream differs')
    return Path(directory) / 'stdout.log'


def wrong_profile(execute, owner, receipts, argv, sdd_core, typed_arguments, cwd, env):
    """Only the actual typed d5-refused plan may consume an expected nonzero."""
    require(isinstance(typed_arguments, list) and 0 < len(typed_arguments) <= 128
            and all(isinstance(v, str) for v in typed_arguments), 'bounded typed refusal argv required')
    require(len(argv) >= 3 and argv[1] == str(sdd_core) and argv[2:] == typed_arguments and typed_arguments[:2] == ['typed-sdd', 'author']
            and '--backend' not in typed_arguments, 'typed refusal argv differs')
    require(typed_arguments.count('--work') == 1 and typed_arguments.index('--work') + 1 < len(typed_arguments)
            and typed_arguments[typed_arguments.index('--work') + 1] == 'd5-refused', 'wrong refusal work')
    require(Path(sdd_core).is_absolute() and Path(sdd_core).is_file() and not Path(sdd_core).is_symlink(), 'regular installed SDD core required')
    core_hash = sha(sdd_core)
    previous = len(receipts)
    try:
        execute(argv, cwd, env, inputs=[Path(sdd_core)])
    except RuntimeError as failure:
        cause = failure.__cause__
        require(not getattr(failure,'__notes__',[]) and not getattr(cause,'__notes__',[]), 'managed reporting failure cannot be expected refusal')
        require(isinstance(cause, owner.GroupFailed) and len(receipts) == previous + 1, 'not the original managed command failure')
        entry = receipts[-1]
        require(entry.get('status') == 'failed' and entry.get('executable') == os.path.realpath(argv[0])
                and entry.get('inputs', {}).get(str(sdd_core)) == core_hash and sha(sdd_core) == core_hash, 'managed index/input join differs')
        return refusal_receipt(owner, cause.receipt, entry['outDir'], argv, cwd, env)
    raise ValueError('wrong-profile author unexpectedly succeeded')


def sandbox_read(path, maximum=16384):
    """Closed callers only: bounded, read-only final object; never follow a file link."""
    fd=os.open(path,os.O_RDONLY|os.O_CLOEXEC|os.O_NOFOLLOW|os.O_NONBLOCK)
    try:
        data=bytearray()
        while True:
            block=os.read(fd,min(65536,maximum+1-len(data)))
            if not block:return bytes(data)
            data.extend(block)
            require(len(data)<=maximum,'optional parent observation byte cap exceeded')
    finally:os.close(fd)


def sandbox_prctl(option):
    # GET_DUMPABLE=3 / GET_SECUREBITS=27 only; no SET operation or executable.
    require(option in (3,27),'read-only parent prctl required')
    import ctypes
    libc=ctypes.CDLL(None,use_errno=True)
    result=libc.prctl(option,0,0,0,0)
    if result<0:raise OSError(ctypes.get_errno(),'read-only parent prctl failed')
    return result


def sandbox_image():
    path='/usr/bin/unshare';info=os.stat(path,follow_symlinks=False)
    require(stat.S_ISREG(info.st_mode),'regular unshare image required')
    body=sandbox_read(path,8388608);after=os.stat(path,follow_symlinks=False)
    require((info.st_dev,info.st_ino,info.st_size,info.st_mtime_ns)==
            (after.st_dev,after.st_ino,after.st_size,after.st_mtime_ns) and len(body)==info.st_size,
            'unshare image changed or was not completely read')
    value={'path':path,'resolved':os.path.realpath(path),'uid':info.st_uid,'gid':info.st_gid,
           'mode':oct(info.st_mode&0o7777),'bytes':info.st_size,
           'sha256':hashlib.sha256(body).hexdigest(),
           'version':'Unknown: binary hash alone does not establish util-linux version'}
    try:value['fileCapabilities']={'status':'observed','hex':os.getxattr(path,'security.capability').hex()}
    except OSError as error:value['fileCapabilities']={'status':'Unknown','reason':type(error).__name__+': '+str(error)[:512]}
    return value


def sandbox_parent_data(deadline):
    """Read current collector only. Never infer post-exec/post-CLONE child state."""
    started=time.monotonic();end=min(deadline,started+5)
    def observe(read):
        try:
            require(time.monotonic()<end,'optional parent observation deadline expired')
            value=read()
            require(time.monotonic()<=end,'optional parent observation deadline expired')
            return {'status':'observed','value':value}
        except Exception as error:
            return {'status':'Unknown','reason':type(error).__name__+': '+str(error)[:512]}
    result={'schema':'fsgg.d5.sandbox-parent/1','scope':'current D5 collector before literal probe',
            'childState':'Unknown: not post-exec/post-CLONE unshare state; no cause attribution',
            'startedMonotonic':started,'originalPhaseDeadline':deadline,
            'identity':observe(lambda:{'pid':os.getpid(),'ppid':os.getppid(),'uid':list(os.getresuid()),
                                      'gid':list(os.getresgid()),'groups':os.getgroups()}),
            'kernel':observe(lambda:list(os.uname())),
            'dumpable':observe(lambda:sandbox_prctl(3)),
            'securebits':observe(lambda:sandbox_prctl(27)),
            'unitObservation':'unit.json; unchanged canonical unit reader',
            'imageEnvironment':{k:os.environ.get(k,'Unknown: not propagated into unit')[:128]
                                for k in ('ImageOS','ImageVersion')},
            'unshareImage':observe(sandbox_image),'files':{},'namespaces':{},'procOwnership':{}}
    paths=('/proc/self/status','/proc/self/uid_map','/proc/self/gid_map','/proc/self/setgroups',
           '/proc/self/cgroup','/proc/self/attr/current','/proc/sys/fs/suid_dumpable',
           '/proc/sys/kernel/unprivileged_userns_clone','/proc/sys/user/max_user_namespaces',
           '/proc/sys/kernel/apparmor_restrict_unprivileged_userns',
           '/proc/sys/kernel/apparmor_restrict_unprivileged_unconfined',
           '/sys/kernel/security/lsm','/sys/module/apparmor/parameters/enabled',
           '/proc/sys/kernel/random/boot_id','/usr/lib/os-release')
    status_fields={'Uid','Gid','CapInh','CapPrm','CapEff','CapBnd','CapAmb','NoNewPrivs','Seccomp','NSpid','Groups'}
    def text(path):
        value=sandbox_read(path).decode('utf-8','strict')
        if path=='/proc/self/status':
            return {k:v.strip() for line in value.splitlines() if ':' in line
                    for k,v in [line.split(':',1)] if k in status_fields}
        return value
    for path in paths:result['files'][path]=observe(lambda path=path:text(path))
    for name in ('user','mnt','pid','net','cgroup'):
        result['namespaces'][name]=observe(lambda name=name:os.readlink('/proc/self/ns/'+name))
    for path in ('/proc','/proc/self','/proc/self/uid_map','/proc/self/ns/net'):
        def ownership(path=path):
            info=os.stat(path)
            return {'uid':info.st_uid,'gid':info.st_gid,'mode':oct(info.st_mode&0o7777),'device':info.st_dev,'inode':info.st_ino}
        result['procOwnership'][path]=observe(ownership)
    result['procMounts']=observe(lambda:[line for line in sandbox_read('/proc/self/mountinfo',65536).decode().splitlines()
                                        if ' - proc ' in line])
    return result


def optional_sandbox_parent(deadline):
    """Keep diagnostic failure/overflow secondary inside the canonical attempt JSON."""
    try:
        value=sandbox_parent_data(deadline)
        data=json.dumps(value,allow_nan=False)
        require(len(data.encode())<=131072,'optional parent metadata cap exceeded')
        return {'status':'observed','data':value}
    except Exception as error:
        return {'status':'Unknown','reason':type(error).__name__+': '+str(error)[:512],
                'childState':'Unknown; original probe/terminal collection remain authoritative'}


def probe_backend_sandbox(caller, run, identities, root):
    """Fixed SDD2.4 sandbox prerequisite, before asset acquisition; no host change."""
    unshare,unshare_sha=caller['host_image']('/usr/bin/unshare')
    true,true_sha=caller['host_image']('/usr/bin/true')
    require(unshare=='/usr/bin/unshare' and true=='/usr/bin/true','literal sandbox executable paths differ')
    caller['bind_identity'](identities,true,'host-observed')
    caller['bind_identity'](identities,unshare,'host-observed',images=[unshare_sha,true_sha])
    return run([unshare,'--user','--map-root-user','--net','--',true],root,{'LANG':'C.UTF-8','TZ':'UTC'})


def lmt_build_arguments(go, source, output):
    """Exact canonical file-build recipe; trimpath does not erase the basename."""
    source=Path(source)
    require(source.name=='main.go' and source.is_absolute() and Path(go).is_absolute()
            and Path(output).is_absolute(), 'canonical LMT paths required')
    return [str(go),'build','-trimpath','-ldflags',LMT['ldflags'],'-o',str(output),str(source)]


def write(path, value):
    data=json.dumps(value,indent=2)+'\n'
    require(len(data.encode())<=1048576,'D5 metadata cap exceeded')
    Path(path).write_text(data)


def finish_collection(reader, contract, root, summary, inventory, primary, start):
    collection_failure=None
    try:
        summary['seconds']=time.monotonic()-start;write(root/'attempt.json',summary)
        inventory += [str(p.relative_to(root)) for p in root.iterdir() if p.is_file() and p.suffix in ('.json','.log','.tsv','.yml') and p.name!='d5-evidence-inputs.json']
        write(root/'d5-evidence-inputs.json',sorted(set(inventory)))
        result=reader.collect(root,min(time.monotonic()+120,start+1770),contract)
        require(not result['failures'],'D5 collection incomplete')
    except BaseException as reporting:
        message=(type(reporting).__name__+': '+str(reporting))[:8192]
        if primary is None:
            collection_failure=reporting
            summary.update(disposition='failed',executionDisposition='failed',firstCause=message)
        else:
            summary['additionalFailures'].append('D5 reporting/collection: '+message)
            primary.add_note('additional D5 reporting/collection failure: '+message)
        print('D5 reporting/collection failure: '+message,file=sys.stderr)
    try:
        # Append a distinct terminal record/index entry; never rewrite the copied attempt.
        reader.collection_terminal(root,summary,contract)
    except BaseException as reporting:
        deciding=primary or collection_failure
        print('terminal collection report Unknown: '+str(reporting)[:8192],file=sys.stderr)
        if deciding is None:raise
        deciding.add_note('terminal collection report Unknown: '+str(reporting)[:8192])
    if collection_failure is not None:raise collection_failure


def run_d5(reader, contract, environ):
    """Fixed D5 sequence; every executable goes through the existing managed owner."""
    source=reader.validate_admission(environ,ADMISSION,contract)
    runtime_scope(environ)
    require(Path(environ['GITHUB_WORKSPACE'])==HERE.parents[2],'executing checkout differs')
    initial=reader.operational_start(environ,contract)
    root=Path(environ['RUNNER_TEMP'])/('current-d5-'+environ['RUN_ID']+'-1')
    reader.normalized_roots(root,HERE.parents[2]);reader.no_global_before_create(root)
    caller=reader.load_file('d5_actual_loader',HERE/'wasm-installed-c.py').actual_caller()
    env=caller['fresh_environment'](root,environ)
    env.update(UNIT_NAME=environ['UNIT_NAME'],PRIVATE_ROOT=str(root),GIT_CONFIG_NOSYSTEM='1')
    helper=reader.load_file('d5_observations',HERE/'d5-current-public.py')
    start=reader.original_clock(environ,initial['boot'],contract)['startedMonotonic']
    receipts=[]; summary={'schema':'fsgg.current-d5.managed-attempt/1','disposition':'failed','retirement':'unqualified',
                         'source':source,'scope':environ['SCOPE'],'executionDisposition':'started','firstCause':None,'additionalFailures':[],'phases':{}}
    selected=['d5-managed-runtime.py','d5-current-public.py','verify-svg-release-d5-current-public.sh','retained-reference-rehearsal.py','wasm-installed-c.py']
    write(root/'source-seals.json',{name:sha(HERE/name) for name in selected})
    inventory=['attempt.json','source-seals.json','pins.json','unit.json','input-downloads.json','executable-identities.json']
    primary=None
    try:
        runtime_scope(environ)
        require(len(environ['PUBLIC_PINS'].encode())<=65536,'pin input cap exceeded')
        pins=json.loads(environ['PUBLIC_PINS'],object_pairs_hook=unique)
        write(root/'pins.json',pins)
        setup=phase_deadline(start,'setup',time.monotonic())
        owner=caller['load_owner'](root,setup);caller['probe_containment'](owner,root)
        identities={};run=managed_transport(caller,owner,root,setup,identities,'setup',receipts)
        expected={'TasksMax':'512','MemoryMax':str(8*1073741824),'MemorySwapMax':'0','RuntimeMaxUSec':'30min','Delegate':'yes','NoNewPrivileges':'yes','KillMode':'control-group'}
        write(root/'unit.json',reader.unit_properties(caller,run,env,identities,initial,expected))
        reader.acquisition_capacity(owner,root,initial)
        # Match SDD2.4's literal launcher/arguments and cleared child environment.
        # Test the actual unchanged host before any SDK/Go/public asset acquisition.
        summary['sandboxParentObservation']=optional_sandbox_parent(setup)
        probe_backend_sandbox(caller,run,identities,root)
        # No sudo/sysctl or host profile mutation. An unavailable sandbox refuses.
        tools=root/'tools';tools.mkdir();downloads=root/'downloads';downloads.mkdir()
        acquisitions=[];get=caller['acquirer'](root,downloads,caller['download'],setup,acquisitions)
        def sdk_get(name,url,expected,maximum,algorithm='sha256'):
            reader.verify_sdk_selection(name,url,expected,maximum,algorithm)
            result=get(name,url,expected,maximum,algorithm)
            if name=='dotnet-releases.json':reader.sdk_metadata(result.read_bytes())
            return result
        dotnet=str(caller['provision_sdk'](sdk_get,tools,setup))
        env.update(DOTNET_ROOT=str(tools/'dotnet'),DOTNET_HOST_PATH=dotnet,PATH=str(tools/'dotnet')+':/usr/bin:/bin')
        caller['bind_identity'](identities,dotnet,'verified-archive-member')
        reader.native_closure(caller,run,root,tools,env,identities)
        require(run([dotnet,'--version'],root,env).strip()=='10.0.401','SDK selection differs')
        inputs={}
        for role,package in [('templates','FS.GG.Workspace.Template'),('overlay','FS.GG.Workspace.Template'),('sdd','FS.GG.SDD.Cli'),('wizard','FS.GG.NewSddWorkspace')]:
            row=helper.PINS[role];name=package+'.'+row['version']+'.nupkg'
            inputs[role]=get(name,'https://api.nuget.org/v3-flatcontainer/'+package.lower()+'/'+row['version']+'/'+name.lower(),row['sha256'],134217728)
            inventory.append(str(inputs[role].relative_to(root)))
        provider=get('provider.yml','https://raw.githubusercontent.com/FS-GG/FS.GG.Templates/'+helper.PINS['templates']['sourceCommit']+'/providers/fable-game.providers.yml',helper.PINS['templates']['providerSha256'],1048576)
        inventory.append(str(provider.relative_to(root)))
        config=caller['closed_nuget_config'](root)
        project=HERE.parents[2]/'src/FS.GG.Templates.ProviderTool/FS.GG.Templates.ProviderTool.fsproj'
        artifacts=root/'validator-artifacts'
        run(caller['provider_tool_restore_argv'](dotnet,project,config)+['--artifacts-path',str(artifacts),'-m:1'],root,env)
        run(caller['provider_tool_build_argv'](dotnet,project)+['--artifacts-path',str(artifacts),'--disable-build-servers','-m:1'],root,env)
        validator=artifacts/'bin/FS.GG.Templates.ProviderTool/release/FS.GG.Templates.ProviderTool.dll'
        require(validator.is_file(),'owned validator output missing')
        def check(args):return run([dotnet,str(validator),*args],root,env,inputs=[validator])
        check(['current-d5-pins-check','--pins',str(root/'pins.json')])
        # Check exact public identities before installation or generation.
        cores={}
        for role,package,command in [('sdd','FS.GG.SDD.Cli','fsgg-sdd'),('wizard','FS.GG.NewSddWorkspace','new-sdd-workspace')]:
            row=helper.PINS[role];common=['--archive',str(inputs[role]),'--package-id',package,'--version',row['version'],'--sha256',row['sha256'],'--source-revision',row['sourceCommit']]
            check(['published-tool-check',*common]);store=tools/role
            run([dotnet,'tool','install',package,'--version',row['version'],'--tool-path',str(store),'--configfile',str(config),'--add-source',str(downloads),'--no-cache'],root,env)
            core=Path(check(['installed-tool-check',*common,'--tool-root',str(store),'--command-name',command]).strip())
            require(core.is_relative_to(store/'.store') and core.is_file(),'installed tool core escaped store');cores[role]=core
        env['PATH']=str(tools/'sdd')+':'+env['PATH']
        row=helper.PINS['templates'];revision=row['sourceCommit']
        git,_=caller['host_image']('/usr/bin/git');caller['bind_identity'](identities,git,'host-observed')
        refs=run([git,'ls-remote','--tags','https://github.com/FS-GG/FS.GG.Templates.git','refs/tags/fs-gg-templates/v0.19.3','refs/tags/fs-gg-templates/v0.19.3^{}'],root,env)
        values={ref:value for value,ref in (line.split() for line in refs.splitlines())};tag='refs/tags/fs-gg-templates/v0.19.3'
        require(values.get(tag+'^{}',values.get(tag))==revision,'public tag revision differs')
        check(['reference-publication-check','--archive',str(inputs['templates']),'--descriptor',str(provider),'--template-version','0.19.3','--sha256',row['sha256'],'--source-revision',revision,'--tag-revision',revision,'--descriptor-sha256',row['providerSha256']])
        # Fixed official Go URL: no redirect, no mutable global allowlist extension.
        curl,_=caller['host_image']('/usr/bin/curl');caller['bind_identity'](identities,curl,'host-observed')
        goarchive=downloads/'go1.24.1.tar.gz'
        run([curl,'--proto','=https','--fail','--silent','--show-error','--max-time',str(max(1,int(setup-time.monotonic()))),'--max-filesize',str(GO['maximumBytes']),'--output',str(goarchive),'https://dl.google.com/go/go1.24.1.linux-amd64.tar.gz'],root,env)
        require(sha(goarchive)==GO['sha256'],'Go archive differs')
        caller['unpack_tar'](goarchive,tools/'go-unpacked',1073741824,setup)
        go=tools/'go-unpacked/go/bin/go';caller['bind_identity'](identities,str(go),'verified-archive-member')
        env.update(GOCACHE=str(root/'go-cache'),GOPATH=str(root/'go-path'),CGO_ENABLED='1',GO111MODULE='off')
        main=get('main.go','https://raw.githubusercontent.com/driusan/lmt/62fe18f2f6a6e11c158ff2b2209e1082a4fcd59c/main.go',LMT['sourceSha256'],1048576)
        lmt=tools/'lmt';run(lmt_build_arguments(go,main,lmt),root,env,inputs=[main])
        require(sha(lmt)==LMT['sha256'],'canonical LMT output differs')
        quint=get('quint','https://github.com/quint-co/quint/releases/download/v0.32.0/quint-linux-amd64','939b64095b706017f2f202c6f99c860c40be7c31bddc2b98557316e50f42cd7f',134217728);quint.chmod(0o700)
        write(root/'input-downloads.json',acquisitions);write(root/'executable-identities.json',identities)
        generation=phase_deadline(start,'generation',time.monotonic());run=managed_transport(caller,owner,root,generation,identities,'generation',receipts)
        # check closes over run, so all subsequent typed decisions use this phase.
        run([dotnet,'new','install',str(inputs['templates'])],root,env)
        raw=root/'raw-omitted';run([dotnet,'new','fs-gg-fable-game','-n','CurrentD5Raw','-o',str(raw)],root,env)
        check(['current-d5-receiver-check','--archive',str(inputs['templates']),'--receiver',str(raw),'--route','direct','--lifecycle','none','--bundle','omitted','--product-name','CurrentD5Raw'])
        inventory += [str(p.relative_to(root)) for p in raw.rglob('*') if p.is_file()]
        cases=check(['current-d5-cases','--scope',environ['SCOPE']]);(root/'cases.tsv').write_text(cases);inventory.append('cases.tsv')
        rows=[line.split('\t') for line in cases.splitlines()];require(len(rows)==(2 if environ['SCOPE']=='rehearsal' else 42) and all(len(row)==4 for row in rows),'typed D5 cases missing')
        for name,route,lifecycle,bundle in rows:
            destination=root/name;effective='typed-sdd' if lifecycle=='omitted' else lifecycle;product='D5'+name.replace('-','')
            if route=='provider':
                (destination/'.fsgg').mkdir(parents=True);(destination/'.fsgg/providers.yml').write_bytes(provider.read_bytes())
                args=['scaffold','--root',str(destination),'--provider','fable-game','--no-update','--json','--param','productName='+product]
                if lifecycle!='omitted':args+=['--param','lifecycle='+lifecycle]
                if bundle!='omitted':args+=['--param','bundle='+bundle]
                report=run([dotnet,str(cores['sdd']),*args],root,env,inputs=[cores['sdd']]);(root/(name+'.json')).write_text(report)
            else:
                hive=root/'hives'/name;hive.mkdir(parents=True);wizardenv={**env,'DOTNET_CLI_HOME':str(hive)}
                if effective=='typed-sdd':run([dotnet,'new','install',str(inputs['overlay'])],root,wizardenv)
                args=[str(destination),product,'--template','fable-game','--ref','fs-gg-templates/v0.19.3','--pinned','--no-governance','--no-coordination']
                if lifecycle!='omitted':args+=['--lifecycle',lifecycle]
                if bundle!='omitted':args+=['--bundle',bundle]
                run([dotnet,str(cores['wizard']),*args],root,wizardenv,inputs=[cores['wizard']])
                registry=hive/'.templateengine/packages.json';reader.template_registration(hive,root,'0.19.3',row['sha256'])
                (root/(name+'-registry.json')).write_bytes(registry.read_bytes())
            check(['current-d5-receiver-check','--archive',str(inputs['templates']),'--receiver',str(destination),'--route',route,'--lifecycle',effective,'--bundle',bundle,'--product-name',product])
            inventory += [str(p.relative_to(root)) for p in destination.rglob('*') if p.is_file() and not set(p.relative_to(destination).parts)&{'.git','.nuget','node_modules','bin','obj'}]
            require(len(set(inventory))<=20000,'D5 evidence file population exceeded')
        backend=phase_deadline(start,'backend',time.monotonic());run=managed_transport(caller,owner,root,backend,identities,'backend',receipts)
        cache=root/'quint-cache';run([dotnet,str(cores['sdd']),'typed-sdd','provision','--cache',str(cache),'--quint',str(quint),'--lmt',str(lmt)],root,env,inputs=[cores['sdd']])
        for name in ('provider-omitted','wizard-omitted'):
            destination=root/name;helper.extract_model(inputs['templates'],destination/'models/svg-arena')
            def author_args(work,bindings):return json.loads(check(['current-d5-author-args','--root',str(destination),'--work',work,'--cache',str(cache),'--bindings',bindings]))
            args=author_args('d5-default','models/svg-arena/arena-rules.bindings.json')
            authored=root/(name+'-author.json');authored.write_text(run([dotnet,str(cores['sdd']),*args],root,env,inputs=[cores['sdd']]))
            inspected=root/(name+'-inspect.json');inspected.write_text(run([dotnet,str(cores['sdd']),'typed-sdd','inspect','--root',str(destination),'--work','d5-default'],root,env,inputs=[cores['sdd']]))
            bindings=destination/'models/svg-arena/refused.bindings.json';value=read_json(destination/'models/svg-arena/arena-rules.bindings.json');value['profile']='fsgg-quint-profile/1';write(bindings,value)
            before=root/(name+'-before.json');write(before,helper.owner_snapshot(destination))
            args=author_args('d5-refused','models/svg-arena/refused.bindings.json')
            refused=wrong_profile(run,owner,receipts,[dotnet,str(cores['sdd']),*args],cores['sdd'],args,root,env)
            after=root/(name+'-after.json');write(after,helper.owner_snapshot(destination))
            check(['current-d5-backend-check','--receiver',str(destination),'--author',str(authored),'--inspect',str(inspected),'--refused',str(refused),'--before',str(before),'--after',str(after)])
            for path in destination.rglob('*'):
                if path.is_file() and not set(path.relative_to(destination).parts)&{'.git','.nuget','node_modules','bin','obj'}:inventory.append(str(path.relative_to(root)))
        summary['disposition']='receiver-checks-complete';summary['executionDisposition']='receiver-checks-complete'
    except BaseException as error:
        primary=error
        summary['executionDisposition']='failed'
        summary['firstCause']=type(error).__name__+': '+str(error)
        raise
    finally:
        finish_collection(reader,contract,root,summary,inventory,primary,start)
    return summary


def main(argv=None):
    args = sys.argv[1:] if argv is None else argv
    require(len(args)==1 and args[0] in ('--check-admission','--outer-preflight','--record-client-exit','--post-unit','--run'), 'closed D5 operation required')
    require(ADMISSION is not None,'HELD: runtime admission None; retirement unqualified') # before imports/effects
    runtime_scope(os.environ)
    reader=load_reader(HERE.parents[2]);contract=reader.caller_contract(OUTER_CALLER_CONTRACT,ADMISSION)
    reader.validate_admission(os.environ,ADMISSION,contract)
    if args==['--check-admission']:return
    if args==['--outer-preflight']:reader.outer_preflight(os.environ,contract)
    elif args==['--record-client-exit']:reader.record_client_exit(os.environ,contract)
    elif args==['--post-unit']:reader.post_unit(os.environ,contract)
    else:run_d5(reader,contract,os.environ)


if __name__ == '__main__':
    try:
        main()
    except (ValueError, KeyError, OSError, TypeError) as error:
        print(str(error), file=sys.stderr)
        raise SystemExit(3)
