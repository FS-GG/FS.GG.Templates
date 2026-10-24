"""Original outer work horizon only; no renewed per-product deadline."""
import math
import os
import time
remaining = float(os.environ['FSGG_QUALIFICATION_WORK_END_MONOTONIC']) - time.monotonic() - 60
if not math.isfinite(remaining) or remaining < 1:
    raise ValueError('original qualification work horizon exhausted')
print(min(1560, math.floor(remaining)))
