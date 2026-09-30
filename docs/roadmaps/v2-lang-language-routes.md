# V2 language-route qualification

Qualify the six declared product routes through the published portable workspace contract. This plan
owns **V2-LANG-01.5** for Templates and links to the
[programme amendment](https://github.com/FS-GG/.github/blob/main/docs/roadmaps/2026-09-29-language-independent-workspaces-and-agent-integration.md)
and [Unified roadmap §9.8](https://github.com/FS-GG/.github/blob/main/docs/2026-09-07-154210-fs-gg-unified-development-roadmap.md#98-feature-parts-and-subroadmap-index).
Coordination owns the [portable producer plan](https://github.com/FS-GG/FS.GG.Coordination/blob/main/docs/roadmaps/v2-lang-portable-integration.md);
Templates owns these native fixtures and receiver materialization. Product owners retain functional
acceptance and artifact custody. The programme integrator joins the shared boundaries.

**Status, 2026-09-30:** native fixture preparation is locally qualified. The TypeScript Todo browser-image
source checkpoint is prepared; its exact-head strict native image run and source delivery remain pending.
Portable binding, publication, installed adoption and complete matrix acceptance remain open. The prospective
population below does not alter the accepted R5 cohort or its cutoff.

## Declared population

| Route | Selected source and runtime | Native product evidence | Portable disposition |
|---|---|---|---|
| Python Hello | Coordination `tests/portable-workspace/image/fixture/python`; CPython 3.14.0 | Invoke the actual greeting entry point as well as build/test operations | Await enforced P2 and qualified image |
| TypeScript Todo | [Fixture](../../examples/language-routes/typescript-todo/README.md); Node 24.8.0, TypeScript 5.9.2, Playwright 1.63.0 | Served compiled entry point: add/edit/complete/filter/delete, reload and malformed retained state | Browser-image source prepared; strict native image qualification, binding and adoption pending |
| Rust Tic-tac-toe | [Fixture](../../examples/language-routes/rust-tic-tac-toe/README.md); Rust/Cargo 1.98.1 | Built entry point, legal play, both winners, draw, terminal refusal and restart | Native preparation passed; reviewed image and binding pending |
| Go Snake | [Fixture](../../examples/language-routes/go-snake/README.md); Go 1.27.1 | Built JSON entry point, input, growth/score, pause, collision, terminal refusal and restart | Native preparation passed; reviewed image and binding pending |
| FourD | Existing selected stack and product revision `931869236b4253b1489c4e8095a36017709194e2`; .NET SDK 10.0.401, Fable 5.13.0 | Preserve the accepted design-v2 technical comparison and save/runtime boundaries | Existing product evidence retained; portable binding and adoption pending |
| Composed TypeScript/Python | Coordination `tests/portable-workspace/image/fixture/composed`; Node 24.8.0, TypeScript 5.9.2, CPython 3.14.0 | Verify both components and the actual frontend-to-backend journey | Await enforced P2 and qualified image |

Reuse the Python and composed producer fixtures rather than maintaining another copy in Templates.
Before binding each route, retain exact source and tree, reviewed profile/schema digest, toolchain and
single-platform OCI identity. Rust, Go and FourD still require their own reviewed execution images;
the Python/Node image cannot establish those capabilities. Unsupported required toolchains must refuse
before an effect. An unresolved required route keeps the parent open.

## Native preparation evidence

Preparation starts from protected Templates `ba760d7725fe64b9311c20b57a05ef8630533804` and leaves the
delivered JavaScript enrollment apps unchanged. The three new fixture directories have no CLR,
Akka.NET or Agent Framework product dependency.

- Rust source `68d5c92c96601fbf5d1495891f40cc9a06052fa4`: isolated Rust/Cargo 1.98.1;
  six library tests and one actual built-entrypoint test passed, with locked Clippy and formatting.
- Go source `e711e495167a119b00df711f983148a9ff670991`: verified official Go 1.27.1 archive;
  five tests including the built entry point, formatting, vet and trimmed build passed. Toolchain
  switching and module network discovery are disabled by the fixture verifier.
- TypeScript source `8e0b3e81efa857eb8b45aa50ee10fa9b12cde33e`: verified official Node 24.8.0
  archive and exact TypeScript 5.9.2; five unit tests and two served compiled browser journeys passed.
  The qualifier binds subprocesses to the selected absolute Node executable.

The [native fixture workflow](../../.github/workflows/language-route-fixtures.yml) repeats these checks
in three independent bounded jobs. Native source checks do not establish portable image qualification,
publication or installed receiver acceptance. Retain the exact joined head and hosted run when delivered.

## TypeScript Todo browser-image source checkpoint

Source commit `6859ece6a0b94cea51444a5b5d13bc0303948900` prepares the dedicated image recipe, fixed
qualification entry point, source contracts and strict workflow and is retained as the integration candidate's
first commit. Review then tightened the OCI archive verifier to close every referenced layer before acceptance;
the pinned recipe, inputs and product fixture remain byte-identical to that source commit. The fixed entry point
later added a private umask and actual container uid/gid evidence for host-readable rootless custody.
The inputs pin Node 24.8.0, TypeScript 5.9.2, Playwright 1.63.0, Chromium
153.0.8010.12 revision 1243, the Linux amd64 Playwright base manifest, browser archives, npm packages and
licence identities. Reviewed source digests are `995914cf786fb2021e2034171935b88cced44a05fe542662f8d91e9daa2fa8e9`
for the input manifest, `d622348d58f7584d4214a921611bbd8ca976cd349098dc4978dedcf97b0b1553`
for the recipe and `2e297b09cda323601766eed8722de1319cf8f7501b0eb873cd01ca99cbf9d6db`
for the fixed entry point.

The operation exposes no caller-controlled command. It mounts committed source read only, runs as uid/gid
`32768:32768` mapped by rootless `keep-id` to the calling host user, disables external container networking
while retaining loopback for the served journey, and
places compiled output, reports, cache, home, temporary browser profiles and retained browser state beneath
scoped `/output`. Its result covers add, edit, complete, filter, delete, reload and malformed retained-state
recovery. The qualifier binds the exact source revision and tree, local image ID and digest, exported OCI
layout/index with unique safe members, manifest and config, and every referenced layer by descriptor media type,
path, declared size and content hash. The archive blob inventory must exactly match those descriptors. The local
image digest must equal the exported manifest digest, and the local image ID must equal the exported config
digest. It also retains candidate archive, journal and operation-result hashes. Candidate and evidence custody
is limited to the dedicated workflow artifact for 14 days; this checkpoint publishes or activates nothing.

Pipeline preflight remains static and precedes the costly base pull and image build. The workflow is one linear
job with no fan-out, shared cache, evidence reuse, retry state or publication, so a separate state model would
duplicate the execution plan without testing another interaction. Existing source contracts check reviewed
hashes, closed command construction and OCI closure; exact-head rootless preflight checks platform, uid mapping,
Podman capabilities and clean source. This adds no setup job or dependency and can avoid the bounded 35-minute
native workload on a malformed candidate. Reassess the preflight if fan-out, cross-job artifacts, retries, reuse
or publication are added.

This is a source checkpoint only. A future run of the dedicated strict workflow must qualify the exact admitted
head and retain its OCI candidate and evidence before the image can enter native binding. Portable executor
binding, lifecycle evidence, publication, installed adoption, defaults and parent closure remain pending.

## Dependency-ready windows

| Window | Ready condition | Completion evidence |
|---|---|---|
| Native preparation | Amendment selected; disjoint fixtures and exact toolchains available | Protected coherent fixture/plan/workflow change and successful exact-head native checks |
| BIND | Coordination P2 enforces the reviewed source, toolchain/image, authority, deadline and durable recovery boundary; each route's image is qualified | Each selected route executes its real product journey through the enforced contract; source/profile/image and scoped result artifacts read back |
| ADOPT | P3 publishes the coherent producer bytes and P4 selects a receiver window | Actual distributed tooling installs without a product .NET SDK dependency; fresh creation and retained upgrade independently verified |
| CLOSE | Every declared route completes its binding/adoption evidence | Joined matrix covers native function, cancellation/termination, duplicate delivery, recovery, unsupported-toolchain refusal and truthful unknown results |

Native preparation can proceed in parallel with P2 enforcement and image qualification. Each BIND
route waits only for its own qualified boundary and image. P2's entire parent is not a prerequisite:
its P5 consumes this completed matrix, so requiring P5 before BIND would create a circular dependency.
Publication and receiver adoption still precede installed acceptance. Optional AG-UI endpoint or Agent
Framework adoption is not selected by this plan; its independent trial outcomes do not add a matrix gate.

For each route, retain finite command/allocation identity, exact source/profile/image, actual entrypoint
result, output digests, cancellation request and observed termination, duplicate receipt and restart
recovery. Unknown effect or cleanup state remains unknown and does not permit another native write.
Verify at least one non-.NET product environment using the distributed integration tooling; record
any runtime prerequisite of the tooling separately from product dependencies. Composed qualification
must demonstrate the component commands and the real combined journey.

## Workspace impact and adoption

The new fixture source and CI change no generated workspace behavior. Existing enrollment apps,
FourD's selected stack, R5 evidence, lifecycle defaults and opt-in boundaries remain unchanged.
The affected future families are Python, TypeScript, Rust, Go and mixed workspaces. Before adoption,
they have no claimed installed portable execution capability; afterward, only a reviewed selected
profile and qualified producer/receiver combination provides that capability.

The first milestone that can change fresh creation or enabled behavior is Coordination P4 receiver
adoption, following P3 publication. It must name the exact SDD/Templates materialization path and
published artifacts, and prove clean creation using installed bytes. Language-route selection remains
explicit opt-in; this plan introduces no default service or generated dependency. Retained workspaces
need a separate upgrade check that preserves source and saved product state, refuses incompatible
required capabilities, and records any unsupported local-only route without claiming adoption.

Close V2-LANG-01.5 only after the complete declared matrix meets these gates. Source delivery and
partial native success remain separately reportable milestones.
