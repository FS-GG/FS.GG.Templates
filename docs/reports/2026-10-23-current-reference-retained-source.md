# Current public reference retained adoption source

The [current-reference manifest](../../scripts/svg-current-reference-adoption.json)
extends the existing complete-workspace transaction for the published
`FS.GG.Workspace.Template` 0.19.3 Complete reference. This is source preparation
for [#4816](https://github.com/FS-GG/.github/issues/4816). Installed retained
adoption, builds and browser qualification remain open.

The historical manifest and Release-D gates retain their original identities.
The successor verifies the historical manifest's SHA256 and inherits its exact
0.10.0–0.13.0 archive and path allowlists, including the previously selected 0.14 source-candidate
repair bytes. That inherited source baseline adds no public 0.14 upgrade claim.
It additionally authenticates the original package-owned
`.config/dotnet-tools.json` bytes for those four versions and upgrades Fable5.13.0
to the current manifest's Fable5.18.0. Only the exact historical or current Fable row is replaceable. Edited Fable
rows, duplicate JSON keys and changed manifest version/root semantics refuse.
Existing SDD, Coordination, formatter and local tool entries and root metadata
survive the compiler update; missing current defaults may be added. Other
configuration files remain preserved. It adds the FourD, local-save/replay,
external-authority, Soldier and WASM reference files and their browser test
sources. Every managed product file must match canonical hashes from immutable
source `7be0bcf5886d39a8161b186beb8cc06e82415f1e`; missing or edited target files
refuse before adoption. This prevents file-existence guards from silently
omitting reference modules. The tool merge returns its bytes directly, so product-name substitution cannot
rewrite owner tool metadata. The existing skill-manifest merge still authenticates
package declarations and bodies and preserves other producers' rows.

The target declaration binds the signed public archive SHA256
`9594ec204a26f238a06e016d1cfe1e796a07fda23c16589eceb19366cd4a72a2`
and provider descriptor SHA256
`6b3d8f2dcbdcd429e4f622cfd6e1515c439097147bb79f5d5c7969d36c3b5006`.
Source hashes establish selected content correspondence; they do not establish
archive acquisition, materialization or execution. Product/lifecycle configuration
outside the managed list remains preserved. No newer retained baseline or blanket
upgrade guarantee is added.

## Supplied-receiver transaction harness

[verify-current-reference-adoption.py](../../tests/composition/fable-game/verify-current-reference-adoption.py)
accepts a materialized Complete candidate, one materialized retained receiver,
the corresponding old public archive, the current public archive and a new
external output directory. Its CLI checks package hashes and NuGet identities.
The caller must independently join those archives to the actual generated trees.
The harness acquires no packages and launches no compiler, browser or installer.

It copies the retained receiver before testing adoption, verifies full target
coverage and preserved file bytes/modes, and retains an adopted copy for later
build qualification. Separate copied cases reject old managed-file and new
reference-path collisions, roll an interrupted apply back, and resume interrupted
explicit rollback. Its receipt describes transaction controls and lists remaining
qualification. It does not assert a successful application build or browser run.
Candidate, receiver and output boundaries are normalized and checked from the
filesystem root for symlinks before any output is created; resolved overlap
refuses, including ancestor aliases and `..` spellings.
The transaction's existing journal, stale-inventory checks, corrupt-backup and
newer-edit refusals remain in force.

## Source controls and Portal coupling

The [pure source suite](../../tests/composition/fable-game/test-current-reference-adoption.py)
uses copied template source with synthetic identity substitutions and authored
save, replay, configuration, extension and lifecycle sentinels. It exercises
manifest identity and historical-hash refusals, complete reference population,
missing/edited candidate paths, transaction recovery, collisions, stale modes and
review diffs, symlinks, corrupt backups and newer managed edits. The typed-SDD fixture mirrors the
[SDD2.0.2 merge](https://github.com/FS-GG/FS.GG.SDD/blob/83790aedc228e2158c9da7a9ac8e30195bdf9fbe/src/FS.GG.SDD.Commands/CommandWorkflow/ScaffoldMutation.fs):
`fs.gg.sdd.cli`2.0.2 and `fs.gg.coord.cli`0.90.0 coexist with the historical
Fable row. A Fable-only whole-file hash would incorrectly refuse that promised
receiver. Co-tenant metadata containing the candidate's product name survives,
and rollback restores the entire original tool file bytes and modes. These fixtures
are explicitly synthetic; they do not substitute for historical public receivers.

The shared adopter is also projected as `PortalExample/manage.py`. Changing its
bytes initially made the existing Portal suite refuse the old helper digest in
`source-provenance.json`. The source delivery refreshes that one projected-helper
digest. It changes no Portal package closure, Game source, scene or API.
The Portal suite checks adoption/removal and its stronger late-conflict
controls. First failing source results are retained separately from the repairs.

## CI preflight

The existing composition job runs both pure suites after checkout, before SDK,
Node and authenticated CLI setup, under its existing source-scope condition.
A failure stops the job before tool setup. Static controls check that actual
workflow ordering, both commands, the scope condition and fail-fast shell mode;
deliberately moved or weakened steps fail those controls. The docs-only scope and
all later composition stages remain unchanged.

The pipeline preflight choice is static validation plus these small pure suites;
this linear addition needs no state-machine model. The work is reusable on each
source composition run, with a ten-minute implementation/validation cap. Local
pure runs are measured in seconds. Hosted setup time and avoided runner cost are
unknown; no CI savings or end-to-end hosted qualification is claimed.

## Remaining installed qualification

A separately admitted rehearsal must genuinely materialize the exact public
0.19.3 Complete candidate and public 0.13.0 typed-SDD retained receiver in isolated
homes, then join their archives, provider/lifecycle provenance and generated
bytes to this source contract. The other promised 0.10.0–0.13.0 receivers retain
their original creation options and independent package identities. Do not
substitute current source copies for those receivers.

Run the transaction controls and then qualify the retained adopted tree through
locked solution/Fable builds and relevant actual browser conformance, including
opted-in WASM only for the selected Complete path. Read back exact dependency
content hashes, executable/tool/browser identities, original deadlines and
cleanup. Preserve the old lifecycle record; upgrading it or an installed Wizard
is a separate operation. A canonical managed-group supplier and a new
invocation-specific resource profile precede runtime. Historical clean installed-C
acceptance, old Release-D/AT runs and package publication grant no runtime replay.

The whole #4816 promise remains open after source delivery. FourD/SC2/BAR product
adoption and native acceptance remain with their owners under the staged plan.


## Fixed earlier-three source successor

The held earlier-three entry selects only the already declared public0.10.0,
0.11.0 and0.12.0 cohorts. Actual bounded NuGet archive readbacks matched the
historical manifest, and each NuSpec repository commit joined a primary GitHub
commit readback: respectively `565ad45d2dda386e9d1673071cc0b424cfd02be6`,
`6a66e0a31c33feab4c8f650709b585df6ac3d4c4` and
`7146224843419a10613b0f23c781b38bc88514b8`. These input observations establish no
materialization or runtime result. The accepted0.13 typed-SDD run40032045163 is
reused as scoped prior evidence and is not replayed.

The new fixed operation shares qualified SDK401/runtime12 and one current0.19.3
candidate. Four empty template homes and three independent receivers, transaction
copies, journals and adopted lock censuses prevent registration or mutable-fixture
reuse. The0.10 receiver uses lifecycle none without an SVG argument;0.11/0.12 use
lifecycle none with `--svgFoundation true`. No SDD/Wizard install is added to these
historical routes. Old roots receive no SDK invocation before adoption. Each
adopted workspace retains its product-owned private package cache; no shared
package-restore saving or cold fit is asserted.

The source proposes one original finite3000-second graph: setup720, target60,
three cohorts each generation60/transactions100/locked-restore480, collection120,
cleanup90 and overhead90. Its separate job has a3060-second unit and3300-second
original first-step horizon,5-second stop and30-second independent post-read
reservation. CPU2,8GiB unit memory,512 tasks,10GiB available ancestor memory and
20GiB staging floors remain. The original0.13 job/default1800/2100 limits and all
D5/DOM defaults remain unchanged. The initial reviewed source used `EARLIER_ADMISSION=None`; the later conditional source selection below still requires separate actual runtime admission;
fit is unmeasured and expired reserves refuse without renewal. There is no version
or arbitrary command input.

Fifty-two synthetic retained/earlier controls passed after a causal workflow-path
repair. A subsequent existing17-test transaction suite did not pass: the private
source-check wrapper's restrictive fixture umask made a0600 mode-change control
inert. The exact affected stale-mode method passed separately with the intended
0644-to0600 fixture transition inside a private0700 root; the original failed suite
is retained, not relabeled. An accidental Python-only source-check child also
lacks original birth/wait/EOF custody and remains a separate Unknown. Later process
absence does not clear it. No Node, compiler, SDK, browser or native unit executed
in these source checks. Coupled DOM/D5 suites were not repeated in this stage;
normal exact-head CI and independent review remain required.

All three genuine materializations, preserving transactions and locked restores
remain unobserved. Their solution/Fable builds, adopted browser acceptance,
durable/product-save and broader4816 obligations remain open. Source delivery
must integrate the actual protected D5 squash before first push; a pending source
ancestor is not that delivery proof.


## Shared qualifier clock and diagnostic successor

Conditional source selections [4816/6378268057](https://github.com/FS-GG/.github/issues/4816#issuecomment-6378268057)
and [4849/6378268333](https://github.com/FS-GG/.github/issues/4849#issuecomment-6378268333)
are separate and expire for new final selections after2026-10-24T03:30:00Z. Actual
Root selection UTC, dispatch and run remain unset. Earlier-three validates fixed
300-second start/3600-second observer intervals; D5 retains300/2400 and its first
rehearsal-only gate. Both earliest-step records retain UTC observation, original
source/run/boot, fixed monotonic deadline projection and accepted/refused cause.
Earlier-three now retains that original clock even when admission refuses. Neither
clock projects again from a later read; checkout/unit reserve is counted against
the original shorter bound. Original0.13 execution and budgets remain unchanged.

The earlier-three setup now uses the existing D5 canonical managed literal
`unshare --user --map-root-user --net -- /usr/bin/true` before SDK or public package
acquisition. Exact host-observed unshare/true image identities, cleared LANG/TZ,
managed receipts/streams and require-empty retirement remain authoritative. A
failed or unobservable prerequisite stops the batch without a weaker sandbox,
host-policy mutation or retry. D5 additionally retains the reviewed bounded
optional collector-parent observations: unavailable/overflow metadata is secondary,
never replaces the original probe streams/cause and does not describe the child's
post-exec or post-CLONE state. No producer/backend policy changes accompany this.

Focused source controls observed six initial clock/hold/late controls passing;
two new probe controls initially caught an inappropriate source-path overlap
guard, then passed after the causal symlink-chain fix. Nine focused D5 clock,
new-grant/scope and metadata-failure-isolation controls passed. The failed original
attempt is retained; no whole52/17/DOM/D5 suite was repeated. Checks used one CPU,
normal virtual address space and sampled aggregate RSS below75MiB, with original
birth/argv/image/wait/EOF custody and no remaining sampled owned births. No actual
namespace, SDK, Node, Go, GI, network or product runtime executed. The earlier
accidental Python-child Unknown and all original failed-check/native/AT holds stay
unreleased. Exact-head independent review/CI/protected delivery and a fresh Root
one-POST selection remain required; neither source grant starts a runtime clock.
