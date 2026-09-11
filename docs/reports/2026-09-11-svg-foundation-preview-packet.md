# SVG foundation local preview packet

SVG-FOUND-01.5 prepares a local candidate and adoption rehearsal. It publishes no package, changes no
default, and does not qualify an installed public consumer.

The coherent candidate identities are `FS.GG.UI.Scene` `0.4.0-preview.1`,
`FS.GG.UI.Scene.SvgBrowser` `0.4.0-preview.1`, and `FS.GG.Workspace.Template`
`0.11.0-preview.1`. Rendering is packed from exact source
`d29f272c741d534a8269c4995c3b2da00fb97669`; the packet manifest records the exact Templates source,
archive hashes, and template payload-tree hash observed by each run. NuGet archive bytes are retained and
hashed as produced. They are not claimed deterministic across independent packs.

Run `tests/composition/fable-game/verify-svg-preview-packet.sh <output-directory>`. The output directory is
the packet: `feed/` contains the three exact candidate archives and `preview-packet.json` binds their hashes,
source identities, selection, feed, observed browser result, and authority state. The supported selection is
`dotnet new fs-gg-fable-game --svgFoundation true --lifecycle none`; the ordinary arena remains the default.

Release order is Scene, SvgBrowser, then Workspace.Template. Rendering owns the first two releases and
Templates owns the template release. The consumer pins are exact bracketed versions in
`SvgFoundation.fsproj`. Publication of both producers, publication of Templates, registry/default activation,
and public-feed installed qualification all remain separately authorized pending operations.

For a retained workspace created from Templates `d19fc1d48647edfebad4a706db64648017fead65`, materialize the current
candidate with the retained workspace's name and parameters, then run
`scripts/apply-svg-foundation-preview.sh <materialized-current-workspace> <retained-workspace>`.
The updater changes only its declared SVG foundation files, preflights all collisions before writing, and
refuses unknown content. The materialization is a staging input; it never targets the retained workspace. Keep
the old workspace or a source-control commit as rollback input. The updater does not rerun
the scaffold, alter authored domain/client files, change lifecycle identity, or backfill skills. Existing owner
guidance and skill bytes remain the installed workspace's versions until their own supported refresh route runs.
