#!/usr/bin/env python3
"""Actual external-reference Orca journey; --self-test runs only pure/static controls."""
import argparse
import configparser
import shlex
import copy
import contextlib
import hashlib
import json
import importlib.util
import os
from pathlib import Path
import re
import shutil
import signal
import select
import stat
import xml.etree.ElementTree as ET
import subprocess
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[3]
SCHEMA = "fsgg.external-reference-orca-observation/1"
PHRASES = {
    "unknown": "Command sample:1 outcome is unknown.",
    "reconciled": "Original command sample:1 was confirmed accepted.",
    "rearmed": "Commands are ready.",
    "disposed": "Reference disposed. Command evidence is retained; controls are inactive.",
}
TOOLS = ["dbus-run-session", "Xvfb", "openbox", "xdotool", "xprop", "xdpyinfo", "gsettings",
         "pulseaudio", "speech-dispatcher", "orca", "node", "dotnet"]


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, value):
    Path(path).write_text(json.dumps(value, indent=2) + "\n")


def require(condition, message):
    if not condition:
        raise RuntimeError(message)



# Authenticated Ubuntu sources: at-spi2-core2.52.0-1build1 and dbus1.14.10-4ubuntu4.1.
# Vendor SystemdService remains unresolved data. This diagnostic route never activates it.
SOURCE_PROOF = {"atSpiSource": "2.52.0-1build1", "dbusSource": "1.14.10-4ubuntu4.1",
    "atSpiArchiveSha256": "0ac3fc8320c8d01fa147c272ba7fa03806389c6b03d3c406d0823e30e35ff5ab",
    "dbusArchiveSha256": "ba1f21d2bd9d339da2d4aa8780c09df32fea87998b73da24f49ab9df1e36a50f",
    "atSpiPackagingSha256": "20bda0a6815fb1e7c6ca286a02b4b70aaa706f304664aad30bd88a4ee163b91c",
    "dbusPackagingSha256": "c28e0e4840bf3c3f3cbdacae9b7228bb4694dd234f325535942dde76af3c322e",
    "accessorSha256": "f3950265e70f62de3b3b072f52547312b2e4fd770ace3533e7cc88e6b8fdaac1",
    "configParserSha256": "74963b85348c116e9d2d08214a73ad08d825de07ce4be53d49efddf6e9cf914d"}
ROUTE_PATHS = ["/usr/bin/dbus-run-session", "/usr/bin/dbus-daemon", "/usr/libexec/at-spi2-registryd"]
LIBRARY_PREFIXES = ["libatspi.so.", "libatk-bridge-2.0.so."]


def closed_bus_config(socket, uid):
    # Exact serialization, without DTD/entities, includes, service dirs, helpers or activation.
    require(re.fullmatch(r"/tmp/fsgg-at-[a-z0-9_]+/(session|accessibility)\.sock", socket) is not None,
            "private bus socket path unsupported")
    require(type(uid) is int and uid >= 0, "private bus uid unsupported")
    return (f'<busconfig><type>session</type><listen>unix:path={socket}</listen><auth>EXTERNAL</auth>'
            f'<policy context="default"><allow user="{uid}"/><allow own="*"/>'
            '<allow send_destination="*"/><allow receive_sender="*"/></policy></busconfig>\n').encode()


def check_closed_config(raw, socket, uid):
    require(raw == closed_bus_config(socket, uid), "private bus config differs from closed serializer")
    # Equality is the admission guard: all other directives, including both standard_*_servicedirs,
    # include/includedir/servicedir/servicehelper and external entities, are refused.
    require(len(raw) <= 2048 and ET.fromstring(raw).tag == "busconfig", "private bus config malformed")


def route_metadata(packet):
    require(packet.get("schema") == "fsgg.at-activation-provenance/1", "activation packet schema unsupported")
    require(packet.get("sourceProof") == SOURCE_PROOF, "authenticated source correspondence absent")
    versions = packet["versions"]
    for package in ["at-spi2-core", "libatspi2.0-0t64", "libatk-bridge2.0-0t64"]:
        require(versions.get(package) == SOURCE_PROOF["atSpiSource"], "AT source/package version mismatch: " + package)
    for package in ["dbus", "dbus-daemon", "dbus-session-bus-common"]:
        require(versions.get(package) == SOURCE_PROOF["dbusSource"], "D-Bus source/package version mismatch: " + package)
    # Vendor delegation is not silently reclassified as complete. Only that known declaration
    # may remain unresolved; missing ownership, files, independent capture errors still block.
    require(set(packet["services"]) == {"org.a11y.Bus", "org.a11y.atspi.Registry"}, "vendor declarations unavailable")
    require(all(error == "unresolved systemd activation delegation: org.a11y.Bus" for error in packet["errors"]),
            "independent activation metadata incomplete")
    facts = packet["binaries"]
    selected = {}
    for path in ROUTE_PATHS:
        matches = [v for v in facts if v["path"] == path]
        require(len(matches) == 1, "owned route binary missing/ambiguous: " + path)
        selected[path] = matches[0]
    for prefix in LIBRARY_PREFIXES:
        matches = [v for v in facts if Path(v["path"]).name.startswith(prefix)]
        # Symlink aliases can name the same canonical library, but cannot select two objects.
        require(matches and len({(v["resolvedPath"], v["sha256"]) for v in matches}) == 1,
                "AT library identity missing/ambiguous: " + prefix)
        selected[prefix] = matches[0]
    for fact in selected.values():
        require(packet["packageFileManifest"].get(fact["path"]) == fact["package"] and
                packet["packageFileManifest"].get(fact["resolvedPath"]) == fact["package"] and
                re.fullmatch("[0-9a-f]{64}", fact["sha256"]) is not None and 0 < fact["bytes"] <= 32*1024**2,
                "route object ownership/hash unavailable")
    return selected


def check_route_files(packet):
    selected = route_metadata(packet)
    for fact in selected.values():
        require(str(Path(fact["path"]).resolve()) == fact["resolvedPath"] and
                Path(fact["resolvedPath"]).stat().st_size == fact["bytes"] and
                digest(fact["resolvedPath"]) == fact["sha256"], "installed route object changed: " + fact["path"])
    return selected


def check_launch_object(directory, executable):
    selected = check_route_files(json.loads((directory / "activation-provenance.json").read_text()))
    require(executable in ROUTE_PATHS and executable in selected, "unselected route launch")


def descendant_birth(actual, root, reader=None):
    reader = proc if reader is None else reader
    chain = []
    current = actual
    while current is not None and len(chain) < 64:
        require(current["pid"] not in {v["pid"] for v in chain}, "browser ancestry cycle")
        chain.append({k: current[k] for k in ["pid", "start", "ppid", "sid"]})
        if current["pid"] == root["pid"]:
            require(same_birth(current, root), "browser registered ancestor birth changed")
            require(all(same_birth(reader(v["pid"]), v) for v in chain), "browser ancestry changed during read")
            return chain
        current = reader(current["ppid"])
    raise RuntimeError("actual browser is not a live descendant of registered launcher")


def wait_display_ready(child, listener=None, probe=None, clock=time.monotonic, pause=time.sleep, absolute_deadline=None):
    listener = bus_listener if listener is None else listener
    def query(seconds):
        return subprocess.run(["xdpyinfo", "-display", ":97"], stdout=subprocess.DEVNULL,
                              stderr=subprocess.DEVNULL, timeout=seconds, check=False).returncode == 0
    probe = query if probe is None else probe
    deadline = clock() + 15
    if absolute_deadline is not None:
        deadline = min(deadline, absolute_deadline)
    while clock() < deadline:
        require(child.poll() is None, "original X display exited before readiness")
        if listener(child.pid, "/tmp/.X11-unix/X97") and probe(max(.001, deadline-clock())):
            require(child.poll() is None, "original X display exited during readiness")
            return
        pause(.1)
    raise RuntimeError("original X display readiness deadline exceeded")


def session_argv(directory, receiver):
    return ["/usr/bin/dbus-run-session", "--dbus-daemon=/usr/bin/dbus-daemon",
            "--config-file=" + str(directory / "session.conf"), "--", "/usr/bin/python3", "-B",
            str(Path(__file__).resolve()), "--inner", str(receiver), str(directory)]


def same_birth(actual, original):
    return actual is not None and all(actual[k] == original[k] for k in ["pid", "start", "ppid", "sid"])


def require_birth(identity, parent, sid):
    require(identity is not None and identity["ppid"] == parent and identity["sid"] == sid,
            "new AT resource parent/session custody unavailable")


def bus_listener(pid, socket):
    # The filesystem socket alone is not readiness: require the original live leader's FD inode.
    try:
        sockets = {os.readlink(p)[8:-1] for p in Path(f"/proc/{pid}/fd").iterdir()
                   if os.readlink(p).startswith("socket:[")}
        rows = [row.split() for row in Path("/proc/net/unix").read_text().splitlines()[1:]]
        return any(len(row) == 8 and row[3] == "00010000" and row[6] in sockets and row[7] == socket for row in rows)
    except (FileNotFoundError, ProcessLookupError):
        return False


def read_bus_address(child, fd, socket, clock=time.monotonic, pause=time.sleep, absolute_deadline=None):
    deadline = clock() + 15
    if absolute_deadline is not None:
        deadline = min(deadline, absolute_deadline)
    raw = b""
    while clock() < deadline:
        require(child.poll() is None, "original accessibility bus exited before readiness")
        if select.select([fd], [], [], min(.1, max(0, deadline-clock())))[0]:
            data = os.read(fd, 513-len(raw))
            require(data, "accessibility bus address pipe closed")
            raw += data
            require(len(raw) <= 512, "accessibility bus address oversized")
            if b"\n" in raw:
                require(raw.count(b"\n") == 1 and raw.endswith(b"\n"), "accessibility bus address ambiguous")
                address = raw[:-1].decode("ascii")
                require(re.fullmatch(re.escape("unix:path="+socket)+r",guid=[0-9a-f]{32}", address) is not None,
                        "accessibility bus address outside owned socket")
                while clock() < deadline:
                    require(child.poll() is None, "original accessibility bus exited before listener readiness")
                    if bus_listener(child.pid, socket):
                        return address
                    pause(.1)
                break
    raise RuntimeError("original accessibility bus readiness deadline exceeded")


def require_registry_owner(pid, birth):
    require(birth is not None and pid == birth["pid"], "registry name owned by different/preexisting process")


def registry_owner(connection, child, birth, clock=time.monotonic, pause=time.sleep, absolute_deadline=None):
    from gi.repository import Gio, GLib
    deadline = clock() + 15
    if absolute_deadline is not None:
        deadline = min(deadline, absolute_deadline)
    while clock() < deadline:
        require(child.poll() is None and same_birth(proc(child.pid), birth), "original registry birth changed/exited")
        try:
            owner = connection.call_sync("org.freedesktop.DBus", "/org/freedesktop/DBus", "org.freedesktop.DBus",
                    "GetNameOwner", GLib.Variant("(s)", ("org.a11y.atspi.Registry",)), GLib.VariantType("(s)"),
                    Gio.DBusCallFlags.NONE, max(1, int((deadline-clock())*1000)), None).unpack()[0]
        except GLib.Error as ex:
            require("NameHasNoOwner" in str(ex), "registry name query failed: " + str(ex))
            pause(.1)
            continue
        pid = connection.call_sync("org.freedesktop.DBus", "/org/freedesktop/DBus", "org.freedesktop.DBus",
                "GetConnectionUnixProcessID", GLib.Variant("(s)", (owner,)), GLib.VariantType("(u)"),
                Gio.DBusCallFlags.NONE, max(1, int((deadline-clock())*1000)), None).unpack()[0]
        require_registry_owner(pid, birth)
        return {"name": "org.a11y.atspi.Registry", "uniqueOwner": owner, "pid": pid, "birth": birth}
    raise RuntimeError("original registry name readiness deadline exceeded")


# Infrastructure contract from authenticated at-spi2-core2.52.0 bus launcher.
CONTRACT_SOURCE_SHA256 = "08583d7655298336c667bd85bed6dd336d75c89df147844940d6476cc7dafc5e"
CONTRACT_XML = """<node><interface name='org.a11y.Bus'><method name='GetAddress'>
<arg type='s' name='address' direction='out'/></method></interface>
<interface name='org.a11y.Status'><property name='IsEnabled' type='b' access='readwrite'/>
<property name='ScreenReaderEnabled' type='b' access='readwrite'/></interface></node>"""
STATUS_KEYS = {"IsEnabled": ("org.gnome.desktop.interface", "toolkit-accessibility"),
               "ScreenReaderEnabled": ("org.gnome.desktop.a11y.applications", "screen-reader-enabled")}
CONTRACT_PATH = "/org/a11y/bus"


class SessionStatus:
    """Truthful settings adapter; persistence failure is deliberately stricter than upstream."""
    def __init__(self, address, read, persist, emit, health):
        self.address, self.read, self.persist, self.emit, self.health = address, read, persist, emit, health
        self.updating = False
        self.values = {name: self.checked(read(name)) for name in STATUS_KEYS}

    @staticmethod
    def checked(value):
        require(type(value) is bool, "session status is not a boolean")
        return value

    def truthful(self):
        self.health()
        require(all(self.checked(self.read(name)) == value for name, value in self.values.items()),
                "session status backend/cache disagreement")

    def change(self, name, value, persist=True):
        require(name in STATUS_KEYS, "unknown session status property")
        value = self.checked(value)
        if self.values[name] == value:
            return
        # Upstream: only a false-to-true screen-reader transition enables accessibility.
        if name == "ScreenReaderEnabled" and value:
            self.change("IsEnabled", True)
        if persist:
            self.updating = True
            try:
                require(self.persist(name, value) is True, "session status settings write failed")
                require(self.checked(self.read(name)) == value, "session status write/readback mismatch")
            finally:
                self.updating = False
        self.values[name] = value
        self.emit(name, value)

    def external(self, name):
        require(name in STATUS_KEYS, "unknown external settings property")
        if self.updating:
            return
        self.health()
        self.change(name, self.checked(self.read(name)), persist=False)
        self.truthful()

    def dispatch(self, interface, member, parameters):
        self.truthful()
        require(type(parameters) is tuple, "session contract parameters malformed")
        if interface == "org.a11y.Bus" and member == "GetAddress":
            require(parameters == (), "GetAddress takes no arguments")
            return self.address
        require(interface == "org.freedesktop.DBus.Properties", "unknown session contract interface")
        require(member in ["Get", "GetAll", "Set"], "unknown session contract method")
        require(len(parameters) == {"Get": 2, "GetAll": 1, "Set": 3}[member] and parameters[0] == "org.a11y.Status",
                "session status property interface/arity mismatch")
        if member == "GetAll":
            return dict(self.values)
        name = parameters[1]
        require(name in STATUS_KEYS, "unknown session status property")
        if member == "Set":
            self.change(name, parameters[2])
            self.truthful()
            return None
        return self.values[name]


def contract_births(runtime, state, reader=None, listener=None):
    reader = proc if reader is None else reader
    listener = bus_listener if listener is None else listener
    for name, record, socket in [("session", runtime["sessionBus"], state["sockets"]["session"]),
                                 ("accessibility", runtime["bus"], state["sockets"]["accessibility"])]:
        actual = reader(record["pid"])
        require(same_birth(actual, record) and actual.get("state") != "Z" and listener(record["pid"], socket),
                "original " + name + " daemon birth/socket changed")
        address = runtime["sessionAddress"] if name == "session" else runtime["address"]
        require(re.fullmatch(re.escape("unix:path="+socket)+r",guid=[0-9a-f]{32}", address) is not None,
                "original " + name + " address malformed")
    registry = runtime["registry"]["birth"]
    registry_actual = reader(registry["pid"])
    require(same_birth(registry_actual, registry) and registry_actual.get("state") != "Z", "original registry birth changed")


def keyfile_status(directory):
    path = directory / "config/glib-2.0/settings/keyfile"
    require(path.is_file() and path.stat().st_size <= 65536, "private settings keyfile absent/oversized")
    config = configparser.ConfigParser(interpolation=None, strict=True)
    config.read_string(path.read_text())
    values = {}
    for name, (schema, key) in STATUS_KEYS.items():
        section = schema.replace(".", "/")
        raw = config.get(section, key)
        require(raw in ["true", "false"], "private settings keyfile boolean malformed")
        values[name] = raw == "true"
    return values


def require_status_schema(schema, key):
    require(schema is not None and schema.has_key(key) and schema.get_key(key).get_value_type().dup_string() == "b",
            "session status schema/key missing or wrong type")


def status_settings(directory, activation):
    # Native-only; --self-test never imports GI or accesses installed schemas.
    from gi.repository import Gio, GLib
    require(os.environ.get("GSETTINGS_BACKEND") == "keyfile" and
            os.environ.get("XDG_CONFIG_HOME") == str(directory / "config") and
            "GSETTINGS_SCHEMA_DIR" not in os.environ, "session settings route is not private keyfile/default schemas")
    backend = Gio.SettingsBackend.get_default()
    backend_type = backend.__gtype__.name
    require(backend_type == "GKeyfileSettingsBackend", "actual settings backend is not keyfile")
    manifest = activation["packageFileManifest"]
    gio = [v for v in activation["binaries"] if Path(v["path"]).name.startswith("libgio-2.0.so.")]
    require(gio and len({(v["resolvedPath"], v["sha256"]) for v in gio}) == 1, "installed Gio identity absent/ambiguous")
    fact = gio[0]
    require(digest(fact["resolvedPath"]) == fact["sha256"] and activation["versions"].get(fact["package"]), "installed Gio identity/version changed")
    with Path("/proc/self/maps").open() as stream:
        maps = stream.read(4*1024**2+1)
    require(len(maps.encode()) <= 4*1024**2, "actual Gio library mapping oversized")
    require(any(line.split()[-1] == fact["resolvedPath"] for line in maps.splitlines() if line.split()),
            "actual settings Gio library mapping absent")
    settings, facts = {}, {}
    for name, (schema_id, key) in STATUS_KEYS.items():
        paths = [p for p in manifest if Path(p).name == schema_id+".gschema.xml"]
        require(len(paths) == 1, "installed settings schema source absent/ambiguous")
        path = Path(paths[0]); compiled = path.parent / "gschemas.compiled"
        require(not path.is_symlink() and path.stat().st_size <= 256*1024 and not compiled.is_symlink() and
                compiled.is_file() and compiled.stat().st_size <= 4*1024**2,
                "installed settings schema input absent/oversized")
        source = Gio.SettingsSchemaSource.new_from_directory(str(path.parent), None, False)
        schema = source.lookup(schema_id, False)
        require_status_schema(schema, key)
        facts[name] = {"schema": schema_id, "key": key, "type": "b", "sourcePath": str(path),
                       "package": manifest[str(path)], "packageVersion": activation["versions"][manifest[str(path)]], "sourceSha256": digest(path),
                       "compiledPath": str(compiled), "compiledSha256": digest(compiled)}
        settings[name] = Gio.Settings.new_full(schema, backend, None)
    def read(name):
        value = settings[name].get_value(STATUS_KEYS[name][1])
        require(value.get_type_string() == "b", "actual session setting type changed")
        result = value.unpack()
        require(keyfile_status(directory)[name] == result, "private keyfile/Gio readback mismatch")
        return result
    def persist(name, value):
        ok = settings[name].set_boolean(STATUS_KEYS[name][1], value)
        Gio.Settings.sync()
        return ok is True and read(name) == value
    return settings, read, persist, {"backend": backend_type, "backendRoute": "keyfile", "gioObject": fact, "gioPackageVersion": activation["versions"][fact["package"]],
                                    "schemas": facts, "privateKeyfile": str(directory / "config/glib-2.0/settings/keyfile"),
                                    "persistence": "strict refusal on failed write/readback or backend/cache disagreement"}


def bounded_bus_connection(Gio, GLib, address, deadline, clock=time.monotonic):
    """One async connect observed within the remaining original budget; no retry/thread."""
    require(clock() < deadline, "original private bus connection deadline exceeded")
    loop = GLib.MainLoop()
    cancellable = Gio.Cancellable()
    result, errors = [], []
    timer_fired = [False]
    def completed(source, pending, unused):
        try:
            result.append(Gio.DBusConnection.new_for_address_finish(pending))
        except BaseException as ex:
            errors.append(ex)
        loop.quit()
    def expired():
        timer_fired[0] = True
        errors.append(RuntimeError("original private bus connection deadline exceeded"))
        cancellable.cancel()
        loop.quit()
        return False
    timer = GLib.timeout_add(max(1, int((deadline-clock())*1000)), expired)
    primary = None
    try:
        Gio.DBusConnection.new_for_address(address,
            Gio.DBusConnectionFlags.AUTHENTICATION_CLIENT | Gio.DBusConnectionFlags.MESSAGE_BUS_CONNECTION,
            None, cancellable, completed, None)
        loop.run()
        if errors:
            raise errors[0]
        require(clock() < deadline and len(result) == 1 and result[0] is not None,
                "original private bus connection unavailable/deadline exceeded")
        return result[0]
    except BaseException as ex:
        primary = ex
        raise
    finally:
        if not timer_fired[0]:
            try:
                GLib.source_remove(timer)
            except BaseException as report:
                if primary is None:
                    raise
                print("BUS_CONNECTION_REPORT_FAILURE "+type(report).__name__+": "+str(report), file=sys.stderr, flush=True)


def native_gio():
    import gi
    gi.require_version("Gio", "2.0")
    from gi.repository import Gio, GLib
    return Gio, GLib


def contract_call(connection, destination, path, interface, member, parameters, result_type, deadline):
    from gi.repository import Gio, GLib
    require(time.monotonic() < deadline, "original session contract deadline exceeded")
    return connection.call_sync(destination, path, interface, member, GLib.Variant(parameters[0], parameters[1]),
        GLib.VariantType(result_type), Gio.DBusCallFlags.NONE,
        max(1, min(1000, int((deadline-time.monotonic())*1000))), None).unpack()


def contract_query(connection, deadline, health=lambda: None):
    def invoke(interface, member, signature, values, reply, destination="org.freedesktop.DBus", path="/org/freedesktop/DBus"):
        health()
        value = contract_call(connection, destination, path, interface, member, (signature, values), reply, deadline)
        health()
        return value
    owner = invoke("org.freedesktop.DBus", "GetNameOwner", "(s)", ("org.a11y.Bus",), "(s)")[0]
    pid = invoke("org.freedesktop.DBus", "GetConnectionUnixProcessID", "(s)", (owner,), "(u)")[0]
    address = invoke("org.a11y.Bus", "GetAddress", "()", (), "(s)", owner, CONTRACT_PATH)[0]
    values = invoke("org.freedesktop.DBus.Properties", "GetAll", "(s)", ("org.a11y.Status",), "(a{sv})", owner, CONTRACT_PATH)[0]
    return owner, pid, address, values


def contract_ready(connection, child, birth, runtime, state, directory, deadline,
                   query=None, reader=None, listener=None, clock=time.monotonic, pause=time.sleep):
    reader = proc if reader is None else reader
    def health():
        require(clock() < deadline, "original session contract readiness deadline exceeded")
        require(child.poll() is None and same_birth(reader(child.pid), birth), service_first_cause(directory))
        contract_births(runtime, state, reader, listener)
    query = (lambda c, d: contract_query(c, d, health)) if query is None else query
    while clock() < deadline:
        health()
        try:
            owner, pid, address, values = query(connection, deadline)
        except Exception as ex:
            require("NameHasNoOwner" in str(ex), "session contract readiness query failed: " + str(ex))
            pause(.1)
            continue
        require(re.fullmatch(r":\d+\.\d+", owner) is not None and pid == child.pid,
                "session contract name belongs to different/preexisting process")
        require(address == runtime["address"], "session contract returned different original address")
        require(set(values) == set(STATUS_KEYS) and all(type(v) is bool for v in values.values()),
                "session contract typed status readback malformed")
        require(values == keyfile_status(directory), "session contract/private settings readback mismatch")
        contract_births(runtime, state, reader, listener)
        require(child.poll() is None and same_birth(reader(pid), birth), service_first_cause(directory))
        require((directory / "session-contract-state.json").stat().st_size <= 65536, "session contract startup evidence oversized")
        snapshot = json.loads((directory / "session-contract-state.json").read_text())
        require(snapshot["sourceSha256"] == CONTRACT_SOURCE_SHA256 and snapshot["observerSourceSha256"] == digest(Path(__file__).resolve()) and snapshot["initialValues"] == values and
                same_birth(snapshot["birth"], birth), "session contract startup evidence mismatch")
        return {"name": "org.a11y.Bus", "uniqueOwner": owner, "pid": pid, "birth": birth,
                "address": address, "initialValues": values, "settings": snapshot["settings"],
                "sourceSha256": CONTRACT_SOURCE_SHA256, "observerSourceSha256": snapshot["observerSourceSha256"], "parentBirth": snapshot["parentBirth"], "readyBeforeOrca": True}
    raise RuntimeError("original session contract readiness deadline exceeded")


def service_first_cause(directory, fallback="prior required AT service exited"):
    path = directory / "session-contract-failure.json"
    if path.is_file():
        require(path.stat().st_size <= 65536, "session contract failure evidence oversized")
        packet = json.loads(path.read_text())
        leaders = json.loads((directory / "resource-leaders.json").read_text())
        require(any(v["resource"] == "session-contract" and same_birth(packet["birth"], v) for v in leaders),
                "session contract failure birth unregistered")
        return packet["firstCause"]
    log = directory / "session-contract.log"
    if log.is_file() and log.stat().st_size <= 4*1024**2:
        causes = [line[len("SESSION_CONTRACT_FIRST_CAUSE "):] for line in log.read_text(errors="replace").splitlines()
                  if line.startswith("SESSION_CONTRACT_FIRST_CAUSE ")]
        if causes:
            return causes[0]
    return fallback


def required_children(children, directory):
    for child in children:
        code = child.poll()
        if code is not None:
            leaders_path = directory / "resource-leaders.json"
            leaders = json.loads(leaders_path.read_text()) if leaders_path.exists() else []
            role = next((v["resource"] for v in leaders if v["pid"] == getattr(child, "pid", None)), None)
            if role == "browser":
                raise RuntimeError("original Chrome exited before journey completion: "+str(code))
            if role == "browser-companion":
                failure = directory / "browser-companion-failure.json"
                if failure.exists():
                    packet = completion_record(failure)
                    require(any(v["resource"] == role and same_birth(packet["birth"], v) for v in leaders),
                            "browser failure child identity changed")
                    raise RuntimeError(packet["firstCause"])
                log = directory / "browser-companion.log"
                if log.exists() and log.stat().st_size <= 4*1024**2:
                    causes = [line.split("BROWSER_COMPANION_FIRST_CAUSE ", 1)[1] for line in log.read_text(errors="replace").splitlines()
                              if line.startswith("BROWSER_COMPANION_FIRST_CAUSE ")]
                    if causes:
                        raise RuntimeError(causes[0])
                raise RuntimeError("original browser companion exited: "+str(code)+"; specific cause unavailable")
            raise RuntimeError(service_first_cause(directory))


def register_contract_objects(connection, interfaces, method, get_property, set_property, reporting=None):
    registrations = []
    try:
        for interface in interfaces:
            rid = connection.register_object(CONTRACT_PATH, interface, method, get_property, set_property)
            require(type(rid) is int and rid > 0, "session contract object registration failed")
            registrations.append(rid)
        require(len(registrations) == 2, "session contract interface registration incomplete")
        return registrations
    except BaseException:
        for rid in registrations:
            try:
                connection.unregister_object(rid)
            except BaseException as ex:
                if reporting is not None:
                    reporting.append("partial registration cleanup: "+type(ex).__name__+": "+str(ex))
        raise


def claim_contract_name(connection, deadline):
    code = contract_call(connection, "org.freedesktop.DBus", "/org/freedesktop/DBus", "org.freedesktop.DBus",
        "RequestName", ("(su)", ("org.a11y.Bus", 4)), "(u)", deadline)[0]
    require(type(code) is int and code == 1, "session contract owner conflict; no replacement/queue")


def contract_name_health(connection, deadline):
    require(not connection.is_closed(), "original session contract connection closed")
    actual_owner = contract_call(connection, "org.freedesktop.DBus", "/org/freedesktop/DBus", "org.freedesktop.DBus",
        "GetNameOwner", ("(s)", ("org.a11y.Bus",)), "(s)", deadline)[0]
    require(actual_owner == connection.get_unique_name(), "original session contract name lost")


# Completion belongs to the original live child, before dbus-run-session ends the bus.
FINISH_SCHEMA = "fsgg.at-session-contract-finish/1"
FINISH_FILES = ["session-contract-finish-request.json", "session-contract-finish-ack.json",
                "session-contract-completion.json"]


def atomic_record_once(path, value):
    raw = (json.dumps(value, sort_keys=True)+"\n").encode()
    require(len(raw) <= 65536, "session completion record oversized")
    require(not path.exists() and not path.is_symlink(), "duplicate session completion record")
    temporary = path.with_name("."+path.name+".pending")
    first = None
    try:
        with temporary.open("xb") as stream:
            os.chmod(temporary, 0o600)
            stream.write(raw)
            stream.flush()
        # A hard link publishes the complete bytes atomically and refuses an existing destination.
        os.link(temporary, path)
    except BaseException as ex:
        first = ex
        raise
    finally:
        try:
            temporary.unlink(missing_ok=True)
        except BaseException:
            if first is None:
                raise


def completion_record(path):
    require(path.is_file() and not path.is_symlink() and 0 < path.stat().st_size <= 65536,
            "session completion evidence missing/oversized/linked")
    def unique(pairs):
        result = {}
        for key, value in pairs:
            require(key not in result, "duplicate session completion field")
            result[key] = value
        return result
    try:
        value = json.loads(path.read_bytes(), object_pairs_hook=unique)
    except (ValueError, UnicodeError) as ex:
        raise RuntimeError("session completion evidence malformed") from ex
    require(type(value) is dict, "session completion record malformed")
    return value


def completion_birth(birth):
    require(type(birth) is dict and all(type(birth.get(key)) is int and birth[key] > 0
            for key in ["pid", "start", "ppid", "sid"]), "session completion birth malformed")
    return {key: birth[key] for key in ["pid", "start", "ppid", "sid"]}


def completion_identity(directory, runtime, parent, child, unique_owner):
    parent, child = completion_birth(parent), completion_birth(child)
    require(child["ppid"] == parent["pid"] == runtime["bus"]["ppid"] and
            parent["sid"] == child["sid"] == runtime["bus"]["sid"] and
            re.fullmatch(r":\d+\.\d+", unique_owner) is not None, "session completion original custody/owner mismatch")
    budget = completion_record(directory / "session-budget.json")
    require(set(budget) == {"deadline", "seconds"} and type(budget["seconds"]) is int and budget["seconds"] == 300 and
            type(budget["deadline"]) in [int, float] and 0 < budget["deadline"] < float("inf"),
            "original session completion budget malformed")
    # No completion is possible before an actual observation wrote its journey evidence.
    journey = completion_record(directory / "journey.json")
    require(journey, "session completion journey absent")
    return {"parentBirth": parent, "childBirth": child,
            "sessionBusBirth": completion_birth(runtime["sessionBus"]),
            "accessibilityBusBirth": completion_birth(runtime["bus"]),
            "registryBirth": completion_birth(runtime["registry"]["birth"]),
            "sessionAddress": runtime["sessionAddress"], "address": runtime["address"], "uniqueOwner": unique_owner,
            "sourceContractSha256": CONTRACT_SOURCE_SHA256, "observerSourceSha256": digest(Path(__file__).resolve()),
            "sessionBudgetSha256": digest(directory / "session-budget.json"), "deadline": budget["deadline"],
            "journeySha256": digest(directory / "journey.json")}


def completion_request(directory, identity):
    path = directory / FINISH_FILES[0]
    value = completion_record(path)
    require(set(value) == {"schema", "phase", "identity"} and value["schema"] == FINISH_SCHEMA and
            value["phase"] == "request" and value["identity"] == identity,
            "session finish request identity/phase mismatch")
    return value, digest(path)


def complete_contract_child(directory, identity, health, teardown, first_cause=lambda: None,
                            clock=None):
    clock = time.monotonic if clock is None else clock
    require(first_cause() is None, first_cause())
    require(clock() < identity["deadline"], "original session completion deadline exhausted")
    request, request_sha = completion_request(directory, identity)
    require(not (directory / FINISH_FILES[1]).exists(), "duplicate session completion acknowledgment")
    health()
    require(first_cause() is None, first_cause())
    require(clock() < identity["deadline"], "original session completion deadline exhausted before drain")
    teardown()
    require(first_cause() is None, first_cause())
    require(clock() < identity["deadline"], "original session completion deadline exhausted after drain")
    require(digest(directory / FINISH_FILES[0]) == request_sha, "session finish request changed during drain")
    ack = {"schema": FINISH_SCHEMA, "phase": "ack", "identity": identity,
           "requestSha256": request_sha, "teardown": "completed", "firstCause": None}
    atomic_record_once(directory / FINISH_FILES[1], ack)
    return ack


def bounded_connection_close(connection, Gio, GLib, deadline, clock=None):
    clock = time.monotonic if clock is None else clock
    require(clock() < deadline, "original session close deadline exhausted")
    loop, cancellable = GLib.MainLoop(), Gio.Cancellable()
    outcome, timed_out = [], []
    def done(conn, pending, unused):
        try:
            require(connection.close_finish(pending) is True, "session contract close not completed")
            outcome.append(None)
        except BaseException as ex:
            outcome.append(ex)
        loop.quit()
    def expired():
        timed_out.append(True)
        cancellable.cancel()
        loop.quit()
        return False
    timer = GLib.timeout_add(max(1, int((deadline-clock())*1000)), expired)
    primary = None
    try:
        connection.close(cancellable, done, None)
        loop.run()
        require(not timed_out and clock() < deadline, "session contract close deadline/cancellation; completion unknown")
        require(len(outcome) == 1, "session contract close completion unavailable")
        if outcome[0] is not None:
            raise outcome[0]
    except BaseException as ex:
        primary = ex
        raise
    finally:
        try:
            if not timed_out:
                GLib.source_remove(timer)
        except BaseException:
            if primary is None:
                raise


def finish_contract(directory, runtime, child, birth, parent_birth, health,
                    clock=None, pause=None, reader=None):
    clock = time.monotonic if clock is None else clock
    pause = time.sleep if pause is None else pause
    reader = proc if reader is None else reader
    deadline = completion_record(directory / "session-budget.json")["deadline"]
    require(child.poll() is None and same_birth(reader(child.pid), birth), "original session contract exited before finish")
    require(same_birth(reader(parent_birth["pid"]), parent_birth), "original session finish requester birth changed")
    health()
    identity = completion_identity(directory, runtime, parent_birth, birth, runtime["sessionContract"]["uniqueOwner"])
    require(clock() < deadline, "original session completion deadline exhausted before request")
    require(service_first_cause(directory, None) is None, service_first_cause(directory))
    atomic_record_once(directory / FINISH_FILES[0], {"schema": FINISH_SCHEMA, "phase": "request", "identity": identity})
    request_sha = digest(directory / FINISH_FILES[0])
    while clock() < deadline:
        health()
        require(service_first_cause(directory, None) is None, service_first_cause(directory))
        code = child.poll()
        if code is not None:
            # poll/wait act on the original Popen handle; a file cannot establish exit or reaping.
            require(type(code) is int and code == 0 and child.wait(timeout=max(.001, deadline-clock())) == 0,
                    "original session contract completion exit nonzero")
            ack = completion_record(directory / FINISH_FILES[1])
            require(set(ack) == {"schema", "phase", "identity", "requestSha256", "teardown", "firstCause"} and
                    ack["schema"] == FINISH_SCHEMA and ack["phase"] == "ack" and ack["identity"] == identity and
                    ack["requestSha256"] == request_sha and ack["teardown"] == "completed" and ack["firstCause"] is None,
                    "session completion acknowledgment mismatch")
            require(digest(directory / FINISH_FILES[0]) == request_sha, "session finish request changed before reaping")
            require(clock() < deadline, "original session completion deadline exhausted before evidence")
            health()
            result = {"schema": FINISH_SCHEMA, "phase": "reaped", "identity": identity,
                      "requestSha256": request_sha, "ackSha256": digest(directory / FINISH_FILES[1]),
                      "childExit": code, "reaped": True, "firstCause": None}
            atomic_record_once(directory / FINISH_FILES[2], result)
            return result
        require(same_birth(reader(child.pid), birth), "original session contract birth changed during finish")
        pause(min(.1, max(0, deadline-clock())))
    raise RuntimeError("original session completion deadline exhausted waiting for child")


def completion_evidence(directory, runtime, contract):
    snapshot = completion_record(directory / "session-contract-state.json")
    identity = completion_identity(directory, runtime, snapshot["parentBirth"], contract["birth"], contract["uniqueOwner"])
    request, request_sha = completion_request(directory, identity)
    ack = completion_record(directory / FINISH_FILES[1])
    result = completion_record(directory / FINISH_FILES[2])
    require(set(ack) == {"schema", "phase", "identity", "requestSha256", "teardown", "firstCause"} and
            ack["schema"] == FINISH_SCHEMA and ack["phase"] == "ack" and ack["identity"] == identity and
            ack["requestSha256"] == request_sha and ack["teardown"] == "completed" and ack["firstCause"] is None,
            "session completion child acknowledgment unbound")
    require(set(result) == {"schema", "phase", "identity", "requestSha256", "ackSha256", "childExit", "reaped", "firstCause"} and
            result["schema"] == FINISH_SCHEMA and result["phase"] == "reaped" and result["identity"] == identity and
            result["requestSha256"] == request_sha and result["ackSha256"] == digest(directory / FINISH_FILES[1]) and
            type(result["childExit"]) is int and result["childExit"] == 0 and result["reaped"] is True and
            result["firstCause"] is None and contract["completion"] == result,
            "session completion original exit/reap evidence unbound")
    require(service_first_cause(directory, None) is None, "session contract retained original failure")
    return True



def expected_local_close(own_close, remote_peer_vanished, error):
    return own_close is True and remote_peer_vanished is False and error is None


def drain_contract(connection, registrations, deadline, close_started, Gio, GLib):
    for rid in registrations:
        require(connection.unregister_object(rid) is True, "session contract object unregister failed")
    code = contract_call(connection, "org.freedesktop.DBus", "/org/freedesktop/DBus", "org.freedesktop.DBus",
                         "ReleaseName", ("(s)", ("org.a11y.Bus",)), "(u)", deadline)[0]
    require(type(code) is int and code == 1, "session contract name release failed")
    require(not connection.is_closed(), "session contract connection lost before intentional close")
    close_started()
    bounded_connection_close(connection, Gio, GLib, deadline)


def contract_child(directory):
    import gi
    gi.require_version("Gio", "2.0")
    from gi.repository import Gio, GLib
    first, reporting = None, []
    observed_source = digest(Path(__file__).resolve())
    birth = proc(os.getpid())
    parent_birth = proc(os.getppid())
    finished, draining, own_close = False, False, False
    loop, connection, owner, registrations = None, None, False, []
    try:
        runtime = json.loads((directory / "owned-bus-runtime.json").read_text())
        state = json.loads((directory / "owned-bus-route.json").read_text())
        deadline = json.loads((directory / "session-budget.json").read_text())["deadline"]
        contract_births(runtime, state)
        require_birth(birth, os.getppid(), runtime["bus"]["sid"])
        require(parent_birth is not None and parent_birth["pid"] == birth["ppid"], "session contract parent birth unavailable")
        require(time.monotonic() < deadline, "original session contract deadline exceeded")
        require(os.environ["AT_SPI_BUS_ADDRESS"] == runtime["address"] and
                os.environ["DBUS_SESSION_BUS_ADDRESS"] == runtime["sessionAddress"], "session contract original addresses changed")
        connection = bounded_bus_connection(Gio, GLib, runtime["sessionAddress"], min(deadline, time.monotonic()+15))
        settings, read, persist, settings_facts = status_settings(directory, json.loads((directory / "activation-provenance.json").read_text()))
        loop = GLib.MainLoop()
        def fail(ex):
            nonlocal first
            if first is None:
                first = type(ex).__name__+": "+str(ex)
            loop.quit()
        def health():
            require(time.monotonic() < deadline, "original session contract deadline exceeded")
            require(digest(Path(__file__).resolve()) == observed_source, "original observer source changed")
            contract_births(runtime, state)
            require(not connection.is_closed(), "original session contract connection closed")
        def emit(name, value):
            require(connection.emit_signal(None, CONTRACT_PATH, "org.freedesktop.DBus.Properties", "PropertiesChanged",
                GLib.Variant("(sa{sv}as)", ("org.a11y.Status", {name: GLib.Variant("b", value)}, []))),
                "session status notification failed")
        model = SessionStatus(runtime["address"], read, persist, emit, health)
        def method(conn, sender, path, interface, member, parameters, invocation):
            try:
                require(path == CONTRACT_PATH, "unknown session contract object")
                result = model.dispatch(interface, member, parameters.unpack())
                invocation.return_value(GLib.Variant("(s)", (result,)))
            except BaseException as ex:
                fail(ex)
                invocation.return_dbus_error("org.a11y.Bus.Error", first)
        def get_property(conn, sender, path, interface, name):
            try:
                require(path == CONTRACT_PATH, "unknown session contract object")
                return GLib.Variant("b", model.dispatch("org.freedesktop.DBus.Properties", "Get", (interface, name)))
            except BaseException as ex:
                fail(ex)
                return None
        def set_property(conn, sender, path, interface, name, value):
            try:
                require(path == CONTRACT_PATH and value.get_type_string() == "b", "session status Set type/object malformed")
                model.dispatch("org.freedesktop.DBus.Properties", "Set", (interface, name, value.unpack()))
                return True
            except BaseException as ex:
                fail(ex)
                return False
        registrations = register_contract_objects(connection, Gio.DBusNodeInfo.new_for_xml(CONTRACT_XML).interfaces,
                                                   method, get_property, set_property, reporting)
        startup = {"birth": birth, "parentBirth": completion_birth(parent_birth), "observerSourceSha256": observed_source, "sourceSha256": CONTRACT_SOURCE_SHA256,
                   "address": runtime["address"], "sessionAddress": runtime["sessionAddress"],
                   "initialValues": dict(model.values), "settings": settings_facts}
        require(len(json.dumps(startup).encode()) <= 65536, "session contract startup evidence oversized")
        write(directory / "session-contract-state.json", startup)
        claim_contract_name(connection, deadline)
        owner = True
        for name, setting in settings.items():
            def changed(setting, key, name=name):
                try:
                    model.external(name)
                except BaseException as ex:
                    fail(ex)
            setting.connect("changed::"+STATUS_KEYS[name][1], changed)
        def closed(conn, remote_peer_vanished, error):
            # Only the successful locally initiated close is normal. Remote/active errors remain failures.
            if not expected_local_close(own_close, remote_peer_vanished, error):
                fail(RuntimeError("original session contract connection closed"))
        connection.connect("closed", closed)
        def teardown():
            nonlocal draining, own_close, owner, registrations
            draining = True
            def close_started():
                nonlocal own_close
                own_close = True
            drain_contract(connection, registrations, deadline, close_started, Gio, GLib)
            registrations = []
            owner = False
        def monitored():
            nonlocal finished
            if draining:
                return False
            try:
                model.truthful()
                contract_name_health(connection, deadline)
                if (directory / FINISH_FILES[0]).exists():
                    final_runtime = json.loads((directory / "owned-bus-runtime.json").read_text())
                    require(final_runtime["address"] == runtime["address"] and
                            final_runtime["sessionAddress"] == runtime["sessionAddress"] and
                            all(same_birth(final_runtime[key], runtime[key]) for key in ["bus", "sessionBus"]) and
                            same_birth(final_runtime["registry"]["birth"], runtime["registry"]["birth"]) and
                            final_runtime["sessionContract"]["uniqueOwner"] == connection.get_unique_name() and
                            same_birth(final_runtime["sessionContract"]["birth"], birth),
                            "original session completion runtime identity changed")
                    def final_health():
                        require(same_birth(proc(parent_birth["pid"]), parent_birth), "original completion requester birth changed")
                        require(same_birth(proc(birth["pid"]), birth), "original completion child birth changed")
                        model.truthful()
                        contract_name_health(connection, deadline)
                    identity = completion_identity(directory, final_runtime, parent_birth, birth, connection.get_unique_name())
                    complete_contract_child(directory, identity, final_health, teardown, lambda: first)
                    finished = True
                    loop.quit()
                    return False
                return True
            except BaseException as ex:
                fail(ex)
                return False
        GLib.timeout_add(100, monitored)
        require(first is None, first)
        loop.run()
        require(first is None, first)
        require(finished, "session contract exited without original completion")
    except BaseException as ex:
        if first is None:
            first = type(ex).__name__+": "+str(ex)
    finally:
        # Causal state is already in memory; teardown and reporting cannot replace it or bypass parent cleanup.
        try:
            if not finished and connection is not None and not connection.is_closed():
                for rid in registrations:
                    connection.unregister_object(rid)
                if owner:
                    contract_call(connection, "org.freedesktop.DBus", "/org/freedesktop/DBus", "org.freedesktop.DBus",
                        "ReleaseName", ("(s)", ("org.a11y.Bus",)), "(u)", deadline)
                own_close = True
                bounded_connection_close(connection, Gio, GLib, deadline)
        except BaseException as ex:
            reporting.append("teardown: "+type(ex).__name__+": "+str(ex))
            if first is None:
                first = "session contract teardown failed"
        if first is not None:
            print("SESSION_CONTRACT_FIRST_CAUSE "+first, file=sys.stderr, flush=True)
            try:
                write(directory / "session-contract-failure.json", {"birth": birth, "firstCause": first, "reportingErrors": reporting})
            except BaseException as ex:
                reporting.append(type(ex).__name__+": "+str(ex))
                print("SESSION_CONTRACT_REPORT_FAILURE "+reporting[-1], file=sys.stderr, flush=True)
    require(first is None, first)


def contract_evidence(directory, runtime, leaders):
    contract = runtime["sessionContract"]
    require(contract["sourceSha256"] == CONTRACT_SOURCE_SHA256 and contract["readyBeforeOrca"] is True and
            contract["name"] == "org.a11y.Bus" and re.fullmatch(r":\d+\.\d+", contract["uniqueOwner"]) is not None,
            "session contract source/name/readiness absent")
    birth = contract["birth"]
    require(type(contract["pid"]) is int and contract["pid"] == birth["pid"] > 0 and
            birth["sid"] == runtime["bus"]["sid"] and birth["ppid"] == runtime["bus"]["ppid"] and
            any(v["resource"] == "session-contract" and same_birth(v, birth) for v in leaders),
            "session contract birth not registered")
    require(contract["address"] == runtime["address"] and set(contract["initialValues"]) == set(STATUS_KEYS) and
            all(type(v) is bool for v in contract["initialValues"].values()), "session contract initial address/status absent")
    settings = contract["settings"]
    require(settings["backend"] == "GKeyfileSettingsBackend" and settings["backendRoute"] == "keyfile" and
            settings["persistence"] == "strict refusal on failed write/readback or backend/cache disagreement" and
            settings["privateKeyfile"] == str(directory / "config/glib-2.0/settings/keyfile"),
            "session contract settings backend evidence absent")
    activation = json.loads((directory / "activation-provenance.json").read_text())
    gio = settings["gioObject"]
    require(gio in activation["binaries"] and Path(gio["path"]).name.startswith("libgio-2.0.so.") and
            activation["packageFileManifest"].get(gio["path"]) == gio["package"] and
            activation["packageFileManifest"].get(gio["resolvedPath"]) == gio["package"] and
            settings["gioPackageVersion"] == activation["versions"].get(gio["package"]) and bool(settings["gioPackageVersion"]) and
            re.fullmatch(r"[0-9a-f]{64}", gio["sha256"]) is not None,
            "session contract Gio object not captured/package-owned")
    require(set(settings["schemas"]) == set(STATUS_KEYS), "session contract schema inventory incomplete")
    for name, (schema, key) in STATUS_KEYS.items():
        fact = settings["schemas"][name]
        require(fact["schema"] == schema and fact["key"] == key and fact["type"] == "b" and
                Path(fact["sourcePath"]).name == schema+".gschema.xml" and
                activation["packageFileManifest"].get(fact["sourcePath"]) == fact["package"] and
                fact["packageVersion"] == activation["versions"].get(fact["package"]) and bool(fact["packageVersion"]) and
                Path(fact["compiledPath"]) == Path(fact["sourcePath"]).parent / "gschemas.compiled" and
                all(re.fullmatch(r"[0-9a-f]{64}", fact[k]) for k in ["sourceSha256", "compiledSha256"]),
                "session contract schema identity malformed")
    snapshot = json.loads((directory / "session-contract-state.json").read_text())
    require(same_birth(snapshot["birth"], birth) and snapshot["sourceSha256"] == CONTRACT_SOURCE_SHA256 and
            snapshot["observerSourceSha256"] == contract["observerSourceSha256"] == digest(Path(__file__).resolve()) and
            snapshot["address"] == contract["address"] and snapshot["sessionAddress"] == runtime["sessionAddress"] and
            snapshot["initialValues"] == contract["initialValues"] and snapshot["settings"] == settings,
            "session contract startup/runtime evidence mismatch")
    require(service_first_cause(directory, None) is None, "session contract failed during original journey")
    completion_evidence(directory, runtime, contract)
    return True


def route_evidence(directory, packet, receipt):
    selected = route_metadata(packet)
    state = json.loads((directory / "owned-bus-route.json").read_text())
    require(state["sourceProof"] == SOURCE_PROOF and state["uid"] >= 0, "route source identity absent")
    for name in ["session", "accessibility"]:
        socket = state["sockets"][name]
        check_closed_config((directory / (name+".conf")).read_bytes(), socket, state["uid"])
    runtime = json.loads((directory / "owned-bus-runtime.json").read_text())
    require(runtime["addressSetBeforeAtspiImport"] is True and runtime["registry"]["pid"] == runtime["registry"]["birth"]["pid"],
            "private AT address/name-owner binding absent")
    leaders = json.loads((directory / "resource-leaders.json").read_text())
    for name, record in [("accessibility-bus", runtime["bus"]), ("registry", runtime["registry"]["birth"])]:
        require(any(v["resource"] == name and all(v[k] == record[k] for k in ["pid", "start", "ppid", "sid"]) for v in leaders),
                "route birth not registered")
    require(runtime["address"].startswith("unix:path="+state["sockets"]["accessibility"]+",guid="), "runtime address/config mismatch")
    require(runtime["objectIdentities"] == selected, "runtime installed route metadata changed")
    require(runtime["sessionBus"]["sid"] == runtime["bus"]["sid"] and
            runtime["sessionAddress"].startswith("unix:path="+state["sockets"]["session"]+",guid="), "session route binding absent")
    contract_evidence(directory, runtime, leaders)
    for prefix, client in [("libatspi.so.", "observer"), ("libatk-bridge-2.0.so.", "browser")]:
        mapped = runtime["mappedLibraries"][client]
        require(mapped["object"] == selected[prefix] and mapped["birth"]["pid"] > 0, "actual client library mapping absent")
    browser = runtime["mappedLibraries"]["browser"]
    require(browser["birth"]["pid"] == receipt["browser"]["pid"], "browser mapped PID/receipt mismatch")
    chain = browser["ancestry"]
    require(chain and same_birth(chain[0], browser["birth"]) and chain[-1]["pid"] == receipt["browser"]["launcherPid"] and
            len({v["pid"] for v in chain}) == len(chain) and
            all(chain[n]["ppid"] == chain[n+1]["pid"] and chain[n]["sid"] == chain[n+1]["sid"] for n in range(len(chain)-1)) and
            any(v["resource"] == "browser" and same_birth(chain[-1], v) for v in leaders),
            "browser mapping not joined to registered launcher ancestry")
    browser_evidence(directory, receipt, runtime, leaders)
    return True


def prerequisites(packet, preflight, available):
    errors = []
    checks = [
        (lambda: packet["disposition"] == "passed", "generated candidate failed/unknown"),
        (lambda: packet["templates"] == preflight["templates"], "consumer identity mismatch"),
        (lambda: packet["producer"]["revision"] == preflight["producer"]["revision"], "producer identity mismatch"),
        (lambda: packet["producer"]["custodyManifestSha256"] == preflight["producer"]["custodySha256"], "producer custody mismatch"),
        (lambda: preflight["caller"]["repository"] == "FS-GG/FS.GG.Rendering" and re.fullmatch("[0-9a-f]{40}", preflight["caller"]["revision"]) and int(preflight["caller"]["run"]) > 0 and preflight["caller"]["attempt"] == "1", "caller identity unsupported"),
        (lambda: preflight["disposition"] == "preflight-passed" and preflight["requestedPhase"] == "full", "authenticated full input prerequisite absent"),
        (lambda: packet["passedPerFamily"] == 8 and packet["skipped"] == 0 and packet["browserFamilies"] == ["chromium", "firefox", "webkit"], "browser prerequisite incomplete"),
    ]
    for check, message in checks:
        try:
            if not check():
                errors.append(message)
        except (KeyError, TypeError, ValueError):
            errors.append(message + " (malformed)")
    errors += ["tool unavailable: " + name for name in TOOLS if not available(name)]
    return errors


def validate(receipt, packet, preflight, directory):
    """The actual runtime binder, also exercised by finite negative fixtures."""
    require(receipt["schema"] == SCHEMA and receipt["result"] == "passed", "AT result incomplete")
    require(receipt["templates"] == packet["templates"] == preflight["templates"], "consumer mismatch")
    require(receipt["caller"] == preflight["caller"], "caller mismatch")
    require(receipt["producer"] == preflight["producer"], "original producer mismatch")
    require(receipt["process"]["name"] == "orca" and receipt["process"]["pid"] > 0, "actual Orca identity absent")
    require(receipt["browser"]["family"] == "chromium" and receipt["browser"]["pid"] > 0, "headed browser identity absent")
    require(receipt["keyboard"] == "xdotool-X11" and receipt["speechBoundary"] == "Orca SPEECH OUTPUT", "actual AT boundary absent")
    require(receipt["physicalAudioHardware"] == "not-observed", "physical audio claim unsupported")
    require(receipt["cleanup"]["disposition"] == "observed-empty" and receipt["cleanup"]["unknown"] == [] and receipt["cleanup"]["remaining"] == [], "cleanup unknown")
    require(receipt["sourceQualificationSha256"] == digest(directory / "source-qualification.json"), "candidate receipt changed")
    for name, sha in receipt["evidenceSha256"].items():
        require(Path(name).name == name and digest(directory / name) == sha, "AT evidence hash mismatch")
    execution = json.loads((directory / "process-result.json").read_text())
    require(execution["exit"] == 0 and execution["firstCause"] is None and execution["cleanup"] == receipt["cleanup"], "original AT exit/cause/cleanup mismatch")
    require(execution.get("firstGuardCensus") is None, "historical custody uncertainty retained")
    require("activation-provenance.json" in receipt["evidenceSha256"], "activation provenance unbound")
    activation = json.loads((directory / "activation-provenance.json").read_text())
    route_metadata(activation)
    for name in ["owned-bus-route.json", "owned-bus-runtime.json", "session.conf", "accessibility.conf",
                 "session-contract-state.json", "session-budget.json", "journey.json", *FINISH_FILES, *BROWSER_FILES]:
        require(name in receipt["evidenceSha256"], "owned private route evidence unbound")
    route_evidence(directory, activation, receipt)
    sequences = [e["eventSequence"] for e in receipt["actions"]]
    require(sequences == sorted(set(sequences)), "keyboard event replay or ordering drift")
    raw = (directory / "orca-debug.log").read_bytes()
    observations = receipt["observations"]
    for phase, phrase in PHRASES.items():
        entry = observations[phase]
        require(entry["rootCount"] == 1 and entry["statusCount"] == 1, "reference/status identity ambiguous")
        require(entry["speechStart"] < entry["speechEnd"] <= len(raw), "speech range missing")
        speech = "\n".join(line.split("SPEECH OUTPUT:", 1)[1] for line in
                           raw[entry["speechStart"]:entry["speechEnd"]].decode(errors="replace").splitlines()
                           if "SPEECH OUTPUT:" in line)
        require(phrase in speech, "actual " + phase + " speech absent")
        if phase == "unknown":
            require("Commands are suspended" in speech and "reconnect never retries it" in speech, "suspension/no-replay warning not spoken")
    original = {"commandOrder": "sample:1:external.increment", "receiptOrder": "sample:1:unknown",
                "unknownCorrelation": "sample:1", "unknownEpoch": "epoch-A", "commandSuspended": "true"}
    for phase in ["unknown", "reconnected", "prematureRearm"]:
        require(all(observations[phase][key] == value for key, value in original.items()), "unknown command replay or correlation drift")
        require(observations[phase]["unknownGeneration"] == observations["unknown"]["unknownGeneration"], "unknown original generation drift")
    require(observations["reconciled"]["commandRecovery"] == "Reconciled" and
            observations["reconciled"]["commandSuspended"] == "true", "reconciliation silently rearmed")
    require(observations["fresh"]["commandOrder"] == "sample:1:external.increment,sample:2:external.increment" and
            observations["fresh"]["receiptOrder"] == "sample:1:unknown,sample:2:accepted" and
            observations["fresh"]["unknownCorrelation"] == "sample:1", "fresh command identity lost")
    require(all(observations["disposed"][key + "Owned"] == "0" for key in ["command", "gateway", "host", "input", "button", "svg"]), "disposed ownership nonzero")
    require(observations["disposed"]["receiptOrder"] == observations["fresh"]["receiptOrder"] and
            observations["disposed"]["commandOrder"] == observations["fresh"]["commandOrder"], "disposal changed ledger")
    require(all(observations["retainedInert"][key] == observations["disposed"][key] for key in
                ["receiptOrder", "commandOrder", "authorityRevision"] + [name + "Owned" for name in ["command", "gateway", "host", "input", "button", "svg"]]), "retained disposed control had an effect")
    required_actions = ["Mount external authority reference", "Connect sample authority", "Complete current external snapshot",
                        "Lose next command receipt", "Increment external value", "Disconnect sample authority",
                        "Rearm sample commands", "Reconcile unknown command", "Dispose external reference"]
    for name in required_actions:
        require(any(e["name"] == name and e["key"] == "Return" and e["atspiFocused"] and e["directReferenceControl"] for e in receipt["actions"]), "keyboard/AT focus action missing: " + name)
    return True


# The browser companion only records actual state/focus/keys. It never invokes a command.
BROWSER = r'''
'use strict';
const fs=require('node:fs'),path=require('node:path'),crypto=require('node:crypto');
const SCHEMA='fsgg.at-owned-chromium-cdp/1',CAP=4*1024*1024;
function demand(ok,message){if(!ok)throw Error(message)}
const hash=raw=>crypto.createHash('sha256').update(raw).digest('hex');
function deadlineFromBudget(remaining,issued,now=Date.now,clock=()=>performance.now()){
 const elapsed=now()-issued;
 demand(Number.isFinite(remaining)&&remaining>0&&Number.isFinite(issued)&&elapsed>=0&&elapsed<remaining,'original companion deadline expired or clock moved');
 return clock()+remaining-elapsed;
}
function endpointIdentity(value){
 demand(typeof value==='string'&&/^ws:\/\/127\.0\.0\.1:[1-9][0-9]{0,4}\/devtools\/browser\/[A-Za-z0-9-]+$/.test(value),'CDP endpoint identity invalid');
 demand(new URL(value).port&&Number(new URL(value).port)<=65535,'CDP endpoint port invalid');return value;
}
function transportAdapter(endpoint,{Socket=globalThis.WebSocket,deadline,clock=()=>performance.now(),timers={set:setTimeout,clear:clearTimeout},failure=()=>{}}){
 endpointIdentity(endpoint);demand(typeof Socket==='function','selected Node WebSocket unavailable');
 let socket,opened=false,closing=false,closed=false,first=null,callback,queued=[],queuedBytes=0,closeCallback;
 let resolveOpen,rejectOpen,resolveClose;const ready=new Promise((resolve,reject)=>{resolveOpen=resolve;rejectOpen=reject});
 const done=new Promise(resolve=>resolveClose=resolve);let timer;
 function finish(reason){if(closed)return;closed=true;timers.clear(timer);resolveClose();if(closeCallback)closeCallback(reason)}
 function refuse(message,kind='active-failure'){if(first)return;first=message;failure(message,kind);rejectOpen(Error(message));closing=true;try{socket?.close()}catch{}finish(message)}
 function remaining(){const n=deadline-clock();demand(Number.isFinite(n)&&n>0,'original companion deadline expired');return n}
 const transport={
  ready,done,
  get firstCause(){return first},
  send(message){try{
   remaining();demand(!closing&&!closed&&message&&typeof message==='object'&&!Array.isArray(message),'CDP send state or object invalid');
   demand(message.method!=='Browser.close'&&message.method!=='Emulation.setFocusEmulationEnabled','CDP authority-changing command refused');
   const body=JSON.stringify(message),size=Buffer.byteLength(body);demand(size<=CAP,'CDP outgoing message oversized');
   if(opened){demand(socket.bufferedAmount+size<=CAP,'CDP socket buffer exceeded');socket.send(body)}
   else{demand(queuedBytes+size<=CAP,'CDP pending buffer exceeded');queued.push(body);queuedBytes+=size}
  }catch(error){refuse(error.message);throw error}},
  close(){if(closing||closed)return;closing=true;queued=[];queuedBytes=0;timers.clear(timer);timer=timers.set(()=>refuse('CDP close deadline'),Math.min(1000,Math.max(0,deadline-clock())));try{socket.close()}catch(error){refuse('CDP close failed: '+error.message)}},
  get onmessage(){return callback},set onmessage(value){demand(value===undefined||typeof value==='function','CDP message callback invalid');callback=value},
  get onclose(){return closeCallback},set onclose(value){demand(value===undefined||typeof value==='function','CDP close callback invalid');closeCallback=value;if(closed&&value)value(first||'CDP transport closed')}
 };
 try{
  const ms=remaining();timer=timers.set(()=>refuse(closing?'CDP close deadline':'original companion deadline expired'),ms);
  // Node26.10's authenticated built-in WebSocket handshake uses redirect:error; no URL-overload fallback.
  socket=new Socket(endpoint);socket.binaryType='arraybuffer';
  socket.addEventListener('open',()=>{if(closing||closed)return;try{remaining();opened=true;for(const body of queued){demand(socket.bufferedAmount+Buffer.byteLength(body)<=CAP,'CDP socket buffer exceeded');socket.send(body)}queued=[];queuedBytes=0;resolveOpen()}catch(error){refuse(error.message)}});
  socket.addEventListener('message',event=>{try{
   remaining();demand(opened&&!closing&&!closed&&typeof event.data==='string','CDP message state or text invalid');
   demand(Buffer.byteLength(event.data)<=CAP,'CDP incoming message oversized');const value=JSON.parse(event.data);
   demand(value&&typeof value==='object'&&!Array.isArray(value)&&(Number.isInteger(value.id)||typeof value.method==='string'),'CDP message object malformed');
   demand(typeof callback==='function','unsolicited CDP message before attachment');callback(value);
  }catch(error){refuse(error.message)}});
  socket.addEventListener('error',()=>refuse('CDP handshake or transport error (redirect/non101 refused)','transport-error'));
  socket.addEventListener('close',()=>{if(!closing)refuse('CDP transport closed before completion','transport-close');else finish(first)});
 }catch(error){refuse(error.message)}
 return transport;
}
function readBirth(pid){
 const raw=fs.readFileSync('/proc/'+pid+'/stat','utf8'),a=raw.slice(raw.lastIndexOf(')')+2).split(/\s+/);
 return {pid,start:Number(a[19]),ppid:Number(a[1]),pgid:Number(a[2]),sid:Number(a[3])};
}
function sameBirth(a,b){return ['pid','start','ppid','pgid','sid'].every(k=>a[k]===b[k])}
function atomic(file,value){fs.writeFileSync(file+'.tmp',JSON.stringify(value),{flag:'wx',mode:0o600});fs.renameSync(file+'.tmp',file)}
function readInnerResult(file){const fd=fs.openSync(file,fs.constants.O_RDONLY|fs.constants.O_NOFOLLOW);try{const stat=fs.fstatSync(fd);demand(stat.isFile()&&stat.size<=65536,'inner result marker invalid');return fs.readFileSync(fd)}finally{fs.closeSync(fd)}}
function captureInnerResultDigest(file,read=readInnerResult){try{const raw=read(file);return raw.length<=65536?hash(raw):null}catch{return null}}
function realKeyRecorder(){window.__externalKeys=[];window.__externalKeySequence=0;document.addEventListener('keydown',e=>{if(!e.isTrusted)return;
   window.__externalKeys.push({sequence:++window.__externalKeySequence,key:e.key,text:e.target.textContent?.trim(),id:e.target.id,parentId:e.target.parentElement?.id});window.__externalKeys=window.__externalKeys.slice(-128);
  },true)}
async function drainSample(pending,{deadline,clock=()=>performance.now(),timers={set:setTimeout,clear:clearTimeout}}){
 if(!pending)return;const left=Math.min(1000,deadline-clock());demand(left>0,'original sample drain deadline expired');let timer;
 try{await Promise.race([pending,new Promise((_,reject)=>{timer=timers.set(()=>reject(Error('original sample drain unresolved')),left)})])}finally{timers.clear(timer)}
}
async function attachOwnedPage(chromium,transport,remaining,artifactsDir){
  demand(typeof artifactsDir==='string'&&path.isAbsolute(artifactsDir),'private artifacts directory absent');
  const browserConnection=await chromium.connectOverCDP(transport,{noDefaults:true,timeout:remaining(),artifactsDir});
  const contexts=browserConnection.contexts();demand(contexts.length===1,'CDP default context missing or ambiguous');
  const context=contexts[0];context.setDefaultTimeout(remaining());context.setDefaultNavigationTimeout(remaining());
  const pages=context.pages();demand(pages.length===1&&pages[0].url()==='about:blank','CDP initial page missing or ambiguous');const page=pages[0];
  await page.addInitScript(realKeyRecorder);remaining();
  await page.goto('http://127.0.0.1:5100/',{timeout:remaining()});
  await page.getByRole('button',{name:'Mount external authority reference',exact:true}).waitFor({timeout:remaining()});
 return page;
}
async function runCompanion(argv,{getChromium,Socket,clock=()=>performance.now(),now=Date.now}={}){
 demand(process.version==='v26.10.0','selected Node runtime differs');
 const [receiver,out,launchPath,remainingText,issuedText]=argv,started=clock();
 const raw=fs.readFileSync(launchPath);demand(raw.length<=65536,'browser launch evidence oversized');const launch=JSON.parse(raw);
 demand(launch.schema===SCHEMA&&launch.companionSourceSha256===hash(fs.readFileSync(__filename)),'browser companion source changed');
 const deadline=deadlineFromBudget(Number(remainingText),Number(issuedText),now,clock),left=()=>{const n=deadline-clock();demand(n>0,'original companion deadline expired');return n};
 const birth=readBirth(process.pid),browser=readBirth(launch.browserBirth.pid);
 demand(sameBirth(browser,launch.browserBirth)&&birth.ppid===browser.ppid&&birth.sid===browser.sid&&birth.pgid===browser.pgid,'companion/browser original custody differs');
 const profile=fs.lstatSync(launch.profile.path);demand(profile.isDirectory()&&!profile.isSymbolicLink()&&profile.dev===launch.profile.device&&profile.ino===launch.profile.inode&&profile.uid===launch.profile.uid,'companion profile changed');
 const endpointFile=path.join(launch.profile.path,'DevToolsActivePort'),endpointStat=fs.lstatSync(endpointFile),endpointRaw=fs.readFileSync(endpointFile);
 demand(endpointStat.isFile()&&!endpointStat.isSymbolicLink()&&endpointStat.dev===launch.endpoint.file.device&&endpointStat.ino===launch.endpoint.file.inode&&endpointRaw.length===launch.endpoint.file.bytes&&hash(endpointRaw)===launch.endpoint.file.sha256,'companion endpoint file changed');
 const endpoint=endpointIdentity(launch.endpoint.endpoint);let stopping=false,first=null,timer,transport;
 const fail=(message,kind='active-failure')=>{if(first)return;first=message;const innerResultSha256AtFailure=captureInnerResultDigest(path.join(path.dirname(out),'inner-result.json'));try{atomic(path.join(path.dirname(out),'browser-companion-failure.json'),{schema:SCHEMA,birth,firstCause:message,kind,launchSha256:hash(raw),innerResultSha256AtFailure})}catch(report){console.error('BROWSER_COMPANION_REPORT_FAILURE '+report.message)}console.error('BROWSER_COMPANION_FIRST_CAUSE '+message)};
 transport=transportAdapter(endpoint,{Socket,deadline,clock,failure:fail});
 try{
  await transport.ready;left();
  const chromium=getChromium?getChromium():require(path.join(receiver,'Browser.Tests/node_modules/@playwright/test')).chromium;
  const page=await attachOwnedPage(chromium,transport,left,path.dirname(out));
  let sequence=0,sampling=false,pendingSample=null;
  async function sample(){if(stopping||sampling)return;sampling=true;try{left();demand(sameBirth(readBirth(browser.pid),browser),'original browser birth changed during sampling');const value=await page.evaluate(()=>{
   const root=document.querySelector('#external-authority-reference'),active=document.activeElement;
   return {documentHasFocus:document.hasFocus(),active:{text:active?.textContent?.trim(),id:active?.id,parentId:active?.parentElement?.id},reference:root?{...Object.fromEntries([...root.attributes].filter(a=>a.name.startsWith('data-')).map(a=>[a.name.slice(5).replace(/-([a-z])/g,(_,c)=>c.toUpperCase()),a.value])),rootCount:document.querySelectorAll('#external-authority-reference').length,statusCount:root.querySelectorAll(':scope > [role="status"]').length,status:root.querySelector(':scope > [role="status"]')?.textContent,directButtons:[...root.querySelectorAll(':scope > button')].map(b=>b.textContent)}:null,keys:window.__externalKeys};
  });left();atomic(out,{sequence:++sequence,at:now(),...value})}finally{sampling=false}}
  await sample();demand(page.url()==='http://127.0.0.1:5100/','owned server navigation changed');
  atomic(path.join(path.dirname(out),'browser-companion-ready.json'),{schema:SCHEMA,launchSha256:hash(raw),browserBirth:browser,companionBirth:birth,endpoint,profile:launch.profile,sourceSha256:hash(fs.readFileSync(__filename)),noDefaults:true,contexts:1,initialPages:1,initialURL:'about:blank',pageURL:page.url(),sampleSequence:sequence,setupMilliseconds:clock()-started});
  timer=setInterval(()=>{if(stopping||sampling)return;pendingSample=sample();pendingSample.catch(error=>{fail(error.message);transport.close();process.exitCode=1})},100);
  const stop=async()=>{if(stopping)return;stopping=true;clearInterval(timer);await drainSample(pendingSample,{deadline,clock});transport.close();await transport.done;process.exit(first?1:0)};
  process.on('SIGTERM',()=>stop().catch(error=>{fail(error.message);process.exit(1)}));process.on('SIGINT',()=>stop().catch(error=>{fail(error.message);process.exit(1)}));
  await transport.done;
  if(!stopping)throw Error(transport.firstCause||'CDP disconnected before cleanup');
 }catch(error){fail(error.message);clearInterval(timer);transport.close();throw error}
}
async function adapterSelfTest(){
 demand(process.version==='v26.10.0','selected inert Node runtime differs');
 const checked=[];function caseName(name,work){work();checked.push(name)}
 function refused(work){let caught=false;try{work()}catch{caught=true}demand(caught,'invalid adapter state accepted')}
 class FakeSocket{
  static all=[];constructor(url){this.url=url;this.listeners={};this.sent=[];this.bufferedAmount=0;this.closeCalls=0;FakeSocket.all.push(this)}
  addEventListener(name,fn){this.listeners[name]=fn}send(body){this.sent.push(body)}close(){this.closeCalls++;this.listeners.close?.({})}emit(name,value={}){this.listeners[name]?.(value)}
 }
 const endpoint='ws://127.0.0.1:1234/devtools/browser/fixture';let callbacks=[];
 function fixture(){callbacks=[];const failures=[],transport=transportAdapter(endpoint,{Socket:FakeSocket,deadline:100,clock:()=>0,timers:{set:fn=>{callbacks.push(fn);return 1},clear:()=>{}},failure:(message,kind)=>failures.push({message,kind})});transport.ready.catch(()=>{});return {transport,socket:FakeSocket.all.at(-1),failures}}
 caseName('adapter-event-captures-existing-success-bytes',()=>{const raw=Buffer.from('{"exit":0}');demand(captureInnerResultDigest('/private/result',()=>raw)===hash(raw),'event marker digest drift')});
 caseName('adapter-event-missing-marker-unknown',()=>demand(captureInnerResultDigest('/private/result',()=>{throw Error('absent')})===null,'missing marker became success'));
 caseName('adapter-event-oversized-marker-unknown',()=>demand(captureInnerResultDigest('/private/result',()=>Buffer.alloc(65537))===null,'oversized marker became success'));
 caseName('adapter-budget-subtracts-setup',()=>demand(deadlineFromBudget(100,1000,()=>1030,()=>50)===120,'setup time borrowed'));
 for(const [name,remaining,issued,now] of [['expired',10,1000,1010],['backward-clock',10,1000,999],['nonfinite',NaN,1000,1000]])caseName('adapter-budget-'+name,()=>refused(()=>deadlineFromBudget(remaining,issued,()=>now,()=>0)));
 for(const value of ['ws://localhost:1234/devtools/browser/a','wss://127.0.0.1:1234/devtools/browser/a','ws://127.0.0.1:65536/devtools/browser/a','ws://127.0.0.1:1234/devtools/browser/a?redirect=x'])caseName('adapter-endpoint-refusal-'+checked.length,()=>refused(()=>endpointIdentity(value)));
 caseName('adapter-success-object-forwarding',()=>{const {transport,socket}=fixture();let seen;transport.onmessage=value=>seen=value;transport.send({id:1,method:'Browser.getVersion'});socket.emit('open');socket.emit('message',{data:'{"id":1,"result":{}}'});demand(socket.sent.length===1&&seen.id===1,'adapter forwarding drift');transport.close()});
 for(const event of ['error','close'])caseName('adapter-'+event+'-no-reconnect',()=>{const before=FakeSocket.all.length,{transport,socket,failures}=fixture();socket.emit(event);demand(failures.length===1&&failures[0].kind==='transport-'+event&&transport.firstCause&&FakeSocket.all.length===before+1,'first cause or one socket drift')});
 for(const [name,data] of [['invalid-json','{'],['array','[]'],['binary',new ArrayBuffer(2)],['oversized','x'.repeat(CAP+1)],['missing-id-method','{}']])caseName('adapter-message-'+name,()=>{const {socket,failures}=fixture();socket.emit('open');socket.emit('message',{data});demand(failures.length===1&&failures[0].kind==='active-failure','invalid CDP message forwarded')});
 caseName('adapter-expired-timer',()=>{const {transport,failures}=fixture();callbacks[0]();demand(failures.length===1&&transport.firstCause.includes('deadline'),'deadline first cause drift')});
 caseName('adapter-close-idempotent-no-browser-close',()=>{const {transport,socket}=fixture();socket.emit('open');transport.close();transport.close();demand(socket.closeCalls===1&&socket.sent.length===0,'transport close used browser command')});
 for(const method of ['Browser.close','Emulation.setFocusEmulationEnabled'])caseName('adapter-forbidden-'+method,()=>{const {transport}=fixture();refused(()=>transport.send({id:1,method}))});
 caseName('adapter-public-callback-clear',()=>{const {transport,socket}=fixture();transport.onmessage=()=>{};transport.onclose=()=>{};transport.onmessage=undefined;transport.onclose=undefined;socket.emit('open');transport.close();demand(socket.closeCalls===1,'callback removal broke close')});
 caseName('adapter-outgoing-cap',()=>{const {transport}=fixture();refused(()=>transport.send({id:1,method:'test',data:'x'.repeat(CAP)}))});
 caseName('adapter-unsolicited-before-attachment',()=>{const {socket,failures}=fixture();socket.emit('open');socket.emit('message',{data:'{"method":"test"}'});demand(failures.length===1,'unsolicited message accepted')});
 caseName('adapter-real-key-recorder-observes-trusted-only',()=>{
  const previousWindow=globalThis.window,previousDocument=globalThis.document;let listener;
  try{globalThis.window={};globalThis.document={addEventListener:(name,callback,capture)=>{demand(name==='keydown'&&capture===true,'key boundary drift');listener=callback}};
   realKeyRecorder();const event={key:'Return',target:{textContent:'actual control',id:'id',parentElement:{id:'parent'}}};listener({...event,isTrusted:false});demand(window.__externalKeys.length===0,'synthetic keyboard accepted');listener({...event,isTrusted:true});demand(window.__externalKeys.length===1&&window.__externalKeys[0].sequence===1,'trusted key not observed');
  }finally{globalThis.window=previousWindow;globalThis.document=previousDocument}
 });
 const trace=[];
 function model(contextCount=1,pageCount=1,url='about:blank'){
  const page={url:()=>url,addInitScript:async()=>trace.push('instrument'),goto:async(target,options)=>{demand(options.timeout>0,'navigation unbounded');trace.push('navigate');url=target},getByRole:()=>({waitFor:async options=>{demand(options.timeout>0,'readiness unbounded');trace.push('ready')}})};
  const context={setDefaultTimeout:value=>demand(value>0,'default timeout unbounded'),setDefaultNavigationTimeout:value=>demand(value>0,'navigation timeout unbounded'),pages:()=>Array(pageCount).fill(page)};
  const chromium={connectOverCDP:async(value,options)=>{demand(typeof value==='object'&&value.send&&options.noDefaults===true&&options.timeout>0&&options.artifactsDir==='/private/fixture','public transport/defaults drift');trace.push('attach');return {contexts:()=>Array(contextCount).fill(context),close:()=>{throw Error('Browser.close must not run')}}}};
  return chromium;
 }
 await drainSample(Promise.resolve(),{deadline:100,clock:()=>0,timers:{set:()=>1,clear:()=>{}}});checked.push('adapter-inflight-sample-drained-before-local-close');
 for(const [name,pending,deadline] of [['sample-rejected',Promise.reject(Error('original sample failure')),100],['sample-deadline',Promise.resolve(),0]]){let caught=false;try{await drainSample(pending,{deadline,clock:()=>0,timers:{set:()=>1,clear:()=>{}}})}catch{caught=true}demand(caught,'sample drain uncertainty accepted');checked.push('adapter-'+name)}
 let expire;const unresolved=drainSample(new Promise(()=>{}),{deadline:100,clock:()=>0,timers:{set:fn=>{expire=fn;return 1},clear:()=>{}}});expire();let expired=false;try{await unresolved}catch{expired=true}demand(expired,'pending sample drain accepted');checked.push('adapter-sample-drain-unresolved');
 const good=fixture();await attachOwnedPage(model(),good.transport,()=>100,'/private/fixture');checked.push('adapter-public-transport-noDefaults-observational-order');demand(trace.join(',')==='attach,instrument,navigate,ready','instrumentation/navigation order drift');good.transport.close();
 for(const [name,contexts,pages,url] of [['missing-context',0,1,'about:blank'],['extra-context',2,1,'about:blank'],['missing-page',1,0,'about:blank'],['extra-page',1,2,'about:blank'],['wrong-page',1,1,'http://foreign/']]){
  trace.length=0;const f=fixture();let failed=false;try{await attachOwnedPage(model(contexts,pages,url),f.transport,()=>100,'/private/fixture')}catch{failed=true}demand(failed&&!trace.includes('navigate'),'invalid context/page released navigation');f.transport.close();checked.push('adapter-'+name);
 }
 console.log(JSON.stringify({schema:'fsgg.at-browser-adapter-controls/1',names:checked,count:checked.length,network:0,browserLaunches:0}));return checked;
}
module.exports={drainSample,attachOwnedPage,transportAdapter,deadlineFromBudget,endpointIdentity,runCompanion,adapterSelfTest};
if(require.main===module){(process.argv[2]==='--self-test'?adapterSelfTest():runCompanion(process.argv.slice(2))).catch(error=>{console.error('BROWSER_COMPANION_FIRST_CAUSE '+error.message);process.exitCode=1})}

'''


def proc(pid):
    try:
        raw = Path(f"/proc/{pid}/stat").read_text()
        a = raw[raw.rindex(")") + 2:].split()
        return {"pid": pid, "start": int(a[19]), "ppid": int(a[1]), "pgid": int(a[2]), "sid": int(a[3]), "state": a[0], "rss": int(a[21]) * os.sysconf("SC_PAGE_SIZE")}
    except (FileNotFoundError, ProcessLookupError):
        return None


def census(leader, known):
    rows = [v for p in Path("/proc").iterdir() if p.name.isdigit() and (v := proc(int(p.name)))]
    by = {v["pid"]: v for v in rows}
    changed = True
    while changed:
        changed = False
        for row in rows:
            parent = by.get(row["ppid"])
            if parent and known.get(parent["pid"]) == parent["start"] and row["pid"] not in known:
                known[row["pid"]] = row["start"]
                changed = True
    owned = [v for v in rows if known.get(v["pid"]) == v["start"]]
    unknown = [v for v in rows if v["sid"] == leader["sid"] and known.get(v["pid"]) != v["start"]]
    escaped = [v for v in owned if v["sid"] != leader["sid"]]
    return owned, unknown, escaped


def cleanup(leader, known, child):
    end = time.monotonic() + 30
    signals = []
    for sig in [signal.SIGTERM, signal.SIGKILL]:
        owned, unknown, escaped = census(leader, known)
        for row in owned:
            now = proc(row["pid"])
            if now and now["state"] != "Z" and now["start"] == row["start"] and now["sid"] == leader["sid"]:
                try:
                    os.kill(row["pid"], sig)
                    signals.append({"pid": row["pid"], "start": row["start"], "signal": sig.name})
                except ProcessLookupError:
                    pass
        deadline = end - 2 if sig == signal.SIGTERM else end
        while time.monotonic() < deadline:
            child.poll()
            owned, unknown, escaped = census(leader, known)
            if not owned:
                break
            time.sleep(.1)
    child.poll()
    owned, unknown, escaped = census(leader, known)
    return {"disposition": "observed-empty" if not owned and not unknown and not escaped else "unknown",
            "remaining": owned, "unknown": unknown + escaped, "signals": signals}


@contextlib.contextmanager
def capture_termination():
    """Record cancellation without interrupting first-cause reporting or bounded cleanup."""
    pending = []
    previous = {sig: signal.getsignal(sig) for sig in [signal.SIGTERM, signal.SIGINT]}

    def record(sig, _frame):
        if not pending:
            pending.append("original observer termination: " + signal.Signals(sig).name)

    try:
        for sig in previous:
            signal.signal(sig, record)
        yield pending
    finally:
        for sig, handler in previous.items():
            signal.signal(sig, handler)


def owned_server_listener(pid):
    """Require port5100's listening inode in the original server's live fd population."""
    sockets = set()
    try:
        descriptors = list(Path(f"/proc/{pid}/fd").iterdir())
    except (FileNotFoundError, ProcessLookupError):
        return False
    for descriptor in descriptors:
        try:
            target = os.readlink(descriptor)
        except (FileNotFoundError, ProcessLookupError):
            continue
        if target.startswith("socket:["):
            sockets.add(target[8:-1])
    return listener_matches(Path("/proc/net/tcp").read_text(), sockets)


def listener_matches(tcp, sockets):
    for row in tcp.splitlines()[1:]:
        fields = row.split()
        if fields[1] == "0100007F:13EC" and fields[3] == "0A" and fields[9] in sockets:
            return True
    return False


def wait_server_ready(child, ready=owned_server_listener, clock=time.monotonic, pause=time.sleep, absolute_deadline=None):
    """Observe one original startup for at most15s; never restart server or retry navigation."""
    deadline = clock() + 15
    if absolute_deadline is not None:
        deadline = min(deadline, absolute_deadline)
    while clock() < deadline:
        code = child.poll()
        require(code is None, "original server exited before readiness: " + str(code) + "; see server.log")
        if ready(child.pid):
            return
        pause(.1)
    raise RuntimeError("original owned server readiness deadline exceeded; see server.log")


# Exact locked Playwright1.63.0 headed defaults; no private API evaluation.
BROWSER_LOCK_SHA = 'f5ed53b9ee86e12f3053e0378fcd1c6d65e925e86792bd3cd82466141c49e67a'
BROWSER_LOCK_GRAPH_SHA = '9783d542fb830f416767cb168e6454318ae9483e50e04fbdc63e83b19b0ba245'
BROWSER_PACKAGE_SHA = 'f061c58427e47e843e26d201f0a57076c734e57c734ecbbd87d4a23b7a20db9b'
BROWSER_CORE_SHA = '549070af3acabb3efcc4f55bfe6210f9f7c2fcf633cf7eaa59bfe60719969171'
BROWSER_REGISTRY_SHA = '545d52f8382c391e605562c330e9c1c534a16045898203037a49bb8bd769a946'
BROWSER_PLAYWRIGHT_SOURCE_SHA = '208593d4e1bcd8f8fe5f869cad1cc332dc7f1d70dc1d58c102dc3ac36e30f26c'
BROWSER_NODE_SOURCE = '151845ab90d3926ceb36eedf1eade09619c3adc9'
BROWSER_SCHEMA = 'fsgg.at-owned-chromium-cdp/1'
BROWSER_FLAGS = ['--disable-field-trial-config', '--disable-background-networking', '--disable-background-timer-throttling', '--disable-backgrounding-occluded-windows', '--disable-back-forward-cache', '--disable-breakpad', '--disable-client-side-phishing-detection', '--disable-component-extensions-with-background-pages', '--disable-component-update', '--no-default-browser-check', '--disable-default-apps', '--disable-dev-shm-usage', '--disable-edgeupdater', '--disable-extensions', '--disable-features=AvoidUnnecessaryBeforeUnloadCheckSync,DestroyProfileOnBrowserClose,DialMediaRouteProvider,GlobalMediaControls,HttpsUpgrades,LensOverlay,MediaRouter,PaintHolding,ThirdPartyStoragePartitioning,BlockOriginHeaderModificationOnRedirect,Translate,AutoDeElevate,OptimizationHints,msForceBrowserSignIn,msEdgeUpdateLaunchServicesPreferredVersion', '--enable-features=CDPScreenshotNewSurface', '--allow-pre-commit-input', '--disable-hang-monitor', '--disable-ipc-flooding-protection', '--disable-popup-blocking', '--disable-prompt-on-repost', '--disable-renderer-backgrounding', '--disable-updater-scheduler', '--force-color-profile=srgb', '--metrics-recording-only', '--no-first-run', '--password-store=basic', '--use-mock-keychain', '--no-service-autorun', '--export-tagged-pdf', '--disable-search-engine-choice-screen', '--unsafely-disable-devtools-self-xss-warnings', '--edge-skip-compat-layer-relaunch', '--disable-infobars', '--disable-search-engine-choice-screen', '--disable-sync', '--enable-unsafe-swiftshader', '--no-sandbox', '--force-renderer-accessibility']
BROWSER_FILES = ['browser-launch.json', 'browser-companion-ready.json', 'browser.cjs', 'tool-identities.json', 'inner-result.json', 'browser-companion.log']
BROWSER_RESOLVER = r"const fs=require('node:fs'),path=require('node:path');const root=process.argv[1];const {chromium}=require(path.join(root,'Browser.Tests/node_modules/@playwright/test'));console.log(JSON.stringify({path:chromium.executablePath()}));"


def browser_profile_identity(profile):
    require(not profile.is_symlink() and profile.is_dir() and profile.resolve() == profile.absolute(),
            'browser profile linked or missing')
    value = profile.stat()
    require(stat.S_IMODE(value.st_mode) == 0o700 and value.st_uid == os.getuid(), 'browser profile not privately owned')
    return {'path': str(profile), 'device': value.st_dev, 'inode': value.st_ino, 'uid': value.st_uid}


def fresh_browser_profile(profile):
    require(not profile.exists() and not profile.is_symlink(), 'browser profile already used')
    profile.mkdir(mode=0o700)
    return browser_profile_identity(profile)


def browser_argv(executable, profile):
    return [executable, *BROWSER_FLAGS, '--user-data-dir='+str(profile), '--remote-debugging-port=0', 'about:blank']


def check_node_tool(directory):
    selected = json.loads((directory / 'tool-identities.json').read_text())['node']
    require(shutil.which('node') == selected['path'] and digest(Path(selected['path']).resolve()) == selected['sha256'],
            'original Node executable changed')
    return selected


def browser_dependency_lock(dependencies):
    lock_path = dependencies / 'package-lock.json'
    package_path = dependencies / 'package.json'
    for path in [lock_path, package_path]:
        require(not path.is_symlink() and path.is_file() and path.stat().st_size <= 1048576,
                'browser dependency metadata missing, linked or oversized')
    lock = completion_record(lock_path)
    package = completion_record(package_path)
    require(package.get('devDependencies', {}) == lock['packages'][''].get('devDependencies', {}) and
            package.get('dependencies', {}) == lock['packages'][''].get('dependencies', {}), 'generated package dependency declarations changed')
    name = package['name']
    require(isinstance(name, str) and name and lock['name'] == lock['packages']['']['name'] == name,
            'generated browser package name mismatch')
    # Only the template engine's root project-name projection is excluded; every dependency byte/value remains bound.
    lock['name'] = lock['packages']['']['name'] = 'fablegameworkspace-browser-tests'
    graph = hashlib.sha256(json.dumps(lock, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
    require(graph == BROWSER_LOCK_GRAPH_SHA, 'locked browser dependency graph changed')
    return {'actualLockSha256': digest(lock_path), 'dependencyGraphSha256': graph, 'generatedPackageName': name}


def resolve_browser(receiver, deadline, run=None, clock=None, directory=None):
    clock = time.monotonic if clock is None else clock
    run = subprocess.run if run is None else run
    dependencies = receiver / 'Browser.Tests'
    core = dependencies / 'node_modules/playwright-core'
    lock_identity = browser_dependency_lock(dependencies)
    require(digest(core / 'package.json') == BROWSER_PACKAGE_SHA and digest(core / 'browsers.json') == BROWSER_REGISTRY_SHA and
            digest(core / 'lib/coreBundle.js') == BROWSER_CORE_SHA,
            'locked browser dependency changed')
    remaining = deadline-clock()
    require(remaining > 0, 'original browser resolution deadline expired')
    result = run(['node', '-e', BROWSER_RESOLVER, str(receiver)], check=False, stdout=subprocess.PIPE,
                 stderr=subprocess.PIPE, timeout=min(10, remaining))
    require(len(result.stdout) <= 4096 and len(result.stderr) <= 65536, 'browser resolver report oversized')
    if directory is not None:
        write(directory / 'browser-resolver.json', {'exit': result.returncode, 'stdout': result.stdout.decode(errors='replace'), 'stderr': result.stderr.decode(errors='replace')})
    require(result.returncode == 0, 'original browser resolver failed: '+str(result.returncode)+'; see browser-resolver.json')
    value = json.loads(result.stdout)
    require(set(value) == {'path'} and isinstance(value['path'], str), 'browser resolver malformed')
    selected = Path(value['path'])
    require(selected.is_absolute() and selected.resolve() == selected and selected.is_file() and
            not selected.is_symlink() and selected.parts[-3:] == ('chromium-1243', 'chrome-linux64', 'chrome'),
            'headed locked Chromium installation absent or overridden')
    info = selected.stat()
    require(info.st_size > 0 and info.st_mode & stat.S_IXUSR, 'Chromium executable unavailable')
    return {'path': str(selected), 'bytes': info.st_size, 'sha256': digest(selected),
            'device': info.st_dev, 'inode': info.st_ino, 'mtimeNs': info.st_mtime_ns, 'version': '153.0.8010.12', 'revision': '1243',
            'lockSha256': BROWSER_LOCK_SHA, 'packageSha256': BROWSER_PACKAGE_SHA, 'registrySha256': BROWSER_REGISTRY_SHA, 'coreBundleSha256': BROWSER_CORE_SHA, **lock_identity}


def check_browser_executable(value, hash_bytes=True):
    path = Path(value['path'])
    require(path.resolve() == path and not path.is_symlink() and path.is_file(), 'selected browser executable changed')
    info = path.stat()
    require(info.st_size == value['bytes'] and info.st_dev == value['device'] and info.st_ino == value['inode'] and
            info.st_mtime_ns == value['mtimeNs'] and (not hash_bytes or digest(path) == value['sha256']), 'selected browser executable bytes changed')


def browser_endpoint_bytes(raw):
    require(len(raw) <= 4096, 'browser endpoint record oversized')
    try:
        value = raw.decode('ascii')
    except UnicodeDecodeError as error:
        raise RuntimeError('browser endpoint not ASCII') from error
    # Missing or partial startup records are handled by the bounded parent wait, never parsed as success.
    require(re.fullmatch(r'[1-9][0-9]{0,4}\n/devtools/browser/[A-Za-z0-9-]+\n?', value) is not None,
            'browser endpoint record malformed')
    port, path = value.rstrip('\n').split('\n')
    require(0 < int(port) <= 65535, 'browser endpoint port invalid')
    return {'port': int(port), 'path': path, 'endpoint': 'ws://127.0.0.1:'+port+path}


def browser_listener_rows(tables, port, owned_sockets):
    listeners = []
    for family, table in tables.items():
        for row in table.splitlines()[1:]:
            fields = row.split()
            if len(fields) < 10 or fields[3] != '0A':
                continue
            address, selected_port = fields[1].split(':')
            if int(selected_port, 16) != port:
                continue
            require((family == 'tcp' and address == '0100007F') or
                    (family == 'tcp6' and address == '00000000000000000000000001000000'),
                    'browser listener wildcard or foreign address')
            require(fields[9] in owned_sockets, 'browser listener foreign process inode')
            listeners.append({'family': family, 'address': address, 'port': port, 'inode': fields[9]})
    require(len(listeners) == 1 and listeners[0]['family'] == 'tcp', 'browser loopback listener missing or ambiguous')
    return listeners[0]


def browser_listener(pid, port):
    sockets = set()
    for descriptor in Path(f'/proc/{pid}/fd').iterdir():
        try:
            target = os.readlink(descriptor)
        except (FileNotFoundError, ProcessLookupError):
            continue
        if target.startswith('socket:['):
            sockets.add(target[8:-1])
    return browser_listener_rows({family: Path('/proc/net/'+family).read_text() for family in ['tcp', 'tcp6']}, port, sockets)


def browser_active(browser, birth, profile, profile_identity, executable, reader=None):
    reader = proc if reader is None else reader
    require(browser.poll() is None, 'original Chrome exited before journey completion')
    actual = reader(browser.pid)
    require(same_birth(actual, birth) and actual['pgid'] == birth['pgid'] == birth['sid'],
            'original Chrome birth/session/group changed')
    require(browser_profile_identity(profile) == profile_identity, 'original browser profile identity changed')
    check_browser_executable(executable, hash_bytes=False)


def wait_browser_endpoint(browser, birth, profile, identity, executable, deadline, health,
                          listener=None, clock=None, pause=None):
    clock = time.monotonic if clock is None else clock
    pause = time.sleep if pause is None else pause
    listener = browser_listener if listener is None else listener
    end = min(deadline, clock()+15)
    path = profile / 'DevToolsActivePort'
    while clock() < end:
        health()
        browser_active(browser, birth, profile, identity, executable)
        if path.exists() or path.is_symlink():
            fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
            with os.fdopen(fd, 'rb') as stream:
                info = os.fstat(stream.fileno())
                require(stat.S_ISREG(info.st_mode) and info.st_uid == identity['uid'] and info.st_size <= 4096,
                        'browser endpoint file custody absent')
                raw = stream.read(4097)
            if raw and b'\n/devtools/browser/' in raw:
                endpoint = browser_endpoint_bytes(raw)
                endpoint['file'] = {'device': info.st_dev, 'inode': info.st_ino, 'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()}
                endpoint['listener'] = listener(browser.pid, endpoint['port'])
                browser_active(browser, birth, profile, identity, executable)
                return endpoint
        pause(.1)
    raise RuntimeError('original browser endpoint readiness deadline exceeded')


def check_browser_endpoint(profile, endpoint):
    path = profile / 'DevToolsActivePort'
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    with os.fdopen(fd, 'rb') as stream:
        info = os.fstat(stream.fileno())
        require(stat.S_ISREG(info.st_mode) and info.st_size <= 4096, 'browser endpoint changed type or size')
        raw = stream.read(4097)
    observed = {'device': info.st_dev, 'inode': info.st_ino, 'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()}
    require(observed == endpoint['file'] and browser_endpoint_bytes(raw) == {k: endpoint[k] for k in ['port', 'path', 'endpoint']},
            'original browser endpoint file changed')


def browser_ready_matches(ready, launch, launch_sha, companion):
    require(ready['schema'] == BROWSER_SCHEMA and ready['launchSha256'] == launch_sha and
            ready['browserBirth'] == launch['browserBirth'] and same_birth(ready['companionBirth'], companion) and ready['companionBirth']['pgid'] == companion['pgid'] and
            ready['companionBirth']['pgid'] == companion['pgid'] == launch['browserBirth']['pgid'] and
            ready['companionBirth']['pid'] != launch['browserBirth']['pid'] and
            ready['endpoint'] == launch['endpoint']['endpoint'] and ready['profile'] == launch['profile'] and
            ready['sourceSha256'] == launch['companionSourceSha256'] and ready['noDefaults'] is True and
            ready['contexts'] == 1 and ready['initialPages'] == 1 and ready['initialURL'] == 'about:blank' and
            ready['pageURL'] == 'http://127.0.0.1:5100/' and ready['sampleSequence'] > 0,
            'browser companion readiness identity differs')
    return True


def record_inner_success(directory):
    runtime = completion_record(directory / 'owned-bus-runtime.json')
    leaders = json.loads((directory / 'resource-leaders.json').read_text())
    contract_evidence(directory, runtime, leaders)
    launch = completion_record(directory / 'browser-launch.json')
    browser = next(v for v in leaders if v['resource'] == 'browser')
    companion = next(v for v in leaders if v['resource'] == 'browser-companion')
    require(same_birth(proc(browser['pid']), browser) and same_birth(proc(companion['pid']), companion),
            'original browser resource changed after inner success')
    browser_active_failure(directory, companion)
    require(browser_profile_identity(Path(launch['profile']['path'])) == launch['profile'], 'browser profile changed after inner success')
    check_browser_executable(launch['executable'])
    check_browser_endpoint(Path(launch['profile']['path']), launch['endpoint'])
    require(browser_listener(browser['pid'], launch['endpoint']['port']) == launch['endpoint']['listener'], 'browser listener changed after inner success')
    require(time.monotonic() < launch['absoluteDeadline'], 'original inner success deadline expired')
    parent = completion_birth(proc(os.getpid()))
    require(parent == runtime['sessionContract']['completion']['identity']['parentBirth'], 'successful inner parent birth changed')
    packet = {'schema': 'fsgg.at-inner-result/1', 'exit': 0, 'firstCause': None,
              'sourceSha256': digest(Path(__file__).resolve()), 'parentBirth': parent,
              'browserBirth': launch['browserBirth'], 'companionBirth': {k: companion[k] for k in ['pid', 'start', 'ppid', 'pgid', 'sid']},
              'completionSha256': digest(directory / FINISH_FILES[2]), 'journeySha256': digest(directory / 'journey.json'),
              'launchSha256': digest(directory / 'browser-launch.json')}
    atomic_record_once(directory / 'inner-result.json', packet)
    return packet


def browser_companion_log(directory):
    path = directory / 'browser-companion.log'
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        info = os.fstat(fd)
        require(stat.S_ISREG(info.st_mode) and info.st_size <= 4 * 1024**2,
                'original browser companion log missing, nonregular or oversized')
        raw = bytearray()
        while len(raw) <= 4 * 1024**2:
            chunk = os.read(fd, min(65536, 4 * 1024**2 + 1 - len(raw)))
            if not chunk:
                break
            raw.extend(chunk)
    finally:
        os.close(fd)
    require(len(raw) <= 4 * 1024**2, 'original browser companion log grew beyond bound')
    try:
        lines = raw.decode('utf8').splitlines()
    except UnicodeDecodeError as error:
        raise RuntimeError('original browser companion log unreadable') from error
    causes = [line[len('BROWSER_COMPANION_FIRST_CAUSE '):] for line in lines
              if line.startswith('BROWSER_COMPANION_FIRST_CAUSE ')]
    reports = [line[len('BROWSER_COMPANION_REPORT_FAILURE '):] for line in lines
               if line.startswith('BROWSER_COMPANION_REPORT_FAILURE ')]
    require(all(cause.strip() for cause in causes), 'browser companion log original cause missing')
    return {'sha256': hashlib.sha256(raw).hexdigest(), 'firstCauses': causes, 'reportFailures': reports}


def browser_active_failure(directory, companion):
    failure = directory / 'browser-companion-failure.json'
    if failure.exists():
        packet = completion_record(failure)
        require(same_birth(packet['birth'], companion) and packet['birth']['pgid'] == companion['pgid'], 'browser active failure birth changed')
        raise RuntimeError(packet['firstCause'])
    log = browser_companion_log(directory)
    if log['firstCauses']:
        raise RuntimeError(log['firstCauses'][0])
    if log['reportFailures']:
        raise RuntimeError('browser companion failure reporting failed; original cause unknown: '+log['reportFailures'][0])


def browser_transport_outcome(directory, launch, companion):
    failure = directory / 'browser-companion-failure.json'
    log = browser_companion_log(directory)
    if not failure.exists():
        require(not log['firstCauses'] and not log['reportFailures'],
                log['firstCauses'][0] if log['firstCauses'] else 'browser companion failure reporting failed; original cause unknown')
        return {'reported': False, 'stage': 'not-observed'}
    packet = completion_record(failure)
    require(isinstance(packet['firstCause'], str) and packet['firstCause'], 'browser companion original cause missing')
    require(log['firstCauses'] and not log['reportFailures'] and
            all(cause == packet['firstCause'].splitlines()[0] for cause in log['firstCauses']), packet['firstCause'])
    success = completion_record(directory / 'inner-result.json')
    require(packet['schema'] == BROWSER_SCHEMA and packet['kind'] in ['transport-close', 'transport-error'] and same_birth(packet['birth'], companion) and packet['birth']['pgid'] == companion['pgid'] and
            packet['launchSha256'] == digest(directory / 'browser-launch.json') and
            packet.get('innerResultSha256AtFailure') == digest(directory / 'inner-result.json') and
            success['schema'] == 'fsgg.at-inner-result/1' and success['exit'] == 0 and success['firstCause'] is None and
            success['sourceSha256'] == launch['sourceSha256'] and success['browserBirth'] == launch['browserBirth'] and
            same_birth(success['companionBirth'], companion) and success['companionBirth']['pgid'] == companion['pgid'] and success['completionSha256'] == digest(directory / FINISH_FILES[2]) and
            success['parentBirth'] == completion_record(directory / FINISH_FILES[2])['identity']['parentBirth'] and
            success['parentBirth']['pid'] == launch['browserBirth']['ppid'] == companion['ppid'] and
            success['journeySha256'] == digest(directory / 'journey.json') and success['launchSha256'] == digest(directory / 'browser-launch.json'),
            'active or unbound companion transport failure')
    process = completion_record(directory / 'process-result.json')
    require(process['leader']['pid'] == process['leader']['pgid'] == process['leader']['sid'] == success['parentBirth']['sid'] and
            process['exit'] == 0 and process['firstCause'] is None and process['firstGuardCensus'] is None and
            not process['termination'] and not process['reportingErrors'] and
            process['cleanup']['disposition'] == 'observed-empty' and not process['cleanup']['remaining'] and not process['cleanup']['unknown'],
            'post-observation transport outcome lacks original successful wrapper and cleanup')
    return {'reported': True, 'stage': 'post-observation-transport-outcome', 'firstCause': packet['firstCause'],
            'failureSha256': digest(failure), 'innerResultSha256': digest(directory / 'inner-result.json')}


def browser_evidence(directory, receipt, runtime, leaders):
    launch = completion_record(directory / 'browser-launch.json')
    ready = completion_record(directory / 'browser-companion-ready.json')
    browser = next(v for v in leaders if v['resource'] == 'browser')
    companion = next(v for v in leaders if v['resource'] == 'browser-companion')
    require(launch['schema'] == BROWSER_SCHEMA and launch['sourceSha256'] == digest(Path(__file__).resolve()) and
            launch['playwrightSourceSha256'] == BROWSER_PLAYWRIGHT_SOURCE_SHA and launch['nodeSourceCommit'] == BROWSER_NODE_SOURCE and
            launch['companionSourceSha256'] == digest(directory / 'browser.cjs') == hashlib.sha256(BROWSER.encode()).hexdigest() and
            launch['argv'] == browser_argv(launch['executable']['path'], directory / 'profile') and
            launch['profile']['path'] == str(directory / 'profile') and launch['profile']['uid'] == json.loads((directory / 'owned-bus-route.json').read_text())['uid'] and
            launch['nodeTool'] == json.loads((directory / 'tool-identities.json').read_text())['node'] and
            launch['executable']['lockSha256'] == BROWSER_LOCK_SHA and launch['executable']['packageSha256'] == BROWSER_PACKAGE_SHA and
            launch['executable']['registrySha256'] == BROWSER_REGISTRY_SHA and launch['executable']['coreBundleSha256'] == BROWSER_CORE_SHA and
            launch['executable']['dependencyGraphSha256'] == BROWSER_LOCK_GRAPH_SHA and
            re.fullmatch('[0-9a-f]{64}', launch['executable']['actualLockSha256']) is not None and
            isinstance(launch['executable']['generatedPackageName'], str) and launch['executable']['generatedPackageName'] and launch['executable']['revision'] == '1243' and
            launch['executable']['version'] == '153.0.8010.12' and launch['browserBirth'] == {k: browser[k] for k in launch['browserBirth']} and
            browser['pgid'] == browser['sid'] == companion['pgid'] == companion['sid'] and browser['ppid'] == companion['ppid'] and
            receipt['browser']['pid'] == receipt['browser']['launcherPid'] == browser['pid'] and
            receipt['browser']['companionPid'] == companion['pid'], 'owned browser launch/receipt binding absent')
    parsed = browser_endpoint_bytes((str(launch['endpoint']['port'])+'\n'+launch['endpoint']['path']+'\n').encode())
    require(parsed['endpoint'] == launch['endpoint']['endpoint'] and launch['endpoint']['listener']['port'] == parsed['port'] and
            launch['endpoint']['listener']['family'] == 'tcp' and launch['endpoint']['listener']['address'] == '0100007F' and
            launch['endpoint']['listener']['inode'].isdigit(), 'owned browser endpoint evidence absent')
    browser_ready_matches(ready, launch, digest(directory / 'browser-launch.json'), companion)
    success = completion_record(directory / 'inner-result.json')
    require(success['schema'] == 'fsgg.at-inner-result/1' and success['exit'] == 0 and success['firstCause'] is None and
            success['completionSha256'] == digest(directory / FINISH_FILES[2]) and success['journeySha256'] == digest(directory / 'journey.json') and
            success['launchSha256'] == digest(directory / 'browser-launch.json') and success['browserBirth'] == launch['browserBirth'] and
            same_birth(success['companionBirth'], companion) and success['companionBirth']['pgid'] == companion['pgid'] and success['sourceSha256'] == launch['sourceSha256'] and
            success['parentBirth'] == runtime['sessionContract']['completion']['identity']['parentBirth'] and
            success['parentBirth']['pid'] == browser['ppid'] == companion['ppid'], 'successful original inner return evidence absent')
    outcome = browser_transport_outcome(directory, launch, companion)
    require(receipt['browser'].get('transportOutcome', {'reported': False, 'stage': 'not-observed'}) == outcome, 'browser transport outcome unreported')
    require(runtime['mappedLibraries']['browser']['birth']['pid'] == browser['pid'], 'actual browser mapping authority swapped')
    return True


def inner(receiver, directory, gio_adapter=None):
    # Private D-Bus, XDG settings, display, Pulse server and speech socket: no user-session replacement.
    os.environ.update(DISPLAY=":97", NO_AT_BRIDGE="0", GTK_MODULES="gail:atk-bridge",
                      GSETTINGS_BACKEND="keyfile", GNOME_ACCESSIBILITY="1",
                      XDG_CONFIG_HOME=str(directory / "config"), XDG_CACHE_HOME=str(directory / "cache"),
                      XDG_RUNTIME_DIR=str(directory / "runtime"), XDG_DATA_HOME=str(directory / "data"),
                      TMPDIR=str(directory / "tmp"), PULSE_SERVER="unix:" + str(directory / "pulse.sock"),
                      SPEECHD_ADDRESS="unix_socket:" + str(directory / "speech.sock"))
    for name in ["config", "cache", "runtime", "data", "tmp", "speech-config/modules", "speech-logs"]:
        (directory / name).mkdir(mode=0o700, parents=True, exist_ok=True)
    children = []
    leaders = []
    session_deadline = json.loads((directory / "session-budget.json").read_text())["deadline"]

    def launch(argv, name, cwd=None, pass_fds=()):
        require(time.monotonic() < session_deadline, "original AT session deadline exhausted before launch")
        required_children(children, directory)
        if argv[0] in ROUTE_PATHS:
            check_launch_object(directory, argv[0])
        log = (directory / (name + ".log")).open("xb")
        child = subprocess.Popen(argv, cwd=cwd, stdout=log, stderr=subprocess.STDOUT, pass_fds=pass_fds)
        children.append(child)
        identity = proc(child.pid)
        require_birth(identity, os.getpid(), os.getsid(0))
        leaders.append({"resource": name, **identity})
        write(directory / "resource-leaders.json", leaders)
        return child

    def command(argv, seconds=10):
        required_children(children, directory)
        remaining = session_deadline-time.monotonic()
        require(remaining > 0, "original AT session deadline exhausted before command")
        subprocess.run(argv, check=True, timeout=min(seconds, remaining))

    activation = json.loads((directory / "activation-provenance.json").read_text())
    objects = check_route_files(activation)
    state = json.loads((directory / "owned-bus-route.json").read_text())
    for name in ["session", "accessibility"]:
        check_closed_config((directory / (name+".conf")).read_bytes(), state["sockets"][name], os.getuid())
    require("AT_SPI_BUS_ADDRESS" not in os.environ, "inherited accessibility address refused; no client rebinding")
    read_fd, write_fd = os.pipe()
    try:
        bus = launch(["/usr/bin/dbus-daemon", "--nofork", "--nopidfile",
                      "--config-file=" + str(directory / "accessibility.conf"),
                      "--print-address=" + str(write_fd)], "accessibility-bus", pass_fds=(write_fd,))
        os.close(write_fd)
        write_fd = None
        address = read_bus_address(bus, read_fd, state["sockets"]["accessibility"], absolute_deadline=session_deadline)
    finally:
        os.close(read_fd)
        if write_fd is not None:
            os.close(write_fd)
    # libatspi caches its first connection: this assignment precedes every AT import and fresh client.
    os.environ["AT_SPI_BUS_ADDRESS"] = address
    require(not Path("/tmp/.X97-lock").exists() and not Path("/tmp/.X11-unix/X97").exists(), "selected display already occupied; no reuse")
    xvfb = launch(["Xvfb", ":97", "-screen", "0", "1280x800x24", "-nolisten", "tcp"], "xvfb")
    wait_display_ready(xvfb, absolute_deadline=session_deadline)
    Gio, GLib = native_gio() if gio_adapter is None else gio_adapter
    session_address = os.environ["DBUS_SESSION_BUS_ADDRESS"]
    require(re.fullmatch(re.escape("unix:path="+state["sockets"]["session"])+r",guid=[0-9a-f]{32}", session_address) is not None,
            "session bus address outside owned config")
    session_deadline = json.loads((directory / "session-budget.json").read_text())["deadline"]
    session_connection = bounded_bus_connection(Gio, GLib, session_address, min(session_deadline, time.monotonic()+15))
    session_pid = session_connection.call_sync("org.freedesktop.DBus", "/org/freedesktop/DBus", "org.freedesktop.DBus",
        "GetConnectionUnixProcessID", GLib.Variant("(s)", ("org.freedesktop.DBus",)), GLib.VariantType("(u)"),
        Gio.DBusCallFlags.NONE, max(1, min(5000, int((session_deadline-time.monotonic())*1000))), None).unpack()[0]
    session_birth = proc(session_pid)
    require_birth(session_birth, os.getppid(), os.getsid(0))
    require(bus_listener(session_pid, state["sockets"]["session"]), "session socket not owned by original daemon")
    connection = bounded_bus_connection(Gio, GLib, address, min(session_deadline, time.monotonic()+15))
    registry = launch(["/usr/libexec/at-spi2-registryd"], "registry")
    birth = proc(registry.pid)
    owner = registry_owner(connection, registry, birth, absolute_deadline=session_deadline)
    write(directory / "owned-bus-runtime.json", {"bus": proc(bus.pid), "address": address,
          "registry": owner, "sessionBus": session_birth, "sessionAddress": session_address,
          "addressSetBeforeAtspiImport": True, "objectIdentities": objects,
          "activation": "disabled by exact closed configs; vendor declarations retained unresolved"})
    launch(["openbox", "--sm-disable"], "openbox")
    command(["gsettings", "set", "org.gnome.desktop.interface", "toolkit-accessibility", "true"])
    command(["gsettings", "set", "org.gnome.desktop.a11y.applications", "screen-reader-enabled", "true"])
    session_deadline = json.loads((directory / "session-budget.json").read_text())["deadline"]
    status = launch(["/usr/bin/python3", "-B", str(Path(__file__).resolve()), "--owned-status", str(directory)], "session-contract")
    status_birth = proc(status.pid)
    runtime = json.loads((directory / "owned-bus-runtime.json").read_text())
    runtime["sessionContract"] = contract_ready(session_connection, status, status_birth, runtime, state, directory,
                                               min(session_deadline, time.monotonic()+15))
    write(directory / "owned-bus-runtime.json", runtime)
    def prerequisite_health():
        required_children(children, directory)
        contract_births(runtime, state)
        def checked():
            required_children(children, directory)
            require(same_birth(proc(status.pid), status_birth), "original session contract birth changed")
            contract_births(runtime, state)
        owner, pid, current_address, values = contract_query(session_connection, session_deadline, checked)
        require(owner == runtime["sessionContract"]["uniqueOwner"] and pid == status.pid and
                same_birth(proc(pid), status_birth) and current_address == address and values == keyfile_status(directory),
                "session contract readiness/liveness drift")
    prerequisite_health()
    launch(["pulseaudio", "-n", "--daemonize=no", "--exit-idle-time=-1", "--log-target=stderr",
            "--load=module-native-protocol-unix socket=" + str(directory / "pulse.sock"),
            "--load=module-null-sink sink_name=external_reference_orca"], "pulse")
    config = (Path("/etc/speech-dispatcher/speechd.conf")).read_text()
    config = re.sub(r"(?m)^(\s*(CommunicationMethod|SocketPath|AudioOutputMethod|AudioPulseDevice|AddModule|DefaultModule|DisableAutoSpawn)\b.*)$", r"# private override: \1", config)
    config += f'\nCommunicationMethod "unix_socket"\nSocketPath "{directory / "speech.sock"}"\nAudioOutputMethod "pulse"\nAudioPulseDevice "external_reference_orca"\nAddModule "espeak-ng" "sd_espeak-ng" "espeak-ng.conf"\nDefaultModule espeak-ng\nDisableAutoSpawn\n'
    (directory / "speech-config/speechd.conf").write_text(config)
    shutil.copyfile("/etc/speech-dispatcher/modules/espeak-ng.conf", directory / "speech-config/modules/espeak-ng.conf")
    launch(["speech-dispatcher", "-s", "-C", str(directory / "speech-config"), "-S", str(directory / "speech.sock"),
            "-P", str(directory / "speech.pid"), "-L", str(directory / "speech-logs"), "-t", "0"], "speech")
    deadline = min(time.monotonic() + 15, session_deadline)
    while not (directory / "speech.sock").exists() and time.monotonic() < deadline:
        time.sleep(.1)
    require((directory / "speech.sock").exists(), "private speech service unavailable")
    command(["/usr/bin/python3", str(Path(__file__).with_name("speech-dispatcher-preflight.py")), str(directory / "speech-preflight.json")], seconds=30)
    prerequisite_health()
    orca = launch(["/usr/bin/python3", str(Path(__file__).with_name("orca-faulthandler.py")), "--replace", "--debug",
                   "--debug-file=" + str(directory / "orca-debug.log")], "orca")
    time.sleep(3)
    prerequisite_health()
    server = launch(["dotnet", "Server.dll", "--urls", "http://127.0.0.1:5100"], "server", receiver / "artifacts/authority-server")
    wait_server_ready(server, absolute_deadline=session_deadline)
    profile = directory / "profile"
    profile_identity = fresh_browser_profile(profile)
    node_tool = check_node_tool(directory)
    executable = resolve_browser(receiver, session_deadline, directory=directory)
    check_browser_executable(executable)
    require(browser_profile_identity(profile) == profile_identity and not list(profile.iterdir()), "fresh browser profile changed before foreground launch")
    (directory / "browser.cjs").write_text(BROWSER)
    prerequisite_health()
    argv = browser_argv(executable["path"], profile)
    browser = launch(argv, "browser")
    browser_birth = proc(browser.pid)
    require(browser_birth["pgid"] == browser_birth["sid"] == os.getsid(0), "foreground browser changed original process group")
    endpoint = wait_browser_endpoint(browser, browser_birth, profile, profile_identity, executable, session_deadline, prerequisite_health)
    launch_record = {"schema": BROWSER_SCHEMA, "sourceSha256": digest(Path(__file__).resolve()),
        "playwrightSourceSha256": BROWSER_PLAYWRIGHT_SOURCE_SHA, "nodeSourceCommit": BROWSER_NODE_SOURCE,
        "executable": executable, "nodeTool": node_tool, "argv": argv, "profile": profile_identity, "endpoint": endpoint,
        "browserBirth": {k: browser_birth[k] for k in ["pid", "start", "ppid", "sid", "pgid"]},
        "companionSourceSha256": digest(directory / "browser.cjs"), "absoluteDeadline": session_deadline}
    write(directory / "browser-launch.json", launch_record)
    remaining = (session_deadline-time.monotonic())*1000
    require(remaining > 0, "original companion launch deadline expired")
    check_node_tool(directory)
    companion = launch(["node", str(directory / "browser.cjs"), str(receiver), str(directory / "browser-dom.json"),
                        str(directory / "browser-launch.json"), str(remaining), str(time.time()*1000)], "browser-companion")
    companion_birth = proc(companion.pid)
    require(companion_birth["pgid"] == browser_birth["pgid"], "browser companion changed original process group")
    ready_deadline = min(time.monotonic()+15, session_deadline)
    while time.monotonic() < ready_deadline:
        prerequisite_health()
        browser_active_failure(directory, companion_birth)
        browser_active(browser, browser_birth, profile, profile_identity, executable)
        check_browser_endpoint(profile, endpoint)
        require(browser_listener(browser.pid, endpoint["port"]) == endpoint["listener"], "original browser listener changed")
        if (directory / "browser-companion-ready.json").exists():
            ready = completion_record(directory / "browser-companion-ready.json")
            browser_ready_matches(ready, launch_record, digest(directory / "browser-launch.json"), companion_birth)
            break
        time.sleep(.1)
    else:
        raise RuntimeError("original browser companion readiness deadline exceeded")
    check_browser_executable(executable)
    def browser_health():
        prerequisite_health()
        browser_active_failure(directory, companion_birth)
        browser_active(browser, browser_birth, profile, profile_identity, executable)
        require(same_birth(proc(companion.pid), companion_birth), "original browser companion birth changed")
        check_browser_endpoint(profile, endpoint)
        require(browser_listener(browser.pid, endpoint["port"]) == endpoint["listener"], "original browser listener changed")
    browser_health()
    observe(directory, orca.pid, browser.pid, browser_health)
    browser_health()
    require(all(child.poll() is None for child in children), "required AT/browser service exited")
    parent_birth = proc(os.getpid())
    require(same_birth(parent_birth, runtime["sessionContract"]["parentBirth"]), "original completion parent birth changed")
    def finishing_health():
        required_children([child for child in children if child is not status], directory)
        browser_active_failure(directory, companion_birth)
        browser_active(browser, browser_birth, profile, profile_identity, executable)
        require(same_birth(proc(companion.pid), companion_birth), "original companion birth changed during completion")
        check_browser_endpoint(profile, endpoint)
        require(browser_listener(browser.pid, endpoint["port"]) == endpoint["listener"], "original browser listener changed during completion")
        contract_births(runtime, state)
    completion = finish_contract(directory, runtime, status, status_birth, parent_birth, finishing_health)
    runtime = json.loads((directory / "owned-bus-runtime.json").read_text())
    runtime["sessionContract"]["completion"] = completion
    write(directory / "owned-bus-runtime.json", runtime)
    finishing_health()
    require(status.poll() == 0 and all(child is status or child.poll() is None for child in children),
            "required AT/browser service exited after proven contract completion")


def observe(directory, orca_pid, browser_pid, health=lambda: None):
    import gi
    gi.require_version("Atspi", "2.0")
    from gi.repository import Atspi
    actions = []
    observations = {}

    def dom():
        health()
        value = json.loads((directory / "browser-dom.json").read_text())
        require(abs(time.time() * 1000 - value["at"]) < 2000, "browser companion stale")
        return value

    def wait(predicate, seconds=15):
        end = time.monotonic() + seconds
        last = None
        while time.monotonic() < end:
            try:
                value = dom()
                if predicate(value):
                    return value
            except (FileNotFoundError, json.JSONDecodeError) as ex:
                last = str(ex)
            time.sleep(.1)
        raise RuntimeError("bounded reference observation unavailable: " + str(last))

    def walk(node):
        yield node
        for index in range(node.get_child_count()):
            yield from walk(node.get_child_at_index(index))

    def focused(name):
        health()
        return any((item.get_name() or "") == name and item.get_state_set().contains(Atspi.StateType.FOCUSED)
                   for item in walk(Atspi.get_desktop(0)))

    def press(name):
        # Require real Tab focus plus AT-SPI agreement; duplicate nested scene labels cannot qualify.
        for _ in range(240):
            value = dom()
            active = value["active"]
            direct = (name == "Mount external authority reference" and active["id"] == "mount-external-authority-reference") or active["parentId"] == "external-authority-reference"
            if value["documentHasFocus"] and active["text"] == name and direct and focused(name):
                require(name == "Mount external authority reference" or value["reference"]["directButtons"].count(name) == 1, "direct reference button identity ambiguous")
                before_key = max([k["sequence"] for k in value["keys"]], default=0)
                subprocess.run(["xdotool", "key", "--clearmodifiers", "Return"], check=True, timeout=5)
                time.sleep(.3)
                after = dom()
                events = [k for k in after["keys"] if k["sequence"] > before_key and k["key"] == "Enter" and k["text"] == name and (k["parentId"] == "external-authority-reference" or k["id"] == "mount-external-authority-reference")]
                require(len(events) == 1, "fresh unique activation key absent")
                actions.append({"name": name, "key": "Return", "atspiFocused": True, "directReferenceControl": True, "eventSequence": events[0]["sequence"]})
                return
            subprocess.run(["xdotool", "key", "--clearmodifiers", "Tab"], check=True, timeout=5)
            time.sleep(.15)
        raise RuntimeError("keyboard focus did not reach exact reference control: " + name)

    def speech_offset():
        return (directory / "orca-debug.log").stat().st_size

    def speech(phase, start):
        end = time.monotonic() + 15
        while time.monotonic() < end:
            health()
            raw = (directory / "orca-debug.log").read_bytes()
            spoken = "\n".join(line.split("SPEECH OUTPUT:", 1)[1] for line in raw[start:].decode(errors="replace").splitlines() if "SPEECH OUTPUT:" in line)
            if PHRASES[phase] in spoken:
                value = dom()["reference"]
                value.update(speechStart=start, speechEnd=len(raw))
                observations[phase] = value
                return
            time.sleep(.1)
        raise RuntimeError("actual Orca " + phase + " announcement not observed")

    wait(lambda d: d["sequence"] > 0)
    windows = subprocess.check_output(["xdotool", "search", "--sync", "--onlyvisible", "--class", "chromium"], text=True, timeout=15).split()
    require(len(windows) == 1, "headed browser window identity ambiguous")
    subprocess.run(["xdotool", "windowactivate", "--sync", windows[0]], check=True, timeout=15)
    actual_browser_pid = int(subprocess.check_output(["xdotool", "getwindowpid", windows[0]], text=True, timeout=5))
    require(proc(actual_browser_pid) and proc(actual_browser_pid)["sid"] == os.getsid(0), "headed browser ownership mismatch")
    registered_window_browser = next(v for v in json.loads((directory / "resource-leaders.json").read_text()) if v["resource"] == "browser")
    browser_window_identity(actual_browser_pid, registered_window_browser)
    # Source-version correspondence is not evidence of the client loading that object.
    activation = json.loads((directory / "activation-provenance.json").read_text())
    objects = check_route_files(activation)
    mappings = {}
    registered_browser = next(v for v in json.loads((directory / "resource-leaders.json").read_text()) if v["resource"] == "browser")
    for client, pid, prefix in [("observer", os.getpid(), "libatspi.so."),
                                ("browser", actual_browser_pid, "libatk-bridge-2.0.so.")]:
        identity = proc(pid)
        with Path(f"/proc/{pid}/maps").open() as stream:
            maps = stream.read(4*1024**2+1)
        require(identity is not None and len(maps.encode()) <= 4*1024**2 and
                any(line.split()[-1] == objects[prefix]["resolvedPath"] for line in maps.splitlines() if line.split()),
                "actual AT client library mapping unavailable: " + client)
        require(same_birth(proc(pid), identity), "actual AT client birth changed during mapping read")
        mappings[client] = {"birth": identity, "object": objects[prefix]}
        if client == "browser":
            mappings[client]["ancestry"] = descendant_birth(identity, registered_browser)
    runtime = json.loads((directory / "owned-bus-runtime.json").read_text())
    runtime["mappedLibraries"] = mappings
    write(directory / "owned-bus-runtime.json", runtime)
    press("Mount external authority reference")
    press("Connect sample authority")
    press("Complete current external snapshot")
    press("Lose next command receipt")
    start = speech_offset()
    press("Increment external value")
    wait(lambda d: d["reference"]["receiptOrder"] == "sample:1:unknown")
    speech("unknown", start)
    press("Disconnect sample authority")
    press("Connect sample authority")
    press("Complete current external snapshot")
    observations["reconnected"] = dom()["reference"]
    press("Rearm sample commands")
    press("Increment external value")
    observations["prematureRearm"] = dom()["reference"]
    start = speech_offset()
    press("Reconcile unknown command")
    speech("reconciled", start)
    start = speech_offset()
    press("Rearm sample commands")
    speech("rearmed", start)
    press("Increment external value")
    observations["fresh"] = wait(lambda d: d["reference"]["receiptOrder"] == "sample:1:unknown,sample:2:accepted")["reference"]
    start = speech_offset()
    press("Dispose external reference")
    speech("disposed", start)
    press("Increment external value")
    observations["retainedInert"] = dom()["reference"]
    write(directory / "journey.json", {"process": {"name": "orca", "pid": orca_pid},
          "browser": {"family": "chromium", "pid": actual_browser_pid, "launcherPid": browser_pid, "companionPid": next(v["pid"] for v in json.loads((directory / "resource-leaders.json").read_text()) if v["resource"] == "browser-companion")}, "actions": actions, "observations": observations})


def activation_packet(manifest, versions, read, resolve, clock=time.monotonic, deadline=None, retained=None):
    """Read independent package-owned facts; service Exec values are never executed."""
    deadline = clock() + 15 if deadline is None else deadline
    texts, binaries, errors = [], [], []
    total = 0
    services = {}
    packet = {"schema": "fsgg.at-activation-provenance/1", "disposition": "incomplete", "versions": versions,
              "packageFileManifest": manifest, "services": services, "textFiles": texts, "binaries": binaries,
              "errors": errors, "omittedTextFiles": 0,
              "limits": "15s;64 texts;256KiB/text;1MiB text aggregate;32MiB/binary",
              "boundary": "installed activation metadata only; no Exec execution or foreground ownership proof"}
    if retained is not None:
        retained.update(packet)
    def checked_read(path, limit):
        require(clock() < deadline, "activation provenance deadline exceeded")
        target = resolve(path)
        require(target in manifest, "activation path resolves outside package manifest: " + path)
        data = read(target, limit)
        require(len(data) <= limit, "activation file size exceeded: " + path)
        require(clock() < deadline, "activation provenance deadline exceeded")
        return target, data
    def binary_fact(path):
        if any(v["path"] == path for v in binaries):
            return next(v for v in binaries if v["path"] == path)
        require(Path(path).is_absolute() and path in manifest, "activation executable not package-owned: " + path)
        target, binary = checked_read(path, 32 * 1024**2)
        fact = {"path": path, "resolvedPath": target, "package": manifest[path], "bytes": len(binary),
                "sha256": hashlib.sha256(binary).hexdigest()}
        binaries.append(fact)
        return fact
    relevant = [path for path in sorted(manifest) if
                ("/dbus-1/" in path or "at-spi" in path or "/systemd/" in path) and Path(path).suffix in [".service", ".conf"]]
    for index, path in enumerate(relevant):
        if len(texts) >= 64 or clock() >= deadline:
            errors.append("activation text count/deadline exceeded")
            packet["omittedTextFiles"] = len(relevant) - index
            break
        try:
            target, raw = checked_read(path, 256 * 1024)
            require(total + len(raw) <= 1024**2, "activation aggregate text budget exceeded: " + path)
            total += len(raw)
            text = raw.decode("utf-8")
            texts.append({"path": path, "resolvedPath": target, "package": manifest[path],
                          "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest(), "text": text})
            if "/dbus-1/" in path and path.endswith(".service"):
                service = configparser.ConfigParser(interpolation=None, strict=True)
                service.read_string(text)
                if not service.has_section("D-BUS Service"):
                    continue
                section = service["D-BUS Service"]
                name = section.get("Name")
                if name not in ["org.a11y.Bus", "org.a11y.atspi.Registry"]:
                    continue
                require(name not in services, "ambiguous activation service: " + name)
                fact = {"servicePath": path, "argvDataOnly": [], "executableSha256": None}
                services[name] = fact
                unit = section.get("SystemdService")
                if unit:
                    fact["systemdDelegation"] = unit
                    fact["referencedUnitPaths"] = [p for p in manifest if "/systemd/" in p and Path(p).name == unit]
                    errors.append("unresolved systemd activation delegation: " + name)
                    if len(fact["referencedUnitPaths"]) != 1:
                        errors.append("referenced activation unit missing/ambiguous: " + unit)
                argv = shlex.split(section.get("Exec", ""))
                fact["argvDataOnly"] = argv
                require(argv, "activation executable missing: " + name)
                fact["executableSha256"] = binary_fact(argv[0])["sha256"]
        except Exception as ex:
            errors.append(path + ": " + str(ex))
    # Independent binary identities remain useful even if one activation service is malformed.
    for path in sorted(manifest):
        if Path(path).name in ["dbus-run-session", "dbus-daemon", "at-spi-bus-launcher", "at-spi2-registryd"] or any(Path(path).name.startswith(prefix) for prefix in LIBRARY_PREFIXES+["libgio-2.0.so."]):
            try:
                binary_fact(path)
            except Exception as ex:
                errors.append(path + ": " + str(ex))
    if set(services) != {"org.a11y.Bus", "org.a11y.atspi.Registry"}:
        errors.append("required activation service unavailable")
    if not any(Path(v["path"]).name == "dbus-daemon" for v in binaries):
        errors.append("D-Bus daemon identity unavailable")
    if clock() >= deadline:
        errors.append("activation provenance deadline exceeded")
    packet["disposition"] = "incomplete" if errors else "complete"
    return packet


def capture_activation(output):
    deadline = time.monotonic() + 15
    manifest = {}
    versions = {}
    packet = {}
    query_errors = []
    try:
        for package in ["at-spi2-core", "dbus", "dbus-daemon", "dbus-session-bus-common", "libatspi2.0-0t64", "libatk-bridge2.0-0t64",
                        "gsettings-desktop-schemas", "libglib2.0-0t64"]:
            def query(*args):
                remaining = deadline - time.monotonic()
                require(remaining > 0, "activation provenance deadline exceeded")
                result = subprocess.run(["dpkg-query", *args, package], capture_output=True, timeout=remaining, check=True)
                require(len(result.stdout) <= 1024**2 and len(result.stderr) <= 1024**2, "package metadata output exceeded")
                return result.stdout.decode("utf-8")
            try:
                versions[package] = query("--show", "--showformat=${Version}").strip()
                for path in query("--listfiles").splitlines():
                    if Path(path).is_file():
                        manifest[path] = package
                        require(len(json.dumps(manifest).encode()) <= 512 * 1024, "package file manifest exceeded")
            except Exception as ex:
                query_errors.append(package + ": " + str(ex))
        def read(path, limit):
            with Path(path).open("rb") as stream:
                return stream.read(limit + 1)
        packet = activation_packet(manifest, versions, read, lambda p: str(Path(p).resolve()),
                                   deadline=deadline, retained=packet)
        if query_errors:
            packet["errors"].extend(query_errors)
            packet["disposition"] = "incomplete"
        require(len(json.dumps(packet).encode()) <= 4 * 1024**2, "activation packet output exceeded")
        packet["sourceProof"] = SOURCE_PROOF
        packet["selectedRoute"] = "explicit-owned-private-bus-registry"
        # The vendor activation declaration can remain incomplete; the selected route has a separate gate.
        try:
            packet["routeObjectIdentities"] = route_metadata(packet)
            packet["routePrerequisites"] = "complete"
        except BaseException as ex:
            packet["routePrerequisites"] = "incomplete"
            packet["routeFirstCause"] = str(ex)
        write(output, packet)
        require(packet["routePrerequisites"] == "complete", "private route prerequisites incomplete: " + str(packet.get("routeFirstCause")))
    except BaseException as ex:
        packet.update(schema="fsgg.at-activation-provenance/1", disposition="incomplete", firstCause=str(ex),
                      versions=versions, packageFileManifest=manifest)
        write(output, packet)
        raise


def execute_session(receiver, directory, env, termination):
    first = None
    result = None
    peak = 0
    first_guard = None
    reporting_errors = []
    require(not termination, termination[0] if termination else "")
    deadline = time.monotonic() + 300
    write(directory / "session-budget.json", {"deadline": deadline, "seconds": 300})
    with (directory / "session.log").open("xb") as log:
        check_launch_object(directory, "/usr/bin/dbus-run-session")
        child = subprocess.Popen(session_argv(directory, receiver), env=env, stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
        leader = proc(child.pid)
        if not leader or leader["sid"] != child.pid:
            write(directory / "process-result.json", {"exit": child.poll(), "firstCause": "fresh AT session custody unavailable",
                  "cleanup": {"disposition": "unknown", "unknown": [child.pid]}, "signals": [], "noRetry": True})
            raise RuntimeError("fresh AT session custody unavailable; original identity observation required")
        known = {child.pid: leader["start"]}
        try:
            while True:
                require(not termination, termination[0] if termination else "")
                child.poll()
                owned, unknown, escaped = census(leader, known)
                if unknown or escaped:
                    # Preserve the actual first rejected sample before cleanup can change it.
                    first = "AT custody uncertainty"
                    first_guard = {"stage": "AT session supervision", "monotonic": time.monotonic(),
                                   "leader": copy.deepcopy(leader), "knownStarts": dict(known),
                                   "branches": {"unknown": bool(unknown), "escaped": bool(escaped)},
                                   "counts": {"owned": len(owned), "unknown": len(unknown), "escaped": len(escaped)},
                                   "rows": {name: copy.deepcopy(rows[:1024]) for name, rows in
                                            [("owned", owned), ("unknown", unknown), ("escaped", escaped)]},
                                   "omittedRows": {name: max(0, len(rows) - 1024) for name, rows in
                                                   [("owned", owned), ("unknown", unknown), ("escaped", escaped)]}}
                    try:
                        write(directory / "first-guard-census.json", first_guard)
                    except BaseException as ex:
                        reporting_errors.append("first guard write: " + str(ex))
                    raise RuntimeError(first)
                peak = max(peak, sum(row["rss"] for row in owned) + proc(os.getpid())["rss"])
                require(peak <= 2 * 1024**3, "sampled AT RSS budget exceeded")
                require(all(p.stat().st_size <= 4 * 1024**2 for p in directory.rglob("*.log")), "AT log budget exceeded")
                require(time.monotonic() < deadline, "original five-minute AT deadline exceeded")
                if child.poll() is not None:
                    causal = directory / "inner-result.json"
                    inner_cause = json.loads(causal.read_text()).get("firstCause") if causal.exists() else None
                    if inner_cause is None:
                        log.flush()
                        with (directory / "session.log").open() as retained:
                            prefixes = [line.rstrip()[len("INNER_FIRST_CAUSE "):] for line in retained
                                        if line.startswith("INNER_FIRST_CAUSE ")]
                        inner_cause = prefixes[0] if prefixes else None
                    require(child.returncode == 0, inner_cause or "first original AT exit " + str(child.returncode))
                    break
                time.sleep(.1)
        except BaseException as ex:
            if first is None:
                first = str(ex)
        finally:
            try:
                result = cleanup(leader, known, child)
            except BaseException as ex:
                result = {"disposition": "unknown", "unknown": ["cleanup observation failed"], "reportingError": str(ex)}
            if first is None and termination:
                first = termination[0]
            snapshot_sha = None
            if first_guard and not reporting_errors:
                try:
                    snapshot_sha = digest(directory / "first-guard-census.json")
                except BaseException as ex:
                    reporting_errors.append("first guard hash: " + str(ex))
            process_result = {"leader": leader, "knownStarts": known, "exit": child.returncode,
                  "firstCause": first, "termination": termination, "cleanup": result, "sampledPeakRss": peak,
                  "firstGuardCensus": first_guard, "reportingErrors": reporting_errors,
                  "historicalCustody": "unresolved" if first_guard else "no rejected census observed",
                  "firstGuardCensusSha256": snapshot_sha,
                  "limits": "100ms ancestry/RSS samples, no hard containment; detached unobserved descendants unknown"}
            try:
                write(directory / "process-result.json", process_result)
            except BaseException as ex:
                reporting_errors.append("process result write: " + str(ex))
                if first is None:
                    first = "AT process result reporting failed"
                # A separate best-effort report is not an operation retry.
                try:
                    write(directory / "reporting-failure.json", {"firstCause": first,
                          "reportingErrors": reporting_errors, "processResult": process_result})
                except BaseException:
                    pass
    require(first is None, first)
    require(result["disposition"] == "observed-empty", "AT cleanup incomplete")
    return child.returncode, result


def qualify(out, preflight_path, termination):
    packet_path = out / "qualification.json"
    packet = json.loads(packet_path.read_text())
    preflight = json.loads(preflight_path.read_text())
    errors = prerequisites(packet, preflight, shutil.which)
    receiver = out / "complete"
    for row in packet.get("receiver", []):
        try:
            if digest(receiver / "SvgFoundation" / row["path"]) != row["sha256"]:
                errors.append("generated receiver input changed: " + row["path"])
        except (FileNotFoundError, KeyError, TypeError) as ex:
            errors.append("generated receiver prerequisite malformed/missing: " + str(ex))
    if not packet.get("receiver"):
        errors.append("generated receiver manifest absent")
    require(subprocess.check_output(["git", "-C", str(ROOT), "rev-parse", "HEAD"], text=True).strip() == packet["templates"]["revision"], "checked-out consumer mismatch")
    missing = ["tool:" + name for name in TOOLS if not shutil.which(name)]
    missing += ["Python module:" + name for name in ["gi", "speechd"] if importlib.util.find_spec(name) is None]
    missing += ["file:" + name for name in ["/etc/speech-dispatcher/speechd.conf", "/etc/speech-dispatcher/modules/espeak-ng.conf"] if not Path(name).is_file()]
    missing += ["generated input:" + str(path) for path in [receiver / "artifacts/authority-server/Server.dll", receiver / "Browser.Tests/node_modules/@playwright/test/package.json"] if not path.is_file()]
    errors += missing
    require(not errors, "independent AT prerequisites unavailable: " + "; ".join(errors))
    activation = out / "orca-activation-provenance.json"
    require(activation.is_file() and activation.stat().st_size <= 5 * 1024**2, "activation provenance unavailable/oversized")
    activation_packet_value = json.loads(activation.read_text())
    check_route_files(activation_packet_value)
    served_digest = digest(receiver / "artifacts/authority-server/Server.dll")
    directory = out / "orca"
    directory.mkdir(mode=0o700)
    shutil.copyfile(packet_path, directory / "source-qualification.json")
    shutil.copyfile(activation, directory / "activation-provenance.json")
    # A short fresh mode0700 root avoids UNIX socket path truncation. Retain it on unknown cleanup.
    socket_root = Path(tempfile.mkdtemp(prefix="fsgg-at-", dir="/tmp"))
    root_stat = socket_root.stat()
    root_identity = {"device": root_stat.st_dev, "inode": root_stat.st_ino, "uid": root_stat.st_uid}
    sockets = {name: str(socket_root / (name+".sock")) for name in ["session", "accessibility"]}
    for name, socket in sockets.items():
        (directory / (name+".conf")).write_bytes(closed_bus_config(socket, os.getuid()))
    write(directory / "owned-bus-route.json", {"sourceProof": SOURCE_PROOF, "uid": os.getuid(),
          "socketRoot": str(socket_root), "socketRootIdentity": root_identity, "sockets": sockets, "sessionArgv": session_argv(directory, receiver),
          "registryArgv": ["/usr/libexec/at-spi2-registryd"], "configBoundary": "exact closed serializer; no activation"})
    write(directory / "tool-identities.json", {name: {"path": shutil.which(name), "sha256": digest(Path(shutil.which(name)).resolve())} for name in TOOLS})
    # No inherited session/audio/display/config credentials enter the isolated AT stage.
    env = {key: os.environ[key] for key in ["HOME", "PATH", "LANG", "PLAYWRIGHT_BROWSERS_PATH"] if key in os.environ}
    env.update(PYTHONDONTWRITEBYTECODE="1", DISPLAY=":97", NO_AT_BRIDGE="0", GTK_MODULES="gail:atk-bridge",
               GSETTINGS_BACKEND="keyfile", GNOME_ACCESSIBILITY="1", XDG_CONFIG_HOME=str(directory / "config"),
               XDG_CACHE_HOME=str(directory / "cache"), XDG_DATA_HOME=str(directory / "data"),
               XDG_RUNTIME_DIR=str(directory / "runtime"), TMPDIR=str(directory / "tmp"),
               PULSE_SERVER="unix:" + str(directory / "pulse.sock"), SPEECHD_ADDRESS="unix_socket:" + str(directory / "speech.sock"))
    for name in ["config", "cache", "data", "runtime", "tmp"]:
        (directory / name).mkdir(mode=0o700)
    metadata = out / "orca-host-packages.txt"
    require(metadata.is_file() and metadata.stat().st_size > 0, "actual installed AT package metadata unavailable")
    shutil.copyfile(metadata, directory / "host-packages.txt")
    runtime_exit, result = execute_session(receiver, directory, env, termination)
    current_root = socket_root.stat()
    require(socket_root.is_dir() and stat.S_IMODE(current_root.st_mode) == 0o700 and
            {"device": current_root.st_dev, "inode": current_root.st_ino, "uid": current_root.st_uid} == root_identity,
            "owned socket root custody changed; retain unknown root")
    shutil.rmtree(socket_root)
    require(digest(receiver / "artifacts/authority-server/Server.dll") == served_digest, "served assembly input changed")
    journey = json.loads((directory / "journey.json").read_text())
    journey["browser"]["transportOutcome"] = browser_transport_outcome(directory, completion_record(directory / "browser-launch.json"),
         next(v for v in json.loads((directory / "resource-leaders.json").read_text()) if v["resource"] == "browser-companion"))
    receipt = {"schema": SCHEMA, "result": "passed", "templates": packet["templates"], "caller": preflight["caller"],
               "producer": preflight["producer"], **journey, "keyboard": "xdotool-X11", "speechBoundary": "Orca SPEECH OUTPUT",
               "physicalAudioHardware": "not-observed", "cleanup": result, "sourceQualificationSha256": digest(packet_path),
               "servedAssemblySha256": served_digest,
               "evidenceSha256": {name: digest(directory / name) for name in ["orca-debug.log", "journey.json", "process-result.json", "speech-preflight.json", "tool-identities.json", "source-qualification.json", "host-packages.txt", "resource-leaders.json", "activation-provenance.json", "owned-bus-route.json", "owned-bus-runtime.json", "session.conf", "accessibility.conf", "session-contract-state.json", "session-budget.json", *FINISH_FILES, *BROWSER_FILES]}}
    try:
        validate(receipt, packet, preflight, directory)
    except BaseException as ex:
        write(directory / "bind-result.json", {"exit": 1, "firstCause": type(ex).__name__ + ": " + str(ex),
              "runtimeExit": runtime_exit, "cleanup": result})
        raise
    write(directory / "bind-result.json", {"exit": 0, "firstCause": None, "runtimeExit": runtime_exit, "cleanup": result})
    receipt["evidenceSha256"]["bind-result.json"] = digest(directory / "bind-result.json")
    require(not termination, termination[0] if termination else "")
    write(directory / "observation.json", receipt)
    # Preserve the candidate result bytes: AT qualification is an additional independently bound receipt.
    print("PASS external-reference actual Orca keyboard/receipt journey; evidence=" + str(directory / "observation.json"))


def self_test():
    with tempfile.TemporaryDirectory() as temporary:
        directory = Path(temporary) / "orca"
        directory.mkdir()
        packet = {"templates": {"revision": "a" * 40, "tree": "b" * 40}}
        preflight = {**packet, "disposition": "preflight-passed", "requestedPhase": "full",
                     "caller": {"repository": "FS-GG/FS.GG.Rendering", "revision": "c" * 40, "run": "1", "attempt": "1"},
                     "producer": {"revision": "d" * 40, "custodySha256": "e" * 64}}
        packet.update(disposition="passed", producer={"revision": "d" * 40, "custodyManifestSha256": "e" * 64},
                      passedPerFamily=8, skipped=0, browserFamilies=["chromium", "firefox", "webkit"])
        require(not prerequisites(packet, preflight, lambda _: True), "good prerequisite refused")
        bad_inputs = []
        for field, value in [("disposition", "unknown"), ("passedPerFamily", 4), ("skipped", 1), ("templates", {}), ("producer", {}), ("browserFamilies", ["chromium"])]:
            bad = copy.deepcopy(packet); bad[field] = value; bad_inputs.append(bad)
        for bad in bad_inputs:
            require(prerequisites(bad, preflight, lambda _: True), "bad prerequisite could launch AT")
        require(prerequisites({}, {}, lambda _: False), "malformed/missing-tool input could launch AT")
        bad_phase = copy.deepcopy(preflight); bad_phase["requestedPhase"] = "preflight"
        require(prerequisites(packet, bad_phase, lambda _: True), "preflight-only input could launch AT")
        write(directory / "source-qualification.json", packet)
        raw = b""
        observations = {}
        original = {"commandOrder": "sample:1:external.increment", "receiptOrder": "sample:1:unknown", "unknownCorrelation": "sample:1", "unknownEpoch": "epoch-A", "unknownGeneration": "1", "commandSuspended": "true", "rootCount": 1, "statusCount": 1}
        for phase, phrase in PHRASES.items():
            begin = len(raw)
            raw += ("SPEECH OUTPUT: " + phrase + (" Commands are suspended; reconnect never retries it" if phase == "unknown" else "") + "\n").encode()
            observations[phase] = {**original, "speechStart": begin, "speechEnd": len(raw)}
        observations["reconnected"] = copy.deepcopy(original)
        observations["prematureRearm"] = copy.deepcopy(original)
        observations["reconciled"]["commandRecovery"] = "Reconciled"
        observations["fresh"] = {**original, "commandOrder": "sample:1:external.increment,sample:2:external.increment", "receiptOrder": "sample:1:unknown,sample:2:accepted"}
        observations["disposed"].update(observations["fresh"])
        observations["disposed"]["authorityRevision"] = "3"
        observations["disposed"].update({key + "Owned": "0" for key in ["command", "gateway", "host", "input", "button", "svg"]})
        observations["retainedInert"] = copy.deepcopy(observations["disposed"])
        (directory / "orca-debug.log").write_bytes(raw)
        names = ["Mount external authority reference", "Connect sample authority", "Complete current external snapshot", "Lose next command receipt", "Increment external value", "Disconnect sample authority", "Rearm sample commands", "Reconcile unknown command", "Dispose external reference"]
        receipt = {"schema": SCHEMA, "result": "passed", **preflight, "process": {"name": "orca", "pid": 1}, "browser": {"family": "chromium", "pid": 2, "launcherPid": 2, "companionPid": 60},
                   "keyboard": "xdotool-X11", "speechBoundary": "Orca SPEECH OUTPUT", "physicalAudioHardware": "not-observed",
                   "cleanup": {"disposition": "observed-empty", "unknown": [], "remaining": []}, "sourceQualificationSha256": digest(directory / "source-qualification.json"),
                   "evidenceSha256": {"orca-debug.log": digest(directory / "orca-debug.log")}, "observations": observations,
                   "actions": [{"name": name, "key": "Return", "atspiFocused": True, "directReferenceControl": True, "eventSequence": index + 1} for index, name in enumerate(names)]}
        write(directory / "process-result.json", {"exit": 0, "firstCause": None, "cleanup": receipt["cleanup"]})
        receipt["evidenceSha256"]["process-result.json"] = digest(directory / "process-result.json")
        write(directory / "journey.json", {key: receipt[key] for key in ["process", "browser", "actions", "observations"]})
        activation = route_fixture()
        write(directory / "activation-provenance.json", activation)
        route_fixture_evidence(directory, activation)
        for name in ["owned-bus-route.json", "owned-bus-runtime.json", "session.conf", "accessibility.conf",
                     "session-contract-state.json", "session-budget.json", "journey.json", *FINISH_FILES, *BROWSER_FILES]:
            receipt["evidenceSha256"][name] = digest(directory / name)
        receipt["evidenceSha256"]["activation-provenance.json"] = digest(directory / "activation-provenance.json")
        require(validate(receipt, packet, preflight, directory), "good AT fixture refused")
        for file, replacement in [("process-result.json", {"exit": 0, "firstCause": None, "cleanup": receipt["cleanup"], "firstGuardCensus": {"unknown": [43]}}),
                                  ("activation-provenance.json", {"schema": "fsgg.at-activation-provenance/1", "disposition": "incomplete", "services": {}})]:
            original_bytes = (directory / file).read_bytes()
            write(directory / file, replacement)
            bad = copy.deepcopy(receipt)
            bad["evidenceSha256"][file] = digest(directory / file)
            try:
                validate(bad, packet, preflight, directory)
            except RuntimeError:
                pass
            else:
                raise RuntimeError("historical custody/incomplete provenance accepted")
            (directory / file).write_bytes(original_bytes)
        changes = [lambda r: r.update(result="not-run"), lambda r: r["templates"].update(revision="wrong"),
                   lambda r: r["caller"].update(run="wrong"), lambda r: r["producer"].update(revision="wrong"),
                   lambda r: r.update(speechBoundary="DOM"), lambda r: r["process"].update(name="mock"),
                   lambda r: r["cleanup"].update(disposition="unknown"), lambda r: r["observations"]["unknown"].update(speechEnd=0),
                   lambda r: r["observations"]["unknown"].update(statusCount=2),
                   lambda r: r["observations"]["reconnected"].update(commandOrder="replayed"),
                   lambda r: r["observations"]["prematureRearm"].update(commandSuspended="false"),
                   lambda r: r["observations"]["fresh"].update(unknownCorrelation="sample:2"),
                   lambda r: r["observations"]["disposed"].update(hostOwned="1"),
                   lambda r: r["observations"]["retainedInert"].update(authorityRevision="4"),
                   lambda r: r["actions"][0].update(atspiFocused=False), lambda r: r["actions"][0].update(directReferenceControl=False),
                   lambda r: r["evidenceSha256"].update({"orca-debug.log": "0" * 64})]
        for change in changes:
            bad = copy.deepcopy(receipt)
            change(bad)
            try:
                validate(bad, packet, preflight, directory)
            except (RuntimeError, KeyError):
                pass
            else:
                raise RuntimeError("bad AT fixture accepted")
        for outcome in [{"exit": 124, "firstCause": "timeout"}, {"exit": 1, "firstCause": "original failure"}, {"exit": None, "firstCause": "unknown"}]:
            write(directory / "process-result.json", {**outcome, "cleanup": receipt["cleanup"]})
            bad = copy.deepcopy(receipt)
            bad["evidenceSha256"]["process-result.json"] = digest(directory / "process-result.json")
            try:
                validate(bad, packet, preflight, directory)
            except RuntimeError:
                pass
            else:
                raise RuntimeError("timeout/failed/unknown original process accepted")
        # Missing speech cannot be replaced by an otherwise matching DOM/ledger report.
        write(directory / "process-result.json", {"exit": 0, "firstCause": None, "cleanup": receipt["cleanup"]})
        for phase in PHRASES:
            bad = copy.deepcopy(receipt)
            bad["observations"][phase]["speechEnd"] = 0
            try:
                validate(bad, packet, preflight, directory)
            except RuntimeError:
                pass
            else:
                raise RuntimeError("missing actual phase speech accepted")
        (directory / "orca-debug.log").write_bytes(raw.replace(b"SPEECH OUTPUT:", b"DOM OBSERVED::"))
        bad = copy.deepcopy(receipt)
        bad["evidenceSha256"]["orca-debug.log"] = digest(directory / "orca-debug.log")
        try:
            validate(bad, packet, preflight, directory)
        except RuntimeError:
            pass
        else:
            raise RuntimeError("DOM text substituted for Orca speech")
    workflow = (ROOT / ".github/workflows/fable-external-reference-source.yml").read_text()
    workflow_guard(workflow)
    for bad in [workflow.replace("external-reference-orca.py --self-test", "true"), workflow.replace("if: ${{ !inputs.preflight-only }}", "if: always()"), workflow.replace("external-reference/orca/**", "missing"), workflow.replace("--capture-activation", "--missing-capture"), workflow.replace("${{ runner.temp }}/external-reference/orca-activation-provenance.json", "missing")]:
        try:
            workflow_guard(bad)
        except (RuntimeError, IndexError):
            pass
        else:
            raise RuntimeError("unsafe AT workflow accepted")
    supervision_self_test()
    diagnostic_self_test()
    route_self_test()
    contract_controls = contract_self_test()
    print("PASS actual AT binder: good receipt, 25 existing plus 2 diagnostic refusal controls; 8 prerequisite refusals and workflow bad controls; no AT/browser launched")
    return contract_controls + browser_self_test()



def route_fixture():
    versions = {p: SOURCE_PROOF["atSpiSource"] for p in ["at-spi2-core", "libatspi2.0-0t64", "libatk-bridge2.0-0t64"]}
    versions.update({p: SOURCE_PROOF["dbusSource"] for p in ["dbus", "dbus-daemon", "dbus-session-bus-common"]})
    paths = ROUTE_PATHS + ["/usr/lib/fixture/libatspi.so.0", "/usr/lib/fixture/libatk-bridge-2.0.so.0"]
    packages = ["dbus-daemon", "dbus-daemon", "at-spi2-core", "libatspi2.0-0t64", "libatk-bridge2.0-0t64"]
    facts = [{"path": path, "resolvedPath": path, "package": package, "bytes": 1, "sha256": "a"*64}
             for path, package in zip(paths, packages)]
    return {"schema": "fsgg.at-activation-provenance/1", "disposition": "incomplete", "sourceProof": SOURCE_PROOF,
            "versions": versions, "services": {"org.a11y.Bus": {"systemdDelegation": "at-spi-dbus-bus.service"},
            "org.a11y.atspi.Registry": {}}, "errors": ["unresolved systemd activation delegation: org.a11y.Bus"],
            "binaries": facts, "packageFileManifest": {v["path"]: v["package"] for v in facts}}


def contract_fixture_evidence(directory, activation, runtime, leaders, parent_birth=None, complete=True):
    birth = {"pid": 61, "start": 11, "ppid": runtime["bus"]["ppid"], "sid": runtime["bus"]["sid"]}
    parent_birth = parent_birth or {"pid": birth["ppid"], "start": 420, "ppid": 44, "sid": birth["sid"]}
    gio = {"path": "/usr/lib/fixture/libgio-2.0.so.0", "resolvedPath": "/usr/lib/fixture/libgio-2.0.so.0",
           "package": "libglib2.0-0t64", "bytes": 1, "sha256": "a"*64}
    activation["versions"].update({"libglib2.0-0t64": "fixture-glib-version", "gsettings-desktop-schemas": "fixture-schemas-version"})
    activation["binaries"].append(gio)
    activation["packageFileManifest"].update({gio["path"]: gio["package"]})
    schemas = {}
    for name, (schema, key) in STATUS_KEYS.items():
        path = "/usr/share/glib-2.0/schemas/"+schema+".gschema.xml"
        activation["packageFileManifest"][path] = "gsettings-desktop-schemas"
        schemas[name] = {"schema": schema, "key": key, "type": "b", "sourcePath": path,
                         "package": "gsettings-desktop-schemas", "packageVersion": "fixture-schemas-version", "sourceSha256": "b"*64,
                         "compiledPath": "/usr/share/glib-2.0/schemas/gschemas.compiled", "compiledSha256": "c"*64}
    settings = {"backend": "GKeyfileSettingsBackend", "backendRoute": "keyfile", "gioObject": gio, "gioPackageVersion": "fixture-glib-version",
                "schemas": schemas, "privateKeyfile": str(directory / "config/glib-2.0/settings/keyfile"),
                "persistence": "strict refusal on failed write/readback or backend/cache disagreement"}
    values = {"IsEnabled": True, "ScreenReaderEnabled": True}
    contract = {"name": "org.a11y.Bus", "uniqueOwner": ":1.2", "pid": 61, "birth": birth,
                "address": runtime["address"], "initialValues": values, "settings": settings,
                "sourceSha256": CONTRACT_SOURCE_SHA256, "observerSourceSha256": digest(Path(__file__).resolve()), "parentBirth": parent_birth, "readyBeforeOrca": True}
    runtime["sessionContract"] = contract
    leaders.append({"resource": "session-contract", **birth})
    write(directory / "session-contract-state.json", {"birth": birth, "parentBirth": parent_birth, "observerSourceSha256": digest(Path(__file__).resolve()), "sourceSha256": CONTRACT_SOURCE_SHA256,
          "address": runtime["address"], "sessionAddress": runtime["sessionAddress"], "initialValues": values, "settings": settings})
    if not (directory / "session-budget.json").exists():
        write(directory / "session-budget.json", {"deadline": 300, "seconds": 300})
    path = directory / "config/glib-2.0/settings/keyfile"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("[org/gnome/desktop/interface]\ntoolkit-accessibility=true\n\n"
                    "[org/gnome/desktop/a11y/applications]\nscreen-reader-enabled=true\n")
    write(directory / "activation-provenance.json", activation)
    if complete:
        if not (directory / "journey.json").exists():
            write(directory / "journey.json", {"inertFixture": True})
        identity = completion_identity(directory, runtime, parent_birth, birth, contract["uniqueOwner"])
        atomic_record_once(directory / FINISH_FILES[0], {"schema": FINISH_SCHEMA, "phase": "request", "identity": identity})
        complete_contract_child(directory, identity, lambda: None, lambda: None, clock=lambda: 0)
        result = {"schema": FINISH_SCHEMA, "phase": "reaped", "identity": identity,
                  "requestSha256": digest(directory / FINISH_FILES[0]), "ackSha256": digest(directory / FINISH_FILES[1]),
                  "childExit": 0, "reaped": True, "firstCause": None}
        atomic_record_once(directory / FINISH_FILES[2], result)
        contract["completion"] = result
    return contract


def route_fixture_evidence(directory, activation, uid=1000, complete=True):
    sockets = {name: "/tmp/fsgg-at-fixture/"+name+".sock" for name in ["session", "accessibility"]}
    for name, socket in sockets.items():
        (directory / (name+".conf")).write_bytes(closed_bus_config(socket, uid))
    write(directory / "owned-bus-route.json", {"sourceProof": SOURCE_PROOF, "uid": uid, "sockets": sockets})
    bus = {"pid": 40, "start": 1, "ppid": 42, "sid": 42}
    registry = {"pid": 41, "start": 2, "ppid": 42, "sid": 42}
    selected = route_metadata(activation)
    browser = {"pid": 2, "start": 10, "ppid": 42, "sid": 42, "pgid": 42}
    launcher = {"pid": 60, "start": 9, "ppid": 42, "sid": 42, "pgid": 42}
    leaders = [{"resource": "accessibility-bus", **bus}, {"resource": "registry", **registry}, {"resource": "browser", **browser}, {"resource": "browser-companion", **launcher}]
    runtime = {"bus": bus, "address": "unix:path="+sockets["accessibility"]+",guid="+"a"*32,
          "sessionBus": {"pid": 43, "start": 3, "ppid": 44, "sid": 42},
          "sessionAddress": "unix:path="+sockets["session"]+",guid="+"b"*32,
          "registry": {"pid": 41, "birth": registry}, "addressSetBeforeAtspiImport": True, "objectIdentities": selected,
          "mappedLibraries": {"observer": {"birth": bus, "object": selected["libatspi.so."]},
                              "browser": {"birth": browser, "ancestry": [browser], "object": selected["libatk-bridge-2.0.so."]}}}
    contract_fixture_evidence(directory, activation, runtime, leaders, complete=complete)
    write(directory / "resource-leaders.json", leaders)
    write(directory / "owned-bus-runtime.json", runtime)
    browser_fixture_evidence(directory, browser, launcher, uid, complete)


def browser_fixture_executable():
    return {'path': '/private/chromium-1243/chrome-linux64/chrome', 'bytes': 100, 'sha256': 'e'*64,
            'device': 1, 'inode': 2, 'mtimeNs': 3, 'version': '153.0.8010.12', 'revision': '1243',
            'lockSha256': BROWSER_LOCK_SHA, 'packageSha256': BROWSER_PACKAGE_SHA, 'registrySha256': BROWSER_REGISTRY_SHA, 'coreBundleSha256': BROWSER_CORE_SHA,
            'actualLockSha256': BROWSER_LOCK_SHA, 'dependencyGraphSha256': BROWSER_LOCK_GRAPH_SHA, 'generatedPackageName': 'fablegameworkspace-browser-tests'}


def browser_fixture_endpoint():
    raw = b'1234\n/devtools/browser/fixture\n'
    return {**browser_endpoint_bytes(raw), 'file': {'device': 1, 'inode': 2, 'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()},
            'listener': {'family': 'tcp', 'address': '0100007F', 'port': 1234, 'inode': '987'}}


def browser_fixture_ready(launch, launch_sha, companion):
    return {'schema': BROWSER_SCHEMA, 'launchSha256': launch_sha, 'browserBirth': launch['browserBirth'],
            'companionBirth': {k: companion[k] for k in ['pid', 'start', 'ppid', 'pgid', 'sid']},
            'endpoint': launch['endpoint']['endpoint'], 'profile': launch['profile'], 'sourceSha256': launch['companionSourceSha256'],
            'noDefaults': True, 'contexts': 1, 'initialPages': 1, 'initialURL': 'about:blank',
            'pageURL': 'http://127.0.0.1:5100/', 'sampleSequence': 1}


def browser_fixture_evidence(directory, browser, companion, uid=1000, complete=True):
    write(directory / 'tool-identities.json', {'node': {'path': '/selected/node', 'sha256': 'a'*64}})
    (directory / 'browser.cjs').write_text(BROWSER)
    (directory / 'browser-companion.log').write_text('')
    value = {'schema': BROWSER_SCHEMA, 'sourceSha256': digest(Path(__file__).resolve()),
             'playwrightSourceSha256': BROWSER_PLAYWRIGHT_SOURCE_SHA, 'nodeSourceCommit': BROWSER_NODE_SOURCE,
             'executable': browser_fixture_executable(), 'nodeTool': {'path': '/selected/node', 'sha256': 'a'*64}, 'argv': browser_argv(browser_fixture_executable()['path'], directory / 'profile'),
             'profile': {'path': str(directory / 'profile'), 'device': 1, 'inode': 2, 'uid': uid},
             'endpoint': browser_fixture_endpoint(), 'browserBirth': {k: browser[k] for k in ['pid', 'start', 'ppid', 'pgid', 'sid']},
             'companionSourceSha256': digest(directory / 'browser.cjs'), 'absoluteDeadline': 300}
    write(directory / 'browser-launch.json', value)
    write(directory / 'browser-companion-ready.json', browser_fixture_ready(value, digest(directory / 'browser-launch.json'), companion))
    if complete:
        runtime = completion_record(directory / 'owned-bus-runtime.json')
        write(directory / 'inner-result.json', {'schema': 'fsgg.at-inner-result/1', 'exit': 0, 'firstCause': None,
             'sourceSha256': digest(Path(__file__).resolve()), 'parentBirth': runtime['sessionContract']['completion']['identity']['parentBirth'],
             'browserBirth': value['browserBirth'], 'companionBirth': {k: companion[k] for k in ['pid', 'start', 'ppid', 'pgid', 'sid']},
             'completionSha256': digest(directory / FINISH_FILES[2]), 'journeySha256': digest(directory / 'journey.json'),
             'launchSha256': digest(directory / 'browser-launch.json')})


def browser_window_identity(actual_pid, registered, reader=None):
    reader = proc if reader is None else reader
    require(actual_pid == registered['pid'] and same_birth(reader(actual_pid), registered) and
            reader(actual_pid)['pgid'] == registered['pgid'] == registered['sid'],
            'actual X11 browser PID is not original registered Chrome leader')


def browser_self_test():
    from unittest.mock import patch
    from types import SimpleNamespace
    checked = []
    def case(name, work):
        work()
        checked.append(name)
    def refused(work, phrase=None):
        try:
            work()
        except (RuntimeError, KeyError, ValueError, OSError) as error:
            require(phrase is None or phrase in str(error), 'browser first cause changed')
        else:
            raise RuntimeError('invalid owned browser fixture accepted')
    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary); dependencies = root / 'Browser.Tests'; dependencies.mkdir()
        graph = {'name': 'fablegameworkspace-browser-tests', 'lockfileVersion': 3,
                 'packages': {'': {'name': 'fablegameworkspace-browser-tests', 'devDependencies': {'@playwright/test': '1.63.0'}}}}
        graph_sha = hashlib.sha256(json.dumps(graph, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
        package = {'name': 'generated-browser-tests', 'devDependencies': {'@playwright/test': '1.63.0'}}
        generated = copy.deepcopy(graph); generated['name'] = package['name']; generated['packages']['']['name'] = package['name']
        write(dependencies / 'package-lock.json', generated); write(dependencies / 'package.json', package)
        with patch.dict(globals(), BROWSER_LOCK_GRAPH_SHA=graph_sha):
            case('browser-lock-permits-only-generated-root-name', lambda: require(browser_dependency_lock(dependencies)['generatedPackageName'] ==
                 package['name'], 'generated lock root projection lost'))
            wrong = copy.deepcopy(generated); wrong['packages']['']['devDependencies']['@playwright/test'] = '1.62.0'
            write(dependencies / 'package-lock.json', wrong)
            case('browser-lock-refuses-dependency-drift', lambda: refused(lambda: browser_dependency_lock(dependencies)))
            write(dependencies / 'package-lock.json', generated)
            wrong = copy.deepcopy(generated); wrong['packages']['']['name'] = 'foreign-name'; write(dependencies / 'package-lock.json', wrong)
            case('browser-lock-refuses-inconsistent-root-name', lambda: refused(lambda: browser_dependency_lock(dependencies)))
        selected = root / 'chromium-1243/chrome-linux64/chrome'; selected.parent.mkdir(parents=True); selected.write_bytes(b'inert executable fixture'); selected.chmod(0o700)
        native_digest = digest
        def dependency_digest(path):
            name = str(path)
            if name.endswith('node_modules/playwright-core/package.json'): return BROWSER_PACKAGE_SHA
            if name.endswith('node_modules/playwright-core/browsers.json'): return BROWSER_REGISTRY_SHA
            if name.endswith('node_modules/playwright-core/lib/coreBundle.js'): return BROWSER_CORE_SHA
            return native_digest(path)
        invocations = []
        def resolver(stdout=None, exit=0):
            def run(argv, **options):
                invocations.append(argv); require(options['timeout'] <= 10 and options['check'] is False, 'resolver budget/check drift')
                return SimpleNamespace(returncode=exit, stdout=json.dumps({'path': str(selected)}).encode() if stdout is None else stdout, stderr=b'')
            return run
        with patch.dict(globals(), browser_dependency_lock=lambda _: {'actualLockSha256': 'a'*64, 'dependencyGraphSha256': BROWSER_LOCK_GRAPH_SHA,
                         'generatedPackageName': 'inert-fixture'}, digest=dependency_digest):
            resolved = resolve_browser(root, 10, run=resolver(), clock=lambda: 0)
            case('browser-resolver-public-selected-path', lambda: require(resolved['path'] == str(selected) and len(invocations) == 1, 'resolver changed selected path'))
            case('browser-resolver-original-deadline', lambda: refused(lambda: resolve_browser(root, 0, run=resolver(), clock=lambda: 0)))
            for name, stdout, exit in [('nonzero', b'', 1), ('oversized', b'x'*4097, 0), ('malformed', b'{}', 0),
                                       ('headless', json.dumps({'path': str(root/'chromium-headless-shell-1243/chrome')}).encode(), 0),
                                       ('missing-installation', json.dumps({'path': str(root/'chromium-1243/chrome-linux64/absent')}).encode(), 0)]:
                case('browser-resolver-'+name, lambda stdout=stdout, exit=exit: refused(lambda: resolve_browser(root, 10, run=resolver(stdout, exit), clock=lambda: 0)))
            with patch.dict(globals(), digest=lambda _: '0'*64):
                case('browser-resolver-core-source-drift', lambda: refused(lambda: resolve_browser(root, 10, run=resolver(), clock=lambda: 0)))
        case('browser-selected-executable-positive', lambda: check_browser_executable(resolved))
        selected.write_bytes(b'changed fixture')
        case('browser-selected-executable-changed', lambda: refused(lambda: check_browser_executable(resolved)))
        selected.unlink(); selected.symlink_to(root/'absent')
        case('browser-selected-executable-symlink', lambda: refused(lambda: check_browser_executable(resolved)))
    case('browser-valid-endpoint', lambda: require(browser_endpoint_bytes(b'1234\n/devtools/browser/abc-123\n')['endpoint'] ==
         'ws://127.0.0.1:1234/devtools/browser/abc-123', 'endpoint drift'))
    for name, raw in [('empty', b''), ('partial', b'1234\n'), ('extra', b'1234\n/devtools/browser/a\nx'),
                      ('userinfo', b'1234\n/devtools/browser/a@host'), ('query', b'1234\n/devtools/browser/a?b'),
                      ('fragment', b'1234\n/devtools/browser/a#b'), ('foreign', b'1234\nhttp://foreign/'),
                      ('oversized', b'x'*4097), ('port-zero', b'0\n/devtools/browser/a'), ('port-large', b'65536\n/devtools/browser/a'),
                      ('binary', b'1234\n/devtools/browser/\xff')]:
        case('browser-endpoint-'+name, lambda raw=raw: refused(lambda: browser_endpoint_bytes(raw)))
    def table(address='0100007F', port='04D2', inode='987'):
        return 'header\n 0: '+address+':'+port+' 00000000:0000 0A 0:0 0:0 0 1000 0 '+inode+'\n'
    case('browser-owned-loopback-socket', lambda: require(browser_listener_rows({'tcp': table(), 'tcp6': 'header'}, 1234, {'987'})['inode'] == '987', 'socket drift'))
    for name, tables, sockets in [('missing', {'tcp': 'header'}, {'987'}), ('foreign-pid', {'tcp': table()}, {'9'}),
                                  ('wildcard', {'tcp': table('00000000')}, {'987'}), ('foreign-address', {'tcp': table('0100000A')}, {'987'}),
                                  ('ambiguous', {'tcp': table()+table().split('\n', 1)[1]}, {'987'}),
                                  ('ipv6-only', {'tcp6': table('00000000000000000000000001000000')}, {'987'}),
                                  ('port-drift', {'tcp': table(port='04D3')}, {'987'})]:
        case('browser-socket-'+name, lambda tables=tables, sockets=sockets: refused(lambda: browser_listener_rows(tables, 1234, sockets)))
    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary)
        profile = root / 'profile'
        case('browser-fresh-private-profile', lambda: require(fresh_browser_profile(profile)['uid'] == os.getuid(), 'profile owner drift'))
        case('browser-used-profile', lambda: refused(lambda: fresh_browser_profile(profile)))
        case('browser-profile-wrong-uid', lambda: wrong_uid(profile))
        linked = root / 'linked'; linked.symlink_to(profile, target_is_directory=True)
        case('browser-linked-profile', lambda: refused(lambda: browser_profile_identity(linked)))
        profile.chmod(0o755)
        case('browser-open-profile-mode', lambda: refused(lambda: browser_profile_identity(profile)))
        profile.chmod(0o700)
        endpoint = profile / 'DevToolsActivePort'; endpoint.write_bytes(b'1234\n/devtools/browser/fixture\n')
        info = endpoint.stat(); bound = browser_fixture_endpoint(); bound['file'] = {'device': info.st_dev, 'inode': info.st_ino, 'bytes': info.st_size, 'sha256': digest(endpoint)}
        case('browser-original-endpoint-file', lambda: check_browser_endpoint(profile, bound))
        endpoint.write_bytes(b'1235\n/devtools/browser/fixture\n')
        case('browser-changed-endpoint-file', lambda: refused(lambda: check_browser_endpoint(profile, bound)))
        endpoint.unlink(); endpoint.symlink_to(root / 'missing')
        case('browser-symlink-endpoint-file', lambda: refused(lambda: check_browser_endpoint(profile, bound)))
    with tempfile.TemporaryDirectory() as temporary:
        directory = Path(temporary); activation = route_fixture(); route_fixture_evidence(directory, activation)
        runtime = json.loads((directory / 'owned-bus-runtime.json').read_text()); leaders = json.loads((directory / 'resource-leaders.json').read_text())
        receipt = {'browser': {'pid': 2, 'launcherPid': 2, 'companionPid': 60}}
        case('browser-direct-authority-binder', lambda: browser_evidence(directory, receipt, runtime, leaders))
        original = (directory / 'browser-launch.json').read_bytes()
        mutations = [('wrong-browser-birth', lambda v: v['browserBirth'].update(start=999)), ('detached-group', lambda v: v['browserBirth'].update(pgid=2)),
                     ('source-drift', lambda v: v.update(sourceSha256='0'*64)), ('dependency-drift', lambda v: v['executable'].update(lockSha256='0'*64)),
                     ('headless-selection', lambda v: v['executable'].update(revision='headless-shell')), ('argv-drift', lambda v: v['argv'].append('--remote-debugging-pipe')),
                     ('foreign-profile', lambda v: v['profile'].update(path='/foreign')), ('foreign-endpoint', lambda v: v['endpoint'].update(endpoint='ws://foreign/')),
                     ('wildcard-evidence', lambda v: v['endpoint']['listener'].update(address='00000000'))]
        for name, mutate in mutations:
            value = json.loads(original); mutate(value); write(directory / 'browser-launch.json', value)
            case('browser-binder-'+name, lambda: refused(lambda: browser_evidence(directory, receipt, runtime, leaders)))
        (directory / 'browser-launch.json').write_bytes(original)
        ready_original = (directory / 'browser-companion-ready.json').read_bytes()
        for name, mutate in [('stale-ready', lambda v: v.update(launchSha256='0'*64)), ('companion-pid-reuse', lambda v: v['companionBirth'].update(start=999)),
                             ('synthetic-focus', lambda v: v.update(noDefaults=False)), ('missing-context', lambda v: v.update(contexts=0)),
                             ('ambiguous-page', lambda v: v.update(initialPages=2)), ('unready-sample', lambda v: v.update(sampleSequence=0))]:
            value = json.loads(ready_original); mutate(value); write(directory / 'browser-companion-ready.json', value)
            case('browser-ready-'+name, lambda: refused(lambda: browser_evidence(directory, receipt, runtime, leaders)))
        (directory / 'browser-companion-ready.json').write_bytes(ready_original)
        bad = copy.deepcopy(receipt); bad['browser'].update(pid=60, launcherPid=60, companionPid=2)
        case('browser-swapped-node-authority', lambda: refused(lambda: browser_evidence(directory, bad, runtime, leaders)))
        browser = next(v for v in leaders if v['resource'] == 'browser')
        case('browser-window-original-leader', lambda: browser_window_identity(2, browser, lambda _: browser))
        case('browser-window-node-swap', lambda: refused(lambda: browser_window_identity(60, browser, lambda _: browser)))
        case('browser-window-reused-pid', lambda: refused(lambda: browser_window_identity(2, browser, lambda _: {**browser, 'start': 99})))
        class Dead:
            pid = 60
            def poll(self): return 1
        failure = {'birth': copy.deepcopy(next(v for v in leaders if v['resource'] == 'browser-companion')), 'firstCause': 'specific original CDP failure'}
        write(directory / 'browser-companion-failure.json', failure)
        case('browser-companion-first-cause', lambda: refused(lambda: required_children([Dead()], directory), 'specific original CDP failure'))
        failure['birth']['start'] = 99; write(directory / 'browser-companion-failure.json', failure)
        case('browser-companion-stale-failure', lambda: refused(lambda: required_children([Dead()], directory), 'identity'))
        failure_path = directory / 'browser-companion-failure.json'
        failure_path.unlink()
        companion = next(v for v in leaders if v['resource'] == 'browser-companion')
        launch = completion_record(directory / 'browser-launch.json')
        marker = (directory / 'inner-result.json').read_bytes()
        parent = json.loads(marker)['parentBirth']
        successful_process = {'leader': {'pid': parent['sid'], 'start': 1, 'ppid': 1, 'sid': parent['sid'], 'pgid': parent['sid']},
            'exit': 0, 'firstCause': None, 'firstGuardCensus': None, 'termination': [], 'reportingErrors': [],
            'cleanup': {'disposition': 'observed-empty', 'remaining': [], 'unknown': []}}
        write(directory / 'process-result.json', successful_process)
        valid_event = {'schema': BROWSER_SCHEMA, 'birth': companion, 'firstCause': 'CDP transport closed before completion',
            'kind': 'transport-close', 'launchSha256': digest(directory / 'browser-launch.json'),
            'innerResultSha256AtFailure': digest(directory / 'inner-result.json')}
        write(failure_path, valid_event)
        (directory / 'browser-companion.log').write_text('BROWSER_COMPANION_FIRST_CAUSE '+valid_event['firstCause']+'\n')
        case('browser-post-observation-bound-transport-close', lambda: require(browser_transport_outcome(directory, launch, companion)['stage'] ==
             'post-observation-transport-outcome', 'post-observation stage mislabeled'))
        log_path = directory / 'browser-companion.log'
        valid_log = log_path.read_bytes()
        failure_path.unlink()
        case('browser-log-full-authority-missing-json-refuses', lambda: refused(lambda: browser_evidence(directory, receipt, runtime, leaders), valid_event['firstCause']))
        case('browser-log-missing-json-first-cause-refuses', lambda: refused(lambda: browser_transport_outcome(directory, launch, companion), valid_event['firstCause']))
        case('browser-log-active-missing-json-first-cause-refuses', lambda: refused(lambda: browser_active_failure(directory, companion), valid_event['firstCause']))
        log_path.write_text('BROWSER_COMPANION_REPORT_FAILURE original atomic write refused\n')
        case('browser-log-missing-json-report-failure-refuses', lambda: refused(lambda: browser_transport_outcome(directory, launch, companion), 'original cause unknown'))
        case('browser-log-active-report-failure-refuses', lambda: refused(lambda: browser_active_failure(directory, companion), 'original cause unknown'))
        log_path.write_text('')
        case('browser-log-no-json-clean-original-log', lambda: require(browser_transport_outcome(directory, launch, companion) ==
             {'reported': False, 'stage': 'not-observed'}, 'clean log fabricated transport outcome'))
        log_path.unlink()
        case('browser-log-no-json-missing-log-refuses', lambda: refused(lambda: browser_transport_outcome(directory, launch, companion)))
        write(failure_path, valid_event)
        case('browser-log-missing-refuses', lambda: refused(lambda: browser_transport_outcome(directory, launch, companion)))
        log_path.write_bytes(b'\xff')
        case('browser-log-invalid-encoding-refuses', lambda: refused(lambda: browser_transport_outcome(directory, launch, companion), 'unreadable'))
        log_path.write_bytes(b'x' * (4 * 1024**2 + 1))
        case('browser-log-oversized-refuses', lambda: refused(lambda: browser_transport_outcome(directory, launch, companion), 'oversized'))
        log_path.unlink(); log_path.mkdir()
        case('browser-log-nonregular-refuses', lambda: refused(lambda: browser_transport_outcome(directory, launch, companion), 'nonregular'))
        log_path.rmdir(); os.mkfifo(log_path, mode=0o600)
        case('browser-log-fifo-refuses-without-blocking', lambda: refused(lambda: browser_transport_outcome(directory, launch, companion), 'nonregular'))
        log_path.unlink()
        def closed_on_type_refusal():
            closed = []
            with patch.object(os, 'open', return_value=1234), patch.object(os, 'fstat', return_value=SimpleNamespace(st_mode=stat.S_IFDIR, st_size=0)), \
                    patch.object(os, 'close', side_effect=closed.append):
                refused(lambda: browser_companion_log(directory), 'nonregular')
            require(closed == [1234], 'original log descriptor leaked on type refusal')
        case('browser-log-original-fd-closed-on-refusal', closed_on_type_refusal)
        target = directory / 'foreign-companion-log'; target.write_bytes(valid_log); log_path.symlink_to(target)
        case('browser-log-symlink-refuses', lambda: refused(lambda: browser_transport_outcome(directory, launch, companion)))
        log_path.unlink(); log_path.write_bytes(valid_log)
        def unreadable_log():
            with patch.object(os, 'open', side_effect=PermissionError('original log permission denied')):
                refused(lambda: browser_transport_outcome(directory, launch, companion), 'permission denied')
        case('browser-log-read-error-refuses', unreadable_log)
        log_path.write_text('BROWSER_COMPANION_FIRST_CAUSE distinct original failure\n')
        case('browser-log-json-cause-mismatch-refuses', lambda: refused(lambda: browser_transport_outcome(directory, launch, companion), valid_event['firstCause']))
        log_path.write_bytes(valid_log+b'BROWSER_COMPANION_REPORT_FAILURE original atomic write refused\n')
        case('browser-log-json-report-failure-refuses', lambda: refused(lambda: browser_transport_outcome(directory, launch, companion), valid_event['firstCause']))
        log_path.write_bytes(valid_log+b'BROWSER_COMPANION_FIRST_CAUSE distinct later failure\n')
        case('browser-log-distinct-cause-contradiction-refuses', lambda: refused(lambda: browser_transport_outcome(directory, launch, companion), valid_event['firstCause']))
        log_path.write_bytes(valid_log+valid_log)
        case('browser-log-repeated-exact-first-cause-retained', lambda: require(browser_transport_outcome(directory, launch, companion)['firstCause'] ==
             valid_event['firstCause'], 'exact duplicate cause changed original'))
        log_path.write_bytes(valid_log)
        bound_receipt = copy.deepcopy(receipt); bound_receipt['browser']['transportOutcome'] = browser_transport_outcome(directory, launch, companion)
        case('browser-log-full-authority-valid-post-observation', lambda: browser_evidence(directory, bound_receipt, runtime, leaders))
        case('browser-log-valid-post-observation-bound', lambda: require(browser_transport_outcome(directory, launch, companion)['stage'] ==
             'post-observation-transport-outcome', 'valid post-observation log lost stage'))
        case('browser-post-observation-active-health-still-refuses', lambda: refused(lambda: browser_active_failure(directory, companion), 'CDP transport closed'))
        for name, mutate in [('absent-event-marker', lambda v: v.update(innerResultSha256AtFailure=None)),
                             ('stale-event-marker', lambda v: v.update(innerResultSha256AtFailure='0'*64)),
                             ('wrong-event-child', lambda v: v['birth'].update(start=999)),
                             ('wrong-event-group', lambda v: v['birth'].update(pgid=999)),
                             ('wrong-event-launch', lambda v: v.update(launchSha256='0'*64)),
                             ('active-protocol-failure', lambda v: v.update(kind='active-failure'))]:
            value = copy.deepcopy(valid_event); mutate(value); write(failure_path, value)
            case('browser-post-observation-'+name, lambda: refused(lambda: browser_transport_outcome(directory, launch, companion)))
        write(failure_path, valid_event)
        for name, mutate in [('wrapper-nonzero', lambda v: v.update(exit=1)), ('earlier-first-cause', lambda v: v.update(firstCause='earlier original failure')),
                             ('earlier-custody', lambda v: v.update(firstGuardCensus={'escaped': [1]})),
                             ('wrong-wrapper-session', lambda v: v['leader'].update(sid=999)),
                             ('cancellation', lambda v: v.update(termination=['SIGTERM'])),
                             ('reporting-failure', lambda v: v.update(reportingErrors=['write failed'])),
                             ('cleanup-unknown', lambda v: v['cleanup'].update(disposition='unknown', unknown=[1])),
                             ('cleanup-survivor', lambda v: v['cleanup'].update(remaining=[1]))]:
            value = copy.deepcopy(successful_process); mutate(value); write(directory / 'process-result.json', value)
            case('browser-post-observation-'+name, lambda: refused(lambda: browser_transport_outcome(directory, launch, companion)))
        write(directory / 'process-result.json', successful_process)
        (directory / 'inner-result.json').unlink()
        case('browser-post-observation-no-inner-success', lambda: refused(lambda: browser_transport_outcome(directory, launch, companion)))
        (directory / 'inner-result.json').write_bytes(marker)
        for name, mutate in [('premature-inner-failure', lambda v: v.update(exit=1)), ('wrong-original-parent', lambda v: v['parentBirth'].update(start=999)),
                             ('wrong-completion', lambda v: v.update(completionSha256='0'*64)), ('wrong-journey', lambda v: v.update(journeySha256='0'*64))]:
            value = json.loads(marker); mutate(value); write(directory / 'inner-result.json', value)
            rebound = {**valid_event, 'innerResultSha256AtFailure': digest(directory / 'inner-result.json')}; write(failure_path, rebound)
            case('browser-post-observation-'+name, lambda: refused(lambda: browser_transport_outcome(directory, launch, companion)))
        (directory / 'inner-result.json').write_bytes(marker); write(failure_path, valid_event)
        case('browser-post-observation-repeat-first-cause-unchanged', lambda: require(browser_transport_outcome(directory, launch, companion)['firstCause'] ==
             valid_event['firstCause'], 'post-observation erased original first cause'))
    def expired_endpoint():
        ticks = iter([0, 1]);
        refused(lambda: wait_browser_endpoint(None, {}, Path('/unused'), {}, {}, 0, lambda: None, clock=lambda: next(ticks)), 'deadline')
    case('browser-original-endpoint-deadline', expired_endpoint)
    case('browser-headed-literal-argv', lambda: require('--remote-debugging-port=0' in browser_argv('/selected/chrome', Path('/private/profile')) and
         '--remote-debugging-pipe' not in browser_argv('/selected/chrome', Path('/private/profile')) and
         not any('--headless' in v for v in BROWSER_FLAGS), 'foreground headed argv drift'))
    workflow = (ROOT / '.github/workflows/fable-external-reference-source.yml').read_text()
    case('browser-workflow-actual-node-controls-retained', lambda: workflow_guard(workflow))
    marker = 'external-reference-orca.py --browser-self-test'
    for name, value in [('missing-node-controls', workflow.replace(marker, 'external-reference-orca.py --absent-controls')),
                        ('duplicate-node-controls', workflow+'\n'+marker),
                        ('node-controls-before-version', workflow.replace('test "$(node --version)" = v26.10.0', 'removed-version-check')+'\ntest "$(node --version)" = v26.10.0')]:
        case('browser-workflow-'+name, lambda value=value: refused(lambda: workflow_guard(value)))
    print('PASS owned browser Python controls: '+str(len(checked))+' named cases; no browser, Node or network launched')
    return checked


def wrong_uid(profile):
    from unittest.mock import patch
    with patch.object(os, 'getuid', return_value=profile.stat().st_uid+1):
        try:
            browser_profile_identity(profile)
        except RuntimeError:
            return
        raise RuntimeError('foreign profile owner accepted')


def browser_js_self_test():
    # Separate explicit inert mode; no Playwright/browser/service import or network creation.
    with tempfile.TemporaryDirectory() as temporary:
        source = Path(temporary) / 'browser.cjs'
        source.write_text(BROWSER)
        result = subprocess.run(['node', str(source), '--self-test'], check=True, stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE, timeout=10)
        require(len(result.stdout) <= 1024*1024 and len(result.stderr) <= 1024*1024, 'inert JS output exceeded')
        packet = json.loads(result.stdout)
        require(packet['schema'] == 'fsgg.at-browser-adapter-controls/1' and packet['count'] == len(packet['names']) and
                len(set(packet['names'])) == packet['count'] and packet['network'] == packet['browserLaunches'] == 0,
                'actual inert JS control receipt malformed')
        print(json.dumps(packet))
        return packet['names']


def route_self_test():
    # Finite inert fixtures exercise the actual serializer and receipt/metadata gates, not AT runtime.
    good = route_fixture()
    selected = route_metadata(good)
    require(len(selected) == 5 and good["disposition"] == "incomplete", "vendor delegation reclassified")
    socket = "/tmp/fsgg-at-fixture/accessibility.sock"
    raw = closed_bus_config(socket, 1000)
    check_closed_config(raw, socket, 1000)
    for bad in [raw.replace(b"<auth>EXTERNAL</auth>", b"<auth>ANONYMOUS</auth>"),
                *[raw.replace(b"</busconfig>", directive+b"</busconfig>") for directive in
                  [b"<standard_session_servicedirs/>", b"<standard_system_servicedirs/>",
                   b"<servicedir>/unowned</servicedir>", b"<include>/etc/dbus-1/session.conf</include>",
                   b"<includedir>/etc/dbus-1/session.d</includedir>", b"<servicehelper>/unowned</servicehelper>"]],
                b'<!DOCTYPE busconfig [<!ENTITY leak SYSTEM "file:///unowned">]>'+raw]:
        try:
            check_closed_config(bad, socket, 1000)
        except RuntimeError:
            pass
        else:
            raise RuntimeError("open/activation/entity config accepted")
    mutations = [lambda p: p["sourceProof"].update(dbusSource="wrong"),
                 lambda p: p["versions"].update({"libatspi2.0-0t64": "wrong"}),
                 lambda p: p["binaries"].pop(), lambda p: p["binaries"][0].update(sha256="wrong"),
                 lambda p: p["packageFileManifest"].pop(ROUTE_PATHS[0]),
                 lambda p: p["errors"].append("missing independent activation file")]
    for mutate in mutations:
        bad = copy.deepcopy(good)
        mutate(bad)
        try:
            route_metadata(bad)
        except RuntimeError:
            pass
        else:
            raise RuntimeError("unqualified route metadata accepted")
    identity = {"pid": 1, "start": 2, "ppid": 3, "sid": 4}
    require_birth(identity, 3, 4)
    require(not same_birth({**identity, "start": 5}, identity), "stale birth accepted")
    for parent, sid in [(9, 4), (3, 9)]:
        try:
            require_birth(identity, parent, sid)
        except RuntimeError:
            pass
        else:
            raise RuntimeError("wrong parent/session accepted")
    require_registry_owner(1, identity)
    try:
        require_registry_owner(99, identity)
    except RuntimeError:
        pass
    else:
        raise RuntimeError("preexisting wrong registry owner accepted")
    from unittest.mock import patch
    class Bus:
        pid = 1
        def __init__(self, exit=None):
            self.exit = exit
        def poll(self):
            return self.exit
    address = ("unix:path="+socket+",guid="+"a"*32+"\n").encode()
    with patch.object(select, "select", return_value=([9], [], [])), patch.object(os, "read", return_value=address), \
            patch.dict(globals(), bus_listener=lambda pid, path: pid == 1 and path == socket):
        require(read_bus_address(Bus(), 9, socket, lambda: 0, lambda _: None) == address[:-1].decode(),
                "owned original bus address refused")
        for data in [address.replace(b"accessibility.sock", b"session.sock"), b"x"*513, address+address, b""]:
            with patch.object(os, "read", return_value=data):
                try:
                    read_bus_address(Bus(), 9, socket, lambda: 0, lambda _: None)
                except RuntimeError:
                    pass
                else:
                    raise RuntimeError("wrong/oversized/ambiguous/closed address accepted")
        try:
            read_bus_address(Bus(7), 9, socket, lambda: 0, lambda _: None)
        except RuntimeError as ex:
            require("exited" in str(ex), "early bus exit first cause lost")
        else:
            raise RuntimeError("dead original bus accepted")
    ticks = iter([0, 16])
    try:
        read_bus_address(Bus(), 9, socket, lambda: next(ticks), lambda _: None)
    except RuntimeError as ex:
        require("deadline" in str(ex), "original bus deadline first cause lost")
    else:
        raise RuntimeError("expired original bus accepted")
    argv = session_argv(Path("/private/output"), Path("/private/receiver"))
    require(argv[:4] == ["/usr/bin/dbus-run-session", "--dbus-daemon=/usr/bin/dbus-daemon",
            "--config-file=/private/output/session.conf", "--"], "session closed argv drift")
    with tempfile.TemporaryDirectory() as temporary:
        directory = Path(temporary)
        route_fixture_evidence(directory, good)
        require(route_evidence(directory, good, {"browser": {"pid": 2, "launcherPid": 2, "companionPid": 60}}), "good owned route fixture refused")
        actual = (directory / "owned-bus-runtime.json").read_bytes()
        for change in [lambda p: p.update(addressSetBeforeAtspiImport=False),
                       lambda p: p["registry"].update(pid=99),
                       lambda p: p.update(address="unix:path=/unowned,guid="+"a"*32),
                       lambda p: p["bus"].update(start=999),
                       lambda p: p["mappedLibraries"]["browser"]["object"].update(sha256="wrong"),
                       lambda p: p["mappedLibraries"]["browser"]["birth"].update(pid=99),
                       lambda p: p["mappedLibraries"]["browser"]["ancestry"][-1].update(start=99)]:
            value = json.loads(actual)
            change(value)
            write(directory / "owned-bus-runtime.json", value)
            try:
                route_evidence(directory, good, {"browser": {"pid": 2, "launcherPid": 2, "companionPid": 60}})
            except RuntimeError:
                pass
            else:
                raise RuntimeError("unbound runtime route accepted")
        (directory / "owned-bus-runtime.json").write_bytes(actual)
    source = Path(__file__).read_text()
    inner_source = source.split("def inner(", 1)[1].split("def observe(", 1)[0]
    require(inner_source.index('os.environ["AT_SPI_BUS_ADDRESS"] = address') < inner_source.index("native_gio()") <
            inner_source.index('registry = launch'), "cached AT client imported before owned address")
    require(inner_source.index("wait_display_ready(xvfb, absolute_deadline=session_deadline)") < inner_source.index('registry = launch') <
            inner_source.index('orca = launch'), "registry constructed before owned ready X display")
    require('"--use-gnome-session"' not in inner_source and 'launch(["/usr/libexec/at-spi2-registryd"]' in inner_source,
            "unowned GNOME activation/registry argv drift")
    rows = {2: {"pid": 2, "start": 10, "ppid": 60, "sid": 42}, 60: {"pid": 60, "start": 9, "ppid": 42, "sid": 42}}
    require(descendant_birth(rows[2], rows[60], rows.get) == [rows[2], rows[60]], "registered ancestry refused")
    for read in [lambda pid: None, lambda pid: {**rows[60], "start": 999} if pid == 60 else rows.get(pid)]:
        try:
            descendant_birth(rows[2], rows[60], read)
        except RuntimeError:
            pass
        else:
            raise RuntimeError("missing/stale registered ancestry accepted")
    wait_display_ready(Bus(), lambda *_: True, lambda _: True, lambda: 0, lambda _: None)
    for bus, listener in [(Bus(7), lambda *_: True), (Bus(), lambda *_: False)]:
        ticks = [0]
        def clock():
            ticks[0] += 1
            return ticks[0]
        try:
            wait_display_ready(bus, listener, lambda _: True, clock, lambda _: None)
        except RuntimeError:
            pass
        else:
            raise RuntimeError("dead/unready X display accepted")
    print("PASS inert explicit-owned route controls; no daemon/registry/AT/browser launched")


def supervision_self_test():
    # Mocked signal registration exercises cancellation without signalling or launching a process.
    from unittest.mock import patch
    handlers = {}
    previous = {signal.SIGTERM: "term-old", signal.SIGINT: "int-old"}
    with patch.object(signal, "getsignal", side_effect=lambda sig: previous[sig]), patch.object(signal, "signal", side_effect=lambda sig, fn: handlers.update({sig: fn})):
        with capture_termination() as pending:
            handlers[signal.SIGTERM](signal.SIGTERM, None)
            handlers[signal.SIGINT](signal.SIGINT, None)
            require(pending == ["original observer termination: SIGTERM"], "termination first cause overwritten")
        require(handlers == previous, "previous signal handlers not restored")
    with tempfile.TemporaryDirectory() as temporary:
        directory = Path(temporary)
        pending = []
        class Child:
            pid = 42
            returncode = None
            def poll(self):
                return self.returncode
        child = Child()
        leader = {"pid": 42, "start": 1, "sid": 42, "rss": 100}
        def observed(*_):
            pending.append("original observer termination: SIGTERM")
            return [], [], []
        def cleaned(*_):
            child.returncode = -15
            return {"disposition": "observed-empty", "remaining": [], "unknown": [], "signals": []}
        with patch.object(subprocess, "Popen", return_value=child), patch.dict(globals(), check_launch_object=lambda *_: None, proc=lambda _: leader, census=observed), patch.object(time, "sleep"), patch.dict(globals(), cleanup=cleaned):
            try:
                execute_session(Path("unused-receiver"), directory, {}, pending)
            except RuntimeError as ex:
                require(str(ex) == "original observer termination: SIGTERM", "actual supervisor lost termination cause")
            else:
                raise RuntimeError("terminated supervisor accepted")
        result = json.loads((directory / "process-result.json").read_text())
        require(result["firstCause"] == pending[0] and result["cleanup"]["disposition"] == "observed-empty" and result["exit"] == -15,
                "actual supervisor skipped original cleanup/result")
    class Server:
        pid = 42
        def __init__(self, code=None):
            self.code = code
        def poll(self):
            return self.code
    tcp = "header\n0: 0100007F:13EC 00000000:0000 0A 0 0 0 0 0 123 0\n"
    require(listener_matches(tcp, {"123"}), "owned listener refused")
    for bad_tcp, sockets in [(tcp, {"999"}), (tcp.replace("13EC", "13ED"), {"123"}), (tcp.replace(" 0A ", " 01 "), {"123"})]:
        require(not listener_matches(bad_tcp, sockets), "unowned/wrong-port/nonlistening socket accepted")
    ticks = [0]
    probes = []
    def clock():
        return ticks[0]
    def pause(_):
        ticks[0] += 1
    def ready(pid):
        probes.append(pid)
        return len(probes) == 3
    wait_server_ready(Server(), ready, clock, pause)
    require(probes == [42, 42, 42], "startup observation changed original server")
    for child, predicate, message in [(Server(17), lambda _: (_ for _ in ()).throw(RuntimeError("unexpected probe")), "original server exited before readiness: 17"),
                                       (Server(), lambda _: False, "original owned server readiness deadline exceeded")]:
        ticks[0] = 0
        try:
            wait_server_ready(child, predicate, clock, pause)
        except RuntimeError as ex:
            require(message in str(ex), "readiness first cause lost")
        else:
            raise RuntimeError("failed/timeout original startup accepted")
    print("PASS supervision controls: original startup ready/dead/deadline; SIGTERM first cause, cleanup and handler restoration mocked; SIGKILL remains unobservable")


def diagnostic_self_test():
    from unittest.mock import patch
    leader = {"pid": 42, "start": 1, "sid": 42, "rss": 100}
    unknown_row = {"pid": 43, "start": 2, "ppid": 1, "pgid": 42, "sid": 42, "state": "S", "rss": 50}
    escaped_row = {**unknown_row, "pid": 44, "sid": 44}
    for unknown, escaped in [([unknown_row], []), ([], [escaped_row]), ([unknown_row], [escaped_row])]:
        for failure in [None, "snapshot", "hash", "cleanup", "result"]:
            fail_snapshot = failure == "snapshot"
            with tempfile.TemporaryDirectory() as temporary:
                directory = Path(temporary)
                class Child:
                    pid = 42
                    returncode = None
                    def poll(self):
                        return self.returncode
                child = Child()
                clean_calls = []
                def cleaned(*args):
                    clean_calls.append(args)
                    child.returncode = -15
                    if failure == "cleanup":
                        raise OSError("mock cleanup observation failure")
                    return {"disposition": "observed-empty", "remaining": [], "unknown": [], "signals": []}
                actual_write = write
                actual_digest = digest
                def hashed(path):
                    if failure == "hash" and Path(path).name == "first-guard-census.json":
                        raise OSError("mock snapshot hash-read failure")
                    return actual_digest(path)
                def recorded(path, value):
                    if failure == "result" and Path(path).name == "process-result.json":
                        raise OSError("mock process result write failure")
                    if fail_snapshot and Path(path).name == "first-guard-census.json":
                        raise OSError("mock snapshot write failure")
                    actual_write(path, value)
                with patch.object(subprocess, "Popen", return_value=child), patch.dict(globals(), check_launch_object=lambda *_: None, proc=lambda _: leader,
                        census=lambda *_: ([leader, *escaped], unknown, escaped), cleanup=cleaned, write=recorded, digest=hashed):
                    try:
                        execute_session(Path("unused"), directory, {}, [])
                    except RuntimeError as ex:
                        require(str(ex) == "AT custody uncertainty", "diagnostic first cause changed")
                    else:
                        raise RuntimeError("custody uncertainty accepted")
                result = json.loads((directory / "reporting-failure.json").read_text())["processResult"] if failure == "result" else json.loads((directory / "process-result.json").read_text())
                snapshot = result["firstGuardCensus"]
                require(len(clean_calls) == 1 and result["firstCause"] == "AT custody uncertainty", "diagnostic cleanup skipped")
                require(snapshot["rows"]["unknown"] == unknown and snapshot["rows"]["escaped"] == escaped,
                        "first rejected birth census changed")
                require(snapshot["branches"] == {"unknown": bool(unknown), "escaped": bool(escaped)} and
                        snapshot["knownStarts"] == {"42": 1}, "rejected branch/known birth lost")
                require(result["historicalCustody"] == "unresolved" and result["cleanup"]["disposition"] == ("unknown" if failure == "cleanup" else "observed-empty"),
                        "later cleanup changed historical uncertainty")
                require(bool(result["reportingErrors"]) == (failure in ["snapshot", "hash", "result"]), "snapshot reporting failure lost")
    with tempfile.TemporaryDirectory() as temporary:
        directory = Path(temporary)
        class GoodChild:
            pid = 42
            returncode = 0
            def poll(self):
                return self.returncode
        child = GoodChild()
        empty = {"disposition": "observed-empty", "remaining": [], "unknown": [], "signals": []}
        with patch.object(subprocess, "Popen", return_value=child), patch.dict(globals(), check_launch_object=lambda *_: None, proc=lambda _: leader,
                census=lambda *_: ([], [], []), cleanup=lambda *_: empty):
            code, result = execute_session(Path("unused"), directory, {}, [])
        require(code == 0 and result == empty and json.loads((directory / "process-result.json").read_text())["firstGuardCensus"] is None,
                "good owned terminal path refused")
    files = {
        "/usr/share/dbus-1/services/org.a11y.Bus.service": b"[D-BUS Service]\nName=org.a11y.Bus\nExec=/usr/libexec/at-spi-bus-launcher\n",
        "/usr/share/dbus-1/accessibility-services/org.a11y.atspi.Registry.service": b"[D-BUS Service]\nName=org.a11y.atspi.Registry\nExec=/usr/libexec/at-spi2-registryd\n",
        "/usr/libexec/at-spi-bus-launcher": b"bus fixture",
        "/usr/libexec/at-spi2-registryd": b"registry fixture",
        "/usr/bin/dbus-daemon": b"dbus fixture"}
    manifest = {path: "fixture-package" for path in files}
    def packet(data=files, paths=manifest, resolve=lambda p: p, clock=lambda: 0):
        return activation_packet(paths, {"fixture-package": "fixture-version"}, lambda path, _: data[path], resolve, clock)
    good = packet()
    require(good["disposition"] == "complete" and len(good["services"]) == 2 and len(good["binaries"]) == 3,
            "package-owned activation fixture refused")
    service = "/usr/share/dbus-1/services/org.a11y.Bus.service"
    controls = [lambda: packet(paths={k: v for k, v in manifest.items() if k != service}),
                lambda: packet(data={**files, service: files[service].replace(b"/usr/libexec/at-spi-bus-launcher", b"sh -c untrusted")}),
                lambda: packet(resolve=lambda p: "/unowned/escape"),
                lambda: packet(data={**files, service: b"x" * (256 * 1024 + 1)}),
                lambda: packet(data={**files, service: files[service] + b"SystemdService=unresolved.service\n"})]
    unit = "/usr/lib/systemd/user/a11y-fixture.service"
    delegated = packet(data={**files, service: files[service] + b"SystemdService=a11y-fixture.service\n", unit: b"[Service]\nExecStart=/usr/libexec/at-spi-bus-launcher\n"},
                       paths={**manifest, unit: "fixture-package"})
    require(delegated["disposition"] == "incomplete" and delegated["services"]["org.a11y.Bus"]["executableSha256"] and
            any(v["path"] == unit for v in delegated["textFiles"]) and len(delegated["binaries"]) == 3,
            "delegation suppressed independent activation provenance")
    duplicate = "/usr/share/dbus-1/services/duplicate.service"
    controls.append(lambda: packet(data={**files, duplicate: files[service]}, paths={**manifest, duplicate: "fixture-package"}))
    ticks = [0]
    def expired_clock():
        ticks[0] += 1
        return 0 if ticks[0] == 1 else 16
    controls.append(lambda: packet(clock=expired_clock))
    for control in controls:
        try:
            result = control()
            require(result["disposition"] == "incomplete", "incomplete activation provenance accepted")
        except (ValueError, StopIteration):
            pass
    print("PASS diagnostic controls: unknown/escaped/both first census, snapshot/hash-read/cleanup/result write failures, later empty remains historically unresolved; package activation good and seven refusals; no AT launched")


def contract_self_test():
    from unittest.mock import patch
    checked = []
    def case(name, action):
        action()
        checked.append(name)
    def refused(action, phrase=None):
        try:
            action()
        except (RuntimeError, KeyError, configparser.Error) as ex:
            require(phrase is None or phrase in str(ex), "contract refusal first cause lost")
        else:
            raise RuntimeError("invalid session contract accepted")
    def model(values=None, write_failure=False, readback_failure=False, health=lambda: None):
        store = dict({"IsEnabled": False, "ScreenReaderEnabled": False} if values is None else values)
        events = []
        def persist(name, value):
            if write_failure:
                return False
            if not readback_failure:
                store[name] = value
            return True
        value = SessionStatus("unix:path=/tmp/fsgg-at-fixture/accessibility.sock,guid="+"a"*32,
                              store.__getitem__, persist, lambda n, v: events.append((n, v)), health)
        return value, store, events
    def set_value(value, name, state):
        return value.dispatch("org.freedesktop.DBus.Properties", "Set", ("org.a11y.Status", name, state))
    def signatures():
        xml = ET.fromstring(CONTRACT_XML)
        bus, status = list(xml)
        require(bus.attrib == {"name": "org.a11y.Bus"} and bus[0].attrib["name"] == "GetAddress" and
                bus[0][0].attrib == {"type": "s", "name": "address", "direction": "out"} and
                [(p.attrib["name"], p.attrib["type"], p.attrib["access"]) for p in status] ==
                [("IsEnabled", "b", "readwrite"), ("ScreenReaderEnabled", "b", "readwrite")],
                "authenticated interface signatures drift")
    case("native-signatures", signatures)
    value, store, events = model()
    case("GetAddress-original", lambda: require(value.dispatch("org.a11y.Bus", "GetAddress", ()) == value.address, "address drift"))
    case("Get-boolean", lambda: require(value.dispatch("org.freedesktop.DBus.Properties", "Get", ("org.a11y.Status", "IsEnabled")) is False, "Get drift"))
    case("GetAll-independent", lambda: require(value.dispatch("org.freedesktop.DBus.Properties", "GetAll", ("org.a11y.Status",)) == store, "GetAll drift"))
    case("Set-actual-persistence", lambda: set_value(value, "IsEnabled", True))
    def transition():
        value, store, events = model()
        set_value(value, "ScreenReaderEnabled", True)
        require(store == {"IsEnabled": True, "ScreenReaderEnabled": True} and
                events == [("IsEnabled", True), ("ScreenReaderEnabled", True)], "enabling transition/notification drift")
    case("screen-reader-enabling-transition", transition)
    def repeated_true():
        value, store, events = model({"IsEnabled": True, "ScreenReaderEnabled": True})
        set_value(value, "IsEnabled", False)
        set_value(value, "ScreenReaderEnabled", True)
        require(store == {"IsEnabled": False, "ScreenReaderEnabled": True} and events == [("IsEnabled", False)],
                "same-value screen-reader update incorrectly re-enabled accessibility")
    case("same-true-no-permanent-implication", repeated_true)
    def disabling():
        value, store, events = model({"IsEnabled": True, "ScreenReaderEnabled": True})
        set_value(value, "ScreenReaderEnabled", False)
        require(store == {"IsEnabled": True, "ScreenReaderEnabled": False}, "screen-reader disable cleared accessibility")
    case("screen-reader-disable-retains-accessibility", disabling)
    case("initial-values-independent", lambda: require(model({"IsEnabled": False, "ScreenReaderEnabled": True})[0].values ==
         {"IsEnabled": False, "ScreenReaderEnabled": True}, "initial state normalized"))
    case("same-value-no-notification", lambda: require(set_value(value, "IsEnabled", True) is None and events == [("IsEnabled", True)], "same-value notified"))
    for name, action in [
        ("invalid-value-type", lambda: set_value(value, "IsEnabled", 1)),
        ("invalid-interface", lambda: value.dispatch("unknown", "GetAddress", ())),
        ("invalid-property", lambda: value.dispatch("org.freedesktop.DBus.Properties", "Get", ("org.a11y.Status", "Unknown"))),
        ("invalid-method", lambda: value.dispatch("org.a11y.Bus", "Unknown", ())),
        ("invalid-arity", lambda: value.dispatch("org.a11y.Bus", "GetAddress", ("extra",))),
        ("invalid-status-interface", lambda: value.dispatch("org.freedesktop.DBus.Properties", "GetAll", ("wrong",))),
        ("write-failure", lambda: set_value(model(write_failure=True)[0], "IsEnabled", True)),
        ("write-readback-failure", lambda: set_value(model(readback_failure=True)[0], "IsEnabled", True))]:
        case(name, lambda action=action: refused(action))
    def backend_divergence():
        value, store, _ = model()
        store["IsEnabled"] = True
        refused(value.truthful, "backend/cache")
    case("backend-cache-disagreement", backend_divergence)
    def external_change():
        value, store, events = model()
        store["IsEnabled"] = True
        value.external("IsEnabled")
        require(events == [("IsEnabled", True)] and value.values == store, "external setting change lost")
    case("external-settings-change", external_change)
    def external_screen():
        value, store, events = model()
        store["ScreenReaderEnabled"] = True
        value.external("ScreenReaderEnabled")
        require(events == [("IsEnabled", True), ("ScreenReaderEnabled", True)] and value.values == store,
                "external enabling transition drift")
        store["IsEnabled"] = False
        value.external("IsEnabled")
        require(value.values["ScreenReaderEnabled"] is True, "external accessibility disable normalized screen reader")
    case("external-screen-reader-transition", external_screen)
    case("GetAddress-original-health-failure", lambda: refused(lambda: model(health=lambda: require(False, "original bus disappeared"))[0].dispatch("org.a11y.Bus", "GetAddress", ()), "disappeared"))
    def registration(fail=False, cleanup_failure=False):
        ids, removed, reporting = [], [], []
        class FakeConnection:
            def register_object(self, path, interface, *callbacks):
                require(path == CONTRACT_PATH and len(callbacks) == 3, "registration object/callback drift")
                ids.append(interface)
                return 0 if fail and len(ids) == 2 else len(ids)
            def unregister_object(self, rid):
                removed.append(rid)
                if cleanup_failure:
                    raise OSError("partial cleanup report failure")
        if fail:
            refused(lambda: register_contract_objects(FakeConnection(), ["bus", "status"], None, None, None, reporting), "registration")
            require(removed == [1] and bool(reporting) == cleanup_failure, "partial registration cleanup/report lost")
        else:
            require(register_contract_objects(FakeConnection(), ["bus", "status"], None, None, None) == [1, 2], "registration drift")
    def connect_fixture(outcome):
        from types import SimpleNamespace
        callbacks, timers, cancelled, removed = [], [], [], []
        connection = object()
        class Loop:
            def run(self):
                if outcome == "deadline":
                    timers[0]()
                else:
                    callbacks[0](None, "pending", None)
            def quit(self):
                pass
        def finish(pending):
            require(pending == "pending", "async connect result identity changed")
            if outcome == "error":
                raise RuntimeError("original private connect failed")
            return connection
        def begin(address, flags, observer, cancellable, callback, data):
            require(address == "unix:path=/original" and flags == 3 and observer is None, "async private connect route drift")
            callbacks.append(callback)
        gio = SimpleNamespace(Cancellable=lambda: SimpleNamespace(cancel=lambda: cancelled.append(1)),
              DBusConnection=SimpleNamespace(new_for_address=begin, new_for_address_finish=finish),
              DBusConnectionFlags=SimpleNamespace(AUTHENTICATION_CLIENT=1, MESSAGE_BUS_CONNECTION=2))
        glib = SimpleNamespace(MainLoop=Loop, timeout_add=lambda timeout, fn: (timers.append(fn) or 1),
                               source_remove=lambda rid: removed.append(rid))
        action = lambda: bounded_bus_connection(gio, glib, "unix:path=/original", 15, lambda: 0)
        if outcome == "ready":
            require(action() is connection and removed == [1] and not cancelled, "async original connect failed")
        else:
            refused(action, "deadline" if outcome == "deadline" else "connect failed")
            require(cancelled == ([1] if outcome == "deadline" else []), "connection cancellation observation drift")
    def schema_fixture(present=True, key_present=True, signature="b"):
        from types import SimpleNamespace
        schema = SimpleNamespace(has_key=lambda _: key_present,
            get_key=lambda _: SimpleNamespace(get_value_type=lambda: SimpleNamespace(dup_string=lambda: signature))) if present else None
        if present and key_present and signature == "b":
            require_status_schema(schema, "toolkit-accessibility")
        else:
            refused(lambda: require_status_schema(schema, "toolkit-accessibility"), "schema/key")
    case("actual-boolean-settings-schema", schema_fixture)
    case("missing-settings-schema-refusal", lambda: schema_fixture(False))
    case("missing-settings-key-refusal", lambda: schema_fixture(True, False))
    case("wrong-settings-schema-type-refusal", lambda: schema_fixture(True, True, "s"))
    case("bounded-private-connection-ready", lambda: connect_fixture("ready"))
    case("bounded-private-connection-deadline", lambda: connect_fixture("deadline"))
    case("bounded-private-connection-first-failure", lambda: connect_fixture("error"))
    case("actual-registration-success", registration)
    case("partial-registration-failure-cleanup", lambda: registration(True))
    case("partial-registration-cleanup-report-first-cause", lambda: registration(True, True))
    def claim(code):
        calls = []
        with patch.dict(globals(), contract_call=lambda *args: (calls.append(args) or (code,))):
            if code == 1:
                claim_contract_name(None, 15)
            else:
                refused(lambda: claim_contract_name(None, 15), "conflict")
        require(calls[0][5] == ("(su)", ("org.a11y.Bus", 4)), "RequestName replacement/queue enabled")
    case("exclusive-name-claim", lambda: claim(1))
    for label, code in [("name-claim-queue-refusal", 2), ("name-claim-existing-owner-refusal", 3), ("name-claim-already-owner-refusal", 4)]:
        case(label, lambda code=code: claim(code))
    def name_health(closed, owner):
        class FakeConnection:
            def is_closed(self):
                return closed
            def get_unique_name(self):
                return ":1.2"
        with patch.dict(globals(), contract_call=lambda *_: (owner,)):
            if not closed and owner == ":1.2":
                contract_name_health(FakeConnection(), 15)
            else:
                refused(lambda: contract_name_health(FakeConnection(), 15), "closed" if closed else "name lost")
    case("original-name-live", lambda: name_health(False, ":1.2"))
    case("original-name-lost", lambda: name_health(False, ":1.9"))
    case("original-session-connection-closed", lambda: name_health(True, ":1.2"))
    with tempfile.TemporaryDirectory() as temporary:
        directory = Path(temporary)
        activation = route_fixture()
        route_fixture_evidence(directory, activation)
        runtime = json.loads((directory / "owned-bus-runtime.json").read_text())
        state = json.loads((directory / "owned-bus-route.json").read_text())
        leaders = json.loads((directory / "resource-leaders.json").read_text())
        contract = runtime["sessionContract"]
        birth = contract["birth"]
        rows = {v["pid"]: {**v, "state": "S"} for v in
                [runtime["bus"], runtime["sessionBus"], runtime["registry"]["birth"], birth]}
        class Child:
            pid = birth["pid"]
            def poll(self):
                return None
        child = Child()
        def query(*_):
            return contract["uniqueOwner"], child.pid, runtime["address"], dict(contract["initialValues"])
        def ready(query_fn=query, read=rows.get, listener=lambda *_: True, clock=lambda: 0, candidate=child):
            return contract_ready(None, candidate, birth, runtime, state, directory, 15, query_fn, read, listener, clock, lambda _: None)
        case("readiness-original-owner-settings", lambda: require(ready() == {k: v for k, v in contract.items() if k != "completion"}, "ready facts drift"))
        case("readiness-owner-conflict", lambda: refused(lambda: ready(lambda *_: (":1.9", 999, runtime["address"], contract["initialValues"])), "different"))
        case("readiness-child-PID-reuse", lambda: refused(lambda: ready(read=lambda p: {**rows[p], "start": 99} if p == child.pid else rows.get(p))))
        case("readiness-original-bus-dead", lambda: refused(lambda: ready(read=lambda p: None if p == runtime["bus"]["pid"] else rows.get(p)), "daemon birth"))
        case("readiness-original-registry-dead", lambda: refused(lambda: ready(read=lambda p: None if p == runtime["registry"]["pid"] else rows.get(p)), "registry"))
        case("readiness-unowned-socket", lambda: refused(lambda: ready(listener=lambda *_: False), "socket"))
        case("readiness-address-drift", lambda: refused(lambda: ready(lambda *_: (":1.2", child.pid, "unix:path=/other", contract["initialValues"])), "different original address"))
        case("readiness-bool-type-drift", lambda: refused(lambda: ready(lambda *_: (":1.2", child.pid, runtime["address"], {"IsEnabled": 1, "ScreenReaderEnabled": True})), "typed"))
        case("readiness-private-settings-disagreement", lambda: refused(lambda: ready(lambda *_: (":1.2", child.pid, runtime["address"], {"IsEnabled": False, "ScreenReaderEnabled": True})), "readback"))
        case("readiness-deadline", lambda: refused(lambda: ready(clock=lambda: 16), "deadline"))
        case("readiness-query-failure", lambda: refused(lambda: ready(lambda *_: (_ for _ in ()).throw(RuntimeError("query broke"))), "query failed"))
        def name_wait():
            ticks = [0]
            calls = []
            def clock():
                ticks[0] += 1
                return ticks[0]
            def delayed(*_):
                calls.append(1)
                if len(calls) == 1:
                    raise RuntimeError("NameHasNoOwner")
                return query()
            require(ready(delayed, clock=clock) == {k: v for k, v in contract.items() if k != "completion"} and len(calls) == 2, "bounded original startup wait failed")
        case("readiness-bounded-name-startup", name_wait)
        case("binder-complete-original", lambda: require(contract_evidence(directory, runtime, leaders), "valid contract evidence refused"))
        for label, mutate in [
            ("binder-source-drift", lambda d: d["sessionContract"].update(sourceSha256="0"*64)),
            ("binder-readiness-absent", lambda d: d["sessionContract"].update(readyBeforeOrca=False)),
            ("binder-child-birth-drift", lambda d: d["sessionContract"]["birth"].update(start=999)),
            ("binder-original-address-drift", lambda d: d["sessionContract"].update(address="other")),
            ("binder-status-type-drift", lambda d: d["sessionContract"]["initialValues"].update(IsEnabled=1)),
            ("binder-backend-drift", lambda d: d["sessionContract"]["settings"].update(backend="GMemorySettingsBackend")),
            ("binder-Gio-object-drift", lambda d: d["sessionContract"]["settings"]["gioObject"].update(sha256="0"*64)),
            ("binder-schema-drift", lambda d: d["sessionContract"]["settings"]["schemas"]["IsEnabled"].update(type="s"))]:
            def mutation(mutate=mutate):
                value = copy.deepcopy(runtime)
                mutate(value)
                refused(lambda: contract_evidence(directory, value, leaders))
            case(label, mutation)
        def startup_failure():
            write(directory / "session-contract-failure.json", {"birth": birth, "firstCause": "specific settings registration failure"})
            class Dead:
                pid = child.pid
                def poll(self):
                    return 3
            refused(lambda: required_children([Dead()], directory), "specific settings registration failure")
            refused(lambda: ready(candidate=Dead()), "specific settings registration failure")
            (directory / "session-contract-failure.json").unlink()
        case("exact-child-first-cause-before-generic", startup_failure)
        def failed_report():
            (directory / "session-contract.log").write_text("SESSION_CONTRACT_FIRST_CAUSE original settings failure\n")
            class Dead:
                def poll(self):
                    return 3
            refused(lambda: required_children([Dead()], directory), "original settings failure")
        case("failed-child-report-log-first-cause", failed_report)
    case("assembled-inner-readiness-before-work", lambda: contract_inner_self_test(False))
    case("assembled-inner-readiness-refuses-work", lambda: contract_inner_self_test(True))
    case("specific-inner-report-failure-cleanup", contract_reporting_self_test)
    checked.extend(completion_self_test())
    print("PASS session contract inert controls: "+str(len(checked))+" named cases; no GI/services/browser/AT launched")
    print("SESSION_CONTRACT_CONTROL_INVENTORY "+json.dumps(checked))
    return checked


def completion_self_test():
    """Finite controls exercise real finish/binder helpers with inert process/Gio adapters."""
    from unittest.mock import patch
    from types import SimpleNamespace
    checked = []
    def case(name, action):
        action()
        checked.append(name)
    def refused(action, phrase=None):
        try:
            action()
        except (RuntimeError, KeyError, ValueError, OSError) as ex:
            require(phrase is None or phrase in str(ex), "completion first cause lost: "+str(ex))
        else:
            raise RuntimeError("invalid session completion accepted")
    @contextlib.contextmanager
    def fixture():
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            activation = route_fixture()
            route_fixture_evidence(directory, activation, uid=12345, complete=False)
            runtime = json.loads((directory / "owned-bus-runtime.json").read_text())
            birth = runtime["sessionContract"]["birth"]
            parent = runtime["sessionContract"]["parentBirth"]
            rows = {birth["pid"]: birth, parent["pid"]: parent}
            write(directory / "journey.json", {"inertObservedJourney": True})
            yield directory, runtime, birth, parent, rows
    def child_adapter(directory, runtime, birth, parent, mode="ok", mutate=None):
        events = []
        class Child:
            pid = birth["pid"]
            def poll(self):
                if mode == "premature":
                    return 0
                if not (directory / FINISH_FILES[0]).exists():
                    return None
                if mode == "unknown":
                    return None
                if mode == "missing-ack":
                    return 0
                if not (directory / FINISH_FILES[1]).exists():
                    identity = completion_identity(directory, runtime, parent, birth, runtime["sessionContract"]["uniqueOwner"])
                    complete_contract_child(directory, identity, lambda: events.append("final-health"),
                                            lambda: events.append("drain"), clock=lambda: 0)
                    if mutate is not None:
                        value = completion_record(directory / FINISH_FILES[1]);mutate(value)
                        write(directory / FINISH_FILES[1], value)
                return 7 if mode == "nonzero" else 0
            def wait(self, timeout):
                require(timeout > 0, "completion used renewed/empty wait")
                events.append("reap")
                return self.poll()
        return Child(), events
    def successful():
        with fixture() as (directory, runtime, birth, parent, rows):
            child, events = child_adapter(directory, runtime, birth, parent)
            result = finish_contract(directory, runtime, child, birth, parent, lambda: None,
                                     clock=lambda: 0, pause=lambda _: None, reader=rows.get)
            runtime["sessionContract"]["completion"] = result
            require(events == ["final-health", "drain", "reap"] and completion_evidence(directory, runtime, runtime["sessionContract"]),
                    "original completion order/binder drift")
            # After proven completion/reap, originals may disappear; offline binding retains their identities.
            rows.clear()
            require(completion_evidence(directory, runtime, runtime["sessionContract"]), "normal wrapper closure became active failure")
    case("completion-original-finish-ack-reap-binder", successful)
    def runtime_default_finish():
        with fixture() as (directory, runtime, birth, parent, rows):
            child, _ = child_adapter(directory, runtime, birth, parent)
            with patch.object(time, "monotonic", return_value=0), patch.object(time, "sleep") as sleeper:
                result = finish_contract(directory, runtime, child, birth, parent, lambda: None, reader=rows.get)
            require(result["identity"]["deadline"] == 300 and sleeper.call_count == 0,
                    "finish retained definition-time host clock/pause")
    case("completion-runtime-default-finish-clock", runtime_default_finish)
    def runtime_default_child():
        with fixture() as (directory, runtime, birth, parent, rows):
            identity = completion_identity(directory, runtime, parent, birth, ":1.2")
            atomic_record_once(directory / FINISH_FILES[0], {"schema": FINISH_SCHEMA, "phase": "request", "identity": identity})
            with patch.object(time, "monotonic", return_value=0):
                complete_contract_child(directory, identity, lambda: None, lambda: None)
            require((directory / FINISH_FILES[1]).is_file(), "child retained definition-time host clock")
    case("completion-runtime-default-child-clock", runtime_default_child)
    case("completion-assembled-wrapper-cleanup-binder", lambda: contract_inner_self_test(False, 4242))
    case("completion-portable-non1000-UID", lambda: contract_inner_self_test(False, 67890))
    case("completion-genuine-wrong-UID-refusal", lambda: refused(lambda: check_closed_config(
         closed_bus_config("/tmp/fsgg-at-fixture/session.sock", 12345), "/tmp/fsgg-at-fixture/session.sock", 12346), "serializer"))
    for label, mode in [("completion-child-exit-before-request", "premature"),
                        ("completion-child-exit-before-ack", "missing-ack"),
                        ("completion-ack-followed-by-nonzero", "nonzero")]:
        def exit_case(mode=mode):
            with fixture() as (directory, runtime, birth, parent, rows):
                child, _ = child_adapter(directory, runtime, birth, parent, mode)
                refused(lambda: finish_contract(directory, runtime, child, birth, parent, lambda: None,
                         clock=lambda: 0, pause=lambda _: None, reader=rows.get))
                require(not (directory / FINISH_FILES[2]).exists(), "unproven child exit produced completion")
        case(label, exit_case)
    for label, mutate in [
        ("completion-ack-wrong-request", lambda d: d.update(requestSha256="0"*64)),
        ("completion-ack-wrong-birth", lambda d: d["identity"]["childBirth"].update(start=999)),
        ("completion-ack-wrong-parent", lambda d: d["identity"]["parentBirth"].update(start=999)),
        ("completion-ack-wrong-source", lambda d: d["identity"].update(observerSourceSha256="0"*64)),
        ("completion-ack-wrong-journey", lambda d: d["identity"].update(journeySha256="0"*64)),
        ("completion-ack-wrong-budget", lambda d: d["identity"].update(sessionBudgetSha256="0"*64)),
        ("completion-ack-extra-field", lambda d: d.update(unexpected=True)),
        ("completion-ack-partial", lambda d: d.pop("teardown")),
        ("completion-ack-earlier-cause", lambda d: d.update(firstCause="original failure"))]:
        def bad_ack(mutate=mutate):
            with fixture() as (directory, runtime, birth, parent, rows):
                child, _ = child_adapter(directory, runtime, birth, parent, mutate=mutate)
                refused(lambda: finish_contract(directory, runtime, child, birth, parent, lambda: None,
                         clock=lambda: 0, pause=lambda _: None, reader=rows.get))
                require(not (directory / FINISH_FILES[2]).exists(), "invalid ack produced completion")
        case(label, bad_ack)
    def malformed_ack(kind):
        with fixture() as (directory, runtime, birth, parent, rows):
            child, _ = child_adapter(directory, runtime, birth, parent)
            original_poll = child.poll
            def poll():
                code = original_poll()
                if code is not None:
                    (directory / FINISH_FILES[1]).write_text('{"phase":' if kind == "malformed" else '{"phase":"ack","phase":"ack"}')
                return code
            child.poll = poll
            refused(lambda: finish_contract(directory, runtime, child, birth, parent, lambda: None,
                     clock=lambda: 0, pause=lambda _: None, reader=rows.get))
            require(not (directory / FINISH_FILES[2]).exists(), "malformed/duplicate ack produced completion")
    for label, kind in [("completion-ack-malformed-JSON", "malformed"), ("completion-ack-duplicate-fields", "duplicate")]:
        case(label, lambda kind=kind: malformed_ack(kind))
    def retained_failure():
        with fixture() as (directory, runtime, birth, parent, rows):
            write(directory / "session-contract-failure.json", {"birth": birth, "firstCause": "original pre-completion failure"})
            before = (directory / "session-contract-failure.json").read_bytes()
            child, _ = child_adapter(directory, runtime, birth, parent)
            refused(lambda: finish_contract(directory, runtime, child, birth, parent, lambda: None,
                     clock=lambda: 0, pause=lambda _: None, reader=rows.get), "original pre-completion failure")
            require((directory / "session-contract-failure.json").read_bytes() == before and
                    not (directory / FINISH_FILES[0]).exists(), "finish cleared prior cause or issued request")
    case("completion-retains-prior-child-failure", retained_failure)
    def bad_request(kind):
        with fixture() as (directory, runtime, birth, parent, rows):
            identity = completion_identity(directory, runtime, parent, birth, ":1.2")
            request = {"schema": FINISH_SCHEMA, "phase": "request", "identity": identity}
            if kind == "missing":
                refused(lambda: complete_contract_child(directory, identity, lambda: None, lambda: None, clock=lambda: 0))
                return
            atomic_record_once(directory / FINISH_FILES[0], request)
            if kind == "malformed":
                (directory / FINISH_FILES[0]).write_text('{"schema":')
            elif kind == "duplicate":
                (directory / FINISH_FILES[0]).write_text('{"phase":"request","phase":"request"}')
            elif kind == "stale":
                value = copy.deepcopy(request);value["identity"]["childBirth"]["start"] += 1
                write(directory / FINISH_FILES[0], value)
            elif kind == "before-journey":
                (directory / "journey.json").unlink()
                refused(lambda: completion_identity(directory, runtime, parent, birth, ":1.2"))
                return
            refused(lambda: complete_contract_child(directory, identity, lambda: None, lambda: None, clock=lambda: 0))
            require(not (directory / FINISH_FILES[1]).exists(), "invalid request acknowledged")
    for label, kind in [("completion-request-missing", "missing"), ("completion-request-malformed", "malformed"),
                        ("completion-request-duplicate-fields", "duplicate"), ("completion-request-stale", "stale"),
                        ("completion-request-before-journey", "before-journey")]:
        case(label, lambda kind=kind: bad_request(kind))
    def duplicate_ack():
        with fixture() as (directory, runtime, birth, parent, rows):
            identity = completion_identity(directory, runtime, parent, birth, ":1.2")
            atomic_record_once(directory / FINISH_FILES[0], {"schema": FINISH_SCHEMA, "phase": "request", "identity": identity})
            complete_contract_child(directory, identity, lambda: None, lambda: None, clock=lambda: 0)
            refused(lambda: complete_contract_child(directory, identity, lambda: None, lambda: None, clock=lambda: 0), "duplicate")
    case("completion-duplicate-ack-refusal", duplicate_ack)
    def active_failure(cause, queued=False):
        with fixture() as (directory, runtime, birth, parent, rows):
            identity = completion_identity(directory, runtime, parent, birth, ":1.2")
            atomic_record_once(directory / FINISH_FILES[0], {"schema": FINISH_SCHEMA, "phase": "request", "identity": identity})
            first, events = [], []
            def health():
                if not queued:
                    raise RuntimeError(cause)
            def drain():
                events.append("drain")
                first.append(cause)
            refused(lambda: complete_contract_child(directory, identity, health, drain,
                    lambda: first[0] if first else None, clock=lambda: 0), cause)
            require(not (directory / FINISH_FILES[1]).exists() and (bool(events) == queued), "failure was cleared by finish")
    for label, cause in [("completion-active-bus-loss", "original bus loss"),
                          ("completion-active-name-loss", "original name loss"),
                          ("completion-active-registry-loss", "original registry loss")]:
        case(label, lambda cause=cause: active_failure(cause))
    case("completion-queued-failure-wins", lambda: active_failure("original queued failure", True))
    def deadline_or_cancel(cancel=False):
        with fixture() as (directory, runtime, birth, parent, rows):
            child, _ = child_adapter(directory, runtime, birth, parent, "unknown")
            ticks, calls = [0], [0]
            def clock():
                ticks[0] += 100
                return ticks[0]
            def health():
                calls[0] += 1
                if cancel and calls[0] >= 2:
                    raise RuntimeError("original completion cancellation")
            refused(lambda: finish_contract(directory, runtime, child, birth, parent, health,
                    clock=clock, pause=lambda _: None, reader=rows.get), "cancellation" if cancel else "deadline")
            require(not (directory / FINISH_FILES[2]).exists(), "deadline/cancellation produced completion")
        contract_reporting_self_test("RuntimeError: original completion cancellation" if cancel else "original completion deadline")
    case("completion-deadline-first-cause-cleanup", deadline_or_cancel)
    case("completion-cancellation-first-cause-cleanup", lambda: deadline_or_cancel(True))
    def evidence_failure():
        with fixture() as (directory, runtime, birth, parent, rows):
            identity = completion_identity(directory, runtime, parent, birth, ":1.2")
            atomic_record_once(directory / FINISH_FILES[0], {"schema": FINISH_SCHEMA, "phase": "request", "identity": identity})
            with patch.object(os, "link", side_effect=OSError("original completion evidence write failed")):
                refused(lambda: complete_contract_child(directory, identity, lambda: None, lambda: None, clock=lambda: 0), "evidence write")
            require(not (directory / FINISH_FILES[1]).exists(), "failed ack write accepted")
        contract_reporting_self_test("RuntimeError: original completion evidence write failed")
    case("completion-evidence-write-first-cause-cleanup", evidence_failure)
    def close_fixture(outcome, runtime_default=False):
        callbacks, timers, canceled = [], [], []
        class Loop:
            def run(self):
                (timers[0] if outcome == "deadline" else lambda: callbacks[0](None, "pending", None))()
            def quit(self): pass
        class Connection:
            def close(self, cancellable, callback, data): callbacks.append(callback)
            def close_finish(self, pending):
                require(pending == "pending", "close result identity changed")
                if outcome == "error": raise RuntimeError("original close failed")
                return outcome != "false"
        gio = SimpleNamespace(Cancellable=lambda: SimpleNamespace(cancel=lambda: canceled.append(True)))
        glib = SimpleNamespace(MainLoop=Loop, timeout_add=lambda timeout, fn: (timers.append(fn) or 1), source_remove=lambda _: True)
        def action():
            with patch.object(time, "monotonic", return_value=0):
                if runtime_default:
                    bounded_connection_close(Connection(), gio, glib, 300)
                else:
                    bounded_connection_close(Connection(), gio, glib, 300, clock=lambda: 0)
        if outcome == "ok": action()
        else: refused(action, "deadline" if outcome == "deadline" else "close")
        require(canceled == ([True] if outcome == "deadline" else []), "close cancellation evidence drift")
    for label, outcome in [("completion-bounded-local-close", "ok"), ("completion-close-error", "error"),
                            ("completion-close-incomplete", "false"), ("completion-close-timeout-unknown", "deadline")]:
        case(label, lambda outcome=outcome: close_fixture(outcome))
    case("completion-runtime-default-close-clock", lambda: close_fixture("ok", True))
    case("completion-own-clean-close-only", lambda: require(expected_local_close(True, False, None) and
         not expected_local_close(False, False, None) and not expected_local_close(True, True, None) and
         not expected_local_close(True, False, RuntimeError("remote failure")), "unexpected close suppressed"))
    def drain_fixture(outcome):
        calls = []
        class Connection:
            def unregister_object(self, rid):
                calls.append("unregister")
                if outcome == "unregister-error": raise RuntimeError("original unregister failed")
                return outcome != "unregister-false"
            def is_closed(self): return outcome == "closed"
        def release(*_):
            calls.append("release")
            if outcome == "release-error": raise RuntimeError("original release failed")
            return (2 if outcome == "release-false" else 1,)
        def close(*_):
            calls.append("close")
            if outcome == "close-error": raise RuntimeError("original close failed")
        with patch.dict(globals(), contract_call=release, bounded_connection_close=close):
            action = lambda: drain_contract(Connection(), [1, 2], 300, lambda: calls.append("own-close"), None, None)
            if outcome == "ok":
                action();require(calls == ["unregister", "unregister", "release", "own-close", "close"], "drain ordering drift")
            else: refused(action)
    for label, outcome in [("completion-drain-order", "ok"), ("completion-unregister-error", "unregister-error"),
        ("completion-unregister-false", "unregister-false"), ("completion-release-error", "release-error"),
        ("completion-release-not-owner", "release-false"), ("completion-remote-close-before-intent", "closed"),
        ("completion-drain-close-error", "close-error")]:
        case(label, lambda outcome=outcome: drain_fixture(outcome))
    def missing_terminal(which):
        with fixture() as (directory, runtime, birth, parent, rows):
            child, _ = child_adapter(directory, runtime, birth, parent)
            result = finish_contract(directory, runtime, child, birth, parent, lambda: None,
                       clock=lambda: 0, pause=lambda _: None, reader=rows.get)
            runtime["sessionContract"]["completion"] = result
            (directory / FINISH_FILES[which]).unlink()
            refused(lambda: completion_evidence(directory, runtime, runtime["sessionContract"]))
    for label, which in [("completion-request-alone-insufficient", 1), ("completion-ack-alone-insufficient", 2),
                         ("completion-missing-request-binder", 0)]:
        case(label, lambda which=which: missing_terminal(which))
    def invalid_terminal(mutate):
        with fixture() as (directory, runtime, birth, parent, rows):
            child, _ = child_adapter(directory, runtime, birth, parent)
            result = finish_contract(directory, runtime, child, birth, parent, lambda: None,
                       clock=lambda: 0, pause=lambda _: None, reader=rows.get)
            mutate(result)
            write(directory / FINISH_FILES[2], result)
            runtime["sessionContract"]["completion"] = result
            refused(lambda: completion_evidence(directory, runtime, runtime["sessionContract"]))
    for label, mutate in [("completion-binder-not-reaped", lambda d: d.update(reaped=False)),
                          ("completion-binder-nonzero-exit", lambda d: d.update(childExit=7)),
                          ("completion-binder-boolean-exit", lambda d: d.update(childExit=False)),
                          ("completion-binder-first-cause", lambda d: d.update(firstCause="retained failure")),
                          ("completion-binder-wrong-ack", lambda d: d.update(ackSha256="0"*64)),
                          ("completion-binder-stale-child", lambda d: d["identity"]["childBirth"].update(start=999))]:
        case(label, lambda mutate=mutate: invalid_terminal(mutate))
    print("PASS completion lifecycle inert controls: "+str(len(checked))+" named cases; native completion remains unobserved")
    return checked


def contract_inner_self_test(refuse_ready, fixture_uid=12345):
    """Actual assembled inner with inert adapters; no GI import, fork, fd, bus or workload."""
    from unittest.mock import patch
    from types import SimpleNamespace
    with tempfile.TemporaryDirectory() as temporary:
        directory = Path(temporary)
        activation = route_fixture()
        route_fixture_evidence(directory, activation, uid=fixture_uid, complete=False)
        write(directory / "session-budget.json", {"deadline": 300, "seconds": 300})
        browser_outputs = ['browser.cjs', 'browser-launch.json', 'browser-companion-ready.json',
                           'browser-companion.log', 'browser-dom.json', 'inner-result.json']
        # Offline route fixtures own these fabricated records; actual assembled inner must produce its own.
        for name in browser_outputs:
            (directory / name).unlink(missing_ok=True)
        require(all(not (directory / name).exists() for name in browser_outputs) and not (directory / 'profile').exists(),
                'assembled browser outputs/profile were precreated')
        launched, readiness, observed, browser_order = [], [], [], []
        original_ready = contract_ready
        (directory / "speech.sock").touch()
        children, rows = {}, {}
        parent, sid = 42, 42
        class Child:
            def __init__(self, name):
                self.pid = 100+len(launched)
                self.name = name
            def poll(self):
                if self.name == "browser-companion" and not (directory / "browser-companion-ready.json").exists():
                    launch = json.loads((directory / "browser-launch.json").read_text())
                    registered = json.loads((directory / "resource-leaders.json").read_text())
                    require(any(v['resource'] == 'browser-companion' and same_birth(v, rows[self.pid]) for v in registered),
                            'assembled companion ready preceded current birth registration')
                    browser_order.append('ready')
                    ready = browser_fixture_ready(launch, digest(directory / "browser-launch.json"), rows[self.pid])
                    write(directory / "browser-companion-ready.json", ready)
                if self.name == "session-contract" and (directory / FINISH_FILES[0]).exists():
                    if not (directory / FINISH_FILES[1]).exists():
                        latest = json.loads((directory / "owned-bus-runtime.json").read_text())
                        identity = completion_identity(directory, latest, rows[parent], rows[self.pid], ":1.2")
                        complete_contract_child(directory, identity, lambda: None, lambda: None, clock=lambda: 0)
                    return 0
                return None
            def wait(self, timeout):
                return self.poll()
        def spawn(argv, **kwargs):
            name = Path(kwargs["stdout"].name).stem
            launched.append(name)
            if name == 'browser':
                require((directory / 'profile').is_dir() and not list((directory / 'profile').iterdir()),
                        'assembled foreground browser started without fresh empty profile')
                browser_order.append('profile')
            if name == 'browser-companion':
                require((directory / 'browser-launch.json').exists() and (directory / 'profile/DevToolsActivePort').exists(),
                        'assembled companion started without original launch/endpoint records')
                browser_order.append('launch-record')
            if name in ['browser', 'browser-companion']:
                browser_order.append(name)
            child = Child(name)
            children[name] = child
            rows[child.pid] = {"pid": child.pid, "start": child.pid+1000, "ppid": parent, "sid": sid, "pgid": sid, "state": "S"}
            return child
        session = {"pid": 90, "start": 900, "ppid": 89, "sid": sid, "pgid": sid, "state": "S"}
        rows[90] = session
        rows[parent] = {"pid": parent, "start": 420, "ppid": 89, "sid": sid, "pgid": sid, "rss": 100}
        class Reply:
            def unpack(self):
                return (90,)
        class Connection:
            def call_sync(self, *args):
                return Reply()
        flags = SimpleNamespace(AUTHENTICATION_CLIENT=1, MESSAGE_BUS_CONNECTION=2)
        gio = SimpleNamespace(DBusConnection=SimpleNamespace(new_for_address_sync=lambda *_: Connection()),
                              DBusConnectionFlags=flags, DBusCallFlags=SimpleNamespace(NONE=0))
        glib = SimpleNamespace(Variant=lambda *_: None, VariantType=lambda *_: None)
        def registry(connection, child, birth, **kwargs):
            return {"name": "org.a11y.atspi.Registry", "uniqueOwner": ":1.1", "pid": child.pid, "birth": birth}
        def ready(connection, child, birth, runtime, state, root, deadline):
            readiness.append(tuple(launched))
            require("orca" not in launched and "server" not in launched and "browser" not in launched,
                    "dependent workload released before contract readiness")
            if refuse_ready:
                raise RuntimeError("specific original contract readiness failure")
            # Exercise the actual readiness/binder with exact fake original births and settings.
            current_leaders = json.loads((directory / "resource-leaders.json").read_text())
            contract = contract_fixture_evidence(directory, activation, runtime, current_leaders, parent_birth=rows[parent], complete=False)
            contract.update(pid=child.pid, birth=birth)
            snapshot = json.loads((directory / "session-contract-state.json").read_text())
            snapshot["birth"] = birth
            write(directory / "session-contract-state.json", snapshot)
            return original_ready(connection, child, birth, runtime, state, directory, deadline,
                query=lambda *_: (":1.2", child.pid, runtime["address"], {"IsEnabled": True, "ScreenReaderEnabled": True}),
                reader=rows.get, listener=lambda *_: True, clock=lambda: 0, pause=lambda _: None)
        def query(connection, deadline, health=lambda: None):
            health()
            return ":1.2", children["session-contract"].pid, os.environ["AT_SPI_BUS_ADDRESS"], {"IsEnabled": True, "ScreenReaderEnabled": True}
        original_close = os.close
        def close(fd):
            if fd not in [901, 902]:
                original_close(fd)
        def endpoint_ready(browser, birth, profile, identity, executable, deadline, health):
            health()
            require('browser' in launched and 'browser-companion' not in launched and profile.is_dir() and not list(profile.iterdir()),
                    'assembled endpoint preceded foreground browser or reused profile')
            endpoint_path = profile / 'DevToolsActivePort'
            endpoint_path.write_bytes(b'1234\n/devtools/browser/fixture\n')
            info = endpoint_path.stat()
            endpoint = browser_fixture_endpoint()
            endpoint['file'] = {'device': info.st_dev, 'inode': info.st_ino, 'bytes': info.st_size, 'sha256': digest(endpoint_path)}
            check_browser_endpoint(profile, endpoint)
            browser_order.append('endpoint')
            return endpoint
        original_exists = Path.exists
        def exists(path):
            return False if str(path) in ["/tmp/.X97-lock", "/tmp/.X11-unix/X97"] else original_exists(path)
        original_read = Path.read_text
        def read(path, *args, **kwargs):
            if str(path) == "/etc/speech-dispatcher/speechd.conf":
                return ""
            return original_read(path, *args, **kwargs)
        def observation(root, orca, browser, health):
            health()
            observed.append((orca, browser))
            browser_order.append('journey')
            write(directory / "journey.json", {"inertObservedJourney": True})
        with patch.dict(os.environ, {"DBUS_SESSION_BUS_ADDRESS": "unix:path=/tmp/fsgg-at-fixture/session.sock,guid="+"b"*32}, clear=True), \
             patch.object(subprocess, "Popen", side_effect=spawn), patch.object(subprocess, "run"), \
             patch.object(os, "pipe", return_value=(901, 902)), patch.object(os, "close", side_effect=close), \
             patch.object(os, "getuid", return_value=fixture_uid), patch.object(os, "getpid", return_value=parent), patch.object(os, "getppid", return_value=89), \
             patch.object(os, "getsid", return_value=sid), patch.object(time, "monotonic", return_value=0), \
             patch.object(time, "sleep"), patch.object(Path, "read_text", read), patch.object(Path, "exists", exists), patch.object(shutil, "copyfile"), \
             patch.dict(globals(), check_route_files=lambda p: route_metadata(p), check_launch_object=lambda *_: None,
                proc=rows.get, bus_listener=lambda *_: True, wait_display_ready=lambda *args, **kwargs: None,
                read_bus_address=lambda *args, **kwargs: "unix:path=/tmp/fsgg-at-fixture/accessibility.sock,guid="+"a"*32,
                registry_owner=registry, contract_ready=ready, contract_query=query, wait_server_ready=lambda *args, **kwargs: None,
                bounded_bus_connection=lambda *_: Connection(),
                browser_profile_identity=lambda profile: {"path": str(profile), "device": 1, "inode": 2, "uid": fixture_uid},
                resolve_browser=lambda *_args, **_kwargs: browser_fixture_executable(),
                check_node_tool=lambda *_: {"path": "/selected/node", "sha256": "a"*64}, check_browser_executable=lambda *_args, **_kwargs: None,
                browser_active=lambda *_args, **_kwargs: None,
                browser_listener=lambda *_: browser_fixture_endpoint()["listener"],
                wait_browser_endpoint=endpoint_ready,
                observe=observation):
            if refuse_ready:
                try:
                    inner(Path("/private/receiver"), directory, (gio, glib))
                except RuntimeError as ex:
                    require("specific original contract" in str(ex), "assembled readiness first cause lost")
                else:
                    raise RuntimeError("assembled unready service released workload")
            else:
                inner(Path("/private/receiver"), directory, (gio, glib))
                record_inner_success(directory)
                browser_order.append('completed-inner')
                launch = completion_record(directory / 'browser-launch.json')
                companion = rows[children['browser-companion'].pid]
                browser_ready_matches(completion_record(directory / 'browser-companion-ready.json'), launch,
                                      digest(directory / 'browser-launch.json'), companion)
                require(launch['browserBirth']['pid'] == children['browser'].pid and launch['browserBirth']['ppid'] == parent and
                        launch['profile']['path'] == str(directory / 'profile') and
                        digest(directory / 'browser.cjs') == launch['companionSourceSha256'] and
                        not (directory / 'browser-companion.log').read_bytes() and
                        completion_record(directory / 'inner-result.json')['completionSha256'] == digest(directory / FINISH_FILES[2]),
                        'assembled browser/completion artifacts retained stale fixture authority')
                check_browser_endpoint(directory / 'profile', launch['endpoint'])
                require(browser_order == ['profile', 'browser', 'endpoint', 'launch-record', 'browser-companion', 'ready', 'journey', 'completed-inner'],
                        'assembled original browser endpoint/launch/ready/journey/completion order drift')
        require(len(readiness) == 1 and readiness[0].index("accessibility-bus") < readiness[0].index("xvfb") <
                readiness[0].index("registry") < readiness[0].index("session-contract"), "assembled startup order drift")
        if refuse_ready:
            require(not observed and all(n not in launched for n in ["orca", "server", "browser", "browser-companion"]), "failed readiness launched dependent work")
            require(not browser_order and not (directory / 'profile').exists() and
                    all(not (directory / name).exists() for name in browser_outputs),
                    'failed original contract readiness left fabricated browser/completion evidence')
        else:
            require(len(observed) == 1 and launched.index("session-contract") < launched.index("orca") <
                    launched.index("server") < launched.index("browser"), "ready startup dependent order drift")
            class Wrapper:
                pid = 900
                returncode = 0
                def poll(self): return 0
            wrapper_birth = {"pid": 900, "start": 9000, "sid": 900, "ppid": parent, "rss": 100}
            cleaned = []
            def cleanup_wrapper(*_):
                cleaned.append(True)
                rows.pop(90, None)
                rows.pop(children["accessibility-bus"].pid, None)
                return {"disposition": "observed-empty", "remaining": [], "unknown": [], "signals": []}
            # Same fake absolute300 deadline; actual outer success/cleanup code runs with no native process.
            with patch.object(subprocess, "Popen", return_value=Wrapper()), patch.object(time, "monotonic", return_value=0), \
                 patch.object(os, "getpid", return_value=parent), \
                 patch.dict(globals(), check_launch_object=lambda *_: None, proc=lambda pid: wrapper_birth if pid == 900 else rows.get(pid),
                            census=lambda *_: ([], [], []), cleanup=cleanup_wrapper):
                require(execute_session(Path("/private/receiver"), directory, {}, [])[0] == 0 and cleaned == [True],
                        "assembled outer cleanup did not follow completed child")
            latest = json.loads((directory / "owned-bus-runtime.json").read_text())
            # Simulate wrapper bus closure only after exact child completion/reaping. The final binder is offline.
            require(90 not in rows and children["accessibility-bus"].pid not in rows, "wrapper originals did not close")
            require(contract_evidence(directory, latest, json.loads((directory / "resource-leaders.json").read_text())),
                    "normal wrapper shutdown invalidated completed contract")


def contract_reporting_self_test(cause="RuntimeError: original contract settings failure"):
    from unittest.mock import patch
    with tempfile.TemporaryDirectory() as temporary:
        directory = Path(temporary)
        class Child:
            pid = 42
            returncode = 1
            def poll(self):
                return self.returncode
        child = Child()
        leader = {"pid": 42, "start": 1, "sid": 42, "rss": 100}
        cleaned = []
        def spawn(*args, **kwargs):
            kwargs["stdout"].write(("INNER_FIRST_CAUSE "+cause+"\nINNER_REPORT_FAILURE OSError: refused\n").encode())
            kwargs["stdout"].flush()
            return child
        def cleanup_actual(*args):
            cleaned.append(1)
            return {"disposition": "observed-empty", "remaining": [], "unknown": [], "signals": []}
        actual_write = write
        def broken(path, data):
            if Path(path).name == "process-result.json":
                raise OSError("result write refused")
            return actual_write(path, data)
        with patch.object(subprocess, "Popen", side_effect=spawn), patch.dict(globals(), check_launch_object=lambda *_: None,
                proc=lambda *_: leader, census=lambda *_: ([], [], []), cleanup=cleanup_actual, write=broken):
            try:
                execute_session(Path("unused"), directory, {}, [])
            except RuntimeError as ex:
                require(str(ex) == cause, "specific original/reporting cause overwritten")
            else:
                raise RuntimeError("failed original service accepted")
        result = json.loads((directory / "reporting-failure.json").read_text())
        require(cleaned == [1] and result["firstCause"] == cause and result["processResult"]["firstCause"] == cause,
                "cleanup skipped or reporting replaced first cause")


def workflow_guard(workflow):
    require(workflow.count("external-reference-orca.py --browser-self-test") == 1 and
            workflow.index('test "$(node --version)" = v26.10.0') < workflow.index("external-reference-orca.py --browser-self-test") <
            workflow.index("Qualify exact generated"), "actual pinned Node adapter controls missing or misplaced")
    require(workflow.count("external-reference-orca.py --self-test") == 2, "static controls missing from PR/reusable path")
    for name in ["Provision external reference assistive technology", "Observe actual external reference Orca journey"]:
        section = workflow.split("      - name: " + name, 1)[1].split("\n      - ", 1)[0]
        require("if: ${{ !inputs.preflight-only }}" in section, "AT workload unguarded")
    require(workflow.index("external-reference-orca.py --self-test") < workflow.index("Verify native producer run"), "AT static controls after acquisition")
    require(workflow.index("Qualify exact generated") < workflow.index("Observe actual external reference") < workflow.index("Bind successful full"), "AT dependency ordering drift")
    require("external-reference/orca/**" in workflow, "AT original failure evidence omitted")
    capture = 'external-reference-orca.py --capture-activation "$RUNNER_TEMP/external-reference/orca-activation-provenance.json"'
    require(workflow.count(capture) == 1, "activation capture missing/ambiguous")
    provision = workflow.split("      - name: Provision external reference assistive technology", 1)[1].split("\n      - ", 1)[0]
    require(provision.index("apt-get install") < provision.index(capture), "activation readback before installed source")
    require("${{ runner.temp }}/external-reference/orca-activation-provenance.json" in workflow,
            "activation original failure evidence omitted")


def main():
    parser = argparse.ArgumentParser()
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument("--self-test", action="store_true")
    modes.add_argument("--browser-self-test", action="store_true")
    modes.add_argument("--inner", action="store_true")
    modes.add_argument("--owned-status", action="store_true")
    modes.add_argument("--capture-activation", action="store_true")
    parser.add_argument("first", nargs="?")
    parser.add_argument("second", nargs="?")
    args = parser.parse_args()
    if args.self_test:
        self_test()
    elif args.browser_self_test:
        browser_js_self_test()
    elif args.owned_status:
        require(args.first and not args.second, "private contract directory required")
        contract_child(Path(args.first))
    elif args.capture_activation:
        require(args.first, "activation output path required")
        capture_activation(Path(args.first))
    elif args.inner:
        directory = Path(args.second)
        try:
            inner(Path(args.first), directory)
            record_inner_success(directory)
        except BaseException as ex:
            first = type(ex).__name__ + ": " + str(ex)
            try:
                write(directory / "inner-result.json", {"firstCause": first, "exit": 1})
            except BaseException as report:
                print("INNER_FIRST_CAUSE "+first, file=sys.stderr, flush=True)
                print("INNER_REPORT_FAILURE "+type(report).__name__+": "+str(report), file=sys.stderr, flush=True)
            raise RuntimeError(first) from ex
    else:
        require(args.first and args.second, "candidate directory and authenticated preflight required")
        with capture_termination() as termination:
            qualify(Path(args.first).resolve(), Path(args.second).resolve(), termination)


if __name__ == "__main__":
    main()
