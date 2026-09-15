import { mkdir, writeFile, access } from "node:fs/promises";
import path from "node:path";
import { buildSystemPrompt, paths, validateConfiguration } from "./config.mjs";
import { faceIdOf, faceNameOf, selectFace } from "./tavus-client.mjs";

async function exists(filePath) {
  try {
    await access(filePath);
    return true;
  } catch {
    return false;
  }
}

async function persistState(filePath, state) {
  await mkdir(path.dirname(filePath), { recursive: true });
  await writeFile(filePath, `${JSON.stringify(state, null, 2)}\n`, { mode: 0o600 });
}

function withCallback(items, webhookUrl) {
  if (!webhookUrl) return items;
  return items.map((item) => ({ ...item, callback_url: webhookUrl }));
}

export async function provision(client, config, { onProgress = () => {} } = {}) {
  const errors = validateConfiguration(config);
  if (errors.length) throw new Error(`Конфигурация не готова:\n- ${errors.join("\n- ")}`);
  if (await exists(paths.state)) {
    throw new Error("Профиль уже создан: найден .tavus/state.json. Не создаю дубликаты.");
  }

  const created = { guardrail_ids: [] };
  try {
    onProgress("Выбираю доступное stock-лицо");
    const faces = await client.get("/faces?limit=100&verbose=true");
    const face = selectFace(faces, config.tavus.face_id);
    created.face_id = faceIdOf(face);
    created.face_name = faceNameOf(face);
    if (!created.face_id) throw new Error("У выбранного лица отсутствует face_id");

    onProgress("Создаю Objectives");
    const objectiveResponse = await client.post("/objectives", {
      data: withCallback(config.objectives.data, config.business.webhook_url)
    });
    created.objectives_id = objectiveResponse.objectives_id;

    onProgress("Создаю Guardrails");
    for (const guardrail of config.guardrails) {
      const response = await client.post("/guardrails", {
        ...guardrail,
        ...(config.business.webhook_url ? { callback_url: config.business.webhook_url } : {})
      });
      created.guardrail_ids.push(response.uuid);
    }

    onProgress("Создаю PAL");
    const palResponse = await client.post("/pals", {
      pal_name: config.tavus.pal_name,
      pipeline_mode: config.tavus.pipeline_mode,
      system_prompt: buildSystemPrompt(config),
      default_face_id: created.face_id,
      languages: config.tavus.languages,
      objectives_id: created.objectives_id,
      guardrail_ids: created.guardrail_ids,
      disclosure_type: config.tavus.disclosure_type,
      verbal_disclosure: config.tavus.verbal_disclosure,
      visual_disclosure: config.tavus.visual_disclosure
    });
    created.pal_id = palResponse.pal_id;

    for (const skill of config.tavus.skills ?? []) {
      onProgress(`Подключаю skill ${skill}`);
      await client.put(`/pals/${created.pal_id}/skills/${skill}`, {});
    }

    onProgress("Создаю защищённый Deployment");
    const deployment = config.tavus.deployment;
    const deploymentResponse = await client.post("/deployments", {
      pal_id: created.pal_id,
      channel: deployment.channel,
      name: deployment.name,
      password: deployment.password,
      customization: deployment.customization,
      limits: deployment.limits,
      allowed_origins: config.business.allowed_origins
    });
    created.deployment_id = deploymentResponse.deployment_id;

    if (deployment.status && deploymentResponse.status !== deployment.status) {
      onProgress(`Перевожу Deployment в статус ${deployment.status}`);
      await client.patch(`/deployments/${created.deployment_id}`, [
        { op: "replace", path: "/status", value: deployment.status }
      ]);
    }

    const state = {
      version: 1,
      created_at: new Date().toISOString(),
      brand_name: config.business.brand_name,
      ...created
    };
    await persistState(paths.state, state);
    await writeFile(
      paths.runtime,
      `window.TAVUS_RUNTIME = ${JSON.stringify({
        deploymentId: created.deployment_id,
        greeting: config.business.greeting,
        context: `Это демонстрация для бренда ${config.business.brand_name}. Цель текущего разговора: ${config.business.primary_goal}.`,
        memoryEnabled: config.business.memory.enabled_for_anonymous_visitors,
        memoryNamespace: config.business.memory.namespace
      }, null, 2)};\n`
    );

    onProgress("Готово");
    return state;
  } catch (error) {
    await persistState(paths.failedState, {
      created_at: new Date().toISOString(),
      error: error.message,
      ...created
    });
    throw error;
  }
}

