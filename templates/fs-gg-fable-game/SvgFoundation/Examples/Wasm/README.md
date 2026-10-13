# Optional WASM policy advice

This source example composes the shared strict SC2 guest profile as an advisor.
It accepts opaque input/output bytes; the consuming domain owns their meaning.
Advice grants no native command capability and has no deterministic replay claim.

The interface selection is the coherent Contracts/Browser/guest SDK 0.3.0 set at
[producer 16a40169](https://github.com/FS-GG/FS.GG.Game/tree/16a401692f4c0dee7f6da1a86d0cd49e6ea3ec2c).
The published [`Host` interface](https://github.com/FS-GG/FS.GG.Game/blob/16a401692f4c0dee7f6da1a86d0cd49e6ea3ec2c/src/Wasm.Browser/Host.fsi)
owns Worker lifecycle. The strict profile rejects legacy direct-URL admission;
BAR has no advisor role capacity. This example uses default compatibility and
adds no scheduling or allocation policy.

## Compose the installed host

1. Supply the selected guest's actual artifact/configuration digests and bounded
   ceilings to `prepare`. Shape-valid test digests are fixtures, not guest identities.
2. Create the package-owned browser transport and pass it to `connect`. Deliver
   its callbacks to the same host owner. Package integration must materialize the
   complete Worker/ESM and generated policy assets under the deployment base.
3. Call `LoadConfigured` with a fresh Worker/request/generation identity and the
   selected artifact bytes. Wait for successful current compilation settlement.
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

These files are not yet wired into `SvgFoundation.fsproj`. The Templates integrator
owns project/dependency/descriptor changes after the exact producer acceptance
join. Producer H4 installed qualification is accepted in
[run 37191263989](https://github.com/FS-GG/FS.GG.Game/actions/runs/37191263989).
That producer proof does not qualify this new template example. Example compilation
and test execution, generated-workspace Fable/Vite/Worker/ESM/browser conformance,
template publication, fresh creation and any promised retaining upgrade remain
separate acceptance outcomes.
