# SVG-QUAL-01.3 typed package receivers

This qualification is owned by Templates and exercises two installed-package receivers. A clean
workspace uses the current local template candidate; a retained workspace starts from the older
`d19fc1d48647edfebad4a706db64648017fead65` package and receives only the bounded SVG package and
configuration delta. Both select `lifecycle=typed-sdd` and `svgFoundation=true` explicitly while
the ordinary template defaults remain unchanged.

The receiver copies the canonical Markdown authority, explicit bindings, and model-generated trace
corpus from Rendering release commit `c654a33bb206c6f3aa0a3adb310231a0d54aec63`. Public
`FS.GG.SDD.Cli` 1.7.0 authors and inspects profile `fsgg-quint-profile/2` with backend
`quint-specification-v1` offline. Independent .NET and Fable/Node programs then replay that corpus
through `SvgRetained.update` from public `FS.GG.UI.Scene` 0.29.0. The selected SVG workspace also
Fable-compiles against public Scene and SvgBrowser 0.29.0 packages.

An implementation-only repair changes receiver diagnostics and reuses the current extracted
authority. The semantic-change case widens the bounded pointer domain, refreshes the explicit source
ranges and generated profile bindings, deterministically generates a 32-trace corpus containing a
pointer-3 witness, and replays all 384 transitions through both real reducers. Separate controls
reject a modified tool object, the wrong profile, and stale source ranges. Retained authored files,
lifecycle provenance, and installed owner guidance retain their digests; the collision case reports
the colliding path and writes no file. Installed product skills are observed as retained state and
are not presumed to refresh during package backfill.

Rendering archives are downloaded from NuGet.org and retained with their hashes and Fable interface
digests; only the exact-head Templates 0.11.0 candidate remains local. This step publishes no Templates
package and changes no template, lifecycle, or registry default. The qualification workflow uploads
the exact public producer files and local template archive it used.
