import { fireEvent, render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

// Talks to a dev server running on the synthetic study database (default port 8125).
const URL_ = vi.hoisted(() => {
  process.env.NEXT_PUBLIC_API_URL = process.env.ADMIN_API_URL ?? "http://127.0.0.1:8125";
  return process.env.NEXT_PUBLIC_API_URL;
});
import Dashboard from "@/components/admin/Dashboard";
import type { RiskCoverage, Summary, Calibration } from "@/lib/adminApi";

const TOKEN = "dev-admin-token";
const get = async <T,>(p: string): Promise<T> => (await fetch(`${URL_}/api/admin/${p}`, { headers: { "X-Admin-Token": TOKEN } })).json() as Promise<T>;
const pct = (x: number | null, d = 1) => (x == null ? "n/a" : `${(x * 100).toFixed(d)}%`);
const T = 20000;

describe("admin dashboard on synthetic data", () => {
  it("warns that the data is synthetic and shows the API's numbers", async () => {
    const s = await get<Summary>("summary");
    render(<Dashboard token={TOKEN} onSignOut={() => {}} />);
    expect(await screen.findByText("SYNTHETIC DATA. Not results.", {}, { timeout: T })).toBeInTheDocument();
    const started = screen.getByText("Participants started").parentElement!;
    expect(within(started).getByText(String(s.participants.started))).toBeInTheDocument();
    expect(within(started).getByText(`${s.participants.completed} completed`)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Export CSV/ })).toBeInTheDocument();
  });

  it("replays thresholds: the slider changes the numbers, and they equal the API's", async () => {
    const u = userEvent.setup();
    const rc = await get<RiskCoverage>("risk-coverage");
    const live = rc.curve.findIndex((p) => p.threshold === rc.live_delta);
    render(<Dashboard token={TOKEN} onSignOut={() => {}} />);
    await u.click(await screen.findByRole("tab", { name: "Risk and coverage" }, { timeout: T }));

    const slider = screen.getByLabelText(/Replay threshold offset/) as HTMLInputElement;
    expect(slider.value).toBe(String(live));
    expect(screen.getByText(/\(live router\)/)).toBeInTheDocument();
    const p0 = rc.curve[live];
    expect(screen.getByText(`${p0.n_fast} of ${p0.n_total} commands`)).toBeInTheDocument();
    expect(screen.getByText(pct(p0.coverage))).toBeInTheDocument();

    const target = Math.min(rc.curve.length - 1, live + 8); // stricter bar: fewer commands take the fast path
    fireEvent.change(slider, { target: { value: String(target) } });
    const p1 = rc.curve[target];
    expect(p1.n_fast).toBeLessThanOrEqual(p0.n_fast);
    expect(screen.getByText(`${p1.n_fast} of ${p1.n_total} commands`)).toBeInTheDocument();
    expect(screen.getByLabelText(/Replay threshold offset: 0\.08/)).toBeInTheDocument();
    expect(screen.queryByText(/\(live router\)/)).toBeNull();

    // the pre-registered H2 rule preview agrees with a direct computation on the API curve
    const b = 0.05;
    const ok = rc.curve.filter((p) => p.n_fast > 0 && p.wilson_hi <= b);
    const best = ok.length ? ok.reduce((a, c) => (c.coverage > a.coverage || (c.coverage === a.coverage && c.threshold > a.threshold) ? c : a)) : null;
    expect(best ? screen.getByText(best.threshold.toFixed(2), { selector: "b" }) : screen.getByText(/No threshold meets this bound/)).toBeInTheDocument();
  });

  it("shows calibration numbers that match the API", async () => {
    const u = userEvent.setup();
    const cal = await get<Calibration>("calibration");
    render(<Dashboard token={TOKEN} onSignOut={() => {}} />);
    await u.click(await screen.findByRole("tab", { name: "Calibration" }, { timeout: T }));
    const s = cal.signals["amount.combined"];
    const ece = screen.getByText("ECE (10 bins)").parentElement!;
    expect(within(ece).getByText((s.ece as number).toFixed(3))).toBeInTheDocument();
    await u.selectOptions(screen.getByLabelText("Signal:"), "amount.self_conf");
    expect(within(screen.getByText("ECE (10 bins)").parentElement!).getByText((cal.signals["amount.self_conf"].ece as number).toFixed(3))).toBeInTheDocument();
  });

  it("rejects a wrong token", async () => {
    render(<Dashboard token="not-the-token" onSignOut={() => {}} />);
    expect(await screen.findByRole("alert", {}, { timeout: T })).toHaveTextContent("That token was not accepted");
  });
});
