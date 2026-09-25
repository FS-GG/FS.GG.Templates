# SVG workspace transaction race characterization

Run `python3 tests/svg-workspace-race-characterization/run.py`. All six cases
use disposable candidate, receiver, backup and outside directories. Hooks in
the test module swap a receiver parent or edit a file immediately after the
Python adopter's classification or journal-status write. Before the bounded
repair, the four original cases all admitted the change and overwrote authored
or outside content. The current repair rechecks the workspace tree before
staging and rechecks every journaled before-state and staged/backup object
after the journal status transition, before the first receiver mutation. The
six controls now refuse these changes.

Run `python3 tests/svg-workspace-race-characterization/remaining.py` to see
the remaining gap. The disposable probes swap a parent after the last per-row
check, just before `mkstemp`, or edit a leaf before `os.replace`. They confirm
that path-based apply and rollback can still overwrite changed content. This
is a characterization of an unresolved race, not a safe-write qualification.

The package candidate and receiver here are synthetic. The served 0.14.0
archive still differs from the selected native candidate hash; producer
custody, handle-bound transaction operations, concurrent rollback safety and
installed parity remain unproved. No real workspace is touched by these tests.
