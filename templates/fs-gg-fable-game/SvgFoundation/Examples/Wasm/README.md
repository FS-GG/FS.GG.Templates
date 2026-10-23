# Optional WASM policy advice

This source example composes the shared strict SC2 guest profile as an advisor.
It accepts opaque input/output bytes; the consuming domain owns their meaning.
Advice grants no native command capability and has no deterministic replay claim.

The interface selection is the coherent Contracts/Browser/guest SDK 0.7.0 set at
[producer 15e287d7](https://github.com/FS-GG/FS.GG.Game/tree/15e287d7c8884f088b7db41140f108f3f0136043) (`wasm/v0.7.0`).
The published [`Host` interface](https://github.com/FS-GG/FS.GG.Game/blob/15e287d7c8884f088b7db41140f108f3f0136043/src/Wasm.Browser/Host.fsi)
owns Worker lifecycle. The strict profile rejects legacy direct-URL admission;
BAR has no advisor role capacity. This example uses default compatibility and
adds no scheduling or allocation policy.

## Select the optional composition

The nonlegacy Complete bundle contains this example. `FsGgWasmPolicyExample` is
false by default; explicit true selects the public Contracts/Browser `[0.7.0]`
references, the browser adapter and a separate `Examples/Wasm/packages.lock.json`.
The ordinary player lock and dependencies remain unchanged. The opt-in NuGet
lock and independent Rust `Cargo.lock` contain actual qualified consumer outputs.
Regenerate and qualify them when their inputs change; absent locks refuse.

Once the actual public package restore/profile is admitted, generate the enabled
NuGet graph with `dotnet msbuild SvgFoundation.fsproj -t:GenerateWasmPolicyLock
-p:FsGgWasmPolicyExample=true`. This target performs force-evaluated, unlocked
Restore only and selects the separate opt-in lock path. It returns before project
compilation. Inspect and qualify the resulting genuine lock, then use ordinary
locked restore/build. A generation property does not bypass Build/Fable or locked
restore missing-lock checks.

Once SDK bytes and Cargo execution are admitted, run
`bash Examples/Wasm/build-guests.sh --generate-lock <sdk-archive> <wasi-sdk-root>`.
It verifies the pinned SDK and constructs the authored crate inside that SDK's
layout, runs `cargo generate-lockfile --offline`, copies the actual generated lock
back, and returns without compiling guests. The included lock was generated
through this route from the verified SDK layout.

After those prerequisites are accepted, run `bash Examples/Wasm/build-guests.sh` with the authenticated
SDK 0.7 archive and pinned WASI SDK 34 root. It builds independent C/Rust policy
inputs and C malformed/trap/loop controls. It acquires no tools or packages.
`FSGG_WASM_POLICY_EXAMPLE=true ./build.sh` then selects the example through
restore, Fable and the ordinary Vite production build. The default deployment
base is `/wasm-example/`; `FSGG_WASM_POLICY_BASE` can select another non-root base.
Serve the production output at that base for the existing Browser.Tests route.

`PolicyObservationV1` is exactly two bytes: version 1 and a visible choice 0–2.
`PolicyAdviceV1` is exactly three bytes: ASCII P, version 1 and a recommendation
0–2 (`hold`, `observe`, `wait`). This illustrative format belongs to the example;
it contains no product observations, commands or authoritative state. Invalid,
stale or failed output displays a refusal. The adapter grants no game effects.

`materialize-assets.py` checks the restored Browser archive against its public
SHA-256, compares every cached asset with its package member and checks relative
ESM imports before copying the complete package tree into
`obj/wasm-policy-public`. It merges ordinary owner `public` assets without changing
them and refuses collisions with the package/guest reserved paths. Guest outputs
live separately under `obj/wasm-policy-guests`. Repeat materialization accepts only
an unchanged generated-file manifest; foreign/modified output fails closed. The
default Vite build keeps its original implicit `public` directory and ignores
these generated `obj` trees, including after toggling the option off.
The Worker, policy, Contracts and Fable runtime keep their package owner. Generated
public assets and modules are excluded from template packing.

## Compose the installed host

1. Supply the selected guest's actual artifact/configuration digests and bounded
   ceilings to `prepare`. Shape-valid test digests are fixtures, not guest identities.
2. Create the package-owned browser transport and pass it to `connect`. Deliver
   its callbacks to the same host owner. Package integration must materialize the
   complete Worker/ESM and generated policy assets under the deployment base.
3. Call `LoadConfigured` with a fresh Worker/request/generation identity and the
   selected artifact bytes. Wait for successful current compilation settlement.
   Since 0.7.0 the strict profile's 250 ms guest deadline starts only when the Worker
   reports readiness; Worker startup has its own bound (default 5000 ms, refused as
   `WorkerStartTimeout`). Pass no enclosing deadline to this load: it would also cap
   startup (FS-GG/FS.GG.Game#727). The 0.7.0 package Worker is one self-contained
   bundle. `materialize-assets.py` binds it to the package's `worker-build.json` and to the
   exact archive bytes, and refuses the code-loading forms it detects lexically: module
   imports, dynamic `import()`, `importScripts`, nested Workers, `fetch`,
   `import.meta`, `eval` and `new Function`. The client may build only the bundle
   Worker.
4. Call `Initialize` with a fresh request identity for that Worker/generation.
   Wait for successful current initialization settlement before `Invoke`.
5. Give each invocation its own request identity and use `currentAdvice` with the
   expected identity and the host's current projection. Decode and validate the
   returned copy in the domain adapter. Retain refusal/fault evidence separately;
   do not automatically replay a timed-out or unknown invocation.
6. Call `Shutdown` for the guest export when applicable, then `Dispose` to settle
   owned resources. Replacement uses the host's explicit candidate
   prepare/initialize/validate/commit path. A retained callback must be checked
   again after replacement; an old generation cannot become current advice.

Independent C and Rust guests should import the exact selected SDK's helpers and
frozen SC2 exports. Guest authoring and package-only production Worker conformance
remain in the producer/integration qualification; this example contains no copied
SDK, product codec, guest binary or alternative execution harness.

## Source boundary

`WasmPolicyExample.fs` and its companion test definitions are prepared source.
The tests cover current/stale identities, initialization versus processing,
retained output ownership, faults/cleanup, freeze/replacement/disposal and the
actual host's configured-load/initialization/disposal sequence with inert effects.
Projection fixtures do not establish successful guest execution.

The opt-in NuGet and Cargo locks were regenerated for 0.7.0 from nuget.org and the
verified SDK 0.7.0 archive with clean caches, through `GenerateWasmPolicyLock` and
`build-guests.sh --generate-lock`. The complete enabled player and adapter were
typechecked and emitted with Fable 5.18.0. The independent C and Rust guests compiled
against SDK 0.7.0 with the pinned WASI and Rust toolchains. The tableless Rust output requires
no normalization; when a table is present, the SDK owns its removal.

With 0.7.0, the downloaded-only installed path was rehearsed locally: in an Ubuntu
24.04 container, with clean caches, limited to 4 CPUs by affinity, and from a locally
packed candidate of this source. Its production build passed the nine browser tests
in each of Chromium, Firefox and WebKit. These exercised the self-contained
package Worker, C/Rust advice, replacement and retained-advice refusal, shutdown,
explicit disposal, malformed candidate admission and malformed/trapping/looping
invocation refusal. Twenty cold loads per family, each in a fresh browser context,
all reached `ready`; the p95 from the "Load policy" click to `ready` was 34 ms in
Chromium, 47 ms in Firefox and 43 ms in WebKit. The rehearsal used the verified
browser archives, and Firefox ran with its content sandbox enabled. This profile
makes no product security claim.
Captured response bodies matched the production output where available; missing
bodies remain unknown. Owned Worker wrapper counts observe constructor and
termination calls, not native exit acknowledgments or detached navigation cleanup.
The earlier 23 pure/inert-host assertions qualify the two unchanged example source
files in their recorded .NET consumer separately from these browser tests.

Producer H4 installed qualification is accepted in
[run 37191263989](https://github.com/FS-GG/FS.GG.Game/actions/runs/37191263989).
That producer proof does not qualify this template example. Candidate generated
workspace conformance, template publication, fresh feed-installed creation and
any promised retaining upgrade remain separate acceptance outcomes.
