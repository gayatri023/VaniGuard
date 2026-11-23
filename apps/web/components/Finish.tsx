"use client";
import { useState } from "react";
import type { Strings } from "@/lib/i18n";
import { Button, Card, Heading, Notice, Screen } from "./ui";

export function Survey({ t, busy, onSubmit }: { t: Strings; busy: boolean; onSubmit: (a: [number, number, number], free: string) => void }) {
  const [a, setA] = useState<(number | null)[]>([null, null, null]);
  const [free, setFree] = useState("");
  const ready = a.every((x) => x !== null) && !busy;
  return (
    <Screen>
      <Card tone="high" className="space-y-7">
        <Heading icon="query_stats">{t.survey.title}</Heading>
        {t.survey.q.map((q, i) => (
          <fieldset key={q}>
            <legend className="type-title-m mb-3 text-on-surface">{q}</legend>
            <div className="flex gap-2" role="radiogroup" aria-label={q}>
              {[1, 2, 3, 4, 5].map((n) => (
                <label key={n} className={`state-layer flex min-h-14 flex-1 cursor-pointer items-center justify-center rounded-2xl border type-title-l has-[:focus-visible]:outline-3 has-[:focus-visible]:outline-primary ${a[i] === n ? "border-transparent bg-primary text-on-primary" : "border-outline text-on-surface"}`}>
                  <input type="radio" className="sr-only" name={`q${i}`} checked={a[i] === n} onChange={() => setA((p) => p.map((v, j) => (j === i ? n : v)))} />
                  {n}
                </label>
              ))}
            </div>
            <div className="type-body-m mt-2 flex justify-between text-on-surface-variant"><span>1 {t.survey.lo}</span><span>5 {t.survey.hi}</span></div>
          </fieldset>
        ))}
        <div>
          <label htmlFor="free" className="type-title-m mb-2 block text-on-surface">{t.survey.free}</label>
          <textarea id="free" rows={3} maxLength={500} value={free} onChange={(e) => setFree(e.target.value)} className="type-body-l w-full rounded-2xl border border-outline bg-surface p-3 text-on-surface" />
        </div>
      </Card>
      <Button icon="check" disabled={!ready} onClick={() => ready && onSubmit(a as [number, number, number], free.trim())}>{t.survey.submit}</Button>
    </Screen>
  );
}

export function End({ t, code, probes, onDelete }: { t: Strings; code: string; probes: boolean; onDelete: () => Promise<boolean> }) {
  const [copied, setCopied] = useState(false);
  const [confirming, setConfirming] = useState(false);
  const [deleted, setDeleted] = useState(false);
  async function copy() {
    try { await navigator.clipboard.writeText(code); setCopied(true); } catch {}
  }
  async function share() {
    const url = typeof window !== "undefined" ? window.location.origin : "";
    try {
      if (navigator.share) await navigator.share({ text: t.end.shareText, url });
      else await navigator.clipboard.writeText(`${t.end.shareText} ${url}`);
    } catch {}
  }
  if (deleted) return <Screen><Card><Notice tone="ok" title={t.end.deleted} /></Card></Screen>;
  return (
    <Screen>
      <Card tone="high" className="space-y-5">
        <Heading icon="check_circle" sub={t.end.body}>{t.end.title}</Heading>
        <div className="rounded-2xl bg-primary-container p-5 text-center text-on-primary-container">
          <p className="type-label-l uppercase opacity-80">{t.end.codeTitle}</p>
          <p className="mt-1 font-mono text-4xl font-bold tracking-[0.2em]" aria-label={code.split("").join(" ")}>{code}</p>
        </div>
        <p className="type-body-l text-on-surface-variant">{t.end.codeHelp}</p>
        <Button variant="tonal" icon={copied ? "check" : "content_copy"} onClick={copy}>{copied ? "\u2713" : t.end.copy}</Button>
        <Button icon="share" onClick={share}>{t.end.share}</Button>
      </Card>
      <Card tone="low">
        <h2 className="type-title-l text-on-surface">{t.end.debrief}</h2>
        <p className="type-body-l mt-2 text-on-surface-variant">{t.end.debriefBody}{probes ? t.end.debriefProbes : ""}</p>
      </Card>
      <Card tone="outlined" className="space-y-3">
        {confirming ? <p className="type-title-m text-on-surface">{t.end.deleting}</p> : null}
        <Button variant={confirming ? "filled" : "text"} icon="delete" className={confirming ? "!bg-error !text-on-error" : "!text-error"}
          onClick={async () => { if (!confirming) return setConfirming(true); if (await onDelete()) setDeleted(true); }}>
          {confirming ? t.end.deleteYes : t.end.del}
        </Button>
      </Card>
    </Screen>
  );
}

export function SystemNotice({ t, kind, onRetry }: { t: Strings; kind: "paused" | "error" | "network" | "limit"; onRetry?: () => void }) {
  const m = t.sys[kind];
  return (
    <Screen>
      <Card tone="high" className="space-y-4">
        <Notice tone={kind === "paused" || kind === "limit" ? "info" : "error"} title={m.t}>{m.b}</Notice>
        {onRetry && kind !== "paused" && kind !== "limit" ? <Button icon="refresh" onClick={onRetry}>{t.sys.retry}</Button> : null}
      </Card>
    </Screen>
  );
}
