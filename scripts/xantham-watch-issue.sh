#!/usr/bin/env bash
# Create or update the ONE open fbx-07-watch issue for a Xantham watch signal (FS.GG.Templates#751).
#
# Usage: scripts/xantham-watch-issue.sh <issue-body-file>
# Env:   GH_TOKEN (issues: write), GITHUB_REPOSITORY
#
# The only effect is one issue: no PR, branch, pin or baseline change. The body is the deterministic
# text scripts/xantham-watch.mjs renders and starts with the dedupe marker; an open labelled issue
# carrying the marker is edited only if its body differs, otherwise a new one is created. A closed
# issue is not reused, so a signal that persists after fdev closes the issue is raised again.
set -euo pipefail

body_file="${1:?usage: xantham-watch-issue.sh <issue-body-file>}"
repo="${GITHUB_REPOSITORY:?GITHUB_REPOSITORY is required}"
label="fbx-07-watch"
marker="<!-- fsgg:fbx-07-watch -->"
title="FBX-07 watch: upstream Xantham change detected"

head -n 1 "$body_file" | grep -Fxq "$marker" || { echo "xantham-watch-issue: body does not start with the dedupe marker" >&2; exit 1; }

if ! gh api "repos/$repo/labels/$label" >/dev/null 2>&1; then
  gh label create "$label" --repo "$repo" --color "fbca04" \
    --description "Scheduled read-only Xantham upstream watch signal (Templates#751)"
fi

existing="$(gh issue list --repo "$repo" --label "$label" --state open --limit 100 --json number,body \
  | jq -r --arg m "$marker" '[.[] | select(.body | startswith($m))] | sort_by(.number) | .[0].number // empty')"

if [[ -z "$existing" ]]; then
  gh issue create --repo "$repo" --title "$title" --label "$label" --body-file "$body_file"
  exit 0
fi

current="$(gh issue view "$existing" --repo "$repo" --json body --jq .body)"
# $(...) strips trailing newlines on both sides; CRs are removed in case the API returns CRLF.
if [[ "$(printf '%s' "$current" | tr -d '\r')" == "$(tr -d '\r' <"$body_file")" ]]; then
  echo "xantham-watch-issue: #$existing already carries this signal; no edit"
else
  gh issue edit "$existing" --repo "$repo" --body-file "$body_file"
fi
