# Fable full-stack toolchain compatibility spike

**Status:** not qualified for template baseline

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

## Result: no coherent Fable.Remoting baseline yet

The current candidates do not form a qualified coherent set. The published
`Fable.Remoting.Client` 8.0.0 nuspec depends on `Fable.Core` 3.1.5, whereas the
current Fable compiler/toolchain uses Fable.Core 5.2.0. The current server is
6.1.0 and targets net8.0. A successful NuGet resolution would therefore not
prove that the client is supported by this compiler; taking it as a template
baseline would turn a transitive downgrade into a public promise.

This spike is consequently **red** for the required end-to-end qualification.
It did not claim a successful browser startup, production publish, bundle size,
or Fable.Remoting/SignalR exchange. These are deliberately recorded as
unmeasured rather than inferred:

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

