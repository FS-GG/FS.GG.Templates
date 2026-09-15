#!/usr/bin/env python3
"""Run the installed Orca entry point with retained periodic Python stacks."""

import faulthandler
import runpy
import sys

faulthandler.enable()
faulthandler.dump_traceback_later(45, repeat=True)
sys.argv[0] = "/usr/bin/orca"
runpy.run_path("/usr/bin/orca", run_name="__main__")
