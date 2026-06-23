import assert from "node:assert/strict";
import { bootstrap } from "../src/api";

const originalFetch = globalThis.fetch;

try {
  globalThis.fetch = (async () =>
    new Response("<!DOCTYPE html><html><body>Restarting</body></html>", {
      status: 502,
      statusText: "Bad Gateway",
      headers: { "content-type": "text/html; charset=utf-8" }
    })) as typeof fetch;

  await assert.rejects(
    () => bootstrap(),
    /Workbench host returned HTML for \/api\/bootstrap \(502 Bad Gateway\)/
  );
} finally {
  globalThis.fetch = originalFetch;
}

console.log("api tests passed");
