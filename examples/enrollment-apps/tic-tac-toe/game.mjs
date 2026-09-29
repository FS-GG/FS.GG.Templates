const WINNING_LINES = [
  [0, 1, 2],
  [3, 4, 5],
  [6, 7, 8],
  [0, 3, 6],
  [1, 4, 7],
  [2, 5, 8],
  [0, 4, 8],
  [2, 4, 6],
];

export function initialState() {
  return {
    board: Array(9).fill(null),
    phase: "playing",
    turn: "X",
    winner: null,
  };
}

function hasWon(board, player) {
  return WINNING_LINES.some((line) => line.every((index) => board[index] === player));
}

export function reduce(state, action) {
  if (action?.type === "restart") {
    return initialState();
  }

  if (action?.type !== "move" || state.phase !== "playing") {
    return state;
  }

  const { index } = action;
  if (!Number.isInteger(index) || index < 0 || index >= state.board.length || state.board[index] !== null) {
    return state;
  }

  const board = state.board.slice();
  board[index] = state.turn;

  if (hasWon(board, state.turn)) {
    return { board, phase: "won", turn: state.turn, winner: state.turn };
  }

  if (board.every((cell) => cell !== null)) {
    return { board, phase: "draw", turn: state.turn, winner: null };
  }

  return {
    board,
    phase: "playing",
    turn: state.turn === "X" ? "O" : "X",
    winner: null,
  };
}
