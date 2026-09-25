# SVG workspace write-set policy (source only)

This pure F# reducer takes validated manifest path lists and an explicit
observation of the receiver's `.claude/skills` mirror. It refuses symlinked or
non-directory mirrors, unsafe/noncanonical paths, duplicate and ancestor paths,
and lists unordered by Python's Unicode codepoint order. It returns logical
`Put` and `Retire` intents without reading or writing files. The mirror state is
a caller-supplied fact; this reducer cannot observe a real filesystem link.

It is provisional source stacked on Python path repair #500. The live Python
adopter remains authoritative. The later adapter must independently verify
manifest schema and custody, physical source/target closure, symlink chains,
baseline bytes and modes, identity substitution, conflicts, journal durability,
rollback, and special solution-name mapping before any live adoption. These
checks cannot be inferred from a logical write set.

The current Python `json.loads` path accepts duplicate raw manifest keys by
keeping the last occurrence. Typed path lists cannot reveal those duplicates;
the manifest-loading adapter must settle and prove that boundary separately.
The provider YAML source and composition pilots (#497/#499) are separate inputs
and do not validate this JSON manifest.

Run `dotnet restore tests/SvgWorkspacePolicy.Tests/SvgWorkspacePolicy.Tests.fsproj --locked-mode`
and `dotnet run --project tests/SvgWorkspacePolicy.Tests/SvgWorkspacePolicy.Tests.fsproj --no-restore`.
