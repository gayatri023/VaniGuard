"use client";
import { useState } from "react";
import type { Strings } from "@/lib/i18n";
import { Button, Card, Heading, Icon, InfoRow, Notice, Screen } from "./ui";

export interface ConsentChoice { comfort: "hindi_dominant" | "english_dominant" | "balanced"; noise: "quiet" | "some" | "noisy" }

function Radios<T extends string>({ legend, value, options, onChange }: { legend: string; value: T | null; options: Record<T, string>; onChange: (v: T) => void }) {
  return (
    <fieldset className="mt-6">
      <legend className="type-title-m mb-3 text-on-surface">{legend}</legend>
      <div className="grid gap-2">
        {(Object.keys(options) as T[]).map((k) => (
          <label key={k} className={`state-layer flex min-h-14 cursor-pointer items-center gap-3 rounded-2xl border px-4 has-[:focus-visible]:outline-3 has-[:focus-visible]:outline-primary ${value === k ? "border-primary bg-secondary-container text-on-secondary-container" : "border-outline-variant text-on-surface"}`}>
            <input type="radio" name={legend} checked={value === k} onChange={() => onChange(k)} className="sr-only" />
            <span aria-hidden className={`flex size-5 items-center justify-center rounded-full border-2 ${value === k ? "border-primary" : "border-outline"}`}>
              {value === k ? <span className="size-2.5 rounded-full bg-primary" /> : null}
            </span>
            <span className="type-body-l">{options[k]}</span>
          </label>
        ))}
      </div>
    </fieldset>
  );
}

export function Consent({ t, busy, error, probes, onStart }: { t: Strings; busy: boolean; error: boolean; probes: boolean; onStart: (c: ConsentChoice) => void }) {
  const c = t.consent;
  const [agree, setAgree] = useState(false);
  const [comfort, setComfort] = useState<ConsentChoice["comfort"] | null>(null);
  const [noise, setNoise] = useState<ConsentChoice["noise"] | null>(null);
  const ready = agree && comfort && noise && !busy;
  return (
    <Screen>
      <Card>
        <Heading icon="payments" sub={c.what}>{c.title}</Heading>
        <div className="mt-2 space-y-5">
          <InfoRow icon="mic" title={c.recordTitle}>{c.record}</InfoRow>
          <InfoRow icon="shield" title={c.notTitle}>{c.notCollect}</InfoRow>
          <InfoRow icon="volume_up" title="Audio">{c.audio}</InfoRow>
          <InfoRow icon="tune" title="Your control">{c.quit}</InfoRow>
          {probes ? <InfoRow icon="visibility" title="Attention check">{c.probes}</InfoRow> : null}
        </div>
      </Card>
      <Card tone="outlined">
        <Radios legend={c.comfort} value={comfort} options={c.comfortOpts} onChange={setComfort} />
        <Radios legend={c.noise} value={noise} options={c.noiseOpts} onChange={setNoise} />
        <label className="mt-6 flex min-h-14 cursor-pointer items-start gap-3 has-[:focus-visible]:outline-3 has-[:focus-visible]:outline-primary">
          <input type="checkbox" checked={agree} onChange={(e) => setAgree(e.target.checked)} className="sr-only" />
          <span aria-hidden className={`mt-0.5 flex size-6 shrink-0 items-center justify-center rounded-md border-2 ${agree ? "border-primary bg-primary text-on-primary" : "border-outline"}`}>
            {agree ? <Icon name="check" size={18} /> : null}
          </span>
          <span className="type-body-l text-on-surface">{c.check}</span>
        </label>
        {error ? <div className="mt-4"><Notice tone="error" title={t.sys.error.t}>{t.sys.error.b}</Notice></div> : null}
        <div className="mt-6">
          <Button icon="arrow_forward" disabled={!ready} onClick={() => comfort && noise && onStart({ comfort, noise })}>{c.start}</Button>
        </div>
      </Card>
    </Screen>
  );
}
