#!/usr/bin/env python3
"""Named Noble AT factory: source-derived bytes, offline installation, original keymap inputs.

Only the separately selected private AT v2 guest may install or start a display.
Data/fixture checks grant no image, caller, outer-containment, runtime or AT acceptance.
The existing sampled observer census keeps its detached-descendant limitations.
"""
import argparse
import bz2
import hashlib
import importlib.util
import io
import json
import lzma
import os
from pathlib import Path
import re
import selectors
import signal
import stat
import subprocess
import tarfile
import time
import zlib

ENTRY_STARTED=time.monotonic()
HERE=Path(__file__).resolve().parent
FACTORY_FILES=('current-reference-noble-factory.py','current-reference-noble-transaction.py',
    'current-reference-noble-acquisition.py','current-reference-native-input.py','external-reference-orca.py',
    'fixtures/noble-c068-status.xz','fixtures/noble-source-prefix-request.json')


def sealed_imports():
    """The baked ATv2 driver seals exact Git blobs before any factory imports execute."""
    controller=HERE.parents[2]
    if controller.parent!=Path('/opt/fsgg/current-at-controller') or re.fullmatch('[0-9a-f]{40}',controller.name) is None:
        raise RuntimeError('fixed root-sealed factory controller path required before imports')
    seal=controller/'factory-seal.json';info=seal.lstat()
    if not stat.S_ISREG(info.st_mode) or info.st_uid!=0 or stat.S_IMODE(info.st_mode)!=0o644 or info.st_size>16384:
        raise RuntimeError('root factory seal absent/mutable/oversized')
    value=json.loads(seal.read_bytes())
    if value.get('schema')!='fsgg.current-reference-factory-seal/1' or value.get('source')!=controller.name or set(value.get('files',{}))!=set(FACTORY_FILES):
        raise RuntimeError('closed selected factory seal required')
    for name in FACTORY_FILES:
        path=HERE/name
        for ancestor in [path,*path.parents]:
            info=ancestor.lstat()
            if info.st_uid!=0 or info.st_mode&0o022 or stat.S_ISLNK(info.st_mode):
                raise RuntimeError('factory import closure/ancestor mutable')
        info=path.lstat()
        if not stat.S_ISREG(info.st_mode) or info.st_size>1024**2 or hashlib.sha256(path.read_bytes()).hexdigest()!=value['files'][name]:
            raise RuntimeError('actual factory import differs from root seal')
    binding=Path('/etc/fsgg-qualification-runner/instance-binding.json').read_bytes()
    if hashlib.sha256(binding).hexdigest()!=value.get('rootBindingSha256'):
        raise RuntimeError('factory root binding changed before imports')


if __name__=='__main__':sealed_imports()

def module(name,path):
    spec=importlib.util.spec_from_file_location(name,path)
    value=importlib.util.module_from_spec(spec);spec.loader.exec_module(value)
    return value

T=module('noble_factory_transaction',HERE/'current-reference-noble-transaction.py')
N=T.N
O=module('noble_factory_observer',HERE/'external-reference-orca.py')
need=T.A.need
DPKG_DEB='/usr/bin/dpkg-deb'
DPKG_DEB_SHA256='fc9dde782ca8309b65ab92e61d13318bf463cd1aa71daa8967b87b81b48b63d2'
# Authenticated ibus-data contains 135,925,760 decoded tar bytes, mostly locales.
# This affects readonly decoding only; archive acquisition limits are unchanged.
IBUS_DATA_SHA256='1a3fac02f9bb69ad32e68e0f9e00fc98cccf2bacf5c9d2f034676a821c266c7c'
LAYER=Path('/opt/fsgg/qualification-layer')
STATE=Path('/etc/fsgg-qualification-runner')
INSTALL_ROOT=Path('/var/lib/fs-gg-current-at')
ROLES={
 'ibusDaemon':('ibus','ibus-daemon'),'ibusConfig':('ibus','ibus-dconf'),
 'pinyinEngine':('ibus-libpinyin','ibus-engine-libpinyin'),'simpleEngine':('ibus','ibus-engine-simple'),
 'dconfService':('dconf-service','dconf-service'),'gtk3':('libgtk-3-0t64','libgtk-3.so.0.'),
 'ibusGtk3':('ibus-gtk3','im-ibus.so'),'setxkbmap':('x11-xkb-utils','setxkbmap'),
 'xkbcomp':('x11-xkb-utils','xkbcomp'),'xdotool':('xdotool','xdotool'),
 'dpkgQuery':('dpkg','dpkg-query'),'glibCompileSchemas':('libglib2.0-0t64','glib-compile-schemas'),
 'gsettings':('libglib2.0-bin','gsettings')}
FACTORY_ROLES={'xvfb':('xvfb','Xvfb'),'openbox':('openbox','openbox'),'xdpyinfo':('x11-utils','xdpyinfo')}
DATA_PACKAGES=('libpinyin-data','xkb-data','libx11-data','ibus-data','ibus-libpinyin','gsettings-desktop-schemas')
POLICY=b'#!/bin/sh\n# Fixed disposable AT factory: do not start services during offline installation.\nexit 101\n'


def load(path,cap=1024**2):
    def unique(pairs):
        result={}
        for key,value in pairs:
            need(key not in result,'duplicate factory input field');result[key]=value
        return result
    return json.loads(T.read(path,cap),object_pairs_hook=unique)


def qualified_scope(software_sha,phase):
    """Root's sealed image/request is data; external admission is never inferred from it."""
    need(phase in ('install-readback','qualify-inputs'),'closed factory phase required')
    need(os.geteuid()==(0 if phase=='install-readback' else 1001),'factory privilege role differs')
    tool=LAYER/'eng/dedicated_qualification_runner.py';info=tool.lstat()
    need(stat.S_ISREG(info.st_mode) and info.st_uid==0 and not info.st_mode&0o022,'AT-capable baked layer absent/mutable')
    C=module('sealed_at_guest_layer',tool)
    need(hasattr(C,'AT_TARGET'),'legacy baked layer cannot admit AT v2; distinct qualified image required')
    binding_path=STATE/'instance-binding.json';info=binding_path.lstat()
    need(stat.S_ISREG(info.st_mode) and info.st_uid==0 and stat.S_IMODE(info.st_mode)==0o644,'sealed root AT binding required')
    binding=C.load(binding_path,131072);lock=C.load(STATE/'acquired-input-lock.json')
    C.validate_registration_data(binding,lock,os.environ.get('RUNNER_NAME'))
    need(binding.get('schema')=='fsgg.dedicated-qualification-instance/2' and binding.get('runnerWorkload')==C.AT_WORKLOAD,
         'only separately admitted AT v2 guest supported')
    need(binding['atSoftwareContractSha256']==software_sha,'selected software contract differs from root seal')
    expected={'GITHUB_REPOSITORY':C.AT_TARGET['repository'],'GITHUB_WORKFLOW_REF':C.AT_TARGET['workflow'],
              'GITHUB_JOB':C.AT_TARGET['job'],'GITHUB_RUN_ATTEMPT':'1','RUNNER_ENVIRONMENT':'self-hosted'}
    need(all(os.environ.get(key)==value for key,value in expected.items()),'actual private AT caller context differs')
    need(re.fullmatch('[0-9a-f]{40}',os.environ.get('GITHUB_SHA','')) and re.fullmatch('[1-9][0-9]*',os.environ.get('GITHUB_RUN_ID','')),
         'actual caller source/run absent')
    need(not any(os.environ.get(key) for key in ['GH_TOKEN','GITHUB_TOKEN','LD_PRELOAD','LD_LIBRARY_PATH','PYTHONPATH']),
         'credentials/loader state must be removed before factory privilege transition')
    uuid=Path('/sys/class/dmi/id/product_uuid').read_text().strip()
    checked=C.verify_guest('/',LAYER,'boot',system_uuid=uuid,runner_name=binding['runnerName'])
    need(not checked['refusals'] and binding['systemUuid']==uuid,'actual qualified guest/layer readback refused')
    if binding['atSoftwareContract']['stage']=='full-current-public-reference':
        O.current_public_at_admission(os.environ)
    return binding,{'bindingSha256':N.sha(binding_path.read_bytes()),'callerSource':os.environ['GITHUB_SHA'],
        'bootId':Path('/proc/sys/kernel/random/boot_id').read_text().strip(),
        'callerRun':int(os.environ['GITHUB_RUN_ID']),'callerAttempt':1,'callerRepository':expected['GITHUB_REPOSITORY'],
        'callerWorkflow':expected['GITHUB_WORKFLOW_REF'],'callerJob':expected['GITHUB_JOB'],
        'outerAuthority':'external Root/provider; not established by JSON or this factory'}


class Owned:
    """Reuse original birth/census/cleanup controls; no stronger containment claim."""
    def __init__(self,directory,deadline):
        self.directory=directory;self.deadline=deadline;self.children=[];self.first=None;self.reporting=[];self.retired=None
        self.supervisor=O.proc(os.getpid())
        need(self.supervisor is not None,'original factory supervisor birth unavailable')
        self.env={'PATH':'/usr/sbin:/usr/bin:/sbin:/bin','LANG':'C.UTF-8','LC_ALL':'C.UTF-8',
            'HOME':str(directory/'home'),'TMPDIR':str(directory/'tmp'),'DEBIAN_FRONTEND':'noninteractive',
            'APT_CONFIG':str(directory/'apt-bootstrap.conf')}
        for name in ['home','tmp']:(directory/name).mkdir(mode=0o700,exist_ok=True)
    def left(self):
        value=self.deadline-time.monotonic();need(value>0,'original factory step deadline exhausted');return value
    def launch(self,argv,name,phase,output_limit=128*1024**2,separate_stderr=False):
        need(type(output_limit) is int and 0<output_limit<=136*1024**2,'bounded factory output required')
        self.left();path=self.directory/(name+'.log')
        (self.directory/(name+'.intent.json')).write_text(json.dumps({'argv':argv,'phase':phase,
            'installationSelected':phase=='offline-installation','runtimeAT':False})+'\n')
        stream=path.open('xb');error_stream=None
        try:
            if separate_stderr:error_stream=(self.directory/(name+'.stderr.log')).open('xb')
            child=subprocess.Popen(argv,stdout=stream,stderr=error_stream or subprocess.STDOUT,env=self.env,start_new_session=True)
        except BaseException:
            stream.close()
            if error_stream:error_stream.close()
            raise
        leader=O.proc(child.pid)
        item={'name':name,'child':child,'stream':stream,'errorStream':error_stream,'leader':leader,'known':{},'outputLimit':output_limit}
        self.children.append(item)
        need(leader and leader['sid']==child.pid,'original factory child birth unavailable')
        item['known'][child.pid]=leader['start'];return item
    def health(self):
        self.left();supervisor=O.proc(self.supervisor['pid'])
        need(O.same_birth(supervisor,self.supervisor) and type(supervisor.get('rss')) is int and supervisor['rss']>=0,
             'original factory supervisor birth/RSS changed or unavailable')
        aggregate={(supervisor['pid'],supervisor['start']):supervisor['rss']}
        for item in self.children:
            if not item['leader']:raise RuntimeError('factory birth unknown')
            owned,unknown,escaped=O.census(item['leader'],item['known'])
            need(not unknown and not escaped,'factory actor custody reported-unverifiable')
            aggregate.update({(row['pid'],row['start']):row['rss'] for row in owned})
            size=(self.directory/(item['name']+'.log')).stat().st_size
            if item.get('errorStream'):size+=(self.directory/(item['name']+'.stderr.log')).stat().st_size
            need(size<=item['outputLimit'],'factory output exceeded')
        need(sum(aggregate.values())<=4*1024**3,'aggregate sampled factory RSS exceeded')
    def command(self,argv,name,phase,cap=4*1024**2,stdout_only=False):
        item=self.launch(argv,name,phase,output_limit=max(cap,128*1024**2),separate_stderr=stdout_only)
        while item['child'].poll() is None:self.health();time.sleep(.05)
        self.health();code=item['child'].returncode
        need(code==0,'original '+name+' exit '+str(code))
        raw=T.read(self.directory/(name+'.log'),cap);self.left()
        return raw
    def finish(self,cause=None):
        if self.retired is not None:
            if cause is not None:
                T.report(self.directory/'partial-failure.json',{'firstCause':str(cause),'phase':'after-original-retirement',
                    'runtimeAT':False,'noCleanupReplay':True},cause)
                raise cause
            return self.retired
        if cause is not None:
            self.first=cause;T.report(self.directory/'partial-failure.json',{'firstCause':str(cause),
                'phase':'before-cleanup','runtimeAT':False,'sampledScopeOnly':True},cause)
        end=min(time.monotonic()+15,self.deadline+15);results=[]
        for item in reversed(self.children):
            original_exit=item['child'].poll()
            if item['leader']:
                try:value=O.cleanup(item['leader'],item['known'],item['child'],seconds=15,absolute_deadline=end)
                except BaseException as error:value={'disposition':'unknown','firstCause':str(error)}
            else:value={'disposition':'unknown','firstCause':'original birth absent'}
            item['child'].poll()
            try:item['stream'].close()
            except BaseException as error:value={'disposition':'unknown','firstCause':str(error)}
            if item.get('errorStream'):
                try:item['errorStream'].close()
                except BaseException as error:value={'disposition':'unknown','firstCause':str(error)}
            results.append({'name':item['name'],'originalExitBeforeCleanup':original_exit,
                            'exitAfterCleanup':item['child'].returncode,'cleanup':value})
        good=all(row['cleanup']['disposition']=='observed-empty' for row in results)
        packet={'scope':'sampled owned process births/groups; detached-descendant/outer-VM limits unchanged',
                'retirement':'observed-empty' if good else 'reported-unverifiable','actors':results,'runtimeAT':False}
        self.retired=packet
        if cause is not None:T.report(self.directory/'retirement.json',packet,cause)
        else:(self.directory/'retirement.json').write_text(json.dumps(packet,indent=2)+'\n')
        if cause is not None:
            if not good:cause.add_note('secondary factory retirement reported-unverifiable')
            raise cause
        need(good,'factory retirement reported-unverifiable')
        return packet


def ar_data(raw):
    need(raw[:8]==b'!<arch>\n','Debian ar header differs');position=8;found=[]
    while position<len(raw):
        head=raw[position:position+60];need(len(head)==60 and head[58:]==b'`\n','Debian ar member malformed')
        name=head[:16].decode().strip().rstrip('/');size=int(head[48:58])
        need(0<=size<=128*1024**2 and position+60+size<=len(raw),'Debian ar size exceeded')
        if name.startswith('data.tar'):found.append((name,raw[position+60:position+60+size]))
        position+=60+size+size%2
    need(position==len(raw) and len(found)==1,'one complete Debian data archive required')
    return found[0]


def archive_records(path,expected,decoder=None):
    raw=T.read(path,128*1024**2);need(N.sha(raw)==expected,'supplied Debian archive digest differs')
    limit=(136 if expected==IBUS_DATA_SHA256 else 128)*1024**2
    name,body=ar_data(raw)
    need(name in ('data.tar','data.tar.zst','data.tar.xz','data.tar.gz','data.tar.bz2'),'unsupported Debian data encoding')
    if name!='data.tar':
        if decoder is not None:
            body=decoder(path,limit)
        elif name.endswith('.zst'):
            try:from compression import zstd
            except ImportError:raise RuntimeError('pinned Noble dpkg-deb decoder required; no tool installation/default')
            stream=zstd.ZstdDecompressor();body=stream.decompress(body,max_length=limit+1)
            need(stream.eof and not stream.unused_data,'complete bounded zstd frame required')
        else:
            stream=(lzma.LZMADecompressor() if name.endswith('.xz') else
                    bz2.BZ2Decompressor() if name.endswith('.bz2') else zlib.decompressobj(31))
            body=stream.decompress(body,limit+1)
            need(stream.eof and not stream.unused_data,'complete bounded Debian compressed stream required')
    need(len(body)<=limit,'Debian data expansion exceeded')
    result={};expanded=0
    with tarfile.open(fileobj=io.BytesIO(body),mode='r:') as archive:
        for index,member in enumerate(archive):
            expanded+=member.size
            need(index<50000 and member.size<=128*1024**2 and expanded<=limit,'Debian member population/expansion exceeded')
            relative=member.name.removeprefix('./').rstrip('/')
            if relative in ('','.'):
                need(member.isdir(),'Debian root member is not a directory')
                continue
            need(not relative.startswith('/') and all(part not in ('','..','.') for part in relative.split('/')),'unsafe Debian member path')
            path='/'+relative;need(path not in result,'duplicate Debian member')
            record={'path':path,'mode':member.mode,'uid':member.uid}
            if member.isfile():
                content=archive.extractfile(member).read(128*1024**2+1)
                need(len(content)==member.size,'Debian member size differs')
                record.update(kind='file',bytes=member.size,sha256=N.sha(content))
            elif member.issym():record.update(kind='symlink',target=member.linkname)
            elif member.isdir():record.update(kind='directory')
            elif member.islnk():record.update(kind='hardlink',target=member.linkname)
            else:raise RuntimeError('unsupported Debian special member')
            result[path]=record
    return result


def pool_inputs(pool,software):
    software_sha=N.sha(N.canonical(software))
    need(pool==Path('/var/lib/fs-gg-current-at-pools')/software_sha and pool==pool.resolve(),
         'fixed root-captured pool required; user preparation is not a privileged input')
    seal_path=pool/'pool-seal.json';info=seal_path.lstat()
    need(stat.S_ISREG(info.st_mode) and info.st_uid==0 and stat.S_IMODE(info.st_mode)==0o644,'root pool seal absent/mutable')
    seal=load(seal_path)
    need(set(seal)=={'schema','softwareContractSha256','files','rootBindingSha256'} and
         seal['schema']=='fsgg.current-reference-pool-seal/1' and seal['softwareContractSha256']==software_sha and
         seal['rootBindingSha256']==N.sha(T.read(STATE/'instance-binding.json',131072)),
         'root-captured pool selection/binding changed')
    need(type(seal['files']) is dict and 1<=len(seal['files'])<=2070,'bounded root-captured population required')
    total=0
    for name,digest in seal['files'].items():
        relative=T.A.relative(name);path=pool/relative
        for ancestor in [path,*path.parents]:
            info=ancestor.lstat()
            need(info.st_uid==0 and not info.st_mode&0o022 and not stat.S_ISLNK(info.st_mode),
                 'captured pool member/ancestor is mutable')
        need(stat.S_ISREG(path.lstat().st_mode),'captured pool member is not regular')
        body=T.read(path,128*1024**2);total+=len(body)
        need(N.sha(body)==digest and total<=768*1024**2,'captured pool content/aggregate differs')
    present={str(path.relative_to(pool)) for path in pool.rglob('*') if path.is_file() or path.is_symlink()}
    need(present==set(seal['files'])|{'pool-seal.json'},'root pool has extra/missing members')
    receipt=load(pool/'frozen-inputs.json')
    need(receipt.get('schema')=='fsgg.current-reference-noble-frozen-inputs/1' and
         receipt.get('originalTransactionSha256')==software['frozenPlan']['transactionSha256'] and
         receipt.get('rootRequestSha256')==software['rootRequestSha256'] and
         receipt.get('declaredArchivesVerified') is True and receipt.get('suppliedOriginalInputsConsistent') is True and
         all(receipt.get(key) is False for key in ['installation','runtimeQualification','actualAT','nativeImeAcceptance']),
         'prepared input scope/digest differs from sealed software selection')
    need(type(receipt.get('selectedRoleBindings')) is list and 1<=len(receipt['selectedRoleBindings'])<=256 and
         (pool/'metadata').is_dir() and (pool/'originals').is_dir(),'self-contained source inputs/role bindings absent')
    original=load(pool/'originals/transaction.json',512*1024)
    need(N.sha(T.read(pool/'originals/transaction.json',512*1024))==software['frozenPlan']['transactionSha256'],
         'original source transaction changed')
    need(receipt['expectedFinalInventory']==original['expectedFinalInventory'] and
         {k:original['expectedFinalInventory'][k] for k in ['packages','sha256']}==software['expectedFinalInventory'],
         'expected installed package state differs')
    rows=receipt['archives'];need(type(rows) is list and 1<=len(rows)<=2048,'bounded prepared archive population required')
    seen=set();total=0
    for row in rows:
        path=T.A.relative(row['path']);need(path not in seen,'duplicate prepared archive');seen.add(path)
        raw=T.read(pool/'archives'/path,T.A.MAX_FILE)
        need(len(raw)==row['bytes'] and N.sha(raw)==row['sha256'],'prepared archive bytes changed')
        total+=len(raw);need(total<=T.A.MAX_TOTAL,'prepared archive population exceeded')
    return receipt,original


def archive_spec(pool,receipt,original,decoder=None):
    """Derive expected regular-file identities from actual authenticated .deb bodies only."""
    bindings={row['package']:row for row in receipt['selectedRoleBindings']}
    for row in original['debs']:
        bindings.setdefault(row['package'],{'package':row['package'],'version':row['version'],
            'binary':{'path':row['filename'],'sha256':row['sha256'],'bytes':row['bytes']},
            'sourceFiles':row['sourceFiles'],'sourcePackage':row['sourcePackage'],'sourceVersion':row['sourceVersion']})
    names=sorted(set(package for package,_ in [*ROLES.values(),*FACTORY_ROLES.values()])|set(DATA_PACKAGES))
    entries={}
    for name in names:
        need(name in bindings,'actual role/data package absent from prepared transaction: '+name)
        binary=bindings[name]['binary'];entries[name]=archive_records(pool/'archives'/binary['path'],binary['sha256'],decoder)
    objects={};factory_objects={}
    for role,(package,leaf) in {**ROLES,**FACTORY_ROLES}.items():
        candidates=[row for row in entries[package].values() if row['kind']=='file' and
            (role in ('gtk3','ibusGtk3') or row['mode']&0o111) and row['path'].startswith('/usr/') and
            (Path(row['path']).name.startswith(leaf) if role=='gtk3' else Path(row['path']).name==leaf)]
        need(len(candidates)==1,'one actual archive role file required: '+role)
        row=candidates[0];need(row['uid']==0 and not row['mode']&0o022,'archive role is not root/nonwritable')
        target=objects if role in ROLES else factory_objects
        target[role]={'path':row['path'],'sha256':row['sha256'],'package':package}
    data=[]
    def include(package,row,kind):
        need(row['kind']=='file' and row['uid']==0 and not row['mode']&0o022,'archive data is not root/nonwritable')
        data.append({'path':row['path'],'sha256':row['sha256'],'package':package,'kind':kind})
    for row in entries['libpinyin-data'].values():
        if row['kind']=='file' and row['path'].startswith('/usr/lib/x86_64-linux-gnu/libpinyin/data/'):include('libpinyin-data',row,'dictionary')
    for path in ['/usr/share/X11/xkb/symbols/us','/usr/share/X11/xkb/symbols/de','/usr/share/X11/xkb/keycodes/evdev']:
        need(path in entries['xkb-data'],'required actual XKB source absent');include('xkb-data',entries['xkb-data'][path],'xkb')
    compose='/usr/share/X11/locale/en_US.UTF-8/Compose'
    need(compose in entries['libx11-data'],'pinned Compose source absent');include('libx11-data',entries['libx11-data'][compose],'compose')
    for package in ['ibus-data','ibus-libpinyin','gsettings-desktop-schemas']:
        for row in entries[package].values():
            if row['kind']=='file' and str(Path(row['path']).parent)==N.TREE_PATHS['schemas'] and row['path'].endswith('.gschema.xml'):
                include(package,row,'schema')
    need({row['kind'] for row in data}=={'dictionary','xkb','schema','compose'} and len(data)<=512,'complete bounded actual data families required')
    return {'objects':objects,'factoryObjects':factory_objects,'dataFiles':sorted(data,key=lambda row:row['path']),'bindings':bindings}


def installed_manifest(spec,runner,software_sha):
    """Read actual ownership/version, keeping derived artifacts outside dpkg-owned rows."""
    packages={};objects={};data=[];factory_objects={}
    query=spec['objects']['dpkgQuery']
    need(N.sha(T.read(Path(query['path']),16*1024**2))==query['sha256'],'installed ownership tool differs before readback')
    rows=[('object',key,row) for key,row in spec['objects'].items()]+[('data',i,row) for i,row in enumerate(spec['dataFiles'])]+[('factory',key,row) for key,row in spec['factoryObjects'].items()]
    paths=sorted({row['path'] for _,_,row in rows})
    need(len(paths)==len(rows),'duplicate expected installed file')
    for path in paths:need(re.fullmatch(r'/usr/[A-Za-z0-9+._/@~-]+',path),'closed installed query path required')
    ownership=runner.command([query['path'],'-S',*paths],'file-owners','installed-readback').decode().splitlines()
    owners={}
    for line in ownership:
        parts=line.rsplit(': ',1);need(len(parts)==2 and parts[1] in paths and parts[1] not in owners,'installed file owner absent/ambiguous')
        owners[parts[1]]=parts[0]
    need(set(owners)==set(paths),'installed ownership population differs')
    owner_names=sorted(set(owners.values()))
    version_rows=runner.command([query['path'],'-W','-f=${binary:Package}\t${Version}\n',*owner_names],
        'owner-versions','installed-readback').decode().splitlines()
    versions={}
    for line in version_rows:
        parts=line.split('\t');need(len(parts)==2 and parts[0] in owner_names and parts[0] not in versions,'installed version population differs')
        versions[parts[0]]=parts[1]
    need(set(versions)==set(owner_names),'installed package version absent')
    for kind,key,row in rows:
        info=Path(row['path']).lstat()
        need(stat.S_ISREG(info.st_mode) and info.st_uid==0 and not info.st_mode&0o022 and
             info.st_size<=128*1024**2 and N.sha(T.read(Path(row['path']),128*1024**2))==row['sha256'],
             'actual installed file differs from signed archive: '+row['path'])
        owner=owners[row['path']];name=owner.removesuffix(':amd64')
        need(name==row['package'] and name in spec['bindings'],'actual installed owner differs from signed package')
        binding=spec['bindings'][name];version=versions[owner]
        need(version==binding['version'],'actual installed package version differs')
        dsc=[source for source in binding['sourceFiles'] if source['path'].endswith('.dsc')]
        need(len(dsc)==1,'one patched source descriptor required')
        package={'name':owner,'version':version,'debSha256':binding['binary']['sha256'],
                 'sourceUri':T.A.BASE+dsc[0]['path'],'sourceSha256':dsc[0]['sha256']}
        need(owner not in packages or packages[owner]==package,'inconsistent installed ownership tuple')
        packages[owner]=package;actual={**row,'package':owner}
        if kind=='object':objects[key]=actual
        elif kind=='factory':factory_objects[key]=actual
        else:data.append(actual)
    schemas=N.tree_identity(N.TREE_PATHS['schemas'],('gschemas.compiled',))
    xkb=N.tree_identity(N.TREE_PATHS['xkb'])
    compiled=Path(N.TREE_PATHS['schemas'])/'gschemas.compiled';info=compiled.lstat()
    need(stat.S_ISREG(info.st_mode) and info.st_uid==0 and not info.st_mode&0o022,'compiled artifact not regular root/nonwritable')
    manifest={'schema':N.SCHEMA2,'platform':'ubuntu-24.04-x11','softwareContractSha256':software_sha,
        'packages':sorted(packages.values(),key=lambda row:row['name']),'objects':objects,'dataFiles':data,
        'dataClosures':{'schemas':{'path':N.TREE_PATHS['schemas'],**schemas},'xkb':{'path':N.TREE_PATHS['xkb'],**xkb}},
        'derivedFiles':{'compiledSchemas':{'path':str(compiled),'sha256':N.sha(T.read(compiled,4*1024**2)),
            'compilerRole':'glibCompileSchemas','inputTreeSha256':schemas['sha256']}},'keymaps':{}}
    return manifest,factory_objects


def phase_clock(seconds):
    try:overall=float(os.environ['FSGG_AT_DEADLINE_MONOTONIC'])
    except (KeyError,ValueError):raise RuntimeError('original private AT overall clock absent')
    now=time.monotonic();need(now<overall<=now+3600,'original private AT clock exhausted/malformed')
    work=min(ENTRY_STARTED+seconds,overall-15);need(work>now,'original step has no work aperture')
    return work,work+15


class OriginalBudget(T.A.Budget):
    def __init__(self,deadline):
        self.clock=time.monotonic;self.deadline=deadline;self.bytes=0;self.requests=0
        self.remaining()


def private_output(out,base):
    base=base.resolve(strict=True)
    need(out.is_absolute() and '..' not in out.parts and out==out.resolve() and
         out==base/'native-at-facility' and not out.exists() and not out.is_symlink(),
         'fresh canonical private runner qualification output required')
    return out


def decoder(runner):
    need(N.sha(T.read(Path(DPKG_DEB),16*1024**2))==DPKG_DEB_SHA256,'installed Noble decoder tool differs')
    count=[0]
    def decode(path,limit):
        count[0]+=1
        return runner.command([DPKG_DEB,'--fsys-tarfile',str(path)],'archive-data-'+str(count[0]),'archive-data-read',limit,stdout_only=True)
    return decode


class ServicePolicy:
    """One fixed guest-only no-start policy; existing different policy is an Unknown."""
    def __init__(self):self.path=Path('/usr/sbin/policy-rc.d');self.created=False;self.identity=None
    def __enter__(self):
        if self.path.exists() or self.path.is_symlink():
            info=self.path.lstat()
            need(stat.S_ISREG(info.st_mode) and info.st_uid==0 and stat.S_IMODE(info.st_mode)==0o755 and
                 T.read(self.path,4096)==POLICY,'existing service policy differs; no replacement')
        else:
            with self.path.open('xb') as stream:stream.write(POLICY)
            self.path.chmod(0o755);self.created=True;info=self.path.lstat()
        self.identity=(info.st_dev,info.st_ino);return self
    def __exit__(self,kind,cause,trace):
        if not self.created:return False
        try:
            info=self.path.lstat()
            need((info.st_dev,info.st_ino)==self.identity and T.read(self.path,4096)==POLICY,
                 'owned service policy changed; retained as reported-unverifiable')
            self.path.unlink()
        except BaseException as secondary:
            if cause is not None:cause.add_note('secondary service-policy retirement: '+str(secondary))
            else:raise
        return False


def install_readback(pool,software_sha):
    binding,context=qualified_scope(software_sha,'install-readback');software=binding['atSoftwareContract']
    T.runtime_guard()
    before=T.inventory(T.read(Path('/var/lib/dpkg/status'),32*1024**2))
    need(len(before)==T.BASE_COUNT and N.sha(T.inventory_bytes(before))==T.BASE_SHA256,'actual live c068 inventory differs before installation')
    receipt,original=pool_inputs(pool,software)
    work=INSTALL_ROOT/software_sha
    need(not work.exists() and not work.is_symlink(),'fresh root factory domain required')
    work.mkdir(parents=True,mode=0o755);deadline,completion=phase_clock(software['resources']['installSeconds'])
    runner=Owned(work,deadline)
    try:
        for name in ['state/lists/partial','cache/archives/partial']:(work/name).mkdir(parents=True,mode=0o700)
        (work/'status').write_bytes(T.read(Path('/var/lib/dpkg/status'),32*1024**2));(work/'extended_states').write_bytes(b'')
        binaries,sources=T.metadata(pool/'metadata',work,OriginalBudget(runner.deadline),Path('/usr/share/keyrings/ubuntu-archive-keyring.gpg'))
        roots=T.request(T.read(HERE/'fixtures/noble-source-prefix-request.json',65536))
        joined=T.frozen_input_plan(pool/'originals',software['frozenPlan']['transactionSha256'],roots,binaries,sources)
        need(receipt['selectedRoleBindings']==T.selected_role_bindings(joined,roots,binaries,sources),
             'prepared role/source identities differ from authenticated signed metadata')
        (work/'sources.list').write_text('\n'.join('deb [signed-by=/usr/share/keyrings/ubuntu-archive-keyring.gpg] '+
            (work/'repo').as_uri()+' '+suite+' main universe' for suite in T.A.RELEASES)+'\n')
        T.bootstrap(work);fixed=T.options(work)
        config=runner.command(['/usr/bin/apt-config',*fixed,'dump'],'live-config','no-install-preflight').decode()
        T.effective_config(config,work)
        update=runner.command(['/usr/bin/apt-get',*fixed,'update'],'live-update','no-install-preflight').decode();T.update_output(update,work)
        simulated=runner.command(['/usr/bin/apt-get',*fixed,'--simulate','--no-install-recommends','install',
            *[row['name']+'='+row['version'] for row in roots['packages']]],'live-simulate','no-install-preflight').decode()
        changes,final=T.frozen(simulated,before,roots,binaries,sources)
        need(changes==original['debs'] and N.sha(T.inventory_bytes(final))==software['expectedFinalInventory']['sha256'],
             'live installed-state proposal differs from the authenticated frozen source inputs')
        inputs=work/'install-debs';inputs.mkdir(mode=0o700);paths=[];copy_budget=OriginalBudget(runner.deadline)
        for row in changes:
            source=pool/'archives'/T.A.relative(row['filename']);parent=source.parent
            while parent!=pool:
                need(not parent.is_symlink(),'installation input ancestor is a symlink');parent=parent.parent
            target=inputs/Path(row['filename']).name
            T.copy_verified_archive(source,target,{'bytes':row['bytes'],'sha256':row['sha256']},copy_budget);paths.append(str(target))
        # APT reads a source-owned config/status snapshot; dpkg writes the actual guest database.
        live=[value.replace('Dir::State::status='+str(work/'status'),'Dir::State::status=/var/lib/dpkg/status') for value in fixed]
        with ServicePolicy():
            runner.command(['/usr/bin/apt-get',*live,'--no-download','--no-remove','--no-install-recommends','--yes','install',*paths],
                'offline-install','offline-installation')
            runner.command(['/usr/bin/apt-get',*live,'check'],'installed-check','installed-readback')
            audit=runner.command(['/usr/bin/dpkg','--audit'],'installed-audit','installed-readback')
            need(not audit.strip(),'installed dpkg state has unfinished/failed packages')
            actual=T.inventory(T.read(Path('/var/lib/dpkg/status'),32*1024**2))
            need(len(actual)==software['expectedFinalInventory']['packages'] and
                 N.sha(T.inventory_bytes(actual))==software['expectedFinalInventory']['sha256'],'actual final inventory differs')
            spec=archive_spec(pool,receipt,original,decoder(runner))
            inputs_before=N.tree_identity(N.TREE_PATHS['schemas'],('gschemas.compiled',))
            compiler=spec['objects']['glibCompileSchemas']
            need(N.sha(T.read(Path(compiler['path']),128*1024**2))==compiler['sha256'],'installed compiler differs before derivation')
            runner.command([compiler['path'],'--strict',N.TREE_PATHS['schemas']],'derive-schemas','schema-derivation')
            need(N.tree_identity(N.TREE_PATHS['schemas'],('gschemas.compiled',))==inputs_before,'schema inputs drifted during compilation')
            draft,factory_objects=installed_manifest(spec,runner,software_sha)
            retirement=runner.finish()
        witness={'schema':'fsgg.current-reference-noble-installed/1','softwareContractSha256':software_sha,
            'originalTransactionSha256':software['frozenPlan']['transactionSha256'],'preparedInputsSha256':N.sha(T.read(pool/'frozen-inputs.json',1024**2)),
            'context':context,'actualInstalledInventory':software['expectedFinalInventory'],'facilityDraft':draft,'factoryObjects':factory_objects,
            'retirement':retirement,'keymaps':'not-observed','actualAT':False,'runtimeQualification':False,
            'completionDeadlineMonotonic':completion}
        need(time.monotonic()<completion,'original install completion deadline exhausted')
        output=work/'installed-inputs.json';output.write_text(json.dumps(witness,indent=2)+'\n');output.chmod(0o644)
        need(time.monotonic()<completion,'original install receipt persistence completed late')
        return witness
    except BaseException as cause:
        runner.finish(cause)
        raise


def qualify_inputs(pool,software_sha,out):
    binding,context=qualified_scope(software_sha,'qualify-inputs');software=binding['atSoftwareContract']
    receipt,original=pool_inputs(pool,software)
    witness_path=INSTALL_ROOT/software_sha/'installed-inputs.json';info=witness_path.lstat()
    need(stat.S_ISREG(info.st_mode) and info.st_uid==0 and stat.S_IMODE(info.st_mode)==0o644,'root installation witness absent/mutable')
    witness=load(witness_path)
    need(witness['softwareContractSha256']==software_sha and witness['context']==context and
         witness['originalTransactionSha256']==software['frozenPlan']['transactionSha256'] and
         witness['preparedInputsSha256']==N.sha(T.read(pool/'frozen-inputs.json',1024**2)) and
         witness['retirement']['retirement']=='observed-empty','root installation/actor evidence differs')
    actual=T.inventory(T.read(Path('/var/lib/dpkg/status'),32*1024**2))
    need(len(actual)==software['expectedFinalInventory']['packages'] and
         N.sha(T.inventory_bytes(actual))==software['expectedFinalInventory']['sha256'],'actual installed inventory changed')
    private_output(out,Path(os.environ['RUNNER_TEMP']))
    out.mkdir(mode=0o700);deadline,completion=phase_clock(software['resources']['keymapSeconds']);runner=Owned(out,deadline)
    runner.env.update(DISPLAY=':97',XDG_DATA_DIRS='/usr/share',XDG_CONFIG_HOME=str(out/'home'),XDG_CACHE_HOME=str(out/'tmp'))
    try:
        spec=archive_spec(pool,receipt,original,decoder(runner))
        manifest,factory_objects=installed_manifest(spec,runner,software_sha)
        need(manifest==witness['facilityDraft'] and factory_objects==witness['factoryObjects'],'installed role/derivation state changed after root handoff')
        for path in ['/tmp/.X97-lock','/tmp/.X11-unix/X97']:need(not Path(path).exists(),'selected factory display occupied; no reuse')
        xvfb=runner.launch([factory_objects['xvfb']['path'],':97','-screen','0','1280x800x24','-nolisten','tcp'],'xvfb','keymap-display')
        # The existing exact readiness predicate authenticates this original Xvfb birth.
        probes=[0]
        def probe(seconds):
            probes[0]+=1
            item=runner.launch([factory_objects['xdpyinfo']['path'],'-display',':97'],
                'display-readiness-'+str(probes[0]),'keymap-display-readiness')
            end=min(deadline,time.monotonic()+seconds)
            while item['child'].poll() is None:
                runner.health();need(time.monotonic()<end,'original display probe deadline exhausted');time.sleep(.05)
            runner.health()
            return item['child'].returncode==0
        O.wait_display_ready(xvfb['child'],probe=probe,absolute_deadline=deadline)
        runner.launch([factory_objects['openbox']['path'],'--sm-disable'],'openbox','keymap-display')
        maps={}
        for layout in ['us','de']:
            runner.command([manifest['objects']['setxkbmap']['path'],'-layout',layout,'-variant','','-option',''],
                'set-layout-'+layout,'keymap-derivation')
            raw=runner.command([manifest['objects']['xkbcomp']['path'],'-xkb',':97','-'],'compiled-keymap-'+layout,'keymap-derivation',stdout_only=True)
            maps[layout]=N.sha(raw)
        manifest['keymaps']=maps;N.manifest(manifest);N.verify_files(manifest)
        retirement=runner.finish()
        need(not Path('/tmp/.X97-lock').exists() and not Path('/tmp/.X11-unix/X97').exists(),
             'original factory display resources remain; reported-unverifiable')
        result={'schema':'fsgg.current-reference-noble-facility-inputs/1','softwareContractSha256':software_sha,
            'rootInstalledWitnessSha256':N.sha(T.read(witness_path,1024**2)),'manifestSha256':N.sha(N.canonical(manifest)),
            'context':context,'actualInstalledInventory':software['expectedFinalInventory'],'retirement':retirement,
            'schemaDerivation':manifest['derivedFiles']['compiledSchemas'],'compiledKeymaps':maps,
            'scope':'actual installed files and retired keymap preparation only; no IME/browser/Orca journey',
            'outerProfileAuthority':'external Root/VM qualification; not inferred from sampled census',
            'actualAT':False,'nativeImeAcceptance':False,'providerMatrixAT':False,'runtimeQualification':False}
        need(time.monotonic()<completion,'original facility completion deadline exhausted')
        (out/'native-input-facility.json').write_bytes(N.canonical(manifest))
        (out/'facility-inputs.json').write_text(json.dumps(result,indent=2)+'\n')
        need(time.monotonic()<completion,'facility output persistence completed late')
        return result
    except BaseException as cause:
        runner.finish(cause)
        raise


def main():
    def interrupted(number,frame):
        raise RuntimeError('original factory interrupted by signal '+str(number))
    for number in (signal.SIGTERM,signal.SIGINT):signal.signal(number,interrupted)
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('phase',choices=['install-readback','qualify-inputs'])
    parser.add_argument('--pool',type=Path,required=True)
    parser.add_argument('--software-contract-sha256',required=True)
    parser.add_argument('--out',type=Path)
    args=parser.parse_args()
    need(re.fullmatch('[0-9a-f]{64}',args.software_contract_sha256),'exact sealed software contract digest required')
    need(args.pool.is_absolute() and not args.pool.is_symlink(),'explicit regular supplied pool root required')
    if args.phase=='install-readback':
        need(args.out is None,'root installation has one fixed contract-bound output domain')
        install_readback(args.pool.resolve(),args.software_contract_sha256)
    else:
        need(args.out is not None,'explicit fresh facility output required')
        qualify_inputs(args.pool.resolve(),args.software_contract_sha256,args.out.absolute())


if __name__=='__main__':main()
