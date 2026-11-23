"use client";
import { useEffect, useState } from "react";
import { getMicStream, inAppBrowser, micSupported, useLevel } from "@/lib/recorder";
import { usePageFact } from "@/lib/store";
import type { Strings } from "@/lib/i18n";
import { Button, Card, Heading, Icon, Notice, Screen } from "./ui";

type State = "idle" | "granted" | "denied";

export function MicSetup({ t, onReady, onEvent }: { t: Strings; onReady: () => void; onEvent: (type: string) => void }) {
  const [state, setState] = useState<State>("idle");
  const [stream, setStream] = useState<MediaStream | null>(null);
  const [copied, setCopied] = useState(false);
  const inApp = usePageFact(inAppBrowser);
  const unsupported = usePageFact(() => !micSupported());
  const { level, peak } = useLevel(stream);
  const heard = peak > 0.12;

  useEffect(() => {
    if (unsupported) onEvent("mic_unsupported");
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [unsupported]);

  async function allow() {
    try {
      setStream(await getMicStream());
      setState("granted");
      onEvent("mic_granted");
    } catch {
      setState("denied");
      onEvent("mic_denied");
    }
  }
  async function copy() {
    try {
      await navigator.clipboard.writeText(window.location.href);
      setCopied(true);
    } catch {}
  }

  const m = t.mic;
  return (
    <Screen>
      <Card>
        <Heading icon="mic" sub={m.why}>{m.title}</Heading>
        {inApp || unsupported ? (
          <div className="mb-4 space-y-3">
            <Notice tone="warn" title={unsupported ? m.unsupported : m.inApp} />
            <Button variant="outlined" icon="content_copy" onClick={copy}>{copied ? m.copied : m.copyLink}</Button>
          </div>
        ) : null}
        {state === "denied" ? (
          <div className="space-y-3">
            <Notice tone="error" title={m.deniedTitle}>{m.deniedSteps}</Notice>
            <Button icon="refresh" onClick={allow}>{m.tryAgain}</Button>
          </div>
        ) : null}
        {state === "idle" && !unsupported ? <Button icon="mic" onClick={allow}>{m.allow}</Button> : null}
        {state === "granted" ? (
          <div className="space-y-5">
            <p className="type-title-l text-on-surface">{m.sayIt}</p>
            <div role="progressbar" aria-label={t.task.mic} aria-valuemin={0} aria-valuemax={100} aria-valuenow={Math.round(level * 100)} className="h-3 w-full overflow-hidden rounded-full bg-surface-container-highest">
              <div className="h-full rounded-full bg-primary transition-[width] duration-75" style={{ width: `${Math.round(level * 100)}%` }} />
            </div>
            <p aria-live="polite" className={`type-title-m flex items-center gap-2 ${heard ? "text-success" : "text-on-surface-variant"}`}>
              {heard ? <Icon name="check_circle" size={22} /> : null}
              {heard ? m.hearing : m.quiet}
            </p>
            <Button icon="arrow_forward" onClick={onReady}>{m.next}</Button>
          </div>
        ) : null}
      </Card>
    </Screen>
  );
}
