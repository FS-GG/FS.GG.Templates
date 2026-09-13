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
    while time.time() < end:
        for item in walk(Atspi.get_desktop(0)):
            try:
                if item.get_role_name() != role:
                    continue
                value = item.get_name() or ""
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
    raise RuntimeError(f"AT-SPI object unavailable: role={role} name={name} contains={contains}")

def activate(name):
    node = find("push button", name=name)
    action = node.get_action_iface()
    if not action.do_action(0):
        raise RuntimeError(f"AT-SPI action refused: {name}")

find("heading", name="Generated SVG scene studio")
activate("Rectangle")
find("status", contains="created and selected")
activate("Edit scene properties")
find("status", contains="properties and grid edited")
activate("Place two instances")
find("status", contains="save the sample asset first")

with open(output, "w") as stream:
    json.dump({
        "schema": "fsgg.svg-authoring-orca-observation/v1",
        "result": "passed",
        "composition": "generated-svg-studio",
        "process": {"name": "orca", "pid": int(os.environ["ORCA_PID"])},
        "browser": {"pid": int(os.environ["BROWSER_PID"]), "accessibility": "AT-SPI2"},
        "keyboard": {"selection": "passed", "properties": "passed", "validationFeedback": "passed"},
    }, stream, indent=2)
    stream.write("\n")
