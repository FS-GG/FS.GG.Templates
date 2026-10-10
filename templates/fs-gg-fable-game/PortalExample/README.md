# Opt-in managed portal example

Generate the current Fable Game template with `--portalExample true`, independently
of its bundle and lifecycle. Omission or false excludes this directory; the legacy
`--svgFoundation` selector does not support it. This is a separately invoked .NET 10
headless game/server example. The browser player, ASP.NET authority, protocol and
ordinary workspace solution do not reference it.

```console
dotnet restore PortalExample/Consumer.fsproj --locked-mode
dotnet run --project PortalExample/Consumer.fsproj --no-restore -- --presentation
```

No argument runs the canonical traversal/replay checks. `--presentation` runs five
simulation ticks and twelve interpolated frames with stable entity ownership,
traveller reset and ordinary interpolation, yielding twenty-four area nodes and
points. An invalid argument prints usage and exits 2. Managed scene nodes do not
establish browser/raster output or cross-boundary collision support.

The independent project uses exact public package pins: Game Core/Physics.Box2D/Render
0.17.0, UI Scene/KeyboardInput 0.31.0, Box2D.NET 3.1.654, FSharp.Core 10.1.302. It has
no sibling projects or linked source; its committed lock is genuinely generated.
Workspace-local package caches may contain other versions for independent projects.
Run `python3 verify-package-boundary.py --presentation --preflight` from this directory
before restore, and omit `--preflight` afterwards to check actual assets and nuspecs.

`source-provenance.json` binds the vendored Game example/tool/project bytes to their
canonical producer revision. Do not locally edit them as a parallel physics model.
The template candidate direct route has passed generation, public seven-package restore,
build and default/presentation/invalid commands. Public template release and installed
provider acceptance are separate. Do not rerun scaffolding over an existing product.

## Retained adoption and removal

Use `manage.py` from a separately generated, qualified opted-in candidate outside the
retained workspace. Its bytes come from the template producer's existing transaction
helper. Initial adoption supports a real public pre-Portal `0.18.1` Fable Game workspace.
Supply the authentic public `FS.GG.Workspace.Template.0.18.1.nupkg` as the baseline;
its archive, source identity and unchanged ordinary project defaults are checked.
Inventory and review files and the new backup directory must be outside both workspaces.

```console
python3 CANDIDATE/PortalExample/manage.py portal-inventory CANDIDATE WORKSPACE PUBLIC-0.18.1.nupkg inventory.json review.diff
python3 CANDIDATE/PortalExample/manage.py portal-apply CANDIDATE WORKSPACE PUBLIC-0.18.1.nupkg inventory.json BACKUP
python3 CANDIDATE/PortalExample/manage.py portal-inventory CANDIDATE WORKSPACE PUBLIC-0.18.1.nupkg removal.json removal.diff --remove
python3 CANDIDATE/PortalExample/manage.py portal-remove CANDIDATE WORKSPACE PUBLIC-0.18.1.nupkg removal.json REMOVAL-BACKUP
python3 CANDIDATE/PortalExample/manage.py portal-recover WORKSPACE BACKUP
```

Review the inventory and diff before apply/remove. Only nine declared Portal files can
change; ordinary solutions, source, data, skills, lifecycle and locks are preserved.
Unowned managed destinations, edited owned files, links, stale inventory, wrong receivers,
forged candidate provenance and corrupt backup objects refuse. Removal unlinks only
unchanged owned files and preserves foreign files inside the folder. Recovery validates
all before/post states before restoring; if a concurrent edit prevents rollback, retain
the journal and resolve the reported conflict before explicit recovery. No recursive
folder deletion or overwrite of unknown edits is performed.

Fresh opted-in receivers establish the same ownership through authentic shipped
provenance. No prior public Portal successor exists, so this helper does not promise
Portal-to-Portal version upgrades. Synthetic transaction controls are separate from
real public retained adoption/removal acceptance; the latter requires its own admitted
receiver qualification. Canonical source/tool bytes and the seven-package lock remain
immutable producer inputs.
