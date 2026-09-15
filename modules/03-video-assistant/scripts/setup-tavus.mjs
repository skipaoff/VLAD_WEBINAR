import { existsSync } from "node:fs";
import { fileURLToPath } from "node:url";
import path from "node:path";

// Ключ можно положить в .env рядом с модулем — тогда его не нужно печатать в терминале.
const envFile = path.join(path.dirname(fileURLToPath(import.meta.url)), "..", ".env");
if (!process.env.TAVUS_API_KEY && existsSync(envFile)) process.loadEnvFile(envFile);

import { loadConfiguration } from "../src/config.mjs";
import { provision } from "../src/provision.mjs";
import { TavusClient } from "../src/tavus-client.mjs";

const apiKey = process.env.TAVUS_API_KEY;
if (!apiKey) {
  console.error("Не задан TAVUS_API_KEY. Положите его в .env рядом с модулем (образец — .env.example).");
  process.exit(1);
}

try {
  const config = await loadConfiguration();
  const client = new TavusClient(apiKey);
  const state = await provision(client, config, {
    onProgress: (message) => console.log(`• ${message}`)
  });
  console.log(`\nPAL: ${state.pal_id}`);
  console.log(`Deployment: ${state.deployment_id}`);
  console.log(`Face: ${state.face_name} (${state.face_id})`);
  console.log("\nЗапустите npm run demo и откройте http://localhost:4173");
} catch (error) {
  console.error(`\nСоздание остановлено: ${error.message}`);
  process.exitCode = 1;
}

