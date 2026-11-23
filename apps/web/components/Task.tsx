"use client";
import { useEffect, useRef } from "react";
import { MAX_MS, useRecorder, type Recording } from "@/lib/recorder";
import type { Strings } from "@/lib/i18n";
import type { DevOverrides, TaskCard } from "@/lib/types";
import { Button, Card, Icon, ProgressBar, Screen } from "./ui";

const DEV = process.env.NEXT_PUBLIC_DEV === "1";

const PRESETS: { label: string; text: string; o?: DevOverrides }[] = [
  { label: "Clear command -> A", text: "Priya ko bees rupaye bhej do" },
  { label: "Samples disagree on 15/50 -> B (amount)", text: "Amit ko pandrah rupaye bhej do", o: { sample_amounts: [15, 15, 50] } },
  { label: "Two Rahuls -> B (payee)", text: "Rahul ko pachaas rupaye bhej do" },
  { label: "Model misreads 15 as 50 -> C", text: "Amit ko pandrah rupaye bhej do", o: { amount_value: 50 } },
  { label: "Can't understand -> C", text: "mujhe kuch samajh nahi aaya" },
];

export function Task({ t, card, index, total, onStart, onRecorded, onMicError, onDev }: {
  t: Strings; card: TaskCard; index: number; total: number;
  onStart: () => void; onRecorded: (r: Recording) => void; onMicError: (e: string) => void;
  onDev: (transcript: string, o: DevOverrides) => void;
}) {
  const rec = useRecorder(onRecorded);
  const textRef = useRef<HTMLInputElement>(null);
  useEffect(() => {
    if (rec.error) onMicError(rec.error);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [rec.error]);

  const R = 68;
  const C = 2 * Math.PI * R;
  const left = Math.max(0, MAX_MS - rec.elapsed);
  const label = card.practice ? t.task.practice : t.task.taskOf(index, total);
  return (
    <Screen>
      <div className="px-1">
        <div className="mb-2 flex items-center justify-between">
          <span className="type-label-l text-primary">{label}</span>
          {card.practice ? null : <span className="type-label-l tnum text-on-surface-variant">{index}/{total}</span>}
        </div>
        <ProgressBar value={card.practice ? 0 : index / total} label={label} />
      </div>

      <Card tone="primary">
        <p className="type-headline-l">{card.scenario_text.replace(/^Practice: /, "")}</p>
        <p className="type-body-l mt-3 opacity-80">{t.task.instruction}</p>
      </Card>

      <Card tone="low" className="flex flex-col items-center gap-3">
        <div className="flex h-14 items-end gap-1" aria-hidden>
          {rec.history.map((h, i) => (
            <span key={i} className="w-1.5 rounded-full bg-primary transition-opacity" style={{ height: `${Math.max(6, h * 56)}px`, opacity: rec.recording ? 1 : 0.25 }} />
          ))}
        </div>
        <div className="relative flex size-44 items-center justify-center">
          {rec.recording ? <span aria-hidden className="vg-ring absolute size-24 rounded-full bg-primary/40" /> : null}
          <svg className="absolute inset-0 -rotate-90" viewBox="0 0 160 160" aria-hidden>
            <circle cx="80" cy="80" r={R} fill="none" stroke="var(--md-sys-color-surface-container-highest)" strokeWidth="8" />
            <circle cx="80" cy="80" r={R} fill="none" stroke="var(--md-sys-color-primary)" strokeWidth="8" strokeLinecap="round"
              strokeDasharray={C} strokeDashoffset={rec.recording ? C * (rec.elapsed / MAX_MS) : C} style={{ transition: "stroke-dashoffset 120ms linear" }} />
          </svg>
          <button type="button" aria-label={rec.recording ? t.task.tapStop : t.task.tapStart}
            onClick={() => { if (rec.recording) rec.stop(); else { onStart(); void rec.start(); } }}
            className={`state-layer relative z-10 flex size-24 items-center justify-center rounded-[32px] shadow-md transition-colors duration-300 ${rec.recording ? "bg-error text-on-error" : "bg-primary text-on-primary"}`}>
            <Icon name={rec.recording ? "stop" : "mic"} size={44} />
          </button>
        </div>
        <p aria-live="polite" className="type-title-l tnum text-on-surface">
          {rec.recording ? `${t.task.listening} ${Math.ceil(left / 1000)}s` : t.task.tapStart}
        </p>
      </Card>

      {DEV ? (
        <details className="rounded-2xl bg-warning-container p-4 text-on-warning-container">
          <summary className="type-title-m cursor-pointer">DEV ONLY: simulate what the model heard</summary>
          <div className="mt-3 space-y-2">
            {PRESETS.map((p) => (
              <Button key={p.label} variant="outlined" className="!min-h-12 !text-base !text-on-warning-container" onClick={() => { onStart(); onDev(p.text, p.o ?? {}); }}>{p.label}</Button>
            ))}
            <input ref={textRef} placeholder="or type a transcript, e.g. Neha ko sau rupaye bhej do" className="min-h-12 w-full rounded-xl border border-outline bg-surface px-3 text-base text-on-surface" />
            <Button className="!min-h-12 !text-base" onClick={() => { const v = textRef.current?.value.trim(); if (v) { onStart(); onDev(v, {}); } }}>Send</Button>
          </div>
        </details>
      ) : null}
    </Screen>
  );
}
