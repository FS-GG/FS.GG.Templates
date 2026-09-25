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

Run `python3 tests/svg-workspace-race-characterization/remaining.py` for five
additional disposable negatives. The first two swap a receiver parent after
the writer opens it, immediately before it creates its temporary file. The
third edits an authored leaf while the temporary file is prepared. The fourth
replaces that leaf with a symlink. The fifth checks that an unsupported
platform is refused before creating a backup.
These now refuse without overwriting outside or authored bytes. The Linux
writer reads regular source files through no-follow directory handles and
uses descriptor-relative temporary creation, replacement and deletion. It
checks expected receiver bytes and mode again after preparing each temporary.

The package candidate and receiver here are synthetic. The served 0.14.0
archive still differs from the selected native candidate hash; producer
custody, concurrent compare-to-replace ownership, all preparation and journal
operations, and installed parity remain unproved. A peer can still edit a leaf
or swap a parent after the final ownership check and before `os.replace` or
`os.unlink`; those calls offer no compare-and-swap condition. No real workspace
is touched by these tests.
