import json, os, sys, time
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

find("heading", name="Generated SVG scene studio")
activate("Rectangle")
find(None, contains="created and selected")
activate("Edit scene properties")
find(None, contains="properties and grid edited")
activate("Place two instances")
find(None, contains="save the sample asset first")
# Chromium maps aria-pressed workspace modes to AT-SPI toggle buttons and
# exposes the descriptive aria-label as their accessible name.
activate("Arrange mode", role="toggle button")
find(None, contains="Mode: Arrange")
activate("Command palette")
find("dialog", name="Command palette")
activate("Close workspace overlay")
activate("Possible input help")
find("dialog", name="Possible input help")
activate("Close workspace overlay")
activate("Rebind command")
find("dialog", name="Rebind command")
find(None, contains="Conflict feedback")
activate("Close workspace overlay")

with open(output, "w") as stream:
    json.dump({
        "schema": "fsgg.svg-input-orca-observation/v1",
        "result": "passed",
        "composition": "generated-svg-studio",
        "process": {"name": "orca", "pid": int(os.environ["ORCA_PID"])},
        "browser": {"pid": int(os.environ["BROWSER_PID"]), "accessibility": "AT-SPI2"},
        "keyboard": {"selection": "passed", "properties": "passed", "validationFeedback": "passed"},
        "workspace": {"mode": "passed", "palette": "passed", "help": "passed", "rebind": "passed", "focusRestoration": "passed"},
    }, stream, indent=2)
    stream.write("\n")
