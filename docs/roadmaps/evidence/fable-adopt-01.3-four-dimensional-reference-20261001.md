# FABLE-ADOPT-01.3 FourD reference slice

**Status:** source candidate qualified on 2026-10-01. Publication, installed-package
qualification, and FourD product adoption remain open.

The `fable-game` template now includes a complete-bundle reference that composes the
published Rendering 0.31.0 and Game.Core 0.16.0 APIs. It projects a local four-axis
encounter to a retained SVG `Scene`, converts normalized input and a transform-aware
semantic hit target to one full-cell command, and runs that command through a
`SessionRuntime` and `SvgSessionHost`.

The reference preserves an ordinary labelled DOM input beside the scene. The browser
case verifies native editing and IME ownership, the keyboard alternative, blur release,
ordered command admission during projection coalescing, rejection of a stale generation,
session replacement, remount, and zero owned input/session resources after disposal.

## Candidate boundary

- Source base: `cfe37f35a66e3494b211197a1c84de69f08bf87e`, tree
  `006553d8a59b6fef729553ed6b3093d94471dd27`.
- Template package: `FS.GG.Workspace.Template.0.16.0.nupkg`, 798,810 bytes,
  SHA-256 `bb3f28cfc22d60d6b8aa588147a11d67afe6db5521e672108f4406a2cd1644d2`.
- Clean generated workspace: `/tmp/fable-reference-four-dimensional-final-20261001/product`,
  created from that package with `--bundle complete --lifecycle none`.
- Generated `FourDReference.fs` SHA-256:
  `0e386acde998b7f7cc90dc3ba630770f0337e50e669d077d20bd8eed08e3b543`.
- Generated fixture SHA-256:
  `45de026198ba5e2fd951276829e096be3aea881d7bacf4f480161d7b8e059a18`.
- A bounded search found no source checkout path or Rendering/Game project reference in
  the generated workspace. Restore, Fable, Vite, and Chromium therefore consumed the
  generated files and declared package graph.

## Verification

The generated workspace's unmodified `build.sh` completed with one .NET lane and one
browser lane:

- solution build: zero warnings and zero errors;
- Domain: 18 passed; Protocol: 26 passed; Server: 20 passed;
- cross-runtime codec, reducer, model correspondence, and malformed-case checks: passed;
- Fable 5.18.0 and Vite 7.3.6 production builds: passed for Client, SVG player, and Studio;
- tactical compatibility: passed;
- Playwright 1.63.0 Chromium: 8 passed, and the legacy-only composition case skipped;
- release staging: `artifacts/releases/workspace-v1` prepared locally.

The browser JUnit record is 1,720 bytes with SHA-256
`8e2c3b611f65bab714bde4dbd85d22a9a18ab02ba63db4ff7ca9645c7824d4da`.

## Remaining boundaries

This source result does not publish template 0.16.0, qualify bytes read back from a feed,
or modify an installed workspace. It does not adopt FourD gameplay, save/replay behavior,
or its Commitment and Pressure choices. The reference uses local Game.Core authority.
The external authority contract needed by SC2 and BAR remains unimplemented and
unqualified.
