export type Tier = "A" | "B" | "C";
export type Field = "payee" | "amount";
export interface Chip { label: string; value: string | number }
export type Mode = "fast" | "verify" | "confirm_all" | "retry";
export interface PublicConfig { probes_enabled: boolean; consent_version: string; total_cards: number }
export interface CommandResult {
  cmd_id: string;
  tier: Tier;
  mode: Mode;
  fields: { payee: { id: string; name: string } | null; amount: number | null; note: string | null } | null;
  chips: { field: Field; options: Chip[] } | null;
  latency_ms: number;
  debug?: Record<string, unknown>;
}
export interface TaskCard { card_id: string; scenario_text: string; practice: boolean }
export interface NextCard { done: boolean; card: TaskCard | null; index: number; total: number }
export interface Contact { payee_id: string; display_name: string }
export interface SessionInfo { id: string; code: string }
export interface ActionBody {
  action: "pay" | "retry" | "manual" | "edit" | "abandon";
  chip_field?: Field;
  chip_value?: string | number;
  final_payee_id?: string;
  final_amount?: number;
  taps_count: number;
  time_to_mic_ms?: number | null;
  time_result_to_action_ms?: number | null;
  time_to_complete_ms?: number | null;
}
export interface Survey { trust_amount: number; low_effort: number; would_use: number; free_text?: string }
export interface DevOverrides {
  amount_value?: number | null;
  self_conf?: number;
  sample_amounts?: (number | null)[];
  fail_samples?: number[];
  intent?: string;
}
