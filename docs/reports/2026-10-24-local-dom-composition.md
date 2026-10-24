# Local DOM composition cases (ADR-0096)

This executes the typed current-composition plan on delivered source for the first time. It is ordinary
development verification under [ADR-0096](https://github.com/FS-GG/.github/blob/main/docs/adr/0096-proportionate-verification-and-unrecoverable-holds.md)
section A: a local build and test of unpublished source in a fresh private root, with no credential,
no shared or remote destination (public NuGet and Playwright downloads are read-only) and no publication,
deployment, live-store, Home, VM or native-capability effect. It needs no Root runtime admission,
original clock or managed-group owner, and it changes none of them.

The held hosted route is unchanged: `ADMISSION=None`, a pre-checkout dispatch refusal and a literal-false
receiver job. A local pass does not open it, and it is not hosted, installed, published, producer-custody,
durable-save, assistive-technology or whole-#4818 acceptance.

## What runs

`tests/composition/fable-game/current-composition-local.py --root <fresh dir>` runs, with a closed child
environment and at most three CPUs:

1. the typed owner (`ProviderTool`) built into a private artifacts path, then `current-composition-plan`;
2. the exact public template and Rendering archives, fetched from nuget.org and refused unless their SHA-256
   equals the typed plan;
3. an independent Fable 5.18 install, whose member closure the stage joins to the receiver's restored tool;
4. the existing `current-source-stage` (generate the Complete receiver with the external reference on and WASM off,
   locked restore, Fable build, Vite build, authority-server publish, plan-bound Playwright config);
5. per browser family, a listing that must equal the nine typed file/suite/title identities, then the run with
   workers 1 and retries 0, whose report must show nine passes and no skip, flake or retry.

Node 24.20.0, npm 11.19.0 and SDK 10.0.401 are read from the hosted caller and refused if different.
Chromium, Firefox and WebKit are Playwright 1.63 stock builds. On a host without their shared libraries,
`--container IMAGE` runs only the browser phase in an Ubuntu 24.04 image from
`current-composition-local-image.sh`, with no network and Node, .NET, the receiver and the browsers bind-mounted
(Node and .NET read-only). `local-summary.json` binds each result to the checkout head and tree, and records `dirty` when `--allow-dirty` was used.

## Defects the first real execution exposed

The held source passed its pure controls but had never reached a real SDK or browser:

| Defect | Effect | Repair |
| --- | --- | --- |
| `dotnet new fs-gg-fable-game ... --package FS.GG.Workspace.Template` | `--package` is not an option of the shipped SDK, so the receiver could never be generated (exit 127). Its pure control used a fake `dotnet` that asserted the flag. | Removed. The custom template hive with SDK templates disabled already scopes the one installed package. The control now asserts the flag is absent. |
| The source stage exports `FsGgExternalReferenceCandidate` for the build only | The four opt-in command-outcome specs register no case in the separate Playwright process, so the listing held 5 of 9 identities and the managed route would have refused at its first family. | `browser_environment(plan)` derives both flags from the typed selection and is applied to every Playwright process in the managed route and the local runner. Controls assert the managed route passes them. |
| The Fable member-closure join needs an independent install | Not a defect of the held route (the managed caller supplies it); the local runner repeats it. | Installed by the runner from the pinned version and core hash. |

## Boundaries that remain

- `actualProducerCustodyReadback` stays false: the typed plan's archive hashes are compared with the published packages and
  the original Rendering custody JSON is a reference only.
- `localSaved` is the synthetic in-memory journey. Durable product save, the AT journey and the hosted original-operation
  route are separate obligations.
- Host-library gaps are solved by the container, not by weakening a case; a missing library fails the listing or run.
