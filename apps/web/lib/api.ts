import type { ActionBody, CommandResult, Contact, DevOverrides, NextCard, PublicConfig, Survey } from "./types";

const BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export class ApiError extends Error {
  constructor(public status: number, public code: string) {
    super(code);
  }
}

async function call<T>(path: string, init?: RequestInit): Promise<T> {
  let res: Response;
  try {
    res = await fetch(`${BASE}${path}`, init);
  } catch (e) {
    if (init?.signal?.aborted) throw e;
    throw new ApiError(0, "network");
  }
  if (!res.ok) {
    let code = `http_${res.status}`;
    try {
      const b = await res.json();
      const c = b.error ?? b.detail;
      if (typeof c === "string") code = c;
    } catch {}
    throw new ApiError(res.status, code);
  }
  return (await res.json()) as T;
}

const json = (body: unknown): RequestInit => ({
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify(body),
});

export interface CommandInput {
  sessionId: string;
  cardId: string;
  requestId: string;
  audio?: { blob: Blob; mime: string; ms: number };
  dev?: { transcript: string; overrides: DevOverrides };
}

export const api = {
  config: () => call<PublicConfig>("/api/config"),
  createSession: (b: { consent_version: string; language_comfort: string; noise_self_report: string; device_class?: string; browser?: string; os?: string }) =>
    call<{ session_id: string; deletion_code: string; total_cards: number }>("/api/sessions", json(b)),
  nextCard: (sid: string) => call<NextCard>(`/api/sessions/${sid}/next-card`),
  contacts: () => call<Contact[]>("/api/contacts"),
  postCommand: (c: CommandInput, signal: AbortSignal) => {
    const f = new FormData();
    f.set("session_id", c.sessionId);
    f.set("card_id", c.cardId);
    f.set("client_request_id", c.requestId);
    if (c.audio) {
      f.set("client_audio_mime", c.audio.mime);
      f.set("audio_ms", String(c.audio.ms));
      f.set("audio", c.audio.blob, "clip");
    }
    if (c.dev) {
      f.set("dev_transcript", c.dev.transcript);
      f.set("dev_overrides", JSON.stringify(c.dev.overrides));
    }
    return call<CommandResult>("/api/commands", { method: "POST", body: f, signal });
  },
  postAction: (cmdId: string, b: ActionBody) => call<{ ok: boolean }>(`/api/commands/${cmdId}/action`, json(b)),
  survey: (sid: string, b: Survey) => call<{ ok: boolean }>(`/api/sessions/${sid}/survey`, json(b)),
  event: (sid: string, type: string, payload: Record<string, unknown> = {}) =>
    call<{ ok: boolean }>("/api/events", json({ session_id: sid, type, payload })).catch(() => undefined),
  deleteSession: (sid: string, code: string) =>
    call<{ deleted: boolean }>(`/api/sessions/${sid}/delete`, json({ deletion_code: code })),
};
