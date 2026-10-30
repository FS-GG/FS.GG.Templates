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

## Source-built mode (`--source-built --coordination-source CLONE`)

Everything above was first run (2026-10-24) against the then-published 0.19.3 template; the published route now pins 0.20.0 (see "Published 0.20.0 bytes" below). `--source-built` instead packs Workspace.Template from the checked-out commit
(`git archive HEAD` into a copy under the private root, `dotnet pack` there with the Coordination Python fixture revision the source
names, taken from a local clone and never fetched) into a private feed, and runs the same typed cases against that package with the
same public Rendering archives and locked graph. It uses a second typed plan, `source-built-composition-plan`, which differs from the
published plan only by its template section (no archive is pinned) and scope string; the stage is `verify-source-built-composition.sh`.
The summary records the source commit and tree, whether the commit is already on the local `origin/main`, the package name, bytes and
SHA-256, and the verdict is `dom-observed-source-built-reference-only` with `origin: source-built` and `publishedAcceptance: false`.
It never claims published or installed acceptance, and it does not run the published-template identity checks (they are bound to the published plan's pinned template).
First source-built run of the unchanged nine cases: 27/27 on the 0.20.0 source package.

## Example composition: what the Done-when asks, and what executes

The #4818 Done-when names six elements; the owning plan (staged Fable game adoption, Stage .3) says to complete the published
examples and generated-workspace conformance for each. Each element is exercised by the typed cases below (titles are the plan's;
27 = 9 x Chromium, Firefox, WebKit, run against the published 0.19.3 template and 0.32.3 Rendering archives at that time; the published route now runs 33 = 11 x 3 on 0.20.0). Assertions are cited
from `Browser.Tests` in the generated Complete receiver.

| Done-when element | Executing typed case(s) | Assertion that carries it |
|---|---|---|
| local save-replay | `Local save and replay example preserves synthetic state and settles detached controls` | inspect, save, inspect, replay preview, restore, new recording epoch over synthetic in-memory storage |
| external receipts and reconnect without replay | `unknown receipt survives projection and reconnect without replay`; `explicit reconciliation and rearm retain the original and use a fresh correlation`; `external authority reference fences captured snapshots and settles commands independently`; `external authority reference recovers failures and disposes owned resources terminally` | unknown receipt kept across snapshots and reconnect; reconcile/rearm uses a fresh correlation; no automatic replay |
| transformed pointer, keyboard, IME, focus | `FourD reference composes local session, normalized input, transformed hit testing and settled disposal`; `external authority reference uses production keyboard pointer editing and IME input` | the painted transformed target selects the full cell; pointer and Enter drive the same `external.increment` command (`r` drives a different one); Enter pressed in a native textbox dispatches nothing; with a synthetic `compositionstart` active on the scene, Enter dispatches nothing while plain Enter does; elements are focused to receive input (no `toBeFocused` check across an update, see below). IME evidence is synthetic composition events, not real IME text insertion |
| held release | the same two cases | `h` held then window `blur` sets `data-held` false (FourD case); in the external case `blur` plus `visibilitychange` are shown only to leave the authority revision unchanged, with no held key released by them |
| DOM islands | the same two cases | native textboxes (`Encounter note`, `External reference note`) beside the retained SVG accept text and keep Enter for themselves (the FourD note value is asserted right after `fill`; the external note is not re-read). The scene is replaced later in the FourD case, but the note is not asserted across that replacement |
| command ordering, coalescing, replacement, disposal | `FourD reference ...`; `old generation completion is inert and abandonment requires explicit rearm`; `delayed completion settles once and disposal makes retained controls inert`; the two `external authority reference` cases above | ordered `data-command-order`; burst keeps one projection request; stale-generation reply is inert; disposal settles owned counts to 0, reload remounts independently |

So every named element has an executing case, and none of the nine is a placeholder. Two gaps remained in the published 0.19.3 archive, and both
are now closed **in the checked-out source only**, by two source-only typed cases that run in `--source-built` mode (11 cases per browser, 33 in total):

- **(a) broader DOM panels** (capability map F04): `FourD reference options panel keeps labelled native controls, tab order and state across retained updates and a session replacement`
  exercises a new `Encounter options` island (a labelled select, a checkbox and a two-radio `Camera` group beside the `Encounter note` textbox): accessible
  names and initial state, document tab order, native keyboard operation of the checkbox (Space) and radios (arrows), `selectOption` for the select (programmatic, so the select's own keyboard handling is not exercised), Enter on a native control dispatching no gameplay command, state and
  focus kept across a retained scene update and a session replacement driven without moving focus, the same DOM nodes before and after, and disposal removing the island's listeners.
- **(b) focus and native editing text survive an update and a replacement** (F01/F04): `FourD reference focus and native editing text survive a retained update and a session replacement`
  keeps a caret range, text and a synthetic composition in the note, then the select, then the reference root, across the same update and replacement, asserting `toBeFocused`, value,
  selection and node identity.

Before the change the two cases fail (commit before the implementation: 2 failed, 9 passed, Chromium). Honestly: they fail there because the island's nodes do not exist (`markIdentity` and the select lookups), not because of a behavioural difference; the note, caret and composition assertions of the second case pass by nature before the change and are shown to discriminate by the regressions below; with it 11/11 in each of Chromium, Firefox and WebKit. Four scratch regressions each fail both
cases while the nine maintained cases pass: the note replaced on session replacement, the island re-rendered on a retained update, and focus stolen on replacement or on a retained update. The reference applies a projection once per revision, so each case drives and awaits exactly one retained update (an applied-projection counter gates the assertions), then replacements.
The evidence is `source-built`, never `published`: these cases are not in the published 0.19.3 archive, so they reach users only with the next Workspace.Template release
(Templates#441's 0.20.0; published-byte result below). 0.20.0 does not contain a durable reference `localSaved` (see below). A fresh installed receiver remains separate.

Cross-lane: `scripts/svg-current-reference-adoption.json` lists the allowed canonical digests per managed path. For `two-client.spec.ts`, `FourDReference.fs` and the FourD README it now allows the published 0.19.3 digest and the source-built successor, so the "derived from the declared immutable public source" comment in `apply-svg-complete-workspace.py` is no longer exact for those three. Real adoption runs authenticate published receivers and still match the old digest; the #4816 owner should drop the old digests, or re-pin, when 0.20.0 is released; 0.20.0 is now published and its bytes for those three paths already match the successor digests, so the #4816 successor scope can drop the old ones.

## Published 0.20.0 bytes (observed 2026-10-25)

`FS.GG.Workspace.Template` 0.20.0 is published (Templates#441). The typed `current-composition-plan` now pins that archive: the signed
nuget.org SHA-256 `e12b36d2d087d0f788894fdec9ba3b3ed1406c1e7237ebee40602c2f7c23355c` (1,114,933 bytes, 590 entries = the 589 accepted entries
plus the repository `.signature.p7s`), source commit `1b9b1ca92556eb1acd0e4d1c9cb851a8c7906f86` and descriptor
`providers/fable-game.providers.yml` SHA-256 `11c7e338b1fa2c29e6d8c2277758f59aeadc9144b1b568204596a0c4152833ee`. The plan selects eleven cases
(the nine maintained plus the options-panel and focus/native-editing survival cases), so the published route runs 33 cases (11 x Chromium, Firefox, WebKit).
The source-built plan is unchanged and selects the same eleven cases; only the published plan's template identity and scope changed.

The generated-receiver conformance check of the composition route is now `current-composition-receiver-check`, bound to the plan's own template
identity. It replaces `current-d5-receiver-check` in this route because that check is pinned to the D5 lane's frozen 0.19.3 archive, which the
D5 lane still owns and which is not edited here.

Run (published route, ADR-0096 ordinary verification: one fresh private root, closed environment, 3 CPUs, host-libraries container, no credential, nuget.org read credential-free):
`current-composition-local.py --root <fresh> --cpus 3 --container localhost/fsgg-pw-host-libs:1.63 --custody-evidence <retained read> --rendering-source <FS.GG.Rendering> --published-all`
at checkout head `c3614f27` (tree `1bbdeae9`, clean):

| check | result |
|---|---|
| template archive downloaded from nuget.org | SHA-256 equals the typed pin (`e12b36d2...`); `published-tool-check`: 590 entries, id/version/source commit as typed |
| Chromium / Firefox / WebKit | 11 / 11 / 11 passed, 0 skipped, 0 flaky, 0 retries (33/33); listing equals the eleven typed identities |
| `actualProducerCustodyReadback` | true (retained original producer read; binder accepts 19 archives; Scene, KeyboardInput, SvgBrowser payload-exact) |
| `--published-all` | 19/19 Rendering 0.32.3 archives payload-exact against the public feed, one feed signature each |

The run also exercised Playwright 1.63.0 stock browsers (downloaded into the private root) in the existing image
(`20a02130014f`). Verdict `dom-observed-local-reference-only` with `origin: published`. This is ADR-0096 local verification: `publishedAcceptance` and `hostedRuntimeAdmission` stay false (no protected or hosted gate is claimed), as do the installed, durable-save, AT and whole-#4818 flags.

### Durable reference `localSaved` is not in 0.20.0

The published 0.20.0 archive's `FourDReference.fs` (identical to the source at `1b9b1ca9`) still holds `localSaved` as
`let mutable localSaved: SessionSnapshot<LocalSaveReplayExample.Payload> option` under `#if LOCAL_SAVE_REPLAY_EXAMPLE`; the buttons save "in memory"
and the FourD README states that no durable storage, byte serializer or clock is provided. No 0.20.0 case can exercise a durable reference save,
so none is added. The only IndexedDB persistence in the template is the Studio generated-scene journey, which is a different journey and is already
covered by its own cases; it is not the reference `localSaved`. The reference-level durable `localSaved` journey is therefore **absent from 0.20.0 and owed to the next
Workspace.Template release**, per Root's re-binding on FS-GG/.github#4818 (2026-10-25: a reference-level durable `localSaved` becomes a source obligation for the next Workspace.Template release), because 0.20.0 shipped without any template source for it, and a published-byte case cannot precede the
published source. Product-level durable save is FourD's under FS-GG/.github#4819.

## Published 0.20.1 bytes (observed 2026-10-30)

`FS.GG.Workspace.Template` 0.20.1 is published (Templates#815 accepted its payload `7c48b222`; FS-GG/.github#3010 closed on its installed provider journeys). The typed
`current-composition-plan` now pins that archive: signed nuget.org SHA-256 `e84d5188b510937fb54218faf4cabbad93a801b58f24fd6e5bfbeba632c44a6a`
(1,215,582 bytes, 621 entries = the 620 payload entries plus the repository signature), repository commit `df896c4bd587b5ef8dd990bc39c0dcb661bf2193` read from the
archive's nuspec, and descriptor `providers/fable-game.providers.yml` SHA-256 `66dd8f066a5fd958e45b1681b934b44b68258efa4cecb2d72aa553839ee4b4a9` (the file at that commit; the
0.20.0 pin used the same derivation). The plan selects thirteen cases: the eleven of 0.20.0 plus the two durable synthetic snapshot cases, so the route runs 39 (13 x Chromium, Firefox, WebKit).
The source-built plan now selects the same thirteen. The plan's Rendering pin was already 0.32.4, which the 0.20.0 archive's lock did not match; the 0.20.1 lock does.

Run (ADR-0096 ordinary verification, fdev KVM guest, glibc 2.44, user-scope `CPUQuota=200%` `MemoryMax=4G`, one fresh private root, closed environment, 2 CPUs, host-libraries container image `789c96b69ae3`
rebuilt from the digest-pinned Ubuntu base, no credential, nuget.org read credential-free, Node 24.20.0 from a SHA-256-verified private distribution) at checkout head `ed31faec` (tree `d0f7c389`, clean):

| check | result |
|---|---|
| template archive downloaded from nuget.org | SHA-256 equals the typed pin |
| Chromium / Firefox / WebKit | 13 / 13 / 13 passed, 0 skipped, 0 flaky, 0 retries (39/39); listing equals the thirteen typed identities |
| wall time | source stage 128 s; browsers 12 s, 20 s, 19 s |

Verdict `dom-observed-local-reference-only` with `origin: published`. `actualProducerCustodyReadback` is **false** in this run: the retained Rendering 0.32.3 custody read of the earlier runs is not present on this host and the 0.32.4 custody
manifest was not read, so no custody claim is made. `publishedAcceptance`, `hostedRuntimeAdmission`, installed, product-save, AT, IME and whole-#4818 flags stay false. The durable reference `localSaved` journey
(IndexedDB through `BrowserPersistenceHost`, lossless uint64 order, typed refusals, injected quota failure, late load and disposal) therefore has published-byte evidence on 0.20.1.

## Source-only release and island cases (after 0.20.1)

The Qualification section of the staged-adoption plan names pointer coordinates under SVG transforms, blur/visibility transitions, editable focus and repeated mount/dispose. Three
more typed cases close what the matrix above states as limits. Each runs only in `--source-built` mode (16 cases per browser, 48 in total); the published plan does not select them until
the next Workspace.Template release carries them. They change only the template's `two-client.spec.ts`; no reference runtime source changed, and none of them exercises a real input method.

| case | what it adds | causal controls (scratch regressions, each fails the case in Chromium, Firefox and WebKit; the other maintained cases are unaffected by construction) |
| --- | --- | --- |
| `FourD reference pointer hit testing inverts a wheel zoom and a narrow viewport and still selects the painted target` | real wheel events zoom the retained camera out about the origin cell; the destination's paint moves and shrinks; a click at its pre-zoom point does not select it (so a hit test that ignored the camera would), the painted centres of both cells select them, only the destination admits a command; a retained scene update keeps the zoomed camera; the same after a 320 px viewport | wheel zoom factor made inert (`1.0000001`): fails at the camera-change assertion. The camera-survives-update assertion has **no** reference-level causal control: a reference whose scene camera follows the revision still passes, because SvgBrowser keeps the user camera on `ReplaceScene`; it guards that Rendering behaviour only |
| `FourD reference held input is released by hidden visibility, focus leaving the reference and disposal` | a `visibilitychange` while visible keeps the hold; a hidden document releases it and the late `keyup` does not hold again; focus moving to the reference's own note keeps the hold, focus leaving releases; disposal while held releases and leaves the disposed element neutral | held release ignored in the reference's handler: fails; reference disposal skips the input host: fails |
| `external authority reference note, caret and focus survive snapshot application, reconnect and authority replacement` | the external reference's native note keeps focus, text, selection and node identity across two snapshots, disconnect/reconnect and an authority replacement; an active composition makes the same invocation inert; Enter in the composing note admits nothing; after disposal the note is still editable and admits nothing | the note re-parented on every `describe`: fails |

Honest limits: the hidden-visibility case overrides `document.hidden` and dispatches `visibilitychange` (headless pages are always visible); the composition is a synthetic `compositionstart`/`compositionend`; the camera
is changed by wheel only (the reference has no pan control).

## Boundaries that remain

- `actualProducerCustodyReadback` is false unless the run is given `--custody-evidence` and `--rendering-source` (the previous section).
- `localSaved` is the synthetic in-memory journey in 0.20.0 and 0.19.3; 0.20.1 carries the durable synthetic browser-storage journey (above). Product save is #4819; the AT journey is #4817.
- Host-library gaps are solved by the container, not by weakening a case; a missing library fails the listing or run.
