import { BOARD, createGame, reduce } from "./domain.js";

const svg = document.querySelector("#board");
const scoreValue = document.querySelector("#score-value");
const stateValue = document.querySelector("#state-value");
const announcement = document.querySelector("#announcement");
const primaryButton = document.querySelector("#primary-action");
const restartButton = document.querySelector("#restart");

const keyDirections = new Map([
  ["ArrowUp", "up"], ["w", "up"], ["W", "up"],
  ["ArrowDown", "down"], ["s", "down"], ["S", "down"],
  ["ArrowLeft", "left"], ["a", "left"], ["A", "left"],
  ["ArrowRight", "right"], ["d", "right"], ["D", "right"],
]);

let state = createGame();
let previousTime = null;
let accumulated = 0;
let announcedScore = state.score;
let announcedStatus = state.status;

function cell(className, point, label) {
  const node = document.createElementNS("http://www.w3.org/2000/svg", "rect");
  node.setAttribute("class", className);
  node.setAttribute("x", point.x);
  node.setAttribute("y", point.y);
  node.setAttribute("width", "1");
  node.setAttribute("height", "1");
  node.dataset.x = String(point.x);
  node.dataset.y = String(point.y);
  if (label) node.setAttribute("aria-label", label);
  return node;
}

function render() {
  svg.replaceChildren();
  state.body.forEach((point, index) => svg.append(cell(index === 0 ? "snake-head" : "snake-body", point)));
  if (state.food) svg.append(cell("food", state.food, "Food"));

  scoreValue.textContent = String(state.score);
  stateValue.textContent = state.status[0].toUpperCase() + state.status.slice(1);
  svg.dataset.status = state.status;
  svg.dataset.length = String(state.body.length);
  svg.dataset.turns = String(state.turns.length);

  const labels = { ready: "Start", running: "Pause", paused: "Resume", lost: "Start new game", won: "Start new game" };
  primaryButton.textContent = labels[state.status];
  primaryButton.setAttribute("aria-label", labels[state.status]);

  if (state.score !== announcedScore || state.status !== announcedStatus) {
    announcement.textContent = `${stateValue.textContent}. Score ${state.score}.`;
    announcedScore = state.score;
    announcedStatus = state.status;
  }
}

function dispatch(message) {
  state = reduce(state, message);
  render();
}

function resetClock() {
  previousTime = null;
  accumulated = 0;
}

function animationFrame(time) {
  if (state.status === "running") {
    if (previousTime === null) previousTime = time;
    accumulated += Math.max(0, time - previousTime);
    previousTime = time;
    let steps = 0;
    while (accumulated >= state.tickMs && steps < 4 && state.status === "running") {
      accumulated -= state.tickMs;
      dispatch({ type: "tick" });
      steps += 1;
    }
    if (steps === 4 && accumulated >= state.tickMs) accumulated = 0;
  } else {
    previousTime = null;
  }
  requestAnimationFrame(animationFrame);
}

function pauseAutomatically() {
  if (state.status === "running") {
    dispatch({ type: "pause" });
    resetClock();
  }
}

primaryButton.addEventListener("click", () => {
  if (state.status === "ready") dispatch({ type: "start" });
  else if (state.status === "running") dispatch({ type: "pause" });
  else if (state.status === "paused") dispatch({ type: "resume" });
  else {
    dispatch({ type: "restart" });
    dispatch({ type: "start" });
  }
  resetClock();
  svg.focus();
});

restartButton.addEventListener("click", () => {
  dispatch({ type: "restart" });
  resetClock();
  svg.focus();
});

svg.addEventListener("keydown", (event) => {
  if (event.repeat) return;
  const direction = keyDirections.get(event.key);
  if (direction && state.status === "running") {
    event.preventDefault();
    dispatch({ type: "direction", direction });
    return;
  }
  if ((event.key === " " || event.key === "p" || event.key === "P") && (state.status === "running" || state.status === "paused")) {
    event.preventDefault();
    dispatch({ type: state.status === "running" ? "pause" : "resume" });
    resetClock();
  }
});

document.addEventListener("visibilitychange", () => {
  if (document.hidden) pauseAutomatically();
});
window.addEventListener("blur", pauseAutomatically);

svg.setAttribute("viewBox", `0 0 ${BOARD.width} ${BOARD.height}`);
render();
requestAnimationFrame(animationFrame);
