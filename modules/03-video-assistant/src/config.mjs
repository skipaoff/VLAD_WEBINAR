import { readFile, readdir } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";

const projectRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const knowledgeOrder = [
  "01-identity.md",
  "02-services.md",
  "03-pricing.md",
  "04-rules.md"
];

export const paths = {
  root: projectRoot,
  business: path.join(projectRoot, "business", "brand.json"),
  knowledge: path.join(projectRoot, "business", "kb"),
  tavus: path.join(projectRoot, "config", "tavus.json"),
  objectives: path.join(projectRoot, "config", "objectives.json"),
  guardrails: path.join(projectRoot, "config", "guardrails.json"),
  state: path.join(projectRoot, ".tavus", "state.json"),
  failedState: path.join(projectRoot, ".tavus", "failed-state.json"),
  runtime: path.join(projectRoot, "demo", "runtime-config.js")
};

export async function readJson(filePath) {
  return JSON.parse(await readFile(filePath, "utf8"));
}

export async function loadConfiguration() {
  const [business, tavus, objectives, guardrails] = await Promise.all([
    readJson(paths.business),
    readJson(paths.tavus),
    readJson(paths.objectives),
    readJson(paths.guardrails)
  ]);

  const knowledge = [];
  for (const filename of knowledgeOrder) {
    knowledge.push({
      filename,
      content: await readFile(path.join(paths.knowledge, filename), "utf8")
    });
  }

  return { business, tavus, objectives, guardrails, knowledge };
}

export function validateConfiguration(config) {
  const errors = [];
  const requiredBusinessFields = [
    "brand_name",
    "assistant_name",
    "business_type",
    "audience",
    "tone",
    "language",
    "greeting",
    "primary_goal"
  ];

  for (const field of requiredBusinessFields) {
    if (!String(config.business[field] ?? "").trim()) {
      errors.push(`business/brand.json: поле ${field} обязательно`);
    }
  }

  if (!Array.isArray(config.business.allowed_origins) || config.business.allowed_origins.length === 0) {
    errors.push("business/brand.json: задайте хотя бы один allowed_origin");
  }

  if (!Array.isArray(config.objectives.data) || config.objectives.data.length === 0) {
    errors.push("config/objectives.json: требуется хотя бы одна цель");
  }

  if (!Array.isArray(config.guardrails) || config.guardrails.length === 0) {
    errors.push("config/guardrails.json: требуется хотя бы одно ограничение");
  }

  const serialized = JSON.stringify(config);
  if (/\{\{[^}]+\}\}/u.test(serialized)) {
    errors.push("В активной конфигурации остались метки {{...}}");
  }

  const objectiveNames = new Set(config.objectives.data.map((item) => item.objective_name));
  for (const objective of config.objectives.data) {
    if (objective.next_required_objective && !objectiveNames.has(objective.next_required_objective)) {
      errors.push(`Objective ${objective.objective_name}: неизвестная следующая цель ${objective.next_required_objective}`);
    }
    for (const nextName of Object.keys(objective.next_conditional_objectives ?? {})) {
      if (!objectiveNames.has(nextName)) {
        errors.push(`Objective ${objective.objective_name}: неизвестная условная цель ${nextName}`);
      }
    }
    if (objective.next_required_objective && objective.next_conditional_objectives) {
      errors.push(`Objective ${objective.objective_name}: нельзя одновременно задавать required и conditional переходы`);
    }
  }

  return errors;
}

export function buildSystemPrompt(config) {
  const { business, knowledge } = config;
  const knowledgeText = knowledge
    .map(({ filename, content }) => `\n<!-- ${filename} -->\n${content.trim()}`)
    .join("\n");

  return `# Основная роль

Ты — ${business.assistant_name}, AI-видеоконсультант бренда «${business.brand_name}».
Бизнес: ${business.business_type}.
Целевая аудитория: ${business.audience}.
Стиль общения: ${business.tone}.
Основная бизнес-цель разговора: ${business.primary_goal}.

# Протокол разговора

- Общайся на языке с кодом ${business.language}.
- Сначала ответь на прямой вопрос посетителя, затем задай не более одного уточняющего вопроса.
- Не превращай разговор в анкету: обычно достаточно двух-трёх уточнений за весь звонок.
- Используй только факты из базы знаний и контекста текущего разговора.
- Если точных данных нет, честно скажи об этом и предложи безопасный следующий шаг.
- Запрашивай контакт только после явного согласия на дальнейшую связь.
- Если интерактивный ввод доступен, предпочитай его для телефона, email и выбора времени.
- Стремись завершить разговор не позднее чем через ${business.call_duration_minutes} минуты.
- После достижения цели кратко подведи итог и заверши звонок инструментом end_call.

# База знаний
${knowledgeText}`;
}

export async function listActiveFiles() {
  const files = [paths.business, paths.tavus, paths.objectives, paths.guardrails];
  for (const filename of await readdir(paths.knowledge)) {
    if (filename.endsWith(".md")) files.push(path.join(paths.knowledge, filename));
  }
  return files;
}

