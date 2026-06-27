# Design: composing SDD + Governance + Rendering

## Why this repo exists

A "full-stack" FS.GG product wants three things at once:

- the **FS.GG.SDD** spec-driven lifecycle (skeleton + `fsgg-sdd` commands),
- a runnable **FS.GG.Rendering** app (Skia/OpenGL + Elmish/MVU), and
- **FS.GG.Governance** rule/evidence/gate config.

None of the three product repos can own that combination, because they are
deliberately decoupled:

- **FS.GG.Rendering never depends on Governance** (org-stated) — so a combined
  template cannot live in the rendering template.
- **FS.GG.SDD stays provider-agnostic** — generic SDD must contain no
  Rendering/Governance package id, template id, path, or docs URL (FR-002 / SC-005).
- **FS.GG.Governance is the optional downstream**, not an upstream that ships product
  templates.

`FS.GG.Templates` sits **downstream of all three** and composes them as a plain
consumer, with no reverse coupling back into any product.

## Approach: compose, don't fork

`dotnet new` cannot include or depend on another template, so a single monolithic
"everything" template would have to **vendor the entire `fs-gg-ui` rendering tree**
into this repo — forking it and going stale whenever Rendering changes. We
deliberately do **not** do that.

Instead the full-stack experience is a thin composition over the products as they
ship:

1. **SDD skeleton + full Rendering app** — `fsgg-sdd scaffold --provider rendering`
   drives FS.GG.Rendering's own `fs-gg-ui` template through the SDD scaffold contract.
   SDD contributes the skeleton; the provider contributes the full, current rendering
   surface (owned and maintained in FS.GG.Rendering).
2. **Governance config** — applied *after* scaffold via the `fs-gg-governance`
   `dotnet new` template here, which drops `.fsgg/policy.yml` / `capabilities.yml` /
   `tooling.yml`. It runs after scaffold (not as the provider) so it is not flagged by
   scaffold's SDD-tree guard, which forbids a *provider* from writing into `.fsgg/`.

[`scripts/new-fullstack.sh`](../scripts/new-fullstack.sh) glues the steps into one
command.

## Contents

- `templates/fs-gg-governance/` — a real `dotnet new` template that activates
  Governance in any project (validated: emits the three `.fsgg/*.yml` configs with a
  `--defaultProfile` choice).
- `providers/rendering.providers.yml` — a drop-in SDD provider registry entry pointing
  `fsgg-sdd scaffold` at `fs-gg-ui` (set `source` to a local path or NuGet id).
- `scripts/new-fullstack.sh` — the one-command composition.

## Open item: the Rendering template `source`

`fs-gg-ui` is not yet published to a feed reachable here, so `source` in the provider
registry is a placeholder (`__RENDERING_TEMPLATE_SOURCE__`). Point it at a local
checkout of FS.GG.Rendering, or at the template's NuGet package id once published.

## Alternative considered: a single vendored template

A monolithic `dotnet new fs-gg-fullstack` that emits all three at once is possible by
copying `fs-gg-ui`'s content into this repo and layering SDD + Governance on top. It
gives a single `dotnet new` invocation, but forks the rendering surface and duplicates
maintenance. If a single self-contained template is required (e.g. for users without
the `fsgg-sdd` CLI), it should pull the rendering content from a published `fs-gg-ui`
package rather than a hand copy.
