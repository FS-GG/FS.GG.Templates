# Selected archive and provider source observation

`run.py` uses copied provider descriptors and disposable ZIP files. It first
shows that both current floor graders return success for the copied live
descriptors even though three `FS.GG.Workspace.Template` source pins are
`0.13.0` and the selected native candidate is `0.14.0`.

`check.py` is an offline, read-only observation over one caller-supplied archive,
baseline, and provider directory. It compares the selected SHA and package
identity, refuses ambiguous or unsafe archive members, and compares four
provider source pins and template short names. Example:

```sh
python3 tests/provider-archive-pin-custody/check.py \
  --archive /path/to/FS.GG.Workspace.Template.0.14.0.nupkg \
  --baseline scripts/svg-complete-workspace-baselines.json \
  --providers providers
```

`PIN_ROSTER_MATCH_ONLY` means only that those copied source facts agree with
the selected bytes. The CLI compares baseline bytes with the digest of the
reviewed, checked-in baseline before using its candidate. The `assess` function
still accepts a caller-supplied baseline for disposable controls; its result
cannot authenticate a production selection. A change to the checked-in
baseline needs an explicit review of the digest constant. The descriptor
reader is intentionally narrower than the full YAML grammar.
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
