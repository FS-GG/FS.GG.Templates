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
the caller-supplied selected bytes. A caller can supply a forged baseline, and
the descriptor reader is intentionally narrower than the full YAML grammar.
No result authenticates producer custody, served feed bytes, installation,
template selection constraints, workspace output, transaction rollback, or a
receiver decision. A duplicate short name, including one that a template host
may disambiguate with constraints, yields `NO_VERDICT` here.
