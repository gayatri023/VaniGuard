"use client";
import { useCallback, useEffect, useRef, useState } from "react";

export interface Recording { blob: Blob; mime: string; ms: number }

const MIME_PREFS = ["audio/webm;codecs=opus", "audio/webm", "audio/mp4", "audio/ogg;codecs=opus"];
export const MAX_MS = 15000;
const SILENCE_MS = 1500;

let sharedStream: MediaStream | null = null;

export function micSupported(): boolean {
  return typeof navigator !== "undefined" && !!navigator.mediaDevices?.getUserMedia && typeof MediaRecorder !== "undefined";
}

export function inAppBrowser(): boolean {
  return typeof navigator !== "undefined" && /FBAN|FBAV|Instagram|MicroMessenger|Snapchat|Line\/|; wv\)|GSA\//i.test(navigator.userAgent);
}

/** One stream is reused for the whole session so iOS does not re-prompt on every task. */
export async function getMicStream(): Promise<MediaStream> {
  if (sharedStream && sharedStream.getAudioTracks().some((t) => t.readyState === "live")) return sharedStream;
  sharedStream = await navigator.mediaDevices.getUserMedia({
    audio: { echoCancellation: true, noiseSuppression: true, autoGainControl: true },
  });
  return sharedStream;
}

export function releaseMic(): void {
  sharedStream?.getTracks().forEach((t) => t.stop());
  sharedStream = null;
}

function pickMime(): string | undefined {
  return MIME_PREFS.find((m) => MediaRecorder.isTypeSupported(m));
}

/** Live input level 0..1 for a stream (used by the mic-setup meter and the recorder). */
export function useLevel(stream: MediaStream | null): { level: number; peak: number } {
  const [level, setLevel] = useState(0);
  const [peak, setPeak] = useState(0);
  useEffect(() => {
    if (!stream) return;
    const ctx = new AudioContext();
    const an = ctx.createAnalyser();
    an.fftSize = 512;
    ctx.createMediaStreamSource(stream).connect(an);
    const buf = new Uint8Array(an.fftSize);
    let raf = 0;
    const tick = () => {
      an.getByteTimeDomainData(buf);
      let s = 0;
      for (const v of buf) s += ((v - 128) / 128) ** 2;
      const lv = Math.min(1, Math.sqrt(s / buf.length) * 4);
      setLevel(lv);
      setPeak((p) => Math.max(p, lv));
      raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => {
      cancelAnimationFrame(raf);
      void ctx.close();
    };
  }, [stream]);
  return { level, peak };
}

/** Tap-to-start recorder. Stops on tap, after 1.5 s of silence following speech, or at 15 s. */
export function useRecorder(onDone: (r: Recording) => void) {
  const [recording, setRecording] = useState(false);
  const [level, setLevel] = useState(0);
  const [history, setHistory] = useState<number[]>(() => Array(28).fill(0));
  const [elapsed, setElapsed] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const recRef = useRef<MediaRecorder | null>(null);
  const stopRef = useRef<() => void>(() => {});
  const doneRef = useRef(onDone);
  useEffect(() => {
    doneRef.current = onDone;
  }, [onDone]);

  const stop = useCallback(() => stopRef.current(), []);

  const start = useCallback(async () => {
    setError(null);
    try {
      const stream = await getMicStream();
      const mime = pickMime();
      const rec = new MediaRecorder(stream, mime ? { mimeType: mime } : undefined);
      const chunks: Blob[] = [];
      const t0 = performance.now();
      const ctx = new AudioContext();
      const an = ctx.createAnalyser();
      an.fftSize = 512;
      ctx.createMediaStreamSource(stream).connect(an);
      const buf = new Uint8Array(an.fftSize);
      let raf = 0;
      let heardSpeech = false;
      let quietSince = 0;
      let floor = 0.01;
      let finished = false;

      const finish = () => {
        if (finished) return;
        finished = true;
        cancelAnimationFrame(raf);
        if (rec.state !== "inactive") rec.stop();
      };
      rec.ondataavailable = (e) => e.data.size && chunks.push(e.data);
      rec.onstop = () => {
        void ctx.close();
        setRecording(false);
        setLevel(0);
        const ms = Math.round(performance.now() - t0);
        const type = rec.mimeType || mime || "audio/webm";
        doneRef.current({ blob: new Blob(chunks, { type }), mime: type, ms });
      };
      const tick = () => {
        an.getByteTimeDomainData(buf);
        let s = 0;
        for (const v of buf) s += ((v - 128) / 128) ** 2;
        const rms = Math.sqrt(s / buf.length);
        const now = performance.now() - t0;
        if (now < 400) floor = Math.max(floor, rms * 1.5); // calibrate to room noise
        const speech = now > 400 && rms > Math.max(0.04, floor * 2);
        if (speech) {
          heardSpeech = true;
          quietSince = 0;
        } else if (heardSpeech && rms < Math.max(0.025, floor * 1.3)) {
          quietSince ||= now;
          if (now - quietSince > SILENCE_MS && now > 800) return finish();
        }
        if (now >= MAX_MS) return finish();
        const lv = Math.min(1, rms * 4);
        setLevel(lv);
        setHistory((h) => [...h.slice(1), lv]);
        setElapsed(now);
        raf = requestAnimationFrame(tick);
      };
      stopRef.current = finish;
      rec.start();
      recRef.current = rec;
      setRecording(true);
      setElapsed(0);
      tick();
    } catch (e) {
      setError(e instanceof DOMException ? e.name : "mic_error");
      setRecording(false);
    }
  }, []);

  useEffect(() => () => stopRef.current(), []);
  return { recording, level, history, elapsed, error, start, stop };
}
