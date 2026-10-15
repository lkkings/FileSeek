import { act, fireEvent, screen, within } from "@testing-library/react";
import type { ComponentProps } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { renderWithI18n } from "../../../test/test-utils";
import type { FileItem } from "../../../services/api/search";
import { FolderDetailsView as FolderDetailsViewImpl } from "./FolderDetailsView";

const mocks = vi.hoisted(() => ({
  reload: vi.fn(),
  refetchTags: vi.fn(),
  useFolderFiles: vi.fn(),
}));

const file: FileItem = {
  file_id: "file-1",
  file_name: "Folder.pdf",
  file_type: "pdf",
  category: "document",
  path: "/documents/Folder.pdf",
  size: 1024,
  modified: "2026-09-28T08:00:00Z",
  tags: ["文档"],
  score: 0,
  metadata: null,
  chunks: null,
};

const responseData = {
  items: [file],
  total: 24,
  page_number: 1,
  page_size: 12,
  has_more: true,
  counter: {
    document: 10,
    image: 8,
    video: 6,
  },
};

const currentFolder = {
  id: "folder-1",
  name: "Documents",
  iconType: "folder",
  description: "",
  modified: "",
  fileCount: 1,
};

const moveFolders = [
  currentFolder,
  {
    id: "folder-2",
    name: "Images",
    iconType: "folder",
    description: "",
    modified: "",
    fileCount: 2,
  },
];

function FolderDetailsView(props: Partial<ComponentProps<typeof FolderDetailsViewImpl>>) {
  return (
    <FolderDetailsViewImpl
      folder={currentFolder}
      onBack={() => undefined}
      onFolderAction={() => undefined}
      onToggleSearch={() => undefined}
      isSearchActive={false}
      folders={moveFolders}
      onMoveToRecycle={async () => true}
      onMoveToFolder={async () => true}
      onOpenFile={() => undefined}
      {...props}
    />
  );
}

vi.mock("../hooks/useFolderFiles", () => ({
  useFolderFiles: mocks.useFolderFiles,
}));

vi.mock("../hooks/useLibraryTags", () => ({
  useLibraryTags: () => ({
    tags: ["文档", "旅游"],
    loading: false,
    error: null,
    refetch: mocks.refetchTags,
  }),
}));

beforeEach(() => {
  mocks.useFolderFiles.mockImplementation(() => ({
    data: responseData,
    loading: false,
    error: null,
    total: responseData.total,
    hasMore: responseData.has_more,
    reload: mocks.reload,
  }));
});

describe("FolderDetailsView", () => {
  afterEach(() => {
    vi.useRealTimers();
    mocks.reload.mockClear();
    mocks.refetchTags.mockClear();
    mocks.useFolderFiles.mockClear();
  });

  it("moves selected folder files to the recycle callback and reloads", async () => {
    vi.useFakeTimers();
    const onMoveToRecycle = vi.fn(async () => true);
    renderWithI18n(
      <FolderDetailsView
        folder={{ id: "folder-1", name: "Documents", iconType: "folder", description: "", modified: "", fileCount: 1 }}
        onBack={() => undefined}
        onFolderAction={() => undefined}
        onToggleSearch={() => undefined}
        isSearchActive={false}
        onMoveToRecycle={onMoveToRecycle}
        onOpenFile={() => undefined}
      />,
    );

    const card = screen.getByText("Folder.pdf").closest("article")!;
    fireEvent.touchStart(card);
    await act(async () => {
      vi.advanceTimersByTime(800);
    });
    fireEvent.touchEnd(card);
    fireEvent.click(card);

    expect(screen.getByRole("button", { name: /移入回收站/ })).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: /移入回收站/ }));
    expect(onMoveToRecycle).not.toHaveBeenCalled();
    fireEvent.click(within(screen.getByRole("dialog")).getByRole("button", { name: /移入回收站/ }));

    await act(async () => {
      await Promise.resolve();
    });

    expect(onMoveToRecycle).toHaveBeenCalledWith(["file-1"]);
    expect(mocks.reload).toHaveBeenCalled();
  });

  it("keeps the recycle dialog and selection when the batch recycle operation fails", async () => {
    vi.useFakeTimers();
    const onFolderAction = vi.fn();
    const onMoveToRecycle = vi.fn(async () => false);
    renderWithI18n(
      <FolderDetailsView
        folder={{ id: "folder-1", name: "Documents", iconType: "folder", description: "", modified: "", fileCount: 1 }}
        onBack={() => undefined}
        onFolderAction={onFolderAction}
        onToggleSearch={() => undefined}
        isSearchActive={false}
        onMoveToRecycle={onMoveToRecycle}
        onOpenFile={() => undefined}
      />,
    );

    const card = screen.getByText("Folder.pdf").closest("article")!;
    fireEvent.touchStart(card);
    await act(async () => {
      vi.advanceTimersByTime(800);
    });
    fireEvent.touchEnd(card);
    fireEvent.click(card);

    fireEvent.click(screen.getByRole("button", { name: /移入回收站/ }));
    fireEvent.click(within(screen.getByRole("dialog")).getByRole("button", { name: /移入回收站/ }));
    await act(async () => {
      await Promise.resolve();
    });

    expect(onFolderAction).toHaveBeenCalledWith("移入回收站失败");
    expect(screen.getByRole("dialog")).toBeInTheDocument();
    expect(within(screen.getByRole("dialog")).getByRole("button", { name: /移入回收站/ })).toBeInTheDocument();
    expect(card).toHaveClass("is-selected");
    expect(mocks.reload).not.toHaveBeenCalled();
  });

  it("confirms and moves selected files to another folder", async () => {
    vi.useFakeTimers();
    const onMoveToFolder = vi.fn(async () => true);
    renderWithI18n(<FolderDetailsView onMoveToFolder={onMoveToFolder} />);

    const card = screen.getByText("Folder.pdf").closest("article")!;
    fireEvent.touchStart(card);
    await act(async () => {
      vi.advanceTimersByTime(800);
    });
    fireEvent.touchEnd(card);
    fireEvent.click(card);

    fireEvent.click(screen.getByRole("button", { name: /移动到/ }));
    expect(onMoveToFolder).not.toHaveBeenCalled();
    const dialog = within(screen.getByRole("dialog"));
    const destinationSelect = dialog.getByRole("combobox", { name: "目标文件夹" });
    expect(
      dialog.getAllByRole("option").map((option) => option.textContent),
    ).toEqual(["请选择文件夹", "Images"]);

    fireEvent.change(destinationSelect, { target: { value: "folder-2" } });
    fireEvent.click(dialog.getByRole("button", { name: /确认移动/ }));
    await act(async () => {
      await Promise.resolve();
    });

    expect(onMoveToFolder).toHaveBeenCalledWith(["file-1"], "folder-2");
    expect(mocks.reload).toHaveBeenCalled();
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /移入回收站/ })).not.toBeInTheDocument();
    expect(card).not.toHaveClass("is-selected");
  });

  it("keeps the move dialog and selection when the batch move operation fails", async () => {
    vi.useFakeTimers();
    const onFolderAction = vi.fn();
    const onMoveToFolder = vi.fn(async () => false);
    renderWithI18n(
      <FolderDetailsView onFolderAction={onFolderAction} onMoveToFolder={onMoveToFolder} />,
    );

    const card = screen.getByText("Folder.pdf").closest("article")!;
    fireEvent.touchStart(card);
    await act(async () => {
      vi.advanceTimersByTime(800);
    });
    fireEvent.touchEnd(card);
    fireEvent.click(card);

    fireEvent.click(screen.getByRole("button", { name: /移动到/ }));
    const dialog = within(screen.getByRole("dialog"));
    fireEvent.change(dialog.getByRole("combobox", { name: "目标文件夹" }), {
      target: { value: "folder-2" },
    });
    fireEvent.click(dialog.getByRole("button", { name: /确认移动/ }));
    await act(async () => {
      await Promise.resolve();
    });

    expect(onFolderAction).toHaveBeenCalledWith("移动文件失败");
    expect(screen.getByRole("dialog")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /移入回收站/ })).toBeInTheDocument();
    expect(card).toHaveClass("is-selected");
    expect(mocks.reload).not.toHaveBeenCalled();
  });

  it("supports navigation, filters, list columns, and pagination interactions", () => {
    const onToggleSearch = vi.fn();
    const onBack = vi.fn();
    renderWithI18n(
      <FolderDetailsView
        folder={{ id: "folder-1", name: "Documents", iconType: "folder", description: "", modified: "", fileCount: 1 }}
        onBack={onBack}
        onFolderAction={() => undefined}
        onToggleSearch={onToggleSearch}
        isSearchActive={false}
        onMoveToRecycle={async () => true}
        onOpenFile={() => undefined}
      />,
    );

    const searchButton = screen.getByRole("button", { name: "在当前文件夹内搜索" });
    const viewToggle = screen.getByRole("group", { name: "视图模式" });
    const sortSelectionGroup = document.querySelector(".sort-selection-group")!;
    expect(sortSelectionGroup.firstElementChild).toBe(viewToggle);
    expect(sortSelectionGroup.lastElementChild).toHaveClass("sort-controls-wrap");
    expect(viewToggle.closest(".details-header")).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: "返回" }));
    expect(onBack).toHaveBeenCalledTimes(1);

    fireEvent.click(searchButton);
    expect(onToggleSearch).toHaveBeenCalledTimes(1);
    expect(searchButton).not.toHaveClass("is-active");

    const imageTab = screen.getByRole("tab", { name: /图片/ });
    fireEvent.click(imageTab);
    expect(imageTab).toHaveClass("is-active");

    fireEvent.click(screen.getByRole("button", { name: "文档" }));
    expect(mocks.useFolderFiles).toHaveBeenLastCalledWith(
      expect.objectContaining({ tag: "文档" }),
    );

    fireEvent.click(screen.getByRole("button", { name: /列表/ }));
    expect(screen.getByRole("table")).toBeInTheDocument();
    const tableHeader = document.querySelector(".file-list-header")!;
    const columnHeaders = within(tableHeader).getAllByRole("columnheader");
    expect(columnHeaders.map((header) => header.textContent)).toEqual(["预览", "文件名", "标签", "大小"]);
    expect(screen.getByRole("table")).toHaveClass("file-list-view");
    expect(tableHeader.closest(".file-list-view")).not.toBeNull();
    expect(screen.queryByRole("columnheader", { name: "路径" })).not.toBeInTheDocument();
    expect(screen.queryByRole("columnheader", { name: "操作" })).not.toBeInTheDocument();
    expect(screen.queryByText("共 24 个文件")).not.toBeInTheDocument();
    expect(screen.queryByText("共 24 条 / 2 页")).not.toBeInTheDocument();
    expect(screen.getByRole("group", { name: "分页" })).toHaveClass("pagination-controls-group");

    fireEvent.click(screen.getByRole("button", { name: /网格/ }));
    expect(screen.getByText("Folder.pdf").closest("article")).toBeInTheDocument();

    const pageTwo = screen.getByRole("button", { name: "2" });
    fireEvent.click(pageTwo);
    expect(pageTwo).toHaveClass("is-active");
    expect(mocks.useFolderFiles).toHaveBeenLastCalledWith(
      expect.objectContaining({ pageNumber: 2 }),
    );
  });

  it("activates batch mode from the list view and preserves selection across view switches", async () => {
    vi.useFakeTimers();
    renderWithI18n(
      <FolderDetailsView
        folder={{ id: "folder-1", name: "Documents", iconType: "folder", description: "", modified: "", fileCount: 1 }}
        onBack={() => undefined}
        onFolderAction={() => undefined}
        onToggleSearch={() => undefined}
        isSearchActive={false}
        onMoveToRecycle={async () => true}
        onOpenFile={() => undefined}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: /列表/ }));
    const row = screen.getByText("Folder.pdf").closest(".file-list-row")!;
    fireEvent.touchStart(row);
    await act(async () => {
      vi.advanceTimersByTime(800);
    });
    fireEvent.touchEnd(row);
    fireEvent.click(row);

    expect(screen.getByRole("button", { name: /移入回收站/ })).toBeInTheDocument();
    expect(row).toHaveClass("is-selected");
    const checkbox = screen.getByRole("checkbox", { name: "Folder.pdf" });
    expect(checkbox).toHaveAttribute("aria-checked", "true");

    fireEvent.click(screen.getByRole("button", { name: /网格/ }));
    expect(screen.getByText("Folder.pdf").closest("article")).toHaveClass("is-selected");
    expect(screen.getByRole("button", { name: /移入回收站/ })).toBeInTheDocument();
  });

  it("renders tag filters on a dedicated single-line row", () => {
    renderWithI18n(
      <FolderDetailsView
        folder={{ id: "folder-1", name: "Documents", iconType: "folder", description: "", modified: "", fileCount: 1 }}
        onBack={() => undefined}
        onFolderAction={() => undefined}
        onToggleSearch={() => undefined}
        isSearchActive={false}
        onMoveToRecycle={async () => true}
        onOpenFile={() => undefined}
      />,
    );

    const categoryRow = screen.getByRole("tablist", { name: "文件类型" });
    const tagRow = screen.getByRole("button", { name: "全部" }).closest(".tag-filter-selector")!;
    expect(categoryRow.parentElement?.nextElementSibling).toBe(tagRow);
    expect(tagRow).toHaveClass("tag-filter-selector");
    expect(tagRow.querySelector(".tag-pills-list")).not.toBeNull();
    expect(screen.queryByRole("button", { name: "添加标签" })).not.toBeInTheDocument();
  });

  it("marks the search toggle active when the search bar is open", () => {
    renderWithI18n(
      <FolderDetailsView
        folder={{ id: "folder-1", name: "Documents", iconType: "folder", description: "", modified: "", fileCount: 1 }}
        onBack={() => undefined}
        onFolderAction={() => undefined}
        onToggleSearch={() => undefined}
        isSearchActive
        onMoveToRecycle={async () => true}
        onOpenFile={() => undefined}
      />,
    );

    expect(screen.getByRole("button", { name: "在当前文件夹内搜索" })).toHaveClass("is-active");
  });

  it("opens the file detail drawer after a single click", async () => {
    vi.useFakeTimers();
    renderWithI18n(
      <FolderDetailsView
        folder={{ id: "folder-1", name: "Documents", iconType: "folder", description: "", modified: "", fileCount: 1 }}
        onBack={() => undefined}
        onFolderAction={() => undefined}
        onToggleSearch={() => undefined}
        isSearchActive={false}
        onMoveToRecycle={async () => true}
        onOpenFile={() => undefined}
      />,
    );

    fireEvent.click(screen.getByText("Folder.pdf").closest("article")!);
    await act(async () => {
      vi.advanceTimersByTime(220);
    });

    expect(screen.getByText("文件详情")).toBeInTheDocument();
    expect(screen.getAllByText("Folder.pdf").length).toBeGreaterThan(1);
  });

  it("opens the file preview after a double click", () => {
    const onOpenFile = vi.fn();
    renderWithI18n(
      <FolderDetailsView
        folder={{ id: "folder-1", name: "Documents", iconType: "folder", description: "", modified: "", fileCount: 1 }}
        onBack={() => undefined}
        onFolderAction={() => undefined}
        onToggleSearch={() => undefined}
        isSearchActive={false}
        onMoveToRecycle={async () => true}
        onOpenFile={onOpenFile}
      />,
    );

    fireEvent.doubleClick(screen.getByText("Folder.pdf").closest("article")!);

    expect(onOpenFile).toHaveBeenCalledWith(expect.objectContaining({ file_id: "file-1" }));
  });
});
