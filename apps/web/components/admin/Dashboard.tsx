"use client";
import { useCallback, useEffect, useMemo, useState, type ReactNode } from "react";
import { AdminError, adminDownload, adminGet, type Calibration, type Health, type Prop, type Quality, type RiskCoverage, type Summary } from "@/lib/adminApi";
import { Icon } from "@/components/ui";
import { ReliabilityChart, RiskCoverageChart } from "./Charts";

type Tab = "live" | "quality" | "risk" | "calibration" | "health";
const TABS: { id: Tab; label: string }[] = [
  { id: "live", label: "Live status" }, { id: "quality", label: "Quality" }, { id: "risk", label: "Risk and coverage" },
  { id: "calibration", label: "Calibration" }, { id: "health", label: "Data health" },
];
const pct = (x: number | null | undefined, d = 1) => (x == null ? "n/a" : `${(x * 100).toFixed(d)}%`);
const num = (x: number | null | undefined, d = 2) => (x == null ? "n/a" : x.toFixed(d));

function Panel({ title, n, children }: { title: string; n?: number; children: ReactNode }) {
  return (
    <section className="rounded-[28px] bg-surface-container-low p-6">
      <div className="mb-4 flex items-baseline justify-between gap-3">
        <h2 className="type-title-l text-on-surface">{title}</h2>
        {n !== undefined ? <span className="type-label-l rounded-full bg-secondary-container px-3 py-1 text-on-secondary-container">n = {n}</span> : null}
      </div>
      {children}
    </section>
  );
}
const Stat = ({ label, value, sub }: { label: string; value: ReactNode; sub?: string }) => (
  <div className="rounded-2xl bg-surface-container-high p-4">
    <p className="type-label-l text-on-surface-variant">{label}</p>
    <p className="tnum type-headline-m text-on-surface">{value}</p>
    {sub ? <p className="type-body-m text-on-surface-variant">{sub}</p> : null}
  </div>
);
const PropRow = ({ name, p, warn }: { name: string; p: Prop; warn?: boolean }) => (
  <tr className="border-t border-outline-variant">
    <td className="py-2 pr-3">{name}{warn ? <span className="ml-2 rounded-full bg-warning-container px-2 py-0.5 text-xs text-on-warning-container">10+ pts below average</span> : null}</td>
    <td className="tnum py-2 pr-3 text-right">{p.k}/{p.n}</td>
    <td className="tnum py-2 pr-3 text-right font-semibold">{pct(p.rate)}</td>
    <td className="tnum py-2 text-right text-on-surface-variant">{pct(p.lo)} to {pct(p.hi)}</td>
  </tr>
);

export default function Dashboard({ token, onSignOut }: { token: string; onSignOut: () => void }) {
  const [tab, setTab] = useState<Tab>("live");
  const [summary, setSummary] = useState<Summary | null>(null);
  const [quality, setQuality] = useState<Quality | null>(null);
  const [rc, setRc] = useState<RiskCoverage | null>(null);
  const [cal, setCal] = useState<Calibration | null>(null);
  const [health, setHealth] = useState<Health | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [sel, setSel] = useState<number | null>(null);
  const [bText, setBText] = useState("5");
  const [signal, setSignal] = useState("amount.combined");

  const load = useCallback(async () => {
    try {
      const [s, q, r, c, h] = await Promise.all([
        adminGet<Summary>("summary", token), adminGet<Quality>("quality", token), adminGet<RiskCoverage>("risk-coverage", token),
        adminGet<Calibration>("calibration", token), adminGet<Health>("health", token),
      ]);
      setSummary(s); setQuality(q); setRc(r); setCal(c); setHealth(h); setError(null);
    } catch (e) {
      setError(e instanceof AdminError ? e.message : "error");
    }
  }, [token]);
  useEffect(() => {
    const first = setTimeout(() => void load(), 0); // initial fetch, then poll every 15 s
    const id = setInterval(() => void load(), 15000);
    return () => { clearTimeout(first); clearInterval(id); };
  }, [load]);

  const liveIdx = useMemo(() => (rc ? Math.max(0, rc.curve.findIndex((p) => p.threshold === rc.live_delta)) : 0), [rc]);
  const idx = sel ?? liveIdx;
  const point = rc?.curve[idx];
  const bMax = /^\d+(\.\d+)?$/.test(bText) && Number(bText) > 0 && Number(bText) < 100 ? Number(bText) / 100 : null;
  const h2 = useMemo(() => {
    if (!rc || bMax === null) return null;
    const ok = rc.curve.filter((p) => p.n_fast > 0 && p.wilson_hi <= bMax);
    return ok.length ? ok.reduce((a, b) => (b.coverage > a.coverage || (b.coverage === a.coverage && b.threshold > a.threshold) ? b : a)) : null;
  }, [rc, bMax]);

  if (error) {
    return (
      <div className="mx-auto max-w-md p-6">
        <div role="alert" className="rounded-2xl bg-error-container p-4 text-on-error-container">
          <p className="type-title-m">{error === "bad_token" ? "That token was not accepted" : error === "admin_disabled" ? "Admin is disabled on this server (no ADMIN_TOKEN set)" : "Cannot reach the API"}</p>
          <button type="button" onClick={onSignOut} className="state-layer type-label-l mt-3 min-h-12 rounded-full border border-outline px-5">Back</button>
        </div>
      </div>
    );
  }
  if (!summary || !quality || !rc || !cal || !health) return <p role="status" className="p-8 text-on-surface-variant">Loading…</p>;

  const sig = cal.signals[signal];
  return (
    <div className="mx-auto max-w-5xl space-y-4 p-4 pb-16">
      {summary.synthetic ? (
        <div role="alert" className="rounded-2xl bg-error-container p-4 text-on-error-container">
          <p className="type-title-m flex items-center gap-2"><Icon name="warning" />SYNTHETIC DATA. Not results.</p>
          <p className="type-body-m">These rows come from the simulator (model = synthetic-sim). Never quote any number on this page.</p>
        </div>
      ) : null}
      <header className="flex flex-wrap items-center justify-between gap-3">
        <h1 className="type-headline-m">Vani-Guard admin</h1>
        <div className="flex gap-2">
          <button type="button" onClick={() => void adminDownload(token)} className="state-layer type-label-l inline-flex min-h-12 items-center gap-2 rounded-full bg-secondary-container px-5 text-on-secondary-container"><Icon name="download" size={20} />Export CSV</button>
          <button type="button" onClick={onSignOut} className="state-layer type-label-l min-h-12 rounded-full border border-outline px-5">Sign out</button>
        </div>
      </header>
      <nav role="tablist" aria-label="Dashboard sections" className="flex gap-1 overflow-x-auto rounded-full bg-surface-container p-1">
        {TABS.map((t) => (
          <button key={t.id} role="tab" type="button" aria-selected={tab === t.id} onClick={() => setTab(t.id)}
            className={`state-layer type-label-l min-h-12 shrink-0 rounded-full px-5 ${tab === t.id ? "bg-secondary-container text-on-secondary-container" : "text-on-surface-variant"}`}>{t.label}</button>
        ))}
      </nav>

      {tab === "live" ? (
        <div className="space-y-4">
          <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
            <Stat label="Participants started" value={summary.participants.started} sub={`${summary.participants.completed} completed`} />
            <Stat label="Commands logged" value={summary.commands.logged} sub={`${summary.commands.practice} practice, ${summary.commands.probes} probes`} />
            <Stat label="Errors, last hour" value={summary.errors_last_hour} />
            <Stat label="Spend today" value={`$${summary.spend.today_usd.toFixed(2)}`} sub={summary.spend.daily_cap_usd ? `cap $${summary.spend.daily_cap_usd}` : "no cap set (dev)"} />
          </div>
          <Panel title="Completion funnel" n={summary.participants.started}>
            <ul className="space-y-2">
              {summary.funnel.map((f) => (
                <li key={f.step} className="flex items-center gap-3">
                  <span className="type-label-l w-24 text-on-surface-variant">{f.step}</span>
                  <div className="h-6 flex-1 overflow-hidden rounded-full bg-surface-container-highest">
                    <div className="h-full rounded-full bg-primary" style={{ width: `${summary.participants.started ? (100 * f.sessions) / summary.participants.started : 0}%` }} />
                  </div>
                  <span className="tnum type-label-l w-10 text-right">{f.sessions}</span>
                </li>
              ))}
            </ul>
            <p className="type-body-m mt-3 text-on-surface-variant">Dropped out at: {Object.entries(summary.dropout_last_screen).map(([k, v]) => `${k} (${v})`).join(", ") || "nobody yet"}</p>
          </Panel>
          <div className="grid gap-4 md:grid-cols-2">
            <Panel title="What participants saw" n={summary.commands.logged}>
              <p className="type-body-l">Modes: {Object.entries(summary.modes).map(([k, v]) => `${k} ${v}`).join(" · ")}</p>
              <p className="type-body-l mt-1">Arms: {Object.entries(summary.arms).map(([k, v]) => `${k} ${v}`).join(" · ")}</p>
              <p className="type-body-l mt-1">Router tiers: {Object.entries(summary.tiers).map(([k, v]) => `${k} ${v}`).join(" · ")}</p>
            </Panel>
            <Panel title="Versions in force">
              <p className="type-body-l">router {summary.versions.router} · prompt {summary.versions.prompt} · app {summary.versions.app}</p>
            </Panel>
          </div>
        </div>
      ) : null}

      {tab === "quality" ? (
        <div className="space-y-4">
          <Panel title="Accuracy by field (95% Wilson interval)" n={quality.n}>
            <table className="type-body-m w-full"><tbody>{Object.entries(quality.fields).map(([k, p]) => <PropRow key={k} name={k === "all" ? "all three fields" : k} p={p} />)}</tbody></table>
          </Panel>
          <div className="grid gap-4 md:grid-cols-2">
            <Panel title="By condition" n={quality.n}>
              <table className="type-body-m w-full"><tbody>{Object.entries(quality.by_tag).map(([k, p]) => <PropRow key={k} name={k} p={p} warn={p.below_average_10pts} />)}</tbody></table>
            </Panel>
            <Panel title="By difficulty" n={quality.n}>
              <table className="type-body-m w-full"><tbody>{Object.entries(quality.by_difficulty).map(([k, p]) => <PropRow key={k} name={k} p={p} warn={p.below_average_10pts} />)}</tbody></table>
            </Panel>
          </div>
          <Panel title="Escalation precision" n={quality.escalation_precision.n}>
            <p className="type-body-l"><span className="type-headline-m tnum">{pct(quality.escalation_precision.rate)}</span> of escalated commands that had a parse were actually wrong ({pct(quality.escalation_precision.lo)} to {pct(quality.escalation_precision.hi)}). Low means needless extra taps.</p>
          </Panel>
          <Panel title="Latency (ms), target p95 at most 5000">
            <table className="type-body-m w-full"><thead><tr className="text-left text-on-surface-variant"><th className="py-1">stage</th><th className="text-right">p50</th><th className="text-right">p95</th></tr></thead>
              <tbody>{Object.entries(quality.latency_ms).map(([k, v]) => <tr key={k} className="border-t border-outline-variant"><td className="py-2">{k}</td><td className="tnum text-right">{num(v.p50, 0)}</td><td className="tnum text-right">{num(v.p95, 0)}</td></tr>)}</tbody></table>
          </Panel>
        </div>
      ) : null}

      {tab === "risk" ? (
        <div className="space-y-4">
          <Panel title="Fast-path coverage versus wrong-execution rate" n={rc.n}>
            <RiskCoverageChart curve={rc.curve} selected={idx} bMax={bMax} />
            <div className="mt-4 space-y-3">
              <label className="type-title-m block" htmlFor="delta">Replay threshold offset: {point ? point.threshold.toFixed(2) : "0.00"}{point?.threshold === rc.live_delta ? " (live router)" : ""}</label>
              <input id="delta" type="range" min={0} max={rc.curve.length - 1} value={idx} onChange={(e) => setSel(Number(e.target.value))} className="w-full accent-primary" aria-describedby="delta-help" />
              <p id="delta-help" className="type-body-m text-on-surface-variant">Replays logged confidences at a stricter (right) or looser (left) bar. No model calls. 0.00 is exactly what participants experienced.</p>
              {point ? (
                <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
                  <Stat label="Coverage" value={pct(point.coverage)} sub={`${point.n_fast} of ${point.n_total} commands`} />
                  <Stat label="Wrong execution" value={pct(point.wrong_rate)} sub={`${point.n_wrong} of ${point.n_fast}`} />
                  <Stat label="95% upper bound" value={pct(point.n_fast ? point.wilson_hi : null)} />
                  <Stat label="Safe fast-path rate" value={pct(point.safe_fast_rate)} sub="north star" />
                </div>
              ) : null}
              {point && !point.reliable ? <p className="type-body-m rounded-xl bg-warning-container p-3 text-on-warning-container">Unreliable: only {point.n_fast} fast-path commands here (under 30).</p> : null}
            </div>
          </Panel>
          <Panel title="Pre-registered H2 rule (preview)">
            <label htmlFor="b" className="type-body-l">Maximum acceptable wrong-execution rate B (Wilson 95% upper bound), %: </label>
            <input id="b" value={bText} onChange={(e) => setBText(e.target.value)} inputMode="decimal" className="tnum ml-2 w-20 rounded-xl border border-outline bg-surface p-2" />
            <p className="type-body-l mt-3">{bMax === null ? "Enter B between 0 and 100." : h2 ? <>Highest coverage meeting the rule: offset <b>{h2.threshold.toFixed(2)}</b> with coverage <b>{pct(h2.coverage)}</b> and upper bound {pct(h2.wilson_hi)} (n_fast {h2.n_fast}).</> : "No threshold meets this bound with the data so far."}</p>
            <p className="type-body-m mt-1 text-on-surface-variant">Preview only. The reported result comes from held-out folds in `make analyze`.</p>
          </Panel>
          <Panel title="Routed versus always-confirm" n={rc.arms.routed.n + rc.arms.always_confirm.n}>
            <table className="type-body-m w-full"><thead><tr className="text-left text-on-surface-variant"><th className="py-1">arm</th><th className="text-right">n</th><th className="text-right">median taps</th><th className="text-right">median time (s)</th><th className="text-right">wrong at payment</th></tr></thead>
              <tbody>{(["routed", "always_confirm"] as const).map((k) => (
                <tr key={k} className="border-t border-outline-variant"><td className="py-2">{k}</td><td className="tnum text-right">{rc.arms[k].n}</td><td className="tnum text-right">{num(rc.arms[k].median_taps, 0)}</td>
                  <td className="tnum text-right">{rc.arms[k].median_time_ms == null ? "n/a" : (rc.arms[k].median_time_ms / 1000).toFixed(1)}</td><td className="tnum text-right">{pct(rc.arms[k].wrong_final.rate)} ({rc.arms[k].wrong_final.k}/{rc.arms[k].wrong_final.n})</td></tr>))}</tbody></table>
          </Panel>
        </div>
      ) : null}

      {tab === "calibration" ? (
        <Panel title="Reliability diagram and ECE per signal" n={sig?.n ?? 0}>
          <label htmlFor="sig" className="type-body-l">Signal: </label>
          <select id="sig" value={signal} onChange={(e) => setSignal(e.target.value)} className="rounded-xl border border-outline bg-surface p-2">
            {Object.keys(cal.signals).map((k) => <option key={k} value={k}>{k}</option>)}
          </select>
          {sig ? (
            <div className="mt-4 grid gap-4 md:grid-cols-2">
              <ReliabilityChart signal={sig} />
              <div className="grid grid-cols-3 content-start gap-3">
                <Stat label="ECE (10 bins)" value={num(sig.ece, 3)} /><Stat label="Brier" value={num(sig.brier, 3)} /><Stat label="AUROC" value={num(sig.auroc, 3)} />
                <p className="type-body-m col-span-3 text-on-surface-variant">Validator scores are not probabilities, so their ECE is not meaningful; read their AUROC.</p>
              </div>
            </div>
          ) : null}
        </Panel>
      ) : null}

      {tab === "health" ? (
        <div className="grid gap-4 md:grid-cols-2">
          <Panel title="Missing fields" n={health.n_commands}>
            <ul className="type-body-l space-y-1">{Object.entries(health.missing).map(([k, v]) => <li key={k} className="flex justify-between"><span>{k.replaceAll("_", " ")}</span><span className="tnum font-semibold">{v}</span></li>)}</ul>
          </Panel>
          <Panel title="Integrity">
            <p className="type-body-l">Duplicate submissions: <b>{health.duplicate_requests}</b></p>
            <p className="type-body-l mt-1">Sessions with no study commands: <b>{health.sessions_without_study_commands}</b></p>
            <p className="type-body-l mt-1">Error codes: {Object.entries(health.error_codes).map(([k, v]) => `${k} ${v}`).join(", ") || "none"}</p>
          </Panel>
          <Panel title="Versions seen (should be exactly one of each mid-study)">
            {Object.entries(health.versions_seen).map(([k, v]) => (
              <p key={k} className="type-body-l">{k}: {Object.entries(v).map(([a, b]) => `${a} (${b})`).join(", ")}{Object.keys(v).length > 1 ? "  <- mixed versions" : ""}</p>
            ))}
          </Panel>
        </div>
      ) : null}
    </div>
  );
}
