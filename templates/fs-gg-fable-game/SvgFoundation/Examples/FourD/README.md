# Pure local save/replay preparation

`LocalSaveReplayExample.fs` and `LocalSaveReplayExample.Tests.fs` are **source-only,
uncompiled and unconnected** preparation. Neither file is included in an `.fsproj`,
test runner, or browser mount. Their presence does not establish generated behavior,
source qualification, publication, installed adoption, or a complete player journey.
The existing `FourDReference.fs` remains the browser fixture.

The example uses the public Game.Core `SessionRuntime`, `ReplayRecorder` and `Replay`
surfaces selected by the template's unchanged **0.16.0** pin. API signatures and
producer behavior were reviewed at the [0.16.0 release source](https://github.com/FS-GG/FS.GG.Game/tree/996832a6ebb5c893199627b0ecc46f7c1da848cd/src/Game.Core)
(`SessionContract.fsi`, `SessionRuntime.fsi`, `Replay.fsi` and their implementations).
Package payload verification and compilation against the actual downloaded 0.16.0
package remain prerequisites for integration; source inspection is not that proof.

## Pure entrypoints

- `initialize agent legalDestination` creates a separately named synthetic session.
- `admit input example` sends semantic commands through the real session runtime and
  records only accepted commands. Runtime or recorder refusal returns the original
  immutable example. Caller supplied sequences determine order; devices and clocks
  do not enter the recording.
- `snapshot example` produces a versioned session payload. `restore snapshot example`
  checks session/schema/profile compatibility through SessionRuntime. Refusal retains
  the accepted runtime and recording. Success starts a fresh recording epoch at the
  restored payload: the producer resets sequence tracking and elapsed accumulation.
- `checkpoint example` adds a producer replay checkpoint after accepted events.
  The producer refuses event index zero and duplicate checkpoint positions.
- `replay targetEventCount recording` previews the producer's deterministic seek
  result. It does not commit returned state. Checkpoint seek can skip earlier events;
  replay without checkpoints exercises the full event sequence.

`InspectFullCell` appends an ordered synthetic inspection trace. The agent never
moves. All four signed coordinates are retained for both agent and destination.
This preserves the existing reference's absence of gameplay changes and does not
supply product rules or product save compatibility.

## Caller extension points

`Payload`, `Command`, contract callbacks and `stateDigest` illustrate caller-owned
domain meaning and serialization boundaries. The fixture digest is canonical text
of integer coordinates and ordered trace entries, used directly for comparison.
It is deliberately transparent and is not a cryptographic authenticity check.
A product must choose its own canonical codec, payload validation, hash and trust
policy. Neither a matching digest nor an edited synthetic identity authenticates a
save. No byte serializer, durable storage, clock, browser control or transport is
provided here. Session snapshots contain product payload, not a complete host or
runtime checkpoint.

SaveMigration is not used: exact-version restore refuses incompatible saves rather
than migrating them. Migration effects, asynchronous completions, disposal and stale
generation refusal need a later explicit integration if migration is selected.

## Finite conformance definitions and follow-up gate

`LocalSaveReplayExampleTests.run` defines snapshot/restore and four-coordinate round
trips; session/schema/profile refusal preserving accepted state; accepted semantic
order; illegal-coordinate and stale-sequence exclusion; altered event/payload/digest
detection; incompatible checkpoints; checkpoint seek and admission boundaries.
These are definitions, not reported passing tests.

The serial Templates integrator must verify actual package APIs, include the exact
source and tests in the existing compile/test route, compile and execute them, then
connect and qualify one genuine browser save/restore/replay journey. That later scope
owns project/descriptor/browser-test edits and normal generated receiver checks.
Publication and downloaded-only installed acceptance retain their separate gates.
