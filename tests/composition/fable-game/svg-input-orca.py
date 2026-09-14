import json, os, subprocess, sys, time
import gi

gi.require_version("Atspi", "2.0")
from gi.repository import Atspi

output = sys.argv[1]

def walk(node):
    yield node
    for index in range(node.get_child_count()):
        try:
            yield from walk(node.get_child_at_index(index))
        except Exception:
            pass

def find(role, name=None, contains=None, timeout=30):
    end = time.time() + timeout
    available = set()
    while time.time() < end:
        for item in walk(Atspi.get_desktop(0)):
            try:
                if role is not None and item.get_role_name() != role:
                    continue
                value = item.get_name() or ""
                if value:
                    available.add(value)
                if contains is not None:
                    try:
                        text = item.get_text_iface()
                        count = Atspi.Text.get_character_count(text)
                        value += " " + Atspi.Text.get_text(text, 0, count)
                    except Exception:
                        pass
                if (name is None or value == name) and (contains is None or contains in value):
                    return item
            except Exception:
                pass
        time.sleep(.2)
    sample = sorted(available)[:40]
    raise RuntimeError(f"AT-SPI object unavailable: role={role} name={name} contains={contains} available={sample}")

def activate(name, role="push button"):
    node = find(role, name=name)
    action = node.get_action_iface()
    if not action.do_action(0):
        raise RuntimeError(f"AT-SPI action refused: {name}")
    # Keep observer traversal behind the accessibility event. The retained
    # Chromium/Orca run stalled at its first AX cache update when traversal
    # followed immediately; this pacing records ordering without claiming the
    # browser-side cause of that stall.
    time.sleep(.75)

def focused():
    candidate = None
    for item in walk(Atspi.get_desktop(0)):
        try:
            if item.get_state_set().contains(Atspi.StateType.FOCUSED):
                # Containers and their focused descendant may both carry the
                # state. The depth-first traversal leaves the actual control
                # last, which is the focus value the keyboard user observes.
                candidate = item
        except Exception:
            pass
    return candidate

def key(*keys):
    subprocess.run(["xdotool", "key", "--clearmodifiers", *keys], check=True)
    # Keep observation behind the browser/Orca event boundary. This is a real X
    # keyboard path; the delay prevents this observer from assuming the focus
    # event was already presented.
    time.sleep(.75)

def tab_to(name, limit=80):
    observed = []
    for _ in range(limit):
        key("Tab")
        dom = None
        try:
            dom = json.load(open(output + ".browser-dom.json"))
        except Exception:
            pass
        active = ((dom or {}).get("observation") or {}).get("activeElement") or {}
        dom_name = active.get("ariaLabel") or active.get("text")
        current = []
        for item in walk(Atspi.get_desktop(0)):
            try:
                if item.get_state_set().contains(Atspi.StateType.FOCUSED):
                    value = item.get_name() or ""
                    if value:
                        current.append({"name": value, "role": item.get_role_name()})
                    # Firefox can retain FOCUSED on an ancestor exposed later in
                    # the tree. Assert the named target's own state rather than
                    # selecting whichever focused object traversal visited last.
                    if value == name and (dom is None or dom_name == name):
                        return item
            except Exception:
                pass
        window = subprocess.run(["xdotool", "getwindowfocus"], capture_output=True, text=True, check=False).stdout.strip()
        observed.append({"window": window, "focused": current, "dom": dom})
    raise RuntimeError(f"keyboard focus did not reach {name}; observed={observed[-10:]}")

def wait_for_focus(name, role=None, timeout=10):
    end = time.time() + timeout
    while time.time() < end:
        for item in walk(Atspi.get_desktop(0)):
            try:
                if (item.get_state_set().contains(Atspi.StateType.FOCUSED)
                    and (item.get_name() or "") == name
                    and (role is None or item.get_role_name() == role)):
                    return item
            except Exception:
                pass
        time.sleep(.1)
    item = focused()
    actual = None if item is None else {"name": item.get_name(), "role": item.get_role_name()}
    raise RuntimeError(f"focus was not restored to role={role} name={name}; actual={actual}")

def wait_until_absent(role, name, timeout=10):
    end = time.time() + timeout
    while time.time() < end:
        present = False
        for item in walk(Atspi.get_desktop(0)):
            try:
                if item.get_role_name() == role and (item.get_name() or "") == name:
                    if item.get_state_set().contains(Atspi.StateType.SHOWING):
                        present = True
                        break
            except Exception:
                pass
        if not present:
            return
        time.sleep(.1)
    raise RuntimeError(f"AT-SPI object remained visible: role={role} name={name}")

def wait_for_speech(*needles, timeout=10):
    debug = output + ".orca-debug.log"
    end = time.time() + timeout
    while time.time() < end:
        try:
            text = open(debug, errors="replace").read()
        except FileNotFoundError:
            text = ""
        speech = "\n".join(
            line.split("SPEECH OUTPUT:", 1)[1]
            for line in text.splitlines()
            if "SPEECH OUTPUT:" in line
        )
        if speech and all(needle in speech for needle in needles):
            return True
        time.sleep(.2)
    raise RuntimeError("Orca did not record the expected speech output")

find("heading", name="Generated SVG scene studio")
# Traverse and activate the real control with X keyboard events. AT-SPI is used
# only to observe where focus arrived and what the application announced.
tab_to("Rectangle")
key("Return")
find(None, contains="created and selected")
activate("Edit scene properties")
find(None, contains="properties and grid edited")
activate("Place two instances")
find(None, contains="save the sample asset first")
# Continue keyboard traversal through the replay panel, its first real action,
# and the command-palette control. Each target's own FOCUSED state is observed,
# so a retained focused ancestor cannot substitute for the requested control.
tab_to("Replay timeline")
tab_to("Replay complete arena recording")
tab_to("Command palette")
key("Return")
find("dialog", name="Command palette")
key("Escape")
wait_until_absent("dialog", "Command palette")
# The application contract records the scene id as RestoreFocus. Its SVG root
# is exposed through Chromium AT-SPI as role=application with this exact label;
# the similarly named document heading is not an acceptable substitute.
wait_for_focus("Generated SVG scene studio", role="application")
# WorkspaceInput declares help as the g,h sequence.
key("g", "h")
find("dialog", name="Possible input help")
activate("Close workspace overlay")
activate("Rebind command")
find("dialog", name="Rebind command")
find(None, contains="Conflict feedback")
activate("Close workspace overlay")
# Mode controls are rendered by the workspace host. Exercise the AT-SPI action,
# then repeat the keyboard route so mode-render focus retention is observed.
activate("Arrange mode", role="toggle button")
find(None, contains="Mode: Arrange")
# Repeat the real Tab route after the dynamic mode render. This preserves the
# previously disputed focus-retention subject instead of inferring it from the
# stable Rectangle route above.
tab_to("Replay timeline")
tab_to("Replay complete arena recording")
tab_to("Command palette")
wait_for_speech("Rectangle", "created and selected")

with open(output, "w") as stream:
    json.dump({
        "schema": "fsgg.svg-input-orca-observation/v1",
        "result": "passed",
        "composition": "generated-svg-studio",
        "process": {"name": "orca", "pid": int(os.environ["ORCA_PID"])},
        "browser": {"name": os.environ["SVG_ORCA_BROWSER_FAMILY"], "pid": int(os.environ["BROWSER_PID"]), "accessibility": "AT-SPI2"},
        "keyboard": {"events": "xdotool-X11", "navigation": "passed", "activation": "passed", "selection": "passed", "palette": "passed", "escape": "passed", "focusRestoration": "passed"},
        "atspiActions": {"properties": "passed", "twoInstancesRefusal": "passed", "mode": "passed", "helpClose": "passed", "rebind": "passed", "validationFeedback": "passed"},
        "workspace": {"mode": "passed", "palette": "passed", "help": "passed", "rebind": "passed", "focusRestoration": "passed"},
        "screenReader": {"name": "Orca", "speechOutputObserved": True, "audibleHardwareOutput": "not-observed"},
    }, stream, indent=2)
    stream.write("\n")
