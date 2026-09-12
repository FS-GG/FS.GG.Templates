# SVG foundation public-producer packet

SVG-PREVIEW-A.3 qualifies the Templates 0.11.0 candidate against published Rendering 0.29.0. It
publishes no Templates package and changes no default.

The producer identities are `FS.GG.UI.Scene`, `FS.GG.UI.KeyboardInput`, and
`FS.GG.UI.Scene.SvgBrowser` 0.29.0 from NuGet.org. Rendering tag `v0.29.0` is fixed at
`c654a33bb206c6f3aa0a3adb310231a0d54aec63`. `FS.GG.Workspace.Template` 0.11.0 is packed once from
the exact Templates head and installed directly for candidate qualification.

Run `tests/composition/fable-game/verify-svg-preview-packet.sh <output-directory>`. The output packet
retains the downloaded public Rendering archives, the local Templates candidate, their hashes and
Fable interface digests, source identities, selection, browser result, and authority state. Generated
projects restore only from NuGet.org. The supported selection is
`dotnet new fs-gg-fable-game --svgFoundation true --lifecycle none`; the ordinary arena remains the
default.

Rendering publication and dual-feed custody readback are complete. Templates 0.11.0 publication,
installed-public receiver qualification, and any registry/default activation remain later roadmap
operations. Consumer pins are exact bracketed versions in `SvgFoundation.fsproj`.

For a retained workspace created from Templates `d19fc1d48647edfebad4a706db64648017fead65`, materialize the current
candidate with the retained workspace's name and parameters, then run
`scripts/apply-svg-foundation-preview.sh apply <materialized-current-workspace> <retained-workspace>
scripts/svg-foundation-preview-baseline.manifest <backup-directory>`. Restore that exact backup with
`scripts/apply-svg-foundation-preview.sh rollback <retained-workspace> <backup-directory>`.
The updater changes only its declared SVG foundation files, preflights all collisions before writing, and
refuses unknown content. The materialization is a staging input; it never targets the retained workspace. Keep
the old workspace or a source-control commit as rollback input. The updater does not rerun
the scaffold, alter authored domain/client files, change lifecycle identity, or backfill skills. Existing owner
guidance and skill bytes remain the installed workspace's versions until their own supported refresh route runs.
