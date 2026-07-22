---
title: "Space Invaders"
slug: space-invaders
category: games
complexity: simple
genre: "Fixed-shooter / arcade"
target_session_minutes: 5
stack: { rendering: "FS.GG.Rendering (Skia/OpenGL)", arch: "Elmish/MVU", lang: "F#" }
status: spec
---

# Space Invaders

## 1. Overview
You are the last planetary defense cannon, pinned to the bottom of the screen while a
grid of 55 aliens marches relentlessly left, right, and downward toward you. The core
verb is **shoot up while dodging what falls down**. The tension is mechanical and
beautiful: every alien you kill makes the survivors march *faster*, so clearing a wave
is a race against an acceleration curve you yourself trigger. Hide behind crumbling
bunkers, snipe the bonus UFO that streaks across the top, and survive as many waves as
your three lives allow. It is simple, readable, and ruthless.

## 2. Core Game Loop
**Moment-to-moment:** scan the formation → position cannon → fire (one shot in flight)
→ dodge descending bombs → duck behind a bunker → repeat. Secondary beat: a UFO appears
periodically; break rhythm to gamble a shot on it for bonus points.

**Wave loop:** all 55 aliens destroyed → brief pause → next wave spawns one row lower and
slightly faster → repeat indefinitely (endless, score-chasing).

**Session loop:** Title → Play → (lose a life on hit/invasion, respawn if lives remain)
→ Game Over (formation reaches the cannon line OR lives exhausted) → Score + High Score
→ Restart.

## 3. Controls & Input
Keyboard is primary. Movement is **held** (continuous while down); firing is
**edge-triggered** (one discrete shot per key-down, subject to cooldown + one-bullet rule).

| Input | Action | Model |
| --- | --- | --- |
| `Left Arrow` / `A` | Move cannon left | Held (continuous) |
| `Right Arrow` / `D` | Move cannon right | Held (continuous) |
| `Space` | Fire player shot | Edge-triggered (key-down only) |
| `Enter` | Start game / restart from Title or Game Over | Edge-triggered |
| `P` / `Esc` | Toggle pause | Edge-triggered |

Notes: holding `Space` does **not** auto-fire; the player must release and re-press, but
in practice the one-bullet-in-flight rule is the binding constraint. Simultaneous
left+right cancels to zero horizontal velocity.

## 4. Mechanics (detailed)
All positions in logical pixels on a 1280×720 playfield. Origin top-left, +x right,
+y down. The "ground line" (top of bunkers / cannon deck) is at **y = 660**. The
**invasion line** (game-over if any alien reaches it) is at **y = 620**.

### 4.1 Player cannon movement
- Horizontal only, on rail at **y = 640** (cannon top), sprite **48×24 px**.
- Speed: **320 px/s**, no acceleration, no friction (instant start/stop — classic feel).
- Clamped to `[24, 1256]` for the cannon center x (keeps the 48-wide sprite on screen).

### 4.2 Player shot ("laser")
- **One player bullet in flight at a time.** Firing is blocked until the previous bullet
  is destroyed (off-screen or on hit).
- Cooldown: **0.30 s** minimum between shots even after a bullet clears (prevents
  machine-gunning on fast kills).
- Bullet size **4×16 px**, velocity **−620 px/s** (upward), spawns at cannon muzzle
  (center x, y = 636).
- Destroyed when: hits an alien, hits a bunker block, hits the UFO, hits an enemy bomb
  (mutual cancel — see 4.6), or y < 0 (top edge).

### 4.3 Alien formation
- Grid **5 rows × 11 columns = 55 aliens**.
- Cell spacing: **48 px horizontal pitch**, **48 px vertical pitch**. Alien sprites are
  **32×24 px**, centered in cells.
- Initial formation top-left at **(x = 180, y = 120)** for the top row; rows stack
  downward. Formation bounding box is computed from *living* aliens only.
- Row identity / point values (top to bottom of the spawned grid):
  | Rows | Type | Sprite | Points |
  | --- | --- | --- | --- |
  | Row 0 (top) | "Squid" (small) | 24×24 | **30** |
  | Rows 1–2 | "Crab" (medium) | 32×24 | **20** |
  | Rows 3–4 (bottom) | "Octopus" (large) | 36×24 | **10** |

### 4.4 March step & acceleration (the heart)
The formation moves in **discrete steps**, not continuously. On each step, every living
alien jumps **8 px** in the current horizontal direction. The interval between steps
shrinks as aliens die — fewer aliens = faster march.

- Step interval is a function of living alien count `n` (0..55):
  `stepIntervalMs = lerp(48 → 800, n/55)` clamped, i.e.
  `intervalMs = 48 + (800 - 48) * (n / 55.0)`.
  - n = 55 → **800 ms/step** (slow, ominous).
  - n = 27 → **~417 ms/step**.
  - n = 1 → **~62 ms/step** (frantic single-alien sprint).
- Per **wave**, multiply the resulting interval by a wave speedup factor
  `waveFactor = 0.92 ^ (wave - 1)` (each wave ~8% faster), clamped so interval ≥ **40 ms**.
- The march is a *fixed step on a timer*, independent of frame dt; the accumulator
  carries leftover time so timing is deterministic regardless of FPS.

### 4.5 Edge detection & drop
- After the formation *would* step, test the living-alien bounding box against the side
  walls: left wall **x = 24**, right wall **x = 1256**.
- If the next horizontal step would push any living alien past a wall:
  1. **Do not** apply the horizontal step.
  2. Drop the entire formation **down by 24 px** (one row's worth of descent), and
  3. **Reverse** horizontal direction.
- Only one drop+reverse per step (no double-bounce in a single frame).
- If, after a drop, the bottom of any living alien reaches **y ≥ 620** (invasion line),
  the game ends immediately (loss — see 11).

### 4.6 Alien bombs (enemy fire)
- Only the **lowest living alien in each column** may drop bombs.
- Fire cadence: every **1.0 s** the game attempts a drop; probability scales with march
  speed and wave. Base attempt picks a random eligible column with chance
  `pFire = clamp(0.35 + 0.05*(wave-1) + (55 - n)*0.004, 0, 0.95)` per attempt.
- Max **3 enemy bombs** on screen at once.
- Bomb size **6×16 px**, velocity **+220 px/s** (downward, +10 px/s per wave).
- Two visual/behavior types alternate (cosmetic in v1): straight bomb and zig-zag bomb;
  v1 may implement straight only.
- A bomb is destroyed when: it hits the cannon (player loses a life), hits a bunker block
  (erodes it), hits the player bullet (both cancel — 50% chance the bomb survives in the
  arcade; v1 = always mutual destroy), or y > 720.

### 4.7 Bunkers (destructible cover)
- **4 bunkers**, evenly spaced along the bottom. Bunker centers at
  **x = 240, 520, 800, 1080**; top at **y = 560**.
- Each bunker is a grid of **destructible blocks**: **22 cols × 16 rows** of **4×4 px**
  cells (≈ 88×64 px), pre-carved into the classic arch/notch silhouette (bottom-center
  doorway, sloped top corners) by masking out cells at init.
- Erosion: any bullet (player or enemy) that overlaps a *solid* cell destroys a small
  cluster — the hit cell plus its 4-neighborhood within a **6 px radius** (a small bite),
  then the bullet is consumed.
- Bunkers do **not** regenerate between lives. They **reset fully** at the start of each
  new wave.
- Aliens that physically overlap a bunker (after enough drops) erode the cells they pass
  through.

### 4.8 Mystery UFO
- Spawns from off-screen, traveling horizontally across the top at **y = 80**.
- Trigger: every **20–30 s** (randomized) **and** only while ≥ 8 aliens remain.
- Size **48×20 px**, speed **150 px/s**, direction random (enters left→right or
  right→left), despawns when fully off the opposite edge.
- Scoring on hit: pseudo-random but classic-flavored set
  `{50, 100, 150, 200, 300}` chosen by a seeded table; v1 may use a simple
  `[100;50;150;100;300;...]`-style lookup keyed on the player's cumulative shot count.

## 5. Entities / Game Objects

### Player cannon
- Properties: `pos: x (rail at y=640)`, size 48×24, 1 hitbox.
- States: `Alive → Hit (death anim ~1.0 s, input frozen) → Respawn (if lives>0) | GameOver`.
- Created at wave/game start at center (x = 640). Destroyed on game over.

### Player bullet
- One max. Properties: pos, vel −620 px/s, size 4×16. Created on fire; destroyed per 4.2.

### Alien
- Properties: `gridRow, gridCol, alienType, alive, screenPos (derived from formation
  origin + cell offset)`, size per type, points per 4.3.
- States: `Alive → Dying (explosion sprite ~0.18 s) → Dead`. Animates a 2-frame walk
  cycle toggled on each march step.

### Alien bomb
- Up to 3. Properties: pos, vel +220 px/s, type (straight|zigzag), size 6×16.

### Bunker block
- Many tiny cells. Properties: `solid: bool` per 4×4 cell. No motion. Eroded by bullets.

### UFO
- 0 or 1 active. Properties: pos, vel ±150 px/s, size 48×20, bonusValue.

```fsharp
type AlienType = Squid | Crab | Octopus       // 30 / 20 / 10 pts
type AlienState = Alive | Dying of float       // remaining anim seconds

type Alien =
    { Row: int; Col: int
      Type: AlienType
      State: AlienState }

type BombKind = Straight | ZigZag
type Bomb = { Pos: float * float; Vel: float; Kind: BombKind }

type Bullet = { Pos: float * float; Vel: float }

type Ufo = { Pos: float * float; Vel: float; Bonus: int }

// Bunkers: 4 grids of bool cells (true = solid)
type Bunker = { OriginX: float; OriginY: float; Cells: bool[,] }  // [22,16]
```

## 6. World / Levels / Progression
- Playfield: **1280×720** logical px (letterboxed/scaled to the window by the renderer).
- Key lines: UFO lane y=80, formation start y=120, bunker top y=560, ground y=660,
  cannon rail y=640, invasion line y=620, side walls x=24 / x=1256.
- **Waves** are endless. Each new wave:
  - Respawns the full 5×11 grid, but with the **formation start y lowered by 24 px per
    wave** (wave 1 → y=120, wave 2 → y=144, …), capped at y=240 so it never starts
    unwinnably low.
  - Applies `waveFactor = 0.92^(wave-1)` to march interval (4.4).
  - Increases bomb fall speed (+10 px/s) and `pFire` (4.6).
  - Resets all 4 bunkers to full.
- Difficulty ramp is therefore two-layered: *within* a wave (kills accelerate the march)
  and *across* waves (lower start, faster steps, deadlier bombs).

## 7. State Model (Elmish/MVU)

### Model
```fsharp
type Phase =
    | Title
    | Playing
    | Paused
    | PlayerDying of float          // seconds of death anim remaining
    | WaveCleared of float          // inter-wave pause remaining
    | GameOver

type Model =
    { Phase: Phase
      Wave: int
      Score: int
      HighScore: int
      Lives: int

      // Player
      CannonX: float
      FireCooldown: float           // seconds until next shot allowed
      Bullet: Bullet option         // one-in-flight rule

      // Formation
      Aliens: Alien list            // only Alive/Dying tracked; Dead removed
      FormationX: float             // top-left origin x of grid
      FormationY: float             // top-left origin y of grid
      MarchDir: int                 // -1 left, +1 right
      StepAccumMs: float            // timer accumulator for next step
      ShotCount: int                // drives UFO bonus table

      // Enemy fire
      Bombs: Bomb list              // <= 3
      BombTimer: float

      // UFO
      Ufo: Ufo option
      UfoTimer: float               // seconds until next spawn attempt

      // Cover
      Bunkers: Bunker list          // 4

      // Input (held keys)
      LeftDown: bool; RightDown: bool

      Rng: System.Random }          // seeded for determinism
```

### Msg
```fsharp
type Msg =
    | Tick of float                 // dt in seconds, ~1/60
    | KeyDown of Key
    | KeyUp of Key
    | StartGame                     // Enter on Title/GameOver
    | TogglePause
```

### update — important cases
- **`KeyDown Left/Right`** → set `LeftDown/RightDown = true`. **`KeyUp`** → false.
- **`KeyDown Space`** (Phase=Playing) → if `Bullet=None && FireCooldown<=0`, spawn bullet
  at muzzle, set `FireCooldown=0.30`, `ShotCount+1`.
- **`KeyDown Enter`** → from Title/GameOver: reset to wave 1 fresh Model, Phase=Playing.
- **`TogglePause`** → Playing↔Paused (freezes all Tick integration).
- **`Tick dt`** (Phase=Playing) does the whole simulation in order:
  1. Move cannon by `(RightDown - LeftDown) * 320 * dt`, clamp.
  2. Decrement `FireCooldown` by dt.
  3. Integrate player bullet; test collisions vs aliens / bunkers / UFO / bombs; apply
     score; clear bullet on hit/off-screen.
  4. **March step:** `StepAccumMs += dt*1000`; while `StepAccumMs >= stepInterval`:
     do edge-test → step or (drop+reverse); subtract interval; toggle walk frame. Check
     invasion line → `GameOver`.
  5. Tick `Dying` aliens; drop them to `Dead` (removed) when timer ≤ 0.
  6. **Bombs:** `BombTimer` countdown → attempt fire (4.6); integrate bombs; collisions
     vs cannon (→ lose life), bunkers (erode), player bullet (cancel), off-screen.
  7. **UFO:** `UfoTimer` countdown → maybe spawn; integrate; despawn off-screen.
  8. If `Aliens` empty → `Phase = WaveCleared 1.5`.
- **`Tick`** in `PlayerDying/WaveCleared/PlayerDying` advances the respective timer; on
  expiry, respawn cannon (life lost) or start next wave (`Wave+1`, rebuild grid+bunkers).

### view
Pure projection of `Model` → a Skia draw list. No mutation, no I/O. Renders cannon,
bullet, every Alive/Dying alien at its derived screen pos, bombs, bunker solid cells,
UFO, and the HUD. Phase selects overlay (Title text / Paused dim / Game Over panel).

### Subscriptions
- A **60 FPS tick** subscription emits `Tick dt` with `dt` in seconds (clamped to ≤ 0.05
  to survive stalls).
- Keyboard subscription maps physical key events to `KeyDown/KeyUp/StartGame/TogglePause`.

## 8. Rendering (Skia 2D)
Coordinate system = logical 1280×720, origin top-left; renderer scales to the surface.
Single full-redraw per frame (cheap at these entity counts); no dirty-rect needed.

Draw order (back to front):
1. **Background** — solid `#000000`. Optional starfield: 60 static white dots.
2. **Ground line** — 2 px bar at y=660, color `#33FF33` (phosphor green).
3. **Bunkers** — each solid cell as a 4×4 filled rect, color `#00DD55`.
4. **Aliens** — filled rects/sprites per type. Squid `#FFFFFF`, Crab `#9AE6FF`, Octopus
   `#FF66AA`. 2-frame walk cycle = swap between two sprite glyphs on each march step.
   `Dying` aliens draw a 4-point "splat" glyph in `#FFD23F`.
5. **UFO** — `48×20` rounded rect, color `#FF3B30`, optional 3 px outline `#FFFFFF`.
6. **Player cannon** — `#33FF33`, a 48×8 base + 12×16 barrel centered on top.
7. **Bullets** — player laser `#FFFFFF` (4×16); enemy bombs `#FFD23F` (6×16),
   drawn as a 3-segment zig glyph for `ZigZag`.
8. **HUD overlay** — see section 9.

Fonts: a monospace pixel font (e.g. "PressStart2P" if available, else default monospace),
HUD text size 24 px, large titles 64 px. Particle/effects: brief alien explosion (the
Dying glyph) and a 0.12 s white flash sprite on cannon hit. No camera/scrolling.

## 9. UI / HUD / Screens

**HUD (Playing)** — drawn in `#FFFFFF` monospace, 24 px:
- **Score**: top-left, `SCORE 001230` (6-digit zero-padded) at (24, 24).
- **High score**: top-center, `HI 004500`, centered at x=640, y=24.
- **Wave**: top-right, `WAVE 03` ending at (1256, 24).
- **Lives**: bottom-left at (24, 690) — a numeral plus up to 3 small cannon icons.

**Screens:**
- **Title**: centered `SPACE INVADERS` (64 px), subtitle `PRESS ENTER` (24 px) blinking
  at 1 Hz, plus a small scoring legend (30/20/10 + `?=mystery`).
- **Paused**: freeze the play scene, dim with `#000000` @ 50% alpha, centered `PAUSED`.
- **Game Over**: dim scene, centered `GAME OVER` (64 px), `SCORE nnnnnn` and
  `HI nnnnnn` below, `PRESS ENTER` prompt. If new high score, show `NEW HIGH SCORE!` in
  `#FFD23F`.

## 10. Audio
Checklist (audio optional in v1):
- [ ] **March heartbeat**: 4-note descending loop whose tempo tracks the step interval
      (the iconic accelerating thump).
- [ ] **Player fire**: short pew on shot.
- [ ] **Alien explosion**: noise burst on kill.
- [ ] **Player death**: descending tone on cannon hit.
- [ ] **UFO**: looping warble while UFO on screen; jingle on UFO hit.
- [ ] **Bunker hit**: soft tick (optional).
- [ ] **Wave clear / Game over**: short stings.

## 11. Win / Loss / Scoring
- **Scoring**: Squid 30, Crab 20, Octopus 10 per kill (4.3). UFO awards a value from the
  bonus table (4.8). Score is 6-digit display, internally unbounded.
- **Extra life**: award +1 life at **10,000** points (once). Lives cap at 4 displayed.
- **Lives**: start with **3**. A cannon hit (bomb or alien contact) costs one life and
  triggers `PlayerDying` (1.0 s) then respawn at center if lives remain.
- **Loss (Game Over)** if either:
  - Lives reach 0 after a hit, **or**
  - Any living alien crosses the invasion line **y ≥ 620** (formation reached the deck).
- **"Win"**: there is no terminal win — the game is endless wave survival; clearing a wave
  advances to the next. The objective is a high score.
- **High score** persists across sessions (section 13).

## 12. Difficulty & Balancing
Data-driven tunables (load from a config record so balance is editable without code):

| Name | Default | Range | Effect |
| --- | --- | --- | --- |
| `cannonSpeed` | 320 px/s | 200–500 | Player horizontal speed |
| `fireCooldown` | 0.30 s | 0.15–0.6 | Min time between shots |
| `bulletSpeed` | 620 px/s | 400–900 | Player laser velocity |
| `marchStepPx` | 8 px | 4–16 | Distance per march step |
| `marchDropPx` | 24 px | 12–32 | Descent per edge bounce |
| `stepIntervalMaxMs` | 800 | 400–1200 | Interval at 55 aliens (slowest) |
| `stepIntervalMinMs` | 48 | 30–120 | Interval at 1 alien (fastest) |
| `waveSpeedup` | 0.92 | 0.80–0.98 | Per-wave interval multiplier |
| `bombSpeed` | 220 px/s | 120–400 | Enemy bomb fall speed |
| `bombSpeedPerWave` | 10 px/s | 0–30 | Added bomb speed each wave |
| `maxBombs` | 3 | 1–6 | Concurrent enemy bombs |
| `bombBaseFireP` | 0.35 | 0.1–0.9 | Base per-attempt drop chance |
| `bombInterval` | 1.0 s | 0.4–2.0 | Time between fire attempts |
| `ufoIntervalMin` | 20 s | 10–60 | Min time between UFO spawns |
| `ufoIntervalMax` | 30 s | 15–90 | Max time between UFO spawns |
| `ufoSpeed` | 150 px/s | 80–300 | UFO horizontal speed |
| `startLives` | 3 | 1–5 | Starting lives |
| `extraLifeAt` | 10000 | 0–50000 | Bonus-life score threshold |
| `formationDropPerWave` | 24 px | 0–48 | Lower start per wave |

## 13. Technical Notes
- **Entity budget**: ≤ 55 aliens + 1 bullet + 3 bombs + 1 UFO + 4×(22×16=352) bunker
  cells = ~1468 bunker cells max. Trivial for Skia at 60 FPS / 16.7 ms frame. Cull Dead
  aliens from the list; iterate bunker cells with simple AABB pre-filter (only test the
  ~1 bunker a bullet overlaps).
- **Timestep**: the *march* uses a **fixed-step accumulator** (deterministic regardless
  of FPS); other motion (cannon, bullets, bombs, UFO) uses variable dt integration with
  dt clamped to ≤ 0.05 s. This keeps the iconic march timing exact while keeping motion
  smooth.
- **Determinism/RNG**: a single seeded `System.Random` in the Model drives UFO timing,
  UFO bonus selection, bomb column choice, and bomb-type alternation. Seeding the RNG
  makes full runs reproducible for tests.
- **Persistence**: high score stored to a local file/`localStorage`-equivalent
  (`%score%` integer); loaded on Title, written on Game Over if exceeded.
- **Edge cases**: simultaneous left+right → no move; firing with bullet in flight →
  ignored; bullet and bomb occupying same cell → mutual cancel, no score; last alien
  reaching min interval clamps at 40 ms (never 0/negative); UFO + last alien — UFO
  suppressed once aliens < 8; drop that crosses invasion line ends game before any
  further bomb resolution.

## 14. Acceptance Criteria (test scenarios)
1. **Cannon movement (input)** — *Given* Phase=Playing and cannon at x=640, *When*
   `Right` is held for 1.0 s of ticks at dt=1/60, *Then* CannonX ≈ 960 (±2 px) and is
   clamped to ≤ 1256.
2. **One bullet in flight** — *Given* a player bullet exists, *When* `Space` is pressed,
   *Then* no second bullet spawns and `ShotCount` is unchanged until the first bullet
   clears and `FireCooldown` ≤ 0.
3. **Fire cooldown** — *Given* a bullet just left the top edge at t=0, *When* `Space` is
   pressed at t=0.1 s, *Then* no shot fires; *When* pressed at t=0.31 s, *Then* a shot
   fires.
4. **Alien kill & score** — *Given* a Squid (row 0) and the player bullet overlapping it,
   *When* the tick resolves, *Then* Score increases by 30, the alien enters `Dying`, the
   bullet is removed, and the alien becomes `Dead` after ~0.18 s.
5. **Row point values** — *Given* one alien of each type is shot, *Then* Score gains
   30 (Squid) + 20 (Crab) + 10 (Octopus) = 60 total.
6. **March acceleration** — *Given* a fresh wave (55 aliens) with stepInterval≈800 ms,
   *When* 54 aliens are destroyed (n=1), *Then* the computed stepInterval is ≈ 62 ms
   (strictly monotonically decreasing as n decreases).
7. **Edge detect & drop** — *Given* the formation moving right and the rightmost living
   alien one step from x=1256, *When* the next march step is due, *Then* the formation
   does **not** move horizontally, drops 24 px, and `MarchDir` flips to −1.
8. **Invasion loss** — *Given* a living alien whose bottom is at y=600, *When* a drop
   moves it to y ≥ 620, *Then* Phase becomes `GameOver` immediately.
9. **Bomb hits cannon → lose life** — *Given* Lives=3 and a bomb overlapping the cannon,
   *When* the tick resolves, *Then* Lives=2, Phase=`PlayerDying`, and after the death
   timer the cannon respawns at x=640.
10. **Last life loss → Game Over** — *Given* Lives=1, *When* a bomb hits the cannon,
    *Then* Lives=0 and Phase=`GameOver` (no respawn).
11. **Bunker erosion** — *Given* a full bunker, *When* 3 player bullets strike the same
    column, *Then* solid cells in a ≥6 px radius around each impact become false and a
    visible gap forms; each bullet is consumed on impact.
12. **Bunker wave reset** — *Given* an eroded bunker at wave 1 clear, *When* wave 2
    begins, *Then* all 4 bunkers are fully solid again.
13. **UFO scoring** — *Given* ≥ 8 aliens remain and a UFO is on screen, *When* the player
    bullet hits it, *Then* Score increases by the table value for the current `ShotCount`
    and the UFO despawns.
14. **UFO suppression** — *Given* fewer than 8 aliens remain, *When* `UfoTimer` expires,
    *Then* no UFO spawns.
15. **Wave clear → next wave** — *Given* the last alien is destroyed, *When* the
    `WaveCleared` pause (1.5 s) elapses, *Then* Wave increments, a full 5×11 grid respawns
    one formation-drop lower, and march interval is multiplied by `0.92^(wave-1)`.
16. **Extra life** — *Given* Score 9,980 and Lives 2, *When* a 30-pt Squid is killed
    (Score→10,010 crossing 10,000), *Then* Lives become 3 exactly once.
17. **Determinism** — *Given* two runs seeded identically with an identical scripted input
    sequence, *Then* final Score, Wave, and Lives are identical.

## 15. Stretch Goals
1. **Splitting/zig-zag bombs** with the 50% bullet-survives rule (faithful arcade RNG).
2. **2-player alternating** mode with separate high scores.
3. **Animated UFO bonus reveal** (floating score number on hit).
4. **Color zones** (classic per-y-band tint of the green phosphor look) + CRT scanline
   shader.
5. **Difficulty presets** (Easy/Classic/Insane) driven entirely by the section-12 table.
6. **Online high-score leaderboard**.
7. **Boss wave** every 5th wave (armored alien that takes multiple hits).

## Menu & configuration — the shared game shell

Space Invaders uses the **generic FS.GG game shell** (FS-GG/FS.GG.Rendering#991) — the same
menu/start screen and settings every FS.GG game shares — rather than a bespoke per-game
menu. Space Invaders supplies only its **name**, its **key→command map** (the rebindable
actions from §3 Controls), and its play `update`/`view`; the shell provides everything below.

- **Main menu / start screen** — the game's name (**Space Invaders**) as the title label,
  with **Start**, **Config**, and **Exit**. This supersedes the bespoke Title-screen "PRESS
  ENTER" affordance of §9 for launching a run.
- **`Esc` from gameplay** opens the pause menu (Resume · Config · Exit to menu) over the
  same shell; `Esc` again resumes. This is the shell home for the §3 `P` / `Esc` pause
  toggle and the §9 Paused screen.
- **Config / Settings**, all applied live and persisted across restarts:
  - **Screen resolution** and **fullscreen** (windowed / borderless / fullscreen), driven
    through the SkiaViewer window-behavior + `LogicalCanvas` letterbox seam — the same seam
    that scales the logical 1280×720 playfield (§4, §8) to the window.
  - **Key rebinding** — the player remaps Space Invaders' controls (the §3 actions: move
    cannon left/right, fire, start/restart, pause) via the `Controls.KeyRebind` UI over the
    `KeyboardInput.Keymap` mechanism; bindings persist via `KeymapCodec` (JSON), beside
    Space Invaders' other saved config (e.g. the persisted high score, §13).
  - (Game-specific rows such as difficulty or volume may be added as extra Config rows, but
    the menu, Esc routing, display settings, and rebind screen come from the shell.)

The shell is pointer- and keyboard-navigable over the interactive Controls host (the
`fs-gg-skiaviewer` "game → pointer host" recipe). It is a shared dependency, so Space
Invaders does **not** re-specify menu-stack/cursor/settings machinery of its own.

## 16. Milestone Roadmap

Delivery is milestone-sequenced (M0..Mn), each a small, demonstrable slice grounded in the
sections above. Earlier milestones stand up the deterministic simulation core; later ones
layer feel, the shared shell, audio, and the acceptance harness.

### M0 — Scaffold & fixed-step loop
Stand up the Elmish/MVU app (§7) on the FS.GG.Rendering host: the `Model`/`Msg` skeleton, the
60 FPS `Tick` subscription with variable-dt motion clamped to ≤ 0.05 s plus the separate
fixed-step accumulator that drives the march (§13), and an empty 1280×720 logical canvas
(§4, §8) that clears to `#000000` every frame. No gameplay yet — just a deterministic,
steppable loop with `Phase = Title`.

### M1 — Player cannon movement
Implement the cannon (§4.1, §5): held Left/Right at 320 px/s with instant start/stop and no
acceleration, simultaneous-left+right cancels to zero horizontal velocity, and the
`[24, 1256]` center-x clamp on the rail at y = 640. Draw the phosphor ground line at y = 660.

### M2 — Player shot & fire rules
Add the player laser (§4.2): edge-triggered `Space` fire, the one-bullet-in-flight rule, the
0.30 s cooldown even after a bullet clears, the 4×16 bullet at −620 px/s spawned at the muzzle
(y = 636), and destruction on top-edge exit (y < 0).

### M3 — Alien formation, collision & scoring
Build the 5×11 = 55-alien grid (§4.3) with the Squid/Crab/Octopus rows and their 30 / 20 / 10
point values, the living-only formation bounding box, bullet→alien AABB collision with the
`Dying → Dead` transition, and score accrual (§11). Two-frame walk-cycle swap on each step.

### M4 — March step, acceleration, edge drop & invasion
Implement the heart (§4.4, §4.5): the fixed-step accumulator march at
`intervalMs = 48 + (800−48)·(n/55)` (faster as aliens die), the per-wave `0.92^(wave−1)`
speedup clamped ≥ 40 ms, 8 px discrete steps, edge detection against x = 24 / 1256, the 24 px
drop + direction reverse (one per step, no double-bounce), and immediate `GameOver` when any
living alien crosses the invasion line y ≥ 620.

### M5 — Alien bombs, player death & lives
Add enemy fire (§4.6): lowest-alien-per-column bomb drops on the 1.0 s cadence with `pFire`
scaling by wave and living count, max 3 bombs at +220 px/s (+10 px/s per wave), bullet↔bomb
mutual cancel, cannon hit → `PlayerDying` (1.0 s) → respawn at center, 3 starting lives,
`GameOver` at 0 lives, and the one-time extra life at 10,000 pts (§11).

### M6 — Bunkers (destructible cover)
Build the 4 bunkers (§4.7): 22×16 grids of 4×4 px cells pre-carved into the classic arch
silhouette, 6 px-radius cluster erosion from any bullet (player or bomb) that consumes the
bullet, no regeneration between lives, a full reset each new wave, and alien-overlap erosion.

### M7 — Mystery UFO
Add the UFO (§4.8): the 20–30 s randomized spawn while ≥ 8 aliens remain, 150 px/s horizontal
cross at y = 80 from a random side, seeded bonus-table scoring on hit `{50,100,150,200,300}`
keyed on shot count, and suppression once fewer than 8 aliens remain.

### M8 — Waves, difficulty & persistence
Wire wave progression: `WaveCleared` (1.5 s) → full 5×11 respawn one formation-drop lower with
the `0.92^(wave−1)` interval multiplier and added bomb speed per wave (§4.4 / §4.6), the
data-driven tunables table (§12) so balance is config not code, and high-score persistence
(§13).

### M9 — Rendering, HUD & screens
Complete the back-to-front draw list (§8): phosphor ground line, bunker cells, per-type alien
glyphs + the `Dying` splat, red UFO, green cannon, laser / bomb glyphs, and the HUD (score /
high / wave / life icons, §9) plus the Title / Paused / Game Over overlays with scrims.

### M10 — Menus, settings & key rebinding (shared game shell)
Adopt the generic game shell (FS-GG/FS.GG.Rendering#991): main menu (title **Space Invaders**
+ Start/Config/Exit), `Esc` pause routing (Resume · Config · Exit to menu), Settings with
screen resolution + fullscreen through the SkiaViewer + `LogicalCanvas` letterbox seam, and
in-game key rebinding of the §3 controls, persisted via `KeymapCodec`. Space Invaders provides
its name + key→command map + play `update`/`view`; the shell provides the rest. No bespoke
menu system — this replaces the ad-hoc Title/Pause launch affordances of §9.

### M11 — Audio
Wire the SFX checklist (§10): the accelerating 4-note march heartbeat tracking the step
interval, the player-fire pew, the alien-explosion noise burst, the descending player-death
tone, the UFO warble + hit jingle, the optional bunker tick, and the wave-clear / game-over
stings.

### M12 — Acceptance & determinism
Land the acceptance harness against all 17 scenarios (§14): cannon movement + clamp, the
one-bullet and cooldown rules, alien kill/score and row values, march-acceleration
monotonicity, edge detect & drop, invasion loss, bomb→life-loss and last-life Game Over,
bunker erosion + wave reset, UFO scoring + suppression, wave advance, extra life, and the
seeded + input-log **determinism** replay yielding identical final Score / Wave / Lives
(§14.17, §13).
