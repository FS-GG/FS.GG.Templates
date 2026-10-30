#!/usr/bin/python3
"""Disposable-container readback of installed Noble files. Emits a draft; host authenticates archives."""
import hashlib, json, os, re, stat, subprocess, time
from pathlib import Path

def sha(b): return hashlib.sha256(b).hexdigest()
def out(*a):
    return subprocess.check_output(list(a), text=True)
ROLES={'ibusDaemon':('ibus','ibus-daemon'),'ibusConfig':('ibus','ibus-dconf'),
 'pinyinEngine':('ibus-libpinyin','ibus-engine-libpinyin'),'simpleEngine':('ibus','ibus-engine-simple'),
 'dconfService':('dconf-service','dconf-service'),'gtk3':('libgtk-3-0t64','libgtk-3.so.0.'),
 'ibusGtk3':('ibus-gtk3','im-ibus.so'),'setxkbmap':('x11-xkb-utils','setxkbmap'),
 'xkbcomp':('x11-xkb-utils','xkbcomp'),'xdotool':('xdotool','xdotool'),'dpkgQuery':('dpkg','dpkg-query')}
def files(pkg):
    res=[]
    for line in out('/usr/bin/dpkg-query','-L',pkg).splitlines():
        if not line.startswith('/usr/'): continue
        try: info=os.lstat(line)
        except OSError: continue
        if stat.S_ISREG(info.st_mode): res.append((line,info))
    return res
def row(path,info,pkg,kind=None):
    assert info.st_uid==0 and not info.st_mode&0o022, path
    raw=Path(path).read_bytes()
    r={'path':path,'sha256':sha(raw),'package':pkg}
    if kind: r['kind']=kind
    return r
objects={}
for role,(pkg,leaf) in ROLES.items():
    c=[(p,i) for p,i in files(pkg) if (Path(p).name.startswith(leaf) if role=='gtk3' else Path(p).name==leaf)
       and (role in ('gtk3','ibusGtk3') or i.st_mode&0o111)]
    assert len(c)==1,(role,c)
    objects[role]=row(*c[0],pkg)
data=[]
for p,i in files('libpinyin-data'):
    if p.startswith('/usr/lib/x86_64-linux-gnu/libpinyin/data/'): data.append(row(p,i,'libpinyin-data','dictionary'))
xk=dict(files('xkb-data'))
for p in ['/usr/share/X11/xkb/symbols/us','/usr/share/X11/xkb/symbols/de','/usr/share/X11/xkb/keycodes/evdev']:
    data.append(row(p,xk[p],'xkb-data','xkb'))
cp='/usr/share/X11/locale/en_US.UTF-8/Compose'
data.append(row(cp,dict(files('libx11-data'))[cp],'libx11-data','compose'))
SCH='/usr/share/glib-2.0/schemas'
for pkg in ['ibus-data','ibus','ibus-libpinyin']:
    try: fl=files(pkg)
    except subprocess.CalledProcessError: continue
    for p,i in fl:
        if str(Path(p).parent)==SCH and p.endswith('.gschema.xml'): data.append(row(p,i,pkg,'schema'))
data.sort(key=lambda r:r['path'])
# every selected path is owned by exactly the named package
paths=[r['path'] for r in [*objects.values(),*data]]
own=out('/usr/bin/dpkg-query','-S',*paths).splitlines()
m={}
for l in own:
    pk,pa=l.rsplit(': ',1); m[pa]=pk
for r in [*objects.values(),*data]:
    assert m[r['path']].removesuffix(':amd64')==r['package'],(r,m[r['path']])
    r['package']=m[r['path']]  # exact dpkg -S owner spelling, as the runtime compares it
owners=sorted({r['package'] for r in [*objects.values(),*data]})
pkgs=[]
for n in owners:
    v=out('/usr/bin/dpkg-query','-W','-f=${Version}',n).strip()
    f=Path('/var/cache/apt/archives')/(n.removesuffix(':amd64')+'_'+v.replace(':','%3a')+'_'+out('/usr/bin/dpkg-query','-W','-f=${Architecture}',n).strip()+'.deb')
    if not f.exists():
        import tempfile
        d=tempfile.mkdtemp(); subprocess.run(['apt-get','download',n.removesuffix(':amd64')+'='+v],cwd=d,check=True,stdout=subprocess.DEVNULL)
        f=next(Path(d).glob('*.deb'))
    pkgs.append({'name':n,'version':v,'debSha256':sha(f.read_bytes())})
# keymaps: LIVE dumps from a private Xvfb. A stock Xvfb resets its keyboard to the compiled default when the last
# client disconnects, and setxkbmap is that last client, so a bare `setxkbmap -layout de; xkbcomp -xkb :97 -` reads
# US again. `-noreset` keeps the server (the maintained route has openbox connected for its whole life instead).
# The switch is discriminating: default start, de, back to us, de again; us must equal the default and differ from de.
env=dict(os.environ,DISPLAY=':97')
xv=subprocess.Popen(['/usr/bin/Xvfb',':97','-screen','0','1280x800x24','-nolisten','tcp','-noreset'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
def live_dump():
    return subprocess.run([objects['xkbcomp']['path'],'-xkb',':97','-'],env=env,check=True,capture_output=True).stdout.decode()
def apply(layout):
    subprocess.run([objects['setxkbmap']['path'],'-layout',layout,'-variant','','-option',''],env=env,check=True)
try:
    for _ in range(50):
        if subprocess.run([objects['xkbcomp']['path'],'-xkb',':97','-'],env=env,capture_output=True).returncode==0: break
        time.sleep(0.2)
    start=live_dump(); apply('de'); de=live_dump(); apply('us'); us=live_dump(); apply('de'); de_again=live_dump()
    assert start==us and de==de_again and de!=us, 'live layout switch is not discriminating'
    assert re.search(r'key\s+<AE12>\s*\{[^}]{0,1024}\[\s*dead_acute\s*,\s*dead_grave',de) and re.search(r'key\s+<AD03>\s*\{[^}]{0,1024}\[\s*e\s*,\s*E',de)
    assert not re.search(r'dead_acute',us)
    km={'us':sha(us.encode()),'de':sha(de.encode())}
    keymap_evidence={'method':'live xkbcomp -xkb :97 dump after setxkbmap, Xvfb -noreset','sequence':['start','de','us','de'],
                     'usEqualsServerStart':True,'deDiffersFromUs':True,'deRepeatable':True,'startSha256':sha(start.encode())}
finally:
    xv.terminate(); xv.wait()
Path('/out/draft.json').write_text(json.dumps({'packages':pkgs,'objects':objects,'dataFiles':data,'keymaps':km,'keymapEvidence':keymap_evidence},indent=1,sort_keys=True)+'\n')
print('draft ok', len(pkgs), len(objects), len(data), km)
