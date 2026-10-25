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
TOOL_SHA256 = {
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
    return ['-o', 'Dir::Etc::main=-', '-o', 'Dir::Etc::parts=-',
            '-o','Dir::Etc::sourceparts=-','-o','Dir::Etc::preferences=-','-o','Dir::Etc::preferencesparts=-',
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


def observed(command, log, budget):
    """One original child group, bounded original output, no retry; outer profile remains required."""
    env={'PATH':'/usr/sbin:/usr/bin:/sbin:/bin','LC_ALL':'C','LANG':'C','DEBIAN_FRONTEND':'noninteractive',
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
        (log.parent/'partial-failure.json').write_text(json.dumps({**intent,'cause':str(cause),'phase':'launch-failed','childIdentity':'not-established'})+'\n')
        raise
    selector=selectors.DefaultSelector();selector.register(child.stdout,selectors.EVENT_READ)
    raw=bytearray()
    try:
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
        # This evidence is written before potentially blocking retirement, and is never a success receipt.
        failure={'schema':'fsgg.current-reference-noble-transaction-failure/1','command':command,
                 'cause':str(cause),'originalOutputBytes':len(raw),'phase':'before-cleanup',
                 'installation':False,'runtimeQualification':False}
        (log.parent/'partial-failure.json').write_text(json.dumps(failure,indent=2)+'\n')
        if child.poll() is None:
            try:os.killpg(child.pid,signal.SIGKILL)
            except ProcessLookupError:pass
        waited=False
        try:
            child.wait(timeout=max(0,min(5,budget.deadline+15-budget.clock())))
            waited=True
        except subprocess.TimeoutExpired:
            pass
        absent=False
        try:os.killpg(child.pid,0)
        except ProcessLookupError:absent=True
        (log.parent/'retirement.json').write_text(json.dumps({'directChildWaited':waited,'originalGroupAbsent':absent,
             'retirement':'group-observed-absent' if waited and absent else 'reported-unverifiable',
             'outerProfileQualification':False,'originalFailurePreserved':True})+'\n')
        raise
    finally:
        selector.close()
        child.stdout.close()


def metadata(inputs,out,budget,keyring):
    binaries=[];sources=[]
    for suite,sha256 in A.RELEASES.items():
        release=inputs/(suite+'.InRelease')
        A.need(A.digest(read(release,1024**2))==sha256,'source-pinned release differs')
        hashes=A.signed_release(release,keyring,suite,budget)
        target=out/'repo/dists'/suite;target.mkdir(parents=True)
        shutil.copyfile(release,target/'InRelease')
        for component in A.COMPONENTS:
            for kind,rows in [('binary-amd64/Packages.xz',binaries),('source/Sources.xz',sources)]:
                name=component+'/'+kind
                A.need(name in hashes,'required signed index absent')
                expected,size=hashes[name]
                path=inputs/(suite+'-'+component+'-'+kind.replace('/','-'))
                raw=read(path,A.MAX_FILE)
                A.need(len(raw)==size and A.digest(raw)==expected,'signed index bytes differ')
                keys = ('Package','Version','Architecture','Filename','SHA256','Size','Source','Multi-Arch') if kind.startswith('binary') else ('Package','Version','Directory','Checksums-Sha256')
                rows.extend({k:r[k] for k in keys if k in r} for r in A.rows(raw))
                if kind.startswith('binary'):
                    dest=target/name;dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(raw)
                budget.remaining()
    return binaries,sources


def source_join(binary,sources):
    match=re.fullmatch(r'([^ ]+)(?: \(([^)]+)\))?',binary.get('Source',binary['Package']))
    A.need(match is not None,'binary source field malformed')
    candidates=[s for s in sources if s.get('Package')==match[1] and s.get('Version')==(match[2] or binary['Version'])]
    A.need(len({json.dumps(s,sort_keys=True) for s in candidates})==1,'exact patched source absent/ambiguous')
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
    changes=[];final=dict(base)
    for line in text.splitlines():
        if not line.startswith('Inst '):
            continue
        match=re.fullmatch(r'Inst ([a-z0-9][a-z0-9+.:~-]*)(?: \[[^\]]+\])? \(([^\s()]+) [^()]*\[([^\]]+)\]\)',line)
        A.need(match is not None,'unrecognized original APT installation row')
        name,version,architecture=match.groups();name=name.removesuffix(':amd64')
        rows=[r for r in binaries if r.get('Package')==name and r.get('Version')==version and r.get('Architecture')==architecture]
        A.need(len({json.dumps(r,sort_keys=True) for r in rows})==1,'solver package absent/ambiguous in signed index')
        row=rows[0];canonical=name+(':amd64' if row.get('Multi-Arch')=='same' else '')
        A.need(not any(c['package']==name for c in changes),'duplicate original APT installation row')
        joined=source_join(row,sources)
        changes.append({'package':name,'version':version,'architecture':architecture,
                        'filename':joined['binary']['path'],'sha256':joined['binary']['sha256'],
                        'bytes':joined['binary']['bytes'],'sourcePackage':joined['sourcePackage'],
                        'sourceVersion':joined['sourceVersion'],'sourceFiles':joined['sourceFiles']})
        final[canonical]=version
    A.need(int(summaries[0][0])+int(summaries[0][1])==len(changes),'original solver summary/change population differs')
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
    fixed=options(out)
    run([APT,*fixed,'update'],out/'apt-update.log',budget)
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


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check-context',action='store_true',help='Read-only installed tool/actual717fixture preflight; no APT process')
    parser.add_argument('--inputs',type=Path)
    parser.add_argument('--request',type=Path)
    parser.add_argument('--out',type=Path)
    parser.add_argument('--keyring',type=Path,default=Path('/usr/share/keyrings/ubuntu-archive-keyring.gpg'))
    args=parser.parse_args()
    if args.check_context:
        A.need(args.inputs is None and args.request is None and args.out is None,'context preflight accepts no work inputs')
        runtime_guard();_,value=base_fixture()
        print(json.dumps({'schema':'fsgg.current-reference-noble-tool-preflight/1','installedToolHashesMatched':True,
                          'installedToolSha256':TOOL_SHA256,'subjectInventoryPackages':len(value),'subjectInventorySha256':BASE_SHA256,
                          'aptSimulation':'not-run','installation':False,'runtimeQualification':False}))
    else:
        A.need(args.inputs is not None and args.request is not None and args.out is not None,'explicit solver inputs/output required')
        plan(args.inputs.resolve(),request(read(args.request,65536)),args.out.resolve(),args.keyring.resolve())
