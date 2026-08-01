import { readFileSync } from "node:fs";
const lock = JSON.parse(readFileSync(new URL("../declaration-lock.json", import.meta.url)));
if (lock.closureSha256 === "REVIEW_REQUIRED" || lock.entryPoints.length === 0)
  throw new Error("declaration closure has not been reviewed and locked");
console.log("declaration closure lock is present; compare its hashes before any upstream update");
