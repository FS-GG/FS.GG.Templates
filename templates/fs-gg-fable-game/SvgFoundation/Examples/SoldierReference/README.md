# Soldier reference preparation

This is the pure preparation slice of SVG-COHERENCE-01.5. It is not wired into the
player or its build. `SoldierWorkload.fs` owns deterministic product IDs, authority
state and semantic commands; `SoldierDocument.fs` projects that state with public
Scene 0.31.0 identified documents. No DOM, timer, network, runtime flag or package
pin changes are part of this slice.

Existing package globs include these source files in modern and legacy Fable
payloads. Modern bundle modifiers copy them only for `complete`; the legacy
`svgFoundation=false` route excludes all SVG files, while true retains them.
Six fresh source-directory template generations verified all five files in complete
and absence in omitted/player/studio/tactical/arcade. The player project lists
compile files explicitly and does not compile or mount this reference. This is a
local template-engine check; packed public/installed qualification remains separate.
Public installed file presence awaits publication and adoption. Later browser
composition must preserve complete-only source and compilation boundaries.

The original MIT soldier has a helmet/visor, backpack, vest/pouches, gloves, rifle
and boots. Six explicit blue/amber and ready/march/kneel symbols preserve authored
paint. Root reviewed the actual glyph on 2026-10-05. Geometry/paint order is frozen;
the qualified canonical shared-codec hash is recorded in
`provenance.json`. Each symbol contains one Scene leaf with 26 geometry nodes,
17 paths and 108/111/112 path commands. Logical leaf counts do not measure browser
shadow-tree work or GPU cost. Definition sets are immutable and built once for
each supported revision. Full document replacement still validates and serializes
all content; browser replacement will additionally parse it.

`reference.json` fixes the version, seed, placements, update ranks, camera route,
churn, offscreen pin/removal semantics, definition revisions and export expectation.
Requested visible counts 1/100/250/500/1,000 and 2,000-world/200-visible are data,
not measured budgets. Health uses one foreground bar per soldier to fit the public
node profile; its width is the authoritative percentage. Selected/focused frames
are separate overlays. Camera, selection and focus have a presentation revision;
they do not increment authority revisions. Removal retains survivor order, clears
removed selection and moves removed focus to the first survivor or the future
panel control. Browser removal announcements remain a later composition obligation.

Projection validates bounded input first. `tryAccept` retains the exact previous
accepted document/display/export on failure. Display filtering preserves product
order and pins selected/focused IDs. Full export always uses the complete document.
Filtering is a pure correctness seam; spatial query integration is later work.

The focused executable links these two files directly and uses only public Scene
0.31.0, with no unpublished sibling reference:

```console
dotnet run --project tests/SoldierReference.Tests/SoldierReference.Tests.fsproj -- --artifacts /private/soldier-reference-results
```

Run from the repository root after programme CLR allocation. It checks deterministic
states/updates, shared validation and codec round trips, geometry, faction/pose/health,
identity/order, culling pins/full export, command limits and atomic invalid-input
preservation. It emits canonical asset/workload oracles and their SHA-256 manifest
outside the checkout. The allocated final run passed 6,222 checks, including many per-instance invariants.
These source checks do not establish Fable/browser/renderer/performance acceptance.
A CPU raster preview of the shared standalone export confirmed visible geometry;
root reviewed that actual-export witness before final hash freeze.

Next joins: actual opt-in complete-player entry; local Game and external session
adapters; accessible HTML controls/input; real-entry bot journey; staged stress and
lifetime tests; producer/host-suite/artifact join; coherent publication and separate
installed clean/retained upgrade qualification. SVG-COHERENCE-01.5 stays open.
