import { describe, expect, it } from "vitest";
import { mount } from "@vue/test-utils";

import BomTable from "../components/BomTable.vue";
import type { BomItem } from "../api/bom";

function makeRow(overrides: Partial<BomItem> = {}): BomItem {
  return {
    id: crypto.randomUUID(),
    project_id: "00000000-0000-0000-0000-000000000000",
    designator: "R1",
    value: "10k",
    package: "0805",
    qty: 1,
    position_hint: null,
    inspect_scope: "pending",
    mi_likely: false,
    component_type: "smd_chip_passive",
    defect_history_count: 0,
    extra: null,
    ...overrides,
  };
}

describe("BomTable", () => {
  it("renders empty state when items is empty", () => {
    const wrapper = mount(BomTable, { props: { items: [] } });
    expect(wrapper.find('[data-testid="bom-table-empty"]').exists()).toBe(true);
    expect(wrapper.findAll('[data-testid="bom-row"]').length).toBe(0);
  });

  it("renders one tr per BomItem", () => {
    const items: BomItem[] = [
      makeRow({ designator: "R1" }),
      makeRow({ designator: "C4", package: "Radial", mi_likely: true, component_type: "electrolytic_cap" }),
      makeRow({ designator: "U7", package: "LQFP-100", mi_likely: false, component_type: "smd_qfp" }),
    ];
    const wrapper = mount(BomTable, { props: { items } });
    const rows = wrapper.findAll('[data-testid="bom-row"]');
    expect(rows.length).toBe(3);
    expect(rows[0].text()).toContain("R1");
    expect(rows[1].text()).toContain("C4");
    expect(rows[2].text()).toContain("U7");
  });

  it("shows total row count footer", () => {
    const items = [makeRow(), makeRow({ designator: "R2" }), makeRow({ designator: "R3" })];
    const wrapper = mount(BomTable, { props: { items } });
    const footer = wrapper.find('[data-testid="bom-footer"]');
    expect(footer.exists()).toBe(true);
    expect(footer.text()).toContain("3");
  });

  it("shows MI vs SMT breakdown in footer", () => {
    const items = [
      makeRow({ designator: "R1", mi_likely: false }),
      makeRow({ designator: "C4", mi_likely: true }),
      makeRow({ designator: "C5", mi_likely: true }),
    ];
    const wrapper = mount(BomTable, { props: { items } });
    const footer = wrapper.find('[data-testid="bom-footer"]').text();
    expect(footer).toContain("2");
    expect(footer).toContain("MI-likely");
    expect(footer).toContain("SMT");
  });

  it("renders dash for null fields", () => {
    const items = [makeRow({ value: null, package: null, qty: null, component_type: null })];
    const wrapper = mount(BomTable, { props: { items } });
    const row = wrapper.find('[data-testid="bom-row"]').text();
    expect(row).toContain("—");
  });
});
