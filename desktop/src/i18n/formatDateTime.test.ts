import { describe, expect, it } from "vitest";

import { formatDateTime } from "./formatDateTime";

describe("formatDateTime", () => {
  it("formats ISO dates to the nearest second", () => {
    expect(formatDateTime("2026-09-28T08:01:02")).toBe("2026-09-28 08:01:02");
  });

  it("keeps non-ISO and invalid values unchanged", () => {
    expect(formatDateTime("2026-09-28 08:01")).toBe("2026-09-28 08:01");
    expect(formatDateTime("2026-09-28Tinvalid")).toBe("2026-09-28Tinvalid");
  });

  it("uses the provided fallback for empty values", () => {
    expect(formatDateTime(null, "")).toBe("");
  });
});
