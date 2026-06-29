---
title: "GitHub Projects v2 — Coordination board & cross-repo roadmap plan"
date: 2026-06-27
status: Draft for setup
author: FS-GG (planning)
affects: FS-GG (org), FS.GG.Rendering, FS.GG.SDD, FS.GG.Governance, FS.GG.Templates, FS-GG/.github
implements: FS-GG/.github ADR-0001 ("Tracking is an org-level Projects v2 board ('Coordination')")
related: docs/reports/2026-06-27-fsgg-packaging-composition-and-governance-architecture.md
---

# GitHub Projects v2 — Coordination board & cross-repo roadmap plan

> **Goal:** stand up the single **org-level Projects v2 board** ADR-0001 already mandates,
> spanning all four product repos + `.github`, with a **Roadmap (timeline) view** that
> sequences the pre-release work — and seed it from the migration plan in the architecture
> analysis. This is the missing **time/sequencing layer**: ADRs answer *why*, the registry
> holds *contracts*, `specs/` hold *feature detail*, and this board answers *when / in what
> order / who is blocked*.

## 0. Current state (2026-06-27)

| Capability | State | Implication |
|---|---|---|
| Milestones | **0** in every repo | No roadmap today; nothing to migrate |
| Org **Issue Types** | ✅ `Task`, `Bug`, `Feature` | Reuse; consider adding `Epic` |
| Issues | 1 Rendering (closed), 6 Governance, 1 Templates, 0 SDD | Tracking lives in `specs/` + ADRs + registry, not issues |
| **Projects v2 "Coordination" board** | Not created (or not visible — this token lacks `read:project`) | ADR-0001 requires it; this plan creates it |

Planning currently lives as in-repo Spec Kit `specs/<feature>/` dirs + the cross-repo
registry + ADRs. None of those is a cross-repo, dated roadmap. **Milestones are repo-scoped
and cannot express one** — Projects v2 is the right tool.

## 1. Why Projects v2 (not milestones)

- **Milestones** group issues toward a date with a % bar, but are **per-repo only**. Keep
  them for repo-local *release cuts* (e.g. `FS.GG.Rendering v0.2.0`), not the org roadmap.
- **Projects v2** is org-level and **spans every repo**, with a **Roadmap view** (timeline
  by start/target date fields or by milestone), **custom fields**, **iterations**, **draft
  issues**, **sub-issues** (epic→task rollup), built-in **workflows**, and **insights**.
  This is the "bigger roadmap with many milestones" surface.

## 2. Board configuration

### 2.1 Identity
- **Owner:** `FS-GG` (org-level, so items can come from all repos).
- **Name:** `Coordination` (matches ADR-0001).
- **Short description:** "Cross-repo roadmap & coordination for the FS-GG F#/.NET product
  line (Rendering · SDD · Governance · Templates)."
- **README (project description):** link ADR-0001, the registry, and this plan; state the
  conventions in §5.

### 2.2 Custom fields

| Field | Type | Options / notes |
|---|---|---|
| `Status` | single-select (built-in) | `Backlog`, `Ready`, `In progress`, `Blocked`, `In review`, `Done` |
| `Phase` | single-select | `P0 Decisions`, `P1 Rendering`, `P2 SDD`, `P3 Governance`, `P4 Templates`, `P5 Versioning` (the §4 roadmap) |
| `Repo` | single-select | `rendering`, `sdd`, `governance`, `templates`, `.github`, `cross-repo` |
| `Workstream` | single-select | `Composition`, `Lifecycle`, `Governance`, `Versioning`, `Docs`, `Coordination` |
| `Start` | date | feeds the Roadmap view |
| `Target` | date | feeds the Roadmap view |
| `Effort` | single-select | `S`, `M`, `L`, `XL` |
| `Contract` | text | registry id this item touches (e.g. `fs-gg-ui-template`, `scaffold-provider`) |
| `Blocked by` | text | item ref(s); the hard dependency in plain text (Projects has no typed dependency field) |

Reuse the org **Issue Types** (`Task`/`Bug`/`Feature`) for *kind*; model **epics** either by
adding an `Epic` issue type **or** by using a `Feature` issue as the **sub-issue parent**.
Recommendation: add an `Epic` issue type (org Settings → Planning → Issue types) so each
Phase is one epic with child `Task` issues and automatic progress rollup.

### 2.3 Views

1. **Roadmap** (default) — timeline; date fields `Start`→`Target`; **group by `Phase`**;
   zoom = Quarter. This is the headline roadmap.
2. **Board** — kanban grouped by `Status`; filter `is:open`.
3. **By repo** — table grouped by `Repo` (per-repo slice without per-repo milestones).
4. **Blocked** — table filtered `Status:Blocked`, sorted by `Phase` (standing impediments;
   pairs with the `blocked` cross-repo label).
5. **All items** — table with every field (grooming/export).
6. *(optional later)* **Current iteration** — if you adopt iterations for cadence.

### 2.4 Built-in workflows (Project → Settings → Workflows)
- **Auto-add** items: enable for each of the five repos (`is:issue,pr is:open`), or scope to
  a label (e.g. `roadmap`) to avoid noise.
- **Item closed → `Status: Done`**.
- **PR merged → `Status: Done`** (or `In review` on open).
- **Auto-add sub-issues** to the project when their parent is added.
- **Status updates** (Project → Status updates): post a short weekly roadmap note.

## 3. How the board relates to what already exists

| Layer | Tool | Owns |
|---|---|---|
| Decisions | **ADRs** (`FS-GG/.github/docs/adr/`) | *why* a cross-repo choice was made |
| Contracts | **registry** (`registry/dependencies.yml`) | *what* the versioned cross-repo surfaces are |
| Coordination messages | **cross-repo issues** (ADR-0001 protocol) | *requests/responses* between repos (the "mailbox") |
| Feature detail | **`specs/<feature>/`** (in each repo) | *the spec* for a unit of work |
| **Sequencing / time** | **this Projects board** | *when / order / blocked-on / who* |

The board **tracks**, it does not replace, the issue protocol: a cross-repo ask is still an
issue in the target repo (`cross-repo` + `cross-repo:request`); the board simply pulls that
issue in and places it on the roadmap. ADR-0001 already says "tracking is an org-level
Projects v2 board"; this operationalizes it.

## 4. Seed roadmap (epics → issues)

> **Contingent on approval of the architecture analysis.** P0 contains the decision gate;
> P1–P5 are the migration plan from that doc turned into trackable work. File these only
> after the four decisions in that report are accepted (or file P0 now and the rest as
> `Backlog`).

Convention below: **Epic** (Phase, target repo) → **child issues** (`repo`: summary). Each
child should carry acceptance criteria, `Contract`, and `Blocked by`.

### P0 — Decisions & coordination foundation · repo `.github` · Workstream Coordination
**Epic:** "Adopt CLI-orchestrated composition + governance-only direction."
- `.github`: **ADR** — "Generated products are composed by `fsgg-sdd scaffold`, not a
  vendored monolith; `lifecycle` is a template parameter; governance populated-by-default."
  (`Contract`: n/a; gate for P1–P5.)
- `.github`: **Registry deltas** — retire the `templates → rendering` *"vendors"* edge;
  annotate `fs-gg-ui-template` with the `lifecycle` parameter; note governance overlay moves
  empty→populated. (`Contract`: `fs-gg-ui-template`, `governance-capabilities`.)
- `.github`: **Create the Coordination board** (this plan) and seed P1–P5.
- Decision item: **constitution ownership** for `lifecycle=sdd` products (Rendering vs SDD).

### P1 — Rendering: lifecycle-agnostic template · repo `rendering` · Workstream Lifecycle
**Epic:** "Make `fs-gg-ui` emit Spec Kit only when asked." **Blocked by:** P0 ADR.
- `rendering`: add `lifecycle` **choice symbol** (`spec-kit`|`sdd`|`none`) + `condition` on
  the `.specify/`, constitution, `.agents/`, and `.template.config/generated/` sources;
  **default `spec-kit` = byte-identical** (existing profile tests unchanged).
  (`Contract`: `fs-gg-ui-template`.)
- `rendering`: move git-init/chmod **out of template post-actions** (CI-hang/VS-skip risk)
  into the scaffold path, or keep strictly behind `skipGitInit`.
- `rendering`: publish `FS.GG.UI.Template` carrying the new parameter; tag the coherent set.
- *Cross-repo request* from `templates`/`sdd` → `rendering` for the `lifecycle` symbol.

### P2 — SDD: confirm the composition path · repo `sdd` · Workstream Composition
**Epic:** "`scaffold --provider rendering --param lifecycle=sdd` yields app-only + skeleton."
**Blocked by:** P1.
- `sdd`: verify scaffold passes `lifecycle=sdd` through the provider wrapper; provenance
  records app-only paths. (`Contract`: `scaffold-provider`.)
- `sdd`: implement the constitution-ownership decision (ship the F# lifecycle constitution
  in the skeleton if P0 assigns it to SDD).

### P3 — Governance: real gates + the enforcement gap · repo `governance` · Workstream Governance
**Epic:** "Governance actually fires, and the handoff is consumed." **Blocked by:** P0.
- `governance`: publish a **populated reference `.fsgg` gate set** (build/test +
  EvidenceGraph/EvidenceAudit) so `checks:`/`commands:` are non-empty.
  (`Contract`: `governance-capabilities`, `governance-tooling`.)
- `governance`: **ship the handoff *consumer*** (ADR-0002 queued work) — today
  `governance-handoff.json` is *produced* by SDD but not *enforced*. This is the real gap;
  track it explicitly. (`Contract`: `governance-handoff`.)
  > **Update (2026-06-29): shipped.** The consumer landed (FS.GG.Governance specs 081/082;
  > epic FS-GG/FS.GG.Governance#8 closed) and the loop is enforced end-to-end through the
  > composed product (Templates#25 composition `govern` stage, matrix GREEN). The gap is
  > closed.

### P4 — Templates: retire the monolith · repo `templates` · Workstream Composition
**Epic:** "Templates becomes registry + populated overlay, not a fork host."
**Blocked by:** P1, P3.
- `templates`: repoint `providers/rendering.providers.yml` at `FS.GG.UI.Template@<ver>` with
  `lifecycle=sdd`. (`Contract`: `scaffold-provider`, `fs-gg-ui-template`.)
- `templates`: **populate** `fs-gg-governance` overlay (real gates from P3).
- `templates`: **delete** `templates/fs-gg-fullstack/` + `scripts/sync-from-rendering.sh`.
- `templates`: add composition tests (pack→install→instantiate profiles→restore/build→verify
  pins/links) and rewrite README around `fsgg-sdd scaffold`.

### P5 — Versioning hardening (cross-cutting) · repo `cross-repo` · Workstream Versioning
**Epic:** "Make the `FsSkiaUiVersion` staleness bug class structurally impossible."
- consumer repos: commit `packages.lock.json` + CI `--locked-mode`; **NU1603 → error**.
- `rendering`: optional `FS.GG.UI` **BOM/metapackage** pinning the 16-package set.
- `cross-repo`: replace `sync-from-rendering.sh` with **Renovate** (`rangeStrategy: bump`,
  grouped `FS.GG.UI.*`) or a `repository_dispatch` auto-PR on upstream release tags.

## 5. Conventions (put in the board README)

- **One roadmap item = one issue** in its owning repo; cross-repo asks additionally carry the
  `cross-repo`/`cross-repo:request` labels and live in the *target* repo.
- Set `Phase`, `Repo`, `Workstream`, `Target`, and (for cross-repo work) `Contract` on every
  item. `Blocked` status mirrors the `blocked` label.
- **Epics** are the Phase parents; use **sub-issues** for the children so progress rolls up.
- A `contract-change` item must link the registry PR (ADR-0001) — put the registry id in
  `Contract`.
- Draft issues are allowed for not-yet-filed ideas; promote to real issues before work
  starts.

## 6. Setup runbook (`gh` CLI)

Prereq — grant Projects scope (this session's token lacks it):

```sh
gh auth refresh -s project,read:project
```

Create the board and capture its number:

```sh
gh project create --owner FS-GG --title "Coordination" \
  --format json --jq '.number'      # -> e.g. 1   (call this $P below)
```

Add fields (single-selects shown; dates/number/text analogous):

```sh
gh project field-create $P --owner FS-GG --name "Phase" --data-type SINGLE_SELECT \
  --single-select-options "P0 Decisions,P1 Rendering,P2 SDD,P3 Governance,P4 Templates,P5 Versioning"
gh project field-create $P --owner FS-GG --name "Repo" --data-type SINGLE_SELECT \
  --single-select-options "rendering,sdd,governance,templates,.github,cross-repo"
gh project field-create $P --owner FS-GG --name "Workstream" --data-type SINGLE_SELECT \
  --single-select-options "Composition,Lifecycle,Governance,Versioning,Docs,Coordination"
gh project field-create $P --owner FS-GG --name "Start"  --data-type DATE
gh project field-create $P --owner FS-GG --name "Target" --data-type DATE
gh project field-create $P --owner FS-GG --name "Effort" --data-type SINGLE_SELECT \
  --single-select-options "S,M,L,XL"
gh project field-create $P --owner FS-GG --name "Contract" --data-type TEXT
gh project field-create $P --owner FS-GG --name "Blocked by" --data-type TEXT
```

Add items (existing issues / draft issues):

```sh
gh project item-add $P --owner FS-GG --url https://github.com/FS-GG/FS.GG.Rendering/issues/<n>
gh project item-create $P --owner FS-GG --title "P1 rendering: add lifecycle symbol to fs-gg-ui" \
  --body "Gate .specify/ + constitution + agent guidance behind a lifecycle choice; default spec-kit byte-identical."
# then set fields with: gh project item-edit --id <itemId> --field-id <fid> --single-select-option-id <oid> ...
```

Notes / caveats:
- **The Roadmap view, field options on existing fields, and per-view grouping are
  configured in the web UI** (`gh project` can create the project, fields, and items, but
  view layout/grouping is UI-driven today).
- **Sub-issues** (epic→child) are set via the UI or the REST API
  (`POST /repos/{owner}/{repo}/issues/{n}/sub_issues`); `gh project` does not create the
  parent/child link.
- **Issue Types** are assigned via the UI or `gh issue edit`/API; add the `Epic` type in org
  Settings → Planning → Issue types first.
- **Built-in workflows** (auto-add, closed→Done) are enabled in Project → Settings →
  Workflows.

## 7. Cadence & ownership

- **Groom** weekly: triage new repo issues into the board, set `Phase`/`Target`, clear
  `Blocked`. Post a **status update** on the board.
- **Roadmap is the source of *order*; the registry is the source of *contracts*; ADRs are
  the source of *decisions*.** Keep them consistent: a re-sequenced phase updates the board;
  a changed surface updates the registry; a reversed choice updates an ADR.
- Pre-release, dates are directional (no customers, no SLA) — use `Phase` order as the
  primary signal and `Target` as a soft horizon.

## 8. Risks / open items

- **Scope:** creating the board needs `project`/`read:project` on the operator's token; this
  session's token does not have it (verified — `gh project list` returns missing-scope).
- **Seeding is contingent** on the architecture-analysis decisions; P0 is the gate. Filing
  P1–P5 before approval risks churn — keep them `Backlog`/draft until P0 lands.
- **Governance enforcement is not wired yet** (P3 / Governance ADR-0002): the board should
  show this as open work, not a done capability.
  > **Update (2026-06-29): no longer a risk.** Enforcement is wired and proven end-to-end
  > (consumer shipped — Governance specs 081/082, epic #8 closed; Templates#25 composition
  > test GREEN). The board shows P3 as Done.
- **Automation noise:** prefer label-scoped `auto-add` (e.g. a `roadmap` label) over
  add-everything, given repos also carry routine PRs.

## 9. Next actions

1. Approve this board shape (fields/views/phases).
2. Grant `project` scope; create `Coordination`; add fields per §6.
3. Land the P0 ADR + registry deltas, then seed P1–P5 epics + sub-issues from §4.
4. Enable auto-add (label-scoped) + closed→Done workflows; build the Roadmap view grouped by
   `Phase`.
