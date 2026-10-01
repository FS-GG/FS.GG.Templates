# FABLE-ADOPT-01.3 hosted receiver repair

**Status:** source repair qualified on 2026-10-01. The hosted receiver rerun and
publication remain open.

The `svg-typed-receivers` job in run `36899513704` failed while building the
wizard receiver. Its root build completed the ordinary Fable/Vite client build,
then invoked an absent `SvgFoundation/build.sh`. The receiver combined two
supported public surfaces:

- `FS.GG.NewSddWorkspace` 0.11.1 emitted the current root `build.sh`;
- `FS.GG.Workspace.Template` 0.11.0 emitted Preview-A SVG source, which contains
  `SvgFoundation.fsproj` but predates the standalone SVG build entry point.

The adoption transaction already knew how to guard that call, but selected the
rewrite only when the destination root contained an older lock-loop literal.
The current wizard has the newer optional-project lock loop, so its root build
was omitted from the transaction and retained the unguarded call.

The repair selects the compatibility rewrite from the real boundary: a new SVG
adoption whose source has neither the root SVG lock nor SVG build entry point,
and whose destination root has the exact project-only guard and SVG build call.
The transformer accepts the reviewed older and current lock-loop forms, rewrites
exactly one SVG build guard, and refuses an unknown or ambiguous root shape.
The root build remains part of the same rollback transaction.

## Verification

- Downloaded public `FS.GG.Workspace.Template` 0.11.0, 390,873 bytes, SHA-256
  `41fa91ba1674a4c1140c4054d4e76cff00cd514462dcdb3d9b3e3cdfa22ba4d9`.
- Installed public `FS.GG.NewSddWorkspace` 0.11.1 and generated the exact pinned
  `fable-game`, lifecycle `none`, SVG-disabled wizard receiver.
- Generated a Preview-A SVG receiver from that exact 0.11.0 package and applied
  it to the clean wizard receiver.
- Confirmed the adopted project is present, the absent SVG build script stays
  absent, and the root build now requires both files before invoking it.
- Confirmed explicit rollback restores the original root build byte-for-byte and
  removes the added SVG tree.
- Confirmed both the earlier root lock form and current root lock form rewrite;
  an unsupported lock form refuses before workspace mutation.
- `bash -n` passed for the adopter, the hosted receiver qualification, and each
  rewritten root build.
- `git diff --check` passed.

The hosted test now asserts the exact installed wizard/source mismatch before it
runs the receiver root build. No workflow, package version, dependency, F# game
policy, or FourD reference code changes in this repair.
