import { act, fireEvent, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

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
import type { StorageLocation } from "../../settings/types";
import { useBatchImport } from "../hooks/useBatchImport";
import { ImportFileDialog } from "./ImportFileDialog";

vi.mock("../../../services/api/library", () => ({
  startBatchImport: vi.fn(async () => ({
    status: "success",
    data: { import_id: "import-1", total: 2 },
    error: null,
  })),
}));

vi.mock("../../../services/api/import-events", () => ({
  openImportEventStream: vi.fn(() => ({
    close: () => undefined,
    done: Promise.resolve(),
  })),
}));

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
];

function ImportFlowHarness() {
  const { state, start } = useBatchImport("folder-1");

  return (
    <ImportFileDialog
      folderName="工作资料"
      storageLocations={storageLocations}
      importState={state}
      onStart={start}
      onClose={() => undefined}
    />
  );
}

function event(id: number, type: ImportEvent["type"], payload: Record<string, unknown>): ImportEvent {
  return { id, type, payload };
}

describe("ImportFileDialog import flow", () => {
  beforeEach(() => {
    activateLocale(defaultLocale);
    vi.stubGlobal("fetch", vi.fn(async () => new Response(JSON.stringify({
      status: "success",
      data: {
        current_path: "/",
        entries: [
          { name: "missing.pdf", kind: "file", source_path: "/missing.pdf", size: 100, modified: "2026-01-01T00:00:00Z" },
          { name: "later.pdf", kind: "file", source_path: "/later.pdf", size: 200, modified: "2026-01-01T00:00:00Z" },
        ],
      },
      error: null,
    }), { status: 200 })));
  });

  afterEach(() => {
    vi.clearAllMocks();
    vi.unstubAllGlobals();
    activateLocale(defaultLocale);
  });

  it("browses, selects files, starts the batch, and renders streamed progress", async () => {
    renderWithProviders(<ImportFlowHarness />);

    fireEvent.click(await screen.findByRole("checkbox", { name: "missing.pdf" }));
    fireEvent.click(screen.getByRole("checkbox", { name: "later.pdf" }));
    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: "开始导入" }));
    });

    expect(vi.mocked(startBatchImport)).toHaveBeenCalledWith<Parameters<typeof startBatchImport>>({
      folderId: "folder-1",
      items: [
        { path: "/missing.pdf", storageId: "local" },
        { path: "/later.pdf", storageId: "local" },
      ],
    } satisfies BatchImportInput);
    expect(vi.mocked(openImportEventStream)).toHaveBeenCalledWith(
      "/api/v1/library/files/import/import-1/events",
      expect.objectContaining({ onEvent: expect.any(Function) }),
    );

    const callbacks = vi.mocked(openImportEventStream).mock.calls[0]?.[1] as ImportEventStreamCallbacks;
    await act(async () => {
      callbacks.onEvent(event(1, "batch_started", { total: 2 }));
      callbacks.onEvent(event(2, "item_started", { index: 0 }));
      callbacks.onEvent(event(3, "item_failed", { index: 0, error: "文件不存在" }));
      callbacks.onEvent(event(4, "item_started", { index: 1 }));
      callbacks.onEvent(event(5, "item_registered", { index: 1, file_id: "file-2", task_id: "task-2" }));
      callbacks.onEvent(event(6, "task_progress", { index: 1, progress: 50, stage: "生成索引" }));
    });

    expect(screen.getByText("文件不存在")).toBeInTheDocument();
    expect(screen.getByText("生成索引")).toBeInTheDocument();
    expect(screen.getByText("50%")).toBeInTheDocument();

    await act(async () => {
      callbacks.onEvent(event(7, "item_completed", { index: 1 }));
      callbacks.onEvent(event(8, "batch_completed", { total: 2, succeeded: 1, failed: 1 }));
    });

    expect(screen.getByText("已完成")).toBeInTheDocument();
    expect(screen.getByRole("progressbar")).toHaveAttribute("aria-valuenow", "100");
  });
});
