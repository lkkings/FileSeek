import { fireEvent, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import type { FileSource } from "anyview";

import { FileDetailDrawer } from "./FileDetailDrawer";
import type { FileItem } from "../services/api/search";
import { renderWithI18n } from "../test/test-utils";
import { activateLocale, defaultLocale } from "../i18n/i18n";

const file: FileItem = {
  file_id: "file-1",
  file_name: "Details.pdf",
  file_type: "pdf",
  category: "document",
  path: "/documents/Details.pdf",
  size: 1024,
  modified: "2026-09-28T08:00:00Z",
  tags: [],
  score: 0,
  metadata: null,
  chunks: null,
};

const unsupportedFile: FileItem = {
  ...file,
  file_name: "Legacy.doc",
  file_type: "doc",
};

const imageFile: FileItem = {
  ...file,
  file_name: "Photo.jpg",
  file_type: "jpg",
  category: "image",
};

const videoFile: FileItem = {
  ...file,
  file_name: "Clip.mp4",
  file_type: "mp4",
  category: "video",
};

const videojsMock = vi.hoisted(() => {
  const dispose = vi.fn();
  return { dispose, create: vi.fn(() => ({ dispose })) };
});

vi.mock("video.js", () => ({
  default: videojsMock.create,
}));

vi.mock("anyview", () => ({
  DocViewer: ({ source, page, showToolbar, showSidebar }: {
    source?: FileSource;
    page?: number;
    showToolbar?: boolean;
    showSidebar?: boolean;
  }) => (
    <div
      data-testid="anyview-document"
      data-page={page}
      data-show-toolbar={showToolbar}
      data-show-sidebar={showSidebar}
      data-url={source?.kind === "url" ? source.url : undefined}
    />
  ),
}));

describe("FileDetailDrawer", () => {
  it("passes the selected file to the open callback", () => {
    const onOpenAction = vi.fn();
    renderWithI18n(
      <FileDetailDrawer isOpen onClose={() => undefined} file={file} onOpenAction={onOpenAction} />,
    );

    fireEvent.click(screen.getByRole("button", { name: /打开/ }));

    expect(onOpenAction).toHaveBeenCalledWith(file);
  });

  it("renders the first document page with viewer chrome disabled", () => {
    renderWithI18n(<FileDetailDrawer isOpen onClose={() => undefined} file={file} />);

    const viewer = screen.getByTestId("anyview-document");
    expect(viewer).toHaveAttribute("data-url", "/api/v1/library/files/preview/file-1");
    expect(viewer).toHaveAttribute("data-page", "0");
    expect(viewer).toHaveAttribute("data-show-toolbar", "false");
    expect(viewer).toHaveAttribute("data-show-sidebar", "false");
  });

  it("renders a format-specific unsupported document state", () => {
    renderWithI18n(<FileDetailDrawer isOpen onClose={() => undefined} file={unsupportedFile} />);

    expect(screen.queryByTestId("anyview-document")).not.toBeInTheDocument();
    expect(screen.getByRole("img", { name: /DOC 文档（不支持预览）/ })).toBeInTheDocument();
    expect(screen.getByText("该格式暂不支持预览")).toBeInTheDocument();
  });

  it("renders the detail image thumbnail", () => {
    renderWithI18n(<FileDetailDrawer isOpen onClose={() => undefined} file={imageFile} />);

    expect(screen.getByRole("img", { name: "Photo.jpg" })).toHaveAttribute(
      "src",
      "/api/v1/library/files/file-1/thumbnail?size=detail",
    );
  });

  it("mounts and disposes the inline video player on demand", () => {
    const { unmount } = renderWithI18n(
      <FileDetailDrawer isOpen onClose={() => undefined} file={videoFile} />,
    );

    expect(screen.getByRole("img", { name: "Clip.mp4" })).toHaveAttribute(
      "src",
      "/api/v1/library/files/file-1/thumbnail?size=detail",
    );

    fireEvent.click(screen.getByRole("button", { name: "播放视频" }));

    const player = screen.getByTestId("drawer-video-player");
    expect(player).toHaveAttribute("src", "/api/v1/library/files/preview/file-1");
    expect(videojsMock.create).toHaveBeenCalledWith(player, expect.objectContaining({ controls: true }));

    unmount();

    expect(videojsMock.dispose).toHaveBeenCalled();
  });

  it("renders a localized video playback control", () => {
    activateLocale("en-US");

    renderWithI18n(<FileDetailDrawer isOpen onClose={() => undefined} file={videoFile} />);

    expect(screen.getByRole("button", { name: "Play video" })).toBeInTheDocument();

    activateLocale(defaultLocale);
  });

  it("supports activating video playback with the keyboard", async () => {
    renderWithI18n(<FileDetailDrawer isOpen onClose={() => undefined} file={videoFile} />);

    await userEvent.setup().type(screen.getByRole("button", { name: "播放视频" }), "{enter}");

    expect(screen.getByTestId("drawer-video-player")).toBeInTheDocument();
  });
});
