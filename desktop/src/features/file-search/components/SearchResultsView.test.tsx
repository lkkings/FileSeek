import { act, fireEvent, screen, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { renderWithI18n } from "../../../test/test-utils";
import type { FileItem } from "../../../services/api/search";
import { SearchResultsView } from "./SearchResultsView";

const file: FileItem = {
  file_id: "file-1",
  file_name: "Result.pdf",
  file_type: "pdf",
  category: "document",
  path: "/documents/Result.pdf",
  size: 1024,
  modified: "2026-09-28T08:00:00Z",
  tags: [],
  score: 1,
  metadata: null,
  chunks: null,
};

describe("SearchResultsView", () => {
  afterEach(() => vi.useRealTimers());

  it("moves selected search results to the recycle callback and refreshes", async () => {
    vi.useFakeTimers();
    const onMoveToRecycle = vi.fn(async () => true);
    const onRefresh = vi.fn();
    renderWithI18n(
      <SearchResultsView
        query="result"
        onNotice={() => undefined}
        onMoveToRecycle={onMoveToRecycle}
        onOpenFile={() => undefined}
        onRefresh={onRefresh}
        data={{ items: [file], total: 1 }}
        status="success"
      />,
    );

    const row = screen.getAllByText("Result.pdf")[0]!.closest("article")!;
    expect(screen.getByRole("tab", { name: /全部/ })).toBeInTheDocument();
    expect(within(row).getByRole("button", { name: "预览文件" })).toBeInTheDocument();
    expect(within(row).getByRole("button", { name: "在文件夹中显示" })).toBeInTheDocument();
    expect(within(row).getByRole("button", { name: "打开文件" })).toBeInTheDocument();
    fireEvent.touchStart(row);
    await act(async () => {
      vi.advanceTimersByTime(800);
    });
    fireEvent.touchEnd(row);
    fireEvent.click(row);
    expect(screen.getByRole("button", { name: /移入回收站/ })).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: /移入回收站/ }));
    fireEvent.click(within(screen.getByRole("dialog")).getByRole("button", { name: /删除/ }));

    await act(async () => {
      await Promise.resolve();
    });

    expect(onMoveToRecycle).toHaveBeenCalledWith(["file-1"]);
    expect(onRefresh).toHaveBeenCalled();
  });
});
