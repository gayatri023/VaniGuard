export function deviceInfo(): { device_class: string; browser: string; os: string } {
  if (typeof navigator === "undefined") return { device_class: "unknown", browser: "unknown", os: "unknown" };
  const ua = navigator.userAgent;
  const os = /Android/i.test(ua) ? "Android" : /iPhone|iPad|iPod/i.test(ua) ? "iOS" : /Windows/i.test(ua) ? "Windows" : /Mac OS X/i.test(ua) ? "macOS" : /Linux/i.test(ua) ? "Linux" : "other";
  const browser = /SamsungBrowser/i.test(ua) ? "Samsung" : /EdgA?\//i.test(ua) ? "Edge" : /CriOS|Chrome/i.test(ua) ? "Chrome" : /FxiOS|Firefox/i.test(ua) ? "Firefox" : /Safari/i.test(ua) ? "Safari" : "other";
  return { device_class: /Mobi|Android|iPhone/i.test(ua) ? "mobile" : "desktop", browser, os };
}

export const uid = (): string =>
  typeof crypto !== "undefined" && "randomUUID" in crypto ? crypto.randomUUID() : `${Date.now()}-${Math.random().toString(16).slice(2)}`;
