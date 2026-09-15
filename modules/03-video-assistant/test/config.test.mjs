import assert from "node:assert/strict";
import test from "node:test";
import { buildSystemPrompt, loadConfiguration, validateConfiguration } from "../src/config.mjs";

const isTemplate = async () => /\{\{[^}]+\}\}/u.test(JSON.stringify((await loadConfiguration()).business));
const templateSkip = (await isTemplate()) && "модуль ещё не заполнен под бизнес";

test("configuration is complete", { skip: templateSkip }, async () => {
  const config = await loadConfiguration();
  assert.deepEqual(validateConfiguration(config), []);
});

test("fresh template is recognised as unfilled", async () => {
  const config = await loadConfiguration();
  if (!templateSkip) return;
  assert.ok(validateConfiguration(config).some((e) => e.includes("{{")),
    "незаполненный шаблон не должен проходить проверку");
});

test("system prompt contains business facts and final safety rules", { skip: templateSkip }, async () => {
  const config = await loadConfiguration();
  const prompt = buildSystemPrompt(config);
  assert.ok(prompt.includes(config.business.brand_name), "в промпте нет названия бренда");
  assert.ok(prompt.includes(config.business.business_type), "в промпте нет описания бизнеса");
  assert.match(prompt, /Не выдумывай факты/u);
  assert.ok(prompt.indexOf("01-identity.md") < prompt.indexOf("04-rules.md"));
});

test("invalid objective transition is reported", async () => {
  const config = await loadConfiguration();
  const broken = structuredClone(config);
  broken.objectives.data[0].next_required_objective = "missing_objective";
  assert.ok(validateConfiguration(broken).some((error) => error.includes("missing_objective")));
});


test("assistant has exactly one name in the prompt", { skip: templateSkip }, async () => {
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
