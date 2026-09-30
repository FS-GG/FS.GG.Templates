import { createReadStream } from "node:fs";
import { stat } from "node:fs/promises";
import { createServer } from "node:http";
import { extname, resolve, sep } from "node:path";

const root = resolve(process.env.TYPESCRIPT_TODO_DIST_DIR ?? new URL("../dist/", import.meta.url).pathname);
const port = Number(process.env.TYPESCRIPT_TODO_PORT ?? 4215);
const types = new Map([[".html", "text/html; charset=utf-8"], [".js", "text/javascript; charset=utf-8"], [".css", "text/css; charset=utf-8"]]);
const server = createServer(async (request, response) => {
  try {
    const pathname = decodeURIComponent(new URL(request.url ?? "/", "http://localhost").pathname);
    const relative = pathname === "/" ? "index.html" : pathname.slice(1);
    const candidate = resolve(root, relative);
    if (candidate !== root && !candidate.startsWith(`${root}${sep}`)) throw new Error("outside root");
    if (!(await stat(candidate)).isFile()) throw new Error("not a file");
    response.writeHead(200, { "content-type": types.get(extname(candidate)) ?? "application/octet-stream", "cache-control": "no-store" });
    createReadStream(candidate).pipe(response);
  } catch { response.writeHead(404).end("not found"); }
});
server.listen(port, "127.0.0.1", () => console.log(`typescript todo listening on http://127.0.0.1:${port}`));
