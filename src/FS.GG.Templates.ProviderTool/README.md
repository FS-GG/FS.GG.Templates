# Provider composition source pilot (FSC-05)

This nonpackable F# command is a read-only source candidate. It does not replace
`scripts/check-provider-floors.py`, `scripts/generate-effective-providers.py`, the
composition workflow, or the published workspace template. Run it beside those
receivers while its contract and installed boundary are qualified.

```sh
dotnet run --project src/FS.GG.Templates.ProviderTool -- grade \
  --providers providers --registry ../.github/registry/dependencies.yml
dotnet run --project src/FS.GG.Templates.ProviderTool -- effective-check \
  --provider providers/rendering.providers.yml
dotnet run --project src/FS.GG.Templates.ProviderTool -- workspace-check \
  --providers providers --workspace generated/.fsgg/providers.yml \
  --registry ../.github/registry/dependencies.yml
bash tests/provider-tool/run.sh
```

`grade` enumerates `*.providers.yml` and compares each declared floor with the
organization registry's `fs-gg-ui-template.minimum-fsgg-sdd.version`. With no
`--registry`, it reads the registry at `main`; an unreachable registry fails.
`effective-check` validates an existing generated summary without writing it.
`workspace-check` accepts only known provider names whose identity, package
source, contract version, and floor match this repository's descriptor set,
and checks every owner descriptor floor against the registry pin, including
providers omitted from the requested workspace selection. It reads the live
registry by default and fails if that authority is unavailable.
The `nameParameter` and `identifierParameter` routing scalars also match the
owner descriptor exactly; changing either can direct generated identity bytes
to a different parameter even when the package source and floor stay the same.
Run `python3 tests/provider-routing-identity/run.py` for disposable route-drift,
duplicate-key, and malformed-value refusals.
The current narrow parameter declarations (`key`, `required`, optional
`default`) also participate in identity comparison. Duplicate or unsupported
provider and parameter fields refuse. The pure `resolveParameters` function
rejects unknown or repeated requests, requires missing mandatory values, and
applies declared defaults in descriptor order. Its UTF-8 effective-summary
projection is checked against bytes independently rendered by the Python
generator.
It does not assert installed workspace byte identity or application of every
descriptor parameter by the scaffold receiver.
The pure selector in `Composition.fs` validates the known and requested provider
sets before the read-only workspace and summary checks. It rejects unknown or
duplicate providers, invalid names or floors, and identity drift, and renders
the summary deterministically. Run its independent controls with
`dotnet run --project tests/ProviderComposition.Tests -c Release`.

The parser intentionally accepts the current narrow descriptor layout. Before
any receiver switch, qualify remaining YAML edge cases and installed workspace parameter semantics,
the producer artifact boundary, CLI output compatibility, installed bytes, and
the full independent Python fixture corpus. A source-only PR does not make those
claims or authorize a receiver flip.

The focused source controls refuse malformed provider/floor indentation, JSON
where a provider YAML descriptor is required, and a directory or dangling link
named `*.providers.yml`. A symlink to a readable descriptor file is still
accepted by both this candidate and the live Python floor checker; any future
physical-source closure rule must be introduced and requalified at both owners.
