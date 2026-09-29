import { act, fireEvent, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { activateLocale, defaultLocale } from "../../../i18n/i18n";
import { renderWithProviders } from "../../../test/test-utils";
import {
  startBatchImport,
  type BatchImportInput,
} from "../../../services/api/library";
import {
  openImportEventStream,
  type ImportEvent,
  type ImportEventStreamCallbacks,
} from "../../../services/api/import-events";
import { useBatchImport } from "../hooks/useBatchImport";
import { SystemImportDialog } from "./SystemImportDialog";

vi.mock("../../../services/api/library", () => ({
  startBatchImport: vi.fn(async () => ({
    status: "success",
    data: { import_id: "import-1", total: 1 },
    error: null,
  })),
}));

vi.mock("../../../services/api/import-events", () => ({
  openImportEventStream: vi.fn(() => ({
    close: () => undefined,
    done: Promise.resolve(),
  })),
}));

function Harness() {
  const { state, start } = useBatchImport("folder-1");

  return (
    <SystemImportDialog
      requestPaths={["/tmp/report.pdf"]}
      requestErrors={[]}
      selections={[{ storageId: "local", path: "/tmp/report.pdf" }]}
      invalidPaths={[]}
      unmappedPaths={[]}
      storageRequired={false}
      folders={[
        {
          id: "folder-1",
          name: "工作资料",
          iconType: "work",
          description: "",
          modified: "2026-01-01T00:00:00Z",
          fileCount: 0,
        },
      ]}
      foldersLoading={false}
      foldersError={null}
      importState={state}
      onConfirm={(folderId) => start([{ storageId: "local", path: "/tmp/report.pdf" }], folderId)}
      onRetry={() => undefined}
      onClose={() => undefined}
    />
  );
}

function event(id: number, type: ImportEvent["type"], payload: Record<string, unknown>) {
  return { id, type, payload };
}

describe("SystemImportDialog integration", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    activateLocale(defaultLocale);
  });

  it("confirms a folder and starts the existing batch import", async () => {
    renderWithProviders(<Harness />);
    fireEvent.click(screen.getByRole("radio", { name: "工作资料" }));
    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: "开始导入" }));
    });

    expect(vi.mocked(startBatchImport)).toHaveBeenCalledWith<Parameters<typeof startBatchImport>>({
      folderId: "folder-1",
      items: [{ path: "/tmp/report.pdf", storageId: "local" }],
    } satisfies BatchImportInput);
    expect(vi.mocked(openImportEventStream)).toHaveBeenCalledWith(
      "/api/v1/library/files/import/import-1/events",
      expect.anything(),
    );
  });

  it("renders per-item failure from the existing SSE stream", async () => {
    renderWithProviders(<Harness />);
    fireEvent.click(screen.getByRole("radio", { name: "工作资料" }));
    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: "开始导入" }));
    });

    const callbacks = vi.mocked(openImportEventStream).mock.calls[0]?.[1] as ImportEventStreamCallbacks;
    await act(async () => {
      callbacks.onEvent(event(1, "item_failed", { index: 0, error: "文件不存在" }));
    });

    expect(screen.getByText("文件不存在")).toBeInTheDocument();
  });

  it("renders stream failures without hiding the dialog", async () => {
    renderWithProviders(<Harness />);
    fireEvent.click(screen.getByRole("radio", { name: "工作资料" }));
    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: "开始导入" }));
    });

    const callbacks = vi.mocked(openImportEventStream).mock.calls[0]?.[1] as ImportEventStreamCallbacks;
    await act(async () => {
      callbacks.onError();
    });

    expect(screen.getByText("导入进度连接失败")).toBeInTheDocument();
  });
});
