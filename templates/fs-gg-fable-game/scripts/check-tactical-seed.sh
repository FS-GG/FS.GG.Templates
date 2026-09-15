#!/usr/bin/env bash
set -euo pipefail

root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
seed="$root/SvgFoundation/Examples/Tactical/scene.json"
implementation="$root/SvgFoundation/TacticalExample.fs"
if [[ -f "$seed" ]]; then
  digest="$(sha256sum "$seed" | cut -d ' ' -f 1)"
  grep -F "let private seedSha256 = \"$digest\"" "$implementation" >/dev/null || {
    echo "tactical seed refused: source SHA-256 does not match TacticalExample.fs" >&2
    exit 1
  }
  jq -e '
    . as $root |
    .schema == "fsgg.svg-example/v1" and
    (.id | type == "string" and length > 0) and
    (.grid.columns > 0 and .grid.rows > 0 and .grid.cellWidth > 0 and .grid.cellHeight > 0) and
    (.units | length == 2) and
    (.units[0].id | type == "string" and length > 0) and
    (.units[1].id | type == "string" and length > 0) and
    (.units[0].id != .units[1].id) and
    (.planningTarget.col >= 0 and .planningTarget.col < .grid.columns) and
    (.planningTarget.row >= 0 and .planningTarget.row < .grid.rows) and
    ([.units[]] | all(.col >= 0 and .col < $root.grid.columns and .row >= 0 and .row < $root.grid.rows))
  ' "$seed" >/dev/null || {
    echo "tactical seed refused: expected exactly two distinct in-bounds units and one in-bounds target on a positive grid" >&2
    exit 1
  }
fi

arcade_seed="$root/SvgFoundation/Examples/Arcade/scene.json"
arcade_implementation="$root/SvgFoundation/ArcadeExample.fs"
if [[ -f "$arcade_seed" ]]; then
  arcade_digest="$(sha256sum "$arcade_seed" | cut -d ' ' -f 1)"
  grep -F "let private seedSha256 = \"$arcade_digest\"" "$arcade_implementation" >/dev/null || {
    echo "arcade seed refused: source SHA-256 does not match ArcadeExample.fs" >&2
    exit 1
  }
  jq -e '
    .schema == "fsgg.svg-example/v1" and
    (.id | type == "string" and length > 0) and
    (.arena.width > 0 and .arena.height > 0) and
    (.player.health > 0 and .player.score == 0) and
    (.collectibles | length == 1) and
    (.movingObstacles | length == 1) and
    (.collectibles[0].id | type == "string" and length > 0) and
    (.movingObstacles[0].id | type == "string" and length > 0) and
    (.goal.requiresCollectibles == 1)
  ' "$arcade_seed" >/dev/null || {
    echo "arcade seed refused: expected initial score 0, exactly one collectible and obstacle, and requiresCollectibles 1" >&2
    exit 1
  }
fi
