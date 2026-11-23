import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

// This file talks to a second dev server that has ARMS_ENABLED=1 and PROBES_ENABLED=1 (default port 8124).
vi.hoisted(() => {
  process.env.NEXT_PUBLIC_API_URL = process.env.ARMS_API_URL ?? "http://127.0.0.1:8124";
});
import Study from "@/components/Study";
import { api } from "@/lib/api";

const T = 20000;
const btn = (name: RegExp | string) => screen.findByRole("button", { name }, { timeout: T });

describe("always-confirm arm and probe disclosure", () => {
  it("discloses probes in consent, balances 1-tap and 3-tap cards, and debriefs", async () => {
    const u = userEvent.setup();
    const actions = vi.spyOn(api, "postAction");
    render(<Study />);

    // the consent screen only mentions deliberate mistakes because the server says probes are on
    expect(await screen.findByText(/deliberate mistakes/, {}, { timeout: T })).toBeInTheDocument();
    await u.click(screen.getByLabelText("Both equally"));
    await u.click(screen.getByLabelText("Quiet"));
    await u.click(screen.getByLabelText(/I understand and I am happy/));
    await u.click(await btn("Start"));
    await u.click(await btn("Allow microphone"));
    await u.click(await btn("Continue"));

    for (let i = 0; i < 9; i++) { // practice + 8 tasks
      await u.click(await btn(/Clear command/));
      const pay = await screen.findByRole("button", { name: /^Pay ₹/ }, { timeout: T });
      const confirms = screen.queryAllByRole("button", { name: /^Confirm / });
      if (confirms.length) {
        expect(pay).toBeDisabled(); // cannot pay before both fields are confirmed
        for (const c of confirms) await u.click(c);
        expect(confirms).toHaveLength(2);
      }
      expect(pay).toBeEnabled();
      await u.click(pay);
      await u.click(await btn("Next task"));
    }

    const taps = actions.mock.calls.map((c) => c[1].taps_count);
    expect(taps).toHaveLength(9);
    expect(taps[0]).toBe(1); // practice is always the routed one-tap path
    expect(taps.filter((t) => t === 3)).toHaveLength(4); // 4 of the 8 cards got the confirm-everything arm
    expect(taps.filter((t) => t === 1)).toHaveLength(5);

    for (const g of await screen.findAllByRole("radiogroup", {}, { timeout: T })) await u.click(within(g).getByLabelText("4"));
    await u.click(await btn("Finish"));
    expect(await screen.findByText(/deliberately wrong amount or person/, {}, { timeout: T })).toBeInTheDocument();
  });
});
