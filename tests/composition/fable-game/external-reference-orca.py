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


def wait_display_ready(child, listener=None, probe=None, clock=time.monotonic, pause=time.sleep):
    listener = bus_listener if listener is None else listener
    def query(seconds):
        return subprocess.run(["xdpyinfo", "-display", ":97"], stdout=subprocess.DEVNULL,
                              stderr=subprocess.DEVNULL, timeout=seconds, check=False).returncode == 0
    probe = query if probe is None else probe
    deadline = clock() + 15
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


def read_bus_address(child, fd, socket, clock=time.monotonic, pause=time.sleep):
    deadline = clock() + 15
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


def registry_owner(connection, child, birth, clock=time.monotonic, pause=time.sleep):
    from gi.repository import Gio, GLib
    deadline = clock() + 15
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
    for name in ["owned-bus-route.json", "owned-bus-runtime.json", "session.conf", "accessibility.conf"]:
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
const fs=require('node:fs'),path=require('node:path');
const [receiver,out,profile]=process.argv.slice(2);
const {chromium}=require(path.join(receiver,'Browser.Tests/node_modules/@playwright/test'));
(async()=>{
 const context=await chromium.launchPersistentContext(profile,{headless:false,args:['--force-renderer-accessibility','--no-sandbox']});
 const page=context.pages()[0]??await context.newPage();
 await page.addInitScript(()=>{window.__externalKeys=[];window.__externalKeySequence=0;document.addEventListener('keydown',e=>{
  window.__externalKeys.push({sequence:++window.__externalKeySequence,key:e.key,text:e.target.textContent?.trim(),id:e.target.id,parentId:e.target.parentElement?.id});
  window.__externalKeys=window.__externalKeys.slice(-128);
 },true)});
 await page.goto('http://127.0.0.1:5100/');
 await page.getByRole('button',{name:'Mount external authority reference',exact:true}).waitFor();
 let sequence=0,stopping=false;
 async function sample(){if(stopping)return;const value=await page.evaluate(()=>{
  const root=document.querySelector('#external-authority-reference'),active=document.activeElement;
  return {documentHasFocus:document.hasFocus(),active:{text:active?.textContent?.trim(),id:active?.id,parentId:active?.parentElement?.id},
   reference:root?{...Object.fromEntries([...root.attributes].filter(a=>a.name.startsWith('data-')).map(a=>[a.name.slice(5).replace(/-([a-z])/g,(_,c)=>c.toUpperCase()),a.value])),
     rootCount:document.querySelectorAll('#external-authority-reference').length,statusCount:root.querySelectorAll(':scope > [role="status"]').length,
     status:root.querySelector(':scope > [role="status"]')?.textContent,
     directButtons:[...root.querySelectorAll(':scope > button')].map(b=>b.textContent)}:null,keys:window.__externalKeys};
 });fs.writeFileSync(out+'.tmp',JSON.stringify({sequence:++sequence,at:Date.now(),...value}));fs.renameSync(out+'.tmp',out);}
 await sample();const timer=setInterval(()=>sample().catch(e=>{console.error(e);process.exit(1)}),100);
 const stop=async()=>{if(stopping)return;stopping=true;clearInterval(timer);await context.close();process.exit(0)};
 process.on('SIGTERM',stop);process.on('SIGINT',stop);await new Promise(()=>{});
})().catch(e=>{console.error(e);process.exit(1)});
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


def wait_server_ready(child, ready=owned_server_listener, clock=time.monotonic, pause=time.sleep):
    """Observe one original startup for at most15s; never restart server or retry navigation."""
    deadline = clock() + 15
    while clock() < deadline:
        code = child.poll()
        require(code is None, "original server exited before readiness: " + str(code) + "; see server.log")
        if ready(child.pid):
            return
        pause(.1)
    raise RuntimeError("original owned server readiness deadline exceeded; see server.log")


def inner(receiver, directory):
    # Private D-Bus, XDG settings, display, Pulse server and speech socket: no user-session replacement.
    os.environ.update(DISPLAY=":97", NO_AT_BRIDGE="0", GTK_MODULES="gail:atk-bridge",
                      GSETTINGS_BACKEND="keyfile", GNOME_ACCESSIBILITY="1",
                      XDG_CONFIG_HOME=str(directory / "config"), XDG_CACHE_HOME=str(directory / "cache"),
                      XDG_RUNTIME_DIR=str(directory / "runtime"), XDG_DATA_HOME=str(directory / "data"),
                      TMPDIR=str(directory / "tmp"), PULSE_SERVER="unix:" + str(directory / "pulse.sock"),
                      SPEECHD_ADDRESS="unix_socket:" + str(directory / "speech.sock"))
    for name in ["config", "cache", "runtime", "data", "tmp", "profile", "speech-config/modules", "speech-logs"]:
        (directory / name).mkdir(mode=0o700, parents=True, exist_ok=True)
    children = []
    leaders = []

    def launch(argv, name, cwd=None, pass_fds=()):
        require(all(child.poll() is None for child in children), "prior required AT service exited")
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
        require(all(child.poll() is None for child in children), "prior required AT service exited")
        subprocess.run(argv, check=True, timeout=seconds)

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
        address = read_bus_address(bus, read_fd, state["sockets"]["accessibility"])
    finally:
        os.close(read_fd)
        if write_fd is not None:
            os.close(write_fd)
    # libatspi caches its first connection: this assignment precedes every AT import and fresh client.
    os.environ["AT_SPI_BUS_ADDRESS"] = address
    require(not Path("/tmp/.X97-lock").exists() and not Path("/tmp/.X11-unix/X97").exists(), "selected display already occupied; no reuse")
    xvfb = launch(["Xvfb", ":97", "-screen", "0", "1280x800x24", "-nolisten", "tcp"], "xvfb")
    wait_display_ready(xvfb)
    import gi
    gi.require_version("Gio", "2.0")
    from gi.repository import Gio
    session_address = os.environ["DBUS_SESSION_BUS_ADDRESS"]
    require(re.fullmatch(re.escape("unix:path="+state["sockets"]["session"])+r",guid=[0-9a-f]{32}", session_address) is not None,
            "session bus address outside owned config")
    session_connection = Gio.DBusConnection.new_for_address_sync(session_address,
        Gio.DBusConnectionFlags.AUTHENTICATION_CLIENT | Gio.DBusConnectionFlags.MESSAGE_BUS_CONNECTION, None, None)
    from gi.repository import GLib
    session_pid = session_connection.call_sync("org.freedesktop.DBus", "/org/freedesktop/DBus", "org.freedesktop.DBus",
        "GetConnectionUnixProcessID", GLib.Variant("(s)", ("org.freedesktop.DBus",)), GLib.VariantType("(u)"),
        Gio.DBusCallFlags.NONE, 5000, None).unpack()[0]
    session_birth = proc(session_pid)
    require_birth(session_birth, os.getppid(), os.getsid(0))
    require(bus_listener(session_pid, state["sockets"]["session"]), "session socket not owned by original daemon")
    connection = Gio.DBusConnection.new_for_address_sync(address,
        Gio.DBusConnectionFlags.AUTHENTICATION_CLIENT | Gio.DBusConnectionFlags.MESSAGE_BUS_CONNECTION, None, None)
    registry = launch(["/usr/libexec/at-spi2-registryd"], "registry")
    birth = proc(registry.pid)
    owner = registry_owner(connection, registry, birth)
    write(directory / "owned-bus-runtime.json", {"bus": proc(bus.pid), "address": address,
          "registry": owner, "sessionBus": session_birth, "sessionAddress": session_address,
          "addressSetBeforeAtspiImport": True, "objectIdentities": objects,
          "activation": "disabled by exact closed configs; vendor declarations retained unresolved"})
    launch(["openbox", "--sm-disable"], "openbox")
    command(["gsettings", "set", "org.gnome.desktop.interface", "toolkit-accessibility", "true"])
    command(["gsettings", "set", "org.gnome.desktop.a11y.applications", "screen-reader-enabled", "true"])
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
    deadline = time.monotonic() + 15
    while not (directory / "speech.sock").exists() and time.monotonic() < deadline:
        time.sleep(.1)
    require((directory / "speech.sock").exists(), "private speech service unavailable")
    command(["/usr/bin/python3", str(Path(__file__).with_name("speech-dispatcher-preflight.py")), str(directory / "speech-preflight.json")], seconds=30)
    orca = launch(["/usr/bin/python3", str(Path(__file__).with_name("orca-faulthandler.py")), "--replace", "--debug",
                   "--debug-file=" + str(directory / "orca-debug.log")], "orca")
    time.sleep(3)
    server = launch(["dotnet", "Server.dll", "--urls", "http://127.0.0.1:5100"], "server", receiver / "artifacts/authority-server")
    wait_server_ready(server)
    (directory / "browser.cjs").write_text(BROWSER)
    browser = launch(["node", str(directory / "browser.cjs"), str(receiver), str(directory / "browser-dom.json"), str(directory / "profile")], "browser")
    observe(directory, orca.pid, browser.pid)
    require(all(child.poll() is None for child in children), "required AT/browser service exited")


def observe(directory, orca_pid, browser_pid):
    import gi
    gi.require_version("Atspi", "2.0")
    from gi.repository import Atspi
    actions = []
    observations = {}

    def dom():
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
          "browser": {"family": "chromium", "pid": actual_browser_pid, "launcherPid": browser_pid}, "actions": actions, "observations": observations})


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
        if Path(path).name in ["dbus-run-session", "dbus-daemon", "at-spi-bus-launcher", "at-spi2-registryd"] or any(Path(path).name.startswith(prefix) for prefix in LIBRARY_PREFIXES):
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
        for package in ["at-spi2-core", "dbus", "dbus-daemon", "dbus-session-bus-common", "libatspi2.0-0t64", "libatk-bridge2.0-0t64"]:
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
    receipt = {"schema": SCHEMA, "result": "passed", "templates": packet["templates"], "caller": preflight["caller"],
               "producer": preflight["producer"], **journey, "keyboard": "xdotool-X11", "speechBoundary": "Orca SPEECH OUTPUT",
               "physicalAudioHardware": "not-observed", "cleanup": result, "sourceQualificationSha256": digest(packet_path),
               "servedAssemblySha256": served_digest,
               "evidenceSha256": {name: digest(directory / name) for name in ["orca-debug.log", "journey.json", "process-result.json", "speech-preflight.json", "tool-identities.json", "source-qualification.json", "host-packages.txt", "resource-leaders.json", "activation-provenance.json", "owned-bus-route.json", "owned-bus-runtime.json", "session.conf", "accessibility.conf"]}}
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
        receipt = {"schema": SCHEMA, "result": "passed", **preflight, "process": {"name": "orca", "pid": 1}, "browser": {"family": "chromium", "pid": 2, "launcherPid": 60},
                   "keyboard": "xdotool-X11", "speechBoundary": "Orca SPEECH OUTPUT", "physicalAudioHardware": "not-observed",
                   "cleanup": {"disposition": "observed-empty", "unknown": [], "remaining": []}, "sourceQualificationSha256": digest(directory / "source-qualification.json"),
                   "evidenceSha256": {"orca-debug.log": digest(directory / "orca-debug.log")}, "observations": observations,
                   "actions": [{"name": name, "key": "Return", "atspiFocused": True, "directReferenceControl": True, "eventSequence": index + 1} for index, name in enumerate(names)]}
        write(directory / "process-result.json", {"exit": 0, "firstCause": None, "cleanup": receipt["cleanup"]})
        receipt["evidenceSha256"]["process-result.json"] = digest(directory / "process-result.json")
        activation = route_fixture()
        write(directory / "activation-provenance.json", activation)
        route_fixture_evidence(directory, activation)
        for name in ["owned-bus-route.json", "owned-bus-runtime.json", "session.conf", "accessibility.conf"]:
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
    print("PASS actual AT binder: good receipt, 25 existing plus 2 diagnostic refusal controls; 8 prerequisite refusals and workflow bad controls; no AT/browser launched")



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


def route_fixture_evidence(directory, activation):
    sockets = {name: "/tmp/fsgg-at-fixture/"+name+".sock" for name in ["session", "accessibility"]}
    for name, socket in sockets.items():
        (directory / (name+".conf")).write_bytes(closed_bus_config(socket, 1000))
    write(directory / "owned-bus-route.json", {"sourceProof": SOURCE_PROOF, "uid": 1000, "sockets": sockets})
    bus = {"pid": 40, "start": 1, "ppid": 42, "sid": 42}
    registry = {"pid": 41, "start": 2, "ppid": 42, "sid": 42}
    selected = route_metadata(activation)
    browser = {"pid": 2, "start": 10, "ppid": 60, "sid": 42}
    launcher = {"pid": 60, "start": 9, "ppid": 42, "sid": 42}
    write(directory / "resource-leaders.json", [{"resource": "accessibility-bus", **bus}, {"resource": "registry", **registry},
          {"resource": "browser", **launcher}])
    write(directory / "owned-bus-runtime.json", {"bus": bus, "address": "unix:path="+sockets["accessibility"]+",guid="+"a"*32,
          "sessionBus": {"pid": 43, "start": 3, "ppid": 44, "sid": 42},
          "sessionAddress": "unix:path="+sockets["session"]+",guid="+"b"*32,
          "registry": {"pid": 41, "birth": registry}, "addressSetBeforeAtspiImport": True, "objectIdentities": selected,
          "mappedLibraries": {"observer": {"birth": bus, "object": selected["libatspi.so."]},
                              "browser": {"birth": browser, "ancestry": [browser, launcher], "object": selected["libatk-bridge-2.0.so."]}}})


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
        require(route_evidence(directory, good, {"browser": {"pid": 2, "launcherPid": 60}}), "good owned route fixture refused")
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
                route_evidence(directory, good, {"browser": {"pid": 2, "launcherPid": 60}})
            except RuntimeError:
                pass
            else:
                raise RuntimeError("unbound runtime route accepted")
        (directory / "owned-bus-runtime.json").write_bytes(actual)
    source = Path(__file__).read_text()
    inner_source = source.split("def inner(", 1)[1].split("def observe(", 1)[0]
    require(inner_source.index('os.environ["AT_SPI_BUS_ADDRESS"] = address') < inner_source.index("import gi") <
            inner_source.index('registry = launch'), "cached AT client imported before owned address")
    require(inner_source.index("wait_display_ready(xvfb)") < inner_source.index('registry = launch') <
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


def workflow_guard(workflow):
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
    parser.add_argument("--self-test", action="store_true")
    parser.add_argument("--inner", action="store_true")
    parser.add_argument("--capture-activation", action="store_true")
    parser.add_argument("first", nargs="?")
    parser.add_argument("second", nargs="?")
    args = parser.parse_args()
    if args.self_test:
        self_test()
    elif args.capture_activation:
        require(args.first, "activation output path required")
        capture_activation(Path(args.first))
    elif args.inner:
        directory = Path(args.second)
        try:
            inner(Path(args.first), directory)
        except BaseException as ex:
            write(directory / "inner-result.json", {"firstCause": type(ex).__name__ + ": " + str(ex), "exit": 1})
            raise
    else:
        require(args.first and args.second, "candidate directory and authenticated preflight required")
        with capture_termination() as termination:
            qualify(Path(args.first).resolve(), Path(args.second).resolve(), termination)


if __name__ == "__main__":
    main()
