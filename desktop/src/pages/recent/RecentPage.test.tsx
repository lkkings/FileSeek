import { act, fireEvent, screen, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { renderWithI18n } from "../../test/test-utils";
import { RecentPage } from "./RecentPage";

const mocks = vi.hoisted(() => ({
  reload: vi.fn(),
  deleteRecords: {
    mutateAsync: vi.fn(async () => ({
      successCount: 1,
      failureCount: 0,
      failedRecordIds: [],
      errors: [],
    })),
  },
  recordAccess: {
    mutateAsync: vi.fn(async () => ({ status: "success", data: null, error: null })),
  },
}));

vi.mock("../../features/recent/hooks/useRecentAccess", () => ({
  useRecentAccess: () => ({
    data: {
      items: [
        {
          recordId: 42,
          fileId: "file-42",
          accessedAt: "2026-09-28T08:00:00Z",
          file: {
            file_id: "file-42",
            file_name: "Recent.pdf",
            file_type: "pdf",
            category: "document",
            path: "/documents/Recent.pdf",
            size: 1024,
            modified: "2026-09-28T08:00:00Z",
            tags: [],
            score: 0,
            metadata: null,
            chunks: null,
          },
        },
      ],
      pageNumber: 1,
      pageSize: 20,
      total: 1,
      hasMore: false,
    },
    loading: false,
    error: null,
    page: 1,
    setPage: vi.fn(),
    pageSize: 20,
    reload: mocks.reload,
    deleteRecords: mocks.deleteRecords,
  }),
}));

vi.mock("../../features/recent/hooks/useRecordRecentAccess", () => ({
  useRecordRecentAccess: () => mocks.recordAccess,
}));

vi.mock("anyview", () => ({
  DocViewer: ({ source }: { source?: { kind: string; url?: string } }) => (
    <div data-testid="anyview-document" data-url={source?.url} />
  ),
}));

vi.mock("video.js", () => ({
  default: vi.fn(() => ({ dispose: vi.fn() })),
}));

describe("RecentPage", () => {
  afterEach(() => {
    vi.useRealTimers();
    mocks.reload.mockClear();
    mocks.deleteRecords.mutateAsync.mockClear();
    mocks.recordAccess.mutateAsync.mockClear();
  });

  it("long-press selects a record and batch deletion refreshes the list", async () => {
    vi.useFakeTimers();
    renderWithI18n(<RecentPage />);

    const row = screen.getByText("Recent.pdf").closest(".file-list-row")!;
    fireEvent.touchStart(row);
    await act(async () => {
      vi.advanceTimersByTime(800);
    });
    fireEvent.touchEnd(row);

    fireEvent.click(screen.getByRole("button", { name: /删除/ }));
    fireEvent.click(within(screen.getByRole("dialog")).getByRole("button", { name: /删除/ }));
    await act(async () => {
      await Promise.resolve();
    });

    expect(mocks.deleteRecords.mutateAsync).toHaveBeenCalledWith([42]);
    expect(mocks.reload).toHaveBeenCalled();
    expect(screen.getByText(/已删除 1/)).toBeInTheDocument();
  });

  it("opens the file detail drawer after a single row click", async () => {
    vi.useFakeTimers();
    renderWithI18n(<RecentPage />);

    fireEvent.click(screen.getByText("Recent.pdf").closest(".file-list-row")!);
    await act(async () => {
      vi.advanceTimersByTime(220);
    });

    const drawer = screen.getByRole("button", { name: /打开/ }).closest("aside")!;
    expect(within(drawer).getByText("文件详情")).toBeInTheDocument();
    expect(within(drawer).getByText("Recent.pdf")).toBeInTheDocument();
  });

  it("opens the selected file in the in-app viewer", async () => {
    vi.useFakeTimers();
    renderWithI18n(<RecentPage />);

    fireEvent.click(screen.getByText("Recent.pdf").closest(".file-list-row")!);
    await act(async () => {
      vi.advanceTimersByTime(220);
    });

    fireEvent.click(screen.getByRole("button", { name: /打开/ }));
    await act(async () => {
      await Promise.resolve();
    });

    const viewer = screen.getByRole("dialog", { name: "文件预览" });
    expect(within(viewer).getByTestId("anyview-document")).toHaveAttribute(
      "data-url",
      "/api/v1/library/files/preview/file-42",
    );

    fireEvent.click(within(viewer).getByRole("button", { name: "关闭" }));
    expect(screen.queryByRole("dialog", { name: "文件预览" })).not.toBeInTheDocument();
    expect(mocks.recordAccess.mutateAsync).toHaveBeenCalledWith("file-42");
  });
});
