# Genuine four-product qualification carrier

Recipe for the dedicated carrier that qualifies ONE once-packed `FS.GG.Workspace.Template` archive for
TypeScript, JavaScript, Rust and Go. Source CI proves mechanical package closure only; this run executes the
published SDD catalog scaffold and Governance Verify against the generated products on the exact host profile
the catalog route requires (Linux x64, .NET 10.0.12, SDK 10.0.401, glibc 2.44 with all 30 required exports).

Carrier: a rootless `podman --rootfs` container from a digest-pinned Arch userland image, packages from a
dated Arch Linux Archive snapshot, official digest-verified Go / Node / .NET archives, Rust through rustup,
`gcc` for CGO, `cargo-audit` 0.22.2 and `govulncheck` 1.9.0 from the same snapshot, and the published
`FS.GG.SDD.Cli` and `FS.GG.Governance.Cli` packages from nuget.org. All acquisition is credential-free and
read-only into a fresh root. Container storage is a private vfs store (the default rootless store is a small
tmpfs); every command runs under `taskset -c 0-3`. `pins.env` holds every pin.

```
eng/polyglot-qualification/provision.sh  <absent-root>                      # carrier + advisory snapshots
eng/polyglot-qualification/pack.sh       <root> <absent-output-dir>          # pack exactly as release.yml does
eng/polyglot-qualification/qualify.sh    <root> <archive.nupkg> <attempt>    # scaffold + Verify, all four
python3 eng/polyglot-qualification/collect-evidence.py <root> <attempt> <archive.nupkg> <evidence.json>
```

The admission inputs are independent of the archive and are recorded by digest in the evidence:
`make-policy.py` derives the catalog policy from the installed tools' own version output (it refuses any
tool that does not print its pinned version exactly once), and `governance-catalog/` is the workspace
Governance catalog that routes each declared capability to a provider-owned gate. Advisory databases must be
at most seven days old when the products run; `provision.sh` records their commits and epochs.

The release gate (`tests/composition/polyglot/verify-release-qualification.py`) accepts a polyglot archive only
when its payload identity is in `readiness/polyglot-qualification-acceptance.json`, which changes only by a
reviewed pull request after root accepts the evidence.
