import assert from "node:assert/strict";
import test from "node:test";
import { faceIdOf, selectFace, TavusApiError, TavusClient } from "../src/tavus-client.mjs";

test("selectFace prefers Phoenix 4.5", () => {
  const selected = selectFace({
    data: [
      { face_id: "old", face_name: "Old", model: "phoenix-3", status: "ready" },
      { face_id: "new", face_name: "New", model: "phoenix-4.5", status: "ready" }
    ]
  });
  assert.equal(faceIdOf(selected), "new");
});

test("TavusClient does not put the key in the request body", async () => {
  const calls = [];
  const client = new TavusClient("secret-value", {
    baseUrl: "https://example.test/v2",
    fetchImpl: async (url, options) => {
      calls.push({ url, options });
      return new Response(JSON.stringify({ ok: true }), { status: 200 });
    }
  });
  await client.post("/pals", { pal_name: "Demo" });
  assert.equal(calls[0].options.headers["x-api-key"], "secret-value");
  assert.doesNotMatch(calls[0].options.body, /secret-value/u);
});

test("TavusClient returns useful API errors", async () => {
  const client = new TavusClient("secret-value", {
    fetchImpl: async () => new Response(JSON.stringify({ error: "bad request" }), { status: 400 })
  });
  await assert.rejects(() => client.get("/faces"), TavusApiError);
});

