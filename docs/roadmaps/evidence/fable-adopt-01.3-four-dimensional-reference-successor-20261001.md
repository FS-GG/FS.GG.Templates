# FABLE-ADOPT-01.3 FourD reference successor

**Status:** repaired source candidate qualified on 2026-10-01. Publication,
installed-package qualification, and FourD product adoption remain open.

This successor closes the disposal defect found by independent review of
`bb54bcedbfa4e4c81ac599bb2c6048a5a6b9d87b`. The prior candidate disposed the
shared hosts but retained live template-owned button callbacks and its mounted DOM root.
The review is `/tmp/fable-reference-four-dimensional-independent-review-20261001.md`,
SHA-256 `788152092e18890f799a46b5e7cf190ad480c63559b75f76461daf3adcccad48`.

The repaired owner removes every button callback, clears its callback inventory,
disposes `SvgInputHost`, `SvgSessionHost`, and `SvgBrowserHost`, then removes its DOM
root. Chromium retains detached references only for the test: clicking the detached
Move button leaves the accepted command order unchanged. A fresh page then mounts,
replaces, and disposes another instance with zero owned input/session resources and no
remaining reference root.

The projection and command mapping are stateless fixture adapters. They validate one
legal full-cell semantic command through Game.Core without creating a second stateful
product policy. Generation, revision, projection coalescing, and lifecycle remain the
published Rendering policy. The slice therefore requires no new Quint model.

## Exact candidate

- Branch base: `bb54bcedbfa4e4c81ac599bb2c6048a5a6b9d87b`.
- Package: `FS.GG.Workspace.Template.0.16.0.nupkg`, 799,755 bytes, SHA-256
  `f543df143466a4d72d21efeaab567a5cf84e7e1378d7d6a73dd98ee1f8f4a62e`.
- Clean generated workspace:
  `/tmp/fable-reference-four-dimensional-slice-successor-generated-20261001/product`,
  created from that package with `--bundle complete --lifecycle none`.
- Generated `FourDReference.fs` SHA-256:
  `59a625ebf887c8c9a57983582d32bf99e42459d8ecd825e216be93e6b27eb553`.
- Generated fixture SHA-256:
  `45de026198ba5e2fd951276829e096be3aea881d7bacf4f480161d7b8e059a18`.
- A bounded search found no source checkout path or Rendering/Game project reference in
  the generated workspace.

## Verification

The clean generated workspace's `build.sh` completed:

- solution build: zero warnings and zero errors;
- Domain: 18 passed; Protocol: 26 passed; Server: 20 passed;
- cross-runtime codec, reducer, model correspondence, and malformed-case checks: passed;
- Fable 5.18.0 and Vite 7.3.6 production builds: passed for Client, SVG player, and Studio;
- tactical compatibility: passed;
- Playwright 1.63.0 Chromium: 8 passed, and the legacy-only composition case skipped;
- release staging: `artifacts/releases/workspace-v1` prepared locally.

The browser JUnit record is 1,719 bytes with SHA-256
`adada806c2efde544b07048325def643644fb74f4b6fb770309403d52b788ecc`.

## Remaining boundaries

This source result does not publish template 0.16.0, qualify bytes read back from a feed,
or modify an installed workspace or the FourD product. It demonstrates a local two-cell
fixture and a fresh-page mount after disposal; it does not claim a same-page product
component remount. Presentation `Replace` does not replace the product-domain runtime.
The external authority contract needed by SC2 and BAR remains unimplemented and
unqualified.
