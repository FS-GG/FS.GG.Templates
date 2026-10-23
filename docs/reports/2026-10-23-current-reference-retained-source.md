# Current public reference retained adoption source

The [current-reference manifest](../../scripts/svg-current-reference-adoption.json)
extends the existing complete-workspace transaction for the published
`FS.GG.Workspace.Template` 0.19.3 Complete reference. This is source preparation
for [#4816](https://github.com/FS-GG/.github/issues/4816). Installed retained
adoption, builds and browser qualification remain open.

The historical manifest and Release-D gates retain their original identities.
The successor verifies the historical manifest's SHA256 and inherits its exact
0.10.0–0.13.0 archive and path allowlists. It adds the FourD, local-save/replay,
external-authority, Soldier and WASM reference files and their browser test
sources. Every managed product file must match canonical hashes from immutable
source `7be0bcf5886d39a8161b186beb8cc06e82415f1e`; missing or edited target files
refuse before adoption. This prevents file-existence guards from silently
omitting reference modules. The existing skill-manifest merge still authenticates
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
The transaction's existing journal, stale-inventory checks, corrupt-backup and
newer-edit refusals remain in force.

## Source controls and Portal coupling

The [pure source suite](../../tests/composition/fable-game/test-current-reference-adoption.py)
uses copied template source with synthetic identity substitutions and authored
save, replay, configuration, extension and lifecycle sentinels. It exercises
manifest identity and historical-hash refusals, complete reference population,
missing/edited candidate paths, transaction recovery, collisions, stale modes and
review diffs, symlinks, corrupt backups and newer managed edits. These fixtures
are explicitly synthetic; they do not substitute for historical public receivers.

The shared adopter is also projected as `PortalExample/manage.py`. Changing its
bytes initially made the existing Portal suite refuse the old helper digest in
`source-provenance.json`. The source delivery refreshes that one projected-helper
digest. It changes no Portal package closure, Game source, scene or API.
The unchanged Portal suite checks adoption/removal and its stronger late-conflict
controls. First failing source results are retained separately from the repairs.

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
