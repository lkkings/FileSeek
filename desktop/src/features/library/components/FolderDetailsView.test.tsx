import { act, fireEvent, screen, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { renderWithI18n } from "../../../test/test-utils";
import type { FileItem } from "../../../services/api/search";
import { FolderDetailsView } from "./FolderDetailsView";

const mocks = vi.hoisted(() => ({ reload: vi.fn() }));

const file: FileItem = {
  file_id: "file-1",
  file_name: "Folder.pdf",
  file_type: "pdf",
  category: "document",
  path: "/documents/Folder.pdf",
  size: 1024,
  modified: "2026-09-28T08:00:00Z",
  tags: [],
  score: 0,
  metadata: null,
  chunks: null,
};

vi.mock("../hooks/useFolderFiles", () => ({
  useFolderFiles: () => ({
    data: { items: [file] },
    loading: false,
    error: null,
    reload: mocks.reload,
  }),
}));

vi.mock("../../file-search", () => ({
  SearchBar: () => null,
  useFileSearch: () => ({
    filters: { globalQuery: "" },
    updateFilter: vi.fn(),
    submitSearch: vi.fn(),
    searchState: { status: "idle", data: undefined, error: null },
  }),
}));

describe("FolderDetailsView", () => {
  afterEach(() => {
    vi.useRealTimers();
    mocks.reload.mockClear();
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

    const row = screen.getByText("Folder.pdf").closest("tr")!;
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
    expect(mocks.reload).toHaveBeenCalled();
  });
});
