import { screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { DocumentFormatIcon } from "./DocumentFormatIcon";
import { getInitialPreviewStatus } from "../state";
import type { FilePreviewItem } from "../types";
import { renderWithI18n } from "../../../test/test-utils";
import { activateLocale, defaultLocale } from "../../../i18n/i18n";

describe("DocumentFormatIcon", () => {
  it.each(["file.pdf", "file.docx", "file.xlsx", "file.pptx", "notes.txt"])(
    "identifies the format for %s",
    (fileName) => {
      renderWithI18n(<DocumentFormatIcon fileName={fileName} />);

      expect(screen.getByRole("img", { name: new RegExp(fileName.split(".")[1] ?? "", "i") })).toBeInTheDocument();
    },
  );

  it("marks unsupported legacy formats", () => {
    renderWithI18n(<DocumentFormatIcon fileName="document.xml" isUnsupported />);

    expect(screen.getByRole("img", { name: /XML 文档（不支持预览）/ })).toBeInTheDocument();
  });

  it("renders localized document labels", () => {
    activateLocale("en-US");

    renderWithI18n(<DocumentFormatIcon fileName="legacy.doc" isUnsupported />);

    expect(screen.getByRole("img", { name: "DOC document (preview unsupported)" })).toBeInTheDocument();

    activateLocale(defaultLocale);
  });
});

describe("preview state helpers", () => {
  it("starts supported documents and media in loading state", () => {
    expect(getInitialPreviewStatus({ fileId: "1", fileName: "file.pdf", fileType: "document" })).toBe("loading");
    expect(getInitialPreviewStatus({ fileId: "2", fileName: "photo.jpg", fileType: "image" })).toBe("loading");
    expect(getInitialPreviewStatus({ fileId: "3", fileName: "clip.mp4", fileType: "video" })).toBe("loading");
  });

  it("starts unsupported documents in unsupported state", () => {
    const item: FilePreviewItem = { fileId: "1", fileName: "legacy.doc", fileType: "document" };

    expect(getInitialPreviewStatus(item)).toBe("unsupported");
  });
});
