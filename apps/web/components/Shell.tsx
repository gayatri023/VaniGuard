"use client";
import type { ReactNode } from "react";
import { useOnline } from "@/lib/store";
import type { Strings } from "@/lib/i18n";
import { Icon } from "./ui";

export function Shell({ t, onLang, children }: { t: Strings; onLang: () => void; children: ReactNode }) {
  const online = useOnline();
  return (
    <div className="mx-auto flex min-h-dvh w-full max-w-md flex-col bg-surface">
      <div className="sticky top-0 z-20">
        <div role="note" className="flex items-center justify-center gap-2 bg-tertiary-container px-3 py-2 text-on-tertiary-container">
          <Icon name="info" size={18} />
          <span className="type-label-l">{t.banner}</span>
        </div>
        {online ? null : (
          <div role="alert" className="type-label-l bg-error px-3 py-2 text-center text-on-error">{t.offline}</div>
        )}
      </div>
      <header className="flex items-center justify-between px-4 pb-1 pt-3">
        <div className="flex items-center gap-3">
          <span aria-hidden className="flex size-10 items-center justify-center rounded-xl bg-primary text-on-primary"><Icon name="mic" size={22} /></span>
          <span className="type-title-l text-on-surface">{t.appName}</span>
        </div>
        <button type="button" onClick={onLang} className="state-layer inline-flex min-h-12 items-center gap-2 rounded-full border border-outline px-4 text-on-surface-variant">
          <Icon name="translate" size={20} />
          <span className="type-label-l">{t.langName}</span>
        </button>
      </header>
      <main className="flex-1 px-4 pb-10 pt-3">{children}</main>
    </div>
  );
}
