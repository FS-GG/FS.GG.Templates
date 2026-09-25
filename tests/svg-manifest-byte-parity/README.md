# F# skill-manifest merge byte comparison

Run `bash tests/svg-manifest-byte-parity/run.sh`. It runs the #504 disposable
Python characterization, then asks the live Python `candidate_bytes` function
for four merged-manifest outputs. The F# test verifies the fixture archive SHA
and member bytes independently, then compares every output byte. Cases cover
an absent receiver manifest, foreign rows with nested values and Unicode IDs
that distinguish UTF-8 from UTF-16 ordering,
identity replacement inside a foreign row, and a candidate without optional
scaffold provenance.

F# controls also refuse duplicate JSON keys, duplicate preserved IDs, invalid
schema and UTF-8, a changed skill body, mismatched provenance, an unsafe skill
path, and duplicate candidate IDs. Floating-point JSON values fail closed
because Python's float rendering has not been qualified for byte parity.
Escaped surrogate sequences also fail closed until their decoding is proved
lossless across runtimes.
The merger is pure: callers supply archive and receiver bytes, and it makes no
filesystem changes.

The synthetic fixture does not establish installed parity. The NuGet.org-served
0.14.0 archive still differs from the selected native candidate hash, producer
custody remains unproved, and this pure output calculation does not make the
Python transaction or later rollback safe from concurrent path swaps.
