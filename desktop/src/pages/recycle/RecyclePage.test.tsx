import { act, fireEvent, screen, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { renderWithI18n } from "../../test/test-utils";
import { RecyclePage } from "./RecyclePage";

const mocks = vi.hoisted(() => ({
  reload: vi.fn(),
  deleteRecords: { mutateAsync: vi.fn(async () => ({ status: "success", data: null, error: null })) },
  restoreRecords: { mutateAsync: vi.fn(async () => ({ status: "success", data: null, error: null })) },
}));

vi.mock("../../features/recycle/hooks/useRecycleBin", () => ({
  useRecycleBin: () => ({
    data: {
      items: [
        {
          id: "item-1",
          original_file_id: "file-1",
          original_name: "Deleted.pdf",
          original_path: "/documents/Deleted.pdf",
          deleted_at: "2026-09-28T08:00:00Z",
          file_type: "pdf",
          size: "1024",
        },
      ],
      page_number: 1,
      page_size: 20,
      total: 1,
      has_more: false,
    },
    loading: false,
    error: null,
    page: 1,
    setPage: vi.fn(),
    pageSize: 20,
    reload: mocks.reload,
    deleteRecords: mocks.deleteRecords,
    restoreRecords: mocks.restoreRecords,
  }),
}));

async function selectFirstRow() {
  const row = screen.getByText("Deleted.pdf").closest("article")!;
  fireEvent.touchStart(row);
  await act(async () => {
    vi.advanceTimersByTime(800);
  });
  fireEvent.touchEnd(row);
}

describe("RecyclePage", () => {
  afterEach(() => {
    vi.useRealTimers();
    mocks.reload.mockClear();
    mocks.deleteRecords.mutateAsync.mockClear();
    mocks.restoreRecords.mutateAsync.mockClear();
  });

  it("permanently deletes selected recycle items", async () => {
    vi.useFakeTimers();
    renderWithI18n(<RecyclePage />);

    await selectFirstRow();
    fireEvent.click(screen.getByRole("button", { name: /永久删除/ }));
    fireEvent.click(within(screen.getByRole("dialog")).getByRole("button", { name: /删除/ }));
    await act(async () => {
      await Promise.resolve();
    });

    expect(mocks.deleteRecords.mutateAsync).toHaveBeenCalledWith(["item-1"]);
    expect(mocks.reload).toHaveBeenCalled();
    expect(screen.getByText(/已彻底删除 1/)).toBeInTheDocument();
  });

  it("restores selected recycle items", async () => {
    vi.useFakeTimers();
    renderWithI18n(<RecyclePage />);

    await selectFirstRow();
    fireEvent.click(screen.getByRole("button", { name: /恢复/ }));
    await act(async () => {
      await Promise.resolve();
    });

    expect(mocks.restoreRecords.mutateAsync).toHaveBeenCalledWith(["item-1"]);
    expect(mocks.reload).toHaveBeenCalled();
    expect(screen.getByText(/已恢复 1/)).toBeInTheDocument();
  });
});
