"use client";
import { useEffect, useRef, useState } from "react";
import { inr } from "@/lib/format";
import type { Strings } from "@/lib/i18n";
import type { Chip as ChipT, CommandResult, Contact } from "@/lib/types";
import { Amount, Avatar, Button, Card, Chip, Heading, Icon, Screen, Spinner } from "./ui";

export function Processing({ t, onCancel, onSlow }: { t: Strings; onCancel: () => void; onSlow: () => void }) {
  const [slow, setSlow] = useState(false);
  useEffect(() => {
    const id = setTimeout(() => { setSlow(true); onSlow(); }, 5000);
    return () => clearTimeout(id);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);
  return (
    <Screen>
      <Card className="flex flex-col items-center gap-6 py-14 text-center">
        <Spinner />
        <p role="status" aria-live="polite" className="type-title-l text-on-surface">{t.processing.title}</p>
        {slow ? (
          <div className="w-full space-y-3">
            <p className="type-body-l text-on-surface-variant">{t.processing.slow}</p>
            <Button variant="outlined" onClick={onCancel}>{t.processing.cancel}</Button>
          </div>
        ) : null}
      </Card>
    </Screen>
  );
}

function PayeeRow({ name, tag }: { name: string; tag?: string }) {
  return (
    <div className="flex items-center gap-4">
      <Avatar name={name} />
      <div>
        <p className="type-label-l uppercase text-on-surface-variant">{tag}</p>
        <p className="type-headline-m text-on-surface">{name}</p>
      </div>
    </div>
  );
}

function NoteChip({ t, note }: { t: Strings; note?: string | null }) {
  return note ? (
    <p className="type-body-l text-on-surface-variant">{t.result.note}: <span className="rounded-lg bg-surface-container-highest px-2 py-0.5 font-semibold text-on-surface">{note}</span></p>
  ) : null;
}

/** Fast path card (Tier A). Also shown after a Tier B chip is picked. */
export function Confirm({ t, payee, amount, note, onPay, onEdit }: {
  t: Strings; payee: string; amount: number; note?: string | null; onPay: () => void; onEdit: () => void;
}) {
  return (
    <Screen>
      <Card tone="high" className="space-y-6">
        <PayeeRow name={payee} tag={t.result.payTo} />
        <hr className="border-outline-variant" />
        <Amount value={amount} />
        <NoteChip t={t} note={note} />
      </Card>
      <Button icon="arrow_forward" onClick={onPay}>{t.result.pay(inr(amount))}</Button>
      <Button variant="text" icon="edit" onClick={onEdit}>{t.result.edit}</Button>
    </Screen>
  );
}

/** Always-confirm arm: read back each field and ask for a separate confirmation before paying (3 taps). */
export function ConfirmAll({ t, payee, amount, note, onTap, onPay, onEdit }: {
  t: Strings; payee: string; amount: number; note?: string | null; onTap: () => void; onPay: () => void; onEdit: () => void;
}) {
  const [okPayee, setOkPayee] = useState(false);
  const [okAmount, setOkAmount] = useState(false);
  const row = (ok: boolean, set: (v: boolean) => void, name: string, children: React.ReactNode) => (
    <div className="flex items-center justify-between gap-3">
      <div>{children}</div>
      <button type="button" aria-label={`${t.result.confirmBtn} ${name}`} aria-pressed={ok} disabled={ok} onClick={() => { onTap(); set(true); }}
        className={`state-layer inline-flex min-h-12 shrink-0 items-center gap-1 rounded-full px-4 type-label-l ${ok ? "bg-success-container text-on-success-container" : "border border-outline text-primary"}`}>
        <Icon name={ok ? "check_circle" : "check"} size={20} />
        {ok ? t.result.confirmed : t.result.confirmBtn}
      </button>
    </div>
  );
  return (
    <Screen>
      <Card tone="high" className="space-y-5">
        <p className="type-title-m text-on-surface-variant">{t.result.checkDetails}</p>
        {row(okPayee, setOkPayee, payee, <PayeeRow name={payee} tag={t.result.payTo} />)}
        <hr className="border-outline-variant" />
        {row(okAmount, setOkAmount, inr(amount), <><p className="type-label-l uppercase text-on-surface-variant">{t.result.amountLabel}</p><Amount value={amount} /></>)}
        <NoteChip t={t} note={note} />
      </Card>
      <Button icon="arrow_forward" disabled={!(okPayee && okAmount)} onClick={onPay}>{t.result.pay(inr(amount))}</Button>
      <Button variant="text" icon="edit" onClick={onEdit}>{t.result.edit}</Button>
    </Screen>
  );
}

export function TierB({ t, result, onPay, onElse, onTap }: {
  t: Strings; result: CommandResult; onPay: (chip: ChipT, field: "payee" | "amount") => void; onElse: () => void; onTap: () => void;
}) {
  const [picked, setPicked] = useState<ChipT | null>(null);
  const chips = result.chips;
  if (!chips) return null;
  const f = result.fields;
  const isAmount = chips.field === "amount";
  if (picked) {
    const payee = isAmount ? f?.payee?.name ?? "" : picked.label;
    const amount = isAmount ? Number(picked.value) : f?.amount ?? 0;
    return <Confirm t={t} payee={payee} amount={amount} note={f?.note} onPay={() => onPay(picked, chips.field)} onEdit={onElse} />;
  }
  return (
    <Screen>
      <Card tone="high" className="space-y-4">
        <p className="type-label-l flex items-center gap-1.5 text-success"><Icon name="check_circle" size={18} />{t.result.confirmed}</p>
        {isAmount && f?.payee ? <PayeeRow name={f.payee.name} tag={t.result.payTo} /> : null}
        {!isAmount && f?.amount ? <Amount value={f.amount} /> : null}
      </Card>
      <div className="rounded-[28px] bg-warning-container p-5 text-on-warning-container">
        <h1 className="type-title-l mb-4 flex items-center gap-2"><Icon name="warning" />{t.result.didYouMean(isAmount ? t.result.amountWord : t.result.payeeWord)}</h1>
        <div className="flex flex-wrap gap-3">
          {chips.options.map((c) => (
            <Chip key={String(c.value)} onClick={() => { onTap(); setPicked(c); }}>{isAmount ? inr(Number(c.value)) : c.label}</Chip>
          ))}
        </div>
      </div>
      <Button variant="text" onClick={onElse}>{t.result.somethingElse}</Button>
    </Screen>
  );
}

export function TierC({ t, retries, onRetry, onManual }: { t: Strings; retries: number; onRetry: () => void; onManual: () => void }) {
  const manualOnly = retries >= 2;
  return (
    <Screen>
      <Card tone="high" className="space-y-5">
        <Heading icon="mic" sub={manualOnly ? t.result.manualOnly : t.result.cantCatchHelp}>{t.result.cantCatch}</Heading>
        {manualOnly ? null : <Button icon="refresh" onClick={onRetry}>{t.result.tryAgain}</Button>}
        <Button variant={manualOnly ? "filled" : "outlined"} icon="keyboard" onClick={onManual}>{t.result.manual}</Button>
      </Card>
    </Screen>
  );
}

export function Manual({ t, contacts, initialPayee, initialAmount, onSubmit, onBack, onTap }: {
  t: Strings; contacts: Contact[]; initialPayee?: string | null; initialAmount?: number | null;
  onSubmit: (payeeId: string, amount: number) => void; onBack: () => void; onTap: () => void;
}) {
  const typed = useRef(false);
  const [payee, setPayee] = useState<string | null>(initialPayee ?? null);
  const [raw, setRaw] = useState(initialAmount ? String(initialAmount) : "");
  const amount = /^\d{1,7}$/.test(raw) ? Number(raw) : 0;
  return (
    <Screen>
      <Card tone="high" className="space-y-6">
        <Heading icon="keyboard">{t.result.manual}</Heading>
        <fieldset>
          <legend className="type-title-m mb-3 text-on-surface">{t.result.pickPayee}</legend>
          <div className="grid grid-cols-2 gap-2">
            {contacts.map((c) => (
              <button key={c.payee_id} type="button" aria-pressed={payee === c.payee_id} onClick={() => { onTap(); setPayee(c.payee_id); }}
                className={`state-layer flex min-h-14 items-center gap-2 rounded-2xl border px-4 text-left type-title-m ${payee === c.payee_id ? "border-transparent bg-secondary-container text-on-secondary-container" : "border-outline text-on-surface"}`}>
                {payee === c.payee_id ? <Icon name="check" size={20} /> : null}
                {c.display_name}
              </button>
            ))}
          </div>
        </fieldset>
        <div>
          <label htmlFor="amt" className="type-title-m mb-2 block text-on-surface">{t.result.typeAmount}</label>
          <div className="flex items-center rounded-2xl border border-outline bg-surface px-4 focus-within:border-primary focus-within:outline-3 focus-within:outline-primary">
            <span aria-hidden className="type-headline-m text-on-surface-variant">{"\u20b9"}</span>
            <input id="amt" inputMode="numeric" pattern="[0-9]*" autoComplete="off" value={raw}
              onChange={(e) => { if (!typed.current) { typed.current = true; onTap(); } setRaw(e.target.value.replace(/\D/g, "").slice(0, 7)); }}
              className="tnum type-headline-m min-h-16 w-full bg-transparent px-2 text-on-surface outline-none" />
          </div>
          {amount ? <p className="type-body-m mt-2 text-on-surface-variant">{inr(amount)}</p> : null}
        </div>
      </Card>
      <Button icon="arrow_forward" disabled={!payee || !amount} onClick={() => payee && onSubmit(payee, amount)}>{amount ? t.result.pay(inr(amount)) : t.result.review}</Button>
      <Button variant="text" icon="arrow_back" onClick={onBack}>{t.back}</Button>
    </Screen>
  );
}

export function Success({ t, onNext }: { t: Strings; onNext: () => void }) {
  return (
    <Screen>
      <Card tone="high" className="flex flex-col items-center gap-5 py-10 text-center">
        <span aria-hidden className="vg-pop flex size-24 items-center justify-center rounded-full bg-success-container text-on-success-container"><Icon name="check_circle" size={56} /></span>
        <Heading sub={t.success.sub}>{t.success.title}</Heading>
      </Card>
      <Button icon="arrow_forward" onClick={onNext}>{t.success.next}</Button>
    </Screen>
  );
}
