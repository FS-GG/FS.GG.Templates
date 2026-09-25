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
  --providers providers --workspace generated/.fsgg/providers.yml
bash tests/provider-tool/run.sh
```

`grade` enumerates `*.providers.yml` and compares each declared floor with the
organization registry's `fs-gg-ui-template.minimum-fsgg-sdd.version`. With no
`--registry`, it reads the registry at `main`; an unreachable registry fails.
`effective-check` validates an existing generated summary without writing it.
`workspace-check` accepts only known provider names whose identity, package
source, contract version, and floor match this repository's descriptor set.
It does not assert byte identity or application of every descriptor parameter.

The parser intentionally accepts the current narrow descriptor layout. Before
any receiver switch, qualify YAML edge cases and workspace parameter semantics,
the producer artifact boundary, CLI output compatibility, installed bytes, and
the full independent Python fixture corpus. A source-only PR does not make those
claims or authorize a receiver flip.

The focused source controls refuse malformed provider/floor indentation, JSON
where a provider YAML descriptor is required, and a directory or dangling link
named `*.providers.yml`. A symlink to a readable descriptor file is still
accepted by both this candidate and the live Python floor checker; any future
physical-source closure rule must be introduced and requalified at both owners.
