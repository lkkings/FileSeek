import { describe, expect, it } from "vitest";
import { filterFiles, sortFiles } from "./model";
import type { FileItem } from "./useLibrary";

const files: FileItem[] = [
  { id: "1", name: "zeta.pdf", category: "document", size: "2 MB", sizeBytes: 2 * 1024 * 1024, modified: "2026-01-03", parentFolder: null, path: "/zeta.pdf" },
  { id: "2", name: "alpha.jpg", category: "image", size: "1 MB", sizeBytes: 1024 * 1024, modified: "2026-01-01", parentFolder: null, path: "/alpha.jpg" },
];

describe("library model", () => {
  it("filters by category, name and size", () => {
    expect(filterFiles(files, { activeCategory: "document", searchQuery: null, filterName: "zeta", filterMinSize: "1", filterMaxSize: "3", filterStartDate: "", filterEndDate: "" })).toEqual([files[0]]);
  });

  it("sorts without mutating the source list", () => {
    const sorted = sortFiles(files, "name", "asc");
    expect(sorted.map((file) => file.name)).toEqual(["alpha.jpg", "zeta.pdf"]);
    expect(files[0]?.name).toBe("zeta.pdf");
  });
});
