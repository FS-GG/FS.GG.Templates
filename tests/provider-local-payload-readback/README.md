# Local template payload readback

This read-only comparison pins three *local files*: the selected native 0.14.0
candidate, a retained 0.14.0 release pack, and a signed NuGet-shaped local
readback. It compares every `content/templates/` member by exact name, body
SHA-256, and Unix mode. Python performs the bounded physical ZIP read, then
passes member records to the nonpackable F# `ProviderPayloadComparison` tool
for typed, pure comparison. F# requires exact 64-character lowercase hex body
digests, one root config, and at least one asset for each template root. It
refuses nested config-shaped members, file/child collisions (including case
aliases), and duplicate or foreign JSON fields. A matching template config
alone is never a payload match. F# also requires NFC member path spelling, so
decomposed Unicode cannot yield a payload match on a filesystem that may alias
it to a composed name. This is a member-name policy, not a proof that every
filesystem path alias is excluded. F# also refuses components ending in a
period or ASCII space, ASCII codes 0–31, reserved path punctuation, and Windows
device names (including names followed by an extension),
following [Windows file naming guidance](https://learn.microsoft.com/en-us/windows/win32/fileio/naming-a-file).
The signed file's signature is recognized by member presence; this script
does not verify its cryptographic signature.

```sh
python3 tests/provider-local-payload-readback/check.py \
  --selected /path/to/selected.nupkg \
  --release /path/to/retained-release.nupkg \
  --nuget /path/to/local-nuget-readback.nupkg \
  --github-http-status 403
```

`--github-http-status` is a caller-reported observation, not a feed fetch.
Without authenticated current GitHub Packages archive bytes, that feed always
has `NO_VERDICT`, including when the reported status is 200. A local NuGet
payload match is labeled `TEMPLATE_PAYLOAD_MATCH_ONLY`; neither local file
path proves current feed origin. The report cannot authorize producer
publication, package pinning, installation, or receiver adoption.
