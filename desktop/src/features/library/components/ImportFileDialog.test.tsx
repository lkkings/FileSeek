import { fireEvent, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { activateLocale, defaultLocale } from "../../../i18n/i18n";
import { renderWithProviders } from "../../../test/test-utils";
import type { StorageLocation } from "../../settings/types";
import type { BatchImportState, ImportFileSelection } from "../types";
import { ImportFileDialog } from "./ImportFileDialog";

const storageLocations: StorageLocation[] = [
  {
    id: "local",
    type: "local",
    name: "本地存储",
    protocol: "file",
    endpoint: "file://localhost",
    root_path: "/",
    account: null,
    status: "active",
    is_system: true,
  },
  {
    id: "nas",
    type: "nas",
    name: "家庭 NAS",
    protocol: "mounted",
    endpoint: "/Volumes/nas",
    root_path: "/Volumes/nas",
    account: null,
    status: "active",
    is_system: false,
  },
];

function createDirectoryResponse(locationId: string, path: string) {
  if (locationId === "nas") {
    return new Response(JSON.stringify({
      status: "success",
      data: {
        current_path: "",
        entries: [
          { name: "Photos", kind: "directory", source_path: "Photos", size: 0, modified: "2026-01-01T00:00:00Z" },
          { name: "nas-root.jpg", kind: "file", source_path: "nas-root.jpg", size: 400, modified: "2026-01-01T00:00:00Z" },
        ],
      },
      error: null,
    }), { status: 200 });
  }

  const entries = path === "/documents"
    ? [
      { name: "document.pdf", kind: "file", source_path: "/documents/document.pdf", size: 300, modified: "2026-01-01T00:00:00Z" },
    ]
    : [
      { name: "documents", kind: "directory", source_path: "/documents", size: 0, modified: "2026-01-01T00:00:00Z" },
      { name: "root-a.pdf", kind: "file", source_path: "/root-a.pdf", size: 100, modified: "2026-01-01T00:00:00Z" },
      { name: "root-b.pdf", kind: "file", source_path: "/root-b.pdf", size: 200, modified: "2026-01-01T00:00:00Z" },
    ];
  return new Response(
    JSON.stringify({ status: "success", data: { current_path: path, entries }, error: null }),
    { status: 200 },
  );
}

function renderDialog({
  importState,
  onStart = vi.fn(async () => true),
  onClose = vi.fn(),
}: {
  importState?: BatchImportState;
  onStart?: (selections: ImportFileSelection[]) => Promise<boolean>;
  onClose?: () => void;
} = {}) {
  return renderWithProviders(
    <ImportFileDialog
      folderName="工作资料"
      storageLocations={storageLocations}
      importState={importState ?? {
        importId: null,
        status: "idle",
        total: 0,
        succeeded: 0,
        failed: 0,
        items: [],
        error: null,
      }}
      onStart={onStart}
      onClose={onClose}
    />,
  );
}

function getSelectedCount(count: number) {
  return screen.getByText(
    (_, element) =>
      element?.classList.contains("import-selected-count") === true &&
      element.textContent === `已选择 ${count}`,
  );
}

describe("ImportFileDialog", () => {
  beforeEach(() => {
    vi.stubGlobal("fetch", vi.fn(async (_input: RequestInfo | URL) => {
      const path = new URL(String(_input), "http://localhost").searchParams.get("path") ?? "";
      const locationId = String(_input).includes("/nas/") ? "nas" : "local";
      return createDirectoryResponse(locationId, path);
    }));
    activateLocale(defaultLocale);
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    activateLocale(defaultLocale);
  });

  it("switches storage tabs and navigates directories", async () => {
    renderDialog();

    expect(await screen.findByText("root-a.pdf")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("tab", { name: "家庭 NAS" }));
    expect(await screen.findByText("nas-root.jpg")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("tab", { name: "本地存储" }));
    expect(await screen.findByRole("button", { name: "documents" }));

    fireEvent.click(screen.getByRole("button", { name: "documents" }));
    expect(await screen.findByText("document.pdf")).toBeInTheDocument();
    await waitFor(() => expect(screen.getByLabelText("路径")).toHaveValue("/documents"));
    expect(fetch).toHaveBeenCalledWith(
      "/api/v1/settings/storage-locations/local/directory?path=%2Fdocuments",
      expect.objectContaining({ method: "GET" }),
    );
  });

  it("shows the storage's current path and supports parent and pasted-path navigation", async () => {
    renderDialog();

    fireEvent.click(await screen.findByRole("button", { name: "documents" }));
    const pathInput = await screen.findByLabelText("路径");
    await waitFor(() => expect(pathInput).toHaveValue("/documents"));

    fireEvent.click(screen.getByRole("button", { name: "返回上一级" }));
    expect(await screen.findByLabelText("路径")).toHaveValue("/");
    expect(fetch).toHaveBeenCalledWith(
      "/api/v1/settings/storage-locations/local/directory?path=%2F",
      expect.objectContaining({ method: "GET" }),
    );

    fireEvent.change(screen.getByLabelText("路径"), { target: { value: "/pasted" } });
    fireEvent.submit(screen.getByLabelText("路径").closest("form")!);

    expect(await screen.findByLabelText("路径")).toHaveValue("/pasted");
    expect(fetch).toHaveBeenLastCalledWith(
      "/api/v1/settings/storage-locations/local/directory?path=%2Fpasted",
      expect.objectContaining({ method: "GET" }),
    );
  });

  it("uses the path returned by the backend when the request path is empty", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => new Response(JSON.stringify({
      status: "success",
      data: {
        current_path: "/home/fileseek",
        entries: [],
      },
      error: null,
    }), { status: 200 })));
    renderDialog();

    await waitFor(() => expect(screen.getByLabelText("路径")).toHaveValue("/home/fileseek"));
  });

  it("keeps selections while navigating and switching storage", async () => {
    renderDialog();

    fireEvent.click(await screen.findByRole("checkbox", { name: "root-a.pdf" }));
    fireEvent.click(screen.getByRole("button", { name: "documents" }));
    expect(await screen.findByText("document.pdf")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("checkbox", { name: "document.pdf" }));
    fireEvent.click(screen.getByRole("tab", { name: "家庭 NAS" }));
    fireEvent.click(await screen.findByRole("checkbox", { name: "nas-root.jpg" }));

    expect(getSelectedCount(3)).toBeInTheDocument();
  });

  it("selects all files and inverts the current selection", async () => {
    renderDialog();

    await screen.findByText("root-a.pdf");
    fireEvent.click(screen.getByRole("checkbox", { name: "root-b.pdf" }));
    fireEvent.click(screen.getByRole("button", { name: "反选" }));
    expect(getSelectedCount(1)).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "全选" }));
    expect(getSelectedCount(2)).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "反选" }));
    expect(getSelectedCount(0)).toBeInTheDocument();
  });

  it("renders failed items without hiding later progress", () => {
    renderDialog({
      importState: {
        importId: "import-1",
        status: "running",
        total: 3,
        succeeded: 1,
        failed: 1,
        error: null,
        items: [
          { storageId: "local", path: "/first.pdf", state: "completed", fileId: "file-1", taskId: "task-1", error: null },
          { storageId: "local", path: "/missing.pdf", state: "failed", fileId: null, taskId: null, error: "文件不存在" },
          { storageId: "local", path: "/later.pdf", state: "processing", fileId: "file-3", taskId: "task-3", error: null },
        ],
      },
    });

    expect(screen.getByText("文件不存在")).toBeInTheDocument();
    expect(screen.getByText("处理中")).toBeInTheDocument();
  });

  it("closes with the dialog button and Escape key", () => {
    const onClose = vi.fn();
    renderDialog({ onClose });
    const dialog = screen.getByRole("dialog", { name: "导入文件到 工作资料" });

    fireEvent.keyDown(dialog, { key: "Escape" });
    expect(onClose).toHaveBeenCalledTimes(1);
    fireEvent.click(screen.getByRole("button", { name: "关闭" }));
    expect(onClose).toHaveBeenCalledTimes(2);
  });

  it("shows empty, error, and retry states", async () => {
    const fetchMock = vi.fn(async () => new Response(JSON.stringify({ status: "error", data: null, error: "目录不可用" }), { status: 200 }));
    vi.stubGlobal("fetch", fetchMock);
    renderDialog();

    expect(await screen.findByText("目录不可用")).toBeInTheDocument();
    fetchMock.mockResolvedValue(new Response(JSON.stringify({
      status: "success",
      data: { current_path: "", entries: [] },
      error: null,
    }), { status: 200 }));
    fireEvent.click(screen.getByRole("button", { name: "重新加载" }));
    expect(await screen.findByText("此目录没有内容")).toBeInTheDocument();
  });

  it("renders accessible English labels", async () => {
    activateLocale("en-US");
    renderDialog();

    expect(screen.getByRole("dialog", { name: "Import files to 工作资料" })).toBeInTheDocument();
    expect(await screen.findByText("Select all")).toBeInTheDocument();
    expect(screen.getByRole("tablist", { name: "Storage locations" })).toBeInTheDocument();
  });
});
