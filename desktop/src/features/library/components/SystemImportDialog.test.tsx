import { cleanup, fireEvent, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { activateLocale, defaultLocale, type SupportedLocale } from "../../../i18n/i18n";
import { renderWithProviders } from "../../../test/test-utils";
import type { BatchImportState, FolderRecord } from "../types";
import { SystemImportDialog } from "./SystemImportDialog";

const folders: FolderRecord[] = [
  {
    id: "folder-1",
    name: "工作资料",
    iconType: "work",
    description: "工作文件",
    modified: "2026-01-01T00:00:00Z",
    fileCount: 0,
  },
];

const idleState: BatchImportState = {
  importId: null,
  status: "idle",
  total: 0,
  succeeded: 0,
  failed: 0,
  items: [],
  error: null,
};

function renderDialog(overrides: Partial<Parameters<typeof SystemImportDialog>[0]> = {}) {
  const onConfirm = vi.fn(async () => true);
  const onClose = vi.fn();
  const onRetry = vi.fn();
  const props = {
    requestPaths: ["/tmp/report.pdf", "/tmp/photo.jpg"],
    requestErrors: [],
    selections: [
      { storageId: "local", path: "/tmp/report.pdf" },
      { storageId: "local", path: "/tmp/photo.jpg" },
    ],
    invalidPaths: [],
    unmappedPaths: [],
    storageRequired: false,
    folders,
    foldersLoading: false,
    foldersError: null,
    importState: idleState,
    onConfirm,
    onRetry,
    onClose,
    ...overrides,
  };

  renderWithProviders(<SystemImportDialog {...props} />);
  return { onConfirm, onClose, onRetry };
}

describe("SystemImportDialog", () => {
  beforeEach(() => {
    activateLocale(defaultLocale);
  });

  afterEach(() => {
    cleanup();
    activateLocale(defaultLocale);
  });

  it.each([
    ["zh-CN", "添加文件到 FileSeek"],
    ["en-US", "Add files to FileSeek"],
  ] as [SupportedLocale, string][])("renders localized dialog in %s", (locale, title) => {
    activateLocale(locale);
    renderDialog();

    expect(screen.getByRole("dialog", { name: title })).toBeInTheDocument();
    expect(screen.getByText("/tmp/report.pdf")).toBeInTheDocument();
    expect(screen.getByText("/tmp/photo.jpg")).toBeInTheDocument();
  });

  it("shows loading and retry states for folders", () => {
    renderDialog({ foldersLoading: true });
    expect(screen.getByText("正在加载文件夹...")).toBeInTheDocument();

    cleanup();
    const { onRetry } = renderDialog({ foldersLoading: false, foldersError: "文件夹加载失败" });
    fireEvent.click(screen.getByRole("button", { name: "重新加载" }));
    expect(screen.getByText("文件夹加载失败")).toBeInTheDocument();
    expect(onRetry).toHaveBeenCalledOnce();
  });

  it("shows an empty-folder state and prevents confirmation", () => {
    renderDialog({ folders: [] });

    expect(screen.getByText("暂无可用文件夹")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "开始导入" })).toBeDisabled();
  });

  it("requires a folder selection, confirms, and cancels", async () => {
    const { onConfirm, onClose } = renderDialog();
    const confirm = screen.getByRole("button", { name: "开始导入" });
    expect(confirm).toBeDisabled();

    fireEvent.click(screen.getByRole("radio", { name: "工作资料" }));
    fireEvent.click(confirm);

    await screen.findByRole("button", { name: "取消" });
    fireEvent.click(screen.getByRole("button", { name: "取消" }));

    expect(onConfirm).toHaveBeenCalledWith("folder-1");
    expect(onClose).toHaveBeenCalled();
  });

  it("blocks imports for invalid and unmapped paths", () => {
    const { onConfirm } = renderDialog({
      selections: [],
      invalidPaths: ["/tmp/missing.pdf"],
      unmappedPaths: ["/Volumes/other/file.pdf"],
    });

    fireEvent.click(screen.getByRole("radio", { name: "工作资料" }));
    fireEvent.click(screen.getByRole("button", { name: "开始导入" }));

    expect(screen.getByText("/tmp/missing.pdf")).toBeInTheDocument();
    expect(screen.getByText("/Volumes/other/file.pdf")).toBeInTheDocument();
    expect(onConfirm).not.toHaveBeenCalled();
  });

  it("passes accessibility checks", async () => {
    const { container } = renderDialog();
    const { default: axe } = await import("axe-core");
    document.title = "FileSeek";
    document.documentElement.setAttribute("lang", "zh-CN");

    const results = await axe.run(container);
    expect(results.violations).toEqual([]);
  });
});
