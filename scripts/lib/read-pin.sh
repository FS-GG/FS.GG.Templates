#!/usr/bin/env bash
# The single most load-bearing value in this repo is the FS.GG.UI.Template version pin —
# recorded once in providers/rendering.providers.yml on the `source:` line as
# `FS.GG.UI.Template::<ver>`. It selects the published UI package the scaffold installs.
#
# Three call sites read it: the composition test (tests/composition/run.sh, "verify —
# rendering provider pin coherence"), the re-pin primitive (scripts/bump-rendering-pin.sh),
# and the dev repack (scripts/dev-repack-ui-feed.sh). They used to each carry an identical
# `grep -oE 'FS\.GG\.UI\.Template::[^ ]+' | head -1 | sed 's/.*:://'` (review A2, issue #60) —
# now they source this one parser instead, so the repo has a single definition of how the pin
# is read. Change the pin's encoding once, here.
#
# read_pin <provider-yml> — echo the pinned FS.GG.UI.Template version to stdout, or return 1
# (echoing nothing) when the file carries no `FS.GG.UI.Template::<ver>` token. Callers decide
# how to react to the empty case (the composition test bad()s it; the two scripts hard-fail).
read_pin() {
  local prov="$1" pin
  pin="$(grep -oE 'FS\.GG\.UI\.Template::[^ ]+' "$prov" 2>/dev/null | head -1 | sed 's/.*:://')"
  [ -n "$pin" ] || return 1
  printf '%s\n' "$pin"
}
