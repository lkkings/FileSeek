import { act, fireEvent, screen, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { renderWithI18n } from "../../../test/test-utils";
import type {
  EnhancedSearchProgressEvent,
  FileItem,
  SearchResponseData,
} from "../../../services/api/search";
import { SearchResultsView } from "./SearchResultsView";

const file: FileItem = {
  file_id: "file-1",
  file_name: "Result.pdf",
  file_type: "pdf",
  category: "document",
  path: "/documents/Result.pdf",
  size: 1024,
  modified: "2026-09-28T08:00:00Z",
  tags: ["旅行"],
  score: 1,
  metadata: null,
  chunks: null,
};

const data: SearchResponseData = {
  items: [file],
  total: 21,
  page_number: 1,
  page_size: 20,
  has_more: true,
  counter: {},
};

const progressEvents: EnhancedSearchProgressEvent[] = [
  { type: "status", phase: "starting", message: "正在理解搜索意图" },
  { type: "reasoning", content: "先按用户描述检索一次" },
  {
    type: "tool_call",
    round_number: 1,
    tool_name: "search_files",
    query: "旅行 猫",
    categories: ["image"],
  },
  {
    type: "tool_result",
    round_number: 1,
    tool_name: "search_files",
    candidate_count: 3,
    total: 3,
  },
];

async function longPress(row: Element) {
  fireEvent.touchStart(row);
  await act(async () => {
    vi.advanceTimersByTime(800);
  });
  fireEvent.touchEnd(row);
}

describe("SearchResultsView", () => {
  afterEach(() => vi.useRealTimers());

  it("renders a single shared file row without category tabs", () => {
    renderWithI18n(
      <SearchResultsView
        query="result"
        onNotice={() => undefined}
        data={data}
        status="success"
      />,
    );

    expect(screen.queryByRole("tab", { name: /全部/ })).not.toBeInTheDocument();
    expect(screen.queryByRole("tab", { name: /文档/ })).not.toBeInTheDocument();
    expect(screen.queryByRole("tab", { name: /图片/ })).not.toBeInTheDocument();
    expect(screen.queryByRole("tab", { name: /视频/ })).not.toBeInTheDocument();

    const rows = document.querySelectorAll(".result-list > .file-list-row");
    expect(rows).toHaveLength(1);
    expect(within(rows[0]!).getByText("Result.pdf")).toBeInTheDocument();
    expect(within(rows[0]!).getByText("2026-09-28 16:00:00")).toBeInTheDocument();
    expect(within(rows[0]!).getByText("0.0 MB")).toBeInTheDocument();
    expect(within(rows[0]!).getByText("旅行")).toBeInTheDocument();
    expect(screen.getByRole("group", { name: "分页" })).toBeInTheDocument();
  });

  it("renders pagination even when the search has only one page", () => {
    renderWithI18n(
      <SearchResultsView
        query="result"
        onNotice={() => undefined}
        data={{ ...data, total: 1, has_more: false }}
        status="success"
      />,
    );

    const pagination = screen.getByRole("group", { name: "分页" });
    expect(within(pagination).getByRole("button", { name: "1" })).toHaveClass("is-active");
    expect(within(pagination).getByRole("button", { name: "下一页" })).toBeDisabled();
  });

  it("renders a readable retrieval timeline while enhanced search is loading", () => {
    renderWithI18n(
      <SearchResultsView
        query="旅行 猫"
        onNotice={() => undefined}
        status="loading"
        progressEvents={progressEvents}
      />,
    );

    expect(screen.getByRole("heading", { name: "智能体检索中" })).toBeInTheDocument();
    expect(screen.getByText("先按用户描述检索一次")).toBeInTheDocument();
    expect(screen.getByText("正在执行文件搜索")).toBeInTheDocument();
    expect(screen.getByText("关键词：旅行 猫；类型：图片")).toBeInTheDocument();
    expect(screen.getByText("找到 3 个候选文件")).toBeInTheDocument();
    expect(screen.queryByText('{"query":"旅行 猫"}')).not.toBeInTheDocument();
    expect(screen.queryByText("search_files")).not.toBeInTheDocument();
    expect(screen.queryByText("加载中...")).not.toBeInTheDocument();
  });

  it("shows final non-empty results and keeps the process collapsed", () => {
    renderWithI18n(
      <SearchResultsView
        query="旅行 猫"
        onNotice={() => undefined}
        status="success"
        data={data}
        progressEvents={progressEvents}
      />,
    );

    expect(screen.getByText("Result.pdf")).toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "智能体检索中" })).not.toBeInTheDocument();
    const disclosure = screen.getByText("查看检索过程").closest("details");
    expect(disclosure).not.toHaveAttribute("open");
    fireEvent.click(screen.getByText("查看检索过程"));
    expect(screen.getByText("检索完成")).toBeInTheDocument();
    expect(screen.getByText("先按用户描述检索一次")).toBeInTheDocument();
  });

  it("shows the existing empty state after an empty final result", () => {
    renderWithI18n(
      <SearchResultsView
        query="不存在"
        onNotice={() => undefined}
        status="success"
        data={{ ...data, items: [], total: 0, has_more: false }}
        progressEvents={progressEvents}
      />,
    );

    expect(screen.getByText("没有找到匹配的文件")).toBeInTheDocument();
    expect(screen.getByText("查看检索过程")).toBeInTheDocument();
    expect(screen.queryByText("Result.pdf")).not.toBeInTheDocument();
  });

  it("shows a retrieval failure with the process available", () => {
    renderWithI18n(
      <SearchResultsView
        query="旅行 猫"
        onNotice={() => undefined}
        status="error"
        error="Agent 请求超时"
        progressEvents={progressEvents}
      />,
    );

    expect(screen.getAllByText("Agent 请求超时").length).toBeGreaterThan(0);
    fireEvent.click(screen.getByText("查看检索过程"));
    expect(screen.getByText("检索失败")).toBeInTheDocument();
    expect(screen.queryByText("Result.pdf")).not.toBeInTheDocument();
  });

  it("opens the file detail drawer after a single row click", async () => {
    vi.useFakeTimers();
    renderWithI18n(
      <SearchResultsView
        query="result"
        onNotice={() => undefined}
        data={data}
        status="success"
      />,
    );

    fireEvent.click(screen.getByText("Result.pdf").closest(".file-list-row")!);
    await act(async () => {
      vi.advanceTimersByTime(220);
    });

    const drawer = screen.getByRole("button", { name: /打开/ }).closest("aside")!;
    expect(within(drawer).getByText("文件详情")).toBeInTheDocument();
    expect(within(drawer).getByText("Result.pdf")).toBeInTheDocument();
  });

  it("shows the search hit in the detail drawer", async () => {
    vi.useFakeTimers();
    renderWithI18n(
      <SearchResultsView
        query="result"
        onNotice={() => undefined}
        data={{
          ...data,
          items: [
            {
              ...file,
              metadata: {
                text: "命中文本",
                page_number: 1,
                line_number: 1,
                chunk_index: 0,
              },
            },
          ],
        }}
        status="success"
      />,
    );

    fireEvent.click(screen.getByText("Result.pdf").closest(".file-list-row")!);
    await act(async () => {
      vi.advanceTimersByTime(220);
    });

    const drawer = screen.getByRole("button", { name: /打开/ }).closest("aside")!;
    expect(within(drawer).getByText("命中：命中文本（第 1 页，第 1 行，片段 0）")).toBeInTheDocument();
  });

  it("moves selected search results to the recycle callback and refreshes", async () => {
    vi.useFakeTimers();
    const onMoveToRecycle = vi.fn(async () => true);
    const onRefresh = vi.fn();
    renderWithI18n(
      <SearchResultsView
        query="result"
        onNotice={() => undefined}
        onMoveToRecycle={onMoveToRecycle}
        onRefresh={onRefresh}
        data={data}
        status="success"
      />,
    );

    await longPress(screen.getByText("Result.pdf").closest(".file-list-row")!);
    expect(screen.getByRole("button", { name: /移入回收站/ })).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: /移入回收站/ }));
    fireEvent.click(within(screen.getByRole("dialog")).getByRole("button", { name: /删除/ }));

    await act(async () => {
      await Promise.resolve();
    });

    expect(onMoveToRecycle).toHaveBeenCalledWith(["file-1"]);
    expect(onRefresh).toHaveBeenCalled();
    expect(screen.queryByRole("button", { name: /移入回收站/ })).not.toBeInTheDocument();
  });

  it("keeps selection and the recycle dialog available when the operation fails", async () => {
    vi.useFakeTimers();
    const onMoveToRecycle = vi.fn(async () => false);
    renderWithI18n(
      <SearchResultsView
        query="result"
        onNotice={() => undefined}
        onMoveToRecycle={onMoveToRecycle}
        data={data}
        status="success"
      />,
    );

    await longPress(screen.getByText("Result.pdf").closest(".file-list-row")!);
    fireEvent.click(screen.getByRole("button", { name: /移入回收站/ }));
    fireEvent.click(within(screen.getByRole("dialog")).getByRole("button", { name: /删除/ }));

    await act(async () => {
      await Promise.resolve();
    });

    expect(screen.getByRole("dialog")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /移入回收站/ })).toBeInTheDocument();
  });

  it("moves selected search results to a chosen folder and refreshes", async () => {
    vi.useFakeTimers();
    const onMoveToFolder = vi.fn(async () => true);
    const onRefresh = vi.fn();
    renderWithI18n(
      <SearchResultsView
        query="result"
        onNotice={() => undefined}
        onMoveToFolder={onMoveToFolder}
        folders={[
          { id: "folder-1", name: "当前范围" },
          { id: "folder-2", name: "目标文件夹" },
        ]}
        searchScopeFolderId="folder-1"
        onRefresh={onRefresh}
        data={data}
        status="success"
      />,
    );

    await longPress(screen.getByText("Result.pdf").closest(".file-list-row")!);
    fireEvent.click(screen.getByRole("button", { name: /移动到/ }));
    const dialog = screen.getByRole("dialog");
    expect(within(dialog).queryByText("当前范围")).not.toBeInTheDocument();
    fireEvent.click(within(dialog).getByRole("radio", { name: /目标文件夹/ }));
    fireEvent.click(within(dialog).getByRole("button", { name: /确认移动/ }));

    await act(async () => {
      await Promise.resolve();
    });

    expect(onMoveToFolder).toHaveBeenCalledWith(["file-1"], "folder-2");
    expect(onRefresh).toHaveBeenCalled();
  });

  it("keeps selection and the move dialog available when the operation fails", async () => {
    vi.useFakeTimers();
    const onMoveToFolder = vi.fn(async () => false);
    renderWithI18n(
      <SearchResultsView
        query="result"
        onNotice={() => undefined}
        onMoveToFolder={onMoveToFolder}
        folders={[{ id: "folder-2", name: "目标文件夹" }]}
        data={data}
        status="success"
      />,
    );

    await longPress(screen.getByText("Result.pdf").closest(".file-list-row")!);
    fireEvent.click(screen.getByRole("button", { name: /移动到/ }));
    fireEvent.click(within(screen.getByRole("dialog")).getByRole("radio", { name: /目标文件夹/ }));
    fireEvent.click(within(screen.getByRole("dialog")).getByRole("button", { name: /确认移动/ }));

    await act(async () => {
      await Promise.resolve();
    });

    expect(screen.getByRole("dialog")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /移动到/ })).toBeInTheDocument();
  });

  it("requests another page through the shared pagination component", () => {
    const onPageChange = vi.fn();
    renderWithI18n(
      <SearchResultsView
        query="result"
        onNotice={() => undefined}
        onPageChange={onPageChange}
        currentPage={1}
        pageSize={20}
        totalItems={21}
        data={data}
        status="success"
      />,
    );

    const pagination = screen.getByRole("group", { name: "分页" });
    expect(document.querySelector(".pagination-total-items")).toHaveTextContent("共 21 条 / 2 页");
    fireEvent.click(within(pagination).getByRole("button", { name: "2" }));

    expect(onPageChange).toHaveBeenCalledWith(2);
  });
});
