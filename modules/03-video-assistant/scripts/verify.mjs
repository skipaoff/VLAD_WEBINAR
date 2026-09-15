import { readFile } from "node:fs/promises";
import { loadConfiguration, listActiveFiles, paths, validateConfiguration } from "../src/config.mjs";

const config = await loadConfiguration();
const errors = validateConfiguration(config);

for (const filePath of await listActiveFiles()) {
  const content = await readFile(filePath, "utf8");
  if (/\b[a-f0-9]{32}\b/iu.test(content)) {
    errors.push(`${filePath.replace(`${paths.root}/`, "")}: обнаружена строка, похожая на API-ключ`);
  }
}

if (errors.length) {
  console.error(`Проверка не пройдена:\n- ${errors.join("\n- ")}`);
  process.exitCode = 1;
} else {
  console.log("Конфигурация готова: обязательные поля заполнены, переходы Objectives корректны, ключей в активных файлах нет.");
}

