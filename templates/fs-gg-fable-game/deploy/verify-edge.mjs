import { createRequire } from "node:module";

const baseUrl = (process.env.GAME_EDGE_URL ?? "http://127.0.0.1:8080").replace(/\/$/, "");
const require = createRequire(new URL("../Client/package.json", import.meta.url));
const signalR = require("@microsoft/signalr");

async function bootstrap(playerName) {
  const response = await fetch(`${baseUrl}/api/bootstrap`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ version: 1, playerName })
  });
  if (!response.ok) throw new Error(`bootstrap failed: ${response.status} ${await response.text()}`);
  return response.json();
}

function connectionProbe() {
  const waiting = [];
  const messages = [];
  const connection = new signalR.HubConnectionBuilder()
    .withUrl(`${baseUrl}/hub/game`, {
      transport: signalR.HttpTransportType.WebSockets,
      skipNegotiation: true
    })
    .configureLogging(signalR.LogLevel.Warning)
    .build();
  connection.on("Message", json => {
    const message = JSON.parse(json);
    const match = waiting.findIndex(waiter => waiter.predicate(message));
    if (match >= 0) {
      const [waiter] = waiting.splice(match, 1);
      clearTimeout(waiter.timeout);
      waiter.resolve(message);
    } else {
      messages.push(message);
    }
  });
  const waitFor = (predicate, label) => {
    const queued = messages.findIndex(predicate);
    if (queued >= 0) return Promise.resolve(messages.splice(queued, 1)[0]);
    return new Promise((resolve, reject) => {
      const waiter = { predicate, resolve, timeout: undefined };
      waiter.timeout = setTimeout(() => {
        const index = waiting.indexOf(waiter);
        if (index >= 0) waiting.splice(index, 1);
        reject(new Error(`timed out waiting for ${label}`));
      }, 10000);
      waiting.push(waiter);
    });
  };
  return { connection, waitFor };
}

async function hello(probe, sessionCapability) {
  await probe.connection.start();
  const snapshot = probe.waitFor(
    message => message.kind === "resyncSnapshot" && message.payload?.version === 3,
    "the V3 authority snapshot"
  );
  await probe.connection.invoke("SendMessage", JSON.stringify({
    kind: "sessionHello",
    payload: { version: 3, sessionCapability }
  }));
  return snapshot;
}

const first = await bootstrap("edge-probe-one");
const second = await bootstrap("edge-probe-two");
const firstProbe = connectionProbe();
let secondProbe = connectionProbe();

try {
  const firstSnapshot = await hello(firstProbe, first.sessionCapability);
  if (!firstSnapshot.payload.players.some(player => player.playerId === first.playerId)) {
    throw new Error("first player is absent from its authority snapshot");
  }

  const secondSnapshot = await hello(secondProbe, second.sessionCapability);
  const playerIds = new Set(secondSnapshot.payload.players.map(player => player.playerId));
  if (!playerIds.has(first.playerId) || !playerIds.has(second.playerId)) {
    throw new Error("two-client authority snapshot does not contain both players");
  }

  const disconnected = firstProbe.waitFor(
    message => message.kind === "presence" && message.payload?.playerId === second.playerId && message.payload?.joined === false,
    "the second player's disconnect presence"
  );
  await secondProbe.connection.stop();
  await disconnected;
  secondProbe = connectionProbe();
  const reconnectSnapshot = await hello(secondProbe, second.sessionCapability);
  if (!reconnectSnapshot.payload.players.some(player => player.playerId === second.playerId)) {
    throw new Error("reconnected player is absent from the resync snapshot");
  }
  process.stdout.write(`edge websocket passed: players=2 room=${first.roomId} reconnect=passed protocol=v3\n`);
} finally {
  await Promise.all([
    firstProbe.connection.stop().catch(() => {}),
    secondProbe.connection.stop().catch(() => {})
  ]);
}
