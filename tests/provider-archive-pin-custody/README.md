# Selected archive and provider source observation

`run.py` uses copied provider descriptors and disposable ZIP files. It first
shows that both current floor graders return success for the copied live
descriptors even though three `FS.GG.Workspace.Template` source pins are
`0.13.0` and the selected native candidate is `0.14.0`.

`check.py` is an offline, read-only observation over one caller-supplied archive,
baseline, and provider directory. It compares the selected SHA and package
identity, requires the selected source head to equal the package nuspec's
single repository commit, streams every regular ZIP member within explicit
archive and expansion bounds, refuses ambiguous or unsafe archive members,
including ZIP names shortened at an embedded NUL by the Python parser,
requires the current reviewed candidate's Unix-created `0644` member modes,
and compares four provider source pins and template short names. Example:

```sh
python3 tests/provider-archive-pin-custody/check.py \
  --archive /path/to/FS.GG.Workspace.Template.0.14.0.nupkg \
  --baseline scripts/svg-complete-workspace-baselines.json \
  --providers providers
```

The observer also accounts for contiguous local member spans, central-directory
records, and the exact end record. It refuses leading/trailing overlays, gaps,
and data-descriptor form pending separate byte-bound proof. This is a physical
boundary check, not complete ZIP metadata parity or producer authentication.

`PIN_ROSTER_MATCH_ONLY` means only that those copied source facts agree with
the selected bytes. The CLI compares baseline bytes with the digest of the
reviewed, checked-in baseline before using its candidate. It also requires
the exact whole-file digests of the five reviewed provider descriptors, so a
parameter-only source edit is visible even though pin/roster fields are the
only fields compared with the archive. The `assess` function still accepts a
caller-supplied baseline and source digest map for disposable controls; an
unqualified fixture result cannot authenticate a production selection. A
change to the checked-in baseline or descriptor set needs an explicit review
of the corresponding digest constant. The descriptor reader is intentionally
narrower than the full YAML grammar.
The observer requires the reviewed five-descriptor inventory and reads each
descriptor as a regular file relative to an opened directory with no-follow
flags. It holds all five descriptors open through bounded reads, then checks
their file identities and change metadata against both open handles and paths.
A new descriptor, linked descriptor, changed descriptor, or rendering descriptor
that selects the workspace package receives `NO_VERDICT` pending owner review.
This detects the tested in-place and rename-and-replace swaps; it is not a
race-free snapshot against every concurrent or privileged mutation.
No result authenticates producer custody, served feed bytes, installation,
template selection constraints, workspace output, transaction rollback, or a
receiver decision. A duplicate short name, including one that a template host
may disambiguate with constraints, yields `NO_VERDICT` here.
