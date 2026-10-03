"""Receiver checks use the installed producer CLI, never interpret its store layout."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re
import subprocess

ROOT = Path(__file__).resolve().parents[2]
FAMILIES = {"console", "web", "fable-bindings", "python", "fable-game", "rendering"}
LANES = ("none", "sdd", "typed-sdd", "spec-kit")


def inventory(root: Path = ROOT) -> list[dict]:
    rows = []
    for path in sorted((root / "providers").glob("*.providers.yml")):
        text = path.read_text()
        def field(pattern):
            match = re.search(pattern, text, re.MULTILINE)
            if not match:
                raise ValueError(f"unreadable descriptor: {path}: {pattern}")
            return match.group(1)
        name = field(r"^  - name:\s*(\S+)")
        template = field(r"^    templateId:\s*(\S+)")
        default = field(r"^      - key: lifecycle\s*\n\s+required: false\s*\n\s+default: (\S+)")
        expected = "typed-sdd" if name == "fable-game" else "sdd"
        if default != expected:
            raise ValueError(f"lifecycle default changed: {name}")
        config = root / "templates" / template / ".template.config/template.json"
        if config.exists():
            symbols = json.loads(config.read_text())["symbols"]
            lane = symbols["lifecycle"]
            if lane["defaultValue"] != expected or tuple(x["choice"] for x in lane["choices"]) != LANES:
                raise ValueError(f"template lifecycle changed: {name}")
            if any((config.parents[1] / p).exists() for p in (".fsgg", "work", "readiness")):
                raise ValueError(f"template owns orchestrator payload: {name}")
        elif name != "rendering":
            raise ValueError(f"owned template missing: {name}")
        rows.append({"provider": name, "template": template,
                     "source": field(r"^    source:\s*(\S+)"), "default": default,
                     "descriptor": str(path.relative_to(root)), "external": not config.exists()})
    if {r["provider"] for r in rows} != FAMILIES or len(rows) != len(FAMILIES):
        raise ValueError("supported provider family inventory changed")
    legacy = json.loads((root / "pack/fs-gg-fable-game-legacy/.template.config/template.json").read_text())
    if legacy["symbols"]["lifecycle"]["defaultValue"] != "sdd":
        raise ValueError("raw legacy Fable game default changed")
    return rows


def call(command: list[str], *args: str, expect_success=True):
    result = subprocess.run(command + list(args), capture_output=True, text=True)
    if (result.returncode == 0) != expect_success:
        raise AssertionError(f"unexpected producer outcome for {args}: {result.stdout}\n{result.stderr}")
    if not expect_success:
        return result
    return json.loads(result.stdout) if result.stdout.strip() else None


def snapshot(root: Path, exclude_knowledge=False):
    return {p.relative_to(root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in root.rglob("*") if p.is_file() and ".git" not in p.relative_to(root).parts
            and not (exclude_knowledge and p.relative_to(root).as_posix().startswith(".fsgg/knowledge/"))}

