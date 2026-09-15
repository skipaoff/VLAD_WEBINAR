import assert from "node:assert/strict";
import test from "node:test";
import { buildSystemPrompt, loadConfiguration, validateConfiguration } from "../src/config.mjs";

test("demo configuration is complete", async () => {
  const config = await loadConfiguration();
  assert.deepEqual(validateConfiguration(config), []);
});

test("system prompt contains business facts and final safety rules", async () => {
  const config = await loadConfiguration();
  const prompt = buildSystemPrompt(config);
  assert.match(prompt, /Universal Agent Demo/u);
  assert.match(prompt, /универсального видео-консультанта/u);
  assert.match(prompt, /Не выдумывай факты/u);
  assert.ok(prompt.indexOf("01-identity.md") < prompt.indexOf("04-rules.md"));
});

test("invalid objective transition is reported", async () => {
  const config = await loadConfiguration();
  const broken = structuredClone(config);
  broken.objectives.data[0].next_required_objective = "missing_objective";
  assert.ok(validateConfiguration(broken).some((error) => error.includes("missing_objective")));
});


test("assistant has exactly one name in the prompt", async () => {
  const config = await loadConfiguration();
  const prompt = buildSystemPrompt(config);
  const names = [...prompt.matchAll(/Ты\s+—\s+([А-ЯЁA-Z][а-яёa-z]+)/gu)].map((m) => m[1]);
  assert.deepEqual([...new Set(names)], [config.business.assistant_name],
    "имя ассистента задаётся только в business/brand.json");
});

test("setup reads the key from .env instead of the command line", async () => {
  const { readFile } = await import("node:fs/promises");
  for (const script of ["scripts/setup-tavus.mjs", "scripts/set-face.mjs"]) {
    const text = await readFile(new URL(`../${script}`, import.meta.url), "utf8");
    assert.match(text, /loadEnvFile/u, `${script} должен читать .env`);
  }
});
