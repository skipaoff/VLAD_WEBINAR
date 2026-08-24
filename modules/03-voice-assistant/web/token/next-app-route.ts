// Выдача короткоживущего токена — вариант для Next.js App Router.
// Копируется как app/api/voice-token/route.ts.
//
// Инварианты те же, что в остальных вариантах:
// - секреты только на сервере, в браузер уходит токен + адрес LiveKit;
// - токен живёт 15 минут и разрешает ровно одну комнату;
// - воркер вызывается по имени: в чужие комнаты он не заходит.
//
// Переменные окружения проекта:
//   LIVEKIT_URL, LIVEKIT_API_KEY, LIVEKIT_API_SECRET, VOICE_AGENT_NAME
// VOICE_AGENT_NAME обязан совпадать с agent_name из worker/config.json.

import { NextResponse } from "next/server";
import {
  AccessToken,
  RoomAgentDispatch,
  RoomConfiguration,
  type VideoGrant,
} from "livekit-server-sdk";

// livekit-server-sdk работает в Node, не в edge.
export const runtime = "nodejs";
export const dynamic = "force-dynamic";

const TOKEN_TTL = "15m";

// Лимит на IP: защита минут LiveKit от того, кто зажал кнопку.
// Память живёт внутри одного инстанса — для демо и небольшого сайта этого хватает;
// на нескольких репликах лимит станет per-instance, тогда нужен Redis.
const RATE_MAX = Number(process.env.VOICE_RATE_MAX || 5);
const RATE_WINDOW_MS = Number(process.env.VOICE_RATE_WINDOW_MS || 10 * 60 * 1000);
const hits = new Map<string, number[]>();

function allow(ip: string): boolean {
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

function clientIp(headers: Headers): string {
  return (
    headers.get("cf-connecting-ip")?.trim() ||
    headers.get("x-real-ip")?.trim() ||
    headers.get("x-forwarded-for")?.split(",")[0].trim() ||
    "local"
  );
}

function rand(n: number): string {
  return crypto.randomUUID().replace(/-/g, "").slice(0, n);
}

export async function POST(req: Request) {
  if (!allow(clientIp(req.headers))) {
    return NextResponse.json({ error: "rate_limited" }, { status: 429 });
  }

  const apiKey = process.env.LIVEKIT_API_KEY;
  const apiSecret = process.env.LIVEKIT_API_SECRET;
  const serverUrl = process.env.LIVEKIT_URL;
  const agentName = process.env.VOICE_AGENT_NAME;

  if (!apiKey || !apiSecret || !serverUrl || !agentName) {
    return NextResponse.json({ error: "voice_not_configured" }, { status: 503 });
  }

  try {
    const roomName = `web-${rand(10)}`;
    const at = new AccessToken(apiKey, apiSecret, {
      identity: `visitor-${rand(12)}`,
      ttl: TOKEN_TTL,
    });
    const grant: VideoGrant = {
      room: roomName,
      roomJoin: true,
      canPublish: true,
      canSubscribe: true,
    };
    at.addGrant(grant);
    at.roomConfig = new RoomConfiguration({
      agents: [new RoomAgentDispatch({ agentName })],
    });

    const token = await at.toJwt();
    return NextResponse.json(
      { serverUrl, token, roomName },
      { headers: { "Cache-Control": "no-store" } },
    );
  } catch {
    return NextResponse.json({ error: "token_failed" }, { status: 500 });
  }
}
