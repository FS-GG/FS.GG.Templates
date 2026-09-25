# SVG workspace write-set policy (source only)

This pure F# reducer takes validated manifest path lists and an explicit fact
about whether the receiver has a configured `.claude/skills` mirror. It refuses
unsafe, noncanonical, duplicate, unordered, and cross-list alias paths. It
returns logical `Put` and `Retire` intents without reading or writing files.

It is provisional source stacked on Python path repair #500. The live Python
adopter remains authoritative. The later adapter must independently verify
manifest schema and custody, physical source/target closure, symlink chains,
baseline bytes and modes, identity substitution, conflicts, journal durability,
rollback, and special solution-name mapping before any live adoption. These
checks cannot be inferred from a logical write set.

Run `dotnet restore tests/SvgWorkspacePolicy.Tests/SvgWorkspacePolicy.Tests.fsproj --locked-mode`
and `dotnet run --project tests/SvgWorkspacePolicy.Tests/SvgWorkspacePolicy.Tests.fsproj --no-restore`.
