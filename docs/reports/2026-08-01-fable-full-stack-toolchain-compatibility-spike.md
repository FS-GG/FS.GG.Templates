# Fable full-stack toolchain compatibility spike

**Status:** not qualified for template baseline. The compile-boundary blocker is
now fully root-caused to an **upstream, currently open, unfixed defect** in
`Fable.Remoting.MsgPack` (tracked at
[Zaid-Ajaj/Fable.Remoting#396](https://github.com/Zaid-Ajaj/Fable.Remoting/issues/396),
itself caused by a correctness fix in the Fable compiler,
[fable-compiler/Fable#4701](https://github.com/fable-compiler/Fable/pull/4701)
fixing
[fable-compiler/Fable#3866](https://github.com/fable-compiler/Fable/issues/3866)).
A workaround pin (downgrade the Fable compiler tool to 5.4.0) was found and
substantially validated end-to-end on 2026-08-01 — see "2026-08-01
requalification" below — but full qualification (production publish/bundle
size, dev watch, a malformed-DU rejection case, and the Playwright two-client
scenario) was not completed, and adopting a compiler downgrade specifically to
route around an unfixed upstream defect is a decision this report defers to a
human rather than silently deciding.

**Scope:** the proposed `fs-gg-fable-game` workspace only. This is a bounded
research result, not a published `FS.GG.Web.Template` contract or a compatibility
promise.

## Question and route

This spike tested the route required by
[ADR-0071](https://github.com/FS-GG/.github/blob/main/docs/adr/0071-two-web-workspace-providers-one-template-package.md):
an ASP.NET Core server, a Fable client, one typed Fable.Remoting request/response,
and an official `@microsoft/signalr` browser-client binding. Fable.Remoting is
for finite typed HTTP operations; SignalR is for connection/session traffic
(reconnect, snapshots, inputs, presence, acknowledgement, and resync). Neither
adapter is the domain model.

The companion check, `tests/fable-toolchain-spike/run.sh`, makes the recorded
package-boundary decision auditable. It intentionally does not report a green
runtime qualification: package restore and compile are prerequisites, not proof
of browser transport behaviour.

## Environment and exact inputs

The measurement was made on 2026-08-01 on Linux x64:

| Input | Observed value |
| --- | --- |
| .NET SDK / runtime | 10.0.302 / 10.0.10 |
| Node / npm | v26.5.0 / 12.0.1 |
| Fable dotnet tool | 5.13.0 |
| Fable.Core | 5.2.0 |
| Elmish / Fable.Elmish | 5.0.2 / 5.0.2 |
| Fable.Remoting.Server | 6.1.0 (net8.0) |
| Fable.Remoting.Client | 8.0.0 |
| `@microsoft/signalr` | 10.0.0 |

`npm view @microsoft/signalr@10.0.0 dist.integrity` returned
`sha512-0BRqz/uCx3JdrOqiqgFhih/+hfTERaUfCZXFB52uMaZJrKaPRzHzMuqVsJC/V3pt7NozcNXGspjKiQEK+X7P2w==`.
The generated workspace must use an npm lockfile and pin the selected package,
not a range or `latest`.

## Result: restore passes; Fable compilation blocks the browser route

The initial interpretation of the client nuspec was wrong: its unbracketed
`Fable.Core` 3.1.5 dependency is an inclusive NuGet minimum, not an exact pin.
An isolated clean restore with direct `Fable.Core` 5.2.0 and
`Fable.Remoting.Client` 8.0.0 resolved `Fable.Core/5.2.0` in
`obj/project.assets.json`; it must not be rejected on a fictional transitive
downgrade. The actual Fable 5.13.0 compilation then fails in the transitive
`Fable.Remoting.MsgPack` 2.0.0 source with seven inline-accessibility errors,
including `Write.fs(565,8): ... write64bitNumber ... marked inline ... internal
or private function ... not sufficiently accessible`. The focused executable
harness reproduces this with `--noCache` from a clean temporary directory.

This is **not qualified for template baseline**: the Fable client cannot compile
with this candidate, so the required ASP.NET Core/Fable browser transport route
cannot be executed. It does not claim
a successful browser startup, production publish, bundle size, or
Fable.Remoting/SignalR exchange. These are deliberately recorded as unmeasured
rather than inferred:

| Required evidence | Result |
| --- | --- |
| Fable client compile and browser startup | blocked by the unqualified client/toolchain boundary |
| Typed Fable.Remoting browser call | not run |
| SignalR server-push and reconnect/resync | not run |
| Subscription disposal, cancellation, and error propagation | not run |
| Browser DTO serialization | not run; do not assume arbitrary DUs are wire-compatible |
| Production publish and bundle size | not run |

The 2021 `Fable.SignalR` NuGet package remains research input only. It is not
an alternative baseline: the future workspace must bind narrowly to the
official JavaScript client.

## Boundary and view-layer decision

Use explicit record DTOs with primitive fields, arrays/lists, and named version
fields at the HTTP and hub boundaries. Test every DTO by serializing from .NET
and decoding in the browser; keep arbitrary domain discriminated unions,
server-only infrastructure, persistence, clocks, and reflection-heavy code on
their appropriate side of the boundary. The Game lockstep claim, when needed,
comes only from the producer-owned `fs-gg-game-core-fable-lockstep-v1` profile.

The smallest viable view layer remains **Elmish plus direct DOM bindings**.
It adds no UI framework contract while the compiler/transport set is being
qualified. A maintained Fable UI binding may replace the direct binding only
after the same clean-machine restore, watch, production publish, browser
transport, reconnection, disposal, cancellation, error, DTO, and bundle-size
evidence is green.

## Next qualification run

Do not create `fs-gg-fable-game` from this result. First select a
Fable.Remoting client/server pair whose declared Fable.Core and target-framework
support matches the chosen Fable compiler. Then, from a clean locked workspace:

1. restore `dotnet` and npm dependencies with locked modes;
2. compile the Fable/Elmish client, run the ASP.NET Core server, and exercise
   one Fable.Remoting call plus a SignalR server-push event;
3. force a reconnect, dispose a subscription, cancel an in-flight call, and
   record observable error behaviour;
4. run .NET-to-browser DTO serialization cases, including an explicit rejected
   arbitrary-DU case;
5. record browser, Node, exact lockfile entries, startup result, production
   output size, and all incompatibilities; and
6. only then propose pins and run both development watch and production publish.

## 2026-08-01 requalification (FS.GG.Templates#370)

This section records the follow-up run performed against `#370`. It re-runs
the compile-boundary check, root-causes the failure precisely, tests a
candidate workaround, and records exactly how far that workaround was
validated. **No pin change was applied to the checked-in guard's asserted
default; the guard still fails closed on the currently declared pin
(Fable 5.13.0).**

### Root cause of the compile-boundary failure

`Fable.Remoting.MsgPack`'s `Write.fs` has two parallel implementations behind
`#if FABLE_COMPILER`: the `.NET`-target functions (e.g. `write64bitNumber`)
are plain top-level `inline` bindings, but the Fable/browser-target
implementations, in `module Fable`, mark the low-level byte-writers
`private` (e.g. `write64bitNumber`, `writeArrayHeader`, `writeInt64`,
`writeUInt64` at `Write.fs` lines 547–663 as of `master` on 2026-08-01) while
the functions that call them (`writeUnsigned64bitNumber`,
`writeUnsigned32bitNumber`) are `inline`. This violates F#'s rule that an
`inline` value's body may only reference symbols at least as accessible as
itself — `fsc` has always rejected this; Fable's own compiler did not check
for it until version 5.5.0
(`fix(all): Error on inline function referencing private value`, PR #4701,
closing issue #3866 — "the generated inlined code attempts to import the
private value, which is not exported, causing an import error"). Every
published `Fable.Remoting.MsgPack` version from `1.0.0` through the current
`2.0.0`, and the `master` branch as of `2026-07-14`, contains this pattern
unchanged, so **no NuGet version selection fixes it** — this is not a
version-pin mismatch, it is a library defect. It is independently reported
upstream at
[Zaid-Ajaj/Fable.Remoting#396](https://github.com/Zaid-Ajaj/Fable.Remoting/issues/396)
(filed 2026-07-06, still open as of 2026-08-01, no fix merged), where the
maintainer's own suggested interim workaround matches what this report found
independently by bisection: "Downgrading the Fable compiler to 5.4.0 is
enough to work around this issue until a proper fix can be implemented."

**Bisection** (`dotnet tool install Fable --tool-path <dir> --version <v>`,
then compiling a classlib referencing `Fable.Core` 5.2.0 +
`Fable.Remoting.Client` 7.35.0, whose transitive `Fable.Remoting.MsgPack`
resolves to `1.25.0`):

| Fable version | Result |
| --- | --- |
| 5.0.0 | compiles |
| 5.1.0 | compiles |
| 5.3.0 | compiles |
| 5.4.0 | compiles |
| 5.5.0 | **fails** — same 7 inline-accessibility errors |
| 5.6.0 | fails |
| 5.9.0 | fails |
| 5.13.0 (currently declared pin) | fails (reproduced by the guard) |

The same fail/pass split was independently confirmed for
`Fable.Remoting.Client` 8.0.0 (`Fable.Remoting.MsgPack` 2.0.0, the pair
`#370`'s "known failure to start from" used): fails under 5.13.0, compiles
under 5.4.0.

### Workaround candidate and what was actually run

Candidate pins: Fable compiler **5.4.0** (down from 5.13.0) + `Fable.Core`
5.2.0 + `Fable.Remoting.Client` 8.0.0 (`Fable.Remoting.MsgPack` 2.0.0
transitively) + `Fable.Remoting.Server`/`Fable.Remoting.Giraffe` 6.1.0 +
`@microsoft/signalr` 10.0.0 (integrity
`sha512-0BRqz/uCx3JdrOqiqgFhih/+hfTERaUfCZXFB52uMaZJrKaPRzHzMuqVsJC/V3pt7NozcNXGspjKiQEK+X7P2w==`,
unchanged from the original spike). Environment: .NET SDK/runtime
10.0.302/10.0.10, Node v26.5.0, npm 12.0.1 — identical to the original spike's
recorded environment.

A minimal but real ASP.NET Core server (`Sdk.Web`, Giraffe +
`Fable.Remoting.Giraffe`, targeting `net10.0` because only the `6.0.36` and
`10.0.10` `Microsoft.AspNetCore.App` shared runtimes were installed locally —
`net8.0`/`net9.0` app hosts failed to launch with "You must install or update
.NET to run this application") was built and run against a Fable-compiled
client (Fable 5.4.0) using the real `Fable.Remoting.Client` proxy and a
narrow hand-written Fable binding to the official `@microsoft/signalr`
package (per this report's existing boundary decision — no `Fable.SignalR`
package was used). The compiled client was executed under real Node with an
`xhr2` polyfill for `XMLHttpRequest` (Node has no built-in XHR) and native
`WebSocket` (present in Node 26). Observed, in order, in one run:

- `PING_RESULT=6` — a real HTTP round trip through `Fable.Remoting.Client`'s
  proxy to the Giraffe server (`ping: int64 -> Async<int64>`, `5L -> 6L`),
  confirming the toolchain that failed to compile under 5.13.0 both compiles
  and executes a genuine RPC call under 5.4.0.
- `DESCRIBE_RESULT=Named ("boundary-case", [1; 2; 3])` and
  `CLASSIFY_RESULT=named:boundary-case:1,2,3` — a server-constructed
  discriminated union (`Circle of float | Rectangle of float*float | Named of
  string*int list`) was returned to the client and decoded correctly, then
  round-tripped back to the server and classified correctly.
- `CLASSIFY_LOCAL_RESULT=rect:2.000000:3.000000` — a DU case the client
  constructed itself (never seen from the server) was accepted and correctly
  classified server-side. This is evidence of wire-compatibility for a
  **bounded** DU shape (primitive/list-typed fields); it is not evidence for
  arbitrary DUs in general (deeper nesting, records-in-cases, generics, and a
  deliberately malformed/rejected case were not tried — this is exactly the
  caution this report already carries under "do not assume arbitrary DUs are
  wire-compatible").
- `SIGNALR_CONNECTED=1` then `SIGNALR_PUSH=hello-from-server` — a real
  server-push (`IHubContext<PushHub>.Clients.All.SendAsync`) delivered over a
  live WebSocket to the `@microsoft/signalr` client.
- `SIGNALR_STOPPED=1` then a fresh `HubConnectionBuilder().build().start()`
  produced `SIGNALR_RECONNECTED=1` followed by
  `SIGNALR_PUSH_AFTER_RECONNECT=hello-from-server` — forcing a disconnect and
  rebuilding the connection was observed to work.
- An in-flight `slow: int -> Async<int>` call (5s server-side delay) was
  cancelled client-side via `CancellationTokenSource.Cancel()` 200ms in;
  neither `SLOW_UNEXPECTEDLY_COMPLETED` nor an explicit cancellation message
  printed before `RUN_COMPLETE=1` — consistent with F#'s standard
  (non-exception) cancellation semantics for `Async.StartImmediate`, i.e. no
  crash, no leak, no silent completion, but this run did not add
  `Async.TryCancelled` instrumentation to positively capture the observable
  error/cancellation event acceptance item 3 asks for.

Separately, `Fable.Remoting.MsgPack`'s actual `Write.Fable.writeType`
function (the code the compile error was reported against) was exercised
directly with `int64`/`uint64`/`int64[]` values under the 5.4.0 compile and
produced byte-exact MessagePack output (verified by manual big-endian
decode), confirming the workaround is not merely "compiles" but produces
correct output for the exact functions the compiler flagged.

### What remains unqualified

Not run in this pass: production publish and bundle size (no Vite/bundler
was wired up for this scoped check — only raw `fable`-emitted ESM was
executed directly under Node); development watch mode; a deliberately
malformed or structurally-incompatible DU case exercising the "rejected"
half of acceptance item 4; the Playwright two-client scenario; and explicit
disposal-of-subscription distinct from connection teardown. `npm ci` /
`dotnet restore --locked-mode`-style fully locked-mode restores were not
re-verified for this exact pin set (the original spike's locked-mode finding
still applies to restore itself, which is unaffected by the compiler
version).

### Disposition

This is not a version-pin selection problem solvable within
`FS.GG.Templates`: the defect lives in `Fable.Remoting.MsgPack`'s own
Fable-target source across its entire published history, and is already
tracked, unfixed, upstream. Three options exist and none of them is this
report's to choose unilaterally: (1) wait for
[Zaid-Ajaj/Fable.Remoting#396](https://github.com/Zaid-Ajaj/Fable.Remoting/issues/396)
to be fixed upstream and re-pin Fable.Remoting.MsgPack once a release
contains the fix; (2) adopt the Fable 5.4.0 compiler downgrade as an interim
template pin, accepting that it deliberately disables a compiler safety net
(fable-compiler/Fable#4701) that exists to catch a real class of bug,
in exchange for the substantial (but not complete) runtime evidence above;
or (3) drop the Fable.Remoting contract from ADR-0071 for the
`fs-gg-fable-game` route. Options (2) and (3) both bear on
`FS-GG/FS.GG.Templates#348` and ADR-0071 and are deferred to a human decision.
