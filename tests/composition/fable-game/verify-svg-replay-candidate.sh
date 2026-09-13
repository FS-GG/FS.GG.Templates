#!/usr/bin/env bash
set -euo pipefail
root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
game="${1:?Game packet directory required}"; out="${2:?empty output directory required}"
bash "$root/scripts/stage-svg-replay-candidate.sh" "$game/manifest.json" "$out"
candidate="$out/feed/FS.GG.Workspace.Template.0.12.0-svg-replay.1.nupkg"
game_version="$(jq -r .game.version "$out/candidate-packet.json")"
mkdir -p "$out/home" "$out/packages" "$out/http" "$out/tools"
export DOTNET_CLI_HOME="$out/home" NUGET_PACKAGES="$out/packages" NUGET_HTTP_CACHE_PATH="$out/http"
cat >"$out/NuGet.Config" <<EOF
<configuration><packageSources><clear/><add key="candidate" value="$out/feed"/><add key="public" value="https://api.nuget.org/v3/index.json"/></packageSources></configuration>
EOF
dotnet new install "$candidate" --force >/dev/null
dotnet new fs-gg-fable-game -n ReplayReceiver -o "$out/receiver" --lifecycle typed-sdd --svgFoundation true >/dev/null
if [[ -n "${FSGG_LOCAL_SDK_VERSION:-}" ]]; then
  python3 - "$out/receiver/global.json" "$FSGG_LOCAL_SDK_VERSION" <<'PY'
import json,pathlib,sys
p=pathlib.Path(sys.argv[1]); data=json.loads(p.read_text()); data['sdk']['version']=sys.argv[2]; p.write_text(json.dumps(data,indent=2)+'\n')
PY
fi
grep -F ">$game_version</FsGgGameReplayVersion>" "$out/receiver/SvgFoundation/Studio/Studio.fsproj" >/dev/null
grep -F '>true</FsGgSvgReplayCandidate>' "$out/receiver/SvgFoundation/Studio/Studio.fsproj" >/dev/null
test -f "$out/receiver/SvgFoundation/Studio/ReplayStudio.fs"
test -f "$out/receiver/models/svg-replay/energy-rules.md"
(cd "$out/receiver" && dotnet tool restore >/dev/null)
FSGG_SVG_CANDIDATE_FEED="$out/feed" FSGG_GAME_REPLAY_VERSION="$game_version" FsGgSvgReplayCandidate=true \
  bash "$out/receiver/SvgFoundation/Studio/build.sh" >"$out/studio-build.log" 2>&1
FSGG_SVG_CANDIDATE_FEED="$out/feed" FSGG_GAME_RUNTIME_VERSION=0.15.0 \
  bash "$out/receiver/SvgFoundation/build.sh" >"$out/player-build.log" 2>&1
! grep -RIE 'ReplayStudio|generated-replay|generated-rule-explorer|RuleCatalog|Scenario planner' "$out/receiver/SvgFoundation/dist"
npm ci --prefix "$out/receiver/Browser.Tests" >/dev/null
cp "$root/tests/composition/fable-game/svg-replay-studio-observe.mjs" "$out/receiver/Browser.Tests/"
(cd "$out/receiver/SvgFoundation/Studio/dist" && python3 -m http.server 8174 --bind 127.0.0.1 >"$out/server.log" 2>&1) & server=$!
trap 'kill "$server" 2>/dev/null || true' EXIT
for _ in {1..40}; do curl -fsS http://127.0.0.1:8174/ >/dev/null && break; sleep .25; done
read -r -a browser_families <<<"${FSGG_BROWSER_FAMILIES:-chromium firefox webkit}"
for family in "${browser_families[@]}"; do (cd "$out/receiver/Browser.Tests" && node svg-replay-studio-observe.mjs "$family" http://127.0.0.1:8174/) >"$out/$family-replay.json"; done

typed_status=not-run
if [[ -n "${QUINT_BIN:-}" && -n "${LMT_BIN:-}" ]]; then
  dotnet tool install FS.GG.SDD.Cli --version 1.7.0 --tool-path "$out/tools/sdd" --configfile "$out/NuGet.Config" --no-cache >/dev/null
  sdd="$out/tools/sdd/fsgg-sdd"
  "$sdd" typed-sdd provision --cache "$out/quint-cache" --quint "$QUINT_BIN" --lmt "$LMT_BIN" >"$out/provision.json"
  "$sdd" typed-sdd author --root "$out/receiver" --work svg-replay-01 --title 'Generated replay rule guidance' \
    --agent qualification --session exact-candidate --backend quint-specification-v1 --profile fsgg-quint-profile/2 \
    --source models/svg-replay/energy-rules.md --bindings models/svg-replay/energy-rules.bindings.json --cache "$out/quint-cache" >"$out/author.json"
  "$sdd" typed-sdd inspect --root "$out/receiver" --work svg-replay-01 >"$out/inspect.json"
  jq -e '.outcome=="succeeded"' "$out/author.json" "$out/inspect.json" >/dev/null
  cp -a "$out/receiver" "$out/stale-receiver"
  printf '\nsemantic drift\n' >>"$out/stale-receiver/models/svg-replay/energy-rules.md"
  if "$sdd" typed-sdd inspect --root "$out/stale-receiver" --work svg-replay-01 >"$out/stale-inspect.json"; then
    echo 'stale typed authority unexpectedly inspected' >&2; exit 1
  fi
  jq -e '.outcome=="blocked"' "$out/stale-inspect.json" >/dev/null
  typed_status=passed
else
  echo '{"status":"not-run","reason":"qualified Quint/lmt paths not supplied"}' >"$out/typed-sdd.json"
fi
browser_json='{}'
for family in "${browser_families[@]}"; do browser_json="$(jq --arg family "$family" --slurpfile result "$out/$family-replay.json" '. + {($family):$result[0]}' <<<"$browser_json")"; done
jq -n --arg typed "$typed_status" --argjson browsers "$browser_json" --slurpfile packet "$out/candidate-packet.json" '{schema:"fsgg.svg-replay.template-qualification/v1",candidate:$packet[0],browser:$browsers,replay:{record:"passed",seek:"passed",cancellation:"passed",divergence:"passed"},planning:{separation:"passed",cancel:"passed"},rules:{dependencyExplanation:"passed",disclosure:"passed"},bundles:{studio:"passed",playerAnalysisExcluded:"passed"},typedSdd:{backend:"quint-specification-v1",profile:"fsgg-quint-profile/2",freshnessRefusal:$typed},publication:false}' >"$out/qualification.json"
