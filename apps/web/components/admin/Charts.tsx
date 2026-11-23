import type { RCPoint, Signal } from "@/lib/adminApi";

const W = 640, H = 340, M = { l: 52, r: 16, t: 16, b: 44 };
const pct = (x: number, d = 0) => `${(x * 100).toFixed(d)}%`;

function Axes({ yMax, yLabel, xLabel }: { yMax: number; yLabel: string; xLabel: string }) {
  const x = (v: number) => M.l + v * (W - M.l - M.r);
  const y = (v: number) => H - M.b - (v / yMax) * (H - M.t - M.b);
  const yt = [0, 0.25, 0.5, 0.75, 1].map((f) => f * yMax);
  return (
    <g className="text-on-surface-variant" fontSize="12">
      {[0, 0.25, 0.5, 0.75, 1].map((v) => (
        <g key={v}><line x1={x(v)} x2={x(v)} y1={M.t} y2={H - M.b} stroke="var(--md-sys-color-outline-variant)" strokeOpacity={0.5} />
          <text x={x(v)} y={H - M.b + 18} textAnchor="middle" fill="currentColor">{pct(v)}</text></g>
      ))}
      {yt.map((v) => (
        <g key={v}><line x1={M.l} x2={W - M.r} y1={y(v)} y2={y(v)} stroke="var(--md-sys-color-outline-variant)" strokeOpacity={0.5} />
          <text x={M.l - 8} y={y(v) + 4} textAnchor="end" fill="currentColor">{pct(v, v < 0.1 ? 1 : 0)}</text></g>
      ))}
      <text x={(M.l + W - M.r) / 2} y={H - 6} textAnchor="middle" fill="currentColor">{xLabel}</text>
      <text transform={`translate(14 ${(M.t + H - M.b) / 2}) rotate(-90)`} textAnchor="middle" fill="currentColor">{yLabel}</text>
    </g>
  );
}

/** Wrong-execution rate (with 95% Wilson band) against fast-path coverage. Hollow points have n_fast < 30. */
export function RiskCoverageChart({ curve, selected, bMax }: { curve: RCPoint[]; selected: number; bMax: number | null }) {
  const pts = curve.filter((p) => p.n_fast > 0 && p.wrong_rate !== null).sort((a, b) => a.coverage - b.coverage);
  const yMax = Math.min(1, Math.max(0.1, Math.ceil(Math.max(0, ...pts.map((p) => p.wilson_hi)) * 20) / 20));
  const x = (v: number) => M.l + v * (W - M.l - M.r);
  const y = (v: number) => H - M.b - (v / yMax) * (H - M.t - M.b);
  const band = [...pts.map((p) => `${x(p.coverage)},${y(p.wilson_hi)}`), ...[...pts].reverse().map((p) => `${x(p.coverage)},${y(p.wilson_lo)}`)].join(" ");
  const sel = curve[selected];
  return (
    <svg viewBox={`0 0 ${W} ${H}`} role="img" className="w-full" aria-label={`Risk-coverage curve. At the selected threshold, coverage ${pct(sel?.coverage ?? 0, 1)} and wrong-execution rate ${sel?.wrong_rate == null ? "undefined" : pct(sel.wrong_rate, 1)}.`}>
      <Axes yMax={yMax} yLabel="Wrong-execution rate" xLabel="Fast-path coverage (share of all commands)" />
      {pts.length > 1 ? <polygon points={band} fill="var(--md-sys-color-primary)" fillOpacity={0.16} /> : null}
      <polyline points={pts.map((p) => `${x(p.coverage)},${y(p.wrong_rate ?? 0)}`).join(" ")} fill="none" stroke="var(--md-sys-color-primary)" strokeWidth={2.5} />
      {pts.map((p) => (
        <circle key={p.threshold} cx={x(p.coverage)} cy={y(p.wrong_rate ?? 0)} r={3.5} fill={p.reliable ? "var(--md-sys-color-primary)" : "var(--md-sys-color-surface)"} stroke="var(--md-sys-color-primary)" strokeWidth={1.5}>
          <title>{`offset ${p.threshold.toFixed(2)}: n_fast=${p.n_fast}, coverage ${pct(p.coverage, 1)}, wrong ${p.n_wrong} (${pct(p.wrong_rate ?? 0, 1)}), 95% upper ${pct(p.wilson_hi, 1)}${p.reliable ? "" : " (unreliable: n<30)"}`}</title>
        </circle>
      ))}
      {bMax !== null && bMax <= yMax ? (
        <g><line x1={M.l} x2={W - M.r} y1={y(bMax)} y2={y(bMax)} stroke="var(--md-sys-color-error)" strokeDasharray="6 4" strokeWidth={1.5} />
          <text x={W - M.r - 4} y={y(bMax) - 6} textAnchor="end" fontSize="12" fill="var(--md-sys-color-error)">B = {pct(bMax, 1)}</text></g>
      ) : null}
      {sel && sel.n_fast > 0 && sel.wrong_rate !== null ? (
        <g><circle cx={x(sel.coverage)} cy={y(sel.wrong_rate)} r={9} fill="none" stroke="var(--md-sys-color-tertiary)" strokeWidth={3} />
          <line x1={x(sel.coverage)} x2={x(sel.coverage)} y1={y(sel.wilson_lo)} y2={y(sel.wilson_hi)} stroke="var(--md-sys-color-tertiary)" strokeWidth={3} /></g>
      ) : null}
      <g><rect x={x(0) - 6} y={y(0) - 6} width={12} height={12} rx={3} fill="var(--md-sys-color-secondary)"><title>Always-confirm baseline: nobody gets the one-tap path (coverage 0%)</title></rect>
        <text x={x(0) + 12} y={y(0) - 10} fontSize="12" fill="var(--md-sys-color-secondary)">always-confirm</text></g>
    </svg>
  );
}

/** Reliability diagram: mean confidence vs observed accuracy per bin; dot size shows n. */
export function ReliabilityChart({ signal }: { signal: Signal }) {
  const S = 320, m = 40;
  const x = (v: number) => m + v * (S - m - 12);
  const y = (v: number) => S - m - v * (S - m - 12);
  const maxN = Math.max(1, ...signal.bins.map((b) => b.n));
  return (
    <svg viewBox={`0 0 ${S} ${S}`} role="img" className="mx-auto w-full max-w-sm" aria-label="Reliability diagram">
      {[0, 0.25, 0.5, 0.75, 1].map((v) => (
        <g key={v} fontSize="11" className="text-on-surface-variant">
          <line x1={x(v)} x2={x(v)} y1={y(0)} y2={y(1)} stroke="var(--md-sys-color-outline-variant)" strokeOpacity={0.5} />
          <line x1={x(0)} x2={x(1)} y1={y(v)} y2={y(v)} stroke="var(--md-sys-color-outline-variant)" strokeOpacity={0.5} />
          <text x={x(v)} y={S - m + 16} textAnchor="middle" fill="currentColor">{v * 100}</text>
          <text x={m - 6} y={y(v) + 4} textAnchor="end" fill="currentColor">{v * 100}</text>
        </g>
      ))}
      <line x1={x(0)} y1={y(0)} x2={x(1)} y2={y(1)} stroke="var(--md-sys-color-outline)" strokeDasharray="5 4" />
      <polyline fill="none" stroke="var(--md-sys-color-primary)" strokeWidth={2} points={signal.bins.map((b) => `${x(b.mean_conf)},${y(b.accuracy)}`).join(" ")} />
      {signal.bins.map((b) => (
        <circle key={b.bin} cx={x(b.mean_conf)} cy={y(b.accuracy)} r={4 + 8 * Math.sqrt(b.n / maxN)} fill="var(--md-sys-color-primary)" fillOpacity={0.55}>
          <title>{`bin ${b.bin}: n=${b.n}, mean confidence ${pct(b.mean_conf, 0)}, accuracy ${pct(b.accuracy, 0)}`}</title>
        </circle>
      ))}
      <text x={S / 2} y={S - 4} textAnchor="middle" fontSize="11" fill="var(--md-sys-color-on-surface-variant)">Confidence (%)</text>
      <text transform={`translate(10 ${S / 2}) rotate(-90)`} textAnchor="middle" fontSize="11" fill="var(--md-sys-color-on-surface-variant)">Accuracy (%)</text>
    </svg>
  );
}
