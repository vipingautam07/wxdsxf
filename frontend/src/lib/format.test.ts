import { describe, expect, it } from "vitest";
import { clock, number, shiftDate, stamp } from "./format";

describe("UK presentation", () => {
  it("keeps missing generation distinct from a real zero", () => {
    expect(number(null)).toBe("—");
    expect(number(0)).toBe("0");
  });
  it("formats UK local time independently of the browser timezone", () => {
    expect(clock("2026-07-01T10:00:00Z")).toBe("11:00");
    expect(stamp("2026-07-01T23:30:00Z")).toContain("2 Jul");
    expect(stamp("2026-07-01T23:30:00Z")).toContain("BST");
  });
  it("includes February 1 delivery for January 31 decisions", () => {
    expect(shiftDate("2026-01-31", 1)).toBe("2026-02-01");
  });
});
