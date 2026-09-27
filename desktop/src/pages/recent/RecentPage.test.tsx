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
  useRecordRecentAccess: () => ({ mutateAsync: vi.fn() }),
}));

describe("RecentPage", () => {
  afterEach(() => {
    vi.useRealTimers();
    mocks.reload.mockClear();
    mocks.deleteRecords.mutateAsync.mockClear();
  });

  it("long-press selects a record and batch deletion refreshes the list", async () => {
    vi.useFakeTimers();
    renderWithI18n(<RecentPage />);

    const row = screen.getByText("Recent.pdf").closest("article")!;
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
});
