import "@testing-library/jest-dom/vitest";
import { afterEach, vi } from "vitest";
import { cleanup } from "@testing-library/react";

afterEach(() => { cleanup(); localStorage.clear(); });

// jsdom has no microphone: stub just enough of the Web Audio / MediaRecorder surface.
const track = { readyState: "live", stop: vi.fn() };
const stream = { getAudioTracks: () => [track], getTracks: () => [track] };
Object.defineProperty(navigator, "mediaDevices", { value: { getUserMedia: vi.fn(async () => stream) }, configurable: true });
Object.defineProperty(navigator, "clipboard", { value: { writeText: vi.fn(async () => undefined) }, configurable: true });
class FakeAnalyser { fftSize = 512; getByteTimeDomainData(b: Uint8Array) { b.fill(128); } }
class FakeAudioContext {
  createAnalyser() { return new FakeAnalyser(); }
  createMediaStreamSource() { return { connect: () => undefined }; }
  close() { return Promise.resolve(); }
}
class FakeRecorder { static isTypeSupported() { return true; } state = "inactive"; mimeType = "audio/webm"; }
vi.stubGlobal("AudioContext", FakeAudioContext);
vi.stubGlobal("MediaRecorder", FakeRecorder);
