# Archive-backed workspace characterization

`run.sh` builds a disposable `.nupkg` ZIP with explicit Unix modes, extracts a
candidate, and drives the live Python inventory, apply, and rollback logic
against a temporary receiver. It checks the journal write set, exact binary and
BOM/CRLF bytes, file modes, author-owned preservation, symlink and nonregular
refusal, and automatic rollback after an injected mid-apply failure. A separate
F# executable compares #501 logical intents with the Python journal rows.

This is source characterization only. The synthetic archive is not an accepted
package or custody proof, and the test does not authorize an F# physical-file
adapter or a receiver flip. The later adapter needs a signed/selected archive
contract, safe extraction and path binding, actual file type and symlink facts,
byte and mode baselines, a durable journal, and complete rollback qualification.
