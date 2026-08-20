// Выдача короткоживущего токена на разговор — вариант для Vercel и Next.js Pages Router.
// Копируется как api/voice-token.js (статика и Vite) или pages/api/voice-token.js (Next Pages).
// Для Next.js App Router используй next-app-route.ts, для Netlify — netlify-function.js.
//
// Инварианты:
// - LIVEKIT_API_SECRET и GEMINI_API_KEY живут только на сервере; в браузер уходит
//   ровно токен, адрес LiveKit и имя комнаты;
// - токен живёт 15 минут и разрешает только одну комнату;
// - воркер вызывается по имени (explicit dispatch) — в чужие комнаты он не заходит.
//
// Переменные окружения проекта сайта:
//   LIVEKIT_URL, LIVEKIT_API_KEY, LIVEKIT_API_SECRET, VOICE_AGENT_NAME
// VOICE_AGENT_NAME обязан совпадать с agent_name из worker/config.json.

import {
  AccessToken,
  RoomAgentDispatch,
  RoomConfiguration,
} from "livekit-server-sdk";

const TOKEN_TTL = "15m";

// Лимит на IP: защита минут LiveKit от того, кто зажал кнопку.
// Память живёт внутри одного инстанса — для демо и небольшого сайта этого хватает;
// на нескольких репликах лимит станет per-instance, тогда нужен Redis.
const RATE_MAX = Number(process.env.VOICE_RATE_MAX || 5);
const RATE_WINDOW_MS = Number(process.env.VOICE_RATE_WINDOW_MS || 10 * 60 * 1000);
const hits = new Map();

function allow(ip) {
  if (RATE_MAX <= 0) return true;
  const now = Date.now();
  const fresh = (hits.get(ip) || []).filter((t) => now - t < RATE_WINDOW_MS);
  if (fresh.length >= RATE_MAX) {
    hits.set(ip, fresh);
    return false;
  }
  fresh.push(now);
  hits.set(ip, fresh);
  return true;
}

function clientIp(req) {
  return (
    req.headers["cf-connecting-ip"] ||
    req.headers["x-real-ip"] ||
    (req.headers["x-forwarded-for"] || "").split(",")[0].trim() ||
    "local"
  );
}

function rand(n) {
  return [...crypto.getRandomValues(new Uint8Array(n))]
    .map((b) => (b % 36).toString(36))
    .join("");
}

export default async function handler(req, res) {
  if (req.method !== "POST") {
    return res.status(405).json({ error: "method_not_allowed" });
  }

  if (!allow(clientIp(req))) {
    return res.status(429).json({ error: "rate_limited" });
  }

  const apiKey = process.env.LIVEKIT_API_KEY;
  const apiSecret = process.env.LIVEKIT_API_SECRET;
  const serverUrl = process.env.LIVEKIT_URL;
  const agentName = process.env.VOICE_AGENT_NAME;

  if (!apiKey || !apiSecret || !serverUrl || !agentName) {
    return res.status(503).json({ error: "voice_not_configured" });
  }

  try {
    const roomName = `web-${rand(10)}`;
    const at = new AccessToken(apiKey, apiSecret, {
      identity: `visitor-${rand(12)}`,
      ttl: TOKEN_TTL,
    });
    at.addGrant({
      room: roomName,
      roomJoin: true,
      canPublish: true,
      canSubscribe: true,
    });
    at.roomConfig = new RoomConfiguration({
      agents: [new RoomAgentDispatch({ agentName })],
    });

    const token = await at.toJwt();
    res.setHeader("Cache-Control", "no-store");
    return res.status(200).json({ serverUrl, token, roomName });
  } catch {
    return res.status(500).json({ error: "token_failed" });
  }
}
