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
                        value += " " + text.get_text(0, text.get_character_count())
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
    time.sleep(.15)

def tab_to(name, limit=80):
    observed = []
    for _ in range(limit):
        key("Tab")
        item = focused()
        if item is None:
            continue
        value = item.get_name() or ""
        if value:
            observed.append(value)
        if value == name:
            return item
    raise RuntimeError(f"keyboard focus did not reach {name}; observed={observed[-20:]}")

def wait_for_focus(name, timeout=10):
    end = time.time() + timeout
    while time.time() < end:
        item = focused()
        if item is not None and (item.get_name() or "") == name:
            return item
        time.sleep(.1)
    item = focused()
    actual = None if item is None else (item.get_name() or item.get_role_name())
    raise RuntimeError(f"focus was not restored to {name}; actual={actual}")

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
# Chromium maps aria-pressed workspace modes to AT-SPI toggle buttons and
# exposes the descriptive aria-label as their accessible name.
activate("Arrange mode", role="toggle button")
find(None, contains="Mode: Arrange")
tab_to("Command palette")
key("Return")
find("dialog", name="Command palette")
key("Escape")
wait_for_focus("Command palette")
tab_to("Possible input help")
key("Return")
find("dialog", name="Possible input help")
activate("Close workspace overlay")
activate("Rebind command")
find("dialog", name="Rebind command")
find(None, contains="Conflict feedback")
activate("Close workspace overlay")
wait_for_speech("Rectangle", "created and selected")

with open(output, "w") as stream:
    json.dump({
        "schema": "fsgg.svg-input-orca-observation/v1",
        "result": "passed",
        "composition": "generated-svg-studio",
        "process": {"name": "orca", "pid": int(os.environ["ORCA_PID"])},
        "browser": {"pid": int(os.environ["BROWSER_PID"]), "accessibility": "AT-SPI2"},
        "keyboard": {"events": "xdotool-X11", "navigation": "passed", "activation": "passed", "selection": "passed", "palette": "passed", "escape": "passed", "focusRestoration": "passed"},
        "atspiActions": {"properties": "passed", "twoInstancesRefusal": "passed", "mode": "passed", "helpClose": "passed", "rebind": "passed", "validationFeedback": "passed"},
        "workspace": {"mode": "passed", "palette": "passed", "help": "passed", "rebind": "passed", "focusRestoration": "passed"},
        "screenReader": {"name": "Orca", "speechOutputObserved": True, "audibleHardwareOutput": "not-observed"},
    }, stream, indent=2)
    stream.write("\n")
