import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { writeFileSync } from "node:fs";
import { describe, expect, it, vi } from "vitest";
import { api } from "@/lib/api";
import Study from "@/components/Study";
import { End } from "@/components/Finish";
import { STRINGS } from "@/lib/i18n";

const T = 20000;
const btn = (name: RegExp | string) => screen.findByRole("button", { name }, { timeout: T });

async function consent(u: ReturnType<typeof userEvent.setup>) {
  expect(screen.getByText("Demo. No real money moves.")).toBeInTheDocument(); // banner on the very first screen
  const start = await btn("Start");
  expect(start).toBeDisabled();
  await u.click(screen.getByLabelText("Both equally"));
  await u.click(screen.getByLabelText("Quiet"));
  await u.click(screen.getByLabelText(/I understand and I am happy/));
  await u.click(start);
  await u.click(await btn("Allow microphone"));
  expect(await screen.findByText(/Say: .testing, one two./)).toBeInTheDocument();
  await u.click(await btn("Continue"));
}

const dev = (u: ReturnType<typeof userEvent.setup>, label: RegExp) => btn(label).then((b) => u.click(b));

describe("participant journey against the real API", () => {
  it("consent -> practice -> tiers A, B, C -> 8 tasks -> survey -> deletion code", async () => {
    const u = userEvent.setup();
    const actions = vi.spyOn(api, "postAction");
    render(<Study />);
    await consent(u);

    // practice card
    expect(await screen.findByText("Practice round", {}, { timeout: T })).toBeInTheDocument();
    expect(screen.getByText("Pay Priya Rs 20 for chai.")).toBeInTheDocument();
    await dev(u, /Clear command/);
    expect(await screen.findByText(/^twenty rupees$/i, {}, { timeout: T })).toBeInTheDocument(); // amount in words
    await u.click(await btn("Pay ₹20"));
    expect(await screen.findByText("Demo payment complete")).toBeInTheDocument();
    expect(screen.getByText("No money moved.")).toBeInTheDocument();
    await u.click(await btn("Next task"));

    // task 1: Tier B, amount chips
    expect(await screen.findByText("Task 1 of 8", {}, { timeout: T })).toBeInTheDocument();
    await dev(u, /Samples disagree/);
    expect(await screen.findByText(/Did you mean this amount/, {}, { timeout: T })).toBeInTheDocument();
    await u.click(await btn("₹15"));
    await u.click(await btn("Pay ₹15"));
    await u.click(await btn("Next task"));

    // task 2: Tier C -> manual entry
    expect(await screen.findByText("Task 2 of 8", {}, { timeout: T })).toBeInTheDocument();
    await dev(u, /misreads 15 as 50/);
    expect(await screen.findByText("I could not catch that clearly", {}, { timeout: T })).toBeInTheDocument();
    await u.click(await btn("Enter manually"));
    await u.click(await btn("Priya"));
    await u.type(screen.getByLabelText("Amount in rupees"), "20");
    await u.click(await btn("Pay ₹20"));
    await u.click(await btn("Next task"));

    // tasks 3..8: Tier A each
    for (let n = 3; n <= 8; n++) {
      expect(await screen.findByText(`Task ${n} of 8`, {}, { timeout: T })).toBeInTheDocument();
      await dev(u, /Clear command/);
      await u.click(await btn(/^Pay ₹/));
      await u.click(await btn("Next task"));
    }

    // survey
    expect(await screen.findByText("Three quick questions", {}, { timeout: T })).toBeInTheDocument();
    const finish = screen.getByRole("button", { name: "Finish" });
    expect(finish).toBeDisabled();
    for (const g of screen.getAllByRole("radiogroup")) await u.click(within(g).getByLabelText("5"));
    await u.click(finish);

    // end screen shows the deletion code
    expect(await screen.findByText("Thank you", {}, { timeout: T })).toBeInTheDocument();
    const code = screen.getByText(/^[0-9A-F]{8}$/).textContent!;
    writeFileSync("/tmp/e2e_out.json", JSON.stringify({ code }));
    expect(localStorage.getItem("vg_session")).toBeNull();

    // tap instrumentation feeds H2, so pin it: A = Pay (1); B = chip + Pay (2); C->manual = Enter manually + contact + amount + Pay (4)
    const taps = actions.mock.calls.map((c) => c[1].taps_count);
    expect(taps.slice(0, 3)).toEqual([1, 2, 4]);
    expect(taps.slice(3)).toEqual([1, 1, 1, 1, 1, 1]);
  });

  it("after two failed retries only manual entry is offered", async () => {
    const u = userEvent.setup();
    render(<Study />);
    await consent(u);
    for (let i = 0; i < 2; i++) {
      await dev(u, /Can't understand/);
      await screen.findByText("I could not catch that clearly", {}, { timeout: T });
      await u.click(await btn(/Try again/));
    }
    await dev(u, /Can't understand/);
    await screen.findByText("Let us enter this one by hand.", {}, { timeout: T });
    expect(screen.queryByRole("button", { name: /Try again/ })).toBeNull();
    expect(screen.getByRole("button", { name: "Enter manually" })).toBeInTheDocument();
  });

  it("switches to Hinglish and the banner follows", async () => {
    const u = userEvent.setup();
    render(<Study />);
    await u.click(screen.getByRole("button", { name: "हिंग्लिश" }));
    expect(await screen.findByText("Demo hai. Asli paisa nahi jaata.")).toBeInTheDocument();
  });
});

describe("end screen", () => {
  it("shows the code, asks before deleting, then confirms", async () => {
    const u = userEvent.setup();
    let called = 0;
    render(<End t={STRINGS.en} code="AB12CD34" probes={false} onDelete={async () => { called++; return true; }} />);
    expect(screen.getByText("AB12CD34")).toBeInTheDocument();
    await u.click(screen.getByRole("button", { name: "Delete my data now" }));
    expect(called).toBe(0); // first tap only asks for confirmation
    expect(screen.getByText("Are you sure? This cannot be undone.")).toBeInTheDocument();
    await u.click(screen.getByRole("button", { name: "Yes, delete everything" }));
    expect(await screen.findByText("Your data has been deleted.")).toBeInTheDocument();
    expect(called).toBe(1);
  });
});
