import assert from "node:assert/strict";
import test from "node:test";
import {
  buildSystemPrompt,
  languagePack,
  loadConfiguration,
  palLanguages,
  validateConfiguration
} from "../src/config.mjs";
import { localizedDeploymentText } from "../src/provision.mjs";

// Язык в шаблоне не заполнен, поэтому проверки языка собирают конфигурацию сами.
const withLanguage = async (code, extra = []) => {
  const config = structuredClone(await loadConfiguration());
  config.business.language = code;
  config.tavus.extra_languages = extra;
  return config;
};

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
  const rules = config.knowledge.at(-1);
  assert.equal(rules.filename, "04-rules.md", "ограничения должны идти последними");
  assert.ok(prompt.includes(rules.content.trim()), "в промпте нет файла с ограничениями");
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


test("language from brand.json reaches the prompt", async () => {
  const config = await withLanguage("uk");
  const pack = languagePack(config);
  const prompt = buildSystemPrompt(config);
  assert.ok(pack, "для uk должен быть блок в config/languages.json");
  assert.ok(prompt.includes(pack.native_instruction), "в промпте нет указания языка на самом языке");
  assert.ok(prompt.includes(`код uk`), "в промпте нет кода языка");
});

test("unknown language code is reported", async () => {
  const errors = validateConfiguration(await withLanguage("zz"));
  assert.ok(errors.some((error) => error.includes("languages.json")),
    "неизвестный язык должен отправлять к config/languages.json");
});

test("language that is not a code at all is reported", async () => {
  const errors = validateConfiguration(await withLanguage("украинский"));
  assert.ok(errors.some((error) => error.includes("ISO 639-1")));
});

test("extra languages join the main one without duplicates", async () => {
  assert.deepEqual(palLanguages(await withLanguage("uk", ["ru"])), ["uk", "ru"]);
  assert.deepEqual(palLanguages(await withLanguage("uk", ["UK", "ru"])), ["uk", "ru"]);
});

test("button labels are translated for every shipped language", async () => {
  const { languages } = await loadConfiguration();
  for (const [code, pack] of Object.entries(languages)) {
    const ops = localizedDeploymentText(pack);
    const paths = ops.map((op) => op.path);
    assert.ok(paths.includes("/customization/widget/text/title"), `${code}: нет заголовка кнопки`);
    assert.ok(paths.includes("/customization/haircheck/join_button"), `${code}: нет кнопки входа`);
    assert.ok(ops.every((op) => op.op === "replace" && typeof op.value === "string" && op.value.length));
  }
  assert.deepEqual(localizedDeploymentText(null), [], "без языкового блока надписи не трогаем");
});
