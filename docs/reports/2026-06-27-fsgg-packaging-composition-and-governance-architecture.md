---
title: "FS-GG packaging, composition & governance architecture"
date: 2026-06-27
status: Draft for decision
author: FS-GG (analysis)
affects: FS.GG.Rendering, FS.GG.SDD, FS.GG.Governance, FS.GG.Templates, FS-GG/.github
supersedes-intent: the vendored monolith (`fs-gg-fullstack`) as the primary composition path
---

# FS-GG packaging, composition & governance architecture

> **One-line recommendation:** Stop vendoring. Make composition a **CLI-orchestrated**
> act owned by `fsgg-sdd` (no copied payload), push the **lifecycle choice** down into
> the `fs-gg-ui` template so a governed product never ships Spec Kit, shrink
> `FS.GG.Templates` to a thin **registry + governance-overlay** layer, and pin the
> framework with **lockstep producer versions + Central Package Management + a committed
> lockfile + NU1603-as-error** downstream.

This is an F#/.NET-specific design note. It assumes the four-repo split is fixed and asks
the narrower question the project can still get right pre-release: **who should ship what,
and how do the pieces fit together** — given (a) the decision to make the generated
product **governance-driven rather than Spec-Kit-driven**, and (b) the
`FsSkiaUiVersion=0.1.0-preview.1` staleness incident that broke `fs-gg-fullstack`.

---

## 1. Context

There are no releases and no customers yet. That is the cheap moment to fix structural
choices that would otherwise calcify into compatibility obligations.

Four deliberately-decoupled repos:

| Repo | Role today |
|---|---|
| **FS.GG.Rendering** | The `FS.GG.UI.*` F#/Skia/Elmish framework (~16 NuGet packages) **and** the `fs-gg-ui` `dotnet new` template that scaffolds a runnable product. |
| **FS.GG.SDD** | The `fsgg-sdd` .NET global tool: lifecycle (`charter → … → ship`), the `.fsgg/` skeleton, and the **`scaffold-provider`** contract. |
| **FS.GG.Governance** | The `fsgg-governance` .NET tool: a pure inference kernel + typed gates over the `.fsgg/{policy,capabilities,tooling}.yml` schemas. Optional, advisory-by-default. |
| **FS.GG.Templates** | The downstream composition: today a **vendored monolith** (`fs-gg-fullstack`) that copies the entire `fs-gg-ui` payload, plus a `fs-gg-governance` overlay, a provider descriptor, and sync scripts. |

Two facts from the codebase make this decision concrete:

1. **The `fs-gg-ui` template emits Spec Kit unconditionally.** In
   `FS.GG.Rendering/.template.config/template.json`, the sources that emit `.specify/`,
   the constitution (`.specify/memory/constitution.md`, shipped from
   `.template.config/generated/`), `.agents/`, and the generated `CLAUDE.md`/`AGENTS.md`
   guidance have **no `condition`**. The only switches are `profile` (which product
   skills), `designSystem` (an additive Ant overlay), `feedback`, and `skipGitInit`.
   **There is no parameter that turns the Spec Kit lifecycle off.** A governance-only
   product is therefore impossible without a template change upstream.

2. **SDD already owns a non-vendoring composition path.** `fsgg-sdd scaffold --provider
   rendering` writes the SDD skeleton and then invokes the provider's template via a
   `dotnet new install … && dotnet new <templateId> -o … -p:<k>=<v>` wrapper, recording
   every produced file in `.fsgg/scaffold-provenance.json` as `owner: generatedProduct`.
   SDD embeds **no** provider-specific id/path/URL (grep-tested, SC-005); the reference
   provider descriptor lives in `FS.GG.Templates/providers/rendering.providers.yml`. This
   is the `scaffold-provider@1.0.0` contract in the registry.

The monolith was built because **`dotnet new` cannot compose templates** (see §3). But the
same constraint is exactly what forces the monolith to *vendor a fork* of Rendering — and
that fork is what went stale.

---

## 2. The incident, as a design signal

`fs-gg-fullstack` pinned `FsSkiaUiVersion=0.1.0-preview.1`, a version that did not exist on
the feed. NuGet did not fail; it emitted **NU1603** and floated each `FS.GG.UI.*` package
to a *different* nearest version, so the vendored sample source compiled against a
mismatched Scene API and the build failed with 19 errors. It was resolved by re-pinning to
the coherent 16-package set behind tag `fs-gg-ui/v0.1.50-preview.1` (renamed from
`fs-skia-ui/v0.1.50-preview.1` per ADR-0003; re-pointed at the same commits).

The root cause is **not** a bad number. It is that **Templates holds a hand-copied fork of
an upstream payload**, so upstream drift is invisible until a consumer compiles it, and
NuGet's nearest-version fallback hides the mismatch
([NU1603](https://learn.microsoft.com/en-us/nuget/reference/errors-and-warnings/nu1603)).
Vendoring guarantees a recurring instance of this bug class. The architecture should remove
the fork, not just refresh it.

---

## 3. The hard .NET constraints (what the platform allows)

These bound every option below. Sources are official Microsoft Learn / `dotnet/templating`.

- **A `dotnet new` template cannot depend on, include, or invoke another template.** A
  template package is just a NuGet package of template folders; one `dotnet new` call
  instantiates exactly one template. There is no "template imports template."
  ([custom templates](https://learn.microsoft.com/en-us/dotnet/core/tools/custom-templates),
  [create a template package](https://learn.microsoft.com/en-us/dotnet/core/tutorials/cli-templates-create-template-package))
  → A single self-contained template must therefore **vendor** everything it emits. This
  is the monolith's load-bearing constraint.
- **Composition *within* one template is first-class.** Choice/bool `symbols` + conditional
  `sources`/`modifiers` gate whole subtrees; `#if/#endif` toggles code.
  ([template.json reference](https://github.com/dotnet/templating/wiki/Reference-for-template.json),
  [conditional processing](https://github.com/dotnet/templating/wiki/Conditional-processing-and-comment-syntax))
  → Gating `.specify/` behind a `lifecycle` parameter is a small, idiomatic change.
- **A package is either a Template or a Tool, not both in practice.** `PackageType=Template`
  sets `IncludeBuildOutput=false` (no assemblies); `PackAsTool` needs the compiled
  app-host. Ship them as **two packages**.
  ([set package type](https://learn.microsoft.com/en-us/nuget/create-packages/set-package-type),
  [create a .NET tool](https://learn.microsoft.com/en-us/dotnet/core/tools/global-tools-how-to-create))
  One template package **can** carry many templates.
- **Run-script post-actions are a CI/agent liability.** They trigger an interactive
  "run this action? (Y/N)" prompt with no documented `--allow-scripts` flag, are **skipped
  in Visual Studio**, and assume a shell/PATH. `git init`/`chmod` belong in an orchestrator
  tool, not template post-actions.
  ([post-action registry](https://github.com/dotnet/templating/wiki/Post-Action-Registry),
  [#765](https://github.com/dotnet/templating/issues/765),
  [#6777](https://github.com/dotnet/templating/issues/6777))
  → The `fs-gg-ui` template's git-init/chmod post-actions are exactly the pattern to push
  into `fsgg-sdd scaffold`.
- **The ecosystem's answer to "compose layers" is "one template with switches" (Clean
  Architecture `ca-sln`, ASP.NET SPA templates) or an orchestrating tool** — never
  template-to-template dependency.
  ([CleanArchitecture](https://github.com/jasontaylordev/CleanArchitecture),
  [SDK templates](https://learn.microsoft.com/en-us/dotnet/core/tools/dotnet-new-sdk-templates))

---

## 4. The three composition shapes

### Option A — Vendored monolith (status quo)
One `dotnet new fs-gg-fullstack`, zero tools required. Self-contained.

- **Pros:** best first-touch UX; no `fsgg-sdd`/`fsgg-governance` install to try it.
- **Cons:** structurally **must vendor** a fork of `fs-gg-ui` (§3) → the recurring
  staleness bug class; Templates re-publishes Rendering's payload (ownership inversion —
  `transition-and-boundaries.md` says templates "move with the rendering project");
  re-emits an entire foreign Spec Kit lifecycle the product no longer wants; the
  `sync-from-rendering.sh` copy is manual and easy to forget.

### Option B — CLI-orchestrated composition (recommended)
`fsgg-sdd scaffold --provider rendering` installs the `fs-gg-ui` **template package from
NuGet at scaffold time** and invokes it live; the SDD skeleton + optional governance
overlay layer on top. **No vendored payload.**

- **Pros:** eliminates the fork → eliminates the staleness class; respects ownership
  (each repo ships its own layer, Templates ships none of Rendering); a bad template
  version **fails `dotnet new install`** instead of silently floating; the lifecycle and
  git-init effects live in the tool, where non-interactivity is controllable; the
  `scaffold-provider@1.0.0` contract already exists for exactly this.
- **Cons:** requires `dotnet tool install` of `fsgg-sdd` first (one extra step); the
  "single command, no tools" demo is gone.

### Option C — Generated monolith (fallback if zero-tool first-touch is mandatory)
Keep a `fs-gg-fullstack` template, but **generate** it in CI from the upstream template
package + overlay on every upstream tag (never hand-vendored), with `.specify/` gated off.

- **Pros:** preserves the one-command UX; the fork is machine-regenerated and pinned, not
  hand-maintained.
- **Cons:** still a fork (a CI artifact rather than a checked-in one); still duplicates the
  payload; only worth it if a tool-free `dotnet new` is a hard product requirement.

**Recommendation: Option B as the default, with Option C available only if a tool-free
first-touch is later judged essential.** The governance-only decision compounds this: SDD's
own lifecycle is *additive over* Spec Kit and never requires it, so "SDD lifecycle, no Spec
Kit" is the natural governed shape — and that shape is trivial to express in Option B and
awkward in Option A.

---

## 5. Recommended target architecture — who ships what

| Repo | Ships (NuGet) | Owns | Stops shipping |
|---|---|---|---|
| **FS.GG.Rendering** | `FS.GG.UI.*` framework packages (lockstep, single version property); `FS.GG.UI.Template` (`PackageType=Template`) | The framework + the runnable-app template **made lifecycle-agnostic** | The assumption that every scaffold is a Spec Kit project |
| **FS.GG.SDD** | `FS.GG.SDD.Cli` (`dotnet tool` → `fsgg-sdd`) | The lifecycle, the `.fsgg/` skeleton, the `scaffold-provider` contract, **composition orchestration** | — |
| **FS.GG.Governance** | `FS.GG.Governance.Cli` (`dotnet tool` → `fsgg-governance`); the `.fsgg/{policy,capabilities,tooling}` **schema + a populated FS.GG gate set** | Enforcement: profiles, gates, audit, the handoff consumer | — |
| **FS.GG.Templates** | (optionally) a small `fs-gg-governance` config-overlay template | The **provider registry** (`rendering.providers.yml`), the **populated** governance overlay, docs, and end-to-end composition tests | The **vendored monolith** and `sync-from-rendering.sh` |

### 5.1 The one upstream change that unlocks governance-only
Add a `lifecycle` **choice symbol** to `fs-gg-ui` and gate the lifecycle subtrees with
conditional `sources` (the idiomatic mechanism, §3):

```jsonc
// FS.GG.Rendering/.template.config/template.json
"symbols": {
  "lifecycle": {
    "type": "parameter", "datatype": "choice", "defaultValue": "spec-kit",
    "choices": [
      { "choice": "spec-kit", "description": "Emit standard Spec Kit (.specify/, constitution) — today's behaviour" },
      { "choice": "sdd",      "description": "No Spec Kit; lifecycle owned by fsgg-sdd (.fsgg/)" },
      { "choice": "none",     "description": "Runnable app only; no lifecycle scaffolding" }
    ]
  }
},
"sources": [
  { "source": ".specify/", "target": ".specify/", "copyOnly": ["**/*"],
    "condition": "(lifecycle == \"spec-kit\")", "exclude": [ "feature.json", "memory/constitution.md", "extensions/evidence/scripts/**" ] },
  { "source": ".template.config/generated/", "target": "./",
    "condition": "(lifecycle == \"spec-kit\")" }
  // agent-guidance / constitution sources likewise gated; the app + product-skill sources stay unconditional
]
```

`spec-kit` default keeps today's output **byte-identical** (no break for the existing
profiles/tests); `fsgg-sdd scaffold --provider rendering` passes `--param lifecycle=sdd` so
the governed product carries **only the runnable app**, and the `.fsgg/` lifecycle comes
from the SDD skeleton instead. This is one symbol + a `condition` on a handful of sources —
not a rewrite.

> **Open question to settle with Rendering:** which constitution governs a `lifecycle=sdd`
> product? Today the product inherits *Rendering's* constitution. If SDD owns the lifecycle,
> the F# constitution should arguably come from the SDD skeleton (`project-split-decision.md`
> already assigns "Standard Spec Kit **with the F# constitution**" to SDD). Recommend: SDD
> ships the lifecycle constitution; Rendering's stays a Rendering-internal artifact.

### 5.2 What `FS.GG.Templates` becomes
A thin **composition + registry** repo, not a fork host:

- `providers/rendering.providers.yml` — the provider descriptor (already exists), pinned to
  the `FS.GG.UI.Template` package version and passing `lifecycle=sdd`.
- `templates/fs-gg-governance/` — kept, but its `.fsgg/{capabilities,tooling}.yml` are
  **populated** with the real FS.GG gate set (today they ship `checks: []` / `commands: []`,
  which is valid-but-inert — see §6).
- Composition **tests** (the standard checks `transition-and-boundaries.md` prescribes:
  pack → install → instantiate representative profiles → restore/build → verify pins/links).
- **Deleted:** `templates/fs-gg-fullstack/` (the vendored payload) and
  `scripts/sync-from-rendering.sh`. If Option C is later required, this becomes a CI
  generator, not a checked-in copy.

---

## 6. How governance actually turns on (it currently does not)

The governed product's `.fsgg/capabilities.yml` and `tooling.yml` ship **empty**
(`checks: []`, `commands: []`). Per FS.GG.SDD's `adopting-governance.md` this is *valid* —
SDD never reads them to gate; they are optional compatibility facts (state
`notEvaluated`). But empty means **no gate fires**. Governance-driven means *populating*
them and running the Governance CLI. The real schema (from FS.GG.Governance
`specs/014…/contracts/fsgg-schema.md`) is concrete:

```yaml
# .fsgg/capabilities.yml  (governance-capabilities@2)
domains: [package-api]
pathMap: [ { glob: "src/**", capability: package-api } ]
surfaces:
  - { kind: protected, owner: platform, maturity: block-on-ship }
checks:
  - id: build
    domain: package-api
    command: dotnet-build         # must name a tooling.yml command
    owner: platform
    cost: medium                  # cheap | medium | high | exhaustive
    environment: local-or-ci
    maturity: block-on-ship       # observe | warn | block-on-pr | block-on-ship | block-on-release
  - id: test
    domain: package-api
    command: dotnet-test
    owner: platform
    cost: high
    environment: local-or-ci
    maturity: block-on-ship
```

```yaml
# .fsgg/tooling.yml  (governance-tooling@1)
commands:
  - { id: dotnet-build, command: "dotnet build", timeout: 600, environment: local-or-ci }
  - { id: dotnet-test,  command: "dotnet test",  timeout: 600, environment: local-or-ci }
environmentClasses: [local, ci]
externalTools:
  - { tool: dotnet, minVersion: "10.0.0" }
```

`policy.yml` profiles (`light | standard | strict`) then **shift the blocking boundary**:
`fsgg-governance` projects each `Check` into a typed `Gate` (`GateId = "<domain>:<checkId>"`)
and `deriveEffectiveSeverity` decides where a `block-on-*` finding becomes blocking —
`standard` blocks at the `gate` boundary, `strict` tightens to `verify`. Execution is
`fsgg-governance verify` / `ship` / `release`, exit `2` on a failing blocking gate.

**The seam:** `fsgg-sdd ship` emits `readiness/<id>/governance-handoff.json`
(`governance-handoff@1.0.0`) carrying **declared facts only** (no verdicts);
`fsgg-governance` consumes it and decides. Note the Governance-side consumer is **queued
work** (FS.GG.Governance ADR-0002), so the handoff is *produced* today but not yet
*enforced* — a real gap to track, not assume closed.

**Recommendation:** ship a populated default gate set (build + test + the in-process
`EvidenceGraph`/`EvidenceAudit` already in `build.fsx`) in the `fs-gg-governance` overlay so
"governance-driven" is true out of the box, not aspirational. Keep `light` as the
no-blocking default for first-touch.

---

## 7. Versioning & coherence — make the §2 bug structurally impossible

Producer side (Rendering already does most of this):

- **Lockstep, single version property.** All `FS.GG.UI.*` packages + the template package
  pack under one `<Version>`/`FsGgUiVersion` from `Directory.Build.props`. This is what
  makes "the v0.1.50 set" a meaningful, verifiable thing.
  ([CPM](https://learn.microsoft.com/en-us/nuget/consume-packages/central-package-management))
- **Tag the coherent snapshot** (`fs-gg-ui/v<ver>`), as already done. The tag is the
  human snapshot; the pin is its machine form.
- **Optional: a `FS.GG.UI` BOM/metapackage** that depends on the exact 16-package set at one
  version. The template's `fsproj` then references one package, not sixteen, and the pin is
  one line. ([metapackage convention](https://learn.microsoft.com/en-us/nuget/concepts/package-versioning))

Consumer side (the generated product + any composition tests):

- **Central Package Management** (`Directory.Packages.props`) — already in use.
- **Commit `packages.lock.json`** (`RestorePackagesWithLockFile`) and restore with
  **`--locked-mode` in CI** for byte-reproducible closures.
  ([repeatable restore](https://learn.microsoft.com/en-us/nuget/consume-packages/package-references-in-project-files#locking-dependencies))
- **Promote NU1603 to an error** (`<WarningsAsErrors>NU1603</WarningsAsErrors>`). This alone
  would have turned the §2 silent float into a hard failure. (`build.fsx` already fails on
  NU1603 at *runtime*; doing it at *restore* is strictly earlier and cheaper.)
- **Never float** the family (`*`/bare-minimum); pin exact published versions.

Sync side (replaces `sync-from-rendering.sh`):

- With Option B there is **nothing to sync** — the template is consumed by version. The only
  artifact to bump is the provider descriptor's template version, which **Renovate's NuGet
  manager** can do with `rangeStrategy: bump` and a grouped `FS.GG.UI.*` rule, or a
  `repository_dispatch` auto-PR fired from the upstream release tag.
  ([Renovate NuGet](https://docs.renovatebot.com/modules/manager/nuget/))

---

## 8. Cross-repo contract impacts (registry deltas)

Tracked in `FS-GG/.github/registry/dependencies.yml`; each is a `contract-change` per
ADR-0001.

1. **`fs-gg-ui-template`** (owner rendering) — gains the `lifecycle` parameter. Additive
   (default `spec-kit` preserves today's surface), but the **surface description** and the
   consumers' expectations change. Bump the contract note; no major break.
2. **`templates → rendering` dependency edge** — changes from *"vendors fs-gg-ui payload +
   FS.GG.UI.* framework"* to *"installs `FS.GG.UI.Template`@<ver> at scaffold time via
   `scaffold-provider@1`; references `FS.GG.UI.*`@<ver>"*. The "vendors" relationship is
   **retired**.
3. **`governance-capabilities@2` / `governance-tooling@1`** — no schema change, but Templates
   moves from shipping empty stubs to a **populated** default gate set (a consumer-side
   change worth noting so the empty-vs-populated default is intentional, not drift).
4. **New ADR** in `FS-GG/.github/docs/adr/` — *"Generated products are composed by
   `fsgg-sdd scaffold`, not by a vendored monolith; lifecycle is a template parameter;
   governance is populated-by-default in the FS-GG composition."* This reverses the implicit
   "monolith is primary" stance and the `project-split-decision.md` "decided later" note for
   Templates.

---

## 9. Migration plan (sequenced, pre-release, no compat debt)

Because there are no customers, this can be done in dependency order without deprecation
windows:

1. **Rendering** — add the `lifecycle` symbol + conditional sources (§5.1); keep
   `spec-kit` default so existing profile tests stay byte-identical; move git-init/chmod
   out of template post-actions (or leave behind `skipGitInit`, but stop relying on them for
   composition). Publish `FS.GG.UI.Template`. Cross-repo request → Rendering.
2. **SDD** — confirm `scaffold --provider rendering --param lifecycle=sdd` produces the
   app-only tree + skeleton; decide constitution ownership (§5.1). No contract change to
   `scaffold-provider` expected.
3. **Governance** — publish a populated default gate set (build/test/evidence) as the
   reference `.fsgg` config; track the ADR-0002 handoff-consumer work as the real
   enforcement gap.
4. **Templates** — point `rendering.providers.yml` at the `FS.GG.UI.Template` version with
   `lifecycle=sdd`; populate the `fs-gg-governance` overlay; **delete** `fs-gg-fullstack/`
   and `sync-from-rendering.sh`; add pack/install/instantiate/restore/build composition
   tests; rewrite the README around `fsgg-sdd scaffold`.
5. **.github** — update `registry/dependencies.yml` (§8), add the ADR.

Each step is a normal PR in its repo; cross-repo asks go through the issue protocol
(ADR-0001). The registry is updated as part of each `contract-change`'s resolution.

---

## 10. Risks & open questions

- **First-touch UX regression.** Option B needs `dotnet tool install`. Mitigation: a
  one-paragraph quickstart; reconsider Option C (generated monolith) only if telemetry/
  feedback later shows tool-install friction blocks adoption.
- **Constitution ownership** for `lifecycle=sdd` (§5.1) — needs a Rendering+SDD decision.
- **Governance enforcement is not actually wired yet** — the handoff *consumer* is queued
  (Governance ADR-0002). "Governance-driven" is partly forward-looking; the doc should not
  claim gates run end-to-end until that ships.
- **Two-tool install** (`fsgg-sdd` + `fsgg-governance`) for the full governed experience.
  Acceptable: governance is opt-in; `light`/absent is a no-op.
- **`fs-gg-ui` default stays `spec-kit`** to avoid breaking Rendering's own tests — so the
  governance-only behaviour is consumer-selected, not the template default. That is the
  right boundary (Rendering shouldn't assume SDD), but it must be set explicitly in the
  provider descriptor.

---

## 11. Decision requested

1. Adopt **Option B (CLI-orchestrated composition)** as the primary path and **retire the
   vendored monolith**? (Option C kept in reserve.)
2. Approve the **`lifecycle` parameter** in `fs-gg-ui` as the mechanism for governance-only
   products?
3. Approve **populating** the governance overlay (real gates) rather than shipping empty
   stubs?
4. Approve the **versioning hardening** (lockfile + locked-mode + NU1603-as-error + optional
   BOM)?

On approval, the concrete next action is the ADR in `FS-GG/.github` plus the cross-repo
request to **FS.GG.Rendering** for the `lifecycle` symbol, per the coordination protocol.

---

### Appendix A — sources

**Platform constraints & packaging**
- dotnet new custom templates — https://learn.microsoft.com/en-us/dotnet/core/tools/custom-templates
- Create a template package — https://learn.microsoft.com/en-us/dotnet/core/tutorials/cli-templates-create-template-package
- template.json reference — https://github.com/dotnet/templating/wiki/Reference-for-template.json
- Conditional processing — https://github.com/dotnet/templating/wiki/Conditional-processing-and-comment-syntax
- Post-action registry — https://github.com/dotnet/templating/wiki/Post-Action-Registry · interactivity: https://github.com/dotnet/templating/issues/765 · VS-skip: https://github.com/dotnet/templating/issues/6777
- Set NuGet package type — https://learn.microsoft.com/en-us/nuget/create-packages/set-package-type
- Create a .NET tool — https://learn.microsoft.com/en-us/dotnet/core/tools/global-tools-how-to-create
- SDK templates (switch-driven) — https://learn.microsoft.com/en-us/dotnet/core/tools/dotnet-new-sdk-templates
- Clean Architecture template — https://github.com/jasontaylordev/CleanArchitecture

**Versioning & coherence**
- Central Package Management — https://learn.microsoft.com/en-us/nuget/consume-packages/central-package-management
- Package versioning — https://learn.microsoft.com/en-us/nuget/concepts/package-versioning
- NU1603 — https://learn.microsoft.com/en-us/nuget/reference/errors-and-warnings/nu1603
- Repeatable restore / lockfiles — https://devblogs.microsoft.com/dotnet/enable-repeatable-package-restores-using-a-lock-file/
- Paket — https://fsprojects.github.io/Paket/
- Renovate NuGet manager — https://docs.renovatebot.com/modules/manager/nuget/

### Appendix B — provenance

Authored 2026-06-27 from: direct read of `FS.GG.Templates`; `gh`-mapped reads of
`FS.GG.Rendering` (`.template.config/template.json`, `.template.package/`),
`FS.GG.Governance` (`specs/012`, `specs/014`, ADR-0002), `FS.GG.SDD` (`README`,
`docs/{quickstart,migration-from-spec-kit,adopting-governance}.md`,
`specs/030`, `specs/017`), and `FS-GG/.github` (`registry/dependencies.yml`,
`docs/adr/*`, `docs/{project-split-decision,transition-and-boundaries}.md`); plus web
research into `dotnet new` templating, NuGet packaging/versioning, and F# build tooling
(Appendix A).
