# Complete SVG workspace traceability

This is the Release-D preparation index for `SVG-WORKSPACE-01`. It binds the complete generated
workspace to the capability, milestone and journey obligations inherited by the roadmap. It records source,
installed-candidate and receiver-development results separately from effects that have not happened.

The frozen exact source candidate is Templates `2d8802d527e01afe4755ae7015a5627be88e318f`. Its native
0.14.0 candidate archive has SHA-256
`340250f942efef30702bf8c3f1f9a9096ca246c1bb4b244a2c5806ac49398380`. Its exact materialized
receiver is bound to the current functional and adoption checks by E3–E11. Templates 0.14.0 and wizard 0.11.2
remain unpublished Release-D candidates. The maintainer accepted the qualified local container edge as the
current hosting boundary; durable public hosting remains explicitly deferred to Templates #491.

## Evidence keys

| Key | Exact subject and retained evidence |
|---|---|
| E1 | [Preview-A handoff](2026-09-12-svg-scene-02-preview-a-handoff.md), [installed public Preview A](2026-09-12-svg-preview-a-installed-public-qualification.md), Rendering 0.31.0 |
| E2 | [authoring](2026-09-13-svg-authoring-candidate.md), [input](2026-09-13-svg-input-candidate.md), [runtime](2026-09-13-svg-runtime-candidate.md), [presentation](2026-09-13-svg-present-candidate.md), [replay](2026-09-13-svg-replay-candidate.md), and [installed public Preview B](2026-09-13-svg-preview-b-installed-public-qualification.md) candidate reports |
| E3 | Templates PR #485 exact source `871489891236c7a79625c56a22ee978da881870f`, merge `80f9c843737e8351c3ea04fe61a88a3a7538a7d4`; production assertions in `templates/fs-gg-fable-game/Domain.Tests/RoomTests.fs`, `Protocol.Tests/CodecTests.fs`, `Server.Tests/BootstrapEndpointTests.fs`, `Server.Tests/GameHubTests.fs`, `Browser.Tests/two-client.spec.ts`, and `tests/composition/fable-game/verify-svg-preview-c-source.sh`; exact-head native source run `34920041582` passed direct source, installed Chromium/Firefox/WebKit, and the named Chromium/Orca 46 route. The latter uses actual Insert+A Focus mode before g,h and observes speech through a real Speech Dispatcher/eSpeak NG null-sink path; physical audio remains unobserved. Earlier Firefox/Orca pre-DOM event loss remains an explicit unqualified configuration. Composition run `34920042036` passed. |
| E4 | Native archive `/tmp/svg-workspace-015-final-generic-871.JOBNpwSj/native/FS.GG.Workspace.Template.0.14.0.nupkg`, SHA-256 `364b1c500dede32a9117d1e4c90daf8d44975698c0178f305836c7fd85940b2e`; exact wizard/SDD materialization `/tmp/svg-workspace-015-final-generic-871.JOBNpwSj/readback.json`, SHA-256 `90bbeb80d874785f4ca6dc4dcc12eef7090c6239157be86cfda469694fd5e869`; independent archive comparison `/tmp/svg-workspace-015-871-native-root/readback.json`, SHA-256 `20d456d9ace92fef8c297721f66e933b95cfde867fa1e3ae3823f9e451def2ad` |
| E5 | Complete adoption production test `tests/composition/fable-game/verify-svg-complete-adoption.sh`; four-baseline qualification `/tmp/svg-workspace-015-final-adoption-192.wErcAiOD/evidence/qualification.json`, SHA-256 `20516747ed4293327868c0dde716ef9f156b4b0188d1460144232608ea320dfc`. The final archive changes only NuGet metadata and materializes identical product bytes and modes [E4]. |
| E6 | [Complete adoption/development report](2026-09-14-svg-complete-workspace-adoption.md), including four linked native PRs and exact delivery heads/merges |
| E7 | Profile-2/offline `/tmp/svg-workspace-015-offline-root/readback.json` SHA-256 `5b7da0e985baccdd8be066200e1ded794a6a8d3a81b248ae2da7b6b35f0514a2`; manifest-v1/profile-1 `/tmp/svg-workspace-015-manifest-v1-root/readback.json` SHA-256 `789fd33695ca8f40d8fb6eabb0ffbf00d3dfec253488fab2a9c0c88b08767c61`; lifecycle `/tmp/svg-workspace-015-lifecycle-root/readback.json` SHA-256 `97fe0922d5e344a13a6d73e0f45603ad37207f80c7cda7591a4a5735a850e4d6` |
| E8 | Bounded Arena correspondence `/tmp/svg-014-model-correspondence-review-b0vbc5xy/review.md`, SHA-256 `d52c66f35522532401d05d8084fb0b28daa69748364a23eedf24f1afba89ef2e`; the current source test paths in E3 execute Arena/Tactical/Arcade model projections and controlled mutants |
| E9 | Final-generic Arcade observation `/tmp/svg-workspace-015-final-generic-sustained.CeJ3dzdR/readback.json`, SHA-256 `4c0844b2d5d7d65cda2ffe27692b681fc02276b27991399d25786f8536868d06`, binds the `7e708ef` package and assets. The bounded archive/materialization comparisons through E4 show that the observed Arcade/player assets remain byte-identical; this is unchanged-subject reuse, not a new native timing run. Individual raw rows retain the probe's source-snapshot label and headless callback scope. |
| E10 | Published Templates 0.13 public-C run `34920041596`; its input observer is the exact tagged file SHA-256 `b936a2a15d6891b4d2fc3cf0e52301e2f527f39b4a8b9cb8f591cd900e282bd9`, alongside frozen old authoring/replay observers. That release retains its known pre-fix edit-focus limitation. Keymap package probe `/tmp/svg-workspace-015-keymap-reader/Program.fs` SHA-256 `b520f2ed4ce2f04f6c88448d8bc52b636803571df148b612c3ab1b907afdaff6` |
| E11 | [Final freeze](2026-09-15-svg-workspace-freeze.md): merged source/tree, native 0.14.0 archive and full lock inventory; exact-head composition `34965730947`, installed receiver `34965730400`, and browser/container `34965730316`. Local Caddy served-byte and forced-WebSocket V3 reconnect passed. Public DNS/TLS/reboot/availability remain unclaimed and deferred to Templates #491. |

## Capability matrix

| Capability | Owner subject and evidence | Disposition |
|---|---|---|
| C01 scene primitives, groups, IDs, layers | Rendering 0.31 Scene APIs [E1] | qualified producer and generated consumer |
| C02 persistent SVG, camera, selection, overlays | Rendering Scene/SvgBrowser plus current blank-authoring and mode/focus browser assertions [E1, E3] | qualified composition; screen-reader route tracked in C18 |
| C03 SVG subset | Rendering document/import/export plus current hostile/limit fixtures [E2, E3] | qualified supported subset; unsupported features refuse |
| C04 art creation/editing | blank primitive edits, history, save/reload and export [E2, E3] | qualified current composition |
| C05 assets, instances and references | catalog/instance contracts and current missing-reference refusal [E2, E3] | qualified current composition |
| C06 map editor, snapping, boundaries and properties | authoring plus schema-3 role/rule adapter [E2, E3] | qualified current composition |
| C07 commands, docking, keybindings and modals | browser keyboard dispatch/help/rebinding passes [E2, E3, E10] | qualified browser keyboard; Orca screen-reader route tracked in C18; external keymap import is outside workspace API |
| C08 runtime and sessions | Game 0.16 SessionRuntime plus local/authority adapters [E2, E3] | qualified current composition |
| C09 keyboard, pointer, touch and gamepad | held ownership, neutral/disconnect, blur and reconnect controls [E2, E3] | qualified controlled devices; no physical-device claim |
| C10 collision and spatial queries | Game 0.16 geometry/collision plus obstacle, boundary, authored geometry and hazard contacts [E2, E3] | qualified selected shapes and game adapters |
| C11 animation and effects | Rendering animation host, reduced-motion and Arcade movement [E2, E3] | qualified current composition |
| C12 browser audio | Audio 0.6 and Rendering browser adapter plus gesture cue/lifecycle [E2, E3] | qualified dispatched/browser cue; no physical audibility claim |
| C13 persistence and migration | Game/Rendering persistence plus real Studio import/storage failure and complete adopter controls [E2, E3, E5] | qualified supported saves and explicit refusals |
| C14 replay, inspection and deterministic export | Game Replay plus accepted-session seek/cancel/divergence [E2, E3, E10] | qualified current composition |
| C15 planning and experiments | Planning/Room/Replay disclosed Tactical target, alternate route, compare/cancel/commit and recorded seek [E3, E8] | qualified Templates fixture |
| C16 rules and formal evidence | SDD 1.8 profile-2 and Arena/Tactical/Arcade model correspondence/mutants [E3, E7, E8] | qualified bounded rule semantics; geometry remains outside model |
| C17 multiplayer and resync | V1/V2/V3 two-browser authored schema-3/reconnect/refusal/recording [E3] | qualified current composition |
| C18 accessibility and responsive UI | three-browser functional, 320 px/400% reflow, reduced motion, named Chromium/Orca keyboard/AT-SPI/speech route [E3] | qualified; physical audio output remains unobserved |
| C19 scale and profiling | frozen reference budgets, startup/resource gates and sustained Arcade [E3, E9] | qualified scoped workloads; physical display and unavailable metrics remain disclosed |
| C20 packaging, skills, samples, docs, deployment and upgrades | seven bundles, archive/provenance, four receiver PRs, complete adopter and accepted local Caddy edge [E4, E5, E6, E11] | qualified for the current boundary; public Release-D publication pending, durable hosting deferred to #491 |

## Milestone matrix

| Milestone | Evidence and result | Remaining effect |
|---|---|---|
| M0 inventory and decisions | public pins, ownership, supported subset, Templates fixtures, browser/performance contracts and migration census [E1, E2] | final live version census belongs to Release D |
| M1 portable contracts | public Rendering/Game/Net/Audio packages compile in clean .NET/Fable consumers; current adapters preserve explicit identities [E1, E2, E3] | none for current candidate |
| M2 SVG runtime | Preview-A installed public rendering plus current camera/selection composition [E1, E3] | none for current candidate |
| M3 vector studio | authoring candidate, Preview-B installed public and contiguous blank-document journey [E2, E3] | none for current candidate |
| M4 shared workspace | input candidate, public Preview-B and modes/history/properties/browser focus/reflow and named Orca route [E2, E3] | none for current candidate |
| M5 game runtime | fixed-step Arcade, Tactical and authority tests [E2, E3] | none for current candidate |
| M6 presentation and saves | animation/audio/persistence failure and reload [E2, E3] | physical audio hardware unobserved by design |
| M7 replay and analysis | executed Quint ITF projections and real Tactical/Arena/Arcade reducers [E2, E7, E8] | none for bounded current models |
| M8 networked game | V3 immutable content, two browsers, queue/reconnect/refusal, accepted recording and local Caddy WebSocket reconnect [E3, E11] | complete for the accepted local boundary; public hosted rerun deferred to #491 |
| M9 scalability | reference workloads, asset/startup/resource measurements and sustained Arcade [E3, E9] | unavailable browser/host counters remain explicitly unavailable where absent |
| M10 product composition | seven bundles, docs/examples, selected owner skills, package, receiver development and local static/ASP.NET deployment [E3, E4, E5, E6, E11] | complete; durable public deployment deferred to #491 |
| M11 publish and adopt | public dependencies, 0.10–0.13 adopter and four protected receiver PRs [E5, E6, E7] | Templates/wizard publication, public installed readback and default activation belong to Release D; later lifecycle-default activation retains its OperatingV2 gate |

## End-to-end journeys

| Journey | Concrete result | Status |
|---|---|---|
| 1 blank to game | blank geometry/role/rule edits through collect/win/restart, save/reload/export [E3] | passed current Chromium; native family source suite passed |
| 2 authoring equivalence | root/camera/selection/modes/history/properties and persisted scene, separate from starter regression [E2, E3] | passed |
| 3 tactical | Planning/Room/Replay compare, cancel, accepted/committed separation, alternate path and causes [E3, E8] | passed .NET/Fable/browser/model |
| 4 general game | fixed-step Arcade, held sources, touch/gamepad/blur, audio/animation, pause/loss/restart [E3, E8, E9] | passed .NET/Fable/browser/model |
| 5 network | configured V3 authority, authored content, reconnect/resync, collision and compatibility refusals [E3] | passed native Chromium/Firefox/WebKit |
| 6 content resilience | real load/import/storage effects preserve last valid content across supported refusals [E3] | passed |
| 7 replay and disclosure | accepted actions record/seek/cancel/diverge; authority sentinel is absent from excluded client surfaces [E3, E8] | passed with redacted predicates |
| 8 performance and accessibility | reflow, reduced motion, three-browser function, named Chromium/Orca route, startup/resources and sustained Arcade [E3, E9] | passed within the stated screen-reader, headless-performance, and no-physical-output scopes |
| 9 delivery | seven installed selections, provenance skills, immutable version staging/rollback logic and accepted local Caddy deployment [E3, E4, E11] | candidate passed; publication pending and public hosting deferred to #491 |
| 10 retained upgrade | public 0.10–0.13 inventory/review/apply/build/rollback with preservation/refusal [E5, E7, E10] | passed complete-adoption v1 |
| 11 generated development | clean and retained routine repair plus separate Arcade-125 model/rule PRs [E6] | passed four native PRs |

## Operation boundaries

Public producer packages are already published at Rendering 0.31, Game 0.16, Net 0.6, Audio 0.6 and SDD
1.8. The current Templates 0.14 and wizard 0.11.2 bytes are qualified candidates only. Explicit typed/profile-2
authoring is qualified in the generated receivers and changes no lifecycle default. The product provider/default,
Templates and wizard publication, deferred durable deployment, and later Typed-SDD lifecycle default are separate
operations. The later lifecycle-default operation still requires its actual OperatingV2 evidence; no epoch,
public-hosting receipt or activation is inferred here.
