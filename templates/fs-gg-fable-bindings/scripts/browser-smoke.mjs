// Serves this workspace over HTTP, opens a page in headless Chromium and waits (in real time)
// until the page's <output> element reports a result. `chromium --dump-dom` cannot do this:
// its virtual-time budget runs out while an image decode or fetch is still pending, so a page
// that loads assets is reported before it finishes.
//
//   node scripts/browser-smoke.mjs --page /runtime/browser/ --expect "Pixi browser smoke passed"
//
// The browser binary is `$CHROMIUM` or `chromium`. `$BROWSER_SMOKE_ARGS` (space separated) adds flags, for
// example `--headless=new --use-angle=vulkan --enable-features=Vulkan --ignore-gpu-blocklist` to run WebGL on a GPU. Exit 0 only when the output equals --expect.
import { spawn } from "node:child_process";
import { mkdtemp, readFile, rm } from "node:fs/promises";
import { createServer } from "node:http";
import { tmpdir } from "node:os";
import { extname, join, normalize, resolve } from "node:path";

const args = process.argv.slice(2);
const valueAfter = (flag, fallback) => { const index = args.indexOf(flag); return index < 0 ? fallback : args[index + 1]; };
const root = resolve(import.meta.dirname, "..");
const page = valueAfter("--page", "/runtime/browser/");
const expected = valueAfter("--expect");
const timeoutMs = Number(valueAfter("--timeout", "60000"));
if (!expected) throw new Error("--expect <output text> is required");

const types = { ".html": "text/html", ".js": "text/javascript", ".mjs": "text/javascript", ".json": "application/json", ".png": "image/png", ".wasm": "application/wasm", ".map": "application/json" };
const server = createServer(async (request, response) => {
  try {
    let path = normalize(decodeURIComponent(new URL(request.url, "http://localhost").pathname));
    if (path.endsWith("/")) path += "index.html";
    const file = join(root, path);
    if (!file.startsWith(`${root}/`)) throw new Error("outside the workspace");
    const body = await readFile(file);
    response.writeHead(200, { "content-type": types[extname(file)] ?? "application/octet-stream" });
    response.end(body);
  } catch {
    response.writeHead(404).end();
  }
});
await new Promise(done => server.listen(0, "127.0.0.1", done));
const url = `http://127.0.0.1:${server.address().port}${page}`;

const profile = await mkdtemp(join(tmpdir(), "browser-smoke-"));
const browser = spawn(process.env.CHROMIUM ?? "chromium", [...(process.env.BROWSER_SMOKE_ARGS ? [] : ["--headless", "--disable-gpu"]), "--no-sandbox", ...(process.env.BROWSER_SMOKE_ARGS?.split(" ").filter(Boolean) ?? []), "--remote-debugging-port=0", `--user-data-dir=${profile}`, "about:blank"], { stdio: "ignore" });
let result = "no result";
try {
  const deadline = Date.now() + timeoutMs;
  const sleep = ms => new Promise(done => setTimeout(done, ms));
  let port;
  while (!port) {
    if (Date.now() > deadline) throw new Error("the browser never opened its debugging port");
    try { port = (await readFile(join(profile, "DevToolsActivePort"), "utf8")).split("\n")[0]; } catch { await sleep(100); }
  }
  const targets = await (await fetch(`http://127.0.0.1:${port}/json/list`)).json();
  const socket = new WebSocket(targets.find(target => target.type === "page").webSocketDebuggerUrl);
  await new Promise((done, fail) => { socket.onopen = done; socket.onerror = fail; });
  const pending = new Map();
  let next = 0;
  socket.onmessage = event => {
    const message = JSON.parse(event.data);
    pending.get(message.id)?.(message);
    if (message.method === "Runtime.consoleAPICalled") console.log(`[page ${message.params.type}] ${message.params.args.map(arg => arg.value ?? arg.description ?? "").join(" ")}`);
    if (message.method === "Runtime.exceptionThrown") console.log(`[page exception] ${message.params.exceptionDetails.exception?.description ?? message.params.exceptionDetails.text}`);
  };
  const send = (method, params = {}) => new Promise(done => { const id = ++next; pending.set(id, done); socket.send(JSON.stringify({ id, method, params })); });
  await send("Runtime.enable");
  await send("Page.enable");
  await send("Page.navigate", { url });
  while (Date.now() < deadline) {
    const { result: evaluated } = await send("Runtime.evaluate", { expression: "document.querySelector('output')?.textContent ?? 'no output element'", returnByValue: true });
    result = String(evaluated?.result?.value ?? "no result");
    if (result !== "running" && result !== "no output element") break;
    await sleep(100);
  }
  socket.close();
} finally {
  const exited = new Promise(done => browser.once("exit", done));
  browser.kill("SIGKILL");
  await exited;
  server.close();
  await rm(profile, { recursive: true, force: true, maxRetries: 10, retryDelay: 100 });
}
console.log(result);
if (result !== expected) process.exit(1);
