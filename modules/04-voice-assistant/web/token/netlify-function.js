// Выдача короткоживущего токена — вариант для Netlify.
// Копируется как netlify/functions/voice-token.js.
// Адрес функции: /.netlify/functions/voice-token — его и передавай виджету
// через data-token-url, либо пропиши редирект в netlify.toml:
//
//   [[redirects]]
//     from = "/api/voice-token"
//     to = "/.netlify/functions/voice-token"
//     status = 200
//
// Переменные окружения сайта:
//   LIVEKIT_URL, LIVEKIT_API_KEY, LIVEKIT_API_SECRET, VOICE_AGENT_NAME

import {
  AccessToken,
  RoomAgentDispatch,
  RoomConfiguration,
} from "livekit-server-sdk";

const TOKEN_TTL = "15m";
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

function rand(n) {
  return [...crypto.getRandomValues(new Uint8Array(n))]
    .map((b) => (b % 36).toString(36))
    .join("");
}

const json = (body, status) =>
  new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json", "Cache-Control": "no-store" },
  });

export default async function handler(req) {
  if (req.method !== "POST") return json({ error: "method_not_allowed" }, 405);

  const ip =
    req.headers.get("x-nf-client-connection-ip") ||
    req.headers.get("x-forwarded-for")?.split(",")[0].trim() ||
    "local";
  if (!allow(ip)) return json({ error: "rate_limited" }, 429);

  const apiKey = process.env.LIVEKIT_API_KEY;
  const apiSecret = process.env.LIVEKIT_API_SECRET;
  const serverUrl = process.env.LIVEKIT_URL;
  const agentName = process.env.VOICE_AGENT_NAME;
  if (!apiKey || !apiSecret || !serverUrl || !agentName) {
    return json({ error: "voice_not_configured" }, 503);
  }

  try {
    const roomName = `web-${rand(10)}`;
    const at = new AccessToken(apiKey, apiSecret, {
      identity: `visitor-${rand(12)}`,
      ttl: TOKEN_TTL,
    });
    at.addGrant({ room: roomName, roomJoin: true, canPublish: true, canSubscribe: true });
    at.roomConfig = new RoomConfiguration({ agents: [new RoomAgentDispatch({ agentName })] });
    return json({ serverUrl, token: await at.toJwt(), roomName }, 200);
  } catch {
    return json({ error: "token_failed" }, 500);
  }
}
