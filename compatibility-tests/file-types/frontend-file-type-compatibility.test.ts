import { createHash } from "node:crypto";
import { readFileSync, statSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";

import type { FilePreviewItem } from "../../desktop/src/features/file-preview/types";
import {
  buildPreviewUrl,
  getDocumentPreviewSupport,
  getPreviewResourceKind,
  resolvePreviewCategory,
} from "../../desktop/src/features/file-preview/preview";

interface FileTypeContractEntry {
  fileType: string;
  fileName: string;
  detectedFileType: string;
  category: "document" | "image" | "video";
  mediaType: string;
  documentPreviewSupport: "supported" | "unsupported" | null;
}

const contractPath = resolve(process.cwd(), "../compatibility-tests/file-types/file-types.json");
const contract = JSON.parse(
  readFileSync(contractPath, "utf-8"),
) as FileTypeContractEntry[];
const fixturesRoot = resolve(process.cwd(), "../test");

interface FixtureManifestEntry {
  fileName: string;
  fileType: string;
  detectedFileType: string;
  category: "document" | "image" | "video";
  mediaType: string;
  size: number;
  sha256: string;
  origin: "downloaded" | "generated" | "derived";
  source: string;
  sourceUrl: string | null;
  license: string;
}

const manifestPath = resolve(fixturesRoot, "manifest.json");
const manifest = JSON.parse(
  readFileSync(manifestPath, "utf-8"),
) as FixtureManifestEntry[];

function createPreviewItem(entry: FileTypeContractEntry): FilePreviewItem {
  return {
    fileId: entry.fileType,
    fileName: entry.fileName,
    fileType: entry.category,
  };
}

describe("file type compatibility", () => {
  it("has a valid real fixture and manifest entry for every backend file type", () => {
    const manifestByFileName = new Map(
      manifest.map((entry) => [entry.fileName, entry]),
    );

    expect(manifest).toHaveLength(contract.length);
    expect(manifestByFileName.size).toBe(contract.length);

    for (const entry of contract) {
      const fixtureEntry = manifestByFileName.get(entry.fileName);
      expect(fixtureEntry, entry.fileType).toBeDefined();
      if (!fixtureEntry) {
        continue;
      }

      const fixturePath = resolve(fixturesRoot, entry.fileName);
      const content = readFileSync(fixturePath);

      expect(fixtureEntry.fileType, entry.fileType).toBe(entry.fileType);
      expect(fixtureEntry.detectedFileType, entry.fileType).toBe(entry.detectedFileType);
      expect(fixtureEntry.category, entry.fileType).toBe(entry.category);
      expect(fixtureEntry.mediaType, entry.fileType).toBe(entry.mediaType);
      expect(fixtureEntry.origin, entry.fileType).toBeOneOf([
        "downloaded",
        "generated",
        "derived",
      ]);
      expect(fixtureEntry.source, entry.fileType).toBeTruthy();
      expect(fixtureEntry.license, entry.fileType).toBeTruthy();
      expect(statSync(fixturePath).size, entry.fileType).toBe(fixtureEntry.size);
      expect(
        createHash("sha256").update(content).digest("hex"),
        entry.fileType,
      ).toBe(fixtureEntry.sha256);
    }
  });

  it("maps every backend file type to a frontend preview category", () => {
    expect(contract).toHaveLength(40);
    expect(new Set(contract.map((entry) => entry.fileType)).size).toBe(contract.length);

    for (const entry of contract) {
      expect(resolvePreviewCategory(entry.fileType), entry.fileType).toBe(entry.category);
    }
  });

  it("gives every backend file type a preview resource and URL", () => {
    for (const entry of contract) {
      const item = createPreviewItem(entry);
      const expectedResource =
        entry.category === "document" ? "document" : "thumbnail";

      expect(getPreviewResourceKind(item), entry.fileType).toBe(expectedResource);
      expect(getDocumentPreviewSupport(item), entry.fileType).toBe(
        entry.documentPreviewSupport,
      );
      expect(buildPreviewUrl(item, "list"), entry.fileType).toBe(
        expectedResource === "document"
          ? `/api/v1/library/files/preview/${entry.fileType}`
          : `/api/v1/library/files/${entry.fileType}/thumbnail?size=list`,
      );
    }
  });
});
