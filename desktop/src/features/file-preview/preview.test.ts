import { describe, expect, it } from "vitest";

import {
  buildPreviewUrl,
  buildThumbnailUrl,
  buildOriginalFileUrl,
  getDocumentPreviewSupport,
  getImagePreviewSupport,
  getPreviewUrlOptions,
  getPreviewResourceKind,
  resolvePreviewCategory,
  resolvePreviewEnvironment,
} from "./preview";
import type { FilePreviewItem } from "./types";

function createItem(fileType: FilePreviewItem["fileType"], fileName: string): FilePreviewItem {
  return { fileId: "file-1", fileName, fileType };
}

describe("document preview classification", () => {
  it.each(["file.pdf", "file.docx", "file.xlsx", "file.pptx", "notes.txt"])(
    "identifies %s as supported",
    (fileName) => {
      expect(getDocumentPreviewSupport(createItem("document", fileName))).toBe("supported");
    },
  );

  it.each(["legacy.doc", "legacy.xls", "legacy.ppt", "document.xml", "document.odt", "document.odp", "document.ods", "document.rtf"])(
    "identifies %s as unsupported",
    (fileName) => {
      expect(getDocumentPreviewSupport(createItem("document", fileName))).toBe("unsupported");
    },
  );

  it("does not classify media files as documents", () => {
    expect(getDocumentPreviewSupport(createItem("image", "photo.jpg"))).toBeNull();
    expect(getDocumentPreviewSupport(createItem("video", "clip.mp4"))).toBeNull();
  });
});

describe("preview resource selection", () => {
  it("uses document resources for documents and thumbnails for media", () => {
    expect(getPreviewResourceKind(createItem("document", "file.pdf"))).toBe("document");
    expect(getPreviewResourceKind(createItem("image", "photo.jpg"))).toBe("thumbnail");
    expect(getPreviewResourceKind(createItem("video", "clip.mp4"))).toBe("thumbnail");
  });

  it.each(["photo.heic", "photo.heif", "graphic.svg"])(
    "identifies %s as unsupported without requesting thumbnails",
    (fileName) => {
      const item = createItem("image", fileName);
      expect(getImagePreviewSupport(item)).toBe("unsupported");
      expect(getPreviewResourceKind(item)).toBe("document");
    },
  );
});

describe("preview category resolution", () => {
  it("maps backend file types to preview categories", () => {
    expect(resolvePreviewCategory("pdf")).toBe("document");
    expect(resolvePreviewCategory("jpg")).toBe("image");
    expect(resolvePreviewCategory("mp4")).toBe("video");
    expect(resolvePreviewCategory(".PNG")).toBe("image");
    expect(resolvePreviewCategory("svg")).toBe("document");
    expect(resolvePreviewCategory("heic")).toBe("document");
  });
});

describe("preview URL construction", () => {
  it("uses relative API URLs in browser development", () => {
    const item = createItem("video", "clip.mp4");

    const url = buildPreviewUrl(item, "detail", { environment: "browser" });

    expect(url).toBe("/api/v1/library/files/file-1/thumbnail?size=detail");
  });

  it("uses the Tauri preview protocol in packaged desktop builds", () => {
    const item = createItem("document", "report.pdf");

    const url = buildPreviewUrl(item, "list", { environment: "tauri-packaged", platform: "macos" });

    expect(url).toBe("fileseek-preview://localhost/api/v1/library/files/preview/file-1");
  });

  it("uses the Windows-compatible Tauri protocol form", () => {
    const item = createItem("image", "photo.jpg");

    const url = buildPreviewUrl(item, "list", { environment: "tauri-packaged", platform: "windows" });

    expect(url).toBe("http://fileseek-preview.localhost/api/v1/library/files/file-1/thumbnail?size=list");
  });

  it("encodes file identifiers and requests the list thumbnail size", () => {
    const item = createItem("image", "photo.jpg");

    const url = buildPreviewUrl({ ...item, fileId: "file/1" }, "list");

    expect(url).toBe("/api/v1/library/files/file%2F1/thumbnail?size=list");
  });

  it("builds an original-file URL for inline video playback", () => {
    const item = createItem("video", "clip.mp4");

    expect(buildOriginalFileUrl({ ...item, fileId: "file/1" })).toBe(
      "/api/v1/library/files/preview/file%2F1",
    );
  });

  it("builds a thumbnail URL without changing PDF preview URLs", () => {
    const item = createItem("document", "report.pdf");

    expect(buildThumbnailUrl(item, "list", { environment: "browser" })).toBe(
      "/api/v1/library/files/file-1/thumbnail?size=list",
    );
    expect(buildPreviewUrl(item, "list", { environment: "browser" })).toBe(
      "/api/v1/library/files/preview/file-1",
    );
  });
});

describe("preview environment resolution", () => {
  it("distinguishes browser, Tauri development, and packaged Tauri modes", () => {
    expect(resolvePreviewEnvironment({ isTauri: false, isDevelopment: true })).toBe("browser");
    expect(resolvePreviewEnvironment({ isTauri: true, isDevelopment: true })).toBe("tauri-development");
    expect(resolvePreviewEnvironment({ isTauri: true, isDevelopment: false })).toBe("tauri-packaged");
  });

  it("uses the Vite proxy for Tauri development and custom protocol for packaged builds", () => {
    const development = getPreviewUrlOptions({ isTauri: true, isDevelopment: true, platform: "macos" });
    const packaged = getPreviewUrlOptions({ isTauri: true, isDevelopment: false, platform: "macos" });

    expect(buildOriginalFileUrl(createItem("video", "clip.mp4"), development)).toBe(
      "/api/v1/library/files/preview/file-1",
    );
    expect(buildOriginalFileUrl(createItem("video", "clip.mp4"), packaged)).toBe(
      "fileseek-preview://localhost/api/v1/library/files/preview/file-1",
    );
  });
});
