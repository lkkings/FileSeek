import { fireEvent, screen } from "@testing-library/react";
import { act } from "react";
import { describe, expect, it, vi } from "vitest";

import { FileListRow } from "./FileListRow";
import type { FileItem } from "../services/api/search";
import { renderWithI18n } from "../test/test-utils";

const file: FileItem = {
  file_id: "file-1",
  file_name: "Report.pdf",
  file_type: "pdf",
  category: "document",
  path: "/documents/Report.pdf",
  size: 1024,
  modified: "2026-09-28T08:00:00Z",
  tags: [],
  score: 0,
  metadata: null,
  chunks: null,
};

function createProps(overrides: Partial<Parameters<typeof FileListRow>[0]>) {
  return {
    file,
    isBatchMode: false,
    isRowChecked: false,
    onRowClick: vi.fn(),
    onRowDoubleClick: vi.fn(),
    onToggleCheck: vi.fn(),
    onLongPress: vi.fn(),
    ...overrides,
  };
}

describe("FileListRow", () => {
  it("supports keyboard interaction for opening the detail drawer", async () => {
    vi.useFakeTimers();
    const onRowClick = vi.fn();
    renderWithI18n(<FileListRow {...createProps({ onRowClick })} />);

    fireEvent.keyDown(screen.getByRole("row", { name: /Report\.pdf/ }), { key: "Enter" });
    await act(async () => {
      vi.advanceTimersByTime(220);
    });

    expect(onRowClick).toHaveBeenCalledWith(file);
    vi.useRealTimers();
  });
});
