# Data card

**Purpose.** Evaluate when a Hinglish voice-payment prototype should proceed on one tap, ask a targeted question, or ask for a retry. Pilot data from consenting peers, scripted scenarios, no real money.
**Collected.** Short voice commands (audio is processed in memory/temp files and deleted immediately, never stored), the transcript text, taps and timings, a 3-item survey, coarse device info, self-reported language comfort and noise level. **Not collected:** names, phone numbers, bank details, IP addresses (rate limiting uses salted in-memory hashes only).
**Unit of analysis.** One row in `commands` per voice attempt; participants are `sessions`. Always group by participant when resampling or splitting.
**Always exclude** `is_practice` and `is_probe` rows from accuracy metrics. **Never analyse** rows whose `model` is `synthetic-sim`.
**Known limits.** Convenience sample of peers; scripted scenarios; small n for rare errors; thresholds are v1 placeholders.

Generated from the SQLAlchemy models in `apps/api/vani/db.py` by the documentation build; semantics below are hand-written.

## `sessions`

| column | type | null | meaning |
|---|---|---|---|
| `session_id` | VARCHAR(36) | no | Anonymous random id (UUID). The only identifier; no name, phone, email or IP is stored. |
| `created_at` | DATETIME | no |  |
| `consent_version` | VARCHAR(32) | no |  |
| `consent_at` | DATETIME | no |  |
| `language_comfort` | VARCHAR(24) | no |  |
| `noise_self_report` | VARCHAR(24) | no |  |
| `device_class` | VARCHAR(24) | yes |  |
| `browser` | VARCHAR(48) | yes |  |
| `os` | VARCHAR(48) | yes |  |
| `status` | VARCHAR(16) | no | active, completed (survey submitted), abandoned, deleted. |
| `deletion_code_hash` | VARCHAR(64) | no | SHA-256 of the 8-character code shown once to the participant. Never exported. |
| `card_ids` | JSON | no | JSON list: practice card first, then 8 main cards (2 easy, 3 medium, 3 hard), least-served first. |
| `arms` | JSON | no | JSON list aligned with card_ids: routed or always_confirm, permuted blocks of 4. All routed if arms are off. |

## `commands`

| column | type | null | meaning |
|---|---|---|---|
| `cmd_id` | VARCHAR(36) | no |  |
| `session_id` | VARCHAR(36) | no |  |
| `client_request_id` | VARCHAR(64) | no |  |
| `card_id` | VARCHAR(16) | no |  |
| `is_practice` | BOOLEAN | no | True for the practice card. ALWAYS exclude from accuracy metrics. |
| `seq` | INTEGER | no |  |
| `arm` | VARCHAR(16) | no | routed or always_confirm: the arm this card was randomised to. |
| `is_probe` | BOOLEAN | no | True when the fast-path card showed a deliberately wrong amount or payee. ALWAYS exclude from accuracy; used only for H3. |
| `probe_type` | VARCHAR(16) | yes | amount or payee (which field was made wrong). |
| `ui_mode` | VARCHAR(16) | no | What the participant actually saw: fast (1 tap), verify (chips), confirm_all (3 taps), retry. |
| `shown_payee_id` | VARCHAR(32) | yes | Payee displayed in fast / confirm_all cards (differs from parsed_payee_id on probes). |
| `shown_amount` | INTEGER | yes | Amount displayed in fast / confirm_all cards (differs from parsed_amount on probes). |
| `created_at` | DATETIME | no |  |
| `audio_ms` | INTEGER | yes |  |
| `transcript_roman` | TEXT | yes |  |
| `transcript_raw` | TEXT | yes |  |
| `parsed_payee_id` | VARCHAR(32) | yes | Model's payee resolved to the contact list (top match), or null. |
| `parsed_amount` | INTEGER | yes | Model's amount (integer rupees), or null. |
| `parsed_intent` | VARCHAR(16) | yes |  |
| `parsed_note` | TEXT | yes |  |
| `self_conf` | JSON | no | JSON {payee, amount, intent}: the model's verbalised confidence for sample 0. |
| `agreement` | JSON | no | JSON per field: share of the 3 samples that agree (a failed sample counts as disagreement). |
| `validator_flags` | JSON | no | JSON list of named flags, e.g. amount_mismatch_transcript, amount_over_ceiling. |
| `validator_scores` | JSON | no | JSON per field in [0,1] from the rule validators (not probabilities). |
| `combined_conf` | JSON | no | JSON per field: weighted combination of the three signals (router version dependent). |
| `router_version` | VARCHAR(48) | no |  |
| `route_tier` | VARCHAR(1) | no | Router decision: A fast path, B verify, C retry/manual. In always_confirm this is what the router WOULD have done. |
| `route_reasons` | JSON | no |  |
| `chips` | JSON | yes |  |
| `model` | VARCHAR(64) | no | Model string. 'synthetic-sim' means FAKE data from the simulator: never analyse as results. |
| `prompt_version` | VARCHAR(32) | no |  |
| `app_version` | VARCHAR(32) | no |  |
| `stage_ms` | JSON | no |  |
| `latency_ms` | INTEGER | no |  |
| `tokens_in` | INTEGER | no |  |
| `tokens_out` | INTEGER | no |  |
| `cost_usd` | FLOAT | no | Computed from token usage and config/pricing.yaml. Zero in the dev simulator. |
| `pricing_version` | VARCHAR(32) | yes |  |
| `error_code` | VARCHAR(48) | yes |  |
| `correct_payee` | BOOLEAN | yes | Parsed payee equals the card's ground truth. Truth comes from the scenario card, never from the model. |
| `correct_amount` | BOOLEAN | yes | Parsed amount equals the card's ground truth. |
| `correct_intent` | BOOLEAN | yes |  |
| `correct_all` | BOOLEAN | yes | Payee, amount and intent all correct. The label for wrong-execution analysis. |
| `user_action_final` | VARCHAR(16) | yes | paid, edited, manual, retried, abandoned. |
| `final_payee_id` | VARCHAR(32) | yes | What was finally paid (after chips / edits / manual entry). |
| `final_amount` | INTEGER | yes |  |
| `final_correct_all` | BOOLEAN | yes | Final values equal ground truth (false for a paid probe). |
| `chip_field` | VARCHAR(8) | yes |  |
| `taps_count` | INTEGER | yes | Button presses from result shown to final action; typing an amount counts once. |
| `time_to_mic_ms` | INTEGER | yes | Card shown to mic tap. |
| `time_result_to_action_ms` | INTEGER | yes | Result shown to final action. |
| `time_to_complete_ms` | INTEGER | yes | Card shown to final action. |
| `response_json` | JSON | no |  |

## `samples`

| column | type | null | meaning |
|---|---|---|---|
| `id` | INTEGER | no |  |
| `cmd_id` | VARCHAR(36) | no |  |
| `sample_idx` | INTEGER | no |  |
| `temperature` | FLOAT | no |  |
| `raw_json` | JSON | yes |  |
| `latency_ms` | INTEGER | no |  |
| `tokens_in` | INTEGER | no |  |
| `tokens_out` | INTEGER | no |  |
| `status` | VARCHAR(32) | no |  |

## `events`

| column | type | null | meaning |
|---|---|---|---|
| `event_id` | INTEGER | no |  |
| `ts` | DATETIME | no |  |
| `session_id` | VARCHAR(36) | no |  |
| `cmd_id` | VARCHAR(36) | yes |  |
| `type` | VARCHAR(32) | no | Funnel and system events (screen_view, command_routed, action, mic_denied...). Append-only at the database level. |
| `payload` | JSON | no |  |
| `app_version` | VARCHAR(32) | no |  |

## `surveys`

| column | type | null | meaning |
|---|---|---|---|
| `session_id` | VARCHAR(36) | no |  |
| `trust_amount` | INTEGER | no |  |
| `low_effort` | INTEGER | no |  |
| `would_use` | INTEGER | no |  |
| `free_text` | TEXT | yes |  |
| `submitted_at` | DATETIME | no |  |

## `deletions`

| column | type | null | meaning |
|---|---|---|---|
| `id` | INTEGER | no |  |
| `session_hash` | VARCHAR(64) | no | SHA-256 of a deleted session id: proof a deletion happened, no data. |
| `deleted_at` | DATETIME | no |  |

## `delete_gate`

| column | type | null | meaning |
|---|---|---|---|
| `id` | INTEGER | no |  |
| `allow` | INTEGER | no | Internal switch, 1 only inside the participant-deletion transaction. |
