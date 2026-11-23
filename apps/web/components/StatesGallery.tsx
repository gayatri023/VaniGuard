"use client";
import type { ReactNode } from "react";
import { STRINGS } from "@/lib/i18n";
import type { CommandResult, Contact } from "@/lib/types";
import { Consent } from "./Consent";
import { End, Survey, SystemNotice } from "./Finish";
import { MicSetup } from "./MicSetup";
import { Confirm, ConfirmAll, Manual, Processing, Success, TierB, TierC } from "./Results";
import { Task } from "./Task";

const t = STRINGS.en;
const noop = () => undefined;
const contacts: Contact[] = ["Priya", "Pooja", "Amit", "Ankit", "Rahul Sharma", "Rahul Sethi"].map((n) => ({ payee_id: n.toLowerCase().replace(" ", "_"), display_name: n }));
const base = { cmd_id: "demo", tier: "B" as const, latency_ms: 1200 };
const amountB: CommandResult = { ...base, mode: "verify", fields: { payee: { id: "amit", name: "Amit" }, amount: null, note: "stationery" }, chips: { field: "amount", options: [{ label: "₹15", value: 15 }, { label: "₹50", value: 50 }] } };
const payeeB: CommandResult = { ...base, mode: "verify", fields: { payee: null, amount: 250, note: "lunch" }, chips: { field: "payee", options: [{ label: "Rahul Sharma", value: "rahul_sharma" }, { label: "Rahul Sethi", value: "rahul_sethi" }] } };

/** Every screen and state with fixture data. Used by /dev/states (visual QA) and by the axe test. */
export const STATES: { id: string; label: string; node: ReactNode }[] = [
  { id: "consent", label: "S0 Consent", node: <Consent t={t} busy={false} error={false} probes={false} onStart={noop} /> },
  { id: "consent-probes", label: "S0 Consent (probes disclosed)", node: <Consent t={t} busy={false} error={true} probes={true} onStart={noop} /> },
  { id: "mic", label: "S1 Mic setup", node: <MicSetup t={t} onReady={noop} onEvent={noop} /> },
  { id: "task-practice", label: "S3 Task: practice", node: <Task t={t} card={{ card_id: "p0", scenario_text: "Practice: Pay Priya Rs 20 for chai.", practice: true }} index={0} total={8} onStart={noop} onRecorded={noop} onMicError={noop} onDev={noop} /> },
  { id: "task", label: "S3 Task 3 of 8", node: <Task t={t} card={{ card_id: "h1", scenario_text: "Pay Rahul Sethi Rs 250 for lunch.", practice: false }} index={3} total={8} onStart={noop} onRecorded={noop} onMicError={noop} onDev={noop} /> },
  { id: "processing", label: "S4 Processing", node: <Processing t={t} onCancel={noop} onSlow={noop} /> },
  { id: "fast", label: "S5a Fast path (Tier A)", node: <Confirm t={t} payee="Priya" amount={150000} note="the cab" onPay={noop} onEdit={noop} /> },
  { id: "verify-amount", label: "S5b Verify: amount chips", node: <TierB t={t} result={amountB} onPay={noop} onElse={noop} onTap={noop} /> },
  { id: "verify-payee", label: "S5b Verify: payee chips", node: <TierB t={t} result={payeeB} onPay={noop} onElse={noop} onTap={noop} /> },
  { id: "retry", label: "S5c Retry", node: <TierC t={t} retries={0} onRetry={noop} onManual={noop} /> },
  { id: "retry-manual", label: "S5c Manual only (after 2 retries)", node: <TierC t={t} retries={2} onRetry={noop} onManual={noop} /> },
  { id: "confirm-all", label: "S5d Always-confirm arm", node: <ConfirmAll t={t} payee="Amit" amount={15} note="stationery" onTap={noop} onPay={noop} onEdit={noop} /> },
  { id: "manual", label: "Manual entry", node: <Manual t={t} contacts={contacts} onSubmit={noop} onBack={noop} onTap={noop} /> },
  { id: "success", label: "S6 Success", node: <Success t={t} onNext={noop} /> },
  { id: "survey", label: "S7 Survey", node: <Survey t={t} busy={false} onSubmit={noop} /> },
  { id: "end", label: "S8 End and deletion code", node: <End t={t} code="A1B2C3D4" probes={true} onDelete={async () => true} /> },
  { id: "sys-paused", label: "System: study paused", node: <SystemNotice t={t} kind="paused" /> },
  { id: "sys-error", label: "System: server error", node: <SystemNotice t={t} kind="error" onRetry={noop} /> },
  { id: "sys-network", label: "System: network", node: <SystemNotice t={t} kind="network" onRetry={noop} /> },
  { id: "sys-limit", label: "System: session limit", node: <SystemNotice t={t} kind="limit" /> },
];

export default function StatesGallery() {
  return (
    <div className="mx-auto max-w-5xl p-4">
      <h1 className="type-headline-m mb-1">Every screen and state</h1>
      <p className="type-body-l mb-6 text-on-surface-variant">Visual QA with fixture data. Toggle your OS dark mode to check both themes. Not linked from the app and disabled in production.</p>
      <ol className="grid gap-8 md:grid-cols-2">
        {STATES.map((s) => (
          <li key={s.id} id={s.id}>
            <p className="type-label-l mb-2 rounded-full bg-secondary-container px-3 py-1 text-on-secondary-container inline-block">{s.label}</p>
            <div className="rounded-3xl border border-outline-variant bg-surface p-3">{s.node}</div>
          </li>
        ))}
      </ol>
    </div>
  );
}
