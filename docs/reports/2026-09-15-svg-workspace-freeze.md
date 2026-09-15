# SVG complete workspace freeze

This report closes `SVG-WORKSPACE-01.6` and hands the qualified composition to `SVG-RELEASE-D`.
It freezes product bytes, generated locks, installed behavior and the hosting boundary separately so a
later operation cannot inherit a claim that was not observed.

## Candidate identity

| Subject | Frozen identity |
|---|---|
| Merged Templates source | `2d8802d527e01afe4755ae7015a5627be88e318f` |
| Git tree | `058b964b75f1b8daa672ee21b4f33155bcff2ed0` |
| `templates/fs-gg-fable-game` tree | `90eefebdeb982c3270b2bacde462d0f11c11e42f` |
| Exact qualified PR head | `5b9b73412cce55bf6c0abc5b51909cc7690f32b5` (tree-equal to the merge) |
| Template version | `FS.GG.Workspace.Template` 0.14.0 |
| Native candidate workflow | run `34965730359`, artifact `10395590118`, server digest `sha256:f6824ce26a37887657e005875a8cb596c6833ec979d48950b046eeccc53e4591` |
| Native candidate archive | `FS.GG.Workspace.Template.0.14.0.nupkg`, SHA-256 `340250f942efef30702bf8c3f1f9a9096ca246c1bb4b244a2c5806ac49398380` |
| Native checksum file | `SHA256SUMS`, SHA-256 `b811e1c848c8ec36caa4236f44df75c0702ed917cccbd5ed857fb8ff856638d1` |
| Wizard candidate | `FS.GG.NewSddWorkspace` 0.11.2, selection source merged by `.github` PR #3476 as `3935b6bb81dc242635bbb8b400537d07de3b954b` |

The native archive is retained by GitHub Actions and is a candidate, not a public-feed readback. Its
source head and the squash merge have the same Git tree. The distinct package digest recorded by source
qualification is a separately packed archive; no byte-identity claim is made between independently created
NuGet ZIP containers.

## Exact-head qualification

| Boundary | Evidence | Result |
|---|---|---|
| Complete composition | run `34965730947`, head `5b9b73412cce55bf6c0abc5b51909cc7690f32b5` | passed |
| Installed typed SDD receiver | run `34965730400`, same head | passed |
| Browser, accessibility and container edge | run `34965730316`, artifact `10394823827`, server digest `sha256:06979b90f20326786a38b072b53aace1100f5195a4fa6abaf0e0123c389937ce` | passed |
| Source qualification receipt | `qualification.json`, SHA-256 `9a483cbe5ec2baaecb17b9da2fbfd6c0bec7bda0419bee7d3a0335e1fb050ec3` | passed |
| Container edge log | `container-edge.log`, SHA-256 `d0a8e87c2d7c02ef0adbcfd0c63fc43157322865a1af6f9d86755a980cc4e975` | passed |

The edge run built the digest-pinned, non-root ASP.NET image and digest-pinned Caddy image through the
Docker-compatible Compose definition. It compared served `VERSION`, `SHA256SUMS`, Player and Studio bytes,
used `/api` to create two sessions, forced V3 SignalR WebSockets through `/hub`, disconnected one client and
verified reconnect/resynchronization. Chromium, Firefox, WebKit and the named Chromium/Orca route passed in
the same exact-head workflow. The [complete traceability index](2026-09-15-svg-workspace-traceability.md)
maps C01–C20, M0–M11 and journeys 1–11 to their owner and executable evidence.

## Generated lock inventory

All hashes are SHA-256 at the frozen source tree.

| Generated lock | SHA-256 |
|---|---|
| `Browser.Tests/package-lock.json` | `d2fddaaefd9ee75fe7ecb3c414ce22f8ef7a0bf4d57e971e2b542a5a80f2747a` |
| `Client/package-lock.json` | `b5c9251a98c891843457951eb7e787fe5af99345b320de707b3deb7cae1fcdd9` |
| `Client/packages.lock.json` | `6dd72161324968d4723f584118b1fe515faeae228511fcae80458e9f05fb3ffd` |
| `Domain/packages.lock.json` | `b11aa789f479a1226ca6b1098e0904eed15e0b46a361760b93ffb992e617d890` |
| `Domain.Tests/packages.lock.json` | `c94a1e343c6de00631260e887aa642f4f0e71c17d5fddd1ef3e1a96f8710ba75` |
| `Protocol/packages.lock.json` | `0e5c6de5749b5c52b4e18c1027c1a7e7387e8c925e7a7c4beedbff56e05a36a0` |
| `Protocol.Tests/packages.lock.json` | `1fb800244ce2d57a162bb2a46ed95c62b66bb58ee7291810694fef79fa0f82a7` |
| `Protocol.Tests/cross-runtime/CodecProbe.Fable/packages.lock.json` | `2fd8a72258eb1934aca6de54ce7d7184bc7ccf182a3fcd5a2133f55102f4e21a` |
| `Protocol.Tests/cross-runtime/CodecProbe.Net/packages.lock.json` | `7f1973ed75259d12206f6cf436171e5ea2785a5a17149c82f2dbf4ec82763cc1` |
| `Server/packages.lock.json` | `15f0b76baad69ec0c5966006bbddad75419047329d1a66b54a06b8ac7ed9bb21` |
| `Server.Tests/packages.lock.json` | `2704b23dfd50ab3f14a071389b1062395a787216ce6ae791141126c267bc4d0f` |
| `SvgFoundation/packages.lock.json` | `fd75c7b9cbdb8e7c878c2a5db57cb4d76c4567e33239733a3270294910606e2a` |
| `SvgFoundation/Studio/packages.lock.json` | `cf94a008e1e4e26f9a8106e57d1b5307092543eec8ae9531f8d2938320d4b79e` |
| `SvgFoundation/Examples/Tactical/packages.lock.json` | `aed8b23a35a96416d19fef19ac3478fd69fd4727dc97a323015cae52076c93f5` |

## Acceptance and exclusions

On 2026-09-15 the maintainer accepted the qualified local container deployment as the current `.4`
hosting boundary. Therefore `.4` and `.6` close without asserting public DNS, trusted TLS, host reboot
recovery, public availability or a real external version rollback. Those stronger effects remain explicit,
uncompleted work in [SVG-HOSTING-02](https://github.com/FS-GG/FS.GG.Templates/issues/491). The production
scripts and protected environment are prepared, but their existence is not operational evidence.

The frozen candidate is eligible for compatible Templates/wizard publication and SVG product-default
activation under existing lifecycle choices. Explicit typed/profile-2 behavior is qualified. The later
workspace lifecycle-default flip is not eligible: it still requires its actual common-base consumer evidence
and `OperatingV2`. No epoch receipt, public hosting receipt or lifecycle activation is inferred by this freeze.
