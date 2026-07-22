---
title: "Bulwark: Tower Defense"
slug: tower-defense
category: games
complexity: complex
genre: "Tower Defense / Strategy"
target_session_minutes: 25
stack: { rendering: "FS.GG.Rendering (Skia/OpenGL)", arch: "Elmish/MVU", lang: "F#" }
status: spec
---

# Bulwark: Tower Defense

## 1. Overview
You are the warden of a contested mountain pass. Endless columns of marauders march from a breach
in the cliffs toward the heart of your keep; if enough of them reach it, the keep falls. Between
waves you spend hard-won gold to **build, upgrade, and sell towers** along (and around) the path,
shaping a gauntlet of fire, frost, and lightning. The core verb is **placement-as-puzzle**:
each tower is a fixed-cost commitment whose value depends on where you put it, what it can reach,
and which threats are coming next. The fun comes from the escalating arithmetic of waves —
reading the incoming composition (fast/armored/flying/boss), committing scarce gold under interest
pressure, and watching a well-laid kill-zone shred a wave you nearly lost to. A run is a tight,
legible economic-tactics loop that rewards forethought and punishes greedy over-extension.

## 2. Core Game Loop
**Moment-to-moment (Build phase):** survey board → read next wave preview → select tower type →
validate placement (hover ghost) → place / upgrade / sell → repeat until gold is committed → press
*Start Wave*.

**Moment-to-moment (Combat phase):** towers auto-acquire targets per their targeting mode → fire
projectiles → projectiles fly and apply damage/effects → enemies die (award gold) or leak (cost a
life) → wave drains → return to Build phase with interest paid out.

**Session-level:** Title → Map select → Wave 1 build → run all N waves (build/combat alternating,
or continuous "endless" mode) → either **Victory** (survive final boss wave) or **Game Over**
(lives reach 0) → score screen → restart / new map.

```
       ┌──────────── Build phase ───────────┐        ┌─── Combat phase ───┐
START → │ place/upgrade/sell · read preview │ → WAVE │ towers fire · enemies│ → wave clear → (interest)
       └─────────────────▲───────────────────┘        └─────────┬───────────┘            │
                         └──────────────── next wave ◄──────────┴── lives>0 ──────────────┘
                                                    lives==0 → GAME OVER
                                          all waves cleared → VICTORY
```

## 3. Controls & Input
Keyboard-primary with mouse for placement (the genre is mouse-native). Input model noted per row:
edge-triggered = fires once on key-down; held = sampled each frame.

| Input | Action | Model |
|---|---|---|
| Mouse move | Move cursor / update placement ghost & range circle | sampled |
| Left click | Place selected tower / select existing tower / confirm | edge (down) |
| Right click | Cancel current placement / deselect | edge (down) |
| Mouse wheel | Cycle tower type in build palette | edge per detent |
| `1` `2` `3` `4` | Select tower type: Arrow / Cannon / Frost / Tesla | edge |
| `U` | Upgrade selected tower (next tier on active branch) | edge |
| `B` / `V` | Choose upgrade **branch** A / B (when tier 2→3 forks) | edge |
| `S` | Sell selected tower (refund 70%) | edge |
| `T` | Cycle targeting mode of selected tower (First→Last→Strongest→Closest→First) | edge |
| `Space` | Start next wave (Build→Combat) / call wave early | edge |
| `F` | Toggle fast-forward (1×↔2×) — scales sim dt only | edge (toggle) |
| `P` / `Esc` | Pause / open pause menu | edge |
| `Esc` (in placement) | Equivalent to right-click cancel | edge |
| `G` | Toggle build grid overlay | edge (toggle) |
| Mouse hover (≥400 ms) | Tooltip for tower/enemy under cursor | sampled |

Notes: placement is committed on left-click only when the ghost is **valid** (Section 4.7);
an invalid click is a no-op with a short error blip. Calling a wave early (`Space` during Combat,
before the previous wave fully drains, only in continuous mode) awards a time bonus (Section 11).

## 4. Mechanics (detailed)

### 4.1 Board, Grid & Path
The playfield is **1280×720 logical px**. The play area is a **40×22 tile grid** of **32×32 px**
tiles, occupying the region `x∈[0,1280), y∈[0,704)`; the bottom 16 px strip plus the right-side
**260 px build panel** overlay the grid (panel covers tile columns ≥ 32 on UI maps; on full maps the
panel floats translucently — see Section 9). Tile coordinate `(col,row)` maps to pixel center
`(col*32+16, row*32+16)`.

Each tile has a `TileKind`:
- `Buildable` — green-tinted ground; towers may be placed.
- `Path` — the lane enemies walk; **never buildable**.
- `Blocked` — rock/water/decoration; never buildable, blocks pathfinding.
- `Spawn` — single entry tile (enemies appear here).
- `Goal` — single exit/keep tile (a leak here costs a life).

Two map families are supported and selected per map via a flag `mazeBuilding: bool`:

1. **Fixed-path maps (`mazeBuilding=false`).** The path is an authored polyline of **waypoints**
   `Waypoint[]` (pixel coordinates) from Spawn to Goal. Enemies follow it; towers cannot block it.
   Pathfinding is trivial (follow the list). This is the default for the v1 shipped maps.
2. **Maze maps (`mazeBuilding=true`).** Spawn and Goal are open; the path is **computed** by
   A* over the grid (4-neighbour, unit cost) treating `Buildable` placed-with-tower tiles as
   temporarily `Blocked`. Players build towers to *shape* the route. Placement is rejected if it
   would **fully seal** Spawn from Goal (Section 4.7). The path is **recomputed** whenever a tower
   is placed or sold, and **in-flight enemies re-target** to the nearest node on the new path
   (Section 4.3).

### 4.2 Time, Tick & Phases
The game runs at a **fixed simulation timestep of 60 Hz (dt = 1/60 s ≈ 0.0167 s)** with an
accumulator (Section 13). All speeds below are in **logical px/s**; all rates in **per-second**.
Phases: `Building` (sim paused for enemies/projectiles; UI live), `Combat` (full sim),
`Paused`, `WaveCleared` (brief 1.5 s interstitial), `Victory`, `GameOver`.
Fast-forward multiplies the number of fixed steps consumed per real frame by 2 (it does **not**
change dt — determinism preserved).

### 4.3 Enemy Movement & Pathfinding
Enemies are points with a movement radius (visual only). Each enemy stores `pathIndex` (the
waypoint it's heading toward) and `pos`. Per fixed step:
```
target   = waypoints[pathIndex]
toTarget = target - pos
dist     = |toTarget|
step     = effectiveSpeed * dt           // effectiveSpeed includes slow multipliers
if step >= dist:
    pos = target; pathIndex += 1         // snap & advance; if last → leak (Section 4.6)
else:
    pos = pos + (toTarget/dist) * step
```
`effectiveSpeed = baseSpeed * slowFactor` where `slowFactor∈(0,1]` is the strongest active slow
(slows do **not** stack multiplicatively; the **strongest** wins, see 4.5). Flying enemies ignore
the grid/path geometry on maze maps and travel a **straight line Spawn→Goal** (their own 2-waypoint
list); on fixed maps they follow the same polyline as ground units but are only hittable by towers
flagged `canHitAir`.

**Maze re-path:** on recompute, each ground enemy finds the path node nearest its current `pos`
(min Euclidean distance to any waypoint segment) and sets `pathIndex` to that node's successor, so it
rejoins the new route without teleporting. If no path exists (should be impossible — placement is
pre-validated), the last valid path is retained.

### 4.4 Tower Targeting & Firing
Each tower has `range` (px radius from tower center), `fireRate` (shots/s), a `cooldown` timer, a
`targetingMode`, and a `target: EnemyId option`. Per fixed step:
1. Decrement `cooldown` by dt.
2. **Acquire/validate target:** gather enemies within `range` that the tower can hit
   (`canHitAir` gate for flyers). If current target left range/died, drop it. If no target, pick one
   per `targetingMode` (Section 4.8).
3. If `cooldown ≤ 0` and a valid target exists: **fire** (spawn projectile or apply hitscan),
   reset `cooldown = 1/fireRate`, emit muzzle SFX/particle.

Tower aim/rotation is cosmetic except for the visual turret angle (`atan2` to target). Towers never
move and never collide with anything.

### 4.5 Damage, Armor, Resistances & Status Effects
**Base damage application:** `applied = max(1, damage - armor)` for *physical* sources; *elemental*
sources (frost/poison/tesla) ignore armor but are modified by per-enemy **resistance** multipliers
(`resist ∈ [0,1]`, applied as `applied = damage * (1 - resist)`), then floored at 1 unless `resist
== 1.0` (full immunity → 0).

Damage **types**: `Physical` (Arrow, Cannon), `Frost` (Frost — applies Slow), `Poison` (an upgrade —
applies DoT), `Electric` (Tesla — chains). A projectile carries `(amount, type, effectPayload)`.

**Status effects** (stored as a list on each enemy; each has a remaining timer in seconds):
- **Slow** `{ factor: 0.0–1.0, dur }` — multiplies speed. Strongest (lowest factor) active slow
  applies; refreshes duration if a stronger or equal slow is reapplied. e.g. Frost L1 = `factor
  0.6, dur 1.5 s`.
- **Poison/DoT** `{ dps, dur }` — deals `dps*dt` Poison damage each step; multiple stacks **do**
  add (cap 3 stacks). Bypasses armor.
- **Stun** `{ dur }` — `effectiveSpeed = 0` while active (Tesla L3 branch). Strongest = "any active".
- **Vulnerable** `{ bonus, dur }` — incoming damage ×(1+bonus) (Cannon L3-B "Demolition").

Effects tick before movement each step; expired effects are removed.

### 4.6 Lives & Leaks
The player starts with **20 lives**. When an enemy reaches the Goal it "leaks": lives -= enemy's
`leakCost` (1 for normal, 2 for "heavy", boss = remaining-lives-or-10 capped at current lives → see
table). The enemy is removed (no bounty). If `lives ≤ 0` → **GameOver** immediately (current wave
abandoned).

### 4.7 Tower Placement Validation
A placement at tile `(c,r)` for tower `t` (cost `k`) is **valid** iff ALL hold:
1. `(c,r)` is in-grid and `TileKind = Buildable`.
2. No existing tower occupies `(c,r)` (towers are 1×1 tile; "large" towers reserve a 2×2 footprint —
   all four tiles must be Buildable & empty).
3. `gold ≥ k`.
4. The tile is not under the build panel / a HUD rect.
5. **(maze maps only)** After tentatively blocking the footprint, A* still finds a Spawn→Goal path
   **and** every currently-alive ground enemy still has a route. If not → reject ("would seal path").
6. Not within the **no-build margin** of the Spawn tile (2-tile radius) — prevents spawn camping
   abuse on maze maps.

On valid left-click: deduct `gold`, create tower at `cooldown=0`, (maze) recompute path, play
build SFX. On invalid: no-op + error blip + brief red ghost flash.

### 4.8 Targeting Modes
Given the set `C` of in-range, hittable enemies, pick:
- **First** (default): max `progress` (distance traveled along path = `pathIndex` major key, then
  `1 - distToNextWaypoint` minor) — i.e. closest to Goal.
- **Last**: min `progress` (newest/furthest from Goal).
- **Strongest**: max current `hp` (tie → First).
- **Closest**: min Euclidean distance to tower (tie → First).
Targeting is re-evaluated only when the tower has no valid target or its target exits range/dies
(sticky targeting — avoids jitter). Cycled live with `T`.

### 4.9 Economy
- **Starting gold:** 250 (Easy 350 / Hard 180 — Section 12).
- **Bounty:** each enemy awards `bounty` gold on death (table Section 5.2). Leaks award nothing.
- **Interest:** at the end of each Build phase when `Start Wave` is pressed, *before* combat, the
  player earns **interest = floor(gold * 0.08)** capped at **+40/wave** (rewards banking without
  making turtling dominant). Interest is disabled in the first build phase (wave 1).
- **Sell refund:** 70% of total gold invested in that tower (base + upgrades), floored.
- **Upgrade cost:** per tier in the tower table; gold deducted on `U`.
- **Wave-clear bonus:** +`(10 + waveNumber)` gold when a wave is fully cleared with no remaining
  enemies (encourages full clears).

### 4.10 Projectiles & Flight
Two firing models:
- **Projectile** (Arrow, Cannon): spawns a moving entity with `pos`, `vel` (toward target's
  *current* position at fire time — no homing for Cannon; Arrow re-homes 1×/0.1 s toward target),
  `speed` px/s, `damage`, `type`, `effectPayload`, optional `splashRadius`. On reaching target (within
  `arriveEps = 6 px`) or target death: resolve hit. Cannon shells **splash**: all enemies within
  `splashRadius` of impact take damage (center 100%, linear falloff to 50% at edge).
- **Hitscan** (Tesla, Frost-beam upgrade): instantaneous; draws a beam for 0.08 s; applies damage &
  effect immediately. Tesla **chains**: after the primary hit, jumps to up to `chainCount` nearest
  un-hit enemies within `chainRange`, each jump dealing `damage * chainFalloff^k` (k = jump index).

Projectile lifetime cap = 2.0 s (despawn if target lost and not arrived). Max ~400 live projectiles.

## 5. Entities / Game Objects

### 5.1 Towers (build/upgrade)
Base stats (Tier 1). `RoF` = shots/s. Range/splash in px. Damage pre-armor.

| Tower | Key | Cost | Dmg | Range | RoF | Projectile | DmgType | Special | Air? | Footprint |
|---|---|---|---|---|---|---|---|---|---|---|
| **Arrow** | 1 | 70 | 8 | 130 | 1.8 | fast arrow (homing) | Physical | cheap, fast | yes | 1×1 |
| **Cannon** | 2 | 120 | 30 | 110 | 0.6 | lobbed shell | Physical | **splash** r=42 | no | 1×1 |
| **Frost** | 3 | 100 | 5 | 120 | 1.2 | frost bolt | Frost | **slow** f=0.6/1.5s | yes | 1×1 |
| **Tesla** | 4 | 160 | 18 | 140 | 0.9 | hitscan beam | Electric | **chain** ×3, falloff .6 | yes | 1×1 |

**Upgrade trees** (each tower: T1→T2 linear, then T2→T3 forks into branch **A**/**B**, then →T4 on
the chosen branch). Costs are upgrade-only (not cumulative shown). Stats are *replacements*.

**Arrow**
| Tier | Cost | Dmg | Range | RoF | Notes |
|---|---|---|---|---|---|
| T1 | (70) | 8 | 130 | 1.8 | — |
| T2 | 60 | 12 | 145 | 2.2 | Sharper Heads |
| **T3-A Sniper** | 130 | 40 | 230 | 1.0 | +crit 15% ×2; Strongest-target affinity |
| **T3-B Volley** | 130 | 9 | 150 | 4.5 | fires 2 arrows; great vs swarms |
| T4-A Marksman | 240 | 90 | 270 | 1.1 | ignores 50% armor |
| T4-B Storm | 240 | 11 | 160 | 6.0 | fires 3 arrows |

**Cannon**
| Tier | Cost | Dmg | Range | RoF | Splash | Notes |
|---|---|---|---|---|---|---|
| T1 | (120) | 30 | 110 | 0.6 | 42 | — |
| T2 | 110 | 45 | 120 | 0.7 | 48 | Bigger Shells |
| **T3-A Mortar** | 220 | 70 | 200 | 0.45 | 70 | long range, huge splash |
| **T3-B Demolition** | 220 | 60 | 120 | 0.8 | 52 | applies **Vulnerable** +25%/2s |
| T4-A Siege | 360 | 130 | 230 | 0.45 | 85 | — |
| T4-B Breaker | 360 | 85 | 125 | 0.9 | 55 | Vulnerable +40%/3s; +50% vs armored |

**Frost**
| Tier | Cost | Dmg | Range | RoF | Slow | Notes |
|---|---|---|---|---|---|---|
| T1 | (100) | 5 | 120 | 1.2 | f0.6/1.5s | — |
| T2 | 90 | 7 | 130 | 1.3 | f0.5/1.8s | Deeper Chill |
| **T3-A Glacier** | 180 | 9 | 140 | 1.3 | f0.35/2.2s | strongest slow in game |
| **T3-B Frostbite** | 180 | 8 | 135 | 1.4 | f0.5/1.8s | adds **Poison** 6 dps/2s (frost-burn) |
| T4-A Absolute Zero | 300 | 12 | 150 | 1.4 | f0.25/2.5s | 8% chance 0.6s **Stun** |
| T4-B Pandemic | 300 | 10 | 140 | 1.6 | f0.5/2s | Poison 12 dps/3s, spreads on death r=40 |

**Tesla**
| Tier | Cost | Dmg | Range | RoF | Chain | Notes |
|---|---|---|---|---|---|---|
| T1 | (160) | 18 | 140 | 0.9 | ×3 f.6 | — |
| T2 | 140 | 26 | 150 | 1.0 | ×3 f.65 | Higher Voltage |
| **T3-A Arc** | 260 | 34 | 165 | 1.1 | ×5 f.7 | mass chain |
| **T3-B Overload** | 260 | 60 | 150 | 1.2 | ×2 f.6 | 12% chance 0.5s **Stun** |
| T4-A Tempest | 420 | 48 | 180 | 1.3 | ×7 f.75 | — |
| T4-B Railgun | 420 | 120 | 160 | 1.2 | ×2 f.6 | 20% **Stun** 0.7s; pierces |

F# sketch:
```fsharp
type TowerKind = Arrow | Cannon | Frost | Tesla
type Branch = None | A | B
type TargetingMode = First | Last | Strongest | Closest

type Tower = {
    Id: TowerId
    Kind: TowerKind
    Tile: int * int
    Pos: Vec2                 // pixel center
    Tier: int                 // 1..4
    Branch: Branch
    Range: float
    Damage: float
    FireRate: float           // shots/s
    Cooldown: float           // seconds until next shot
    DamageType: DamageType
    Special: TowerSpecial     // Splash/Slow/Chain/Poison/Vulnerable/None
    CanHitAir: bool
    Targeting: TargetingMode
    Target: EnemyId option
    Angle: float              // turret render angle
    GoldInvested: int }       // for sell refund
```

### 5.2 Enemies
`HP`, `Speed` px/s, `Armor` (flat, physical only), `Resist` map, `Fly`, `Bounty`, `LeakCost`.

| Enemy | HP | Speed | Armor | Resists | Fly | Bounty | Leak | Notes |
|---|---|---|---|---|---|---|---|---|
| **Grunt** | 40 | 55 | 0 | — | no | 4 | 1 | baseline swarm |
| **Runner** | 25 | 110 | 0 | — | no | 5 | 1 | fast, fragile |
| **Brute** | 160 | 40 | 6 | — | no | 10 | 2 | armored tank |
| **Shielded** | 120 | 50 | 12 | Physical .0 / Frost .5 | no | 12 | 1 | heavy armor, frost-resist |
| **Wisp** | 60 | 70 | 0 | Electric .6 | **yes** | 9 | 1 | flying, shrugs Tesla |
| **Spectre** | 90 | 65 | 0 | Frost 1.0 (immune) | no | 11 | 1 | cannot be slowed |
| **Healer** | 110 | 48 | 2 | — | no | 14 | 1 | heals nearby allies 6 hp/s r=60 |
| **Swarmling** | 12 | 90 | 0 | — | no | 1 | 1 | spawns in packs of 8 |
| **Juggernaut (mini-boss)** | 900 | 35 | 10 | Frost .5 / Poison .5 | no | 60 | 4 | wave 10/20 |
| **Wyrm (boss)** | 4000 | 30 | 15 | Frost .5/Elec .3/Poison .25 | no | 200 | 10 | final wave; spawns 2 Wisp on death |

F# sketch:
```fsharp
type EnemyKind = Grunt | Runner | Brute | Shielded | Wisp | Spectre | Healer | Swarmling | Juggernaut | Wyrm
type StatusEffect =
    | Slow of factor:float * remaining:float
    | Poison of dps:float * remaining:float
    | Stun of remaining:float
    | Vulnerable of bonus:float * remaining:float

type Enemy = {
    Id: EnemyId
    Kind: EnemyKind
    Hp: float
    MaxHp: float
    BaseSpeed: float
    Armor: float
    Resists: Map<DamageType, float>
    Fly: bool
    Bounty: int
    LeakCost: int
    Pos: Vec2
    PathIndex: int
    Effects: StatusEffect list }
```

### 5.3 Projectiles
```fsharp
type Projectile = {
    Id: ProjId
    Source: TowerId
    Pos: Vec2
    Vel: Vec2
    Speed: float
    Damage: float
    DamageType: DamageType
    Target: EnemyId option     // for homing/aim
    SplashRadius: float        // 0 = single target
    Effect: StatusEffect option
    Homing: bool
    Life: float }              // seconds remaining (cap 2.0)
```
Created when a tower fires; destroyed on arrival/hit, on splash resolution, on target loss + life
expiry, or off-board. Hitscan (Tesla/Frost-beam) does not create a `Projectile` — it resolves
instantly and pushes a transient `BeamFx` to the effects layer.

## 6. World / Levels / Progression
**Playfield:** 1280×720 logical px (Section 4.1). Default ships **3 maps**: *Serpentine* (fixed
S-curve path, beginner), *Crossroads* (fixed two-merge path, medium), *The Labyrinth*
(`mazeBuilding=true`, expert).

**Wave structure:** a campaign is **20 waves**; victory = survive wave 20 (the Wyrm). Each wave is a
spawn timeline (Section 4.2 / scheduler below). Difficulty ramp:
- Waves 1–4: Grunts/Runners, small counts (8–14). Teaching economy.
- Waves 5–9: introduce Brute (w5), Wisp/flying (w6), Shielded (w7), Healer (w8), Swarmling packs (w9).
- **Wave 10:** Juggernaut mini-boss + escort.
- Waves 11–14: mixed armored+flying, larger counts, Spectre (w12).
- Waves 15–19: dense mixed waves, two-front (split spawn timing), faster cadence.
- **Wave 20:** Wyrm boss + continuous trickle of Wisps.

**Escalation knobs per wave** `w`: base count `≈ 6 + 1.4*w`; enemy HP global multiplier
`hpScale(w) = 1 + 0.06*(w-1)` applied on top of table HP; spawn interval shrinks
`max(0.35, 0.9 - 0.02*w)` s. Boss waves override with hand-authored timelines.

**Wave timeline / scheduler.** A wave is a list of timed spawn groups:
```fsharp
type SpawnGroup = { At: float; Kind: EnemyKind; Count: int; Interval: float }  // At = seconds from wave start
type Wave = { Number: int; Groups: SpawnGroup list; Reward: int }
```
Example **Wave 7** (introduces Shielded):
```
At 0.0  Grunt    ×10  every 0.6
At 4.0  Runner   ×6   every 0.4
At 8.0  Shielded ×4   every 1.2
At 12.0 Brute    ×3   every 1.5
```
Scheduler keeps `waveClock` (seconds since wave start) and a per-group emit cursor; each fixed step,
for every group, while `waveClock ≥ At + emitted*Interval` and `emitted < Count`, spawn one enemy at
the Spawn tile and `emitted += 1`. A wave is **complete** when all groups exhausted **and** no enemies
remain alive on board → transition `WaveCleared` (1.5 s) → `Building` (next wave) → pay interest &
wave-clear bonus.

## 7. State Model (Elmish/MVU)

### Model
A single layered record; sub-records keep update cases focused.
```fsharp
type Phase = Building | Combat | WaveCleared of timer:float | Paused of prev:Phase | Victory | GameOver

type BoardState = {
    Grid: TileKind[,]            // 40×22
    MazeBuilding: bool
    Waypoints: Vec2[]            // active path (fixed: authored; maze: computed)
    SpawnTile: int*int
    GoalTile: int*int }

type EconomyState = {
    Gold: int
    Lives: int
    Score: int
    InterestRate: float          // 0.08
    InterestCap: int }           // 40

type WaveState = {
    Index: int                   // 0-based into Waves
    Waves: Wave[]
    Clock: float                 // seconds since wave start
    Emitted: int[]               // per-group emit count
    AllSpawned: bool }

type Selection =
    | NoSelection
    | PlacingTower of TowerKind            // ghost follows cursor
    | TowerSelected of TowerId

type Model = {
    Phase: Phase
    Board: BoardState
    Towers: Map<TowerId, Tower>
    Enemies: Map<EnemyId, Enemy>
    Projectiles: Map<ProjId, Projectile>
    Effects: TransientFx list              // beams, explosions (render-only, ticked)
    Wave: WaveState
    Econ: EconomyState
    Selection: Selection
    Cursor: Vec2
    HoverTile: (int*int) option
    Difficulty: Difficulty
    FastForward: bool
    Rng: RngState                          // seeded, deterministic (Section 13)
    NextId: int
    Stats: RunStats }                      // kills, leaks, dmg, for score screen
```

### Msg
```fsharp
type Msg =
    // input
    | MouseMoved of Vec2
    | LeftClick of Vec2
    | RightClick
    | SelectKind of TowerKind
    | UpgradeSelected
    | ChooseBranch of Branch
    | SellSelected
    | CycleTargeting
    | StartWave
    | ToggleFastForward
    | ToggleGrid
    | TogglePause
    | RestartRun | NewMap of MapId
    // sim
    | Tick of dt:float           // one or more fixed steps; see subscriptions
```

### update (important cases)
- **`SelectKind k`** → `Selection = PlacingTower k` (only meaningful; placement happens on click).
- **`LeftClick p`** → if `PlacingTower k`: validate (4.7); on valid, deduct gold, insert Tower,
  (maze) recompute waypoints + re-path enemies; on invalid, emit error blip. If clicking an existing
  tower → `TowerSelected id`. Else `NoSelection`.
- **`UpgradeSelected` / `ChooseBranch`** → resolve next tier on tower's branch; if a fork tier and no
  branch chosen, require `ChooseBranch` first; deduct cost; replace tower stats; add to `GoldInvested`.
- **`SellSelected`** → refund `floor(GoldInvested*0.7)`, remove tower, (maze) recompute + re-path.
- **`CycleTargeting`** → rotate selected tower's `Targeting`.
- **`StartWave`** → only in `Building`; pay interest (`min(cap, floor(gold*rate))`, skipped wave 1),
  reset `Wave.Clock=0`, `Emitted=0…`, `Phase=Combat`.
- **`Tick dt`** → the simulation core (Section 4): for each fixed step, in order:
  1. advance wave scheduler (spawn enemies),
  2. tick enemy status effects (slow/poison/stun/vulnerable; apply DoT, expire),
  3. healer aura heals,
  4. move enemies; detect leaks (lose lives, on `lives≤0`→GameOver),
  5. towers acquire/validate targets & fire (spawn projectiles / resolve hitscan + chains),
  6. move projectiles; resolve hits (damage, splash, effects); award bounty on kills,
  7. tick transient FX,
  8. check wave completion → `WaveCleared`/`Victory`.
- **`TogglePause`** → wrap/unwrap `Paused prev`.
- **`RestartRun`** → fresh Model with same seed family; `NewMap` loads grid+waypoints.

### view
Pure projection of Model → a Skia draw-list (no game logic). Renders board, range circle for
selected/placing tower, towers (by kind/tier/angle), enemies (hp bars, effect icons), projectiles,
beams/explosions, HUD, build panel, screen overlays. The view reads `Selection`/`HoverTile` to draw
the placement ghost (green valid / red invalid).

### Subscriptions
- **Tick subscription:** a 60 FPS timer (`requestAnimationFrame`/Skia frame callback) dispatches
  `Tick realDt`. The `update`/loop converts `realDt` into a whole number of **fixed 1/60 s steps**
  via an accumulator (Section 13); `FastForward` doubles steps consumed. Sim is frozen in
  `Building/Paused/Victory/GameOver` (Tick still arrives but no-ops the sim, keeping UI animations).
- **Input subscription:** mouse move/click/wheel and keydown events mapped to `Msg` (edge vs held per
  Section 3).

## 8. Rendering (Skia 2D)
Logical 1280×720; scale to window with letterbox. Coordinate system: origin top-left, +x right,
+y down (matches grid). **Layered draw order** (painter's algorithm), redrawn every frame
(full-clear is cheap at these counts; no dirty-rect needed):

1. **Background/terrain** — tile fills: Buildable `#2E7D32` w/ subtle 1px grid `#1B5E20`; Path
   `#6D5A3F` with `#5A4A33` edges; Blocked `#37474F`; Spawn glow `#C62828`; Goal banner `#1565C0`.
2. **Range overlay** — when placing/selected: filled circle `#FFFFFF22`, stroke `#FFFFFFAA`.
3. **Towers** — base (rounded rect 28×28, kind color: Arrow `#8D6E63`, Cannon `#455A64`, Frost
   `#4FC3F7`, Tesla `#FDD835`) + rotated turret line/triangle to `Angle`; tier pips (small dots).
4. **Enemies** — colored circles sized by kind (Grunt r=9 `#A1887F`, Runner r=7 `#FF8A65`, Brute
   r=13 `#6D4C41`, Wisp r=8 translucent `#B388FF` with float bob, Spectre `#80CBC4`, boss r=24).
   Above each: **HP bar** (4px tall, `#000000` bg, `#76FF03→#FFEA00→#FF1744` lerp by hp%), and small
   **effect glyphs** (snowflake=slow, droplet=poison, bolt=stun, crack=vulnerable).
5. **Projectiles** — arrows: 10px line `#FFE082`; shells: 5px circle `#263238` with shadow; beams:
   Tesla jagged polyline `#FFF59D` 2px for 0.08 s; explosions: expanding ring `#FF7043` fading.
6. **Particles/FX** — muzzle flash (Arrow), smoke puff (Cannon), frost sparkle, electric arcs, gold
   "+N" floats on kill, "-1" red float on leak. Pool of ≤256 particles.
7. **HUD & panel** (Section 9) — drawn last, opaque.
8. **Screen overlays** — pause/victory/game-over scrims `#000000B0` + centered text.

Fonts: HUD numerals **"Inter"/system sans** 18–22px bold; titles 48px; tooltips 14px. Antialiasing
on; enemy/projectile motion looks smooth at 60 FPS without interpolation, but the renderer **may
interpolate** entity positions between fixed steps using a stored `prevPos` for extra smoothness under
fast-forward (optional).

## 9. UI / HUD / Screens
**Screens:** Title (logo, *Play*, map select, difficulty), Map Select (3 thumbnails), Play
(board + HUD), Pause (Resume/Restart/Quit, sim frozen), Victory (stats + score), Game Over (wave
reached + score + Retry).

**Top HUD bar** (y 0–28, full width, `#212121E0`):
- Left: ❤ Lives `20`, ⛁ Gold `250`, ★ Score.
- Center: **Wave x/20** + a **next-wave preview** strip (icons of enemy kinds in the upcoming wave
  with counts). During Combat: live "enemies remaining" + wave progress bar.
- Right: phase indicator (BUILD / WAVE / ⏩×2), interest preview (`+34`), clock.

**Build panel** (right, x 1020–1280, y 28–720, `#263238F0`): the 4 tower buttons with icon, cost,
and hotkey; greyed if unaffordable. When a tower is **selected**, the panel swaps to an **inspector**:
tower name/tier, current stats, **Upgrade** button(s) (branch A/B with cost when at a fork),
**Targeting** toggle (shows current mode), **Sell (+refund)** button, and a DPS estimate.

**In-world widgets:** placement ghost (tower preview + range circle, green/red), selected-tower
range circle + footprint highlight, hover tooltips (enemy: hp/armor/resists; tower: stats).
**Bottom-left** transient toasts ("Wave 7 incoming!", "Not enough gold").

Formatting: gold/score thousands-separated; timers `M:SS`; DPS to 1 decimal.

## 10. Audio
Checklist (v1 optional):
- **SFX:** tower placed (thunk), invalid placement (low buzz), Arrow shot (twang), Cannon fire
  (boom) + splash (crunch), Frost bolt (shimmer), Tesla zap (crackle), enemy death (pop), boss death
  (roar), leak/life lost (alarm thud), wave start (horn), wave cleared (chime), gold/interest
  (coins), upgrade (power-up), sell (cash register), game over (descending sting), victory (fanfare).
- **Music:** calm loop during Build; tense percussive loop during Combat; boss-wave variant;
  victory/defeat stingers. Ducking: combat music dips 30% on boss roar.

## 11. Win / Loss / Scoring
- **Win:** complete **Wave 20** (Wyrm killed and board cleared) with `lives > 0` → Victory.
- **Loss:** `lives ≤ 0` at any time → Game Over.
- **Lives/continues:** 20 lives (difficulty-scaled), no continues in v1.

**Scoring (additive `Score`):**
- Enemy killed: `+bounty * 2` points (boss/Juggernaut as table bounty ×2).
- Wave cleared: `+ (50 * waveNumber)`.
- **No-leak wave bonus:** `+200` if a wave is cleared with zero leaks that wave.
- **Lives remaining at victory:** `+ lives * 150`.
- **Gold banked at victory:** `+ floor(gold * 0.5)`.
- **Early-call bonus** (continuous mode): calling a wave with `t` seconds of the prior wave's timeline
  unspent → `+ floor(t * 3)`.
- **Difficulty multiplier** applied to final score: Easy ×0.8, Normal ×1.0, Hard ×1.4.
Score persists as a per-map high score (Section 13).

## 12. Difficulty & Balancing
Data-driven; all tunables in a config record so balance is code-free.

| Param | Default | Range | Effect |
|---|---|---|---|
| `startingGold` | 250 | 120–500 | opening economy |
| `startingLives` | 20 | 5–50 | error tolerance |
| `interestRate` | 0.08 | 0–0.15 | banking reward |
| `interestCap` | 40 | 0–100 | caps turtling |
| `sellRefund` | 0.70 | 0.3–1.0 | replan flexibility |
| `hpScalePerWave` | 0.06 | 0–0.15 | wave HP ramp |
| `countBasePerWave` | 1.4 | 0.5–3 | enemy count ramp |
| `spawnIntervalMin` | 0.35 | 0.2–1.0 | max spawn density |
| `globalSpeedMult` | 1.0 | 0.5–1.5 | enemy speed knob |
| `slowFloor` | 0.25 | 0.1–0.6 | strongest possible slow |
| `dotStackCap` | 3 | 1–5 | poison stacking |
| `chainRange` | 90 | 60–140 | Tesla chain reach |
| `waveClearBonusBase` | 10 | 0–50 | full-clear reward |
| `mazeNoBuildSpawnRadius` | 2 | 0–4 | anti-spawn-camp |

**Difficulty presets** scale `(startingGold, startingLives, hpScalePerWave, globalSpeedMult,
scoreMult)`: Easy `(350, 30, 0.04, 0.9, 0.8)`, Normal `(250, 20, 0.06, 1.0, 1.0)`,
Hard `(180, 12, 0.09, 1.15, 1.4)`.

## 13. Technical Notes
**Performance budget:** target **60 FPS / 16.7 ms/frame**. Worst-case live counts: ~120 enemies
(swarm waves), ~50 towers, ~400 projectiles, ~256 particles. Hot loops are O(towers×enemies) for
targeting and O(projectiles×enemies) for splash; bucket enemies into a **uniform spatial grid**
(cell = 64 px) so range/splash queries inspect only neighboring cells — keeps per-frame work well
under budget. Maze A* runs only on place/sell (rare), bounded by 40×22=880 nodes.

**Fixed timestep + accumulator** (determinism):
```fsharp
// in the Tick handler
acc <- acc + realDt
let steps = (if model.FastForward then 2 else 1)
let mutable m = model
let mutable n = 0
while acc >= dtFixed && n < maxStepsPerFrame do      // maxStepsPerFrame = 5 (avoid spiral of death)
    for _ in 1 .. steps do m <- simStep dtFixed m     // fast-forward = more steps, same dt
    acc <- acc - dtFixed
    n <- n + 1
```
All sim math uses `dtFixed = 1/60`; rendering may interpolate with leftover `acc/dtFixed` alpha.

**Determinism / RNG:** a single seeded PRNG (`RngState`, e.g. xorshift) threaded through Model;
every random draw (crit rolls, stun procs, splash falloff jitter, particle spawn) pulls from it in a
fixed order. Same seed + same inputs ⇒ identical run (enables replay & test reproducibility). Seed is
chosen at run start (default fixed `0xBULWARK` in tests).

**Persistence:** per-map high score + best wave reached stored in `localStorage`/app settings as JSON
`{ map, score, wave, difficulty, date }`. No mid-run save in v1.

**Edge cases:** placement during Combat (allowed — towers can be built mid-wave if gold allows);
selling a tower mid-wave on a maze map triggers re-path of live enemies; an enemy dying to DoT after
its killer tower was sold still awards bounty (bounty tied to enemy, not tower); simultaneous
multi-leak dropping lives below 0 → clamp to 0 and GameOver; projectile whose target dies before
arrival still resolves splash at last-known target pos (single-target projectile despawns harmlessly);
two slows applied same frame → strongest wins, no double-decrement; pause during a beam FX freezes
its timer.

## 14. Acceptance Criteria (test scenarios)
Verifiable Given/When/Then. Coordinates assume *Serpentine* (fixed map) unless noted; seed fixed.

1. **Placement — valid build deducts gold.**
   Given Phase=Building, Gold=250, an empty `Buildable` tile `(5,5)`, and `PlacingTower Arrow`
   (cost 70). When `LeftClick` at the pixel center of `(5,5)`. Then a Tower(Arrow,T1) exists at
   `(5,5)`, Gold=180, and a build SFX fires.

2. **Placement — on path is rejected.**
   Given `PlacingTower Cannon`, Gold=250, and a `Path` tile under the cursor. When `LeftClick`.
   Then no tower is created, Gold is unchanged (250), and an error blip is emitted.

3. **Placement — insufficient gold rejected.**
   Given `PlacingTower Tesla` (cost 160), Gold=100, empty Buildable tile. When `LeftClick`.
   Then no tower created, Gold=100, error blip emitted.

4. **Placement — maze seal is rejected.**
   Given a maze map and a candidate tile that is the **last** open cell of the only Spawn→Goal
   corridor. When `LeftClick` to place. Then A* finds no path, placement is rejected, Gold unchanged,
   and toast "would seal path" shows; the previously computed waypoints are unchanged.

5. **Tower kills an enemy and awards gold.**
   Given one Grunt (HP 40, bounty 4) at pixel `(170,170)` and an Arrow T2 (dmg 12) at `(170,300)`
   in range, Gold=G, Phase=Combat. When the sim runs until the Grunt's HP reaches ≤0 (≈4 hits over
   ~1.4 s at RoF 2.2). Then the Grunt is removed from `Enemies`, Gold = G+4, Score increases by 8,
   and a "+4" gold float spawns.

6. **Armor reduces physical damage.**
   Given a Brute (HP 160, armor 6) and an Arrow T1 (dmg 8, Physical). When one arrow hits.
   Then applied damage = `max(1, 8-6)` = 2, Brute HP = 158.

7. **Frost applies a slow that reduces effective speed.**
   Given a Grunt (baseSpeed 55) with no effects and a Frost T1 (slow factor 0.6, dur 1.5 s) in range.
   When the Frost bolt hits. Then the Grunt gains `Slow(0.6, 1.5)`, its `effectiveSpeed` = 33 px/s,
   and after 1.5 s with no further frost hits the effect expires and speed returns to 55.

8. **Strongest slow wins (no stacking).**
   Given a Grunt already under `Slow(0.6,_)` from Frost T1. When a Glacier (factor 0.35) also hits.
   Then `effectiveSpeed = 55*0.35 = 19.25` px/s (strongest applies), not 55*0.6*0.35.

9. **Resistance / immunity respected.**
   Given a Spectre (Frost resist 1.0) hit by a Frost bolt (dmg 5, slow 0.6). Then applied frost
   damage = 0 and **no** Slow effect is added (immune); the Spectre keeps baseSpeed 65.

10. **Cannon splash hits a cluster.**
    Given three Grunts within 30 px of impact point and a Cannon T1 (dmg 30, splash r=42). When the
    shell lands centered on the cluster. Then the center Grunt takes 30, the two within falloff take
    between 15 and 30 each per linear falloff, and all three lose HP that frame.

11. **Tesla chains to multiple targets with falloff.**
    Given a Tesla T1 (dmg 18, chain ×3, falloff 0.6) and 4 enemies spaced within `chainRange`.
    When it fires at the primary. Then primary takes 18, jump1 ≈ 10.8, jump2 ≈ 6.48, and the 4th
    enemy is untouched (chain count exhausted).

12. **Targeting mode changes the chosen target.**
    Given two enemies in range — A nearer the Goal (higher progress), B nearer the tower (closer).
    When targeting = First, the tower targets A; when cycled to Closest (`T`), it retargets B on its
    next acquisition.

13. **Sell refunds 70% and (maze) re-paths.**
    Given a Cannon T1 (invested 120) on a maze map shaping the route, Gold=G. When `SellSelected`.
    Then the tower is removed, Gold = G + floor(120*0.7)=G+84, waypoints are recomputed, and live
    ground enemies re-target to the nearest node on the new path without teleporting.

14. **Interest is paid on Start Wave (capped, skipped on wave 1).**
    Given Phase=Building, Gold=600, rate 0.08, cap 40, wave index ≥ 1. When `StartWave`. Then
    interest = `min(40, floor(600*0.08)=48)` = 40, Gold becomes 640 before Combat. Given the same on
    **wave 1**, no interest is paid.

15. **Wave completes and transitions.**
    Given Phase=Combat with all SpawnGroups exhausted (`AllSpawned`) and the last enemy just died.
    When the sim step resolves. Then Phase=`WaveCleared 1.5`, a wave-clear bonus `+(10+wave)` gold and
    `+(50*wave)` score are awarded, and after 1.5 s Phase=`Building` with the next wave previewed.

16. **Life lost on leak.**
    Given Lives=20 and a Grunt (leakCost 1) reaching the Goal waypoint. When it snaps to the Goal.
    Then the Grunt is removed with no bounty, Lives=19, and a red "-1" float appears.

17. **Game over on lethal leak.**
    Given Lives=1 and a Brute (leakCost 2) leaking. When it reaches the Goal. Then Lives clamps to 0
    and Phase=`GameOver` immediately; the current wave is abandoned and the Game Over screen shows the
    wave reached and final score.

18. **Victory on final wave clear.**
    Given Phase=Combat on Wave 20, the Wyrm dead, board cleared, Lives>0. When the step resolves.
    Then Phase=`Victory`, score adds `lives*150 + floor(gold*0.5)`, multiplied by the difficulty
    score multiplier, and the Victory screen shows.

19. **Fixed timestep determinism.**
    Given a fixed seed and a recorded input sequence. When the run is replayed twice. Then enemy
    positions, kills, and final Score are bit-identical across runs (no real-time-dependent drift).

20. **Input — fast-forward doubles sim rate, not dt.**
    Given Phase=Combat at 1×. When `F` toggles fast-forward (2×). Then two fixed steps are consumed
    per accumulator tick (enemies advance ~2× wall-clock distance) while each step still uses
    dt=1/60, and effect timers/damage remain numerically identical to running 1× for twice as long.

## 15. Stretch Goals
Ranked, out-of-scope for v1:
1. **Endless/continuous mode** with early-wave-call bonus and infinite scaling waves + leaderboard.
2. **Targeting priority per-tower presets** saved across maps; "lock target" hotkey.
3. **Hero/abilities:** a player-controlled commander or active spells (meteor, freeze-all) on cooldown.
4. **More tower types:** Poison Sprayer, Buff/Aura tower (boosts adjacent towers), Tar pit (zone slow).
5. **Maze-building maps as the default** with destructible blockers and ground/air dual lanes.
6. **Map editor** (author grid + waypoints + waves) exporting the `Wave`/grid JSON.
7. **Enemy abilities:** burrowers (skip a path segment), splitters (spawn 2 on death), shielders
   (grant temporary armor aura).
8. **Meta-progression:** unlock tower branches/maps across runs; daily seeded challenge.
9. **Co-op two-warden** mode sharing one economy.

## Menu & configuration — the shared game shell

Tower Defense uses the **generic FS.GG game shell** (FS-GG/FS.GG.Rendering#991) — the same
menu/start screen and settings every FS.GG game shares — rather than a bespoke per-game
menu. Tower Defense supplies only its **name**, its **key→command map** (the rebindable
actions from §3 Controls), and its play `update`/`view`; the shell provides everything below.

- **Main menu / start screen** — the game's name (**Tower Defense**) as the title label, with
  **Start**, **Config**, and **Exit**. The shell's Start hands off to the game's own Map
  Select / difficulty flow (§9).
- **`Esc` from gameplay** opens the pause menu (Resume · Config · Exit to menu) over the same
  shell; `Esc` again resumes. This is the shell home for the §3 `P` / `Esc` pause action and
  the §9 Pause screen (note `Esc` during an active placement still cancels the placement first,
  per §3).
- **Config / Settings**, all applied live and persisted across restarts:
  - **Screen resolution** and **fullscreen** (windowed / borderless / fullscreen), driven
    through the SkiaViewer window-behavior + `LogicalCanvas` letterbox seam — the same seam
    that scales the logical 1280×720 board (§4.1, §8) to the window.
  - **Key rebinding** — the player remaps Tower Defense's controls (the §3 keyboard actions:
    select tower types 1–4, upgrade `U`, branch `B`/`V`, sell `S`, cycle targeting `T`, start
    wave `Space`, fast-forward `F`, toggle grid `G`, pause) via the `Controls.KeyRebind` UI
    over the `KeyboardInput.Keymap` mechanism; bindings persist via `KeymapCodec` (JSON),
    beside Tower Defense's other saved config (e.g. per-map high scores, §13).
  - (Game-specific rows such as difficulty or volume may be added as extra Config rows, but
    the menu, Esc routing, display settings, and rebind screen come from the shell.)

The shell is pointer- and keyboard-navigable over the interactive Controls host (the
`fs-gg-skiaviewer` "game → pointer host" recipe) — this game is mouse-native for placement, so
the shell's pointer host is a natural fit. It is a shared dependency, so Tower Defense does
**not** re-specify menu-stack/cursor/settings machinery of its own.

## 16. Milestone Roadmap

Delivery is milestone-sequenced (M0..Mn), each a small, demonstrable slice grounded in the
sections above. Earlier milestones stand up the deterministic simulation core; later ones layer
feel, the shared shell, audio, and the acceptance harness.

### M0 — Scaffold, fixed-step loop & phases
Stand up the Elmish/MVU app (§7) on the FS.GG.Rendering host: the layered `Model`/`Msg`
skeleton, the **60 Hz fixed-step accumulator** (dt = 1/60 s) with the fast-forward "2 steps per
frame" multiplier that never changes dt (§4.2, §13), the phase machine
(`Building`/`Combat`/`Paused`/`WaveCleared`/`Victory`/`GameOver`), and an empty 1280×720 canvas
(§4.1, §8). No gameplay yet — just a deterministic, steppable loop.

### M1 — Board, grid, tiles & fixed path
Build the 40×22 tile grid of 32×32 tiles with the `TileKind` set
(Buildable/Path/Blocked/Spawn/Goal) and tile↔pixel-center mapping (§4.1), and load a
fixed-path map (`mazeBuilding=false`) as an authored `Waypoint[]` polyline from Spawn to Goal.
Ships the *Serpentine* map (§6).

### M2 — Wave scheduler & enemy movement
Implement enemy movement along the waypoint polyline (§4.3): per-step `pathIndex` advance with
snap-and-advance, `effectiveSpeed` integration, and leak on reaching the last waypoint. Add the
wave scheduler (§6): `SpawnGroup`/`Wave` timelines emitting enemies at the Spawn tile off
`waveClock`, and the `Combat → WaveCleared (1.5 s) → Building` transition when all groups are
exhausted and the board is clear.

### M3 — Tower placement, validation & economy
Add tower placement (§4.7): the build palette, the placement ghost + range circle, and the
validity rules (in-grid Buildable, unoccupied, affordable, off-panel, spawn no-build margin) on
left-click, with an error blip on invalid. Wire the economy (§4.9): starting gold, per-tower
cost deduction, 70% sell refund, and end-of-Build interest (`floor(gold·0.08)` capped +40,
disabled on wave 1) + wave-clear bonus.

### M4 — Tower targeting, firing & targeting modes
Implement the per-step tower loop (§4.4): cooldown decrement, in-range + `canHitAir`-gated
target acquisition, sticky targeting, and firing at `1/fireRate` cadence with cosmetic turret
aim. Add the targeting modes (§4.8): First / Last / Strongest / Closest with the deterministic
`progress` metric and tie-breaks, cycled live with `T`.

### M5 — Projectiles, hitscan, splash & chain
Add the two firing models (§4.10): moving projectiles (Arrow re-homing 1×/0.1 s, Cannon
ballistic with `splashRadius` center-100%→edge-50% falloff) with the 2.0 s lifetime cap, and
hitscan beams (Tesla chaining to `chainCount` nearest un-hit enemies at `damage·chainFalloff^k`;
Frost beam upgrade) drawn for 0.08 s.

### M6 — Damage, armor, resistances & status effects
Implement damage resolution (§4.5): physical `max(1, damage − armor)` vs elemental
`damage·(1−resist)` with full-immunity handling, damage types (Physical/Frost/Poison/Electric),
and the status-effect list — Slow (strongest wins, refresh), Poison DoT (stacks to 3, bypasses
armor), Stun, and Vulnerable — ticking before movement each step with expiry removal.

### M7 — Lives, leaks, upgrades & win/loss
Wire lives and leaks (§4.6): 20 starting lives, `leakCost` on Goal reach, immediate `GameOver`
at `lives ≤ 0`. Add tower upgrades (`U`, branch `B`/`V` at the tier-2→3 fork, §4.9 economy /
tower table), and the win/loss + scoring model (§11): Victory on clearing Wave 20 with lives > 0,
the additive score (bounty, wave-clear, no-leak, lives/gold-at-victory bonuses) and difficulty
multiplier, persisted as a per-map high score (§13).

### M8 — Maze maps & dynamic A* re-pathing
Add maze maps (`mazeBuilding=true`, §4.1): A* over the grid treating tower footprints as
`Blocked`, placement rejection when it would seal Spawn→Goal (§4.7.5), path recompute on
place/sell, and in-flight ground-enemy re-targeting to the nearest node without teleporting
(§4.3). Ships *The Labyrinth* map (§6).

### M9 — Rendering, HUD & build panel
Complete the layered draw list (§8): terrain tiles, range overlays, towers with turret + tier
pips, enemies with HP bars + effect glyphs, projectiles / beams / explosions, particles + gold
floats, and the HUD — top bar (lives / gold / score / wave preview) and the right build panel /
tower inspector (§9) — plus pause / victory / game-over scrims.

### M10 — Menus, settings & key rebinding (shared game shell)
Adopt the generic game shell (FS-GG/FS.GG.Rendering#991): main menu (title **Tower Defense** +
Start/Config/Exit handing off to Map Select), `Esc` pause routing (Resume · Config · Exit to
menu), Settings with screen resolution + fullscreen through the SkiaViewer + `LogicalCanvas`
letterbox seam, and in-game key rebinding of the §3 keyboard controls, persisted via
`KeymapCodec`. Tower Defense provides its name + key→command map + play `update`/`view`; the
shell provides the rest. No bespoke menu system.

### M11 — Audio
Wire the SFX + music checklist (§10): tower placed / invalid, per-tower fire and splash, enemy
and boss death, leak alarm, wave start / cleared, gold + interest, upgrade / sell, game-over and
victory stings, plus the Build / Combat / boss music layers with the boss-roar duck.

### M12 — Acceptance & determinism
Land the acceptance harness against the §14 scenarios: enemy path-follow + leak, wave scheduling,
placement validity + economy math, targeting modes, projectile splash + Tesla chain, damage /
armor / resist + status effects, lives / leaks / win-loss, and maze A* re-path + seal rejection —
plus the seeded + input-log **determinism** replay (fast-forward preserving dt) yielding
identical final board state, score, and lives (§13).
