# Pure local save/replay preparation

`LocalSaveReplayExample.fs` is conditionally compiled in the Complete receiver
before `FourDReference.fs`, with `LOCAL_SAVE_REPLAY_EXAMPLE`; legacy selection
omits it. Default Player generation omits the example directory. The finite cases
and named xUnit entry link into Domain.Tests only when the example is present;
they do not enter the production browser compile graph.

The example uses the public Game.Core `SessionRuntime`, `ReplayRecorder` and `Replay`
surfaces selected by the unchanged **0.16.0** pin. The actual downloaded package's
API and consumed Fable implementation members match the [reviewed release source](https://github.com/FS-GG/FS.GG.Game/tree/996832a6ebb5c893199627b0ecc46f7c1da848cd/src/Game.Core).
The existing Release C source qualification repeats those data-driven mirror checks,
then builds a local candidate archive and generates the Complete receiver. Named
.NET execution, locked package identity and one nonretried browser case per family
are checked explicitly. Exact-candidate hosted qualification remains pending until
that workflow passes; static package/source checks alone do not qualify it.

The browser fixture adds four separate controls: **Synthetic inspect full cell**,
**Save synthetic local snapshot**, **Restore synthetic local snapshot**, and
**Replay synthetic local recording**. The live output describes accepted inspections,
restore and preview results. Save retains a versioned snapshot in memory; restore
starts a fresh recording epoch. The existing button listener owner removes all four
listeners on disposal, including listeners on retained detached controls.

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
The named xUnit entry invokes these definitions; hosted execution evidence is required before reporting them as passing.

The source workflow qualifies these controls in a generated Complete receiver through
production Fable/Vite and Chromium, Firefox and WebKit. It retains the named .NET
TRX, browser reports and locked package evidence. This is source-candidate composition
from a local archive. Durable persistence, product saves, public publication,
downloaded-only installed/retaining acceptance and actual screen-reader qualification
of the new controls retain their separate gates; whole GAME-TEMPLATE-01 remains open.
