import { render } from "@testing-library/react";
import axe from "axe-core";
import { describe, expect, it } from "vitest";
import { STATES } from "@/components/StatesGallery";

// jsdom has no layout, so colour contrast cannot be computed here; names, roles, labels and structure can.
describe("accessibility: every screen and state has no axe violations", () => {
  for (const s of STATES) {
    it(s.label, async () => {
      const { container } = render(<main>{s.node}</main>);
      const res = await axe.run(container, { rules: { "color-contrast": { enabled: false }, region: { enabled: false } } });
      expect(res.violations.map((v) => `${v.id}: ${v.nodes.map((n) => n.target.join(" ")).join(" | ")}`)).toEqual([]);
    });
  }
  it("negative control: the harness really does catch a nameless button and an unlabelled input", async () => {
    const { container } = render(<main><button type="button"><svg aria-hidden /></button><input type="text" /></main>);
    const res = await axe.run(container, { rules: { "color-contrast": { enabled: false }, region: { enabled: false } } });
    expect(res.violations.map((v) => v.id)).toEqual(expect.arrayContaining(["button-name", "label"]));
  });
  it("covers every screen in the spec", () => {
    expect(STATES.length).toBeGreaterThanOrEqual(20);
  });
});
