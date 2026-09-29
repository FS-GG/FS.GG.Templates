import assert from "node:assert/strict";
import test from "node:test";

import { initialState, reduce } from "./game.mjs";

function play(indices) {
  return indices.reduce((state, index) => reduce(state, { type: "move", index }), initialState());
}

function oracleWinningLines(board, player) {
  const lines = [];

  for (let row = 0; row < 3; row += 1) {
    const indices = [row * 3, row * 3 + 1, row * 3 + 2];
    if (indices.every((index) => board[index] === player)) lines.push(`row-${row}`);
  }
  for (let column = 0; column < 3; column += 1) {
    const indices = [column, column + 3, column + 6];
    if (indices.every((index) => board[index] === player)) lines.push(`column-${column}`);
  }

  if ([0, 4, 8].every((index) => board[index] === player)) lines.push("diagonal-down");
  if ([2, 4, 6].every((index) => board[index] === player)) lines.push("diagonal-up");
  return lines;
}

function oracleWinner(board) {
  for (const player of ["X", "O"]) {
    if (oracleWinningLines(board, player).length > 0) return player;
  }
  return null;
}

test("plays wins for each player and evaluates a ninth-move win before a draw", () => {
  assert.deepEqual(play([0, 3, 1, 4, 2]), {
    board: ["X", "X", "X", "O", "O", null, null, null, null],
    phase: "won",
    turn: "X",
    winner: "X",
  });

  assert.equal(play([0, 3, 1, 4, 8, 5]).winner, "O");
  assert.equal(play([0, 1, 2, 4, 3, 5, 7, 6, 8]).phase, "draw");

  const ninthMoveWin = play([0, 1, 2, 3, 4, 5, 7, 6, 8]);
  assert.equal(ninthMoveWin.phase, "won");
  assert.equal(ninthMoveWin.winner, "X");
});

test("refuses occupied, invalid, unknown, and post-terminal moves", () => {
  const oneMove = play([0]);
  for (const action of [
    { type: "move", index: 0 },
    { type: "move", index: -1 },
    { type: "move", index: 9 },
    { type: "move", index: 1.5 },
    { type: "move", index: "1" },
    { type: "something-else", index: 1 },
  ]) {
    assert.strictEqual(reduce(oneMove, action), oneMove);
  }

  for (const terminal of [play([0, 3, 1, 4, 2]), play([0, 1, 2, 4, 3, 5, 7, 6, 8])]) {
    assert.strictEqual(reduce(terminal, { type: "move", index: 6 }), terminal);
  }
});

test("restart returns a fresh empty X-first game from every phase", () => {
  const phases = [
    play([0, 1]),
    play([0, 3, 1, 4, 2]),
    play([0, 1, 2, 4, 3, 5, 7, 6, 8]),
  ];

  for (const state of phases) {
    const restarted = reduce(state, { type: "restart" });
    assert.deepEqual(restarted, initialState());
    assert.notStrictEqual(restarted.board, state.board);
  }
});

test("all reachable states and transitions satisfy the independent game oracle", () => {
  const pending = [initialState()];
  const visited = new Set();
  const winningLinesSeen = { X: new Set(), O: new Set() };

  while (pending.length > 0) {
    const state = pending.pop();
    const key = `${state.phase}|${state.turn}|${state.winner}|${state.board.map((cell) => cell ?? "-").join("")}`;
    if (visited.has(key)) continue;
    visited.add(key);

    const xCount = state.board.filter((cell) => cell === "X").length;
    const oCount = state.board.filter((cell) => cell === "O").length;
    const winner = oracleWinner(state.board);
    assert.ok(xCount === oCount || xCount === oCount + 1, key);

    if (state.phase === "playing") {
      assert.equal(winner, null, key);
      assert.ok(state.board.includes(null), key);
      assert.equal(state.turn, xCount === oCount ? "X" : "O", key);
      assert.equal(state.winner, null, key);
    } else if (state.phase === "won") {
      assert.equal(state.winner, winner, key);
      assert.equal(state.turn, winner, key);
      for (const line of oracleWinningLines(state.board, winner)) winningLinesSeen[winner].add(line);
    } else {
      assert.equal(state.phase, "draw", key);
      assert.equal(winner, null, key);
      assert.ok(state.board.every((cell) => cell !== null), key);
      assert.equal(state.winner, null, key);
    }

    for (let index = 0; index < 9; index += 1) {
      const boardBefore = state.board.slice();
      const next = reduce(state, { type: "move", index });
      assert.deepEqual(state.board, boardBefore, `input mutated: ${key}`);

      const legal = state.phase === "playing" && state.board[index] === null;
      if (!legal) {
        assert.strictEqual(next, state, `invalid transition advanced: ${key}, ${index}`);
        continue;
      }

      const differences = next.board.filter((cell, cellIndex) => cell !== state.board[cellIndex]);
      assert.equal(differences.length, 1, `move changed more than one cell: ${key}, ${index}`);
      assert.equal(next.board[index], state.turn, key);
      assert.notStrictEqual(next.board, state.board, key);
      pending.push(next);
    }
  }

  const allLines = new Set([
    "row-0", "row-1", "row-2",
    "column-0", "column-1", "column-2",
    "diagonal-down", "diagonal-up",
  ]);
  assert.deepEqual(winningLinesSeen.X, allLines);
  assert.deepEqual(winningLinesSeen.O, allLines);
  assert.ok(visited.size > 5_000, `expected exhaustive traversal, saw ${visited.size} states`);
});
