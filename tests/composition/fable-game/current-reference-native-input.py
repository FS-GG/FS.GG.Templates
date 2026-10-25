#!/usr/bin/env python3
"""Selected real X11/IBus inputs. Import/tests launch no desktop or IME.

The authenticated caller supplies the entire facility tuple. This module has no
discovery-to-default, downloaded engine, DOM actuation or acceptance authority.
"""
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import time

SCHEMA = 'fsgg.current-reference-native-input-facility/1'
ROLES = {'ibusDaemon', 'ibusConfig', 'dconfService', 'pinyinEngine', 'simpleEngine',
         'gtk3', 'ibusGtk3', 'setxkbmap', 'xkbcomp', 'xdotool', 'dpkgQuery'}
SETTINGS = {'init-chinese': 'true', 'init-simplified-chinese': 'true',
            'enable-cloud-input': 'false', 'dynamic-adjust': 'false',
            'remember-every-input': 'false'}


def require(value, message):
    if not value:
        raise RuntimeError('native input: ' + message)


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()


def manifest(value):
    """Validate supplied pins only; no local observation is invented here."""
    require(type(value) is dict and set(value) == {'schema', 'platform', 'packages', 'objects', 'dataFiles', 'keymaps'},
            'complete closed facility manifest required')
    require(value['schema'] == SCHEMA and value['platform'] == 'ubuntu-24.04-x11', 'selected Noble X11 facility required')
    require(type(value['packages']) is list and 1 <= len(value['packages']) <= 256, 'package closure absent/bounded')
    names = []
    for row in value['packages']:
        require(set(row) == {'name', 'version', 'debSha256', 'sourceUri', 'sourceSha256'} and
                re.fullmatch(r'[a-z0-9][a-z0-9+.-]*(?::amd64)?', row['name']) and
                type(row['version']) is str and 0 < len(row['version']) <= 128 and
                row['sourceUri'].startswith('https://') and len(row['sourceUri']) <= 512 and
                all(re.fullmatch('[0-9a-f]{64}', row[k]) for k in ['debSha256', 'sourceSha256']),
                'exact package/archive/source tuple absent')
        names.append(row['name'])
    require(len(set(names)) == len(names), 'duplicate package')
    require(set(value['objects']) == ROLES, 'required executable/client identities absent')
    require(type(value['dataFiles']) is list and 4 <= len(value['dataFiles']) <= 512, 'dictionary/keymap/schema/compose closure absent')
    rows = list(value['objects'].values()) + value['dataFiles']
    paths = []
    for row in rows:
        require(set(row) in ({'path', 'sha256', 'package'}, {'path', 'sha256', 'package', 'kind'}) and
                type(row['path']) is str and row['path'].startswith('/usr/') and
                '..' not in Path(row['path']).parts and re.fullmatch('[0-9a-f]{64}', row['sha256']) and
                row['package'] in names, 'package-owned exact file pin absent')
        paths.append(row['path'])
    require(len(paths) == len(set(paths)), 'duplicate facility path')
    require({row.get('kind') for row in value['dataFiles']} == {'dictionary', 'xkb', 'schema', 'compose'}, 'required data families absent')
    require(sum(row['kind'] == 'compose' for row in value['dataFiles']) == 1, 'one exact Compose table required')
    require(set(value['keymaps']) == {'us', 'de'} and all(re.fullmatch('[0-9a-f]{64}', v) for v in value['keymaps'].values()),
            'actual compiled US/German keymap pins absent')
    return value


def read_manifest(raw):
    require(type(raw) is str and 0 < len(raw.encode()) <= 65536, 'facility input missing/oversized')
    def unique(pairs):
        result = {}
        for key, value in pairs:
            require(key not in result, 'duplicate facility field')
            result[key] = value
        return result
    value = json.loads(raw, object_pairs_hook=unique)
    manifest(value)
    return value


def verify_files(value, read=lambda p: Path(p).read_bytes(), inspect=lambda p: Path(p).stat()):
    manifest(value)
    require(b'ID=ubuntu' in read('/etc/os-release') and b'VERSION_ID="24.04"' in read('/etc/os-release'),
            'actual host is not selected Noble')
    for row in [*value['objects'].values(), *value['dataFiles']]:
        info = inspect(row['path'])
        require(stat.S_ISREG(info.st_mode) and info.st_uid == 0 and not info.st_mode & 0o022 and info.st_size <= 256*1024**2,
                'facility file is mutable/nonregular/oversized: ' + row['path'])
        require(sha(read(row['path'])) == row['sha256'], 'facility file bytes differ: ' + row['path'])
    return True


def file_mappings(pid, value, roles, birth, same_birth, proc, read=lambda p: Path(p).read_text()):
    require(same_birth(proc(pid), birth), 'client birth changed before mapping')
    raw = read('/proc/' + str(pid) + '/maps')
    require(len(raw.encode()) <= 4*1024**2, 'client maps exceeded')
    paths = {line.split()[-1] for line in raw.splitlines() if line.split()}
    for role in roles:
        path = str(Path(value['objects'][role]['path']).resolve())
        require(path in paths, 'selected module not loaded: ' + role)
    require(same_birth(proc(pid), birth), 'client birth changed during mapping')
    return {'birth': birth, 'mapsSha256': sha(raw.encode()), 'roles': {role: value['objects'][role] for role in roles}}


def wait_until(predicate, deadline, health, clock=time.monotonic, pause=time.sleep):
    while clock() < deadline:
        health()
        result = predicate()
        require(clock() < deadline, 'late returned native success')
        if result:
            return result
        pause(.05)
    raise RuntimeError('native input: original readiness deadline exhausted')


def start(directory, value, launch, command, query, health, deadline, write, proc, same_birth):
    """Use existing owned launch/budget/cleanup; all services stay foreground."""
    verify_files(value)
    tool = lambda role: value['objects'][role]['path']
    for row in value['packages']:
        actual = query([tool('dpkgQuery'), '-W', '-f=${Version}', row['name']]).strip()
        require(actual == row['version'], 'installed package version differs: ' + row['name'])
    for row in [*value['objects'].values(), *value['dataFiles']]:
        owners = query([tool('dpkgQuery'), '-S', row['path']]).splitlines()
        require(len(owners) == 1 and owners[0].rsplit(': ', 1) == [row['package'], row['path']], 'file package ownership differs/ambiguous')
    home = directory / 'native-home'
    home.mkdir(mode=0o700)
    os.environ.update(HOME=str(home), XCOMPOSEFILE=next(row['path'] for row in value['dataFiles'] if row['kind'] == 'compose'))
    # IBus config is required by PYMain.cc even when Pinyin settings use keyfile.
    # Explicit official services avoid session activation or an ersatz config.
    (directory / 'dconf-profile').write_text('user-db:user\n')
    os.environ['DCONF_PROFILE'] = str(directory / 'dconf-profile')
    route = json.loads((directory / 'owned-bus-route.json').read_text())
    address = 'unix:path=' + str(Path(route['socketRoot']) / 'ibus.sock')
    require(not Path(address.removeprefix('unix:path=')).exists(), 'IBus socket already exists')
    os.environ.update(IBUS_ADDRESS=address, GTK_IM_MODULE='ibus', XMODIFIERS='@im=ibus')
    # --single alone does not disable emoji-extension. No XIM/daemonize/replace/restart.
    daemon = launch([tool('ibusDaemon'), '--single', '--emoji-extension=disable', '--cache=none', '--address=' + address,
                     '--timeout=3000'], 'native-ime-bus')
    import gi
    gi.require_version('IBus', '1.0')
    from gi.repository import IBus, GLib, Gio
    IBus.init()
    bus = IBus.Bus.new()
    wait_until(bus.is_connected, min(deadline, time.monotonic()+10), health)
    owners = {}
    def no_automatic_children():
        tasks = list(Path('/proc/' + str(daemon.pid) + '/task').iterdir())
        require(len(tasks) <= 128, 'IBus task census exceeded')
        require(all(not (task / 'children').read_text().strip() for task in tasks), 'IBus started an unregistered component')
    def owner(name, child):
        # IBus 1.5.29 declares GetConnectionUnixProcessID but its dispatcher
        # returns UnknownMethod. Do not manufacture a PID attribution from it.
        # Bound name appearance to an exact foreground executable birth, with
        # no daemon-spawned components, before selecting any engine.
        no_automatic_children()
        unique = bus.get_name_owner(name)
        if not unique:
            return False
        require(proc(child.pid) is not None and Path('/proc/' + str(child.pid) + '/exe').resolve() ==
                Path(value['objects'][{'org.freedesktop.IBus.Config':'ibusConfig',
                    'org.freedesktop.IBus.Libpinyin':'pinyinEngine', 'org.freedesktop.IBus.Simple':'simpleEngine'}[name]]['path']).resolve(),
                'foreground component executable differs')
        require(name not in owners or owners[name] == unique, 'original IBus unique owner changed')
        owners[name] = unique
        return True
    dconf = launch([tool('dconfService')], 'native-ime-dconf')
    session = Gio.bus_get_sync(Gio.BusType.SESSION, None)
    def dconf_owner():
        health()
        exists = session.call_sync('org.freedesktop.DBus', '/org/freedesktop/DBus', 'org.freedesktop.DBus', 'NameHasOwner',
            GLib.Variant('(s)', ('ca.desrt.dconf',)), GLib.VariantType('(b)'), Gio.DBusCallFlags.NONE, 3000, None).unpack()[0]
        if not exists:
            return False
        actual = session.call_sync('org.freedesktop.DBus', '/org/freedesktop/DBus', 'org.freedesktop.DBus', 'GetConnectionUnixProcessID',
            GLib.Variant('(s)', ('ca.desrt.dconf',)), GLib.VariantType('(u)'), Gio.DBusCallFlags.NONE, 3000, None).unpack()[0]
        require(actual == dconf.pid, 'private dconf owner differs from foreground child')
        return True
    wait_until(dconf_owner, min(deadline, time.monotonic()+10), health)
    require(not bus.get_name_owner('org.freedesktop.IBus.Config'), 'preexisting IBus config owner')
    config = launch([tool('ibusConfig')], 'native-ime-config')
    wait_until(lambda: owner('org.freedesktop.IBus.Config', config), min(deadline, time.monotonic()+10), health)
    command(['gsettings', 'set', 'org.freedesktop.ibus.general', 'use-system-keyboard-layout', 'true'])
    for key, setting in SETTINGS.items():
        command(['gsettings', 'set', 'com.github.libpinyin.ibus-libpinyin', key, setting])
        require(query(['gsettings', 'get', 'com.github.libpinyin.ibus-libpinyin', key]).strip() == setting,
                'private Pinyin setting readback differs')
    require(not bus.get_name_owner('org.freedesktop.IBus.Libpinyin') and not bus.get_name_owner('org.freedesktop.IBus.Simple'),
            'preexisting engine owner; no replace or adoption')
    pinyin = launch([tool('pinyinEngine'), '--ibus'], 'native-ime-pinyin')
    wait_until(lambda: owner('org.freedesktop.IBus.Libpinyin', pinyin), min(deadline, time.monotonic()+10), health)
    simple = launch([tool('simpleEngine')], 'native-ime-simple')
    wait_until(lambda: owner('org.freedesktop.IBus.Simple', simple), min(deadline, time.monotonic()+10), health)
    births = {name: proc(child.pid) for name, child in [('bus', daemon), ('config', config), ('dconf', dconf), ('pinyin', pinyin), ('simple', simple)]}
    def live():
        health()
        require(all(same_birth(proc(v['pid']), v) for v in births.values()), 'original IME service birth changed')
        require(dconf_owner() and owner('org.freedesktop.IBus.Config', config) and owner('org.freedesktop.IBus.Libpinyin', pinyin) and
                owner('org.freedesktop.IBus.Simple', simple), 'original engine/config owner unavailable')
    def select(engine):
        live()
        require(engine in ['libpinyin', 'xkb:de::ger'] and bus.set_global_engine(engine), 'selected actual engine refused')
        wait_until(lambda: bus.get_global_engine() is not None and bus.get_global_engine().get_name() == engine,
                   min(deadline, time.monotonic()+5), live)
        return engine
    def keymap(layout):
        live()
        command([tool('setxkbmap'), '-layout', layout, '-variant', '', '-option', ''])
        raw = query([tool('xkbcomp'), '-xkb', os.environ['DISPLAY'], '-'])
        require(sha(raw.encode()) == value['keymaps'][layout], 'actual compiled keymap differs')
        if layout == 'de':
            require(re.search(r'key\s+<AE12>\s*\{[^}]{0,1024}\[\s*dead_acute\s*,\s*dead_grave', raw) is not None,
                    'German existing dead-key mapping absent')
            require(re.search(r'key\s+<AD03>\s*\{[^}]{0,1024}\[\s*e\s*,\s*E', raw) is not None,
                    'German existing e mapping absent')
        return sha(raw.encode())
    evidence = {'manifestSha256': sha(canonical(value)), 'address': address, 'births': births, 'settings': SETTINGS,
                'uniqueOwners': owners, 'ownerBoundary': 'causal association: foreground birth/executable then stable unique-name appearance; not authenticated bus-connection-to-PID attribution',
                'ibusPidApi': 'not used; upstream dispatcher unsupported; selected package patch level remains pinned by supplier',
                'dataBoundary': 'declared package-owned data rehashed; no claim of per-file read attribution',
                'firstCause': None, 'scope': 'native-input-observation; not installed/provider/whole4817 acceptance'}
    write(directory / 'native-input-runtime.json', evidence)
    return {'select': select, 'keymap': keymap, 'live': live, 'query': query, 'command': command,
            'manifest': value, 'tool': tool, 'evidence': evidence, 'verify': lambda: verify_files(value)}


def target(value):
    note = value['nativeInput']
    require(value['documentHasFocus'] is True and type(note['count']) is int and note['count'] == 1 and note['focused'] is True and
            note['id'] == 'fourd-reference-note' and note['label'] == 'Encounter note' and note['tag'] == 'INPUT',
            'actual generated editable focus differs')
    require(type(note['commandOrder']) is str and len(note['commandOrder']) <= 128 and
            type(note['agentFullCell']) is str and re.fullmatch(r'-?[0-9]+(?::-?[0-9]+){3}', note['agentFullCell']),
            'gameplay observation missing/malformed')
    return note


def validate_phase(before, after, phase):
    a, b = target(before), target(after)
    require(a['commandOrder'] == b['commandOrder'] and a['agentFullCell'] == b['agentFullCell'],
            'native editing dispatched gameplay')
    events = [e for e in b['events'] if e['sequence'] > max([x['sequence'] for x in a['events']], default=0)]
    require(events and all(e['trusted'] is True and e['id'] == 'fourd-reference-note' for e in events), 'fresh trusted target events absent')
    kinds = [e['type'] for e in events]
    require('focusout' not in kinds, 'editable focus was lost during native input')
    sequences = [e['sequence'] for e in events]
    require(all(type(n) is int for n in sequences) and sequences == sorted(set(sequences)), 'native event sequence replayed')
    if phase != 'deadkey':
        require('compositionstart' in kinds and 'compositionupdate' in kinds, 'real preedit absent')
    if phase == 'preedit':
        require(any(e['type'] == 'compositionupdate' and e['data'] for e in events) and 'compositionend' not in kinds,
                'preedit already committed/empty')
    elif phase == 'commit':
        require('compositionend' in kinds and 'input' in kinds and b['value'] == a['value'] + '你好', 'real Pinyin commit absent')
    elif phase == 'cancel':
        require('compositionend' in kinds and b['value'] == a['value'], 'real preedit cancellation changed text')
    elif phase == 'deadkey':
        require(any(e['type'] == 'keydown' and e['key'] == 'Dead' for e in events) and
                'input' in kinds and b['value'] == a['value'] + 'é', 'real composed dead-key result absent')
    else:
        raise RuntimeError('native input: unknown phase')
    return True


def validate_report(report):
    require(report['complete'] is True, 'native journey incomplete/Unknown')
    expected = [*'nihao', 'space', *'nihao', 'Escape', 'dead_acute', 'e']
    keys = report['keys']
    require(type(keys) is list and len(keys) <= 254 and keys[-14:] == expected and all(k == 'Tab' for k in keys[:-14]),
            'original native key route differs')
    requests = report['keyRequests']
    require(type(requests) is list and len(requests) == len(keys) and all(
        set(request) == {'key','returnedZero'} and request['key'] == key and request['returnedZero'] is True
        for request,key in zip(requests,keys)), 'native key request outcome incomplete')
    require(set(report['phases']) == {'commit', 'cancel', 'deadkey'}, 'native phase population incomplete')
    text, prior = '', 0
    for phase in ['commit', 'cancel', 'deadkey']:
        entry = report['phases'][phase]
        before, after = target(entry['before']), target(entry['after'])
        base = max([e['sequence'] for e in before['events']], default=0)
        require(before['value'] == text and before['commandOrder'] == '' and before['agentFullCell'] == '0:0:0:0' and base >= prior,
                'native phase continuity/state differs')
        require(all(e['sequence'] > base for e in after['events']), 'stale native phase event')
        validate_phase(entry['before'], entry['after'], phase)
        if phase != 'deadkey':
            validate_phase(entry['before'], entry['preedit'], 'preedit')
        text = after['value']
        prior = max(e['sequence'] for e in after['events'])
    return True


def journey(runtime, dom, wait, atspi_focused, health, key, retained=None):
    """Only supplied native XTest keys actuate; DOM hooks are capture-only."""
    report = {} if retained is None else retained
    report.update(manifestSha256=runtime['evidence']['manifestSha256'], phases={}, keys=[], keyRequests=[], complete=False)
    keys = report['keys']
    def press(value):
        request = {'key':value,'returnedZero':False}
        report['keyRequests'].append(request)
        key(value)
        request['returnedZero'] = True
        keys.append(value)
    runtime['keymap']('us')
    runtime['select']('libpinyin')
    # Bounded Tab navigation; do not call DOM focus/fill/dispatch/CommitText.
    for _ in range(240):
        health()
        value = dom()
        if value['nativeInput']['focused'] and value['documentHasFocus']:
            break
        press('Tab')
        time.sleep(.05)
    else:
        raise RuntimeError('native input: native Tab did not reach Encounter note')
    require(atspi_focused('Encounter note'), 'AT-SPI editable focus absent')
    original = dom()
    initial = target(original)
    require(initial['commandOrder'] == '' and initial['agentFullCell'] == '0:0:0:0' and initial['value'] == '',
            'fresh generated receiver input state differs')
    phases = report['phases']
    def retained_view(before, after):
        base = max([e['sequence'] for e in before['nativeInput']['events']], default=0)
        def view(value, events):
            return {'documentHasFocus': value['documentHasFocus'], 'nativeInput': {**value['nativeInput'], 'events': events}}
        # Keep the actual sequence boundary and only the new events, avoiding
        # repeated full DOM/event arrays in the original 64KiB custody records.
        return view(before, [{'sequence': base}] if base else []), view(after, [e for e in after['nativeInput']['events'] if e['sequence'] > base])
    for phase, terminal in [('commit', 'space'), ('cancel', 'Escape')]:
        before = dom()
        for letter in 'nihao':
            press(letter)
        preedit = wait(lambda v: any(e['type'] == 'compositionupdate' and e['data'] for e in v['nativeInput']['events']
                            if e['sequence'] > max([x['sequence'] for x in before['nativeInput']['events']], default=0)))
        validate_phase(before, preedit, 'preedit')
        press(terminal)
        after = wait(lambda v: v['nativeInput']['value'] == before['nativeInput']['value'] + ('你好' if phase == 'commit' else '') and
                     any(e['type'] == 'compositionend' for e in v['nativeInput']['events']
                         if e['sequence'] > max([x['sequence'] for x in before['nativeInput']['events']], default=0)))
        validate_phase(before, after, phase)
        require(atspi_focused('Encounter note'), 'AT focus lost after IME phase')
        start, finish = retained_view(before, after)
        phases[phase] = {'before': start, 'preedit': retained_view(before, preedit)[1], 'after': finish}
    german_map = runtime['keymap']('de')
    runtime['select']('xkb:de::ger')
    before = dom()
    press('dead_acute')
    press('e')
    after = wait(lambda v: v['nativeInput']['value'] == before['nativeInput']['value'] + 'é')
    validate_phase(before, after, 'deadkey')
    require(atspi_focused('Encounter note'), 'AT focus lost after dead key')
    require(sha(runtime['query']([runtime['tool']('xkbcomp'), '-xkb', os.environ['DISPLAY'], '-']).encode()) == german_map,
            'native key delivery changed the selected keymap')
    start, finish = retained_view(before, after)
    phases['deadkey'] = {'before': start, 'after': finish}
    runtime['live']()
    runtime['verify']()
    report['complete'] = True
    try:
        validate_report(report)
    except BaseException:
        report['complete'] = False
        raise
    return report
