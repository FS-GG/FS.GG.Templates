#!/usr/bin/env python3
"""No-install offline APT plan against the exact retained c068 Noble base.

This command is for a separately selected qualified Noble execution context.
It is not a guest transport, runner admission, installer or AT qualification.
"""
import argparse
import hashlib
import importlib.util
import json
import lzma
import os
from pathlib import Path
import platform
import re
import selectors
import shutil
import signal
import stat
import subprocess
import time

HERE = Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_file_location('native_noble_acquisition', HERE/'current-reference-noble-acquisition.py')
A = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(A)
SPEC = importlib.util.spec_from_file_location('native_noble_manifest', HERE/'current-reference-native-input.py')
N = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(N)
BASE_COUNT = 717
BASE_SHA256 = '2a0d25ec6ede3165dec5e7763a2556b6ed31a2f9b04292dd5c81df0b37c1cc35'
APT = '/usr/bin/apt-get'
APT_CONFIG_TOOL = '/usr/bin/apt-config'
TOOL_SHA256 = {
    APT_CONFIG_TOOL: '44ec8b9197670a2c12ed2c6b837dd623c23b641e8c491be03ccefc23dd0fba8c',
    APT: 'eb53b3b66cbb7a90a370e26439e941b7cf146ddd91a5422063c761ce9e59c53b',
    '/usr/bin/dpkg': '567180a568ad6af680314fdcb4d963246985e682b28a9e8fafed8b09abbd50af',
    '/usr/bin/dpkg-query': 'cc2a19017c37132e4ad46c1fbddea6472262d0a62a0b8585c383706c20005ea1',
    '/usr/bin/gpgv': 'f14d026b9eae172c432e015bce227483293b4966f2f3fdcfa582f71d3dbb2ae8',
    '/usr/lib/apt/methods/file': 'bf5864959417e354b539fd361ecc1c757312593bf0c8530b36def9bc34f1bd86',
    '/usr/lib/apt/methods/gpgv': '52201cea3a61b3f0e8368687ce46391c482cd0c52cbea10dbbcf2cb04de56e63',
}
STATUS = Path('/var/lib/dpkg/status')
STATUS_FIXTURE = HERE/'fixtures/noble-c068-status.xz'
STATUS_FIXTURE_SHA256 = 'e2ba73498adb51230edf1130de020a7419278f0eeecbd98acc56005e93cee9be'
ORIGINAL_C068_STATUS_SHA256 = 'f12714579833970cd7a965c0097f09f7acc8d8e4af4b2434e9ecbb5c67efa401'
MAX_LOG = 4*1024**2


def read(path, maximum):
    with Path(path).open('rb') as stream:
        raw = stream.read(maximum+1)
    A.need(len(raw) <= maximum, 'bounded input exceeded: '+str(path))
    return raw


def inventory(raw):
    result = {}
    for block in raw.decode('utf-8').split('\n\n'):
        if not block.strip():
            continue
        row = A.fields(block)
        if row.get('Status') != 'install ok installed':
            continue
        A.need(row['Architecture'] in ('all','amd64'), 'nonselected installed architecture')
        name = row['Package']+(':amd64' if row.get('Multi-Arch') == 'same' else '')
        A.need(name not in result, 'duplicate installed package')
        result[name] = row['Version']
    A.need(0 < len(result) <= 20000, 'installed inventory absent/oversized')
    return result


def inventory_bytes(value):
    return ''.join(k+'\t'+v+'\n' for k,v in sorted(value.items())).encode()


def runtime_guard():
    release = read('/etc/os-release',65536)
    A.need(re.search(rb'(?m)^ID=ubuntu$',release) and re.search(rb'(?m)^VERSION_ID="24.04"$',release) and
           platform.machine() == 'x86_64', 'actual selected Noble amd64 runtime required')
    A.need(not any(os.environ.get(k) for k in ['LD_PRELOAD','LD_LIBRARY_PATH','PYTHONHOME','PYTHONPATH']), 'ambient native loader environment refused')
    A.need(Path(shutil.which('gpgv') or '/absent').resolve()==Path('/usr/bin/gpgv'), 'selected signature tool path differs')
    differences=[]
    for path, sha256 in TOOL_SHA256.items():
        try:
            actual=A.digest(read(path,16*1024**2))
        except OSError as cause:
            differences.append(path+' unavailable='+str(cause));continue
        if actual!=sha256:
            differences.append(path+' expected='+sha256+' actual='+actual)
    A.need(not differences, 'installed Noble tool/input prerequisites differ: '+'; '.join(differences))
    return A.digest(read(STATUS,32*1024**2))


def base_fixture():
    decoder=lzma.LZMADecompressor(memlimit=128*1024**2)
    raw=decoder.decompress(read(STATUS_FIXTURE,131072),max_length=8*1024**2+1)
    A.need(len(raw)<=8*1024**2 and decoder.eof and not decoder.unused_data, 'c068 status fixture expansion differs')
    A.need(A.digest(raw)==STATUS_FIXTURE_SHA256,'source-bound c068 solver status fixture differs')
    value=inventory(raw)
    A.need(len(value)==BASE_COUNT and A.digest(inventory_bytes(value))==BASE_SHA256,
           'actual c068 post-bake package inventory differs')
    return raw,value


def request(raw):
    A.need(0 < len(raw) <= 65536, 'closed root request absent/oversized')
    def unique(pairs):
        result={}
        for key,value in pairs:
            A.need(key not in result,'duplicate root request field')
            result[key]=value
        return result
    value=json.loads(raw,object_pairs_hook=unique)
    A.need(type(value) is dict and set(value)=={'schema','packages'} and
           value['schema']=='fsgg.current-reference-noble-package-request/1','closed source package request required')
    N.validate_packages(value['packages'])
    return value


def options(out):
    """c068 offline semantics plus private status/cache/config domains; no host APT configuration."""
    return ['-o', 'Dir::Etc::main='+str(out/'apt-main.conf'), '-o', 'Dir::Etc::parts='+str(out/'apt-config-parts'),
            '-o','Dir::Etc::sourceparts='+str(out/'apt-source-parts'),
            '-o','Dir::Etc::netrc='+str(out/'apt-auth.conf'),'-o','Dir::Etc::netrcparts='+str(out/'apt-auth-parts'),
            '-o','Dir::Etc::preferences='+str(out/'apt-preferences'),'-o','Dir::Etc::preferencesparts='+str(out/'apt-preference-parts'),
            '-o','Dir::Etc::sourcelist='+str(out/'sources.list'),
            '-o','Dir::State='+str(out/'state'), '-o','Dir::State::status='+str(out/'status'),
            '-o','Dir::State::extended_states='+str(out/'extended_states'),
            '-o','Dir::State::lists='+str(out/'state/lists'), '-o','Dir::Cache='+str(out/'cache'),
            '-o','Dir::Cache::archives='+str(out/'cache/archives'),
            '-o','APT::Architecture=amd64','-o','Acquire::Languages=none',
            '-o','APT::Sandbox::User=root','-o','Acquire::By-Hash=no',
            '-o','Acquire::IndexTargets::deb::CNF::DefaultEnabled=false',
            '-o','Acquire::IndexTargets::deb::DEP-11::DefaultEnabled=false',
            '-o','APT::Color=0','-o','Debug::NoLocking=true']


def bootstrap(out):
    # APT_CONFIG is loaded by pkgInitConfig BEFORE command-line -o options.
    # Disable host config/auth/hooks at that first boundary, not after init.
    for name in ['apt-config-parts','apt-source-parts','apt-auth-parts','apt-preference-parts']:
        (out/name).mkdir()
    for name in ['apt-main.conf','apt-auth.conf','apt-preferences']:
        (out/name).touch(exist_ok=False)
    fixed=options(out)
    values=[item.split('=',1) for item in fixed if item!='-o']
    for key,value in values:
        A.need(re.fullmatch('[A-Za-z0-9_:/.-]+',key) and not any(c in value for c in ['"','\\','\n','\r']), 'unsafe private APT bootstrap value')
    body=''.join(key+' "'+value+'";\n' for key,value in values)
    path=out/'apt-bootstrap.conf'
    path.write_text(body)
    return path


def effective_config(raw,out):
    fields={}
    for line in raw.splitlines():
        match=re.fullmatch(r'([^ \n]+) "((?:[^"\\]|\\.)*)";',line)
        A.need(match is not None,'unrecognized actual APT configuration row')
        key,value=match.groups()
        if not key.endswith('::'):
            A.need(key not in fields,'duplicate actual APT configuration scalar')
            fields[key]=value
        else:
            fields.setdefault(key,[]).append(value)
    expected=dict(item.split('=',1) for item in options(out) if item!='-o')
    # apt-config2.8.3 normalizes this scalar to its native one-element list before dump.
    expected.pop('Acquire::Languages')
    A.need(fields.get('Acquire::Languages')=='' and fields.get('Acquire::Languages::')==['none'],
           'effective APT language population differs from selected none')
    A.need(all(fields.get(key)==value for key,value in expected.items()),'effective APT configuration differs from private bootstrap')
    forbidden=('APT::Update::Pre-Invoke','APT::Update::Post-Invoke','DPkg::Pre-Invoke','DPkg::Post-Invoke','DPkg::Pre-Install-Pkgs')
    A.need(not any(any(key.startswith(prefix) for prefix in forbidden) for key in fields),'ambient APT hook survived private bootstrap')
    return A.digest(raw.encode())


def report(path,value,primary):
    try:
        path.write_text(json.dumps(value,indent=2)+'\n')
    except BaseException as secondary:
        try:primary.add_note('secondary reporting failure '+str(path)+': '+str(secondary))
        except BaseException:pass


def observed(command, log, budget):
    """One original child group, bounded original output, no retry; outer profile remains required."""
    config=log.parent/'apt-bootstrap.conf'
    A.need(config.is_file() and not config.is_symlink(),'source-owned early APT_CONFIG required')
    env={'APT_CONFIG':str(config),'PATH':'/usr/sbin:/usr/bin:/sbin:/bin','LC_ALL':'C','LANG':'C','DEBIAN_FRONTEND':'noninteractive',
         'HOME':str(log.parent/'home'),'TMPDIR':str(log.parent/'tmp')}
    budget.remaining()
    intent={'schema':'fsgg.current-reference-noble-transaction-intent/1','command':command,
            'installation':False,'runtimeQualification':False}
    (log.parent/(log.name+'.intent.json')).write_text(json.dumps(intent,indent=2)+'\n')
    budget.remaining()
    try:
        child=subprocess.Popen(command,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,
                               env=env,start_new_session=True)
    except BaseException as cause:
        report(log.parent/'partial-failure.json',{**intent,'cause':str(cause),'phase':'launch-failed','childIdentity':'not-established'},cause)
        raise
    selector=None;raw=bytearray();primary=None
    try:
        selector=selectors.DefaultSelector();selector.register(child.stdout,selectors.EVENT_READ)
        with log.open('xb') as stream:
            while selector.get_map():
                budget.remaining()
                for key,_ in selector.select(min(.1,budget.remaining())):
                    block=os.read(key.fileobj.fileno(),65536)
                    if not block:
                        selector.unregister(key.fileobj);continue
                    A.need(len(raw)+len(block)<=MAX_LOG,'original APT output exceeded bound')
                    raw.extend(block);stream.write(block)
            code=child.wait(timeout=budget.remaining())
            budget.remaining()
            A.need(code==0,'original APT exit '+str(code))
        try:
            os.killpg(child.pid,0)
        except ProcessLookupError:
            pass
        else:
            raise RuntimeError('Noble transaction: original child group retirement unverified')
        budget.remaining()
        return bytes(raw).decode('utf-8')
    except BaseException as cause:
        primary=cause
        failure={'schema':'fsgg.current-reference-noble-transaction-failure/1','command':command,
                 'cause':str(cause),'originalOutputBytes':len(raw),'phase':'before-cleanup',
                 'installation':False,'runtimeQualification':False}
        try:
            report(log.parent/'partial-failure.json',failure,cause)
        finally:
            # Reporting failure cannot skip required bounded cleanup or replace first cause.
            waited=False;absent=False
            try:
                if child.poll() is None:
                    try:os.killpg(child.pid,signal.SIGKILL)
                    except ProcessLookupError:pass
                child.wait(timeout=max(0,min(5,budget.deadline+15-budget.clock())))
                waited=True
                try:os.killpg(child.pid,0)
                except ProcessLookupError:absent=True
            except BaseException as secondary:
                try:cause.add_note('secondary cleanup failure: '+str(secondary))
                except BaseException:pass
            report(log.parent/'retirement.json',{'directChildWaited':waited,'originalGroupAbsent':absent,
                 'retirement':'group-observed-absent' if waited and absent else 'reported-unverifiable',
                 'outerProfileQualification':False,'originalFailurePreserved':True},cause)
        raise
    finally:
        closing=None
        actions=([selector.close] if selector is not None else [])+[child.stdout.close]
        for close in actions:
            try:close()
            except BaseException as secondary:
                if primary is not None:
                    try:primary.add_note('secondary close failure: '+str(secondary))
                    except BaseException:pass
                elif closing is None:
                    closing=secondary
        if closing is not None:raise closing


def metadata(inputs,out,budget,keyring):
    binaries=[];sources=[]
    retained=out/'metadata';retained.mkdir(mode=0o700)
    for suite,sha256 in A.RELEASES.items():
        raw_release=read(inputs/(suite+'.InRelease'),1024**2)
        A.need(A.digest(raw_release)==sha256,'source-pinned release differs')
        release=retained/(suite+'.InRelease');release.write_bytes(raw_release)
        hashes=A.signed_release(release,keyring,suite,budget)
        target=out/'repo/dists'/suite;target.mkdir(parents=True)
        (target/'InRelease').write_bytes(raw_release)
        for component in A.COMPONENTS:
            for kind,rows in [('binary-amd64/Packages.xz',binaries),('source/Sources.xz',sources)]:
                name=component+'/'+kind
                A.need(name in hashes,'required signed index absent')
                expected,size=hashes[name]
                path=inputs/(suite+'-'+component+'-'+kind.replace('/','-'))
                raw=read(path,A.MAX_FILE)
                A.need(len(raw)==size and A.digest(raw)==expected,'signed index bytes differ')
                (retained/path.name).write_bytes(raw)
                keys = (*A.BINARY_IDENTITY_KEYS,'Filename') if kind.startswith('binary') else ('Package','Version','Directory','Checksums-Sha256')
                rows.extend({k:r[k] for k in keys if k in r} for r in A.rows(raw))
                if kind.startswith('binary'):
                    dest=target/name;dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(raw)
                budget.remaining()
    return binaries,sources



def update_output(raw,out):
    expected={(suite,'InRelease') for suite in A.RELEASES}|{(suite+'/'+component,'amd64 Packages') for suite in A.RELEASES for component in ['main','universe']}
    seen=set();ids={}
    for line in raw.splitlines():
        if line=='Reading package lists...':continue
        match=re.fullmatch(r'Get:([1-9][0-9]*) '+re.escape((out/'repo').as_uri().replace('file://','file:'))+r' ([a-z/-]+) (InRelease|amd64 Packages) \[[0-9.]+ [kM]?B\]',line)
        A.need(match is not None,'original APT update output is outside selected private file repository')
        index,distribution,kind=match.groups();identity=(distribution,kind)
        A.need(identity in expected and (index not in ids or ids[index]==identity),'original APT update target differs')
        ids[index]=identity;seen.add(identity)
    A.need(seen==expected,'original APT update population incomplete')
    return A.digest(raw.encode())


def source_join(binary,sources):
    match=re.fullmatch(r'([^ ]+)(?: \(([^)]+)\))?',binary.get('Source',binary['Package']))
    A.need(match is not None,'binary source field malformed')
    candidates=A.patched_sources(match[1],match[2] or binary['Version'],sources)
    source=candidates[0]
    dsc=[line.split() for line in source.get('Checksums-Sha256','').splitlines() if line.strip() and line.split()[-1].endswith('.dsc')]
    A.need(len(dsc)==1,'one authenticated source descriptor required')
    package={'name':binary['Package'],'version':binary['Version'],'debSha256':binary['SHA256'],
             'sourceUri':A.BASE+A.relative(source['Directory'])+'/'+A.relative(dsc[0][2]),'sourceSha256':dsc[0][0]}
    return A.select(package,[binary],sources)


def frozen(text,base,roots,binaries,sources):
    A.need(not re.search(r'(?m)^(Remv|Purg) ',text),'APT removals are outside this preparation domain')
    summaries=re.findall(r'(?m)^(\d+) upgraded, (\d+) newly installed, (\d+) to remove and (\d+) not upgraded\.$',text)
    A.need(len(summaries)==1 and int(summaries[0][2])==0,'original successful no-removal APT summary required')
    changes=[];final=dict(base);installed={};configured=set();upgrades=0
    A.need(not re.search(r'(?m)^(?:E:|W:|Err:)',text),'original APT diagnostic refused')
    for line in text.splitlines():
        if line.startswith('Conf '):
            conf=re.fullmatch(r'Conf ([a-z0-9][a-z0-9+.:~-]*) \(([^\s()]+) ([^()]*)\[([^\]]+)\]\)',line)
            A.need(conf is not None,'unrecognized original APT configuration row')
            name,version,origin,architecture=conf.groups();name=name.removesuffix(':amd64')
            A.need(name in installed and name not in configured and installed[name]==(version,origin,architecture),
                   'original configuration row differs from prior installation proposal')
            configured.add(name)
            continue
        if not line.startswith('Inst '):
            continue
        match=re.fullmatch(r'Inst ([a-z0-9][a-z0-9+.:~-]*)(?: \[([^\]]+)\])? \(([^\s()]+) ([^()]*)\[([^\]]+)\]\)(?: \[\])?',line)
        A.need(match is not None,'unrecognized original APT installation row')
        name,old,version,origin,architecture=match.groups();name=name.removesuffix(':amd64')
        rows=[r for r in binaries if r.get('Package')==name and r.get('Version')==version and r.get('Architecture')==architecture]
        row,aliases=A.binary_aliases(rows)
        canonical=name+(':amd64' if row.get('Multi-Arch')=='same' else '')
        A.need(not any(c['package']==name for c in changes),'duplicate original APT installation row')
        A.need((old is None and canonical not in base) or (old is not None and base.get(canonical)==old and old!=version),
               'original old/new package version differs from subject status')
        upgrades+=int(old is not None)
        installed[name]=(version,origin,architecture)
        joined=source_join(row,sources)
        changes.append({'package':name,'version':version,'architecture':architecture,
                        'filename':joined['binary']['path'],'sha256':joined['binary']['sha256'],
                        'bytes':joined['binary']['bytes'],'sourcePackage':joined['sourcePackage'],
                        'sourceVersion':joined['sourceVersion'],'sourceFiles':joined['sourceFiles'],
                        **({'binaryAliases':aliases} if len(aliases)>1 else {}),
                        **({'sourceDirectoryAliases':joined['sourceDirectoryAliases']} if 'sourceDirectoryAliases' in joined else {})})
        final[canonical]=version
    A.need(int(summaries[0][0])==upgrades and int(summaries[0][1])==len(changes)-upgrades,
           'original solver summary/change population differs')
    A.need(configured==set(installed),'original configuration settlement population differs')
    for root in roots['packages']:
        name=root['name'].removesuffix(':amd64')
        rows=[r for r in binaries if r.get('Package')==name and r.get('Version')==root['version'] and r.get('SHA256')==root['debSha256']]
        A.need(rows,'declared root differs from signed binary')
        A.select(root,rows,sources)
        canonical=name+(':amd64' if rows[0].get('Multi-Arch')=='same' else '')
        A.need(final.get(canonical)==root['version'],'original solver did not satisfy a declared root')
    return sorted(changes,key=lambda r:r['package']),final


def plan(inputs,roots,out,keyring,budget=None,run=observed):
    roots=request(N.canonical(roots))
    budget=budget or A.Budget(105)  # Caller clips total120s, with a separate15s retirement reserve.
    A.need(keyring==Path('/usr/share/keyrings/ubuntu-archive-keyring.gpg'),'selected source keyring path required')
    A.need(not out.is_relative_to(inputs) and not inputs.is_relative_to(out),'input/output domains overlap')
    host_status=runtime_guard()  # Actual installed tools before any child; subject status stays private.
    status,base=base_fixture()
    A.need(not out.exists() and not out.is_symlink(),'fresh transaction output required')
    out.mkdir(mode=0o700)
    for directory in ['state/lists/partial','cache/archives/partial','home','tmp']:
        (out/directory).mkdir(parents=True)
    (out/'status').write_bytes(status);(out/'extended_states').write_bytes(b'')
    binaries,sources=metadata(inputs,out,budget,keyring)
    for root in roots['packages']:
        A.select(root,binaries,sources)  # Exact declared signed roots before any APT execution.
    lines=['deb [signed-by='+str(keyring)+'] '+(out/'repo').as_uri()+' '+s+' main universe' for s in A.RELEASES]
    A.need(not any('\n' in line for line in lines),'APT source path injection refused')
    (out/'sources.list').write_text('\n'.join(lines)+'\n')
    bootstrap(out)
    fixed=options(out)
    config_dump=run([APT_CONFIG_TOOL,*fixed,'dump'],out/'apt-config.log',budget)
    config_sha=effective_config(config_dump,out)
    original_update=run([APT,*fixed,'update'],out/'apt-update.log',budget)
    update_sha=update_output(original_update,out)
    original=run([APT,*fixed,'--simulate','--no-install-recommends','install',
                  *[p['name']+'='+p['version'] for p in roots['packages']]],out/'apt-simulate.log',budget)
    changes,final=frozen(original,base,roots,binaries,sources)
    A.need(A.digest(read(STATUS,32*1024**2))==host_status,'real package state changed during no-install simulation')
    result={'schema':'fsgg.current-reference-noble-transaction/1','snapshot':A.BASE,
            'baseInventory':{'packages':BASE_COUNT,'sha256':BASE_SHA256},
            'subjectStatusSha256':STATUS_FIXTURE_SHA256,
            'originalC068StatusSha256':ORIGINAL_C068_STATUS_SHA256,
            'rootRequestSha256':A.digest(N.canonical(roots)),
            'aptOptionsSha256':A.digest(N.canonical(options(Path('/__fsgg_private_transaction__')))),
            'actualAptArgumentsSha256':A.digest(N.canonical(fixed)),
            'actualUpdateSha256':update_sha,'originalChildOutcomes':{'apt-config':0,'apt-update':0,'apt-simulate':0},
            'actualEffectiveConfigSha256':config_sha,'configurationScope':'private APT_CONFIG before initialization',
            'originalSimulationSha256':A.digest(original.encode()),'debs':changes,
            'expectedFinalInventory':{'packages':len(final),'sha256':A.digest(inventory_bytes(final)),
                                      'derivation':'original successful APT simulation; not installed'},
            'actualSolver':'no-install-apt-simulation','binaryAcquisition':'not-run',
            'sourceArchiveAcquisition':'not-run','installation':False,'runtimeQualification':False,
            'actualAT':False,'nativeImeAcceptance':False,
            'outerProfileQualification':'separately required; not established by this helper'}
    budget.remaining()
    (out/'package-inventory.expected').write_bytes(inventory_bytes(final))
    (out/'transaction.json').write_text(json.dumps(result,indent=2)+'\n')
    budget.remaining()  # Persistence and final return share the original work clock.
    return result


CURRENT_DESKTOP_ROOT_SHA256='47782f4389f3451e843cd9dadff584c51f840511a085f76b063235a56f8098c9'
FACTORY_COMPILER_PACKAGES=('libglib2.0-bin',)


def frozen_input_plan(originals,expected,roots,binaries,sources):
    """Replay supplied originals; custody/solver-run authentication remains caller-owned."""
    raw=read(originals/'transaction.json',512*1024)
    A.need(re.fullmatch('[0-9a-f]{64}',expected) and A.digest(raw)==expected,'original frozen transaction digest differs')
    def unique(pairs):
        result={}
        for key,value in pairs:
            A.need(key not in result,'duplicate original transaction field');result[key]=value
        return result
    result=json.loads(raw,object_pairs_hook=unique)
    fields={'schema','snapshot','baseInventory','subjectStatusSha256','originalC068StatusSha256',
            'rootRequestSha256','aptOptionsSha256','actualAptArgumentsSha256','actualUpdateSha256',
            'originalChildOutcomes','actualEffectiveConfigSha256','configurationScope','originalSimulationSha256',
            'debs','expectedFinalInventory','actualSolver','binaryAcquisition','sourceArchiveAcquisition',
            'installation','runtimeQualification','actualAT','nativeImeAcceptance','outerProfileQualification'}
    A.need(type(result) is dict and set(result)==fields,'closed original transaction required')
    A.need(A.digest(N.canonical(roots))==CURRENT_DESKTOP_ROOT_SHA256==result['rootRequestSha256'],
           'selected current desktop root request differs')
    A.need(result['schema']=='fsgg.current-reference-noble-transaction/1' and result['snapshot']==A.BASE and
           result['baseInventory']=={'packages':BASE_COUNT,'sha256':BASE_SHA256} and
           result['subjectStatusSha256']==STATUS_FIXTURE_SHA256 and result['originalC068StatusSha256']==ORIGINAL_C068_STATUS_SHA256,
           'original c068 subject/source identity differs')
    A.need(type(result['originalChildOutcomes']) is dict and set(result['originalChildOutcomes'])=={'apt-config','apt-update','apt-simulate'} and
           all(type(value) is int and value==0 for value in result['originalChildOutcomes'].values()) and
           result['configurationScope']=='private APT_CONFIG before initialization' and
           result['outerProfileQualification']=='separately required; not established by this helper' and
           result['actualSolver']=='no-install-apt-simulation' and
           result['binaryAcquisition']==result['sourceArchiveAcquisition']=='not-run' and
           all(result[key] is False for key in ['installation','runtimeQualification','actualAT','nativeImeAcceptance']),
           'original source-plan outcome/scope differs')
    config=read(originals/'apt-config.log',MAX_LOG).decode('utf-8')
    matched=re.search(r'^Dir::State::status "([^"\n]+)";$',config,re.M)
    A.need(matched is not None,'original private status path absent')
    original_out=Path(matched[1]).parent
    A.need(original_out.is_absolute() and '..' not in original_out.parts,'original output path malformed')
    A.need(effective_config(config,original_out)==result['actualEffectiveConfigSha256'] and
           A.digest(N.canonical(options(original_out)))==result['actualAptArgumentsSha256'] and
           A.digest(N.canonical(options(Path('/__fsgg_private_transaction__'))))==result['aptOptionsSha256'],
           'original private configuration/arguments differ')
    update=read(originals/'apt-update.log',MAX_LOG).decode('utf-8')
    A.need(update_output(update,original_out)==result['actualUpdateSha256'],'original update digest differs')
    original=read(originals/'apt-simulate.log',MAX_LOG).decode('utf-8')
    A.need(A.digest(original.encode())==result['originalSimulationSha256'],'original simulation digest differs')
    subject,base=base_fixture()
    A.need(read(originals/'status',8*1024**2)==subject,'original subject status differs')
    changes,final=frozen(original,base,roots,binaries,sources)
    A.need(type(result['debs']) is list and 1<=len(result['debs'])<=512 and changes==result['debs'] and
           result['expectedFinalInventory']=={'packages':len(final),'sha256':A.digest(inventory_bytes(final)),
               'derivation':'original successful APT simulation; not installed'},'complete frozen output/input join differs')
    return result


def copy_verified_archive(source,target,row,budget):
    # Retained bytes are untrusted until matched to the freshly authenticated row.
    A.need(not source.is_symlink() and stat.S_ISREG(source.stat().st_mode),'retained archive is not a regular file')
    A.need(0<row['bytes']<=A.MAX_FILE and budget.bytes+row['bytes']<=A.MAX_TOTAL,'retained archive population bound exceeded')
    descriptor=os.open(source,os.O_RDONLY|os.O_NOFOLLOW)
    with os.fdopen(descriptor,'rb') as incoming,target.open('xb') as outgoing:
        birth=os.fstat(incoming.fileno())
        A.need(stat.S_ISREG(birth.st_mode) and birth.st_size==row['bytes'],'retained archive changed type/size')
        digest=hashlib.sha256();count=0
        while True:
            budget.remaining();block=incoming.read(min(65536,row['bytes']+1-count))
            if not block:break
            count+=len(block);budget.bytes+=len(block)
            A.need(count<=row['bytes'] and budget.bytes<=A.MAX_TOTAL,'retained archive body exceeded bound')
            outgoing.write(block);digest.update(block)
        ended=os.fstat(incoming.fileno())
        A.need(all(getattr(birth,k)==getattr(ended,k) for k in ['st_dev','st_ino','st_size','st_mtime_ns','st_ctime_ns']),
               'retained archive changed while read')
        A.need(count==row['bytes'] and digest.hexdigest()==row['sha256'],'retained archive size/digest differs')
    budget.remaining()


def selected_role_bindings(original,roots,binaries,sources):
    selected_roots=list(roots['packages'])
    for name in FACTORY_COMPILER_PACKAGES:
        candidates=[row for row in original['debs'] if row['package']==name]
        A.need(len(candidates)==1,'required factory compiler package absent from frozen transaction')
        row=candidates[0];dsc=[source for source in row['sourceFiles'] if source['path'].endswith('.dsc')]
        A.need(len(dsc)==1,'factory compiler patched source descriptor absent')
        if name not in {root['name'].removesuffix(':amd64') for root in selected_roots}:
            selected_roots.append({'name':name,'version':row['version'],'debSha256':row['sha256'],
                'sourceUri':A.BASE+dsc[0]['path'],'sourceSha256':dsc[0]['sha256']})
    return [A.select(root,binaries,sources) for root in selected_roots]


def prepare_frozen_inputs(originals,expected,roots,inputs,out,keyring,retained=None,budget=None):
    """Download/verify one fixed desktop pool; never install or authenticate a solver run."""
    roots=request(N.canonical(roots));budget=budget or A.Budget(240)
    A.need(A.digest(N.canonical(roots))==CURRENT_DESKTOP_ROOT_SHA256,'only selected current desktop roots supported')
    for source in [originals,inputs,*([retained] if retained is not None else [])]:
        A.need(not out.is_relative_to(source) and not source.is_relative_to(out),'preparation input/output domains overlap')
    A.need(not out.exists() and not out.is_symlink(),'fresh frozen-input output required')
    out.mkdir(mode=0o700)
    try:
        binaries,sources=metadata(inputs,out,budget,keyring)
        original=frozen_input_plan(originals,expected,roots,binaries,sources)
        kept=out/'originals';kept.mkdir(mode=0o700)
        identities={'transaction.json':expected,'apt-config.log':original['actualEffectiveConfigSha256'],
                    'apt-update.log':original['actualUpdateSha256'],'apt-simulate.log':original['originalSimulationSha256'],
                    'status':original['subjectStatusSha256']}
        for name,digest in identities.items():
            raw=read(originals/name,MAX_LOG)
            A.need(A.digest(raw)==digest,'original input changed during preparation handoff')
            (kept/name).write_bytes(raw);budget.remaining()
        roles=selected_role_bindings(original,roots,binaries,sources)
        archives={}
        def include(row,kind):
            path=A.relative(row['path']);old=archives.get(path)
            A.need(old is None or all(old[k]==row[k] for k in ['sha256','bytes']),'conflicting shared frozen archive')
            A.need(type(row['bytes']) is int and 0<row['bytes']<=A.MAX_FILE,'frozen archive body bound differs')
            if old is None:archives[path]={**row,'kinds':[kind]}
            elif kind not in old['kinds']:old['kinds'].append(kind)
        for row in original['debs']:
            include({'path':row['filename'],'sha256':row['sha256'],'bytes':row['bytes']},'runtime-binary')
        for role in roles:
            include(role['binary'],'selected-role-binary')
            for row in role['sourceFiles']:include(row,'selected-role-patched-source')
        A.need(len(archives)<=A.MAX_REQUESTS and sum(row['bytes'] for row in archives.values())<=A.MAX_TOTAL,
               'frozen runtime/selected-role pool exceeds unchanged archive bounds')
        for path,row in sorted(archives.items()):
            budget.remaining();target=out/'archives'/path;target.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
            candidate=retained/'archives'/path if retained is not None else None
            if candidate is not None and (candidate.exists() or candidate.is_symlink()):
                parent=candidate.parent
                while parent!=retained:
                    A.need(not parent.is_symlink(),'retained archive ancestor is a symlink');parent=parent.parent
                A.need(not retained.is_symlink(),'retained archive root is a symlink')
                copy_verified_archive(candidate,target,row,budget);row['acquisition']='hash-verified-retained-copy'
            else:
                A.fetch(A.BASE+path,row['sha256'],row['bytes'],target,budget);row['acquisition']='original-HTTP200'
        result={'schema':'fsgg.current-reference-noble-frozen-inputs/1','snapshot':A.BASE,
                'originalTransactionSha256':expected,'rootRequestSha256':CURRENT_DESKTOP_ROOT_SHA256,
                'helperSha256':A.digest(Path(__file__).read_bytes()),'acquisitionHelperSha256':A.digest((HERE/'current-reference-noble-acquisition.py').read_bytes()),
                'runtimeBinaryPackages':len(original['debs']),'selectedRolePackages':len(roles),'selectedRoleBindings':roles,
                'expectedFinalInventory':original['expectedFinalInventory'],'archives':list(archives.values()),
                'archiveBytes':budget.bytes,'httpRequests':budget.requests,'declaredArchivesVerified':True,
                'suppliedOriginalInputsConsistent':True,'externalSolverRunCustodyVerified':False,
                'dependencySourceArchives':'only selected role closure acquired; remaining source tuples metadata-bound',
                'installation':False,'runtimeQualification':False,'actualAT':False,'nativeImeAcceptance':False}
        budget.remaining();(out/'frozen-inputs.json').write_text(json.dumps(result,indent=2)+'\n');budget.remaining()
        return result
    except BaseException as cause:
        report(out/'partial-failure.json',{'schema':'fsgg.current-reference-noble-frozen-inputs-failure/1',
               'cause':str(cause),'installation':False,'runtimeQualification':False},cause)
        raise


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check-context',action='store_true',help='Read-only installed tool/actual717fixture preflight; no APT process')
    parser.add_argument('--inputs',type=Path)
    parser.add_argument('--request',type=Path)
    parser.add_argument('--out',type=Path)
    parser.add_argument('--keyring',type=Path,default=Path('/usr/share/keyrings/ubuntu-archive-keyring.gpg'))
    parser.add_argument('--prepare-originals',type=Path,help='Read-only fixed desktop binary/selected-role-source preparation from supplied original source outputs')
    parser.add_argument('--expected-transaction-sha256',help='Externally bound original transaction digest; this helper does not authenticate a solver run')
    parser.add_argument('--retained-archives',type=Path,help='Optional explicit prior acquisition input; bytes reverified, no failed-fetch fallback')
    args=parser.parse_args()
    if args.check_context:
        A.need(args.inputs is None and args.request is None and args.out is None and args.prepare_originals is None and
               args.expected_transaction_sha256 is None and args.retained_archives is None,'context preflight accepts no work inputs')
        runtime_guard();_,value=base_fixture()
        print(json.dumps({'schema':'fsgg.current-reference-noble-tool-preflight/1','installedToolHashesMatched':True,
                          'installedToolSha256':TOOL_SHA256,'subjectInventoryPackages':len(value),'subjectInventorySha256':BASE_SHA256,
                          'aptSimulation':'not-run','installation':False,'runtimeQualification':False}))
    else:
        A.need(args.inputs is not None and args.request is not None and args.out is not None,'explicit solver inputs/output required')
        roots=request(read(args.request,65536))
        if args.prepare_originals is not None:
            A.need(args.expected_transaction_sha256 is not None,'explicit externally bound transaction digest required')
            A.need(args.retained_archives is None or not args.retained_archives.is_symlink(),'retained input root is a symlink')
            prepare_frozen_inputs(args.prepare_originals.resolve(),args.expected_transaction_sha256,roots,args.inputs.resolve(),
                                  args.out.resolve(),args.keyring.resolve(),
                                  args.retained_archives.resolve() if args.retained_archives is not None else None)
        else:
            A.need(args.expected_transaction_sha256 is None and args.retained_archives is None,'preparation-only fields on solver route refused')
            plan(args.inputs.resolve(),roots,args.out.resolve(),args.keyring.resolve())
