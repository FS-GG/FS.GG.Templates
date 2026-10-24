# Current public D.5 receiver source

## Current status (2026-10-24)

The sections below were written while this source was held and are kept as history; where
they conflict with this status, this status wins. Root accepted the #4849 Delivery
([acceptance](https://github.com/FS-GG/.github/issues/4849#issuecomment-6388882515)) on three admitted originals:

| Original | Result |
|---|---|
| [40121103111/a1](https://github.com/FS-GG/FS.GG.Templates/actions/runs/40121103111) | Failed at the backend check: its fixture assumed a `work/d5-default/` tree that public SDD 2.4.0 does not write (fixed by Templates#778). Retained as failed evidence. |
| [40124373443/a1](https://github.com/FS-GG/FS.GG.Templates/actions/runs/40124373443) | Rehearsal passed: raw, provider and Wizard omitted receivers (3/3) with actual default `quint-specification-v1` author, inspect and wrong-profile refusal on both typed receivers. |
| [40127488229/a1](https://github.com/FS-GG/FS.GG.Templates/actions/runs/40127488229) | Full matrix passed: `current-d5-receiver-check` 43/43 (raw plus 42 provider/Wizard lifecycle-by-bundle cases), 129 managed groups (127 succeeded, 2 expected refusals), 12,612 evidence files. |

The first two namespace failures ([40047202735](https://github.com/FS-GG/FS.GG.Templates/actions/runs/40047202735),
[40057752243](https://github.com/FS-GG/FS.GG.Templates/actions/runs/40057752243)) were caused by AppArmor's
`kernel.apparmor_restrict_unprivileged_userns=1` on GitHub-hosted ubuntu-24.04 (A/B run
[40116649986](https://github.com/FS-GG/FS.GG.Templates/actions/runs/40116649986)). The workflow now runs one
hosted-only step, `sudo -n sysctl -w kernel.apparmor_restrict_unprivileged_userns=0`, after the capacity guard and before
the delegated unit, recording the value before and after. It refuses unless `RUNNER_ENVIRONMENT=github-hosted`; it is never
applied to Home or self-hosted machines, and NoNewPrivileges, namespace flags and backend are unchanged.
Each activation of the held entry needs a fresh Root conditional selection; every selection so far is consumed. The
workflow `scope` input currently offers only `full`.

Before an original is spent, run the receiver-side checkers offline against real tool output and the retained real
snapshots of the previous original, not only against synthetic fixtures.

Retained upgrades, product-native adoption, hosting and the other holds remain separate. This status carries the
D.5 claim only for the exact published SDD 2.4.0 / Wizard 0.22.0 / Workspace.Template 0.19.3 tuple.

This conditionally selected successor targets the remaining contract in
[organization issue #4849](https://github.com/FS-GG/.github/issues/4849), under
[the SVG release outcome](https://github.com/FS-GG/.github/issues/4644).
It selects public Workspace.Template 0.19.3, SDD 2.4.0 and Wizard 0.22.0.
The historical [D.5 route](svg-release-d5-public-default.md) keeps its original
versions and acceptance. Current [run 39988246429](https://github.com/FS-GG/FS.GG.Templates/actions/runs/39988246429)
retains its scoped clean-creation, four-build and dedicated-browser evidence;
this source does not repeat those product builds or browser runs.

(Historical: the direct shell script remains held; the Python runtime entry now binds the latest Root selection literal.)
The workflow had a [conditional root source selection](https://github.com/FS-GG/.github/issues/4849#issuecomment-6377028965)
for one manual/main/attempt1 rehearsal. No local flag grants an operation. Root still
requires exact source review, CI, protected delivery and one original native intent
before dispatch. Invalid admission/source/scope refuses before workload effects.
The direct script's `--preflight-only` reads bounded JSON but explicitly establishes
no typed qualification. Activating runtime requires a separately reviewed exact
source/main/attempt-1 admission and the existing maintained process owner with
genuine resource, terminal, descendant-retirement and evidence custody. A job
45-minute ceiling is not that seam. Receipts remain `unqualified` with retirement
unqualified; no shell exit or marker set establishes whole qualification.

The existing F# `ReferencePublication`/ProviderTool owner defines current pin,
selection/matrix, source/provenance and backend acceptance. Its current receiver
command checks genuine pinned public archive bytes, product source transformations,
providerName/templateRef, generator, product name, lifecycle and bundle (or the
verified published omission default). The historical receiver entry remains unchanged
in behavior. Actual SDD author and inspect are the backend semantic supplier.
Python only emits input data and observes bounded JSON, arguments, model members and
file hashes; it cannot replace the typed receiver decision.

The full file observation includes the model files, `readiness/d5-default` authority and
quint outputs, root configs, owner files and authority artifacts (public SDD 2.4.0 writes no `work/<id>` tree). Explicit exclusions are `.git`, `.nuget`,
`node_modules`, `bin` and `obj`. F# compares the complete observed population with
actual files and rejects changed/deleted canonical state, new refused-work outputs,
wrong producer/profile and missing/malformed evidence. Backend argument plans also
come from F# and deliberately omit `--backend` for the default proof.

Run the pure I/O and held-caller controls locally:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 tests/composition/fable-game/test-d5-current-public.py
```

They invoke the real held shell entry with workload sentinels and the actual snapshot
and argument observation consumers, including canonical mutation/deletion, partial
refused work and malformed plans. No CLR/network/product execution occurs. The focused
F# cases and existing historical controls in `ProviderComposition.Tests` must additionally
compile and pass in separately admitted source CI; no local compilation is claimed.

The prepared rehearsal describes three fresh receivers: raw SDK omission, provider
omission and Wizard omission. It checks Player contents and the orchestrated typed-sdd
roots, then actual default author/inspect and wrong-profile refusal for both roots.
Each Wizard owns a new hive, initially seeded only with the exact public 0.18.2 knowledge
overlay when required; its final registration must identify public 0.19.3 bytes.

The separately selected full matrix adds the four declared lifecycle tokens (`none`,
`sdd`, `typed-sdd`, `spec-kit`) with all five named bundles (`player`, `studio`, `tactical`,
`arcade`, `complete`) through provider and Wizard routes. The typed owner validates
choice declarations, source closure and actual provenance; unsupported/refused cells
remain gaps, never silently omitted. Rehearsal leaves this full matrix pending.
Complete-only reference contents establish no native/WASM/browser execution. (Historical: the full matrix has since passed as
original 40127488229, see the status above.)

The closed public tuple, immutable provider and installed tools use maintained
publication/installed-tool checks. No producer is packed or descriptor rewritten.
Retained upgrades, product-native adoption, hosting, exhaustive verification and whole
outcome acceptance remain separate. Historical failures and Unknown effects persist.

Preflight uses typed source controls and small pure actual-caller checks before any
costly receiver. No new supervisor, shared cache or retry state machine is introduced.
The corrected four pure controls took 0.547 seconds on the source host; this is local
validation cost, not measured runner savings. Actual dispatch and acceptance
remain pending with Programme/root and the same Delivery owner.

## Held managed transport

The current D5 entry delegates each SDK, tool, generator, validator and backend command
through the existing `wasm-installed-c.py` actual-caller loader and pinned Coordination
`eng/managed_group_owner.py` (`ac222065`, SHA256 `d846dbe1…`). It introduces no process
supervisor or mutable override of the shared caller. The direct shell now delegates to
this entry instead of retaining an unmanaged current-cohort execution path. The direct shell keeps its source hold. The workflow is conditionally selected
only through the fixed root comment and manual/main/attempt1 gates; source delivery
and a separate original native selection are still required.

The independently reviewed PR765 reader is an explicit source dependency. Its narrow
caller-contract extension preserves the retained4816 defaults and supports only the
additional D5 admission, workflow, unit, clock, owner checkout and evidence namespace.
The original first-step clock, complete ancestor capacity screen, selected-unit
accounting, original InvocationID/process birth/cgroup join and independent post-unit
readback use that same maintained controller. Its old admission and original failures
are retained at their own scope. The expanded touch-set was selected after direct reuse
proved to require impersonating4816 or mutating module globals; neither is used.

The proposed first serial rehearsal has an enforced two-CPU,8GiB,512-task delegated
unit, no swap, a30-minute runtime and35-minute outer workflow horizon. Setup720s,
generation360s and backend480s use cumulative original deadlines; collection120s,
cleanup30s and overhead90s complete the1800s envelope. The capacity screen retains the
existing two-CPU/10GiB available-memory/20GiB staging floors. These are proposed limits,
not measured D5 demand or a claim the full matrix fits. Every managed group still needs
contained, empty-and-removed, reaped and EOF-qualified retirement; the independent outer
readback cannot infer success from a shell exit. Receipts remain retirement-unqualified
until that separate readback and root acceptance. Full-matrix resource fit remains a
separate admission prerequisite.

SDK401 provisioning, validator locked restore/build arguments, public/installed tool
checks and typed D5 cases are reused. Validator outputs use a private artifacts root.
The public SDK, NuGet and generator input domains remain closed. Go1.24.1 uses the fixed
official archive SHA256 `cb2396ba…` with a direct, nonredirecting managed download;
canonical LMT compilation must reproduce `37e0b036…`. No shared URL allowlist is patched.
(Historical: superseded. The namespace probe needs the reviewed hosted-only AppArmor sysctl step described in the status
above; any other host mutation still needs its own admission.)

The expected wrong-profile command deliberately has a positive nonzero exit. Its
consumer retains the original failed managed receipt and stdout instead of changing the
process outcome to success. It accepts only that exact typed `d5-refused` plan, the
installed-core input hash, matching profile/argv, the ordinary command-exit first cause,
no additional failure, contained empty retirement, reaping and uncapped EOF streams with
matching original bytes. Signals, timeout, escape, missing receipts, cleanup/reporting
failure and unexpected success refuse. This establishes only a transport result. The
existing F# backend check must still authenticate the actual blocked diagnostic,
unchanged paths, authored authority and complete owner-file population.

Evidence collection reuses the maintained copier with a separate D5 inventory, a20,000
file/512-group ceiling and1GiB aggregate cap; retained4816 limits stay unchanged. It keeps
public input archives, actual group receipts/logs, generated receiver/authority files,
source seals and before/after observations. Missing or over-budget evidence cannot
qualify. The rehearsal contains three receivers; the full selector retains raw omission
plus all42 typed-owner cases. No browser or product build is repeated here.

Pure controls cover the actual held entry, transport delegation, narrow failed-receipt
consumer, first-failure handling and causal cross-caller admission/clock/evidence/output
joins. Fixtures are synthetic; they establish no SDK/backend/runtime acceptance. Normal
source review and CI remain required, followed by a separately admitted first genuine
rehearsal. The complete4849/4644 acceptance and all historical Unknown holds remain open.

## Preparing the first genuine operation

The compiled preflight now belongs only to pull requests. A manual receiver has no
compiled-preflight dependency: its own first-step clock and exact source admission
precede its managed unit and every SDK/Go/package acquisition. The fixed [root conditional source grant](https://github.com/FS-GG/.github/issues/4849#issuecomment-6377028965)
now selects only manual/main/attempt1 rehearsal source. It starts no runtime clock or
dispatch: exact review/CI/protected delivery and Root's fresh one-send intent remain
required. An unused selection expires at01:15UTC on2026-10-24.
(Historical: the first grant covered only `rehearsal`; the full matrix was later selected separately and passed, see the status above.)

The existing managed sandbox probe now precedes all asset acquisition, immediately
after the owner/unit/capacity guards. It uses the published SDD2.4 launcher and arguments
(`/usr/bin/unshare --user --map-root-user --net -- /usr/bin/true`) with the backend's
cleared `LANG=C.UTF-8`, `TZ=UTC` child environment. It changes no host policy. The actual
new VM's user-namespace, network-namespace, seccomp and AppArmor availability remains
Unknown until an admitted probe succeeds on that same host. A failure stops the original
operation; there is no fallback, sysctl toggle or renewed clock. Successful probing alone
would establish no actual author/inspect/refusal or full D5 acceptance.

The separately accepted [retained rehearsal40032045163/a1](https://github.com/FS-GG/.github/issues/4816#issuecomment-6375942312)
proves only its real0.13-to0.19.3 materialization/adoption, one locked restore, scoped
transaction controls and17 managed-command/outer-retirement joins. It supplies neither
this sandbox prerequisite nor current SDD2.4 backend acceptance. Its original failure,
provider physical-disposal Unknown and wider4816 promises remain separate.

Root's final dispatch must supply fixed `selected_utc`, `latest_start_utc` and
`observer_deadline_utc` inputs, exactly300 and2400 seconds after selection. The earliest
receiver step records these original values together with native UTC, monotonic time,
boot and source/run/attempt identity. It refuses an expired or before-selection start,
a wrong interval, or less than2100 seconds remaining before checkout. The observed
UTC-to-monotonic observer projection is stored once; later capacity/unit/readback guards
use the smaller original deadline and never renew it from a later clock read. Refused
first-clock metadata is retained even when checkout/admission never runs. Existing
primary failures and bounded terminal metadata remain retainable after expiry.

These checks use Root and native-runner wall-clock trust. Their skew and uncertainty are
not independently authenticated; this source claims no zero-skew or cryptographic UTC
guarantee. Contradictory timestamps or missing/cross-source evidence refuse. An expired
queued original stays in its original custody with no second POST or new clock.

The current conditional selection6377028965 replaces the unused6376768563 source
selection before publication. No D5 dispatch, possible-send intent or runtime clock
began under the earlier selection; no operation clock is renewed. Actual protected
DOM deliveryb5e72ede is integrated by ancestry. Its functional repairs remain intact;
only its shared-reader/D5 dependency seals follow this D5 source update.
