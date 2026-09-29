import { describe, expect, it } from "vitest";

import type { StorageLocation } from "../../settings/types";
import { mapSystemImportPaths } from "./systemImportMapping";

const local: StorageLocation = {
  id: "local",
  type: "local",
  name: "Local",
  protocol: "file",
  endpoint: "file://localhost",
  root_path: "/",
  account: null,
  status: "active",
  is_system: true,
};

const mounted: StorageLocation = {
  id: "nas",
  type: "nas",
  name: "NAS",
  protocol: "mounted",
  endpoint: "/Volumes/nas",
  root_path: "/Volumes/nas",
  account: null,
  status: "active",
  is_system: false,
};

describe("mapSystemImportPaths", () => {
  it("maps active local paths", () => {
    expect(mapSystemImportPaths(["/tmp/report.pdf"], [local])).toEqual({
      selections: [{ storageId: "local", path: "/tmp/report.pdf" }],
      invalidPaths: [],
      unmappedPaths: [],
      storageRequired: false,
    });
  });

  it("maps mounted paths to storage-relative paths", () => {
    expect(mapSystemImportPaths(["/Volumes/nas/media/photo.jpg"], [mounted])).toEqual({
      selections: [{ storageId: "nas", path: "media/photo.jpg" }],
      invalidPaths: [],
      unmappedPaths: [],
      storageRequired: false,
    });
  });

  it("reports missing active storage separately from invalid paths", () => {
    expect(mapSystemImportPaths(["/tmp/report.pdf"], [])).toEqual({
      selections: [],
      invalidPaths: [],
      unmappedPaths: ["/tmp/report.pdf"],
      storageRequired: true,
    });
  });

  it("normalizes Windows separators and drive-letter case", () => {
    const windowsLocal = {
      ...local,
      id: "windows-local",
      root_path: "C:/Users/demo/Documents",
    };
    const result = mapSystemImportPaths(
      ["c:\\users\\demo\\documents\\report.pdf"],
      [windowsLocal],
    );

    expect(result.selections).toEqual([
      { storageId: "windows-local", path: "c:/users/demo/documents/report.pdf" },
    ]);
    expect(result.unmappedPaths).toEqual([]);
  });

  it("does not apply case-insensitive matching to POSIX roots", () => {
    const result = mapSystemImportPaths(["/volumes/nas/media/photo.jpg"], [mounted]);

    expect(result.selections).toEqual([]);
    expect(result.unmappedPaths).toEqual(["/volumes/nas/media/photo.jpg"]);
  });
});
