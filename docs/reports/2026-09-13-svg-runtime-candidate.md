# SVG runtime generated-candidate boundary

The opt-in SVG player now composes Game.Core's portable session reducer and kinematic collision adapter
with Rendering's animation-frame session host, normalized input adapter, and retained SVG projection. The
product owns arena state, movement meaning, health, score, collectibles, and win/loss decisions. Game owns
fixed-step and collision semantics; Rendering owns browser cadence, device normalization, retained DOM
updates, suspension recovery, generation rejection, and resource disposal.

`scripts/stage-game-runtime-packet.sh` and `scripts/stage-rendering-runtime-packet.sh` pack unique private
candidates from exact accepted producer revisions. Their manifests bind every archive and the required
Fable interfaces. `scripts/stage-svg-runtime-candidate.sh` validates both packets before creating the
private `0.12.0-svg-runtime.1` template. Public Game `0.14.0`, Rendering `0.29.0`, and Templates `0.11.0`
pins remain unchanged.

Run the installed closure with:

```bash
SVG_SCENE_ORCA_OBSERVATION=/absolute/generated-runtime-orca.json \
  bash tests/composition/fable-game/verify-svg-runtime-candidate.sh \
  /absolute/rendering-runtime-packet /absolute/game-runtime-packet /absolute/empty-output
```

Qualification covers direct generation, SDD 1.7.0 none/default/typed routes, the pinned wizard 0.11.1
adopter, and retained 0.10/0.11 upgrades. It refuses managed collisions before writes, rolls interrupted
application back, restores managed bytes exactly, and preserves lifecycle provenance and authored content.
Chromium, Firefox, and WebKit drive keyboard, pointer, touch, and native Gamepad API movement through one
semantic profile, then observe pause, single-step, reset, lose, restart, and win in the actual authority
projection. The player bundle is checked to exclude Studio, workspace, and geometry-worker modules.

The qualification packet records exact Game, Rendering, and Templates revisions, candidate archive and
interface identities, browser observations, the Game lockstep corpus, public baselines, and every adoption
or rollback result. This completes SVG-RUNTIME-01 and hands Preview B a private publication candidate;
public publication and default activation remain release decisions.
