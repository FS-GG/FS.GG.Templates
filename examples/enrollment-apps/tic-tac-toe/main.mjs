import { initialState, reduce } from "./game.mjs";

const cells = Array.from(document.querySelectorAll("[data-cell]"));
const status = document.querySelector("#status");
const restart = document.querySelector("#restart");

let state = initialState();

function statusText() {
  if (state.phase === "won") {
    return `${state.winner} wins!`;
  }
  if (state.phase === "draw") {
    return "Draw game.";
  }
  return `${state.turn} to play.`;
}

function render() {
  status.textContent = statusText();

  cells.forEach((cell, index) => {
    const mark = state.board[index];
    const row = Math.floor(index / 3) + 1;
    const column = (index % 3) + 1;
    const unavailable = mark !== null || state.phase !== "playing";

    cell.textContent = mark ?? "";
    cell.dataset.mark = mark ?? "empty";
    cell.setAttribute("aria-label", `Row ${row}, column ${column}, ${mark ?? "empty"}`);
    cell.setAttribute("aria-disabled", String(unavailable));
  });
}

function play(index) {
  state = reduce(state, { type: "move", index });
  render();
}

cells.forEach((cell) => {
  cell.addEventListener("click", () => play(Number(cell.dataset.cell)));
});

restart.addEventListener("click", () => {
  state = reduce(state, { type: "restart" });
  render();
  cells[0].focus();
});

render();
