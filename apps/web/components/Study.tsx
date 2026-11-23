"use client";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { api, ApiError, type CommandInput } from "@/lib/api";
import { deviceInfo, uid } from "@/lib/device";
import { STRINGS, useLang } from "@/lib/i18n";
import { releaseMic, type Recording } from "@/lib/recorder";
import { useStored, writeStored } from "@/lib/store";
import type { ActionBody, Chip, CommandResult, Contact, DevOverrides, NextCard, PublicConfig, SessionInfo } from "@/lib/types";
import { Consent, type ConsentChoice } from "./Consent";
import { End, Survey, SystemNotice } from "./Finish";
import { MicSetup } from "./MicSetup";
import { Confirm, ConfirmAll, Manual, Processing, Success, TierB, TierC } from "./Results";
import { Shell } from "./Shell";
import { Task } from "./Task";
import { Card, Notice, Screen } from "./ui";

type Screen = "consent" | "mic" | "loading" | "task" | "processing" | "result" | "manual" | "success" | "survey" | "end" | "notice";
type NoticeKind = "paused" | "error" | "network" | "limit";
const HARD_TIMEOUT_MS = 12000;

export default function Study() {
  const [lang, toggleLang] = useLang();
  const t = STRINGS[lang];
  const savedRaw = useStored("vg_session");
  const saved = useMemo<SessionInfo | null>(() => {
    try { return savedRaw ? (JSON.parse(savedRaw) as SessionInfo) : null; } catch { return null; }
  }, [savedRaw]);
  const [created, setCreated] = useState<SessionInfo | null>(null);
  const session = created ?? saved;
  const [screenState, setScreen] = useState<Screen | null>(null);
  const screen: Screen = screenState ?? (session ? "mic" : "consent"); // a saved session resumes at the mic check
  const [card, setCard] = useState<NextCard | null>(null);
  const [result, setResult] = useState<CommandResult | null>(null);
  const [contacts, setContacts] = useState<Contact[]>([]);
  const [notice, setNotice] = useState<NoticeKind>("error");
  const [retries, setRetries] = useState(0);
  const [busy, setBusy] = useState(false);
  const [consentError, setConsentError] = useState(false);
  const [cfg, setCfg] = useState<PublicConfig | null>(null);
  const [manualFrom, setManualFrom] = useState<"edit" | "manual">("manual");

  const pending = useRef<CommandInput | null>(null);
  const abort = useRef<AbortController | null>(null);
  // taps = button presses from the moment the result is shown (chip, Pay, Edit, contact pick); typing an amount counts as one.
  const tm = useRef({ cardShown: 0, micStart: 0, resultShown: 0, taps: 0 });
  const sid = session?.id;
  const probes = cfg?.probes_enabled ?? false;

  useEffect(() => {
    api.config().then(setCfg).catch(() => undefined);
  }, []);

  const event = useCallback((type: string, payload: Record<string, unknown> = {}) => {
    if (sid) void api.event(sid, type, payload);
  }, [sid]);

  useEffect(() => {
    if (sid) event("screen_view", { screen });
  }, [screen, sid, event]);

  const failWith = useCallback((e: unknown) => {
    const code = e instanceof ApiError ? e.code : "network";
    setNotice(code === "study_paused" ? "paused" : code === "session_limit" ? "limit" : code === "network" ? "network" : "error");
    setScreen("notice");
  }, []);

  const loadCard = useCallback(async () => {
    if (!sid) return;
    setScreen("loading");
    try {
      const nc = await api.nextCard(sid);
      if (nc.done) return setScreen("survey");
      setCard(nc);
      setRetries(0);
      tm.current = { cardShown: performance.now(), micStart: 0, resultShown: 0, taps: 0 };
      setScreen("task");
    } catch (e) {
      if (e instanceof ApiError && e.status === 404) {
        writeStored("vg_session", null);
        setCreated(null);
        return setScreen("consent");
      }
      failWith(e);
    }
  }, [sid, failWith]);

  async function startSession(c: ConsentChoice) {
    setBusy(true);
    setConsentError(false);
    try {
      const r = await api.createSession({ consent_version: cfg?.consent_version ?? "v2", language_comfort: c.comfort, noise_self_report: c.noise, ...deviceInfo() });
      const s = { id: r.session_id, code: r.deletion_code };
      writeStored("vg_session", JSON.stringify(s));
      setCreated(s);
      setScreen("mic");
    } catch (e) {
      if (e instanceof ApiError && e.code === "study_paused") { setNotice("paused"); setScreen("notice"); } else setConsentError(true);
    } finally {
      setBusy(false);
    }
  }

  const submit = useCallback(async (input: CommandInput) => {
    pending.current = input;
    setScreen("processing");
    const ctrl = new AbortController();
    abort.current = ctrl;
    const timer = setTimeout(() => ctrl.abort(), HARD_TIMEOUT_MS);
    try {
      const r = await api.postCommand(input, ctrl.signal);
      tm.current.resultShown = performance.now();
      tm.current.taps = 0;
      setResult(r);
      setScreen("result");
    } catch (e) {
      if (abort.current !== ctrl) return; // user cancelled
      if (ctrl.signal.aborted) { event("processing_timeout"); return failWith(new ApiError(0, "network")); }
      failWith(e);
    } finally {
      clearTimeout(timer);
    }
  }, [event, failWith]);

  const onRecorded = useCallback((r: Recording) => {
    if (!sid || !card?.card) return;
    void submit({ sessionId: sid, cardId: card.card.card_id, requestId: uid(), audio: { blob: r.blob, mime: r.mime, ms: r.ms } });
  }, [sid, card, submit]);

  const onDev = (transcript: string, overrides: DevOverrides) => {
    if (!sid || !card?.card) return;
    void submit({ sessionId: sid, cardId: card.card.card_id, requestId: uid(), dev: { transcript, overrides } });
  };

  function cancelProcessing() {
    const c = abort.current;
    abort.current = null;
    c?.abort();
    setScreen("task");
  }

  async function act(body: Omit<ActionBody, "taps_count" | "time_to_mic_ms" | "time_result_to_action_ms" | "time_to_complete_ms">): Promise<boolean> {
    if (!result) return false;
    const now = performance.now();
    const m = tm.current;
    try {
      await api.postAction(result.cmd_id, {
        ...body,
        taps_count: m.taps,
        time_to_mic_ms: m.micStart ? Math.round(m.micStart - m.cardShown) : null,
        time_result_to_action_ms: Math.round(now - m.resultShown),
        time_to_complete_ms: Math.round(now - m.cardShown),
      });
      return true;
    } catch (e) {
      failWith(e);
      return false;
    }
  }
  const tap = () => { tm.current.taps += 1; };

  async function pay(chip?: Chip, field?: "payee" | "amount") {
    tap();
    if (await act({ action: "pay", chip_field: field, chip_value: chip?.value })) setScreen("success");
  }
  async function retry() {
    tap();
    if (await act({ action: "retry" })) { setRetries((n) => n + 1); tm.current.micStart = 0; setScreen("task"); }
  }
  function openManual(from: "edit" | "manual") { tap(); setManualFrom(from); setScreen("manual"); }
  async function submitManual(payee: string, amount: number) {
    tap();
    if (await act({ action: manualFrom, final_payee_id: payee, final_amount: amount })) setScreen("success");
  }
  async function openContactsThenManual(from: "edit" | "manual") {
    if (!contacts.length) { try { setContacts(await api.contacts()); } catch (e) { return failWith(e); } }
    openManual(from);
  }

  async function submitSurvey(a: [number, number, number], free: string) {
    if (!sid) return;
    setBusy(true);
    try {
      await api.survey(sid, { trust_amount: a[0], low_effort: a[1], would_use: a[2], free_text: free || undefined });
      releaseMic();
      setCreated(session); // keep the deletion code on screen after the saved copy is cleared
      writeStored("vg_session", null);
      setScreen("end");
    } catch (e) {
      if (e instanceof ApiError && e.code === "already_submitted") setScreen("end");
      else failWith(e);
    } finally { setBusy(false); }
  }

  async function deleteMyData(): Promise<boolean> {
    if (!session) return false;
    try { await api.deleteSession(session.id, session.code); return true; } catch { return false; }
  }

  const f = result?.fields;
  return (
    <Shell t={t} onLang={toggleLang}>
      {screen === "consent" && <Consent t={t} busy={busy} error={consentError} probes={probes} onStart={startSession} />}
      {screen === "mic" && <MicSetup t={t} onReady={loadCard} onEvent={event} />}
      {screen === "loading" && <Screen><Card className="py-12 text-center"><p role="status" className="type-title-m text-on-surface-variant">{"\u2026"}</p></Card></Screen>}
      {screen === "task" && card?.card && (
        <Task t={t} card={card.card} index={card.index} total={card.total}
          onStart={() => { tm.current.micStart = performance.now(); event("recording_started"); }}
          onRecorded={onRecorded} onDev={onDev}
          onMicError={(e) => { event("mic_denied", { error: e }); setNotice("error"); setScreen("notice"); }} />
      )}
      {screen === "processing" && <Processing t={t} onCancel={cancelProcessing} onSlow={() => event("processing_slow")} />}
      {screen === "result" && result?.mode === "fast" && f?.payee && f.amount != null && (
        <Confirm t={t} payee={f.payee.name} amount={f.amount} note={f.note} onPay={() => pay()} onEdit={() => openContactsThenManual("edit")} />
      )}
      {screen === "result" && result?.mode === "confirm_all" && f?.payee && f.amount != null && (
        <ConfirmAll key={result.cmd_id} t={t} payee={f.payee.name} amount={f.amount} note={f.note} onTap={tap} onPay={() => pay()} onEdit={() => openContactsThenManual("edit")} />
      )}
      {screen === "result" && result?.mode === "verify" && <TierB key={result.cmd_id} t={t} result={result} onPay={pay} onTap={tap} onElse={() => openContactsThenManual("manual")} />}
      {screen === "result" && result && (result.mode === "retry" || (result.mode !== "verify" && !(f?.payee && f.amount != null))) && (
        <TierC t={t} retries={retries} onRetry={retry} onManual={() => openContactsThenManual("manual")} />
      )}
      {screen === "manual" && (
        <Manual t={t} contacts={contacts} initialPayee={manualFrom === "edit" ? f?.payee?.id : null} initialAmount={manualFrom === "edit" ? f?.amount : null}
          onSubmit={submitManual} onTap={tap} onBack={() => setScreen("result")} />
      )}
      {screen === "success" && <Success t={t} onNext={loadCard} />}
      {screen === "survey" && <Survey t={t} busy={busy} onSubmit={submitSurvey} />}
      {screen === "end" && session && <End t={t} code={session.code} probes={probes} onDelete={deleteMyData} />}
      {screen === "notice" && (
        <SystemNotice t={t} kind={notice}
          onRetry={() => (pending.current && screen === "notice" && notice === "network" ? void submit(pending.current) : void loadCard())} />
      )}
      {result?.debug && screen === "result" ? (
        <div className="mt-4"><Notice tone="warn" title="DEV debug (never shown in production)"><pre className="overflow-x-auto text-xs">{JSON.stringify(result.debug, null, 1)}</pre></Notice></div>
      ) : null}
    </Shell>
  );
}
