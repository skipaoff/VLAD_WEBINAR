const defaultBaseUrl = "https://tavusapi.com/v2";

export class TavusApiError extends Error {
  constructor(method, pathname, status, payload) {
    const detail = typeof payload === "string" ? payload : JSON.stringify(payload);
    super(`Tavus ${method} ${pathname} вернул ${status}: ${detail}`);
    this.name = "TavusApiError";
    this.status = status;
    this.payload = payload;
  }
}

export class TavusClient {
  constructor(apiKey, { baseUrl = defaultBaseUrl, fetchImpl = fetch } = {}) {
    if (!apiKey) throw new Error("Не задан TAVUS_API_KEY");
    this.apiKey = apiKey;
    this.baseUrl = baseUrl.replace(/\/$/u, "");
    this.fetch = fetchImpl;
  }

  async request(method, pathname, body) {
    const response = await this.fetch(`${this.baseUrl}${pathname}`, {
      method,
      headers: {
        "x-api-key": this.apiKey,
        ...(body === undefined ? {} : { "content-type": "application/json" })
      },
      ...(body === undefined ? {} : { body: JSON.stringify(body) })
    });

    const raw = await response.text();
    let payload = raw;
    if (raw) {
      try {
        payload = JSON.parse(raw);
      } catch {
        // Keep the original response for a useful error message.
      }
    }

    if (!response.ok) throw new TavusApiError(method, pathname, response.status, payload);
    return payload;
  }

  get(pathname) {
    return this.request("GET", pathname);
  }

  post(pathname, body) {
    return this.request("POST", pathname, body);
  }

  put(pathname, body = {}) {
    return this.request("PUT", pathname, body);
  }

  patch(pathname, body) {
    return this.request("PATCH", pathname, body);
  }

  delete(pathname) {
    return this.request("DELETE", pathname);
  }
}

function normalizeFaces(payload) {
  if (Array.isArray(payload)) return payload;
  for (const key of ["data", "faces", "replicas"]) {
    if (Array.isArray(payload?.[key])) return payload[key];
  }
  return [];
}

export function selectFace(payload, requestedFaceId = "") {
  const faces = normalizeFaces(payload);
  if (requestedFaceId) {
    const exact = faces.find((face) => [face.face_id, face.replica_id, face.id, face.uuid].includes(requestedFaceId));
    return exact ?? { face_id: requestedFaceId, face_name: "Configured face" };
  }

  const ready = faces.filter((face) => !face.status || ["ready", "completed", "active"].includes(String(face.status).toLowerCase()));
  const ranked = ready.length ? ready : faces;
  const preferred = ranked.find((face) => {
    const searchable = JSON.stringify(face).toLowerCase();
    return searchable.includes("phoenix-4.5") || searchable.includes("phoenix_4_5") || searchable.includes("phoenix 4.5");
  });
  const selected = preferred ?? ranked[0];
  if (!selected) throw new Error("Tavus не вернул ни одного доступного лица");
  return selected;
}

export function faceIdOf(face) {
  return face.face_id ?? face.replica_id ?? face.id ?? face.uuid;
}

export function faceNameOf(face) {
  return face.face_name ?? face.replica_name ?? face.name ?? "Stock face";
}
