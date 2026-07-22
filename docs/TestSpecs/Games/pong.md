---
title: "Pong"
slug: pong
category: games
complexity: simple
genre: "Arcade / Table Tennis"
target_session_minutes: 5
stack: { rendering: "FS.GG.Rendering (Skia/OpenGL)", arch: "Elmish/MVU", lang: "F#" }
status: spec
---

# Pong

## 1. Overview
Pong is the canonical 1972 arcade table-tennis game: two paddles, one ball, a center
net, and a race to 11 points. The player fantasy is pure reflex mastery — read the
ball, intercept it, and angle your return to wrong-foot the opponent. The core verb is
**deflect**: move your paddle up/down to bounce the ball back across the net. It's fun
because the rules are trivial but the skill ceiling (angling shots, reading a ball that
speeds up every rally) is high. Two modes ship in v1: **single-player vs. AI** and
**local two-player** (hot-seat).

## 2. Core Game Loop
**Moment-to-moment loop:** read ball trajectory → move paddle to intercept → deflect ball
at an angle → opponent returns (or misses) → repeat until a point is scored.

**Point loop:** serve → rally → ball passes a paddle → award point to the other side →
brief pause (1.0 s) → re-serve toward the player who was just scored on.

**Session loop:** Title screen → choose mode (1P / 2P) → play first-to-11 match →
Game Over screen showing winner and final score → restart (same mode) or return to title.

## 3. Controls & Input
Input is **held-state** for paddle movement (polled each tick, not edge-triggered), and
**edge-triggered** for menu/pause actions.

| Input | Context | Action | Model |
|-------|---------|--------|-------|
| `W` | In play | Left paddle up | Held |
| `S` | In play | Left paddle down | Held |
| `↑` (Up) | In play (2P) | Right paddle up | Held |
| `↓` (Down) | In play (2P) | Right paddle down | Held |
| `Space` | Title | Start match (selected mode) | Edge (key-down) |
| `1` | Title | Select 1-Player mode | Edge |
| `2` | Title | Select 2-Player mode | Edge |
| `P` / `Esc` | In play | Toggle pause | Edge |
| `Space` | Game Over | Restart match | Edge |
| `Esc` | Game Over / Pause | Return to title | Edge |

In **1-Player** mode the right paddle is AI-controlled; the player always controls the
left paddle with `W`/`S`. Mouse and gamepad are out of scope for v1 (see Stretch Goals).
Held keys are tracked in a `KeysDown: Set<Key>` set; movement is applied during `Tick`.

## 4. Mechanics (detailed)

### 4.1 Coordinate system & playfield
Logical playfield is **1280 × 720 px**, origin top-left, +x right, +y down. A 12 px-thick
top wall at y=0 and bottom wall at y=708 bound vertical play. Left/right edges (x=0,
x=1280) are the **goal lines** (scoring planes). A dashed center net is drawn at x=640
but is purely cosmetic (no collision).

### 4.2 Paddle movement
- Paddle size: **18 px wide × 110 px tall**.
- Left paddle center-x: **40 px**; right paddle center-x: **1240 px** (so inner faces sit
  at x=49 and x=1231).
- Movement is **velocity-based, no acceleration** (instant on/off for tight arcade feel):
  paddle speed = **600 px/s** while its up/down key is held.
- Clamp paddle so it never overlaps walls: `paddleY` (top edge) clamped to
  `[12, 720 - 12 - 110]` = `[12, 598]`.
- If both up and down are held simultaneously, net movement is 0.

### 4.3 Ball movement & physics
- Ball is a **16 × 16 px** square (classic blocky look), referenced by its center.
- No gravity, no friction — constant-velocity travel between collisions.
- **Serve speed:** 420 px/s. **Speed cap:** 1100 px/s.
- Velocity stored as `(vx, vy)` in px/s. Position integrates each tick: `pos += vel * dt`.

### 4.4 Serve logic
- On serve, ball spawns at center (640, 360).
- Direction: toward the player who was **just scored on** (so the loser receives). On the
  very first serve of a match, direction is chosen by RNG (50/50 left/right).
- Serve angle: pick a random launch angle `θ ∈ [-35°, +35°]` (measured from the horizontal
  axis toward the target side), excluding the near-flat band `|θ| < 8°` to avoid dull
  horizontal serves. Then `vx = ±420·cos θ`, `vy = 420·sin θ`.
- A **0.8 s freeze** holds the ball stationary at center before it launches (telegraph).

### 4.5 Wall collision (top/bottom)
- When ball center-y reaches `12 + 8 = 20` (top) or `708 - 8 = 700` (bottom), reflect:
  `vy = -vy`. Reposition ball just inside the wall to prevent sticking.
- Speed is unchanged by wall bounces.

### 4.6 Paddle collision & angle control
- Collision test: AABB overlap between the 16×16 ball and the 18×110 paddle rect, only
  considered when the ball is moving **toward** that paddle (`vx < 0` for left, `vx > 0`
  for right). This prevents double-hits.
- On hit:
  1. **Reflect horizontally:** `vx = -vx`.
  2. **Angle from contact point:** compute normalized offset
     `u = (ballY - paddleCenterY) / (110/2)`, clamped to `[-1, 1]`. The new bounce angle is
     `θ = u · 50°` (max ±50° off horizontal — hitting the paddle edge sends the ball
     steeply; hitting center sends it flat).
  3. **Speed-up:** multiply current speed by **1.05** (5% per paddle hit), capped at
     1100 px/s.
  4. Recompute velocity from new speed `s` and angle: `vx = sign · s·cos θ`,
     `vy = s·sin θ`, where `sign = +1` off the left paddle, `-1` off the right paddle.
  5. Reposition ball flush against the paddle face to avoid overlap re-trigger.

### 4.7 Scoring plane
- When ball center-x < 0 → **right player scores**.
- When ball center-x > 1280 → **left player scores**.
- After a point: increment score, enter a 1.0 s `PointPause`, then serve toward the
  player who was scored on.

### 4.8 AI opponent (single-player)
The AI controls the right paddle. It uses **tracking with reaction delay and error** so it
is beatable:
- **Dead zone:** AI only moves when the ball is on its half (`ballX > 640`) AND moving
  toward it (`vx > 0`); otherwise it eases its paddle back toward center-y (360) at
  240 px/s (idle recentering).
- **Target:** predicted ball intercept y. v1 uses simple tracking: target = `ballY +
  aimError`, where `aimError` is a per-rally random offset in `[-aiErrorPx, +aiErrorPx]`
  re-rolled on each paddle hit. `aiErrorPx` defaults to **45 px**.
- **Move:** move paddle center toward target at **aiSpeed = 520 px/s** (slightly slower
  than the 600 px/s player), with a 16 px hysteresis band so it doesn't jitter.
- Difficulty knobs (`aiSpeed`, `aiErrorPx`, dead-zone activation x) are in §12.

## 5. Entities / Game Objects

### 5.1 Paddle
- Properties: `Y: float` (top edge), `Side: Side` (Left | Right), fixed width 18, height 110.
- Behavior: Left/Right human paddles driven by held keys; Right may be AI in 1P.
- Created at match start (two paddles); never destroyed during a match. Reset to
  center-y (Y = 305) on each serve.

### 5.2 Ball
- Properties: `Pos: Vec2`, `Vel: Vec2`, size 16×16.
- State machine: `Frozen` (during 0.8 s serve telegraph) → `Live` (in play) → on
  scoring plane it is consumed and a new serve is set up.
- Created once per match; repositioned/relaunched each serve.

### 5.3 F# type sketch
```fsharp
type Side = Left | Right

type Vec2 = { X: float; Y: float }

type BallState = Frozen of timer:float | Live

type Paddle =
    { Side: Side
      Y: float }            // top edge, px

type Ball =
    { Pos: Vec2             // center, px
      Vel: Vec2             // px/s
      State: BallState }
```

## 6. World / Levels / Progression
- **Playfield:** 1280 × 720 logical px (fixed; scaled to window preserving aspect ratio,
  letterboxed if needed).
- **No discrete levels.** Progression is intra-rally: the ball accelerates 5% per paddle
  hit (§4.6), so each rally gets faster and harder until a point ends. Speed resets to the
  420 px/s serve speed on the next serve.
- A match is **first to 11 points** (no win-by-2 in v1; see Stretch Goals). Difficulty
  effectively ramps within long rallies as the ball nears the 1100 px/s cap.

## 7. State Model (Elmish/MVU)

### 7.1 Model
```fsharp
type Mode = OnePlayer | TwoPlayer

type Screen =
    | Title of selected:Mode
    | Playing
    | Paused
    | GameOver of winner:Side

type Model =
    { Screen: Screen
      Mode: Mode
      Left: Paddle
      Right: Paddle
      Ball: Ball
      ScoreLeft: int
      ScoreRight: int
      PointPause: float        // seconds remaining in post-point pause; 0 = none
      ServeTo: Side            // side the next serve travels toward (the loser)
      AiError: float           // current per-rally AI aim error, px
      KeysDown: Set<Key>
      Rng: System.Random }
```

### 7.2 Msg
```fsharp
type Msg =
    | Tick of dt:float           // seconds since last frame (~0.0167)
    | KeyDown of Key
    | KeyUp of Key
    | StartMatch of Mode
    | TogglePause
    | Restart
    | ToTitle
```

### 7.3 update (key cases)
- `KeyDown`/`KeyUp`: add/remove key in `KeysDown`. On Title, `1`/`2` set selected mode,
  `Space` → `StartMatch`. On Playing/Paused, `P`/`Esc` → `TogglePause`.
- `StartMatch m`: reset scores to 0, center paddles, set `ServeTo` via 50/50 RNG, set
  `Ball.State = Frozen 0.8`, `Screen = Playing`.
- `Tick dt` (only when `Screen = Playing`):
  1. Apply held-key paddle velocity to Left (and Right if 2P); clamp to walls.
  2. If 1P, run AI step on Right paddle (§4.8).
  3. If `PointPause > 0`, decrement it; when it reaches 0, set up the serve
     (`Frozen 0.8`, ServeTo direction). Skip ball physics while paused.
  4. If `Ball.State = Frozen t`, decrement t; at ≤0 launch ball (§4.4) → `Live`.
  5. If `Live`: integrate position, resolve wall bounces (§4.5), resolve paddle
     collisions (§4.6).
  6. Check scoring planes (§4.7): on score, bump the right counter, set `PointPause = 1.0`,
     set `ServeTo` to the scored-on side, re-roll `AiError`. If a score reaches 11,
     `Screen = GameOver winner`.
- `TogglePause`: swap `Playing` ↔ `Paused` (Tick is a no-op while Paused).
- `Restart`: like `StartMatch` with current `Mode`. `ToTitle`: `Screen = Title Mode`.

### 7.4 view
`view` is pure — it maps `Model` to a Skia draw list (see §8). It performs no mutation and
no timing; it reads scores, paddle Ys, ball pos/state, and current `Screen` to decide what
to render (title overlay, HUD, pause dim, game-over panel).

### 7.5 Subscriptions
- **Tick:** a fixed 60 FPS timer subscription emitting `Tick dt` with `dt` in seconds
  (target 1/60 ≈ 0.0167; clamp dt to ≤ 0.05 to survive frame hitches — see §13).
- **Input:** keyboard key-down/key-up events mapped to `KeyDown`/`KeyUp`.

## 8. Rendering (Skia 2D)
- **Coordinate system:** logical 1280×720 canvas; a single scale+translate transform maps
  it to the window (uniform scale, letterbox bars where aspect differs).
- **Draw order (back to front):**
  1. Background fill: `#000000` (black).
  2. Center net: dashed vertical line at x=640, dash 18 px on / 14 px off, 4 px wide,
     color `#3C3C3C`.
  3. Top/bottom walls: filled rects, color `#FFFFFF` (optional; classic Pong omits them —
     keep thin or skip).
  4. Paddles: two filled rects, `#FFFFFF`, hard corners (no anti-alias rounding).
  5. Ball: 16×16 filled square, `#FFFFFF`.
  6. HUD scores (§9): big digits near top.
  7. Overlays (title / pause dim / game-over panel) drawn last.
- **Fonts:** a monospace/blocky font (e.g. bundled "PressStart2P"-style) for scores at
  72 px and HUD/menu text at 28 px, color `#FFFFFF`.
- **Camera:** none (static single screen).
- **Effects (optional, cheap):** 1-frame white flash on the scored-against goal edge;
  brief 80 ms paddle "squash" by scaling paddle width to 22 px on a hit. No particles
  required for v1.
- **Redraw strategy:** full-screen redraw every frame (scene is tiny; cost is negligible).
  No dirty-rect optimization needed.

## 9. UI / HUD / Screens

### 9.1 Title screen
- Centered title "PONG" at 96 px.
- Mode selector: "1 PLAYER" and "2 PLAYERS" stacked; the selected one highlighted
  (inverted: white box, black text). Keys `1`/`2` select, `Space` starts.
- Footer hint: "W/S — Left   ↑/↓ — Right (2P)   SPACE — Start" at 24 px.

### 9.2 Play HUD
- Left score at (x≈480, y=60), right score at (x≈800, y=60), 72 px digits, `#FFFFFF`.
- No other persistent HUD elements.

### 9.3 Pause overlay
- 50% black dim over the frozen scene; centered "PAUSED" at 72 px and
  "P — Resume   ESC — Title" at 24 px.

### 9.4 Game Over screen
- Centered panel: "PLAYER LEFT WINS" / "PLAYER RIGHT WINS" (or "YOU WIN" / "CPU WINS" in
  1P) at 64 px, final score "11 – 7" at 48 px below.
- Hint: "SPACE — Rematch   ESC — Title" at 24 px.

## 10. Audio
Audio is optional in v1. Checklist of cues:
- [ ] Paddle hit — short blip (~120 Hz square, 60 ms).
- [ ] Wall bounce — slightly higher blip (~240 Hz, 50 ms).
- [ ] Point scored — descending two-tone (~200→100 Hz, 250 ms).
- [ ] Serve launch — soft tick.
- [ ] Match win — short victory jingle (3 ascending notes).
- [ ] No background music (classic Pong is silent between events).

## 11. Win / Loss / Scoring
- **Point:** the player whose goal line is NOT crossed scores 1 point when the ball exits
  past the opponent's goal line (§4.7).
- **Win condition:** first side to reach **11 points** wins the match → `GameOver winner`.
- **Loss condition:** the opponent reaches 11 first. In 1P, losing to the CPU is the loss
  state.
- **Scoring values:** exactly 1 point per rally won; no combos, no time bonus.
- **Lives/continues:** none — a match is a single first-to-11 race; Game Over offers
  rematch or title.

## 12. Difficulty & Balancing
Data-driven tunables (all defined as named constants / a config record):

| Name | Default | Range | Effect |
|------|---------|-------|--------|
| `playfieldW` × `playfieldH` | 1280 × 720 | fixed | Logical play area. |
| `paddleW` × `paddleH` | 18 × 110 px | 12–28 × 70–160 | Bigger paddle = easier defense. |
| `playerSpeed` | 600 px/s | 300–900 | Human paddle responsiveness. |
| `serveSpeed` | 420 px/s | 250–600 | Initial ball speed each serve. |
| `speedCap` | 1100 px/s | 600–1600 | Max ball speed (rally ceiling). |
| `hitSpeedUp` | 1.05 | 1.0–1.15 | Per-paddle-hit speed multiplier. |
| `maxBounceAngle` | 50° | 30–60 | Angle range from contact offset. |
| `serveAngleMax` | 35° | 15–45 | Serve launch spread. |
| `aiSpeed` | 520 px/s | 200–700 | AI paddle speed (vs. 600 player). |
| `aiErrorPx` | 45 px | 0–160 | AI aim error; higher = easier. |
| `aiActivateX` | 640 px | 500–900 | x past which AI starts tracking. |
| `winScore` | 11 | 5–21 | Points to win the match. |
| `serveFreeze` | 0.8 s | 0.3–1.5 | Telegraph delay before launch. |
| `pointPause` | 1.0 s | 0.5–2.0 | Delay after a point before serve. |

**Suggested AI difficulty presets:** Easy `aiSpeed 420 / aiErrorPx 90`; Normal
`520 / 45`; Hard `640 / 15`.

## 13. Technical Notes
- **Performance budget:** trivially within 60 FPS / 16.7 ms — fixed entity count (2
  paddles + 1 ball + static net). No allocation per frame beyond the draw list; reuse Skia
  paint objects.
- **Timestep:** logically **fixed-step physics** at 60 Hz. `Tick dt` carries dt in seconds;
  clamp `dt ≤ 0.05` to prevent tunneling on frame hitches. For robustness, an implementer
  may sub-step the ball when `|vel*dt|` exceeds half the ball size (8 px) to avoid passing
  through thin paddles at >1000 px/s — split the integration into N ≥ ceil(speed·dt/8)
  sub-steps and run collision each sub-step.
- **Determinism / RNG:** all randomness (serve direction, serve angle, AI error) draws from
  a single seeded `System.Random` stored in the model, so a match is reproducible given the
  seed and an input log. Tests should inject a fixed-seed RNG.
- **Persistence:** optional — store the single highest player win-streak (1P) in local
  config. Not required for v1.
- **Edge cases:** ball hitting the exact corner of a paddle (resolve via the §4.6 contact
  offset, clamped to ±1 → ±50°); both paddle-up and paddle-down keys held (net 0);
  simultaneous wall+paddle proximity (resolve wall bounce first, then paddle); ball at
  speed cap (clamp, do not exceed); window resize mid-rally (logical coords unaffected).

## 14. Acceptance Criteria (test scenarios)

1. **Serve telegraph & launch.** *Given* a fresh match has started, *when* the serve
   begins, *then* the ball sits frozen at (640, 360) for 0.8 s (±1 frame) and *then*
   launches at 420 px/s with `|θ| ∈ [8°, 35°]` toward `ServeTo`.

2. **Paddle movement & clamp.** *Given* the left paddle top edge is at Y=590, *when* `S`
   (down) is held for 1 s, *then* the paddle stops at Y=598 (clamped) and never overlaps
   the bottom wall.

3. **Held-key net zero.** *Given* both `W` and `S` are held, *when* a Tick is processed,
   *then* the left paddle's Y is unchanged.

4. **Wall bounce preserves speed.** *Given* the ball travels at 500 px/s with vy>0 toward
   the bottom wall, *when* its center-y reaches 700, *then* `vy` flips sign, speed stays
   500 px/s (±0.1), and the ball does not pass below y=700.

5. **Paddle deflection angle (center hit).** *Given* the ball strikes the left paddle at
   its exact center (offset u=0), *when* the collision resolves, *then* `vx` becomes
   positive and the bounce angle is ~0° (near-horizontal return).

6. **Paddle deflection angle (edge hit).** *Given* the ball strikes the left paddle near
   its top edge (u≈-1), *when* the collision resolves, *then* the bounce angle ≈ -50°
   (steeply upward) and `vx > 0`.

7. **Per-hit speed-up & cap.** *Given* a rally with the ball at 420 px/s, *when* it is
   deflected by a paddle, *then* its speed becomes 441 px/s (×1.05); *and* given speed is
   1080 px/s, *when* deflected, *then* speed is clamped to 1100 px/s (not 1134).

8. **No double-hit.** *Given* the ball has just bounced off the left paddle and is moving
   right (vx>0) but still overlaps the paddle for a frame, *when* Ticks process, *then* no
   second reflection occurs (collision ignored because ball moves away).

9. **Scoring left.** *Given* the ball center-x exceeds 1280, *when* the score is resolved,
   *then* `ScoreLeft` increments by 1, a 1.0 s `PointPause` begins, and the next serve
   travels toward Right (the scored-on side).

10. **Win condition.** *Given* `ScoreLeft = 10` in a first-to-11 match, *when* Left scores
    again, *then* `Screen` becomes `GameOver Left` and ball physics stop.

11. **AI is beatable but tracks.** *Given* 1P mode and the ball moving right (vx>0) past
    x=640, *when* Ticks process, *then* the AI right paddle moves toward `ballY ± aiError`
    at ≤520 px/s; *and* given the ball is on the left half moving left, *then* the AI
    paddle eases toward center-y (360).

12. **Pause freezes the world.** *Given* a live rally, *when* `P` is pressed, *then*
    `Screen = Paused`, subsequent Ticks do not move the ball or paddles, and pressing `P`
    again resumes from the exact prior state.

13. **Determinism.** *Given* two matches started with the same RNG seed and the same input
    log, *when* both are simulated, *then* ball positions and final score are identical.

14. **Tunneling guard.** *Given* the ball moves at 1100 px/s toward a paddle on one frame
    (displacement > 18 px), *when* the Tick integrates, *then* sub-stepping detects the
    collision and the ball does not pass through the paddle.

## 15. Stretch Goals
1. **Win-by-2 / deuce** scoring above 10–10.
2. **Mouse & gamepad** paddle control (analog speed).
3. **Difficulty select** on the title screen (Easy/Normal/Hard presets from §12).
4. **Predictive AI** (extrapolate ball trajectory through wall bounces instead of simple
   tracking).
5. **Particles & CRT post-effect** (scanlines, bloom) for retro flavor.
6. **Best-of-N matches** and a simple tournament bracket.
7. **Online two-player** via rollback netcode (deterministic core already supports it).
8. **Power-ups** (multi-ball, paddle grow/shrink) as an optional arcade variant mode.

## Menu & configuration — the shared game shell

Pong uses the **generic FS.GG game shell** (FS-GG/FS.GG.Rendering#991) — the same
menu/start screen and settings every FS.GG game shares — rather than a bespoke per-game
menu. Pong supplies only its **name**, its **key→command map** (the rebindable actions from
§3 Controls), and its play `update`/`view`; the shell provides everything below.

- **Main menu / start screen** — the game's name (**Pong**) as the title label, with
  **Start**, **Config**, and **Exit**. The 1P/2P mode toggle (§9.1) is presented as the
  Start affordance (or a Config row); the shell owns the surrounding menu chrome that the
  bespoke §9.1 Title screen used to draw.
- **`Esc` from gameplay** opens the pause menu (Resume · Config · Exit to menu) over the
  same shell; `Esc` again resumes. This is the shell home for the §3 `P` / `Esc` pause
  action and the §9.3 Pause overlay.
- **Config / Settings**, all applied live and persisted across restarts:
  - **Screen resolution** and **fullscreen** (windowed / borderless / fullscreen), driven
    through the SkiaViewer window-behavior + `LogicalCanvas` letterbox seam — the same seam
    that scales the logical 1280×720 playfield (§4.1, §8) to the window with aspect-preserving
    letterbox bars.
  - **Key rebinding** — the player remaps Pong's controls (the §3 actions: left paddle
    up/down `W`/`S`, right paddle up/down `↑`/`↓`, pause) via the `Controls.KeyRebind` UI
    over the `KeyboardInput.Keymap` mechanism; bindings persist via `KeymapCodec` (JSON),
    beside Pong's other saved config (§13).
  - (Game-specific rows such as AI difficulty (§12 presets) or volume may be added as extra
    Config rows, but the menu, Esc routing, display settings, and rebind screen come from the
    shell.)

The shell is pointer- and keyboard-navigable over the interactive Controls host (the
`fs-gg-skiaviewer` "game → pointer host" recipe). It is a shared dependency, so Pong does
**not** re-specify menu-stack/cursor/settings machinery of its own.

## 16. Milestone Roadmap

Delivery is milestone-sequenced (M0..Mn), each a small, demonstrable slice grounded in the
sections above. Earlier milestones stand up the deterministic simulation core; later ones
layer the AI, feel, the shared shell, audio, and the acceptance harness.

### M0 — Scaffold & fixed-step loop
Stand up the Elmish/MVU app (§7) on the FS.GG.Rendering host: the `Model`/`Msg` skeleton,
the fixed 60 Hz `Tick` subscription with `dt` clamped to ≤ 0.05 s (§7.5, §13), and an empty
1280×720 logical canvas (§4.1, §8) clearing to black each frame. No gameplay yet — just a
deterministic, steppable loop with `Screen = Title`.

### M1 — Playfield, walls & paddle movement
Draw the top/bottom walls and cosmetic center net (§4.1), and implement both paddles (§4.2,
§5.1): velocity-based 600 px/s movement with instant on/off, the `[12, 598]` clamp, and the
both-keys-held → net-zero rule. Held keys tracked in `KeysDown` and applied during `Tick`.

### M2 — Ball movement, serve & wall bounce
Add the ball (§4.3, §5.2) and its `Frozen → Live` serve machine (§4.4): spawn at centre, the
0.8 s freeze telegraph, the `θ ∈ [8°, 35°]` launch toward `ServeTo` at 420 px/s, constant-
velocity integration, and top/bottom `vy`-flip wall bounces (§4.5) with reposition-inside
anti-sticking and radius-bounded sub-stepping (§13).

### M3 — Paddle collision, angle control & rally speed-up
Implement AABB ball–paddle collision considered only when the ball moves **toward** the
paddle (no double-hit), the contact-offset angle control (`θ = u · 50°`, clamped ±1), the
`vx` reflect + reposition-flush, and the ×1.05 per-hit speed-up capped at 1100 px/s (§4.6,
§6). This is the milestone that gives each rally its escalating skill curve.

### M4 — Scoring, match flow & win condition
Wire the scoring planes (§4.7) and the full `Screen` machine (§7.3): award a point when the
ball crosses a goal line, the 1.0 s `PointPause`, re-serve toward the scored-on side, and
`GameOver winner` at the first-to-11 `winScore` (§11). Ball physics stop on game over.

### M5 — AI opponent (single-player)
Implement the beatable tracking AI on the right paddle (§4.8): the `ballX > 640` + moving-
toward dead zone, idle recentre to y = 360, per-rally `aiError` re-rolled on each hit,
520 px/s tracking with a 16 px hysteresis band, and the Easy/Normal/Hard knob presets (§12).
1P vs 2P selection drives whether this step runs.

### M6 — Rendering & juice
Complete the back-to-front draw list (§8): black field, dashed net, hard-cornered white
paddles and 16×16 ball, the 72 px score digits (§9.2), and the cheap optional feel — the
1-frame goal-edge flash and the 80 ms paddle squash on a hit. Render the §9 screen overlays.

### M7 — Menus, settings & key rebinding (shared game shell)
Adopt the generic game shell (FS-GG/FS.GG.Rendering#991): main menu (title **Pong** +
Start/Config/Exit with the 1P/2P mode choice), `Esc` pause routing (Resume · Config · Exit
to menu), Settings with screen resolution + fullscreen through the SkiaViewer +
`LogicalCanvas` letterbox seam, and in-game key rebinding of the §3 controls, persisted via
`KeymapCodec`. Pong provides its name + key→command map + play `update`/`view`; the shell
provides the rest. No bespoke menu system — this replaces the ad-hoc §9.1/§9.3 Title and
Pause chrome.

### M8 — Audio
Wire the SFX checklist (§10): paddle-hit and wall-bounce blips, the descending two-tone
point cue, the serve tick, and the match-win jingle. Classic Pong stays silent between
events (no background music); a shell Config volume row may drive levels.

### M9 — Acceptance & determinism
Land the acceptance harness against all 14 scenarios (§14): serve telegraph/launch, paddle
clamp and held-key net-zero, speed-preserving wall bounce, centre and edge deflection
angles, per-hit speed-up and cap, no-double-hit, scoring and win condition, the beatable-but-
tracking AI, pause-freezes-the-world, the tunneling guard, and the same-seed + same-input-log
**determinism** replay yielding identical ball positions and final score (§13).
