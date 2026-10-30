"""Provider/Studio AT-SPI driver, run inside the shared svg Orca session (observe-svg-input-orca.sh).

Real keyboard (xdotool) and AT-SPI actions drive the generated Studio; the pure runner and every
causal rule live in current-reference-provider-studio.py. This file only supplies the live primitives:
the Orca debug-log offset, fresh browser DOM samples, AT-SPI FOCUSED nodes and tree lookups.
"""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import urllib.request

import gi

gi.require_version("Atspi", "2.0")
from gi.repository import Atspi

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("provider_studio", HERE / "current-reference-provider-studio.py")
M = importlib.util.module_from_spec(spec)
spec.loader.exec_module(M)

output = sys.argv[1]


def walk(node):
    yield node
    for index in range(node.get_child_count()):
        try:
            yield from walk(node.get_child_at_index(index))
        except Exception:
            pass


def text_of(item):
    try:
        text = item.get_text_iface()
        return Atspi.Text.get_text(text, 0, Atspi.Text.get_character_count(text))
    except Exception:
        return ""


class Live:
    def speech_offset(self):
        try:
            return os.path.getsize(output + ".orca-debug.log")
        except OSError:
            return 0

    def speech_between(self, start, end):
        return M.speech_text(output + ".orca-debug.log", start, end)

    def dom(self):
        end = time.time() + 10
        last = None
        while time.time() < end:
            try:
                with open(output + ".browser-dom.json") as stream:
                    value = json.load(stream)
                observation = value.get("observation")
                if (value.get("schema") == "fsgg.orca-browser-dom/v1" and value.get("browserFamily") == "chromium" and
                        isinstance(value.get("sampleSequence"), int) and observation is not None and
                        abs(time.time() * 1000 - value.get("sampledAtUnixMs", 0)) <= 2000):
                    return value
                last = value
            except Exception as error:
                last = str(error)
            time.sleep(.1)
        raise RuntimeError("fresh browser DOM observation unavailable: %s" % (last,))

    def key(self, *keys):
        subprocess.run(["xdotool", "key", "--clearmodifiers", *keys], check=True)
        # Keep observation behind the browser/Orca event boundary; this is the pacing the shared journey uses.
        time.sleep(.75)

    def activate(self, name, role):
        end = time.time() + 30
        while time.time() < end:
            for item in walk(Atspi.get_desktop(0)):
                try:
                    if item.get_role_name() == role and (item.get_name() or "") == name:
                        if not item.get_action_iface().do_action(0):
                            raise RuntimeError("AT-SPI action refused: " + name)
                        time.sleep(.75)
                        return
                except RuntimeError:
                    raise
                except Exception:
                    pass
            time.sleep(.2)
        raise RuntimeError("AT-SPI object unavailable: %s %s" % (role, name))

    def focused(self):
        rows = []
        for item in walk(Atspi.get_desktop(0)):
            try:
                if item.get_state_set().contains(Atspi.StateType.FOCUSED):
                    rows.append({"name": item.get_name() or "", "role": item.get_role_name()})
            except Exception:
                pass
        return rows

    def present(self, role, name):
        for item in walk(Atspi.get_desktop(0)):
            try:
                if role is not None and item.get_role_name() != role:
                    continue
                value = item.get_name() or ""
                if role is None:
                    # Text lookups (live status, feedback) match by containment, as the shared journey does.
                    if name in value or name in text_of(item):
                        return True
                elif value == name and item.get_state_set().contains(Atspi.StateType.SHOWING):
                    return True
            except Exception:
                pass
        return False

    def served_index_sha256(self):
        with urllib.request.urlopen(os.environ["PROVIDER_STUDIO_ADDRESS"], timeout=15) as response:
            return hashlib.sha256(response.read(16 * 1048576)).hexdigest()


custody_before = json.load(open(os.environ["PROVIDER_STUDIO_CUSTODY"]))
steps = M.run_steps(Live(), custody_before)
with open(output, "w") as stream:
    json.dump({"schema": "fsgg.current-provider-studio-journey/1",
               "process": {"name": "orca", "pid": int(os.environ["ORCA_PID"])},
               "browser": {"family": os.environ["SVG_ORCA_BROWSER_FAMILY"], "pid": int(os.environ["BROWSER_PID"]), "accessibility": "AT-SPI2"},
               "orcaVersion": os.environ["PROVIDER_STUDIO_ORCA_VERSION"], "steps": steps}, stream, indent=2)
    stream.write("\n")
