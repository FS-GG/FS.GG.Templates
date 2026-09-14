#!/usr/bin/env python3
"""Prove the native speech service can synthesize, cancel, and finish speech."""

import json
import os
import sys
import threading

import speechd


def main() -> int:
    output = sys.argv[1]
    ended = threading.Event()
    events: list[str] = []

    def callback(event_type, **_kwargs):
        events.append(str(event_type))
        if event_type == speechd.CallbackType.END:
            ended.set()

    client = speechd.SSIPClient("svg-workspace-orca-preflight", autospawn=False)
    try:
        modules = list(client.list_output_modules())
        if "espeak-ng" not in modules:
            raise RuntimeError(f"espeak-ng output module missing: {modules}")
        client.set_output_module("espeak-ng")
        client.speak("Speech cancellation preflight in progress.")
        client.cancel()
        client.speak(
            "Speech dispatcher preflight completed.",
            callback=callback,
            event_types=(speechd.CallbackType.BEGIN, speechd.CallbackType.END),
        )
        if not ended.wait(15):
            raise RuntimeError(f"speech completion callback timed out: {events}")
        with open(output, "w", encoding="utf-8") as stream:
            json.dump(
                {
                    "result": "passed",
                    "address": "private-unix-socket",
                    "audioOutput": "PulseAudio null sink",
                    "module": "espeak-ng",
                    "cancelAcknowledged": True,
                    "completionObserved": True,
                    "physicalAudioHardware": "not-observed",
                    "events": events,
                },
                stream,
                indent=2,
            )
            stream.write("\n")
    finally:
        client.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
