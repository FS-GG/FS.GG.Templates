# SVG Preview B installed public qualification

Date: 2026-09-13. Milestone: **SVG-PREVIEW-B.5**.

Templates release run [34763143762](https://github.com/FS-GG/FS.GG.Templates/actions/runs/34763143762)
packed `FS.GG.Workspace.Template` 0.12.0 once from merge
`7146224843419a10613b0f23c781b38bc88514b8`, gated that checksum-bound archive, published it to
GitHub Packages and nuget.org, and read both payloads back before creating the immutable GitHub release.
The annotated `fs-gg-templates/v0.12.0` tag peels to the same merge.

The installed qualification downloads Templates 0.12.0 from nuget.org into a new isolated cache and permits
only nuget.org for dependency restore. The resulting direct, SDD 1.7.0 none/default/typed-profile-2,
workspace-wizard adopter, and retained Templates 0.11.0 upgrade receivers therefore consume the public
Rendering 0.30.0, Game 0.15.0, and Audio 0.6.0 closure rather than repository-built candidates.

The matrix builds the public generated player and Studio and exercises authoring, command input, continuous
gameplay, animation, reduced motion, gesture-gated browser audio, silent timeline seek, autosave/recovery,
reload, and archive import/export in Chromium, Firefox, and WebKit. Separate Orca/AT-SPI observations cover
the authoring and input keyboard routes. Collision refusal, injected interruption, explicit rollback, retained
authored files, lifecycle state, and installed owner guidance stay transactionally protected.

The workflow retains `fsgg.svg-preview-b.public-qualification/v1` plus the individual browser, Orca, build,
adoption, and rollback observations for 90 days. This closes the installed-public boundary for C04–C13 and
M3–M6. Replay/planning/rules, multiplayer, integrated scale, complete workspace delivery, and lifecycle/default
activation remain later roadmap boundaries.
