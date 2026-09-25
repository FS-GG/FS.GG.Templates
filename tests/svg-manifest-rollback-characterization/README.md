# SVG manifest merge and rollback characterization

Run `bash tests/svg-manifest-rollback-characterization/run.sh` from this repository.
The script creates a disposable candidate, receiver and package archive. It
uses the live Python adopter to inventory, merge, apply and roll back two skill
manifests and two retired skill bodies. The F# check projects those four paths
from the selected baseline through `Policy.plan`, binds both manifest puts to
exact synthetic archive bytes through the #503 observer, and compares the
result with the Python journal paths and post-states.

Controls cover preservation of another producer's manifest row, replacement
of admitted package rows, retirement of legacy skill bodies, duplicate JSON
keys in receiver manifest rows, and rollback refusal before mutation when a
late backup object or a managed post-state has changed. All receiver writes
occur inside a temporary directory.

The fixture is synthetic. The NuGet.org-served 0.14.0 archive still differs
from the selected native candidate hash in the baseline, so this test does not
establish producer custody or installed parity. The F# observer still defers
merged-manifest output bytes. Its read-only receiver snapshot does not prove
the Python apply/rollback transaction is handle-bound or safe from path swaps.
