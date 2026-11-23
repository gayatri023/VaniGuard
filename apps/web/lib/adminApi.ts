const BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export class AdminError extends Error {}

export async function adminGet<T>(path: string, token: string): Promise<T> {
  let res: Response;
  try {
    res = await fetch(`${BASE}/api/admin/${path}`, { headers: { "X-Admin-Token": token }, cache: "no-store" });
  } catch {
    throw new AdminError("network");
  }
  if (res.status === 401) throw new AdminError("bad_token");
  if (res.status === 503) throw new AdminError("admin_disabled");
  if (!res.ok) throw new AdminError(`http_${res.status}`);
  return (await res.json()) as T;
}

export async function adminDownload(token: string): Promise<void> {
  const res = await fetch(`${BASE}/api/admin/export.csv`, { headers: { "X-Admin-Token": token } });
  if (!res.ok) throw new AdminError(`http_${res.status}`);
  const url = URL.createObjectURL(await res.blob());
  const a = Object.assign(document.createElement("a"), { href: url, download: "commands_flat.csv" });
  a.click();
  URL.revokeObjectURL(url);
}

export interface Prop { k: number; n: number; rate: number | null; lo: number; hi: number }
export interface RCPoint { threshold: number; n_total: number; n_fast: number; coverage: number; n_wrong: number; wrong_rate: number | null; wilson_lo: number; wilson_hi: number; safe_fast_rate: number; reliable: boolean }
export interface ArmStats { n: number; median_taps: number | null; median_time_ms: number | null; wrong_final: Prop }
export interface Summary {
  synthetic: boolean;
  participants: { started: number; completed: number };
  commands: { logged: number; practice: number; probes: number };
  funnel: { step: string; sessions: number }[];
  dropout_last_screen: Record<string, number>;
  tiers: Record<string, number>; modes: Record<string, number>; arms: Record<string, number>;
  errors_last_hour: number;
  spend: { today_usd: number; daily_cap_usd: number | null; session_cap_usd: number | null };
  versions: { router: string; prompt: string; app: string };
}
export interface Quality {
  n: number;
  fields: Record<string, Prop>;
  by_tag: Record<string, Prop & { below_average_10pts: boolean }>;
  by_difficulty: Record<string, Prop & { below_average_10pts: boolean }>;
  escalation_precision: Prop;
  latency_ms: Record<string, { p50: number | null; p95: number | null; n?: number }>;
}
export interface RiskCoverage { n: number; deltas: number[]; curve: RCPoint[]; live_delta: number; router_version: string; arms: { routed: ArmStats; always_confirm: ArmStats } }
export interface Signal { n: number; ece: number | null; brier: number | null; auroc: number | null; bins: { bin: number; n: number; mean_conf: number; accuracy: number }[] }
export interface Calibration { n: number; signals: Record<string, Signal> }
export interface Health {
  n_commands: number;
  missing: Record<string, number>;
  duplicate_requests: number;
  sessions_without_study_commands: number;
  error_codes: Record<string, number>;
  versions_seen: Record<string, Record<string, number>>;
}
