import { createRequire } from "node:module";

const baseUrl = (process.env.GAME_EDGE_URL ?? "http://127.0.0.1:8080").replace(/\/$/, "");
const require = createRequire(new URL("../Client/package.json", import.meta.url));
const signalR = require("@microsoft/signalr");

const response = await fetch(`${baseUrl}/api/bootstrap`, {
  method: "POST",
  headers: { "content-type": "application/json" },
  body: JSON.stringify({ version: 1, playerName: "edge-probe" })
});
if (!response.ok) throw new Error(`bootstrap failed: ${response.status} ${await response.text()}`);
const bootstrap = await response.json();

const connection = new signalR.HubConnectionBuilder()
  .withUrl(`${baseUrl}/hub/game`)
  .configureLogging(signalR.LogLevel.Warning)
  .build();

const firstMessage = new Promise((resolve, reject) => {
  const timeout = setTimeout(() => reject(new Error("timed out waiting for the first authority snapshot")), 10000);
  connection.on("Message", json => {
    clearTimeout(timeout);
    resolve(JSON.parse(json));
  });
});

try {
  await connection.start();
  await connection.invoke("SendMessage", JSON.stringify({
    kind: "sessionHello",
    payload: { version: 1, sessionCapability: bootstrap.sessionCapability }
  }));
  const message = await firstMessage;
  if (message.kind !== "resyncSnapshot" || message.payload?.version !== 1) {
    throw new Error(`unexpected first authority message: ${JSON.stringify(message)}`);
  }
  process.stdout.write(`edge websocket passed: player=${bootstrap.playerId} room=${bootstrap.roomId}\n`);
} finally {
  await connection.stop().catch(() => {});
}
