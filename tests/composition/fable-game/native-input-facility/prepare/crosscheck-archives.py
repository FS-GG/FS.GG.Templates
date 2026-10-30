import json,subprocess,hashlib,tempfile,os
from pathlib import Path
m=json.load(open('/out/manifest.json')); acq=json.load(open('/acq/acquisition.json'))
by={p['package']:p for p in acq['packages']}
bad=0;n=0
for pkg in m['packages']:
    base=pkg['name'].removesuffix(':amd64')
    deb=Path('/acq/archives')/by[base]['binary']['path']
    assert hashlib.sha256(deb.read_bytes()).hexdigest()==pkg['debSha256']
    d=tempfile.mkdtemp(); subprocess.run(['dpkg-deb','-x',str(deb),d],check=True)
    rows=[r for r in [*m['objects'].values(),*m['dataFiles']] if r['package']==pkg['name']]
    for r in rows:
        f=Path(d)/r['path'].lstrip('/')
        n+=1
        if hashlib.sha256(f.read_bytes()).hexdigest()!=r['sha256']: bad+=1;print('DIFF',r['path'])
print('files cross-checked against signed archives:',n,'mismatch:',bad)
