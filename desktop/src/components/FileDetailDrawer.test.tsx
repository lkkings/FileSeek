import { fireEvent, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { FileDetailDrawer } from "./FileDetailDrawer";
import type { FileItem } from "../services/api/search";
import { renderWithI18n } from "../test/test-utils";

const file: FileItem = {
  file_id: "file-1",
  file_name: "Details.pdf",
  file_type: "pdf",
  category: "document",
  path: "/documents/Details.pdf",
  size: 1024,
  modified: "2026-09-28T08:00:00Z",
  tags: [],
  score: 0,
  metadata: null,
  chunks: null,
};

describe("FileDetailDrawer", () => {
  it("passes the selected file to the open callback", () => {
    const onOpenAction = vi.fn();
    renderWithI18n(
      <FileDetailDrawer isOpen onClose={() => undefined} file={file} onOpenAction={onOpenAction} />,
    );

    fireEvent.click(screen.getByRole("button", { name: /打开/ }));

    expect(onOpenAction).toHaveBeenCalledWith(file);
  });
});
