#!/usr/bin/env python3
"""Mechanical observations against the typed owner's current-composition-plan DTO.

No current package/version/case registry lives here. The qualified ProviderTool
produces the plan; native execution and installed acceptance remain separate.
"""
import json
import os
from pathlib import Path
import re
import sys


CURRENT_COMPOSITION_ADMISSION = None


def check_admission(env):
    require(CURRENT_COMPOSITION_ADMISSION is not None, 'current composition held: no source admission')
    require(env.get('FSGG_CURRENT_COMPOSITION_ADMISSION') == CURRENT_COMPOSITION_ADMISSION, 'current composition owning admission differs')


def require(ok, message):
    if not ok:
        raise ValueError(message)


def selector(plan):
    return '|'.join('(?:^| )'+re.escape(row['title'])+'$' for row in plan['browsers']['cases'])


def validate_report(report, plan, family):
    require(family in plan['browsers']['families'], 'unselected browser family')
    expected=[(row['file'],tuple(row['suite']),row['title']) for row in plan['browsers']['cases']]
    require(expected and len(set(expected))==len(expected),'ambiguous typed case selection')
    stats=report['stats']
    require(stats['expected']==len(expected) and all(stats[key]==0 for key in ('unexpected','skipped','flaky')),'browser outcomes differ')
    def specs(suite, ancestry=()):
        return [(row,ancestry) for row in suite.get('specs',[])]+[item for child in suite.get('suites',[]) for item in specs(child,ancestry+(child['title'],))]
    observed=[item for suite in report['suites'] for item in specs(suite)]
    identities=[(row['file'],ancestry,row['title']) for row,ancestry in observed]
    require(len(identities)==len(expected) and len(set(identities))==len(expected) and set(identities)==set(expected),'browser file/suite/case identity differs')
    for row,_ in observed:
        require(row.get('ok') is True and len(row['tests'])==1,'browser case not uniquely passed')
        test=row['tests'][0]
        require(test['projectName']==family and test['status']=='expected','browser project/status differs')
        require(len(test['results'])==1 and test['results'][0]['status']=='passed' and test['results'][0].get('retry',0)==0,'browser retried or incomplete')
    return True


def validate_inputs(plan, version, source, template_sha):
    require(version==plan['rendering']['version'] and source==plan['rendering']['sourceCommit'],'typed Rendering selection differs')
    require(template_sha==plan['template']['sha256'],'typed template archive selection differs')
    return True


def validate_locked_graph(plan, receiver):
    lock=json.loads((Path(receiver)/'SvgFoundation/packages.lock.json').read_text())
    selected=[{'id':row['id'],'version':plan['rendering']['version'],'lockContentHash':row['lockContentHash']} for row in plan['rendering']['packages']]+[plan['game']]
    require(lock['dependencies'],'generated lock graph absent')
    for dependencies in lock['dependencies'].values():
        for row in selected:
            actual=dependencies[row['id']]
            require(actual['resolved']==row['version'] and actual['contentHash']==row['lockContentHash'],'typed selected lock identity differs: '+row['id'])
    return True


def validate_assets(plan, receiver):
    assets=json.loads((Path(receiver)/'SvgFoundation/obj/project.assets.json').read_text())
    selected=[(row['id'],plan['rendering']['version']) for row in plan['rendering']['packages']]+[(plan['game']['id'],plan['game']['version'])]
    for identity,version in selected:
        require(assets['libraries'][identity+'/'+version]['type']=='package','selected producer is not package-backed: '+identity)
    require({Path(path).resolve() for path in assets['packageFolders']}=={(Path(receiver)/'.nuget/packages').resolve()},'selected producer cache differs')
    return True


def validate_public_readback(plan, readback):
    expected={row['id']:row['sha256'] for row in plan['rendering']['packages']}
    rows=readback['records']
    require(readback['custodySha256']==plan['rendering']['custodySha256'],'typed public custody differs')
    require(len(rows)==len(expected) and len({row['id'] for row in rows})==len(expected),'public archive population differs')
    require(all(row['state']=='matched' and row['rawSha256']==expected[row['id']] for row in rows),'typed public archive identity differs')
    return True


def main():
    action=sys.argv[1]
    if action=='--check-admission':check_admission(os.environ);return
    plan=json.loads(Path(sys.argv[2]).read_text())
    if action=='selector':print(selector(plan))
    elif action=='inputs':validate_inputs(plan,*sys.argv[3:6])
    elif action=='lock':validate_locked_graph(plan,sys.argv[3])
    elif action=='assets':validate_assets(plan,sys.argv[3])
    elif action=='public-readback':validate_public_readback(plan,json.loads(Path(sys.argv[3]).read_text()))
    elif action=='report':validate_report(json.loads(Path(sys.argv[3]).read_text()),plan,sys.argv[4])
    else:raise ValueError('closed mechanical observation action required')


if __name__=='__main__':main()
