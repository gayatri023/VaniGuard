import type { ButtonHTMLAttributes, ReactNode } from "react";
import { ICONS, type IconName } from "./icons";
import { amountInWords, initials, inr } from "@/lib/format";

export function Icon({ name, size = 24, className = "" }: { name: IconName; size?: number; className?: string }) {
  return (
    <svg aria-hidden viewBox="0 -960 960 960" width={size} height={size} fill="currentColor" className={`shrink-0 ${className}`}>
      <path d={ICONS[name]} />
    </svg>
  );
}

type Variant = "filled" | "tonal" | "outlined" | "text";
const BTN: Record<Variant, string> = {
  filled: "bg-primary text-on-primary shadow-sm disabled:bg-on-surface/12 disabled:text-on-surface/38 disabled:shadow-none",
  tonal: "bg-secondary-container text-on-secondary-container disabled:bg-on-surface/12 disabled:text-on-surface/38",
  outlined: "border border-outline text-primary disabled:border-on-surface/12 disabled:text-on-surface/38",
  text: "text-primary disabled:text-on-surface/38",
};

export function Button({ variant = "filled", icon, className = "", children, ...p }: ButtonHTMLAttributes<HTMLButtonElement> & { variant?: Variant; icon?: IconName }) {
  return (
    <button type="button" {...p}
      className={`state-layer inline-flex min-h-14 w-full items-center justify-center gap-2 rounded-full px-6 text-[17px] font-semibold transition-shadow duration-200 disabled:cursor-not-allowed ${BTN[variant]} ${className}`}>
      {icon ? <Icon name={icon} /> : null}
      {children}
    </button>
  );
}

const CARD = {
  low: "bg-surface-container-low",
  high: "bg-surface-container-high",
  highest: "bg-surface-container-highest",
  primary: "bg-primary-container text-on-primary-container",
  outlined: "border border-outline-variant bg-surface",
};
export function Card({ tone = "low", className = "", children }: { tone?: keyof typeof CARD; className?: string; children: ReactNode }) {
  return <section className={`rounded-[28px] p-6 ${CARD[tone]} ${className}`}>{children}</section>;
}

export function Screen({ children }: { children: ReactNode }) {
  return <div className="screen-enter space-y-4">{children}</div>;
}

export function Heading({ children, sub, icon }: { children: ReactNode; sub?: ReactNode; icon?: IconName }) {
  return (
    <header className="mb-4">
      {icon ? <span className="mb-4 flex size-14 items-center justify-center rounded-full bg-primary-container text-on-primary-container"><Icon name={icon} size={28} /></span> : null}
      <h1 className="type-headline-m text-on-surface">{children}</h1>
      {sub ? <p className="type-body-l mt-2 text-on-surface-variant">{sub}</p> : null}
    </header>
  );
}

export function InfoRow({ icon, title, children }: { icon: IconName; title: string; children: ReactNode }) {
  return (
    <div className="flex gap-4">
      <span className="flex size-10 shrink-0 items-center justify-center rounded-full bg-secondary-container text-on-secondary-container"><Icon name={icon} size={22} /></span>
      <div>
        <p className="type-title-m text-on-surface">{title}</p>
        <p className="type-body-m text-on-surface-variant">{children}</p>
      </div>
    </div>
  );
}

const AVATAR = ["bg-primary-container text-on-primary-container", "bg-secondary-container text-on-secondary-container", "bg-tertiary-container text-on-tertiary-container"];
export function Avatar({ name }: { name: string }) {
  const h = [...name].reduce((a, c) => a + c.charCodeAt(0), 0) % AVATAR.length;
  return <span aria-hidden className={`flex size-14 shrink-0 items-center justify-center rounded-full text-xl font-semibold ${AVATAR[h]}`}>{initials(name)}</span>;
}

/** Big amount, Indian grouping, amount in words underneath. */
export function Amount({ value }: { value: number }) {
  return (
    <div>
      <p className="tnum text-[56px] leading-[64px] font-semibold tracking-tight text-on-surface" aria-label={amountInWords(value)}>{inr(value)}</p>
      <p className="type-body-l first-upper mt-1 text-on-surface-variant">{amountInWords(value)}</p>
    </div>
  );
}

export function Chip({ children, onClick, selected = false }: { children: ReactNode; onClick: () => void; selected?: boolean }) {
  return (
    <button type="button" onClick={onClick} aria-pressed={selected}
      className={`state-layer inline-flex min-h-14 flex-1 items-center justify-center gap-2 rounded-2xl border px-5 text-xl font-semibold ${selected ? "border-transparent bg-secondary-container text-on-secondary-container" : "border-outline bg-surface text-on-surface"}`}>
      {selected ? <Icon name="check" size={20} /> : null}
      {children}
    </button>
  );
}

const NOTICE = {
  info: ["bg-tertiary-container text-on-tertiary-container", "info"],
  warn: ["bg-warning-container text-on-warning-container", "warning"],
  error: ["bg-error-container text-on-error-container", "error"],
  ok: ["bg-success-container text-on-success-container", "check_circle"],
} as const;
export function Notice({ tone, title, children }: { tone: keyof typeof NOTICE; title: string; children?: ReactNode }) {
  const [cls, icon] = NOTICE[tone];
  return (
    <div role="status" className={`flex gap-3 rounded-2xl p-4 ${cls}`}>
      <Icon name={icon as IconName} className="mt-0.5" />
      <div>
        <p className="type-title-m">{title}</p>
        {children ? <div className="type-body-m mt-1">{children}</div> : null}
      </div>
    </div>
  );
}

export function ProgressBar({ value, label }: { value: number; label: string }) {
  return (
    <div role="progressbar" aria-label={label} aria-valuemin={0} aria-valuemax={100} aria-valuenow={Math.round(value * 100)} className="h-1.5 w-full overflow-hidden rounded-full bg-surface-container-highest">
      <div className="h-full rounded-full bg-primary transition-[width] duration-500 ease-[var(--ease-emphasized)]" style={{ width: `${Math.round(value * 100)}%` }} />
    </div>
  );
}

export function Spinner({ size = 56 }: { size?: number }) {
  return (
    <svg aria-hidden viewBox="0 0 48 48" width={size} height={size} className="vg-spin">
      <circle cx="24" cy="24" r="19" fill="none" stroke="var(--md-sys-color-surface-container-highest)" strokeWidth="5" />
      <path d="M24 5a19 19 0 0 1 19 19" fill="none" stroke="var(--md-sys-color-primary)" strokeWidth="5" strokeLinecap="round" />
    </svg>
  );
}
