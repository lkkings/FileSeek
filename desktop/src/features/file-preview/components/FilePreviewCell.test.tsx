import { fireEvent, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { FilePreviewCell } from "./FilePreviewCell";
import type { FilePreviewItem } from "../types";
import { renderWithI18n } from "../../../test/test-utils";
import { activateLocale, defaultLocale } from "../../../i18n/i18n";

function createItem(fileType: FilePreviewItem["fileType"], fileName: string): FilePreviewItem {
  return { fileId: "file-1", fileName, fileType };
}

describe("FilePreviewCell", () => {
  it("renders a PDF format document icon", () => {
    renderWithI18n(<FilePreviewCell item={createItem("document", "report.pdf")} />);

    expect(screen.getByRole("img", { name: "PDF 文档" })).toBeInTheDocument();
  });

  it("renders an unsupported legacy document state", () => {
    renderWithI18n(<FilePreviewCell item={createItem("document", "legacy.doc")} />);

    expect(screen.getByRole("img", { name: /DOC 文档（不支持预览）/ })).toBeInTheDocument();
    expect(screen.getByText("该格式暂不支持预览")).toBeInTheDocument();
  });

  it("lazy-loads an image thumbnail", () => {
    renderWithI18n(<FilePreviewCell item={createItem("image", "photo.jpg")} />);

    const image = screen.getByRole("img", { name: "photo.jpg" });
    expect(image).toHaveAttribute("loading", "lazy");
    expect(image).toHaveAttribute("src", "/api/v1/library/files/file-1/thumbnail?size=list");
  });

  it("renders a video thumbnail with playback affordance", () => {
    renderWithI18n(<FilePreviewCell item={createItem("video", "clip.mp4")} />);

    const image = screen.getByRole("img", { name: "clip.mp4" });
    expect(image).toHaveAttribute("src", "/api/v1/library/files/file-1/thumbnail?size=list");
    expect(document.querySelector(".file-preview-play-affordance")).toBeInTheDocument();
  });

  it("shows a fallback state when the thumbnail fails", () => {
    renderWithI18n(<FilePreviewCell item={createItem("image", "photo.jpg")} />);

    fireEvent.error(screen.getByRole("img", { name: "photo.jpg" }));

    expect(screen.getByRole("alert")).toHaveTextContent("预览加载失败");
    expect(screen.queryByRole("img", { name: "photo.jpg" })).not.toBeInTheDocument();
  });

  it("renders localized loading and unsupported states", () => {
    activateLocale("en-US");

    const { unmount } = renderWithI18n(
      <FilePreviewCell item={createItem("image", "photo.jpg")} />,
    );
    expect(screen.getByRole("status")).toHaveTextContent("Loading preview");

    unmount();
    renderWithI18n(
      <FilePreviewCell item={createItem("document", "legacy.doc")} />,
    );
    expect(screen.getByRole("status")).toHaveTextContent("This format cannot be previewed yet");

    activateLocale(defaultLocale);
  });
});
