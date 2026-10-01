#!/usr/bin/env python3
"""Exact inert producer pin for portable workspace receiver preparation."""

from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
PIN = ROOT / "eng/portable-workspace/producer-pin.json"


def main() -> None:
    value = json.loads(PIN.read_text(encoding="utf-8"))
    assert set(value) == {
        "schema", "producer", "package", "packageManifest", "portableContract",
        "qualifiedImage", "releaseManifest", "adoption",
    }
    assert value["schema"] == "fsgg.portable-workspace-producer-pin/1"
    assert value["producer"] == {
        "repository": "FS-GG/FS.GG.Coordination",
        "tag": "v0.2.0",
        "sourceCommit": "d25b9eaec991c94593adcecda6869d07dabdfb43",
        "sourceTree": "169b7df260ee6668b8b28d43857183ad669b0e12",
        "releaseId": 400643766,
        "verifiedRunId": 36813849644,
    }
    assert value["package"] == {
        "id": "FS.GG.Coordination.Cli",
        "version": "0.2.0",
        "asset": "FS.GG.Coordination.Cli.0.2.0.nupkg",
        "sha256": "8ee67f83cecb3898eee12fd69f54cad0e3d1e232b3c88c18c434e3969019ab13",
    }
    assert value["packageManifest"] == {
        "asset": "callable-cli-release-manifest.json",
        "sha256": "88d1dcf0922328a7c31161a67c505ec7ec926778a07cd1704242e56758d86ee4",
    }
    assert value["portableContract"] == {
        "asset": "portable-workspace-v1-0.2.0.zip",
        "sha256": "c4ccc949ba02d67eba27302dfdffa258ecd4a55b628315fff82c26b2e4566abc",
    }
    assert value["qualifiedImage"] == {
        "asset": "portable-workspace-linux-amd64-0.2.0.oci.tar",
        "sha256": "24dfd6fbf5e5d86b664963e5bcf896f2bbaba8803fdd9125c343a9389d6295b6",
    }
    assert value["releaseManifest"] == {
        "asset": "portable-workspace-release-manifest.json",
        "sha256": "bd08411e277c77f0f607716c510cc487ac438e4aeeff766b6b76e8a63e49d390",
    }
    assert value["adoption"] == {
        "enabled": False,
        "installedQualificationRequired": True,
    }

if __name__ == "__main__":
    main()
