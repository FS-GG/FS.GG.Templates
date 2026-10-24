# Local DOM composition cases (ADR-0096)

This executes the typed current-composition plan on the delivered held source for the first time. The product under test is the exact published template and Rendering archives, fetched by typed SHA-256; the checkout supplies the harness, the typed plan and the stage script, so it is a pre-publication check of that harness, not of unpublished product source. It is ordinary
development verification under [ADR-0096](https://github.com/FS-GG/.github/blob/main/docs/adr/0096-proportionate-verification-and-unrecoverable-holds.md)
section A: a local build and test of unpublished source in a fresh private root, with no credential,
no shared or remote destination (public NuGet and Playwright downloads are read-only; every created file is under the fresh root, except the optional container runtime's image store under the real home) and no publication,
deployment, live-store, Home, VM or native-capability effect. It needs no Root runtime admission,
original clock or managed-group owner, and it changes none of them.

The held hosted original-operation route (manual workflow, managed caller, literal-false receiver) was never admitted and is
retired by the follow-up that removed it; the stage now refuses unless the local verification gate (an explicit marker, no hosted runner, no ambient credential) is declared, which the runner does. A local pass is not hosted, installed,
published, producer-custody, durable-save, assistive-technology or whole-#4818 acceptance. If hosted coverage is wanted
later, an optional job may run this same runner.

## What runs

`tests/composition/fable-game/current-composition-local.py --root <fresh dir>` runs, with a closed child
environment and at most three CPUs:

1. the typed owner (`ProviderTool`) built into a private artifacts path, then `current-composition-plan`;
2. the exact public template and Rendering archives, fetched from nuget.org and refused unless their SHA-256
   equals the typed plan;
3. an independent Fable 5.18 install, whose member closure the stage joins to the receiver's restored tool;
4. the existing `current-source-stage` (generate the Complete receiver with the external reference on and WASM off,
   locked restore, Fable build, Vite build, authority-server publish, plan-bound Playwright config);
5. per browser family, a listing that must equal the nine typed file/suite/title identities, then the run with
   workers 1 and retries 0, whose report must show nine passes and no skip, flake or retry.

Node 24.20.0, npm 11.19.0 and SDK 10.0.401 are read from `fable-reference-public.yml` (the pinned toolchain the hosted callers share) and refused if different.
Chromium, Firefox and WebKit are Playwright 1.63 stock builds. On a host without their shared libraries,
`--container IMAGE` runs only the browser phase in an Ubuntu 24.04 image from
`current-composition-local-image.sh` (base image pinned by digest; apt and Playwright dependency installs are not pinned; rebuilt for each use, not kept as a shared image), with no network, an 8 GiB memory cap and Node, .NET,
the receiver and the browsers bind-mounted (Node and .NET read-only). The runner refuses a hosted runner, a dirty checkout
and more than three CPUs, and passes only an allowlisted environment to children. `local-summary.json` binds each result to the checkout head and tree, and records `dirty` when `--allow-dirty` was used.

## Defects the first real execution exposed

The held source passed its pure controls but had never reached a real SDK or browser:

| Defect | Effect | Repair |
| --- | --- | --- |
| `dotnet new fs-gg-fable-game ... --package FS.GG.Workspace.Template` | `--package` is not an option of the shipped SDK, so the receiver could never be generated (exit 127). Its pure control used a fake `dotnet` that asserted the flag. | Removed. The custom template hive with SDK templates disabled already scopes the one installed package. The control now asserts the flag is absent. |
| The source stage exports `FsGgExternalReferenceCandidate` for the build only | The four opt-in command-outcome specs register no case in the separate Playwright process, so the listing held 5 of 9 identities and the retired managed route would have refused at its first family. | `browser_environment(plan)` derives both flags from the typed selection and is applied to every Playwright process in the managed route and the local runner. Controls assert the managed route passes them. |
| The Fable member-closure join needs an independent install | Not a defect of the retired held route (its managed caller supplied it); the local runner repeats it. | Installed by the runner from the pinned version and core hash. |

## Producer-custody readback (`current-composition-custody.py`)

The original Rendering custody manifest (361,215 bytes, SHA-256 `7dbd4329...98c9`) lives in Actions artifact 12305198394 of
run 39509314882, so reading it is a credentialed GET and stays outside ordinary verification. It was read once, with
no retry, into a fresh private root (receipt, 15,073,469-byte ZIP and the manifest) and read back independently offline.
`--custody-evidence DIR --rendering-source CHECKOUT` joins that retained read to the typed plan with no network call:
the manifest equals the typed SHA-256 and names the typed version and source commit; the producer's own unchanged
`scripts/release-custody.py verify` accepts the 19 archives and the bound release plan at the typed producer commit; and
the producer's `compare` matches each typed package to its custody archive entry for entry. The typed plan pins the signed
nuget.org bytes and the custody records the pre-signing archives, whose entries are identical apart from the feed's added `.signature.p7s`, so the
join is at payload level and the two hashes are never equated. Only a fully successful run sets the flag.
It proves what the original producer packed matches what is published for the three selected packages. It is not
installed or published-feed acceptance, and the retained read is not reproducible without the same credentialed access.

### Published-feed payload acceptance for all 19 archives

`--published-all` (with `--custody-evidence`) also reads every custody archive from the public NuGet flat container
(an unauthenticated read into the fresh root; the bytes are verified by the producer's `compare`, not by a pinned hash) and
requires, per archive, a payload-exact `compare`, exactly one feed `.signature.p7s` entry, a published hash different from the
custody row, and, for the three typed packages, the typed signed SHA-256. Observed 2026-10-24 (UTC) for Rendering 0.32.3 (feed content is live,
so this is a dated observation, not a standing guarantee):

| package | entries | custody bytes | published bytes (+signature) | published sha256 | compare |
|---|---|---|---|---|---|
| FS.GG.UI | 4 | 2211 | 15301 (+13090) | `c5c27a8a0ebb7d6ccbe33268d9315eb3f2b7b32a16e8653b4651de93a4608316` | PASS |
| FS.GG.UI.Build | 8 | 22190 | 35280 (+13090) | `f0a95c0b03a2acc2e79d7ff3f411a281c5f104c8e6d3e05ab443a9c45aa6daf4` | PASS |
| FS.GG.UI.Canvas | 8 | 37449 | 50538 (+13089) | `684d400c7657f1ad7eaed7d842b7f26c4a07f8bf6908cba6a19ab5d04ba41170` | PASS |
| FS.GG.UI.Controls | 53 | 748267 | 761356 (+13089) | `df31529336f5c5d9dad4c62a8cc97379447a3065e5dd80459b487f0a1b19549f` | PASS |
| FS.GG.UI.Controls.Elmish | 10 | 135613 | 148702 (+13089) | `40dcfb502b0a28efd1658a47536d85b5f55dd06e73135dc8f3a60025e10edbb0` | PASS |
| FS.GG.UI.DesignSystem | 12 | 52041 | 65130 (+13089) | `07743367e1ce2a06e3a402b40cd6c1e43ce5e9e23c97404f6e5e883a949b0a7d` | PASS |
| FS.GG.UI.Diagnostics | 8 | 42503 | 55592 (+13089) | `4e9acbb11fa38c3a97365491c821057e0126db4dbd9c78d71169bbc43a3a2368` | PASS |
| FS.GG.UI.Elmish | 10 | 66289 | 79378 (+13089) | `37dc910db99ef78143d9382de8d6bb54c69f443c45fdedc1e93be8c9420d86e9` | PASS |
| FS.GG.UI.KeyboardInput | 19 | 164597 | 177687 (+13090) | `99aa6564e7a3b323da8346c50894f28eca8b981cc31ac763b8f34b19fd8beb4c` | PASS |
| FS.GG.UI.Layout | 11 | 118941 | 132031 (+13090) | `321334f31eb3f9b04bdd0bbd8ac14e32f87a8dea994d2c8aca509c8045ec2a5e` | PASS |
| FS.GG.UI.Scene | 42 | 816681 | 829771 (+13090) | `9cc74f6af082089fb269d7d12c7f1e7ee7684ae3bdab51918b65e06e072a7ac8` | PASS |
| FS.GG.UI.Scene.SvgBrowser | 37 | 263275 | 276364 (+13089) | `8764ce047628f7f58d77e430b2afa0ffafb47560f7633abcf1c8dd12bf8710ad` | PASS |
| FS.GG.UI.SkiaViewer | 19 | 2808108 | 2821197 (+13089) | `639643d5db0bb3ede8a81a48411b3e5e47a1220cd5b845df75206e6d6fce401d` | PASS |
| FS.GG.UI.Symbology | 11 | 124510 | 137599 (+13089) | `76c29f5de289762876b95caddaf06d36cef84913a80b49e4b86ee7fb6c36a735` | PASS |
| FS.GG.UI.Symbology.Render | 7 | 9045 | 22135 (+13090) | `bb20a7e98cb82c800005d2e6566d83f59098eeb6885b6e8913f27d3dab55550f` | PASS |
| FS.GG.UI.Template | 2284 | 9037315 | 9050404 (+13089) | `747f33eb0242783f67b2462d8ca137b14f36bb4133bd0a3d4ca98ca8ad93dfe6` | PASS |
| FS.GG.UI.Testing | 13 | 231440 | 244529 (+13089) | `49f1a0430072af7113e5b07ad0755c3f01cc9c575a84a621c6321384290cc1a3` | PASS |
| FS.GG.UI.Themes.AntDesign | 8 | 10999 | 24089 (+13090) | `80c55b2364069908b159525e515cce72137244c74412f2b6fdbfb9a399c16e72` | PASS |
| FS.GG.UI.Themes.Default | 9 | 17678 | 30767 (+13089) | `4e792b9e72844bc157c0e9ac368295dada3e30eb9c5af063dafc6054ae4edc7f` | PASS |

Every package's published archive is its custody archive plus a feed signature of 13,089 or 13,090 bytes (the overhead in parentheses), with all
payload entries identical. This is published-feed payload agreement with the producer's packed bytes, not installed adoption.

## Example composition: what the Done-when asks, and what executes

The #4818 Done-when names six elements; the owning plan (staged Fable game adoption, Stage .3) says to complete the published
examples and generated-workspace conformance for each. Each element is exercised by the typed cases below (titles are the plan's;
27 = 9 x Chromium, Firefox, WebKit, run against the published 0.19.3 template and 0.32.3 Rendering archives). Assertions are cited
from `Browser.Tests` in the generated Complete receiver.

| Done-when element | Executing typed case(s) | Assertion that carries it |
|---|---|---|
| local save-replay | `Local save and replay example preserves synthetic state and settles detached controls` | inspect, save, inspect, replay preview, restore, new recording epoch over synthetic in-memory storage |
| external receipts and reconnect without replay | `unknown receipt survives projection and reconnect without replay`; `explicit reconciliation and rearm retain the original and use a fresh correlation`; `external authority reference fences captured snapshots and settles commands independently`; `external authority reference recovers failures and disposes owned resources terminally` | unknown receipt kept across snapshots and reconnect; reconcile/rearm uses a fresh correlation; no automatic replay |
| transformed pointer, keyboard, IME, focus | `FourD reference composes local session, normalized input, transformed hit testing and settled disposal`; `external authority reference uses production keyboard pointer editing and IME input` | the painted transformed target selects the full cell; pointer and Enter drive the same `external.increment` command (`r` drives a different one); Enter pressed in a native textbox dispatches nothing; with a synthetic `compositionstart` active on the scene, Enter dispatches nothing while plain Enter does; elements are focused to receive input (no `toBeFocused` check across an update, see below). IME evidence is synthetic composition events, not real IME text insertion |
| held release | the same two cases | `h` held then window `blur` sets `data-held` false (FourD case); in the external case `blur` plus `visibilitychange` are shown only to leave the authority revision unchanged, with no held key released by them |
| DOM islands | the same two cases | native textboxes (`Encounter note`, `External reference note`) beside the retained SVG accept text and keep Enter for themselves (the FourD note value is asserted right after `fill`; the external note is not re-read). The scene is replaced later in the FourD case, but the note is not asserted across that replacement |
| command ordering, coalescing, replacement, disposal | `FourD reference ...`; `old generation completion is inert and abandonment requires explicit rearm`; `delayed completion settles once and disposal makes retained controls inert`; the two `external authority reference` cases above | ordered `data-command-order`; burst keeps one projection request; stale-generation reply is inert; disposal settles owned counts to 0, reload remounts independently |

So every named element has an executing case, and none of the nine is a placeholder. What this does not cover, and is therefore the
final remaining composition piece: **(a) broader DOM panels** (capability map F04), meaning more than one textbox per island (select,
checkbox, radio, tab order and label association across a retained update); **(b) an explicit template-level assertion that focus and native
editing/IME text survive a retained update and a session replacement** (capability map F01 and F04; the producer's own focus and MutationObserver
cases cover it in Rendering, but none of these nine asserts `toBeFocused` or re-reads the note value across an update); and a fresh installed receiver. Adding that example changes
shipped template source, so it can only be proven against a source-built template (the runner tests published bytes) and belongs to
the next Workspace.Template release (Templates#441's 0.20.0) together with the durable reference `localSaved` journey.

## Boundaries that remain

- `actualProducerCustodyReadback` is false unless the run is given `--custody-evidence` and `--rendering-source` (the previous section).
- `localSaved` is the synthetic in-memory journey. Durable product save and the AT journey are separate obligations.
- Host-library gaps are solved by the container, not by weakening a case; a missing library fails the listing or run.
