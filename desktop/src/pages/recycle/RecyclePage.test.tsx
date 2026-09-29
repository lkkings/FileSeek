import { act, fireEvent, screen, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { renderWithI18n } from "../../test/test-utils";
import { RecyclePage } from "./RecyclePage";

const mocks = vi.hoisted(() => ({
  reload: vi.fn(),
  deleteRecords: { mutateAsync: vi.fn(async () => ({ status: "success", data: null, error: null })) },
  restoreRecords: { mutateAsync: vi.fn(async () => ({ status: "success", data: null, error: null })) },
  recycleState: {
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
    reload: vi.fn(),
    deleteRecords: { mutateAsync: vi.fn(async () => ({ status: "success", data: null, error: null })) },
    restoreRecords: { mutateAsync: vi.fn(async () => ({ status: "success", data: null, error: null })) },
  },
  reset() {
    this.recycleState.data = {
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
    };
    this.recycleState.loading = false;
    this.recycleState.error = null;
    this.recycleState.page = 1;
  },
}));

vi.mock("../../features/recycle/hooks/useRecycleBin", () => ({
  useRecycleBin: () => ({
    ...mocks.recycleState,
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
    mocks.reset();
    mocks.reload.mockClear();
    mocks.deleteRecords.mutateAsync.mockClear();
    mocks.restoreRecords.mutateAsync.mockClear();
  });

  it("renders the populated recycle page with a dedicated header and summary", () => {
    renderWithI18n(<RecyclePage />);

    const summary = screen.getByLabelText("回收站摘要");

    expect(screen.getByRole("heading", { level: 1, name: "回收站" })).toBeInTheDocument();
    expect(screen.getByText("查看待恢复文件，恢复或永久删除选中的记录。")).toBeInTheDocument();
    expect(within(summary).getByText("总文件")).toBeInTheDocument();
    expect(within(summary).getByText("1")).toBeInTheDocument();
    expect(screen.getByText("Deleted.pdf")).toBeInTheDocument();
  });

  it("renders a dedicated empty state", () => {
    mocks.recycleState.data = {
      items: [],
      page_number: 1,
      page_size: 20,
      total: 0,
      has_more: false,
    };

    renderWithI18n(<RecyclePage />);

    expect(screen.getByRole("heading", { name: "回收站为空" })).toBeInTheDocument();
    expect(screen.getByText("没有等待恢复或永久删除的文件。")).toBeInTheDocument();
    expect(screen.queryByText("Deleted.pdf")).not.toBeInTheDocument();
  });

  it("renders loading without rows", () => {
    mocks.recycleState.loading = true;
    mocks.recycleState.data = null;

    renderWithI18n(<RecyclePage />);

    expect(screen.getByText("正在加载回收站...")).toBeInTheDocument();
    expect(screen.queryByText("Deleted.pdf")).not.toBeInTheDocument();
  });

  it("renders request errors without rows", () => {
    mocks.recycleState.error = "无法连接回收站";
    mocks.recycleState.data = null;

    renderWithI18n(<RecyclePage />);

    expect(screen.getByText("无法连接回收站")).toBeInTheDocument();
    expect(screen.queryByText("Deleted.pdf")).not.toBeInTheDocument();
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

  it("does not expose preview or detail entry points", async () => {
    vi.useFakeTimers();
    renderWithI18n(<RecyclePage />);

    await selectFirstRow();

    expect(screen.queryByText("文件详情")).not.toBeInTheDocument();
    expect(screen.queryByRole("dialog", { name: "文件预览" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /预览文件/ })).not.toBeInTheDocument();
  });
});
