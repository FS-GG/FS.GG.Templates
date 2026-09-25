# Local template payload readback

This read-only comparison pins three *local files*: the selected native 0.14.0
candidate, a retained 0.14.0 release pack, and a signed NuGet-shaped local
readback. It compares every `content/templates/` member by exact name, body
SHA-256, and Unix mode. Python performs the bounded physical ZIP read, then
passes member records to the nonpackable F# `ProviderPayloadComparison` tool
for typed, pure comparison. A central directory name flagged as UTF-8 but
containing invalid UTF-8 bytes yields `NO_VERDICT` during physical read,
before typed comparison. The physical reader also refuses unsafe paths in
every ZIP member, including ASCII controls and reserved punctuation outside
`content/templates/`, as well as trailing dot or space path segments. It
refuses reserved device stems in any path segment, non-regular members, and
case-aliased file/child collisions outside the template payload. The pinned
signed file's signature metadata is handled explicitly.
Every path segment has the same 255 UTF-8-byte observation bound as the typed
template comparator; this does not establish the receiver filesystem limit.
All ZIP member names must be NFC and NFKC under Python's pinned Unicode data,
including names outside the template payload. This is a name refusal rule,
not proof of receiver filesystem alias behavior. Names with full case-fold
expansions are also refused across the archive. The physical reader refuses a
Python Unicode database version other than 16.0.0. Every ZIP member body is
consumed under per-member and aggregate expansion bounds so a corrupt non-template
member cannot yield a payload-only match. The pinned local archives also
require a local-file header at byte zero and a zero-comment ZIP end record at
the end of the file; this refuses ordinary leading and trailing overlays
and unowned gaps between declared local members or before the central directory.
The readback refuses nonzero disk markers in the end record or central member
records. Both end-record entry counts must equal the number of parsed members.
Central member comments are refused; the three pinned local files have none.
This does not establish complete ZIP-format closure. Local-header
flags, compression methods, CRC, and size fields must match their
central-directory entries.
Data-descriptor form is refused because the three pinned archives use fixed
local fields; support for that form is outside this readback contract. The
pinned archives also have no local or central ZIP extra fields. Those fields
are refused because they can carry alternate member-name metadata. F# requires
exact 64-character lowercase hex body digests, one root config, and at least
one asset for each template root. It refuses nested config-shaped members,
file/child collisions (including case
aliases), and duplicate or foreign JSON fields. A matching template config
alone is never a payload match. F# requires NFC and NFKC member path spelling,
so decomposed Unicode and compatibility ligatures cannot yield a payload match
under those aliases, following [Unicode normalization guidance](https://www.unicode.org/reports/tr15/).
It also refuses the 104 Unicode 16.0 code points whose Python full case fold
expands to multiple code points, including `ß`, `ẞ`, and `İ`. This is a pinned
expansion rule, not proof of simple-fold parity or later Unicode versions, and
does not exclude every filesystem path alias. U+A7F1 receives an explicit
`NO_VERDICT` for the observed Python 16.0 versus .NET NFKC disagreement; no
acceptance is inferred from either runtime's classification. F# also refuses
components ending in a period or ASCII space, ASCII codes 0–31, reserved path
punctuation, and Windows device names, including extension forms. These rules
follow [Windows file naming guidance](https://learn.microsoft.com/en-us/windows/win32/fileio/naming-a-file).
Each member component also has an explicit 255 UTF-8-byte portability bound;
this does not establish the actual receiver filesystem limit.
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
