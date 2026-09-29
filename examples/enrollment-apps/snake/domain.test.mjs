import assert from "node:assert/strict";
import test from "node:test";
import {
  BOARD,
  DIRECTIONS,
  INITIAL_SEED,
  MIN_TICK_MS,
  createGame,
  placeFood,
  reduce,
  tickInterval,
} from "./domain.js";

const running = () => reduce(createGame(), { type: "start" });
const tick = (state, count = 1) => Array.from({ length: count }).reduce((next) => reduce(next, { type: "tick" }), state);

test("starts from the documented deterministic contract and moves one cell", () => {
  const initial = createGame();
  assert.equal(initial.status, "ready");
  assert.deepEqual(initial.body, [{ x: 16, y: 9 }, { x: 15, y: 9 }, { x: 14, y: 9 }]);
  assert.deepEqual(initial.food, { x: 20, y: 9 });
  assert.deepEqual(tick(initial).body, initial.body, "ready games do not move");
  assert.deepEqual(tick(running()).body[0], { x: 17, y: 9 });
});

test("eating grows, scores, speeds up, and never places food on the snake", () => {
  const eaten = tick(running(), 4);
  assert.equal(eaten.score, 10);
  assert.equal(eaten.body.length, 4);
  assert.equal(eaten.tickMs, 174);
  assert.ok(!eaten.body.some((point) => point.x === eaten.food.x && point.y === eaten.food.y));
  assert.equal(tickInterval(10_000), MIN_TICK_MS);
});

test("turn queue holds two legal turns and rejects direct or queued reversals", () => {
  let state = running();
  assert.equal(reduce(state, { type: "direction", direction: "left" }), state);
  state = reduce(state, { type: "direction", direction: "down" });
  const reversed = reduce(state, { type: "direction", direction: "up" });
  assert.equal(reversed, state);
  state = reduce(state, { type: "direction", direction: "left" });
  assert.equal(state.turns.length, 2);
  assert.equal(reduce(state, { type: "direction", direction: "down" }), state);
  state = tick(state);
  assert.deepEqual(state.body[0], { x: 16, y: 10 });
  state = tick(state);
  assert.deepEqual(state.body[0], { x: 15, y: 10 });

  const corrupted = { ...running(), turns: [{ ...DIRECTIONS.left }] };
  assert.deepEqual(tick(corrupted).body[0], { x: 17, y: 9 }, "commit guard rejects an invalid queued reversal");
});

test("pause freezes movement and resume continues without domain catch-up", () => {
  const before = tick(running(), 2);
  const paused = reduce(before, { type: "pause" });
  assert.equal(paused.status, "paused");
  assert.deepEqual(tick(paused, 20), paused);
  const resumed = reduce(paused, { type: "resume" });
  assert.deepEqual(tick(resumed).body[0], { x: 19, y: 9 });
});

test("wall and body collisions retain the last valid body and terminal states refuse input", () => {
  const wallState = {
    ...running(),
    body: [{ x: 31, y: 3 }, { x: 30, y: 3 }, { x: 29, y: 3 }],
    food: { x: 0, y: 0 },
  };
  const wallLost = tick(wallState);
  assert.equal(wallLost.status, "lost");
  assert.deepEqual(wallLost.body, wallState.body);
  assert.equal(reduce(wallLost, { type: "tick" }), wallLost);
  assert.equal(reduce(wallLost, { type: "direction", direction: "up" }), wallLost);
  assert.equal(reduce(wallLost, { type: "pause" }), wallLost);

  const bodyState = {
    ...running(),
    body: [{ x: 2, y: 1 }, { x: 2, y: 2 }, { x: 1, y: 2 }, { x: 1, y: 1 }, { x: 1, y: 0 }],
    direction: { ...DIRECTIONS.left },
    food: { x: 8, y: 8 },
  };
  const bodyLost = tick(bodyState);
  assert.equal(bodyLost.status, "lost");
  assert.deepEqual(bodyLost.body, bodyState.body);
});

test("moving into a vacating tail cell is legal", () => {
  const state = {
    ...running(),
    body: [{ x: 1, y: 1 }, { x: 1, y: 2 }, { x: 2, y: 2 }, { x: 2, y: 1 }],
    direction: { ...DIRECTIONS.right },
    food: { x: 8, y: 8 },
  };
  const moved = tick(state);
  assert.equal(moved.status, "running");
  assert.deepEqual(moved.body[0], { x: 2, y: 1 });
});

test("eating the final free cell wins with no food", () => {
  const state = {
    ...running(),
    board: { width: 3, height: 2 },
    body: [{ x: 1, y: 0 }, { x: 0, y: 0 }, { x: 0, y: 1 }, { x: 1, y: 1 }, { x: 2, y: 1 }],
    direction: { ...DIRECTIONS.right },
    food: { x: 2, y: 0 },
    score: 20,
  };
  const won = tick(state);
  assert.equal(won.status, "won");
  assert.equal(won.food, null);
  assert.equal(won.body.length, 6);
  assert.equal(won.score, 30);
  assert.equal(reduce(won, { type: "tick" }), won);
});

test("restart restores the exact seed, timing, score, queue, and ready state", () => {
  let state = tick(running(), 4);
  state = reduce(state, { type: "direction", direction: "down" });
  assert.deepEqual(reduce(state, { type: "restart" }), createGame(INITIAL_SEED, BOARD));
});

test("food selection is deterministic and reports a full board", () => {
  const body = [{ x: 0, y: 0 }, { x: 1, y: 0 }, { x: 0, y: 1 }];
  assert.deepEqual(placeFood(body, 42, { width: 2, height: 2 }), placeFood(body, 42, { width: 2, height: 2 }));
  assert.deepEqual(placeFood([...body, { x: 1, y: 1 }], 42, { width: 2, height: 2 }).food, null);
});

test("identical seed and message traces produce identical states and preserve invariants", () => {
  const messages = [
    { type: "start" },
    ...Array.from({ length: 4 }, () => ({ type: "tick" })),
    { type: "direction", direction: "down" },
    { type: "tick" },
    { type: "direction", direction: "left" },
    ...Array.from({ length: 9 }, () => ({ type: "tick" })),
    { type: "pause" }, { type: "tick" }, { type: "resume" },
  ];
  const replay = () => messages.reduce(reduce, createGame());
  const first = replay();
  assert.deepEqual(first, replay());

  let state = createGame();
  for (const message of messages) {
    state = reduce(state, message);
    const cells = new Set(state.body.map(({ x, y }) => `${x},${y}`));
    assert.equal(cells.size, state.body.length);
    assert.ok(state.body.every(({ x, y }) => x >= 0 && y >= 0 && x < state.board.width && y < state.board.height));
    assert.equal(state.body.length, 3 + state.score / 10);
    assert.ok(state.turns.length <= 2);
    if (state.food) assert.ok(!cells.has(`${state.food.x},${state.food.y}`));
  }
});
