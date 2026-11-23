"use client";
import { useSyncExternalStore } from "react";

// Browser-only values (localStorage, online status, user agent) read through useSyncExternalStore:
// the server renders a safe default, the phone then re-renders with the real value, no hydration mismatch.
const listeners = new Set<() => void>();
const emit = () => listeners.forEach((l) => l());

function subscribe(cb: () => void) {
  listeners.add(cb);
  window.addEventListener("storage", cb);
  return () => {
    listeners.delete(cb);
    window.removeEventListener("storage", cb);
  };
}

export function readStored(key: string): string | null {
  try {
    return localStorage.getItem(key);
  } catch {
    return null;
  }
}

export function writeStored(key: string, value: string | null): void {
  try {
    if (value === null) localStorage.removeItem(key);
    else localStorage.setItem(key, value);
  } catch {}
  emit();
}

export function useStored(key: string): string | null {
  return useSyncExternalStore(subscribe, () => readStored(key), () => null);
}

function subscribeOnline(cb: () => void) {
  window.addEventListener("online", cb);
  window.addEventListener("offline", cb);
  return () => {
    window.removeEventListener("online", cb);
    window.removeEventListener("offline", cb);
  };
}
export const useOnline = (): boolean => useSyncExternalStore(subscribeOnline, () => navigator.onLine, () => true);

const never = () => () => {};
/** A value that is fixed for the life of the page (feature detection, user agent). */
export const usePageFact = (read: () => boolean): boolean => useSyncExternalStore(never, read, () => false);
