#!/usr/bin/env python3
"""Run the installed Orca entry point with a line-buffered debug file.

/usr/bin/orca opens its --debug-file with the default block buffering, so the
tail of the log (the last speech before the observer reads it) can stay in
Orca's buffer and look absent. A retained run showed exactly that: Orca spoke the
removal live-region message 51 ms after the focus speech, but the observer's
bounded read did not see it. This launcher opens that one file line-buffered and
otherwise behaves like orca-faulthandler.py (retained periodic Python stacks).
"""

import builtins
import faulthandler
import runpy
import sys

debug_files = {arg.split("=", 1)[1] for arg in sys.argv[1:] if arg.startswith("--debug-file=")}
_open = builtins.open


def _line_buffered_open(file, mode="r", buffering=-1, *args, **kwargs):
    if mode == "w" and isinstance(file, str) and file in debug_files:
        buffering = 1
    return _open(file, mode, buffering, *args, **kwargs)


builtins.open = _line_buffered_open
faulthandler.enable()
faulthandler.dump_traceback_later(45, repeat=True)
sys.argv[0] = "/usr/bin/orca"
runpy.run_path("/usr/bin/orca", run_name="__main__")
