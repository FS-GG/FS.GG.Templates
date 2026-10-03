#!/usr/bin/env python3
"""Acquire exact official Rust bytes into Quint 0.32's job-private supported cache.

Acquisition only: this helper never runs Quint, an evaluator or a model. The
compiled Quint 0.32 Linux tool stays pinned by the workflow's existing hash.
Its upstream config.js selects QUINT_HOME/rust-evaluator-v0.6.0/quint_evaluator;
binaryManager.js checks that regular cache executable before fetching. Inspected
0.32 sources have hashes 19b3e12a9f185f306a9a4045626271ddef7cb42702c6bdd913da59548649fab6
and 23fac70fad430d47794a5aa157efa16f754494bf7874970313c8df565cc6a767.
"""
import argparse
import hashlib
import io
import json
import os
from pathlib import Path
import tarfile
import urllib.request
import urllib.parse

QUINT_SHA = '939b64095b706017f2f202c6f99c860c40be7c31bddc2b98557316e50f42cd7f'
REPO = 'quint-co/quint'  # The former informalsystems URL redirects here.
TAG = 'evaluator/v0.6.0'
RELEASE = 303596741
ASSET = 385413317
NAME = 'quint_evaluator-x86_64-unknown-linux-gnu.tar.gz'
SIZE = 1077099
ARCHIVE = '61755a09d5052d93a4e75e840059edfd0d3674aeda164b9d2464be3d6e21b1c2'
MEMBER = 'quint_evaluator'
MEMBER_SIZE = 2628304
MEMBER_SHA = 'b2efdeac5713d153e41bf2143b94ed75d888fdd5637f4a5d61a04c695313510a'
LIMIT = 64 * 1024 * 1024

def need(condition, message):
    if not condition:
        raise ValueError(message)

def sha(body):
    return hashlib.sha256(body).hexdigest()

def metadata(value):
    need(value.get('id') == RELEASE and value.get('tag_name') == TAG and
         value.get('html_url') == f'https://github.com/{REPO}/releases/tag/{TAG}' and
         value.get('draft') is False and value.get('prerelease') is False, 'foreign release tuple')
    assets = [a for a in value.get('assets', []) if a.get('id') == ASSET or a.get('name') == NAME]
    need(len(assets) == 1, 'ambiguous asset')
    a = assets[0]
    need(all(a.get(k) == v for k, v in {
        'id': ASSET, 'name': NAME, 'size': SIZE, 'state': 'uploaded',
        'digest': 'sha256:' + ARCHIVE,
        'url': f'https://api.github.com/repos/{REPO}/releases/assets/{ASSET}',
        'browser_download_url': f'https://github.com/{REPO}/releases/download/{TAG}/{NAME}',
    }.items()), 'foreign asset tuple')
    return a

def binary(body):
    need(len(body) == SIZE and len(body) <= LIMIT and sha(body) == ARCHIVE, 'archive size/digest mismatch')
    with tarfile.open(fileobj=io.BytesIO(body), mode='r:gz') as archive:
        members = archive.getmembers()
        need(len(members) == 1, 'foreign archive members')
        member = members[0]
        need(member.name == MEMBER and member.isreg() and member.size == MEMBER_SIZE,
             'nonregular/foreign archive member')
        data = archive.extractfile(member).read(MEMBER_SIZE + 1)
        need(len(data) == MEMBER_SIZE and sha(data) == MEMBER_SHA, 'binary digest mismatch')
        need(data[:4] == b'\x7fELF', 'non-ELF evaluator')
        return data

class OfficialRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, request, response, code, message, headers, url):
        parsed = urllib.parse.urlsplit(url)
        need(parsed.scheme == 'https' and not parsed.username and not parsed.password and parsed.port in (None, 443) and not parsed.fragment and parsed.hostname in {
            'api.github.com', 'github.com', 'release-assets.githubusercontent.com'}, 'foreign asset redirect')
        redirected = super().redirect_request(request, response, code, message, headers, url)
        if parsed.hostname != 'api.github.com':
            redirected.remove_header('Authorization')
            redirected.unredirected_hdrs.pop('Authorization', None)
        return redirected


def fetch(url, token, accept, maximum):
    request = urllib.request.Request(url, headers={'Authorization': 'Bearer ' + token,
        'Accept': accept, 'User-Agent': 'FS-GG-Templates-pinned-evaluator'})
    with urllib.request.build_opener(OfficialRedirect()).open(request, timeout=60) as response:
        need(response.status == 200, 'official response status')
        body = response.read(maximum + 1)
        need(len(body) <= maximum, 'oversize official response')
        return body


def physical(path):
    need(path.is_absolute() and path.resolve() == path and
         not any(p.is_symlink() for p in [path, *path.parents]), 'physical path required')

def fresh(path, runner, producer):
    physical(path);physical(runner);physical(producer)
    need(runner.is_dir() and path.parent == runner and not path.exists(), 'fresh job-private direct child required')
    need(path != Path.home() and Path.home() / '.quint' not in [path, *path.parents] and
         path != producer and producer not in path.parents, 'global/producer cache forbidden')
    need(runner.stat().st_uid == os.getuid(), 'runner ownership mismatch')

def prepare(quint, home, evidence, runner, producer, token, get=fetch):
    physical(quint)
    need(quint.parent == runner and quint.is_file() and sha(quint.read_bytes()) == QUINT_SHA,
         'wrong compiled Quint 0.32 identity')
    fresh(home, runner, producer);fresh(evidence, runner, producer)
    need(home != evidence and home != quint and evidence != quint, 'overlapping outputs')
    need(os.environ.get('QUINT_HOME') == str(home), 'workflow cache binding mismatch')
    need(bool(token), 'authenticated read-only API token required')
    raw = get(f'https://api.github.com/repos/{REPO}/releases/{RELEASE}', token,
              'application/vnd.github+json', 2 * 1024 * 1024)
    asset = metadata(json.loads(raw))
    body = get(asset['url'], token, 'application/octet-stream', SIZE)
    data = binary(body)
    # All upstream identity checks pass before any owned cache is created.
    home.mkdir(mode=0o700);evidence.mkdir(mode=0o700)
    cache = home / 'rust-evaluator-v0.6.0';cache.mkdir(mode=0o700)
    target = cache / MEMBER
    with target.open('xb') as stream:
        stream.write(data)
    target.chmod(0o700)
    need(not target.is_symlink() and sha(target.read_bytes()) == MEMBER_SHA, 'activated cache drift')
    (evidence/'official-release.json').write_bytes(raw)
    (evidence/NAME).write_bytes(body)
    receipt = {'schema':'fsgg.templates.svg-quint-evaluator-custody/1',
               'role':'acquisition-only-before-unchanged-complete-build',
               'release':RELEASE,'asset':ASSET,'repository':REPO,'tag':TAG,
               'archiveSha256':ARCHIVE,'memberSha256':MEMBER_SHA,
               'compiledQuintVersion':'0.32.0','compiledQuintSha256':QUINT_SHA,
               'quintHome':str(home),'supportedCachePath':str(target),
               'modelsExecuted':False,'qualificationPassed':False}
    (evidence/'custody.json').write_text(json.dumps(receipt,indent=2)+'\n')
    return receipt

def main():
    parser=argparse.ArgumentParser()
    for name in ('quint','quint-home','evidence','runner-temp','producer'):
        parser.add_argument('--'+name,type=Path,required=True)
    a=parser.parse_args()
    prepare(a.quint,a.quint_home,a.evidence,a.runner_temp,a.producer,os.environ.get('GH_TOKEN'))
    print('Pinned official evaluator custody ready; unchanged model qualification still required')

if __name__ == '__main__':
    main()
