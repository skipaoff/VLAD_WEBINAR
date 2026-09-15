import { existsSync } from "node:fs";
import { fileURLToPath } from "node:url";
import path from "node:path";

// Ключ можно положить в .env рядом с модулем — тогда его не нужно печатать в терминале.
const envFile = path.join(path.dirname(fileURLToPath(import.meta.url)), "..", ".env");
if (!process.env.TAVUS_API_KEY && existsSync(envFile)) process.loadEnvFile(envFile);

import { readFile, writeFile } from "node:fs/promises";
import { paths } from "../src/config.mjs";
import { faceNameOf, TavusClient } from "../src/tavus-client.mjs";

const apiKey = process.env.TAVUS_API_KEY;
const faceId = process.argv[2];

if (!apiKey || !faceId) {
  console.error("Использование: TAVUS_API_KEY=... npm run tavus:set-face -- FACE_ID");
  process.exit(1);
}

try {
  const state = JSON.parse(await readFile(paths.state, "utf8"));
  const client = new TavusClient(apiKey);
  const face = await client.get(`/faces/${faceId}`);
  if (String(face.status).toLowerCase() === "error") {
    throw new Error(`Face ${faceId} находится в статусе error`);
  }

  await client.patch(`/pals/${state.pal_id}`, [
    { op: "replace", path: "/default_face_id", value: faceId }
  ]);

  state.face_id = faceId;
  state.face_name = faceNameOf(face);
  state.face_status = face.status ?? "unknown";
  state.face_updated_at = new Date().toISOString();
  await writeFile(paths.state, `${JSON.stringify(state, null, 2)}\n`, { mode: 0o600 });

  console.log(`PAL ${state.pal_id} теперь использует Face ${state.face_name} (${faceId}).`);
  if (face.status && !["completed", "ready", "active"].includes(String(face.status).toLowerCase())) {
    console.log(`Текущий статус Face: ${face.status}. Phoenix-4.5 может продолжать фоновую настройку.`);
  }
  console.log("Deployment ID и код виджета менять не нужно.");
} catch (error) {
  console.error(`Не удалось сменить Face: ${error.message}`);
  process.exitCode = 1;
}

