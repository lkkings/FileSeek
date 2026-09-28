import { act, renderHook } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { useFileViewer } from "./useFileViewer";
import type { FilePreviewItem } from "../types";

const item: FilePreviewItem = {
  fileId: "file-1",
  fileName: "report.pdf",
  fileType: "document",
};

describe("useFileViewer", () => {
  it("opens and closes an in-app viewer item", () => {
    const { result } = renderHook(() => useFileViewer());

    act(() => result.current.openFile(item));
    expect(result.current).toMatchObject({ isOpen: true, item });

    act(() => result.current.onClose());
    expect(result.current).toMatchObject({ isOpen: false, item: null });
  });
});
