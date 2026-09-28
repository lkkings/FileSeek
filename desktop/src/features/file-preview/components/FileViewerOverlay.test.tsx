import { fireEvent, screen } from "@testing-library/react";
import type { FileSource } from "anyview";
import { describe, expect, it, vi } from "vitest";

import { FileViewerOverlay } from "./FileViewerOverlay";
import type { FilePreviewItem } from "../types";
import { renderWithI18n } from "../../../test/test-utils";
import { activateLocale, defaultLocale } from "../../../i18n/i18n";

const anyviewMock = vi.hoisted(() => ({
  DocViewer: ({
    source,
    showToolbar,
    showSidebar,
    persistKey,
  }: {
    source?: FileSource;
    showToolbar?: boolean;
    showSidebar?: boolean;
    persistKey?: string;
  }) => (
    <div
      data-testid="anyview-document"
      data-url={source?.kind === "url" ? source.url : undefined}
      data-show-toolbar={showToolbar}
      data-show-sidebar={showSidebar}
      data-persist-key={persistKey}
    />
  ),
}));

const videojsMock = vi.hoisted(() => {
  const dispose = vi.fn();
  return { dispose, create: vi.fn(() => ({ dispose })) };
});

vi.mock("anyview", () => anyviewMock);
vi.mock("video.js", () => ({ default: videojsMock.create }));

function createItem(fileType: FilePreviewItem["fileType"], fileName: string): FilePreviewItem {
  return { fileId: "file-1", fileName, fileType };
}

describe("FileViewerOverlay", () => {
  it("opens documents with full AnyView chrome", () => {
    renderWithI18n(
      <FileViewerOverlay isOpen item={createItem("document", "report.pdf")} onClose={() => undefined} />,
    );

    const viewer = screen.getByTestId("anyview-document");
    expect(viewer).toHaveAttribute("data-url", "/api/v1/library/files/preview/file-1");
    expect(viewer).toHaveAttribute("data-show-toolbar", "true");
    expect(viewer).toHaveAttribute("data-show-sidebar", "true");
    expect(viewer).toHaveAttribute("data-persist-key", "file-preview-file-1");
  });

  it("opens the original image in a full-screen viewer", () => {
    renderWithI18n(
      <FileViewerOverlay isOpen item={createItem("image", "photo.jpg")} onClose={() => undefined} />,
    );

    expect(screen.getByRole("img", { name: "photo.jpg" })).toHaveAttribute(
      "src",
      "/api/v1/library/files/preview/file-1",
    );
  });

  it("opens videos with video.js and disposes the player on unmount", () => {
    const { unmount } = renderWithI18n(
      <FileViewerOverlay isOpen item={createItem("video", "clip.mp4")} onClose={() => undefined} />,
    );

    const player = screen.getByTestId("viewer-video-player");
    expect(player).toHaveAttribute("src", "/api/v1/library/files/preview/file-1");
    expect(videojsMock.create).toHaveBeenCalledWith(
      player,
      expect.objectContaining({
        controls: true,
        poster: "/api/v1/library/files/file-1/thumbnail?size=detail",
      }),
    );

    unmount();

    expect(videojsMock.dispose).toHaveBeenCalled();
  });

  it("shows an unsupported state for legacy documents", () => {
    renderWithI18n(
      <FileViewerOverlay isOpen item={createItem("document", "legacy.doc")} onClose={() => undefined} />,
    );

    expect(screen.queryByTestId("anyview-document")).not.toBeInTheDocument();
    expect(screen.getByRole("img", { name: /DOC 文档（不支持预览）/ })).toBeInTheDocument();
  });

  it("renders localized viewer controls", () => {
    activateLocale("en-US");

    renderWithI18n(
      <FileViewerOverlay
        isOpen
        item={createItem("document", "legacy.doc")}
        onClose={() => undefined}
      />,
    );

    expect(screen.getByRole("dialog", { name: "File preview" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Close" })).toBeInTheDocument();

    activateLocale(defaultLocale);
  });

  it("closes the viewer with the Escape key", () => {
    const onClose = vi.fn();
    renderWithI18n(
      <FileViewerOverlay
        isOpen
        item={createItem("document", "legacy.doc")}
        onClose={onClose}
      />,
    );

    fireEvent.keyDown(screen.getByRole("dialog", { name: "文件预览" }), { key: "Escape" });

    expect(onClose).toHaveBeenCalledTimes(1);
  });
});
