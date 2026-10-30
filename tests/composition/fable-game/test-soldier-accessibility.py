#!/usr/bin/env python3
"""Data-only verification and finite inert controls for the soldier accessibility evidence.

--self-test   builds a synthetic accepted result set and proves that removing or
              weakening each accepted property is refused by this verifier.
--verify DIR  verifies the real observer outputs written by
              observe-soldier-accessibility.sh (add --orca when the Orca phase ran).

The id rosters below are fixed here on purpose: an observer that silently drops a
gate, a causal control or an Orca step must fail verification, not shrink the claim.
"""
import argparse
import copy
import json
from pathlib import Path
import sys

SCHEMA = "fsgg.soldier-accessibility-observation/v1"
ORCA_SCHEMA = "fsgg.soldier-input-orca-observation/v1"
AXE_VERSION = "4.11.0"
GATES = [
    "panel-region-name", "panel-focusable", "panel-heading-level-2", "note-textbox-name", "status-live-polite",
    "command-buttons-present", "command-names-unique-nonempty", "command-buttons-focusable-enabled",
    "roster-alternatives-complete", "roster-names-unique", "roster-names-nonempty-descriptive",
    "roster-pressed-state-exposed", "svg-canvas-has-roster-alternative",
    "tab-reaches-every-command", "tab-reaches-every-roster-button", "ax-focus-matches-dom-focus",
    "keyboard-select-roster", "roster-pressed-matches-dom-after-selection", "keyboard-command-moves-selected",
    "roster-name-follows-state", "removal-focus-transfers-to-survivor", "removal-announced-in-live-region",
    "offscreen-removal-focus-transfers", "spawn-keeps-focus-on-control", "roster-follows-churn-world",
    "keyboard-export-full-world",
    *[f"population-{n}-roster-exposed-unique" for n in (1, 100, 250, 500, 1000)],
    "disposed-panel-absent-from-ax-tree", "disposed-focus-not-on-detached-node",
]
FINDINGS = ["roster-group-named", "disposal-focus-returns-to-entry-control"]
REFUSALS = {
    "remove-panel-accessible-name": "panel-region-name",
    "remove-panel-focusability": "panel-focusable",
    "remove-roster-button-name": "roster-names-nonempty-descriptive",
    "duplicate-roster-names": "roster-names-unique",
    "disable-command-button": "command-buttons-focusable-enabled",
    "silence-live-region": "status-live-polite",
    "hide-roster-from-ax-tree": "roster-alternatives-complete",
    "remove-pressed-state": "roster-pressed-state-exposed",
    "drop-last-roster-alternative": "roster-alternatives-complete",
    "remove-command-from-tab-order": "tab-reaches-every-command",
    "remove-roster-button-from-tab-order": "tab-reaches-every-roster-button",
    "suppress-programmatic-focus-transfer": "removal-focus-transfers-to-survivor",
}
RESOLUTIONS = {"name-the-roster-group": "roster-group-named", "restore-focus-to-entry-control-on-dispose": "disposal-focus-returns-to-entry-control"}
AXE_ROW = "axe-screening-detects-unnamed-button"
COMMANDS = [
    "Select focused soldier", "Focus next soldier", "Focus previous soldier", "Move selected soldier",
    "Change selected pose", "Change selected appearance", "Spawn soldier", "Remove selected soldier",
    "Pan to offscreen soldiers", "Revise soldier definitions", "Export full soldier world", "Dispose soldier reference",
]
ORCA_STEPS = [
    "mount-by-keyboard", "note-field-reachable-by-tab", "keyboard-selection-without-pointer",
    "keyboard-command-moves-selected", "roster-toggle-exposed-with-pressed-state", "removal-focus-reaches-survivor",
    "removal-focus-spoken-by-orca", "removal-status-exposed-as-polite-live-region", "roster-keyboard-traversal-after-transfer",
]
ORCA_MUTANTS = {
    "unnamed-roster-button": "roster-toggle-exposed-with-pressed-state",
    "no-focus-transfer": "removal-focus-reaches-survivor",
    "silent-status": "removal-status-exposed-as-polite-live-region",
}


def require(condition, message):
    if not condition:
        raise AssertionError(message)


def verify_claims(report):
    claims = report["claims"]
    require(claims["physicalInput"] is False and claims["assistiveTechnology"] is False and claims["axeIsConformanceClaim"] is False,
            "accessibility claims must stay limited to container-qualified evidence")


def verify_chromium(report):
    require(report["schema"] == SCHEMA and report["family"] == "chromium", "chromium schema/family")
    require(report["result"] == "passed" and "error" not in report, "chromium run did not pass")
    verify_claims(report)
    rows = report["observe"]["assertions"]
    gates = [row for row in rows if row["kind"] == "gate"]
    require([row["id"] for row in gates] == GATES, "gate roster differs from the accepted roster")
    require(all(row["passed"] is True for row in gates), "a gate did not pass")
    findings = {row["id"]: row for row in rows if row["kind"] == "finding"}
    require(sorted(findings) == sorted(FINDINGS), "finding roster differs")
    require(sorted(item["id"] for item in report["findings"]) == sorted(FINDINGS)
            and all(item["state"] in ("open", "resolved") for item in report["findings"]), "finding states missing")
    controls = report["controls"]
    names = {row["name"] for row in controls["rows"]}
    require(names == {AXE_ROW, *REFUSALS, *RESOLUTIONS}, "causal control roster differs")
    require(controls["total"] == len(controls["rows"]) == 1 + len(REFUSALS) + len(RESOLUTIONS), "control count")
    require(controls["refused"] == controls["total"] and controls["baselineFailures"] == [], "a causal control survived or the baseline failed")
    for row in controls["rows"]:
        require(row["refused"] is True, f"control survived: {row['name']}")
        if row["name"] in REFUSALS:
            require(row["kind"] == "refusal" and REFUSALS[row["name"]] in row["failed"], f"control refused on the wrong assertion: {row['name']}")
        elif row["name"] in RESOLUTIONS:
            require(row["kind"] == "resolution" and RESOLUTIONS[row["name"]] in row["resolved"], f"resolution control did not flip its finding: {row['name']}")
    screening = report["screening"]
    require(screening["version"] == AXE_VERSION and isinstance(screening["violations"], list), "axe screening identity")
    snapshot = report["ariaSnapshot"]
    require('region "Equipped soldier reference"' in snapshot and all(f'button "{name}"' in snapshot for name in COMMANDS[:-1]), "aria snapshot lacks panel or commands")
    return {"gates": len(gates), "findings": len(findings), "controls": f"{controls['refused']}/{controls['total']}"}


def verify_snapshot_family(report, family):
    require(report["schema"] == SCHEMA and report["family"] == family and report["result"] == "passed" and "error" not in report, f"{family} did not pass")
    verify_claims(report)
    snapshot = report["observe"]["ariaSnapshot"]
    require("Equipped soldier reference" in snapshot and all(name in snapshot for name in COMMANDS[:-1]), f"{family} aria snapshot lacks panel or commands")
    require(report["controls"] is None, f"{family} must not claim causal controls")
    return {"family": family}


def verify_orca(directory):
    base = json.loads((directory / "soldier-orca-baseline.json").read_text())
    require(base["schema"] == ORCA_SCHEMA and base["result"] == "passed" and base["mutant"] is None and base["error"] is None, "orca baseline did not pass")
    require([step["name"] for step in base["steps"]] == ORCA_STEPS and all(step["passed"] for step in base["steps"]), "orca step roster differs")
    require(base["screenReader"]["name"] == "Orca" and base["screenReader"]["speechOutputObserved"] is True
            and base["screenReader"]["audibleHardwareOutput"] == "not-observed", "orca speech evidence")
    require(base["keyboard"]["events"] == "xdotool-X11" and base["browser"]["accessibility"] == "AT-SPI2", "orca input/AT route")
    require(base["claims"] == {"physicalInput": False, "assistiveTechnologyUserStudy": False}, "orca claims")
    for mutant, expected in ORCA_MUTANTS.items():
        control = json.loads((directory / f"soldier-orca-{mutant}.json").read_text())
        require(control["schema"] == ORCA_SCHEMA and control["result"] == "refused" and control["mutant"] == mutant, f"orca control not refused: {mutant}")
        require(control["failedStep"] == expected and control["expectedRefusalStep"] == expected, f"orca control refused at the wrong step: {mutant}")
        require(expected not in [step["name"] for step in control["steps"]], f"orca control completed its refused step: {mutant}")
    return {"orcaSteps": len(ORCA_STEPS), "orcaControls": len(ORCA_MUTANTS)}


def verify_directory(directory, orca):
    directory = Path(directory)
    summary = verify_chromium(json.loads((directory / "soldier-accessibility-chromium.json").read_text()))
    for family in ("firefox", "webkit"):
        path = directory / f"soldier-accessibility-{family}.json"
        if path.exists():
            summary[family] = verify_snapshot_family(json.loads(path.read_text()), family)["family"]
    if orca:
        summary.update(verify_orca(directory))
    return summary


def synthetic():
    rows = [{"id": gate, "kind": "gate", "passed": True, "detail": {}} for gate in GATES]
    rows += [{"id": finding, "kind": "finding", "passed": False, "detail": {}} for finding in FINDINGS]
    control_rows = [{"name": AXE_ROW, "refused": True, "expect": ["axe:button-name"], "failed": ["axe:button-name"]}]
    control_rows += [{"name": name, "kind": "refusal", "expect": [gate], "failed": [gate], "refused": True} for name, gate in REFUSALS.items()]
    control_rows += [{"name": name, "kind": "resolution", "expect": [finding], "failed": [], "resolved": [finding], "refused": True} for name, finding in RESOLUTIONS.items()]
    commands = "\n".join(f'  - button "{name}"' for name in COMMANDS)
    return {
        "schema": SCHEMA, "family": "chromium", "result": "passed",
        "claims": {"physicalInput": False, "assistiveTechnology": False, "axeIsConformanceClaim": False},
        "observe": {"assertions": rows}, "findings": [{"id": f, "state": "open"} for f in FINDINGS],
        "controls": {"rows": control_rows, "baselineFailures": [], "refused": len(control_rows), "total": len(control_rows)},
        "screening": {"version": AXE_VERSION, "violations": []},
        "ariaSnapshot": '- region "Equipped soldier reference":\n' + commands,
    }


def self_test():
    base = synthetic()
    verify_chromium(copy.deepcopy(base))
    refused = 0

    def mutate(label, change):
        nonlocal refused
        report = copy.deepcopy(base)
        change(report)
        try:
            verify_chromium(report)
        except (AssertionError, KeyError, TypeError):
            refused += 1
            return
        raise SystemExit(f"verifier accepted weakened evidence: {label}")

    mutate("failed gate", lambda r: r["observe"]["assertions"][0].update(passed=False))
    mutate("dropped gate", lambda r: r["observe"]["assertions"].pop(0))
    mutate("gate relabelled as finding", lambda r: r["observe"]["assertions"][1].update(kind="finding"))
    mutate("dropped finding", lambda r: r["observe"]["assertions"].pop())
    mutate("survived control", lambda r: r["controls"]["rows"][3].update(refused=False))
    mutate("control count lowered", lambda r: (r["controls"]["rows"].pop(), r["controls"].update(total=len(r["controls"]["rows"]), refused=len(r["controls"]["rows"]))))
    mutate("control refused on wrong assertion", lambda r: r["controls"]["rows"][1].update(failed=["panel-focusable"] if r["controls"]["rows"][1]["expect"] != ["panel-focusable"] else ["panel-region-name"]))
    mutate("baseline failure", lambda r: r["controls"].update(baselineFailures=["panel-region-name"]))
    mutate("resolution not flipped", lambda r: r["controls"]["rows"][-1].update(resolved=[]))
    mutate("physical input claimed", lambda r: r["claims"].update(physicalInput=True))
    mutate("axe promoted to conformance", lambda r: r["claims"].update(axeIsConformanceClaim=True))
    mutate("axe version changed", lambda r: r["screening"].update(version="9.9.9"))
    mutate("run errored", lambda r: r.update(error="boom"))
    mutate("snapshot lost a command", lambda r: r.update(ariaSnapshot=r["ariaSnapshot"].replace('button "Move selected soldier"', "")))
    # Orca: weakened controls and baselines must be refused too.
    import tempfile
    with tempfile.TemporaryDirectory() as raw:
        directory = Path(raw)
        baseline = {"schema": ORCA_SCHEMA, "result": "passed", "mutant": None, "error": None,
                    "steps": [{"name": name, "passed": True} for name in ORCA_STEPS],
                    "screenReader": {"name": "Orca", "speechOutputObserved": True, "audibleHardwareOutput": "not-observed"},
                    "keyboard": {"events": "xdotool-X11"}, "browser": {"accessibility": "AT-SPI2"},
                    "claims": {"physicalInput": False, "assistiveTechnologyUserStudy": False}}

        def write(base_report, controls):
            (directory / "soldier-orca-baseline.json").write_text(json.dumps(base_report))
            for mutant, expected in ORCA_MUTANTS.items():
                control = controls[mutant]
                (directory / f"soldier-orca-{mutant}.json").write_text(json.dumps(control))

        def controls_ok():
            return {m: {"schema": ORCA_SCHEMA, "result": "refused", "mutant": m, "failedStep": e, "expectedRefusalStep": e,
                        "steps": [{"name": n, "passed": True} for n in ORCA_STEPS[:ORCA_STEPS.index(e)]]} for m, e in ORCA_MUTANTS.items()}
        write(baseline, controls_ok())
        verify_orca(directory)
        for label, apply in [
            ("orca baseline step dropped", lambda b, c: b["steps"].pop()),
            ("orca no speech", lambda b, c: b["screenReader"].update(speechOutputObserved=False)),
            ("orca control survived", lambda b, c: c["silent-status"].update(result="passed")),
            ("orca control wrong step", lambda b, c: c["no-focus-transfer"].update(failedStep="mount-by-keyboard")),
            ("orca control completed its step", lambda b, c: c["unnamed-roster-button"]["steps"].append({"name": "roster-toggle-exposed-with-pressed-state", "passed": True})),
        ]:
            b, c = copy.deepcopy(baseline), controls_ok()
            apply(b, c)
            write(b, c)
            try:
                verify_orca(directory)
            except (AssertionError, KeyError):
                refused += 1
                continue
            raise SystemExit(f"verifier accepted weakened Orca evidence: {label}")
    print(f"test-soldier-accessibility: self-test passed; {refused} weakened evidence sets refused; "
          f"{len(GATES)} gates, {len(FINDINGS)} findings, {1 + len(REFUSALS) + len(RESOLUTIONS)} chromium controls, {len(ORCA_MUTANTS)} orca controls")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--self-test", action="store_true")
    parser.add_argument("--verify")
    parser.add_argument("--orca", action="store_true")
    args = parser.parse_args()
    if args.self_test:
        self_test()
    elif args.verify:
        print(json.dumps(verify_directory(args.verify, args.orca), sort_keys=True))
    else:
        parser.error("choose --self-test or --verify")


if __name__ == "__main__":
    sys.exit(main())
