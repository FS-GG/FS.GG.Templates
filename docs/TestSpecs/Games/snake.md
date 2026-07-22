---
title: "Snake"
slug: snake
category: games
complexity: simple
genre: "Arcade / grid-based survival"
target_session_minutes: 5
stack: { rendering: "FS.GG.Rendering (Skia/OpenGL)", arch: "Elmish/MVU", lang: "F#" }
status: spec
---

# Snake

## 1. Overview
You pilot an ever-lengthening snake across a fixed grid, steering it to swallow
food pellets. Each pellet makes the snake longer and the game faster, so the very
act of succeeding shrinks your room to maneuver. The core verb is **turn** —
choosing when to commit the head to a new heading before it crashes into a wall or
its own tail. The fun is the tightening pressure: an early game of lazy loops
becomes a late-game spatial puzzle where you must thread the snake through corridors
of its own body. One mistake ends the run, making every score a personal high-water
mark to beat.

## 2. Core Game Loop
**Moment-to-moment:** observe head position → queue a turn → snake steps one cell on
the tick → eat food (grow) or move into empty cell → repeat. The player is
continuously reading the board and pre-committing turns.

**Session-level:** Title screen → press Start → play (snake grows, speed ramps) →
collision → Game Over screen showing score and high score → press Restart → new run
with a fresh 1-length... (actually 3-length, see §5) snake at center.

## 3. Controls & Input
Input is **edge-triggered** (key-down events), not held-state. Pressing a direction
enqueues a turn for the *next* tick; the snake does not move faster by mashing keys.

| Input | Action | Notes |
|---|---|---|
| Arrow Up / `W` | Queue turn to Up | Ignored if it would reverse 180° |
| Arrow Down / `S` | Queue turn to Down | Ignored if it would reverse 180° |
| Arrow Left / `A` | Queue turn to Left | Ignored if it would reverse 180° |
| Arrow Right / `D` | Queue turn to Right | Ignored if it would reverse 180° |
| `Space` / `P` | Pause / Resume | Toggle; only during Play |
| `Enter` / `Space` | Start / Restart | On Title and GameOver screens |
| `Esc` | Quit to Title | From Play or Pause |

Direction inputs are pushed into a small **direction queue** (max 2 entries). The
tick handler dequeues at most one turn per step. This lets a player buffer a fast
two-step maneuver (e.g. Up then Right around a corner) within a single tick interval
without dropping the second press. See §4.3.

## 4. Mechanics (detailed)

### 4.1 Grid & coordinate system
- Logical playfield: **1280×720 px**.
- Grid: **32 columns × 18 rows** of cells.
- Cell size: **40×40 px** (1280 / 32 = 40, 720 / 18 = 40 — exact, no remainder).
- Cell coordinates are integer `(col, row)` with origin `(0,0)` at top-left, `col`
  increasing right, `row` increasing down.
- A cell's pixel rect is `(col*40, row*40, 40, 40)`.

### 4.2 Movement & stepping
- The snake is a sequence of occupied cells, head first. It moves in **discrete
  steps**, exactly one cell per **tick**, never sub-cell.
- On each step the head advances one cell in the current heading. The body follows:
  conceptually the head is prepended and the tail cell is removed — unless the snake
  grew this step, in which case the tail is retained (net +1 length).
- Heading is one of four unit vectors: Up `(0,-1)`, Down `(0,+1)`, Left `(-1,0)`,
  Right `(+1,0)`.
- Initial heading: **Right**.

### 4.3 Direction queue (180° reversal guard)
- Turns are buffered in a queue of capacity **2**.
- A turn is only enqueued if it is not the direct opposite of the *last committed or
  last queued* direction (whichever is most recent). This prevents the classic bug
  where pressing Left then Right in one tick folds the snake back onto itself.
- At the start of each tick, if the queue is non-empty, dequeue one direction and
  make it the new heading — but only if it is not the 180° opposite of the current
  heading (defense-in-depth; the enqueue guard should already prevent this).
- Repeated presses of the current heading are accepted (no-op turns) but capped by
  queue capacity.

### 4.4 Food & eating
- Exactly **one** food pellet exists at any time.
- Food occupies a single cell, never one currently occupied by the snake.
- Spawn rule: pick a uniformly random cell from the set of **unoccupied** cells
  (all 576 cells minus the snake's body). If the snake fills the entire board
  (no free cell), the player **wins** (see §11).
- When the head steps onto the food cell: increment score, grow the snake, increase
  speed, and spawn a new pellet.

### 4.5 Growth
- Eating food grows the snake by **+1 cell** (default `growthPerFood = 1`). Mechanically
  this means: on the eating step, the tail is **not** removed, so the body lengthens by
  one and fills the cell the food occupied.

### 4.6 Speed & acceleration
- Time-based, not per-frame. Stepping is governed by a **step interval** in seconds.
- `baseStepSeconds = 0.18` (≈ 5.5 steps/s at start).
- Each food eaten reduces the interval: `stepSeconds = max(minStepSeconds, baseStepSeconds - (foodEaten * stepDecrement))`.
- `stepDecrement = 0.006` s per food; `minStepSeconds = 0.06` (≈ 16.6 steps/s cap).
- Reaching the floor takes `(0.18 - 0.06) / 0.006 = 20` pellets, after which speed is
  constant.
- A step accumulator (§7 / §13) decouples stepping from the 60 FPS render tick.

### 4.7 Collision & death
- **Wall collision:** in *Wall* mode, if the next head cell is outside `[0,31]×[0,17]`,
  the snake dies.
- **Self collision:** if the next head cell is currently part of the snake's body, the
  snake dies. Exception: the **current tail cell** is vacating this step (when not
  growing), so moving the head into the old tail position is **allowed** and not a
  collision. When growing, the tail does not vacate, so that cell is solid.
- Death transitions to GameOver.

### 4.8 Wrap vs. wall-death mode (option)
- Config flag `wrapWalls : bool` (default **false** = wall death).
- When `wrapWalls = true`: instead of dying at a boundary, the head wraps to the
  opposite edge — `col = (col + 32) % 32`, `row = (row + 18) % 18`. Self-collision
  still kills. This is selectable from the Title screen.

## 5. Entities / Game Objects

### 5.1 Snake
- Properties: ordered collection of cells (head at front), current heading, pending
  growth, direction queue.
- Initial state: length **3**, occupying cells `(16,9)`, `(15,9)`, `(14,9)` with head at
  `(16,9)`, heading **Right**, placed near board center (col 16 of 32, row 9 of 18).
- Rendered as 40×40 cells inset by a 2 px gap (see §8).
- Created at run start; destroyed/reset on Restart.

```fsharp
type Cell = { Col: int; Row: int }

type Direction = Up | Down | Left | Right

type Snake =
    { Body: Cell list          // head is List.head; tail is List.last
      Heading: Direction
      PendingGrowth: int        // cells still owed from recent food
      TurnQueue: Direction list } // capacity 2, FIFO
```
> Implementation note: a `System.Collections.Generic.Deque`/two-stack structure or an
> `ImmutableQueue` is preferable to `list` for O(1) tail removal at long lengths, but
> the `Body: Cell list` sketch above is the canonical conceptual model. Maintain a
> parallel `HashSet<Cell>` of occupied cells for O(1) collision and food-spawn checks.

### 5.2 Food
- Single pellet, one cell, no behavior (static).
- Created on run start and immediately after each eat; destroyed when eaten.

```fsharp
type Food = { Pos: Cell }
```

## 6. World / Levels / Progression
- Single static playfield, **1280×720** logical px, **32×18** grid. No camera, no scroll.
- There are no discrete levels; progression is the continuous speed ramp (§4.6) and the
  emergent difficulty of a longer body.
- Difficulty ramp summary: length grows +1 per pellet; step interval shrinks 0.006 s per
  pellet down to a 0.06 s floor at 20 pellets. After the floor, difficulty rises only
  through reduced free space.
- A thin border frame is drawn just inside the playfield edges as a visual wall cue
  (purely cosmetic; collision uses grid bounds).

## 7. State Model (Elmish/MVU)

### Model
```fsharp
type Screen = Title | Playing | Paused | GameOver

type Config =
    { WrapWalls: bool
      BaseStepSeconds: float
      MinStepSeconds: float
      StepDecrement: float
      GrowthPerFood: int }

type Model =
    { Screen: Screen
      Snake: Snake
      Food: Food
      Cols: int                 // 32
      Rows: int                 // 18
      FoodEaten: int            // pellets consumed this run
      Score: int
      HighScore: int
      StepSeconds: float        // current step interval
      StepAccumulator: float    // seconds banked toward next step
      Config: Config
      Rng: System.Random }
```

### Msg
```fsharp
type Msg =
    | StartGame
    | TurnRequested of Direction   // from key-down
    | TogglePause
    | QuitToTitle
    | ToggleWrapMode               // Title screen option
    | Tick of float                // dt in seconds, every render frame
    | Restart
```

### update — key transitions
- `StartGame` / `Restart`: build a fresh `Model` — center snake (len 3, heading Right),
  `FoodEaten = 0`, `Score = 0`, `StepSeconds = BaseStepSeconds`, accumulator 0, spawn
  first food in a non-occupied cell, `Screen = Playing`. Preserve `HighScore` and `Config`.
- `TurnRequested d`: only while `Playing`. Enqueue `d` into `Snake.TurnQueue` if queue not
  full **and** `d` is not the 180° opposite of the most-recent committed/queued direction.
- `TogglePause`: `Playing ↔ Paused`. No simulation while `Paused`.
- `ToggleWrapMode`: only on `Title`; flips `Config.WrapWalls`.
- `QuitToTitle`: `Screen = Title`.
- `Tick dt`: only while `Playing`. Add `dt` to `StepAccumulator`; while
  `StepAccumulator >= StepSeconds`, subtract `StepSeconds` and run **one** `step`. Cap
  catch-up at a few steps per frame (§13) to avoid spiral-of-death.
- `step` (internal): dequeue one turn → compute next head cell (apply wrap if configured)
  → if wall/self collision then `Screen = GameOver`, update `HighScore`; else prepend head;
  if next cell == food then `Score += 10`, `FoodEaten += 1`, recompute `StepSeconds`,
  `PendingGrowth += GrowthPerFood`, respawn food (win check if board full); if
  `PendingGrowth > 0` then decrement it and keep tail, else drop tail.

### view
Pure projection of `Model` → draw commands. Renders the grid frame, the food cell, each
snake body cell, and the HUD/overlay appropriate to `Screen`. No mutation, no timing
logic; Skia executes the draw list.

### Subscriptions
- A 60 FPS frame timer dispatching `Tick dt` with `dt` in seconds (target ~0.0167).
- Keyboard subscription mapping key-down events to `TurnRequested` / `TogglePause` /
  `StartGame` / `Restart` / `QuitToTitle` / `ToggleWrapMode`.

## 8. Rendering (Skia 2D)
Coordinate system matches the logical 1280×720 playfield; integer cell math scaled by 40.

Draw order (back to front):
1. **Background** — fill `#0E1116` (near-black slate) over the full 1280×720.
2. **Playfield frame** — 4 px stroke rect inset 6 px from edges, color `#2A3340`.
3. **Grid (optional, subtle)** — 1 px lines at every 40 px, color `#171C24`. Can be
   toggled off; off by default for a cleaner look.
4. **Food** — filled rounded rect (corner radius 8) inside the cell, inset 6 px, color
   `#E5484D` (red), with a 2 px lighter highlight `#FF6369`.
5. **Snake body** — each cell a rounded rect (corner radius 6) inset 2 px (so a 36×36
   visible block with a 4 px gap forming segment seams). Body color `#30A46C` (green);
   **head** drawn brighter `#4CC38A` with two small 4 px eye dots oriented toward the
   heading.
6. **HUD** — score text top-left (see §9).
7. **Overlays** — Title / Pause / GameOver dim the field with a `#000000` at 55% alpha
   panel, then center text.

- Font: a clean sans (e.g. "Inter"/system default), score at 28 px, titles at 56 px,
  prompts at 24 px, all `#E6EDF3`.
- **Redraw strategy:** full redraw each frame (the scene is tiny — ≤576 rects — so partial
  invalidation is unnecessary). Clear to background, then paint the draw list.
- No camera, no transforms beyond the static logical→pixel scale.

## 9. UI / HUD / Screens

**Title screen**
- Centered title "SNAKE" at y≈260.
- Prompt "Press Enter to Start" at y≈400.
- Mode line: "Walls: [Death] / [Wrap] — press M to toggle" at y≈460 reflecting `WrapWalls`.
- High score shown bottom-center: "Best: NNNN".

**Play HUD**
- Top-left: "Score: NNNN" at (24, 20).
- Top-right: "Best: NNNN" right-aligned at (1256, 20).
- Optional small "x.xx s/step" speed readout bottom-left (debug; off by default).

**Pause overlay**
- Dim panel + centered "PAUSED" and "Press P to Resume / Esc to Quit".

**Game Over overlay**
- Dim panel + centered "GAME OVER", "Score: NNNN", "Best: NNNN", and "Press Enter to
  Restart". If a new best was set, show "NEW BEST!" above the score in `#E5484D`.

## 10. Audio
Checklist (optional in v1):
- [ ] Eat pellet → short blip (rising).
- [ ] Turn committed → soft tick (very quiet; optional).
- [ ] Death/collision → descending buzz/thud.
- [ ] New high score → 3-note jingle on Game Over.
- [ ] Menu confirm (Start/Restart) → UI click.
- [ ] Music: optional low ambient loop during Play; silence on menus.

## 11. Win / Loss / Scoring
- **Scoring:** +10 points per pellet eaten. `Score = FoodEaten * 10`. No combo/time bonus
  in v1.
- **High score:** `max(Score, HighScore)`, persisted (§13).
- **Loss:** wall collision (Wall mode) or self-collision (both modes). Single life, no
  continues — death ends the run immediately.
- **Win:** the snake fills all **576** cells (no free cell remains for food). This is a
  perfect game; show a distinct "PERFECT!" message on the Game Over screen and treat the
  run as a win. (Practically rare, but must be handled — see §14 scenario 8.)

## 12. Difficulty & Balancing
| Parameter | Default | Range | Effect |
|---|---|---|---|
| `cols` | 32 | 16–48 | Board width in cells |
| `rows` | 18 | 12–32 | Board height in cells |
| `baseStepSeconds` | 0.18 | 0.10–0.30 | Starting step interval (lower = faster) |
| `minStepSeconds` | 0.06 | 0.04–0.12 | Fastest step interval (speed cap) |
| `stepDecrement` | 0.006 | 0.000–0.02 | Speed-up per pellet (0 disables ramp) |
| `growthPerFood` | 1 | 1–5 | Cells gained per pellet |
| `wrapWalls` | false | bool | Wrap edges vs. wall death |
| `startLength` | 3 | 1–6 | Initial snake length |
| `pointsPerFood` | 10 | 1–100 | Score per pellet |

All live in `Config` so balance is data-driven and testable without code changes.

## 13. Technical Notes
- **Timestep:** fixed-step simulation via accumulator. `Tick dt` banks real time;
  `step` runs at the current `StepSeconds`. This keeps speed identical regardless of
  render FPS. Clamp catch-up to **max 4 steps per frame** to avoid a spiral of death after
  a stall; drop excess accumulator beyond that.
- **Performance budget:** ≤576 cells, one food, one HUD pass — trivially within the
  16.7 ms/60 FPS budget. Full-clear redraw is fine.
- **Determinism / RNG:** food placement uses `Model.Rng` (`System.Random`). For
  reproducible tests, seed it (e.g. `Random(12345)`) so a given input sequence yields a
  deterministic food sequence. Tests should inject a seeded RNG.
- **Collision/spawn efficiency:** maintain a `HashSet<Cell>` mirror of the body for O(1)
  membership; spawn food by sampling the free-cell set (or rejection-sample then fall
  back to enumerating free cells when the board is dense).
- **Persistence:** high score saved to local storage / a small JSON file
  (`snake_highscore.json`) keyed per `wrapWalls` mode; loaded on Title.
- **Edge cases:** (a) eating the last free cell = win, not a normal spawn; (b) head moving
  into the vacating tail cell is legal when not growing; (c) buffered opposite-direction
  inputs must never reverse the snake; (d) pausing mid-accumulation must not lose or
  fast-forward banked time on resume (freeze the accumulator); (e) very small boards must
  still place a valid start snake and food.

## 14. Acceptance Criteria (test scenarios)

1. **Basic step (core mechanic).**
   Given a new game with the snake heading Right at head `(16,9)`,
   When one step occurs,
   Then the head is at `(17,9)`, the snake length is unchanged (3), and the old tail cell
   `(14,9)` is now empty.

2. **Eat and grow + score.**
   Given the snake head at `(16,9)` heading Right and food at `(17,9)`,
   When one step occurs,
   Then the head is at `(17,9)`, snake length becomes 4, `Score` increases by 10,
   `FoodEaten` becomes 1, and a new food appears in a cell not occupied by the snake.

3. **Speed accelerates with length.**
   Given `baseStepSeconds = 0.18`, `stepDecrement = 0.006`, after eating 5 pellets,
   When `StepSeconds` is read,
   Then it equals `0.18 - 5*0.006 = 0.15` s (and never drops below `minStepSeconds = 0.06`).

4. **180° reversal is blocked (input scenario).**
   Given the snake heading Right,
   When `TurnRequested Left` is dispatched and then a step occurs,
   Then the heading remains Right (the reversing turn was rejected, not enqueued) and the
   head advances to the next Right cell.

5. **Direction queue buffers two turns.**
   Given the snake heading Right and the tick interval not yet elapsed,
   When `TurnRequested Up` then `TurnRequested Right` are dispatched before the next step,
   Then the next step turns the head Up and the subsequent step turns it Right (both
   buffered turns are honored in order).

6. **Wall death (default mode).**
   Given `wrapWalls = false` and the head at `(31,9)` heading Right,
   When one step occurs,
   Then the head would exit the grid, the snake dies, and `Screen` becomes `GameOver`.

7. **Wrap mode survives the edge.**
   Given `wrapWalls = true` and the head at `(31,9)` heading Right,
   When one step occurs,
   Then the head wraps to `(0,9)` and the snake is still alive (`Screen = Playing`).

8. **Self-collision death (and tail-follow exception).**
   Given a snake long enough that the cell directly ahead of the head is part of its body
   (and that cell is NOT the vacating tail),
   When one step occurs,
   Then the snake dies and `Screen` becomes `GameOver`.
   And given the cell ahead is exactly the current tail and the snake is not growing,
   When one step occurs,
   Then the move is legal and the snake survives.

9. **High score persists across runs.**
   Given a run ended with `Score = 120` and previous `HighScore = 90`,
   When the GameOver screen is shown and a new game is started,
   Then `HighScore = 120` is displayed and retained.

10. **Pause freezes simulation.**
    Given `Screen = Playing` with a partially filled `StepAccumulator`,
    When `TogglePause` is dispatched and several `Tick` messages arrive,
    Then no `step` occurs and the snake/food are unchanged until `TogglePause` resumes play.

11. **Food never spawns on the snake.**
    Given any game state with N body cells,
    When food is (re)spawned,
    Then `Food.Pos` is not a member of the snake body.

12. **Perfect-game win.**
    Given the snake occupies 575 of 576 cells with food in the last free cell,
    When the head eats that pellet,
    Then there are no free cells, the game is won, and a "PERFECT!" win state is shown.

## 15. Stretch Goals
1. **Obstacles / maze walls** — static blocker cells per level layout.
2. **Multiple food types** — golden pellet (worth 50, +2 growth) with a timeout.
3. **Speed/portal power-ups** — temporary slow-mo or wall-phase pickup.
4. **Two-player co-op or versus** — second snake, shared board, collision rules.
5. **Daily seed challenge** — fixed RNG seed leaderboard for the day.
6. **Difficulty presets** — Casual (no accel), Classic (default), Frenzy (low caps).
7. **Animated interpolation** — smooth sub-cell head movement between steps for visual
   polish (purely cosmetic; sim stays grid-discrete).
8. **Replay/ghost** — record input+seed to replay a run.

## Menu & configuration — the shared game shell

Snake uses the **generic FS.GG game shell** (FS-GG/FS.GG.Rendering#991) — the same
menu/start screen and settings every FS.GG game shares — rather than a bespoke per-game
menu. Snake supplies only its **name**, its **key→command map** (the rebindable actions from
§3 Controls), and its play `update`/`view`; the shell provides everything below.

- **Main menu / start screen** — the game's name (**Snake**) as the title label, with
  **Start**, **Config**, and **Exit**. This supersedes the bespoke §9 Title-screen "Press
  Enter to Start" affordance for launching a run. (The `wrapWalls` mode toggle of §9 remains
  a Snake-specific choice, exposed either on the shell menu as an extra row or as a Config
  row — see below.)
- **`Esc` from gameplay** opens the pause menu (Resume · Config · Exit to menu) over the
  same shell; `Esc` again resumes. This is the shell home for the §3 `Space` / `P` pause and
  the §3 `Esc` quit-to-title action and the §9 Pause overlay.
- **Config / Settings**, all applied live and persisted across restarts:
  - **Screen resolution** and **fullscreen** (windowed / borderless / fullscreen), driven
    through the SkiaViewer window-behavior + `LogicalCanvas` letterbox seam — the same seam
    that scales the logical 1280×720 playfield (§4.1, §8) to the window.
  - **Key rebinding** — the player remaps Snake's controls (the §3 actions: turn
    Up/Down/Left/Right, pause, start/restart, quit-to-title, toggle wrap mode) via the
    `Controls.KeyRebind` UI over the `KeyboardInput.Keymap` mechanism; bindings persist via
    `KeymapCodec` (JSON), beside Snake's other saved config (e.g. `snake_highscore.json`,
    §13). The 180°-reversal and direction-queue rules (§4.3) apply to whatever keys are bound
    to each turn.
  - (Game-specific rows such as the `wrapWalls` walls-death/wrap mode may be added as extra
    Config rows, but the menu, Esc routing, display settings, and rebind screen come from the
    shell.)

The shell is pointer- and keyboard-navigable over the interactive Controls host (the
`fs-gg-skiaviewer` "game → pointer host" recipe). It is a shared dependency, so Snake does
**not** re-specify menu-stack/cursor/settings machinery of its own.

## 16. Milestone Roadmap

Delivery is milestone-sequenced (M0..Mn), each a small, demonstrable slice grounded in the
sections above. Earlier milestones stand up the deterministic simulation core; later ones
layer feel, the shared shell, audio, and the acceptance harness.

### M0 — Scaffold & fixed-step loop
Stand up the Elmish/MVU app (§7) on the FS.GG.Rendering host: the `Model`/`Msg` skeleton,
the 60 FPS `Tick dt` subscription, the **step accumulator** that banks real time and runs
one `step` per `StepSeconds` with catch-up clamped to ≤ 4 steps/frame (§4.6, §7, §13), and
an empty 1280×720 / 32×18 logical grid (§4.1, §8) that clears every frame. No gameplay yet —
just a deterministic, steppable loop with `Screen = Title`.

### M1 — Grid, snake & basic stepping
Place the length-3 snake at center `(16,9)` heading Right (§5.1) and implement discrete
one-cell-per-step movement (§4.2): prepend head, drop tail, integer `(col,row)` math on the
40×40 cell grid. This is the core "turn" verb's substrate before food or death exist.

### M2 — Direction queue & 180° reversal guard
Implement the capacity-2 direction queue (§4.3): `TurnRequested` enqueues a turn only if it
is not the opposite of the most-recent committed/queued direction; each step dequeues at
most one turn (defense-in-depth reversal check). This is what lets a player buffer a two-step
corner without folding the snake onto itself.

### M3 — Food, eating, growth & scoring
Add the single food pellet (§4.4, §5.2) spawned uniformly on an unoccupied cell; on the head
stepping onto it, grow by +1 (retain tail this step, §4.5), `Score += 10`, `FoodEaten += 1`,
and respawn a new pellet. Maintain the `HashSet<Cell>` occupancy mirror (§13) for O(1)
collision and spawn checks.

### M4 — Speed ramp
Wire the time-based acceleration (§4.6): `StepSeconds = max(minStepSeconds, baseStepSeconds −
foodEaten·stepDecrement)` (0.18 → 0.06 floor over 20 pellets), recomputed on each eat, fed
through the accumulator so speed is identical regardless of render FPS.

### M5 — Collision, death & wrap mode
Implement the loss rules (§4.7): wall death when the next head cell exits `[0,31]×[0,17]`
(Wall mode), self-collision death with the vacating-tail exception, and the `wrapWalls`
option (§4.8) that wraps edges instead of dying. Death transitions to `GameOver`; add the
perfect-game **win** when the snake fills all 576 cells (§11).

### M6 — Phase flow & high score
Wire the full `Screen` machine (§7): `Title → Playing → (Paused | GameOver)` plus quit-to-
title and the `ToggleWrapMode` Title option, `StartGame`/`Restart` building a fresh centered
run while preserving `HighScore` and `Config`, pause freezing the accumulator (§13), and
high-score persistence keyed per wrap mode (§13).

### M7 — Rendering, HUD & overlays
Complete the back-to-front draw list (§8): background, inset playfield frame, optional subtle
grid, the rounded-rect food with highlight, snake body/head (brighter head + heading-oriented
eye dots), the HUD score/best (§9), and the Title/Pause/GameOver overlays with dim panels
(including "NEW BEST!" and the "PERFECT!" win state).

### M8 — Menus, settings & key rebinding (shared game shell)
Adopt the generic game shell (FS-GG/FS.GG.Rendering#991): main menu (title **Snake** +
Start/Config/Exit), `Esc` pause routing (Resume · Config · Exit to menu), Settings with
screen resolution + fullscreen through the SkiaViewer + `LogicalCanvas` letterbox seam, and
in-game key rebinding of the §3 controls (turn keys, pause, start/restart, quit, wrap
toggle), persisted via `KeymapCodec`. Snake provides its name + key→command map + play
`update`/`view`; the shell provides the rest. No bespoke menu system — this replaces the
ad-hoc Title/Pause launch affordances of §9.

### M9 — Audio
Wire the SFX checklist (§10): eat-pellet rising blip, optional soft turn tick, death
descending buzz/thud, new-high-score 3-note jingle, menu-confirm click, and the optional low
ambient loop during Play (silence on menus). A shell Config volume row may drive levels.

### M10 — Acceptance & determinism
Land the acceptance harness against all 12 scenarios (§14): basic step, eat/grow/score, speed
ramp, blocked 180° reversal, two-turn queue buffering, wall death, wrap survival,
self-collision with tail-follow exception, high-score persistence, pause-freezes-simulation,
food-never-on-snake, and the perfect-game win — plus the seeded-RNG + input-sequence
**determinism** replay yielding an identical food sequence and final state (§13).
