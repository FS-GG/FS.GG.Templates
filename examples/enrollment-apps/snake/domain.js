export const BOARD = Object.freeze({ width: 32, height: 18 });
export const INITIAL_SEED = 633;
export const INITIAL_TICK_MS = 180;
export const MIN_TICK_MS = 60;
export const TURN_QUEUE_LIMIT = 2;

export const DIRECTIONS = Object.freeze({
  up: Object.freeze({ x: 0, y: -1 }),
  down: Object.freeze({ x: 0, y: 1 }),
  left: Object.freeze({ x: -1, y: 0 }),
  right: Object.freeze({ x: 1, y: 0 }),
});

const INITIAL_BODY = Object.freeze([
  Object.freeze({ x: 16, y: 9 }),
  Object.freeze({ x: 15, y: 9 }),
  Object.freeze({ x: 14, y: 9 }),
]);

const copyPoint = ({ x, y }) => ({ x, y });
const samePoint = (a, b) => a.x === b.x && a.y === b.y;
const isOpposite = (a, b) => a.x + b.x === 0 && a.y + b.y === 0;

export function nextRandom(seed) {
  let value = seed >>> 0;
  value ^= value << 13;
  value ^= value >>> 17;
  value ^= value << 5;
  return value >>> 0;
}

export function placeFood(body, seed, board = BOARD) {
  const occupied = new Set(body.map(({ x, y }) => `${x},${y}`));
  const free = [];
  for (let y = 0; y < board.height; y += 1) {
    for (let x = 0; x < board.width; x += 1) {
      if (!occupied.has(`${x},${y}`)) free.push({ x, y });
    }
  }

  const nextSeed = nextRandom(seed);
  return {
    food: free.length === 0 ? null : free[nextSeed % free.length],
    seed: nextSeed,
  };
}

export function tickInterval(score) {
  return Math.max(MIN_TICK_MS, INITIAL_TICK_MS - (score / 10) * 6);
}

export function createGame(seed = INITIAL_SEED, board = BOARD) {
  const body = INITIAL_BODY.map(copyPoint);
  const placed = placeFood(body, seed, board);
  return {
    board: { ...board },
    status: "ready",
    body,
    direction: { ...DIRECTIONS.right },
    turns: [],
    food: placed.food,
    seed: placed.seed,
    score: 0,
    tickMs: INITIAL_TICK_MS,
  };
}

function queueDirection(state, directionName) {
  const direction = DIRECTIONS[directionName];
  if (!direction || state.status !== "running" || state.turns.length >= TURN_QUEUE_LIMIT) return state;

  const previous = state.turns.at(-1) ?? state.direction;
  if (samePoint(previous, direction) || isOpposite(previous, direction)) return state;
  return { ...state, turns: [...state.turns, { ...direction }] };
}

function move(state) {
  if (state.status !== "running") return state;

  const queued = state.turns[0];
  const direction = queued && !isOpposite(state.direction, queued) ? queued : state.direction;
  const turns = state.turns.slice(queued ? 1 : 0);
  const head = {
    x: state.body[0].x + direction.x,
    y: state.body[0].y + direction.y,
  };

  const outside = head.x < 0 || head.y < 0 || head.x >= state.board.width || head.y >= state.board.height;
  const growing = state.food !== null && samePoint(head, state.food);
  const collisionBody = growing ? state.body : state.body.slice(0, -1);
  const selfCollision = collisionBody.some((point) => samePoint(point, head));
  if (outside || selfCollision) {
    return { ...state, status: "lost", direction: { ...direction }, turns: [] };
  }

  const body = [head, ...state.body];
  if (!growing) body.pop();
  if (!growing) return { ...state, body, direction: { ...direction }, turns };

  const score = state.score + 10;
  const placed = placeFood(body, state.seed, state.board);
  return {
    ...state,
    status: placed.food === null ? "won" : state.status,
    body,
    direction: { ...direction },
    turns: placed.food === null ? [] : turns,
    food: placed.food,
    seed: placed.seed,
    score,
    tickMs: tickInterval(score),
  };
}

export function reduce(state, message) {
  switch (message.type) {
    case "start":
      return state.status === "ready" ? { ...state, status: "running" } : state;
    case "direction":
      return queueDirection(state, message.direction);
    case "tick":
      return move(state);
    case "pause":
      return state.status === "running" ? { ...state, status: "paused" } : state;
    case "resume":
      return state.status === "paused" ? { ...state, status: "running" } : state;
    case "restart":
      return createGame(INITIAL_SEED, state.board);
    default:
      return state;
  }
}
