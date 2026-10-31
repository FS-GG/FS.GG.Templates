"""Orca/AT-SPI observer for the actual generated soldier player (SVG-COHERENCE-01.5).

Same observation contract as svg-input-orca.py: real X11 keyboard events
(xdotool) drive the player, AT-SPI reports where focus arrived and what the
accessibility tree offers, and Orca's debug log records what it spoke. The
browser-side DOM sample (soldier-orca-browser.cjs) must agree with AT-SPI for a
focus claim. Nothing here activates a control through AT-SPI actions.

Run through observe-soldier-orca.sh. SOLDIER_ORCA_MUTANT (read by the browser
host) selects a causal control; a control must end `refused` at its expected
step, never `passed`.
"""
import json, os, subprocess, sys, time
import gi

gi.require_version("Atspi", "2.0")
from gi.repository import Atspi

output = sys.argv[1]
MUTANT = os.environ.get("SOLDIER_ORCA_MUTANT", "")
EXPECTED_STEP = {
    "": None,
    "unnamed-roster-button": "roster-toggle-exposed-with-pressed-state",
    "no-focus-transfer": "removal-focus-reaches-survivor",
    "silent-status": "removal-status-exposed-as-polite-live-region",
}[MUTANT]
FIRST = "soldier-0000, Blue, Ready, health 100"
steps = []
current = {"name": "startup"}


def walk(node):
    yield node
    for index in range(node.get_child_count()):
        try:
            yield from walk(node.get_child_at_index(index))
        except Exception:
            pass


def find(role, name=None, prefix=None, timeout=20):
    end = time.time() + timeout
    seen = set()
    while time.time() < end:
        for item in walk(Atspi.get_desktop(0)):
            try:
                if role is not None and item.get_role_name() != role:
                    continue
                value = item.get_name() or ""
                if value:
                    seen.add(value)
                if (name is None or value == name) and (prefix is None or value.startswith(prefix)):
                    return item
            except Exception:
                pass
        time.sleep(.2)
    raise RuntimeError(f"AT-SPI object unavailable: role={role} name={name} prefix={prefix} sample={sorted(seen)[:12]}")


def key(*keys):
    subprocess.run(["xdotool", "key", "--clearmodifiers", *keys], check=True)
    # Keep observation behind the browser/Orca event boundary; the delay prevents
    # treating a key as presented before the focus event reached the tree.
    time.sleep(.75)


def fresh_dom():
    with open(output + ".browser-dom.json") as stream:
        dom = json.load(stream)
    if (dom.get("schema") != "fsgg.orca-browser-dom/v1"
            or dom.get("browserFamily") != os.environ["SVG_ORCA_BROWSER_FAMILY"]
            or not isinstance(dom.get("sampleSequence"), int)
            or abs(time.time() * 1000 - dom.get("sampledAtUnixMs", 0)) > 2000):
        raise RuntimeError(f"fresh browser DOM observation unavailable: {dom}")
    return dom["observation"]


def wait_dom(predicate, label, timeout=10):
    end = time.time() + timeout
    last = None
    while time.time() < end:
        try:
            last = fresh_dom()
            if predicate(last):
                return last
        except Exception as error:
            last = {"error": str(error)}
        time.sleep(.15)
    raise RuntimeError(f"browser DOM condition not met: {label}; last={json.dumps(last)[:600]}")


def active_name(observation):
    active = observation.get("activeElement") or {}
    return active.get("ariaLabel") or active.get("text")


def atspi_focused(name=None, prefix=None, role=None, timeout=10):
    """AT-SPI object that is FOCUSED, named as requested, and agrees with the DOM."""
    end = time.time() + timeout
    while time.time() < end:
        try:
            dom = fresh_dom()
        except Exception:
            dom = None
        dom_name = active_name(dom) if dom else None
        agrees = (dom is not None and dom.get("documentHasFocus") is True and dom_name is not None
                  and (name is None or dom_name == name) and (prefix is None or dom_name.startswith(prefix)))
        if agrees:
            for item in walk(Atspi.get_desktop(0)):
                try:
                    value = item.get_name() or ""
                    if (item.get_state_set().contains(Atspi.StateType.FOCUSED) and value == dom_name
                            and (role is None or item.get_role_name() == role)):
                        return item
                except Exception:
                    pass
        time.sleep(.15)
    raise RuntimeError(f"focus did not reach name={name} prefix={prefix} role={role}")


def tab_to(name, role=None, limit=160, direction="Tab"):
    for _ in range(limit):
        key(direction)
        try:
            dom = fresh_dom()
        except Exception:
            continue
        if dom.get("documentHasFocus") and active_name(dom) == name:
            return atspi_focused(name=name, role=role)
    raise RuntimeError(f"Tab traversal never focused {name}")


def speech_log_offset():
    try:
        return os.path.getsize(output + ".orca-debug.log")
    except OSError:
        return 0


def wait_for_speech(*needles, timeout=10, after=0):
    debug = output + ".orca-debug.log"
    end = time.time() + timeout
    while time.time() < end:
        try:
            with open(debug, "rb") as stream:
                stream.seek(after)
                text = stream.read().decode(errors="replace")
        except FileNotFoundError:
            text = ""
        speech = "\n".join(line.split("SPEECH OUTPUT:", 1)[1] for line in text.splitlines() if "SPEECH OUTPUT:" in line)
        if speech and all(needle in speech for needle in needles):
            return speech[-400:]
        time.sleep(.2)
    raise RuntimeError(f"Orca did not record speech containing {needles}")


def step(name, action):
    current["name"] = name
    result = action()
    steps.append({"name": name, "passed": True, **({"detail": result} if isinstance(result, dict) else {})})


def finish(result, error=None):
    body = {
        "schema": "fsgg.soldier-input-orca-observation/v1",
        "result": result,
        "composition": "generated-soldier-player",
        "mutant": MUTANT or None,
        "expectedRefusalStep": EXPECTED_STEP,
        "steps": steps,
        "failedStep": None if error is None else current["name"],
        "error": None if error is None else str(error)[:800],
        "process": {"name": "orca", "pid": int(os.environ["ORCA_PID"])},
        "browser": {"name": os.environ["SVG_ORCA_BROWSER_FAMILY"], "pid": int(os.environ["BROWSER_PID"]), "accessibility": "AT-SPI2"},
        "keyboard": {"events": "xdotool-X11"},
        "screenReader": {"name": "Orca", "speechOutputObserved": any(s.get("detail", {}).get("speech") for s in steps), "audibleHardwareOutput": "not-observed"},
        "claims": {"physicalInput": False, "assistiveTechnologyUserStudy": False},
    }
    with open(output, "w") as stream:
        json.dump(body, stream, indent=2)
        stream.write("\n")


def journey():
    state = {}

    def reach_mount():
        tab_to("Mount soldier reference", role="push button")
        key("Return")
        find("heading", name="Equipped soldier reference")
        return {"headingFound": True}
    step("mount-by-keyboard", reach_mount)

    def reach_note():
        item = tab_to("Soldier reference note", role="entry")
        return {"role": item.get_role_name()}
    step("note-field-reachable-by-tab", reach_note)

    def select_first():
        tab_to("Select focused soldier", role="push button")
        key("Return")
        wait_dom(lambda o: (o.get("soldier") or {}).get("selected") == "soldier-0000", "keyboard selection")
        state["before"] = fresh_dom()["soldier"]["firstX"]
        return {"selected": "soldier-0000"}
    step("keyboard-selection-without-pointer", select_first)

    def move_selected():
        tab_to("Move selected soldier", role="push button")
        key("Return")
        wait_dom(lambda o: (o.get("soldier") or {}).get("firstX") == state["before"] + 16, "keyboard move")
        return {"movedBy": 16}
    step("keyboard-command-moves-selected", move_selected)

    def roster_toggle():
        item = find("toggle button", name=FIRST, timeout=10)
        pressed = item.get_state_set().contains(Atspi.StateType.PRESSED) or item.get_state_set().contains(Atspi.StateType.CHECKED)
        if not pressed:
            raise RuntimeError("selected roster toggle button does not expose pressed state")
        return {"name": FIRST, "role": "toggle button", "pressed": True}
    step("roster-toggle-exposed-with-pressed-state", roster_toggle)

    def removal():
        tab_to("Remove selected soldier", role="push button")
        offset = speech_log_offset()
        state["offset"] = offset
        key("Return")
        wait_dom(lambda o: (o.get("soldier") or {}).get("worldCount") == "99", "removal projected")
        item = atspi_focused(prefix="soldier-0001, ", role="toggle button", timeout=8)
        return {"focused": item.get_name(), "role": item.get_role_name()}
    step("removal-focus-reaches-survivor", removal)

    def focus_spoken():
        # The new focus target is what Orca reliably announces: its name, role and state.
        speech = wait_for_speech("soldier-0001", "toggle button", after=state["offset"], timeout=8)
        return {"speech": speech}
    step("removal-focus-spoken-by-orca", focus_spoken)

    def status_exposed():
        # Deterministic AT-SPI read of the polite live region, independent of speech.
        end = time.time() + 8
        found = None
        while time.time() < end and found is None:
            for item in walk(Atspi.get_desktop(0)):
                try:
                    if item.get_role_name() != "status bar":
                        continue
                    text = Atspi.Text.get_text(item.get_text_iface(), 0, Atspi.Text.get_character_count(item.get_text_iface()))
                    if "Focused soldier removed" in text:
                        found = (text, dict(item.get_attributes() or {}))
                        break
                except Exception:
                    pass
            time.sleep(.2)
        if found is None:
            raise RuntimeError("removal status text not exposed through AT-SPI")
        text, attributes = found
        if attributes.get("container-live") != "polite" or attributes.get("live") not in ("polite", None):
            raise RuntimeError(f"status region is not exposed as polite live region: {attributes}")
        return {"text": text, "containerLive": attributes.get("container-live")}
    step("removal-status-exposed-as-polite-live-region", status_exposed)

    def status_spoken():
        # Orca's debug file is line-buffered by soldier-orca-launcher.py, so the
        # speech log is current when read. A retained run proved Orca does speak this
        # message shortly after the focus speech.
        speech = wait_for_speech("Focused soldier removed", after=state["offset"], timeout=10)
        return {"speech": speech}
    step("removal-status-spoken-by-orca", status_spoken)

    def roster_traversal():
        key("Tab")
        atspi_focused(prefix="soldier-0002, ", role="toggle button")
        key("shift+Tab")
        atspi_focused(prefix="soldier-0001, ", role="toggle button")
        return {"forward": "soldier-0002", "back": "soldier-0001"}
    step("roster-keyboard-traversal-after-transfer", roster_traversal)


try:
    journey()
    if MUTANT:
        finish("failed-control-survived", f"mutant {MUTANT} was not refused")
        sys.exit(4)
    finish("passed")
except Exception as error:
    finish("refused" if MUTANT else "failed", error)
    sys.exit(3)
