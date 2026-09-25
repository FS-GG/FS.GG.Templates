# Local template payload readback

This read-only comparison pins three *local files*: the selected native 0.14.0
candidate, a retained 0.14.0 release pack, and a signed NuGet-shaped local
readback. It compares every `content/templates/` member by exact name, body
SHA-256, and Unix mode. A matching template config alone is never a payload
match. The signed file's signature is recognized by member presence; this
script does not verify its cryptographic signature.

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
