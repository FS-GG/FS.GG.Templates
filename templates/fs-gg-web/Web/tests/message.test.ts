import assert from "node:assert/strict";
import test from "node:test";
import { loadMessage } from "../src/api.ts";

test("loadMessage requests the JSON endpoint and returns its payload", async () => {
  let requested = "";
  const value = await loadMessage(async (input) => {
    requested = String(input);
    return new Response(JSON.stringify({ message: "from the server" }), { status: 200 });
  });
  assert.equal(requested, "/api/message");
  assert.equal(value.message, "from the server");
});
