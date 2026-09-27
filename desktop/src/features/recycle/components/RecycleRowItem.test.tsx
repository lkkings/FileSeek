import { fireEvent } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { RecycleRowItem } from "./RecycleRowItem";
import { renderWithI18n } from "../../../test/test-utils";
import type { RecycleItem } from "../../../services/api/recycle";

const item: RecycleItem = {
  id: "item-1",
  original_file_id: "file-1",
  original_name: "Deleted.pdf",
  original_path: "/documents/Deleted.pdf",
  deleted_at: "2026-09-28T08:00:00Z",
  file_type: "pdf",
  size: "1048576",
};

describe("RecycleRowItem", () => {
  afterEach(() => vi.useRealTimers());

  it("toggles row selection through the checkbox", () => {
    const onToggleCheck = vi.fn();
    const { container } = renderWithI18n(
      <RecycleRowItem
        item={item}
        isBatchMode
        isRowChecked
        onToggleCheck={onToggleCheck}
        onLongPress={() => undefined}
      />,
    );

    fireEvent.click(container.querySelector(".search-row-checkbox")!);

    expect(onToggleCheck).toHaveBeenCalledWith(item);
  });

  it("activates long-press selection after 800 milliseconds", () => {
    vi.useFakeTimers();
    const onLongPress = vi.fn();
    const { container } = renderWithI18n(
      <RecycleRowItem
        item={item}
        isBatchMode={false}
        isRowChecked={false}
        onToggleCheck={() => undefined}
        onLongPress={onLongPress}
      />,
    );

    fireEvent.mouseDown(container.querySelector(".recycle-row")!);
    vi.advanceTimersByTime(800);
    fireEvent.mouseUp(container.querySelector(".recycle-row")!);

    expect(onLongPress).toHaveBeenCalledWith("item-1");
  });
});
